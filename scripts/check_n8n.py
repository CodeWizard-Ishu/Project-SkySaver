"""scripts/check_n8n.py — Inspect n8n SQLite database."""
import sqlite3

db = r"C:\Users\UTKARSH JAISWAL\.n8n\database.sqlite"
conn = sqlite3.connect(db)
cur = conn.cursor()

print("=== TABLES ===")
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
for row in cur.fetchall():
    print(" ", row[0])

print("\n=== WORKFLOWS ===")
cur.execute("SELECT id, name, active FROM workflow_entity ORDER BY updatedAt DESC LIMIT 10")
for row in cur.fetchall():
    print(f"  id={row[0]!r:<30} active={row[2]}  name={row[1]!r}")

print("\n=== CREDENTIALS ===")
cur.execute("SELECT id, name, type FROM credentials_entity ORDER BY updatedAt DESC LIMIT 20")
for row in cur.fetchall():
    print(f"  id={row[0]!r:<12} type={row[2]!r:<20} name={row[1]!r}")

print("\n=== USER API KEYS ===")
try:
    cur.execute("SELECT apiKey, label FROM user_api_keys ORDER BY createdAt DESC LIMIT 5")
    for row in cur.fetchall():
        print(f"  label={row[1]!r}  key={row[0]!r}")
except Exception as e:
    print(f"  (no user_api_keys table or error: {e})")

print("\n=== USERS ===")
try:
    cur.execute("SELECT id, email, role FROM user ORDER BY createdAt DESC LIMIT 5")
    for row in cur.fetchall():
        print(f"  id={row[0]!r}  email={row[1]!r}  role={row[2]!r}")
except Exception as e:
    print(f"  (error: {e})")

conn.close()
