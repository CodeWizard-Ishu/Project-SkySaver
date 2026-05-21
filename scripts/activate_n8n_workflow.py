"""scripts/activate_n8n_workflow.py
Activates the correct SkySaver workflow and deactivates old duplicates.
Run ONCE after importing the workflow.
"""
import sqlite3, sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

N8N_DB = r"C:\Users\UTKARSH JAISWAL\.n8n\database.sqlite"
TARGET_ID = "wf-skysaver-6h-monitor"   # Our canonical workflow
OLD_IDS   = ["CpF59Q8EkYHnuY6o", "IDdyVhWxHC0yryWp"]   # Old duplicates

def main():
    conn = sqlite3.connect(N8N_DB)
    cur  = conn.cursor()

    print("=== BEFORE ===")
    cur.execute("SELECT id, name, active FROM workflow_entity WHERE name LIKE '%SkySaver%' ORDER BY updatedAt DESC")
    for row in cur.fetchall():
        print(f"  id={row[0]!r:<30} active={row[2]}  name={row[1]!r}")

    # 1. Deactivate old duplicate workflows
    for old_id in OLD_IDS:
        cur.execute("UPDATE workflow_entity SET active=0 WHERE id=?", (old_id,))
        print(f"\n  Deactivated old workflow: {old_id!r}  (rows={cur.rowcount})")

    # 2. Ensure our target workflow has the Telegram credential patched
    CHOSEN_CRED_ID = "gkiIgoqrkn9WHA8D"
    CHOSEN_CRED_NAME = "Telegram API"

    import json
    cur.execute("SELECT nodes FROM workflow_entity WHERE id=?", (TARGET_ID,))
    row = cur.fetchone()
    if row:
        nodes = json.loads(row[0])
        patched = 0
        for n in nodes:
            if n.get("type") == "n8n-nodes-base.telegram":
                n["credentials"] = {
                    "telegramApi": {"id": CHOSEN_CRED_ID, "name": CHOSEN_CRED_NAME}
                }
                patched += 1
        cur.execute("UPDATE workflow_entity SET nodes=? WHERE id=?", (json.dumps(nodes), TARGET_ID))
        print(f"\n  Patched {patched} Telegram nodes with credential '{CHOSEN_CRED_ID}'.")
    else:
        print(f"\n  ERROR: Target workflow '{TARGET_ID}' not found!")

    conn.commit()

    print("\n=== AFTER ===")
    cur.execute("SELECT id, name, active FROM workflow_entity WHERE name LIKE '%SkySaver%' ORDER BY updatedAt DESC")
    for row in cur.fetchall():
        print(f"  id={row[0]!r:<30} active={row[2]}  name={row[1]!r}")

    conn.close()
    print("\n[OK] Done.")
    print("  -> Open http://localhost:5678 and activate the 'SkySaver - 6h Flight Price Monitor' workflow.")
    print("  -> Make sure you select the correct Telegram credential in each Telegram node.")

if __name__ == "__main__":
    main()
