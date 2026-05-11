#!/bin/bash
# =============================================================================
# SkySaver Deploy Script — Oracle Cloud A1, Ubuntu 24.04 ARM64
#
# Usage:
#   bash deploy/deploy.sh
#
# Run from the project root: /home/ubuntu/flight-agent/
#
# IDEMPOTENT — safe to run multiple times for both initial setup and updates.
# Aborts immediately on:
#   - Any command failure (set -e)
#   - Undefined variable reference (set -u)
#   - Pipe failure (set -o pipefail)
#   - Test suite failure
#   - Post-deploy health check failure
# =============================================================================

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────
PROJECT_DIR="/home/ubuntu/SkySaver"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_NAME="skysaver"
NGINX_CONF="/etc/nginx/sites-available/skysaver"
NGINX_ENABLED="/etc/nginx/sites-enabled/skysaver"
NGINX_HTTP_CONF="/etc/nginx/nginx.conf"

# ─── Banner ───────────────────────────────────────────────────────────────────
echo "================================================================="
echo " SkySaver Deployment"
echo " Project : $PROJECT_DIR"
echo " Time    : $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "================================================================="

# ─── Preflight: ensure we are in the project directory ───────────────────────
if [ ! -f "$PROJECT_DIR/gunicorn_conf.py" ]; then
    echo "ERROR: gunicorn_conf.py not found in $PROJECT_DIR."
    echo "       Run this script from the project root or check PROJECT_DIR."
    exit 1
fi
cd "$PROJECT_DIR"

# ─── Step 1/7: Install/update Python dependencies ────────────────────────────
echo ""
echo "[1/7] Installing Python dependencies..."
"$VENV_DIR/bin/pip" install -r requirements.txt --quiet
echo "      Done."

# ─── Step 2/7: Initialise database (idempotent — IF NOT EXISTS everywhere) ───
echo ""
echo "[2/7] Initialising database..."
"$VENV_DIR/bin/python" db/init_db.py
echo "      Done."

# ─── Step 3/7: Run full test suite — ABORT if any test fails ─────────────────
echo ""
echo "[3/7] Running test suite..."
"$VENV_DIR/bin/pytest" tests/ -q --tb=short
echo "      All tests passed."

# ─── Step 4/7: Install/update systemd service ────────────────────────────────
echo ""
echo "[4/7] Installing systemd service..."
sudo cp deploy/skysaver.service /etc/systemd/system/skysaver.service
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
echo "      Service enabled."

# ─── Step 5/7: Install/update nginx rate-limit zone (idempotent) ─────────────
echo ""
echo "[5/7] Configuring nginx..."

# Ensure the rate-limit zone exists in nginx.conf http block.
# grep -q exits 0 if found, 1 if not found. set -e would abort on 1 — use || true.
if ! grep -q "zone=skysaver:" "$NGINX_HTTP_CONF" 2>/dev/null; then
    echo "      Adding rate-limit zone to $NGINX_HTTP_CONF ..."
    # Insert after the 'http {' line — sed finds first occurrence only
    sudo sed -i '/^http {/a\\    limit_req_zone $binary_remote_addr zone=skysaver:10m rate=30r/m;' \
        "$NGINX_HTTP_CONF"
fi

sudo cp deploy/nginx_skysaver.conf "$NGINX_CONF"
if [ ! -L "$NGINX_ENABLED" ]; then
    sudo ln -s "$NGINX_CONF" "$NGINX_ENABLED"
    echo "      Symlink created: $NGINX_ENABLED -> $NGINX_CONF"
fi

# Remove the default nginx site — its catch-all conflicts with server_name _
if [ -L /etc/nginx/sites-enabled/default ]; then
    sudo rm /etc/nginx/sites-enabled/default
    echo "      Removed default nginx site."
fi

# Test nginx config — abort if invalid syntax
sudo nginx -t
sudo systemctl reload nginx
echo "      Nginx configured and reloaded."

# ─── Step 6/7: Restart service (zero-downtime rolling restart via systemd) ───
echo ""
echo "[6/7] Restarting SkySaver service..."
sudo systemctl restart "$SERVICE_NAME"
echo "      Waiting 5 seconds for service to initialise..."
sleep 5

# Check if the service started successfully
if ! sudo systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "ERROR: Service failed to start. Check logs:"
    echo "       sudo journalctl -u skysaver -n 50 --no-pager"
    exit 1
fi
echo "      Service is active."

# ─── Step 7/7: Post-deploy health check ──────────────────────────────────────
echo ""
echo "[7/7] Verifying deployment..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    --connect-timeout 5 --max-time 10 \
    http://127.0.0.1/health)

if [ "$HTTP_STATUS" = "200" ]; then
    PUBLIC_IP=$(curl -s --connect-timeout 5 --max-time 10 ifconfig.me 2>/dev/null || echo "<unknown>")
    echo ""
    echo "================================================================="
    echo " DEPLOYMENT SUCCESSFUL"
    echo "================================================================="
    echo " API base URL : http://$PUBLIC_IP/api/v1/"
    echo " Health check : http://$PUBLIC_IP/health"
    echo " Service logs : sudo journalctl -u skysaver -f"
    echo " Service status: sudo systemctl status skysaver"
    echo "================================================================="
else
    echo ""
    echo "DEPLOYMENT FAILED — health check returned HTTP $HTTP_STATUS"
    echo "Check logs: sudo journalctl -u skysaver -n 50 --no-pager"
    exit 1
fi
