"""Director trades extraction: parsed 3Y text -> validated DirectorTradesResult."""

from pathlib import Path

import anthropic

from asx_engine.extraction.earnings import (
    MAX_OUTPUT_TOKENS,
    ExtractionRefusedError,
    supports_thinking,
)
from asx_engine.schemas.director_trades import DirectorTradesResult

DIRECTOR_TRADES_PROMPT_PATH = Path("prompts/director_trades_v2.md")


def load_prompt(path: Path = DIRECTOR_TRADES_PROMPT_PATH) -> tuple[str, str]:
    """Read a versioned prompt file -> (prompt_version, system prompt text)."""
    return path.stem, path.read_text(encoding="utf-8")


def extract_director_trades(
    document_text: str,
    *,
    client: anthropic.Anthropic,
    system_prompt: str,
    model: str,
) -> DirectorTradesResult:
    """One 3Y's parsed text -> validated DirectorTradesResult."""
    # `omit` (not None) is the SDK's "leave this parameter out" sentinel — Haiku
    # rejects any thinking config, so the key must be absent, not null.
    response = client.messages.parse(
        model=model,
        max_tokens=MAX_OUTPUT_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": document_text}],
        output_format=DirectorTradesResult,
        thinking={"type": "adaptive"} if supports_thinking(model) else anthropic.omit,
    )
    if response.parsed_output is None:
        raise ExtractionRefusedError(
            f"no parsed payload returned (stop_reason={response.stop_reason})"
        )
    return response.parsed_output
