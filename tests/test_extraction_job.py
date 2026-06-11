"""Tests for the earnings extractor wiring and the extraction job.

The Anthropic SDK is faked at the client boundary (duck-typed — the SDK's
own response types stay out of the tests), and the job is tested against a
structural FakeBackend exactly like the parse job. What the real API returns
is the eval harness's question, not a unit test's.
"""

from datetime import UTC
from decimal import Decimal

import pytest

from asx_engine.extraction.earnings import (
    EARNINGS_PROMPT_PATH,
    ExtractionRefusedError,
    extract_earnings,
    load_prompt,
)
from asx_engine.extraction.job import run
from asx_engine.schemas import EarningsResult, ExtractionRecord, ReportedMetric, SourcedField

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def sourced(value: object, quote: str | None = "quoted") -> SourcedField:  # type: ignore[type-arg]
    return SourcedField(value=value, confidence=0.9, source_quote=quote, page=1)


def metric(current: str, prior: str) -> ReportedMetric:
    return ReportedMetric(current=sourced(Decimal(current)), prior=sourced(Decimal(prior)))


def earnings_result(period: str = "FY2026") -> EarningsResult:
    return EarningsResult(
        period=sourced(period),
        revenue_aud=metric("24212000000", "23490000000"),
        npat_aud=metric("1603000000", "1510000000"),
        eps_cents=metric("207", "195"),
        dividend_cents=metric("145", "140"),
    )


class TestLoadPrompt:
    def test_version_is_file_stem_and_text_is_file_contents(self) -> None:
        version, text = load_prompt()
        assert version == "earnings_v1"
        # The conventions the golden labels must share, pinned by the prompt.
        assert "STATUTORY" in text
        assert "null" in text

    def test_default_path_is_the_versioned_artifact(self) -> None:
        assert EARNINGS_PROMPT_PATH.name == "earnings_v1.md"


class FakeParseResponse:
    def __init__(self, parsed_output: EarningsResult | None, stop_reason: str = "end_turn"):
        self.parsed_output = parsed_output
        self.stop_reason = stop_reason


class FakeMessages:
    def __init__(self, response: FakeParseResponse) -> None:
        self._response = response
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> FakeParseResponse:
        self.calls.append(kwargs)
        return self._response


class FakeClient:
    """Satisfies the slice of anthropic.Anthropic that extract_earnings uses."""

    def __init__(self, response: FakeParseResponse) -> None:
        self.messages = FakeMessages(response)


class TestExtractEarnings:
    def test_returns_validated_payload_and_wires_the_call(self) -> None:
        expected = earnings_result()
        client = FakeClient(FakeParseResponse(expected))

        result = extract_earnings(
            "[page 1]\nRevenue 24,212",
            client=client,  # type: ignore[arg-type]
            system_prompt="the versioned prompt",
            model="claude-opus-4-8",
        )

        assert result is expected
        (call,) = client.messages.calls
        assert call["model"] == "claude-opus-4-8"
        assert call["system"] == "the versioned prompt"
        assert call["output_format"] is EarningsResult
        assert call["thinking"] == {"type": "adaptive"}
        assert call["messages"] == [{"role": "user", "content": "[page 1]\nRevenue 24,212"}]

    def test_missing_payload_raises_with_stop_reason(self) -> None:
        client = FakeClient(FakeParseResponse(None, stop_reason="refusal"))
        with pytest.raises(ExtractionRefusedError, match="refusal"):
            extract_earnings(
                "text",
                client=client,  # type: ignore[arg-type]
                system_prompt="prompt",
            )


class FakeBackend:
    """Satisfies ExtractionBackend structurally."""

    def __init__(self, texts: dict[str, str], already: set[str] | None = None) -> None:
        self._texts = texts
        self._already = already or set()
        self.saved: list[ExtractionRecord[EarningsResult]] = []
        self.loads: list[str] = []

    def parsed_hashes(self, parser_version: str) -> set[str]:
        return set(self._texts)

    def extracted_hashes(self, model: str, prompt_version: str) -> set[str]:
        return self._already

    def load_text(self, content_hash: str) -> str:
        self.loads.append(content_hash)
        return self._texts[content_hash]

    def save(self, record: ExtractionRecord[EarningsResult]) -> None:
        self.saved.append(record)


def fake_extractor(document_text: str) -> EarningsResult:
    return earnings_result()


class TestRun:
    def test_extracts_all_pending_and_stamps_provenance(self) -> None:
        backend = FakeBackend({HASH_A: "text a", HASH_B: "text b"})
        summary = run(
            backend, fake_extractor, model="claude-opus-4-8", prompt_version="earnings_v1"
        )

        assert {r.content_hash for r in backend.saved} == {HASH_A, HASH_B}
        assert len(summary.extracted) == 2
        record = backend.saved[0]
        # The reproducibility envelope: every record names what produced it.
        assert record.model == "claude-opus-4-8"
        assert record.prompt_version == "earnings_v1"
        assert record.extracted_at.tzinfo is UTC

    def test_already_extracted_skipped_without_download(self) -> None:
        backend = FakeBackend({HASH_A: "text a", HASH_B: "text b"}, already={HASH_A})
        summary = run(backend, fake_extractor, model="m", prompt_version="v")

        # Idempotency: completed work is never even downloaded again.
        assert backend.loads == [HASH_B]
        assert summary.already_extracted == 1
        assert [r.content_hash for r in summary.extracted] == [HASH_B]

    def test_limit_takes_a_deterministic_slice_and_reports_the_rest(self) -> None:
        backend = FakeBackend({HASH_C: "c", HASH_A: "a", HASH_B: "b"})
        summary = run(backend, fake_extractor, model="m", prompt_version="v", limit=2)

        # Pending work is sorted before slicing, so --limit is reproducible.
        assert backend.loads == [HASH_A, HASH_B]
        assert summary.pending_after_limit == 1

    def test_nothing_pending_is_a_clean_noop(self) -> None:
        backend = FakeBackend({HASH_A: "text a"}, already={HASH_A})
        summary = run(backend, fake_extractor, model="m", prompt_version="v")
        assert backend.loads == []
        assert summary.extracted == []
