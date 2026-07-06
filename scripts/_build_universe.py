"""Parse the Wikipedia S&P/ASX 200 constituents table into data/universe/."""

import csv
import os
import sys
from pathlib import Path

from bs4 import BeautifulSoup

OUT = Path("data/universe/asx200_2026-04-05_wikipedia.csv")

sys.stdout.reconfigure(encoding="utf-8")
html = Path(os.environ["TEMP"], "asx200_wiki.html").read_text(encoding="utf-8-sig")
soup = BeautifulSoup(html, "html.parser")

rows = []
for table in soup.find_all("table", class_="wikitable"):
    headers = [th.get_text(strip=True).lower() for th in table.find_all("th")[:5]]
    if not any("code" in h or "symbol" in h or "ticker" in h for h in headers):
        continue
    for tr in table.find_all("tr")[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) >= 2 and cells[0].isupper() and 2 <= len(cells[0]) <= 5:
            sector = cells[2] if len(cells) > 2 else ""
            rows.append({"ticker": cells[0], "company": cells[1], "sector": sector})
    if len(rows) > 150:
        break

print(f"parsed {len(rows)} constituents")
print("first 5:", [r["ticker"] for r in rows[:5]])
print("last 5:", [r["ticker"] for r in rows[-5:]])

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["ticker", "company", "sector"])
    w.writeheader()
    w.writerows(rows)
print(f"wrote {OUT}")
