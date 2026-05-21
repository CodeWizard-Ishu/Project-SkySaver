# SkySaver n8n Workflow — Setup & Deployment Guide

## Architecture Overview

```
n8n (port 5678)
   │
   ├─ [Schedule] Every 6 hours (02:00, 08:00, 14:00, 20:00 UTC)
   │
   └─► POST /api/v1/scrape/run  ──►  FastAPI (port 8000)
                │                           │
             15s timeout              202 Accepted + job_id
                │                           │
         ┌──── job_id ◄────────────────────┘
         │
         ├─ Wait 30s
         ├─ GET /api/v1/scrape/job/{job_id}
         │     ↓ status == "running" → loop back (max 80 polls = ~40 min)
         │     ↓ status == "done"    → check alerts_sent
         │     ↓ status == "error"   → Telegram error alert
         │
         ├─ alerts_sent > 0  →  ✅ Telegram: success summary
         ├─ alerts_sent == 0 →  ⚫ Silent (noOp)
         ├─ timeout (>40min) →  ⏰ Telegram: timeout alert
         └─ API unreachable  →  🚨 Telegram: server down alert
```

---

## Workflow Nodes

| Node | Type | Purpose |
|---|---|---|
| Every 6 Hours | scheduleTrigger | Fires at 02/08/14/20 UTC |
| POST — Trigger Pipeline | httpRequest | Starts pipeline, gets job_id (202) |
| Trigger OK? | if | `success == true` |
| Set Job Context | set | Stores `job_id` + `polls_remaining=80` |
| Wait 30s Between Polls | wait | 30s pause between each poll |
| GET — Poll Job Status | httpRequest | Polls `/scrape/job/{job_id}` |
| Still Running? | if | `status == "running"` → loop |
| Decrement Counter | set | Decrements `polls_remaining` |
| Timeout? | if | `polls_remaining <= 0` |
| Pipeline Succeeded? | if | `status == "done"` |
| Alerts Sent? | if | `alerts_sent > 0` |
| Telegram: Success + Alerts | telegram | Rich summary message |
| No Alerts (quiet run) | noOp | Silent when no deal found |
| Telegram: Pipeline Error | telegram | Job error details |
| Telegram: Timeout | telegram | 40min timeout alert |
| Telegram: API Unreachable | telegram | FastAPI down alert |

---

## Local Setup (Windows Development)

### 1. Start FastAPI server
```powershell
cd "C:\Users\UTKARSH JAISWAL\Desktop\Project - SkySaver"
.\venv\Scripts\activate
uvicorn api.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

### 2. Start n8n
```powershell
n8n start
# UI opens at http://localhost:5678
```

### 3. Import workflow (one command)
```powershell
npx n8n import:workflow --input="n8n\skysaver_workflow.json"
```

### 4. Set Telegram credential in n8n UI
1. Open **http://localhost:5678**
2. Go to **Settings → Credentials → New Credential → Telegram API**
3. Enter your **Bot Token** from `.env` (`TELEGRAM_BOT_TOKEN`)
4. Save → open the SkySaver workflow → click each Telegram node → select this credential
5. Or run: `python -X utf8 scripts\activate_n8n_workflow.py` to auto-patch via SQLite

### 5. Fix the API key in HTTP Request nodes
The workflow uses `={{ $env.SKYSAVER_API_KEY }}`. Either:
- **Option A:** Set env var before starting n8n:
  ```powershell
  $env:SKYSAVER_API_KEY = "skysaver-local-dev-key-change-this"
  n8n start
  ```
- **Option B:** Edit the two HTTP nodes manually and hardcode the key value.

### 6. Activate workflow
Toggle the **Active** switch in the n8n UI. The workflow fires at 02/08/14/20 UTC.

### 7. Test manually
Click **Test workflow** in the n8n UI to trigger a run immediately.

---

## VM Deployment (Oracle Cloud A1 — Ubuntu 24.04)

### 1. SSH into VM and copy workflow
```bash
scp n8n/skysaver_workflow.json ubuntu@<VM_IP>:~/skysaver/n8n/
```

### 2. Import on VM
```bash
n8n import:workflow --input=/home/ubuntu/skysaver/n8n/skysaver_workflow.json
```

### 3. Set env var for n8n service
In `/etc/systemd/system/n8n.service` or `~/.n8n/.env`:
```ini
SKYSAVER_API_KEY=<your-production-api-key>
```
Then: `sudo systemctl daemon-reload && sudo systemctl restart n8n`

### 4. Add Telegram credential via n8n UI on VM
- Access n8n at `http://<VM_IP>:5678` (or via SSH tunnel)
- Create a **Telegram API** credential with your bot token
- Open the SkySaver workflow → link all 4 Telegram nodes to it

### 5. Verify FastAPI is running on VM
```bash
systemctl status skysaver.service
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/api/v1/scrape/run \
  -H "X-SkySaver-Key: <your-key>" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'
```

### 6. Activate the workflow in n8n UI

---

## Telegram Messages

| Situation | Message |
|---|---|
| ✅ Run complete, alerts sent | Routes/fares/alerts summary |
| ⚫ Run complete, no alerts | Silent (no message) |
| ⚠️ Pipeline error | Error details + job ID |
| ⏰ Timeout (>40 min) | Server log hint |
| 🚨 API unreachable | systemctl hint |

---

## Key API Endpoints Used by Workflow

| Method | Endpoint | Auth Header | Timeout |
|---|---|---|---|
| `POST` | `/api/v1/scrape/run` | `X-SkySaver-Key` | 15s |
| `GET` | `/api/v1/scrape/job/{job_id}` | `X-SkySaver-Key` | 12s |

**Polling math:** 80 polls × 30s = **40 minutes** max wait — comfortably covers a full pipeline run (~19 min from last real test).

**Job persistence:** All jobs are written atomically to `db/jobs.json` on every state change. If the server restarts mid-run, n8n will receive `status: error` on its next poll (rather than a 404), so it gracefully routes to the Telegram error alert.

---

## Files

| File | Purpose |
|---|---|
| `n8n/skysaver_workflow.json` | Import into n8n (local + VM) |
| `scripts/activate_n8n_workflow.py` | Patches Telegram credential IDs post-import |
| `scripts/check_n8n.py` | Inspect n8n SQLite DB |
| `db/jobs.json` | Persistent job registry (auto-created) |
