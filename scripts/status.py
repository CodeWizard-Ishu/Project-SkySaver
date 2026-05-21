from dotenv import load_dotenv; load_dotenv()
import sqlite3, os, glob

db = os.getenv('DATABASE_PATH', './db/flight_prices.db')
conn = sqlite3.connect(db)
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM flight_prices')
total = cur.fetchone()[0]

cur.execute('SELECT route, COUNT(*) FROM flight_prices GROUP BY route ORDER BY route')
by_route = cur.fetchall()

cur.execute('SELECT MIN(travel_date), MAX(travel_date) FROM flight_prices')
date_range = cur.fetchone()

cur.execute("SELECT COUNT(*) FROM flight_prices WHERE observed_at >= '2026-05-14T17:00'")
real = cur.fetchone()[0]

conn.close()

models = glob.glob('models/lgbm*.pkl')

print('=== SkySaver Data Status ===')
print(f'Total fare rows:  {total}')
print(f'Real scraped:     {real}   (from Google Flights via Gemini)')
print(f'Synthetic seed:   {total - real} (ML bootstrap data)')
print(f'Travel dates:     {date_range[0]} to {date_range[1]}')
print()
print('By route:')
for r, c in by_route:
    print(f'  {r}: {c} rows')
print()
print(f'ML model files:   {len(models)}')
for m in models:
    size = os.path.getsize(m)
    print(f'  {os.path.basename(m)} ({size//1024}KB)')
