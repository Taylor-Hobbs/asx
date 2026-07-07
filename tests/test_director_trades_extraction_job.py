"""Tests for the director-trades extraction job: scopes, sync run, batch run.

Same structural fakes as test_extraction_job — the scope arithmetic and the
batch submit/collect plumbing are what these pin down. Payload correctness is
the eval harness's territory; an empty DirectorTradesResult is a valid payload
and keeps these tests about the plumbing.
"""

from types import SimpleNamespace

from asx_engine.extraction.director_trades_job import run, run_batch
from asx_engine.schemas import ExtractionRecord
from asx_engine.schemas.director_trades import DirectorTradesResult

HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64

EMPTY_PAYLOAD = DirectorTradesResult(trades=[])


def fake_extractor(document_text: str) -> DirectorTradesResult:
    return EMPTY_PAYLOAD


class FakeBackend:
    def __init__(
        self,
        golden: dict[str, str] | None = None,
        corpus: dict[str, str] | None = None,
        already: set[str] | None = None,
    ) -> None:
        self._golden = golden or {}
        self._corpus = corpus or {}
        self._already = already or set()
        self.loads: list[str] = []
        self.saved: list[ExtractionRecord[DirectorTradesResult]] = []
        self.flushes: list[int] = []

    def golden_hashes(self) -> set[str]:
        return set(self._golden)

    def corpus_hashes(self) -> set[str]:
        return set(self._corpus)

    def extracted_hashes(self, model: str, prompt_version: str) -> set[str]:
        return set(self._already)

    def load_text(self, content_hash: str) -> str:
        self.loads.append(content_hash)
        return (self._golden | self._corpus)[content_hash]

    def save_records(self, records: list[ExtractionRecord[DirectorTradesResult]]) -> None:
        self.flushes.append(len(records))
        self.saved.extend(records)


class TestScopes:
    def test_golden_scope_ignores_corpus_documents(self) -> None:
        backend = FakeBackend(golden={HASH_A: "golden doc"}, corpus={HASH_B: "corpus doc"})
        run(backend, fake_extractor, model="m", prompt_version="v", scope="golden")
        assert backend.loads == [HASH_A]

    def test_corpus_scope_ignores_unparsed_goldens(self) -> None:
        backend = FakeBackend(golden={HASH_A: "golden doc"}, corpus={HASH_B: "corpus doc"})
        run(backend, fake_extractor, model="m", prompt_version="v", scope="corpus")
        assert backend.loads == [HASH_B]

    def test_already_extracted_skipped_in_either_scope(self) -> None:
        backend = FakeBackend(corpus={HASH_A: "a", HASH_B: "b"}, already={HASH_A})
        summary = run(backend, fake_extractor, model="m", prompt_version="v", scope="corpus")
        assert backend.loads == [HASH_B]
        assert summary.already_extracted == 1

    def test_limit_slices_deterministically(self) -> None:
        backend = FakeBackend(corpus={HASH_C: "c", HASH_A: "a", HASH_B: "b"})
        summary = run(
            backend, fake_extractor, model="m", prompt_version="v", scope="corpus", limit=2
        )
        assert backend.loads == [HASH_A, HASH_B]  # sorted before slicing
        assert summary.pending_after_limit == 1


# --- batch plumbing ---------------------------------------------------------


def batch_message(payload_json: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=payload_json)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=100, output_tokens=10),
    )


def succeeded(content_hash: str, payload_json: str | None = None) -> SimpleNamespace:
    json = payload_json if payload_json is not None else EMPTY_PAYLOAD.model_dump_json()
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

    def _batch(self, status: str) -> SimpleNamespace:
        return SimpleNamespace(
            id="batch_3y_1",
            processing_status=status,
            request_counts=SimpleNamespace(processing=0, succeeded=0, errored=0),
        )

    def create(self, *, requests: list[dict[str, object]]) -> SimpleNamespace:
        self.created_requests = list(requests)
        return self._batch(self._statuses.pop(0))

    def retrieve(self, batch_id: str) -> SimpleNamespace:
        return self._batch(self._statuses.pop(0))

    def results(self, batch_id: str) -> list[SimpleNamespace]:
        return self._results


class FakeBatchClient:
    def __init__(self, results: list[SimpleNamespace], statuses: list[str]) -> None:
        self.messages = SimpleNamespace(batches=FakeBatches(results, statuses))


def _run_batch(backend: FakeBackend, client: FakeBatchClient, **kw: object):
    defaults: dict = {
        "model": "claude-haiku-4-5",
        "prompt_version": "director_trades_v3",
        "system_prompt": "the versioned prompt",
        "scope": "corpus",
        "poll_seconds": 30.0,
        "sleep": lambda _s: None,
    }
    defaults.update(kw)
    return run_batch(backend, client, **defaults)  # type: ignore[arg-type]


class TestRunBatch:
    def test_submits_corpus_pending_and_saves_on_collection(self) -> None:
        backend = FakeBackend(corpus={HASH_A: "text a", HASH_B: "text b"})
        client = FakeBatchClient(
            results=[succeeded(HASH_A), succeeded(HASH_B)],
            statuses=["in_progress", "ended"],
        )
        summary = _run_batch(backend, client)
        requests = client.messages.batches.created_requests
        assert requests is not None and len(requests) == 2
        assert {r.content_hash for r in backend.saved} == {HASH_A, HASH_B}
        assert summary.failed == []
        assert backend.saved[0].prompt_version == "director_trades_v3"
        # Collection batches its BQ writes: both records in ONE flush, not
        # one load job each (the 1,500 jobs/day quota, third offender).
        assert backend.flushes == [2]

    def test_haiku_requests_carry_no_thinking_param(self) -> None:
        # The bug that errored 26/26 once: haiku rejects any thinking config.
        backend = FakeBackend(corpus={HASH_A: "text a"})
        client = FakeBatchClient(results=[succeeded(HASH_A)], statuses=["ended"])
        _run_batch(backend, client, model="claude-haiku-4-5")
        (request,) = client.messages.batches.created_requests
        assert "thinking" not in request["params"]

    def test_errored_document_is_counted_failed_never_saved(self) -> None:
        backend = FakeBackend(corpus={HASH_A: "a", HASH_B: "b"})
        client = FakeBatchClient(
            results=[succeeded(HASH_A), errored(HASH_B)],
            statuses=["ended"],
        )
        summary = _run_batch(backend, client)
        assert [r.content_hash for r in backend.saved] == [HASH_A]
        assert summary.failed == [HASH_B]

    def test_invalid_payload_is_counted_failed_never_saved(self) -> None:
        backend = FakeBackend(corpus={HASH_A: "a"})
        client = FakeBatchClient(
            results=[succeeded(HASH_A, payload_json='{"not": "a result"}')],
            statuses=["ended"],
        )
        summary = _run_batch(backend, client)
        assert backend.saved == []
        assert summary.failed == [HASH_A]

    def test_resume_collects_without_resubmitting(self) -> None:
        backend = FakeBackend(corpus={HASH_A: "a"})
        client = FakeBatchClient(results=[succeeded(HASH_A)], statuses=["ended"])
        summary = _run_batch(backend, client, resume_batch_id="batch_3y_1")
        assert client.messages.batches.created_requests is None  # no resubmission
        assert [r.content_hash for r in backend.saved] == [HASH_A]
        assert summary.failed == []
