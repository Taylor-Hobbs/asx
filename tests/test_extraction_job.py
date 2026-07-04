"""Tests for the earnings extractor wiring and the extraction job.

The Anthropic SDK is faked at the client boundary (duck-typed — the SDK's
own response types stay out of the tests), and the job is tested against a
structural FakeBackend exactly like the parse job. What the real API returns
is the eval harness's question, not a unit test's.
"""

from datetime import UTC
from decimal import Decimal
from types import SimpleNamespace

import pytest

from asx_engine.extraction.earnings import (
    EARNINGS_PROMPT_PATH,
    ExtractionRefusedError,
    extract_earnings,
    load_prompt,
)
from asx_engine.extraction.job import run, run_batch
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
        reporting_currency=sourced("AUD"),
        revenue=metric("24212000000", "23490000000"),
        npat=metric("1603000000", "1510000000"),
        eps_cents=metric("207", "195"),
        dividend_cents=metric("145", "140"),
    )


class TestLoadPrompt:
    def test_version_is_file_stem_and_text_is_file_contents(self) -> None:
        # The invariant is the version key equals the artifact's stem — not any
        # particular version, which changes every prompt iteration.
        version, text = load_prompt()
        assert version == EARNINGS_PROMPT_PATH.stem
        # The conventions the golden labels must share, pinned by the prompt.
        assert "statutory" in text.lower()
        assert "null" in text

    def test_default_path_is_the_versioned_artifact(self) -> None:
        assert EARNINGS_PROMPT_PATH.parent.name == "prompts"
        assert EARNINGS_PROMPT_PATH.stem.startswith("earnings_v")
        assert EARNINGS_PROMPT_PATH.suffix == ".md"


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


def batch_message(payload_json: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    """The slice of a batch-result Message that run_batch reads."""
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking"),
            SimpleNamespace(type="text", text=payload_json),
        ],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=100, output_tokens=10),
    )


def succeeded(content_hash: str, payload_json: str | None = None) -> SimpleNamespace:
    json = payload_json if payload_json is not None else earnings_result().model_dump_json()
    return SimpleNamespace(
        custom_id=content_hash,
        result=SimpleNamespace(type="succeeded", message=batch_message(json)),
    )


def errored(content_hash: str) -> SimpleNamespace:
    return SimpleNamespace(custom_id=content_hash, result=SimpleNamespace(type="errored"))


class FakeBatches:
    def __init__(self, results: list[SimpleNamespace], statuses: list[str]) -> None:
        self.created_requests: list[dict[str, object]] | None = None
        self._results = results
        self._statuses = statuses
        self.retrieved: list[str] = []

    def _batch(self, status: str) -> SimpleNamespace:
        return SimpleNamespace(
            id="batch_test_1",
            processing_status=status,
            request_counts=SimpleNamespace(processing=0, succeeded=0, errored=0),
        )

    def create(self, *, requests: list[dict[str, object]]) -> SimpleNamespace:
        self.created_requests = list(requests)
        return self._batch(self._statuses.pop(0))

    def retrieve(self, batch_id: str) -> SimpleNamespace:
        self.retrieved.append(batch_id)
        return self._batch(self._statuses.pop(0))

    def results(self, batch_id: str) -> list[SimpleNamespace]:
        return self._results


class FakeBatchClient:
    """Satisfies the slice of anthropic.Anthropic that run_batch uses."""

    def __init__(self, results: list[SimpleNamespace], statuses: list[str]) -> None:
        self.messages = SimpleNamespace(batches=FakeBatches(results, statuses))


class TestRunBatch:
    def test_submits_pending_polls_until_ended_and_saves(self) -> None:
        backend = FakeBackend({HASH_A: "text a", HASH_B: "text b"})
        client = FakeBatchClient(
            results=[succeeded(HASH_A), succeeded(HASH_B)],
            statuses=["in_progress", "in_progress", "ended"],
        )
        sleeps: list[float] = []

        summary = run_batch(
            backend,
            client,  # type: ignore[arg-type]
            model="claude-opus-4-8",
            prompt_version="earnings_v1",
            system_prompt="the versioned prompt",
            poll_seconds=30.0,
            sleep=sleeps.append,
        )

        requests = client.messages.batches.created_requests
        assert requests is not None and len(requests) == 2
        assert [r["custom_id"] for r in requests] == [HASH_A, HASH_B]
        params = requests[0]["params"]
        assert params["model"] == "claude-opus-4-8"  # type: ignore[index]
        assert params["system"] == "the versioned prompt"  # type: ignore[index]
        assert params["output_config"]["format"]["type"] == "json_schema"  # type: ignore[index]
        assert sleeps == [30.0, 30.0]  # polled until "ended"
        assert {r.content_hash for r in backend.saved} == {HASH_A, HASH_B}
        assert summary.input_tokens == 200
        assert summary.output_tokens == 20
        assert summary.failed == []

    def test_failures_are_counted_never_saved_never_fatal(self) -> None:
        backend = FakeBackend({HASH_A: "a", HASH_B: "b", HASH_C: "c"})
        client = FakeBatchClient(
            results=[
                errored(HASH_A),
                succeeded(HASH_B, payload_json='{"period": "not even the right shape"}'),
                succeeded(HASH_C),
            ],
            statuses=["ended"],
        )

        summary = run_batch(
            backend,
            client,  # type: ignore[arg-type]
            model="m",
            prompt_version="v",
            system_prompt="p",
            sleep=lambda _: None,
        )

        assert [r.content_hash for r in backend.saved] == [HASH_C]
        assert sorted(summary.failed) == [HASH_A, HASH_B]

    def test_resume_collects_without_resubmitting_and_skips_done(self) -> None:
        # HASH_A was saved before the crash; its result must not double-save.
        backend = FakeBackend({HASH_A: "a", HASH_B: "b"}, already={HASH_A})
        client = FakeBatchClient(
            results=[succeeded(HASH_A), succeeded(HASH_B)],
            statuses=["ended"],
        )

        summary = run_batch(
            backend,
            client,  # type: ignore[arg-type]
            model="m",
            prompt_version="v",
            system_prompt="p",
            resume_batch_id="batch_test_1",
            sleep=lambda _: None,
        )

        assert client.messages.batches.created_requests is None  # no resubmission
        assert [r.content_hash for r in backend.saved] == [HASH_B]
        assert summary.already_extracted == 1

    def test_nothing_pending_submits_nothing(self) -> None:
        backend = FakeBackend({HASH_A: "a"}, already={HASH_A})
        client = FakeBatchClient(results=[], statuses=[])

        summary = run_batch(
            backend,
            client,  # type: ignore[arg-type]
            model="m",
            prompt_version="v",
            system_prompt="p",
            sleep=lambda _: None,
        )

        assert client.messages.batches.created_requests is None
        assert summary.extracted == []
