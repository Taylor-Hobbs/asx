"""Enforce the 'as stated' convention on director_role golden labels.

For each labeled golden, fetch the parsed document text; if the labeled role
does not appear in the text (case-insensitive), null it. Prints every change.
"""

import json
import sys
from pathlib import Path

import google.cloud.storage as storage
from dotenv import load_dotenv

from asx_engine.config import load_settings
from asx_engine.parsing.pdf import PARSER_VERSION, ParsedDocument

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()
settings = load_settings()
bucket = storage.Client(project=settings.gcp_project).bucket(settings.gcs_raw_bucket)

changed = kept = 0
for path in sorted(Path("golden/director_trades").glob("*.json")):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if data["status"] != "labeled":
        continue
    blob = bucket.blob(f"parsed/{PARSER_VERSION}/{data['content_hash']}.json")
    text = ParsedDocument.model_validate_json(bytes(blob.download_as_bytes())).text().lower()
    dirty = False
    for trade in data["labels"]["trades"]:
        role = trade.get("director_role")
        if role is None:
            continue
        if role.lower() in text:
            kept += 1
            print(f"KEPT    {path.name}: {role!r} (stated in document)")
        else:
            trade["director_role"] = None
            dirty = True
            changed += 1
            print(f"NULLED  {path.name}: {role!r} (not in document text)")
    if dirty:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print(f"\n{changed} roles nulled, {kept} kept (document states them)")
