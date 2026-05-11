"""gunicorn_conf.py — Production Gunicorn configuration for SkySaver.

Oracle A1 VPS: 4 vCPU / 24 GB RAM (ARM64, Ubuntu 24.04)

Worker count rationale:
  Standard formula (2*cores)+1 = 9 would OOM with LightGBM models loaded per
  worker (preload_app=True shares the model via CoW, but still ~600MB resident).
  3 workers is a deliberate conservative choice: enough for concurrent n8n +
  dashboard requests while leaving headroom for the 8GB MemoryMax cap and
  the OS + n8n process (~6GB combined).

Timeout rationale:
  The pipeline run (scrape → forecast → analyse → alert) takes 2–5 minutes per
  run against live APIs. 600s (10 min) gives a full 2x safety margin.
  nginx proxy_read_timeout=700s on /api/v1/scrape/run exceeds this by 100s so
  nginx never cuts the connection before gunicorn returns the response.
"""

import os

# ── Workers ───────────────────────────────────────────────────────────────────
workers = 3
worker_class = "uvicorn.workers.UvicornWorker"

# ── Binding ───────────────────────────────────────────────────────────────────
bind = "127.0.0.1:8000" # localhost only — nginx proxies externally

# ── Timeouts ─────────────────────────────────────────────────────────────────
timeout = 600   # 10 minutes — covers full pipeline run
graceful_timeout = 60   # time to finish in-flight requests on SIGTERM
keepalive = 5           # seconds to keep idle client connections alive

# ── Worker lifecycle ──────────────────────────────────────────────────────────
max_requests = 500       # restart worker after N requests to prevent memory leaks
max_requests_jitter = 50  # ± jitter prevents all workers restarting simultaneously

# ── Memory efficiency ─────────────────────────────────────────────────────────
preload_app = True       # load app + LightGBM model in master before forking;
                          # workers share read-only memory pages via CoW → saves ~1.5GB

# ── Logging ───────────────────────────────────────────────────────────────────
accesslog = "-"           # stdout → captured by journald via StandardOutput=journal
errorlog = "-"            # stderr → captured by journald via StandardError=journal
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(D)s'
)                         # D = request time in microseconds

# ── Process identity ──────────────────────────────────────────────────────────
proc_name = "skysaver"
