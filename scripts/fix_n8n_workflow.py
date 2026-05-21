"""scripts/fix_n8n_workflow.py
Updates the SkySaver workflow to use the correct Telegram credential.
"""
import sqlite3, json, os, sys

# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

N8N_DB = r"C:\Users\UTKARSH JAISWAL\.n8n\database.sqlite"
WORKFLOW_ID = "wf-skysaver-6h-monitor"

def main():
    conn = sqlite3.connect(N8N_DB)
    cur = conn.cursor()

    # 1. List all Telegram credentials
    print("=== TELEGRAM CREDENTIALS ===")
    cur.execute("SELECT id, name, type FROM credentials_entity WHERE type='telegramApi' ORDER BY updatedAt DESC")
    creds = cur.fetchall()
    for i, (cid, cname, ctype) in enumerate(creds):
        print(f"  [{i}] id={cid!r}  name={cname!r}")

    if not creds:
        print("  ERROR: No Telegram credentials found! Create one in n8n UI first.")
        conn.close()
        return

    # Pick the most recently updated one
    CHOSEN_CRED_ID = creds[0][0]
    CHOSEN_CRED_NAME = creds[0][1]
    print(f"\n  -> Using: id={CHOSEN_CRED_ID!r}  name={CHOSEN_CRED_NAME!r}")

    # 2. Load workflow
    cur.execute("SELECT nodes FROM workflow_entity WHERE id=?", (WORKFLOW_ID,))
    row = cur.fetchone()
    if not row:
        print(f"\n  ERROR: Workflow '{WORKFLOW_ID}' not found!")
        conn.close()
        return

    nodes = json.loads(row[0])
    telegram_nodes = [n for n in nodes if n.get("type") == "n8n-nodes-base.telegram"]
    print(f"\n  Found {len(telegram_nodes)} Telegram nodes.")

    # 3. Patch all Telegram nodes
    patched = 0
    for n in nodes:
        if n.get("type") == "n8n-nodes-base.telegram":
            n["credentials"] = {
                "telegramApi": {
                    "id": CHOSEN_CRED_ID,
                    "name": CHOSEN_CRED_NAME,
                }
            }
            patched += 1
            print(f"  Patched: {n['name']!r}")

    # 4. Save
    cur.execute("UPDATE workflow_entity SET nodes=? WHERE id=?", (json.dumps(nodes), WORKFLOW_ID))
    conn.commit()
    print(f"\n  [OK] Patched {patched} nodes. Updated workflow '{WORKFLOW_ID}'.")
    print("  -> Reload the workflow in n8n UI to see the changes.")
    conn.close()

if __name__ == "__main__":
    main()
