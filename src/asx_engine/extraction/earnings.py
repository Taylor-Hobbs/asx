"""Earnings extraction: parsed announcement text -> validated EarningsResult.

The Claude call uses the SDK's `messages.parse()`: EarningsResult's JSON
schema is sent as a structured-output constraint, the response is validated
back through the same Pydantic model, and constraints the API can't enforce
server-side (e.g. `Field(ge=0.0, le=1.0)` bounds) are checked client-side by
the SDK. One schema, one code path, no hand-rolled JSON parsing.

Prompts are versioned artifacts in prompts/ (see prompts/README.md), never
inline strings. The file's stem IS the prompt_version recorded on every
ExtractionRecord, so an eval run can name exactly which prompt produced it.
"""

from pathlib import Path

import anthropic

from asx_engine.schemas import EarningsResult

# Frontier baseline for Q1 (CLAUDE.md "Stack decisions"). The Q3 fine-tune
# benchmarks against records keyed to exactly this string.
EXTRACTION_MODEL = "claude-opus-4-8"

# Relative to the repo root, where the CLI jobs run from.
EARNINGS_PROMPT_PATH = Path("prompts/earnings_v1.md")

# The payload is a small JSON object, but adaptive thinking spends from the
# same budget and big statutory docs (~100K input tokens) warrant room to
# think before committing to numbers.
MAX_OUTPUT_TOKENS = 16_000

# Haiku does not support extended thinking. Opus and Sonnet do.
_NO_THINKING_MODELS = frozenset({"claude-haiku-4-5"})


def supports_thinking(model: str) -> bool:
    """Return True if the model accepts thinking={"type": "adaptive"}."""
    return model not in _NO_THINKING_MODELS and "haiku" not in model


class ExtractionRefusedError(RuntimeError):
    """The model returned no parseable payload (refusal or truncation)."""


def load_prompt(path: Path = EARNINGS_PROMPT_PATH) -> tuple[str, str]:
    """Read a versioned prompt file -> (prompt_version, system prompt text)."""
    return path.stem, path.read_text(encoding="utf-8")


def extract_earnings(
    document_text: str,
    *,
    client: anthropic.Anthropic,
    system_prompt: str,
    model: str = EXTRACTION_MODEL,
) -> EarningsResult:
    """One announcement's parsed text -> validated EarningsResult."""
    kwargs: dict = dict(
        model=model,
        max_tokens=MAX_OUTPUT_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": document_text}],
        output_format=EarningsResult,
    )
    if supports_thinking(model):
        kwargs["thinking"] = {"type": "adaptive"}
    response = client.messages.parse(**kwargs)
    if response.parsed_output is None:
        raise ExtractionRefusedError(
            f"no parsed payload returned (stop_reason={response.stop_reason})"
        )
    return response.parsed_output
