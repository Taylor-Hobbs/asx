"""One-off: extract the 23 earnings goldens with Opus on the v7 prompt.

    uv run python scripts/_opus_v7_golden.py

Golden-scoped ONLY — never touches the broad corpus (the stock job's pending
set would extract 1,600+ docs on Opus). Idempotent: hashes already extracted
for (claude-opus-4-8, earnings_v7) are skipped. After this, score with:

    uv run python -m asx_engine.eval.job --model claude-opus-4-8 --prompt-version earnings_v7
"""

import sys
from pathlib import Path

import anthropic
import structlog
from dotenv import load_dotenv

from asx_engine.config import load_settings
from asx_engine.extraction.earnings import extract_earnings, load_prompt
from asx_engine.extraction.job import GcpExtractionBackend
from asx_engine.schemas import (
    EarningsResult,
    ExtractionRecord,
    GoldenLabel,
    LabelStatus,
    utc_now,
)

log = structlog.get_logger()

OPUS = "claude-opus-4-8"
LABELS_DIR = Path("golden/labels")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    load_dotenv()
    settings = load_settings()
    prompt_version, system_prompt = load_prompt()
    assert prompt_version == "earnings_v7", prompt_version
    client = anthropic.Anthropic()
    backend = GcpExtractionBackend(settings)

    goldens = []
    for path in sorted(LABELS_DIR.glob("*.json")):
        label = GoldenLabel.model_validate_json(path.read_text(encoding="utf-8-sig"))
        if label.status is LabelStatus.LABELED:
            goldens.append(label)
    done = backend.extracted_hashes(OPUS, prompt_version)
    pending = [g for g in goldens if g.content_hash not in done]
    log.info("opus_v7.start", goldens=len(goldens), already_done=len(done), pending=len(pending))

    records: list[ExtractionRecord[EarningsResult]] = []
    failed: list[str] = []
    for i, golden in enumerate(pending, 1):
        text = backend.load_text(golden.content_hash)
        try:
            payload = extract_earnings(text, client=client, system_prompt=system_prompt, model=OPUS)
        except Exception as exc:  # one bad doc must not kill the run
            failed.append(golden.content_hash)
            log.warning("opus_v7.failed", ticker=golden.ticker, error=str(exc))
            continue
        records.append(
            ExtractionRecord[EarningsResult](
                content_hash=golden.content_hash,
                model=OPUS,
                prompt_version=prompt_version,
                extracted_at=utc_now(),
                payload=payload,
            )
        )
        log.info(
            "opus_v7.extracted",
            n=f"{i}/{len(pending)}",
            ticker=golden.ticker,
            npat=str(payload.npat.current.value),
        )

    backend.save_records(records)
    log.info("opus_v7.done", extracted=len(records), failed=len(failed))
    if failed:
        log.warning("opus_v7.failed_hashes", hashes=failed)


if __name__ == "__main__":
    main()
