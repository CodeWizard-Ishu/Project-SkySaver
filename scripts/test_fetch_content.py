from dotenv import load_dotenv; load_dotenv()
from agents.scraper_agent import TinyFishClient, _build_google_flights_goal
from datetime import date
import sys, os

tf = TinyFishClient()
url = _build_google_flights_goal('NAG', 'DEL', date(2026, 8, 20))

with open('fetch_content_raw.txt', 'w', encoding='utf-8') as f:
    f.write(f"URL: {url}\n\n")
    raw = tf.call_fetch(url, 'NAG-DEL')
    f.write(f"Length: {len(raw)} chars\n\n")
    f.write("=== FULL CONTENT ===\n")
    f.write(raw)

print(f"Written to fetch_content_raw.txt ({len(raw)} chars)")
# Also show lines that contain price-like patterns
import re
price_lines = [l for l in raw.splitlines() if re.search(r'\d{3,6}|INR|Rs|₹|fare|price|flight|IndiGo|SpiceJet|Air India', l, re.I)]
print(f"Price-signal lines ({len(price_lines)}):")
for l in price_lines[:20]:
    print(f"  {l.strip()[:120]}")
