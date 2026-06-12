"""Validate every golden label file and report labeling progress.

    uv run python scripts/validate_goldens.py

Run it as you label: catches malformed JSON, schema violations (a "labeled"
file with no labeler, an "excluded" file with no reason), and shows how far
through the corpus you are. Exits non-zero on any invalid file so it can
gate CI later.
"""

import sys
from pathlib import Path

from pydantic import ValidationError

from asx_engine.schemas import GoldenLabel, LabelStatus

LABELS_DIR = Path("golden/labels")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    paths = sorted(LABELS_DIR.glob("*.json"))
    if not paths:
        print(f"no label files in {LABELS_DIR}/ — run scripts/make_golden_stubs.py first")
        raise SystemExit(1)

    counts: dict[LabelStatus, int] = dict.fromkeys(LabelStatus, 0)
    invalid = 0
    for path in paths:
        try:
            label = GoldenLabel.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValidationError, ValueError) as exc:
            invalid += 1
            print(f"INVALID  {path.name}\n         {exc}")
            continue
        counts[label.status] += 1
        if label.status is LabelStatus.UNLABELED:
            print(f"todo     {path.name}")

    total = len(paths)
    print(
        f"\n{total} files: {counts[LabelStatus.LABELED]} labeled, "
        f"{counts[LabelStatus.EXCLUDED]} excluded, "
        f"{counts[LabelStatus.UNLABELED]} to go, {invalid} invalid"
    )
    if invalid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
