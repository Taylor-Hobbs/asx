from pathlib import Path

from pydantic import ValidationError

from asx_engine.schemas.director_trades import DirectorTradeGoldenLabel

bad = 0
for f in sorted(Path("golden/director_trades").glob("*.json")):
    try:
        DirectorTradeGoldenLabel.model_validate_json(f.read_text(encoding="utf-8-sig"))
    except ValidationError as exc:
        bad += 1
        print(f"\n{f.name}")
        for e in exc.errors():
            loc = ".".join(str(p) for p in e["loc"])
            print(f"  {loc}: {e['msg']}  (input: {e.get('input')!r})")
print(f"\n{bad} file(s) fail validation")
