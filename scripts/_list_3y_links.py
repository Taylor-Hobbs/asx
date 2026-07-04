import json
from pathlib import Path

files = sorted(Path("golden/director_trades").glob("*.json"))
for f in files:
    d = json.loads(f.read_text(encoding="utf-8"))
    if d["status"] == "excluded":
        continue
    ids_id = d["announcement_id"]
    url = f"https://www.asx.com.au/asx/v2/statistics/displayAnnouncement.do?display=pdf&idsId={ids_id}"
    print(f"{d['ticker']:<6} {d['headline']:<50} {url}")
