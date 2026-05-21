"""
scripts/run_pipeline.py

Triggers a SkySaver pipeline run via the async API and polls until complete.
The /scrape/run endpoint now returns 202 immediately with a job_id.
This script polls /scrape/job/{job_id} every 15 seconds until done.
"""

import requests
import json
import time
import sys

BASE = 'http://127.0.0.1:8000'
HEADERS = {'X-SkySaver-Key': 'skysaver-local-dev-key-change-this', 'Content-Type': 'application/json'}
POLL_INTERVAL = 15   # seconds between status checks
MAX_WAIT = 7200      # 2 hours maximum wait

print('=== SkySaver Pipeline Run ===')
print(f'Started at: {time.strftime("%H:%M:%S")}')
print()

# --- Step 1: Trigger the pipeline (returns 202 + job_id immediately) ---
try:
    r = requests.post(
        f'{BASE}/api/v1/scrape/run',
        headers=HEADERS,
        json={'dry_run': False},
        timeout=30,   # Only needs to wait for the 202 response, not the full run
    )
except requests.exceptions.ConnectionError:
    print('[ERROR] Cannot connect to API server at localhost:8000')
    print('        Make sure uvicorn is running: uvicorn api.main:create_app --factory ...')
    sys.exit(1)
except requests.exceptions.Timeout:
    print('[ERROR] API server did not respond within 30s')
    sys.exit(1)

if r.status_code == 409:
    d = r.json()
    print(f'[INFO] A pipeline run is already in progress.')
    # Extract job_id (8-char hex) from the conflict error message
    import re
    msg = str(d.get('error', ''))
    match = re.search(r'/scrape/job/([a-f0-9]{8})', msg)
    if match:
        job_id = match.group(1)
        print(f'       Attaching to existing job: {job_id}')
    else:
        print(f'       {msg}')
        sys.exit(0)
elif r.status_code not in (200, 202):
    print(f'[ERROR] Unexpected status {r.status_code}: {r.text[:500]}')
    sys.exit(1)
else:
    d = r.json()
    data = d.get('data', {})
    job_id = data.get('job_id')
    print(f'[OK] Pipeline job started: job_id={job_id}')
    print(f'     Poll URL: {data.get("poll_url")}')

if not job_id:
    print('[ERROR] No job_id in response')
    sys.exit(1)

print()

# --- Step 2: Poll until complete ---
t_start = time.time()
last_elapsed = 0

while True:
    elapsed = round(time.time() - t_start)

    # Print a heartbeat every POLL_INTERVAL seconds
    if elapsed - last_elapsed >= POLL_INTERVAL or elapsed < 5:
        try:
            poll = requests.get(
                f'{BASE}/api/v1/scrape/job/{job_id}',
                headers=HEADERS,
                timeout=10,
            )
        except requests.exceptions.RequestException as e:
            print(f'  [{time.strftime("%H:%M:%S")}] Poll error: {e}')
            time.sleep(POLL_INTERVAL)
            continue

        if not poll.ok:
            print(f'  [{time.strftime("%H:%M:%S")}] Poll HTTP {poll.status_code}: {poll.text[:200]}')
            time.sleep(POLL_INTERVAL)
            continue

        pd = poll.json().get('data', {})
        job_status = pd.get('status', '?')
        job_elapsed = pd.get('elapsed_seconds', elapsed)
        last_elapsed = elapsed

        if job_status == 'running':
            print(f'  [{time.strftime("%H:%M:%S")}] Status: running | Elapsed: {job_elapsed}s ...')

        elif job_status == 'done':
            result = pd.get('result', {})
            total_time = round(time.time() - t_start, 1)
            print()
            print(f'=== DONE in {total_time}s ===')
            print(f'  Routes attempted:    {result.get("routes_attempted")}')
            print(f'  Routes succeeded:    {result.get("routes_succeeded")}')
            print(f'  Routes failed:       {result.get("routes_failed")}')
            print(f'  Total fares scraped: {result.get("total_fares_scraped")}')
            print(f'  Alerts sent:         {result.get("alerts_sent")}')
            print(f'  Retrain triggered:   {result.get("retrain_triggered")}')
            errs = result.get('errors', [])
            if errs:
                print(f'  Errors ({len(errs)}):')
                for e in errs[:5]:
                    print(f'    - {e}')
            with open('pipeline_result.json', 'w') as f:
                json.dump(result, f, indent=2)
            print()
            print('Full result saved to pipeline_result.json')
            sys.exit(0)

        elif job_status == 'error':
            print()
            print(f'=== ERROR ===')
            print(f'  {pd.get("error")}')
            sys.exit(1)

        else:
            print(f'  [{time.strftime("%H:%M:%S")}] Unknown status: {job_status}')

    if elapsed > MAX_WAIT:
        print(f'[TIMEOUT] Job did not complete within {MAX_WAIT}s')
        sys.exit(1)

    time.sleep(5)
