"""Tests for PDF parsing and the parse job.

make_pdf() below assembles a minimal-but-valid PDF byte-for-byte (objects,
streams, xref table with correct offsets) so tests exercise the REAL
pdfplumber path on real PDF structure — no fixture files to drift, no
heavyweight PDF-writing dependency, and an "empty page" is genuinely a page
with no text operators, exactly like a scanned filing.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from asx_engine.parsing.job import run
from asx_engine.parsing.pdf import (
    PARSER_VERSION,
    ParsedDocument,
    ParseQuality,
    parse_pdf,
)

PARSED_AT = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64


def make_pdf(*page_texts: str | None) -> bytes:
    """Build a valid one-or-more-page PDF. None -> a page with no text ops."""
    objects: list[bytes] = []

    def content_stream(text: str | None) -> bytes:
        ops = b"" if text is None else f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        return b"<< /Length " + str(len(ops)).encode() + b" >>\nstream\n" + ops + b"\nendstream"

    page_count = len(page_texts)
    # Object numbering: 1=catalog, 2=pages, then per page: page obj + content
    # obj, finally the shared font object.
    font_num = 3 + 2 * page_count
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(page_count))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode())
    for i, text in enumerate(page_texts):
        content_num = 4 + 2 * i
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_num} 0 R "
            f"/Resources << /Font << /F1 {font_num} 0 R >> >> >>".encode()
        )
        objects.append(content_stream(text))
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for num, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{num} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode()
    return bytes(out)


class TestParsePdf:
    def test_extracts_text_from_each_page(self) -> None:
        doc = parse_pdf(
            make_pdf("Revenue 24,212", "NPAT 1,603"), content_hash=HASH_A, parsed_at=PARSED_AT
        )
        assert doc.page_count == 2
        assert "Revenue 24,212" in doc.pages[0]
        assert "NPAT 1,603" in doc.pages[1]
        assert doc.parser_version == PARSER_VERSION

    def test_all_text_pages_classified_good(self) -> None:
        doc = parse_pdf(
            make_pdf("A full page of disclosure text here."),
            content_hash=HASH_A,
            parsed_at=PARSED_AT,
        )
        assert doc.quality is ParseQuality.GOOD
        assert doc.empty_page_count == 0

    def test_mixed_pages_classified_partial(self) -> None:
        doc = parse_pdf(
            make_pdf("A full page of disclosure text here.", None),
            content_hash=HASH_A,
            parsed_at=PARSED_AT,
        )
        assert doc.quality is ParseQuality.PARTIAL
        assert doc.empty_page_count == 1

    def test_textless_document_classified_empty(self) -> None:
        # The scanned-filing case: pages exist, no text operators anywhere.
        doc = parse_pdf(make_pdf(None, None), content_hash=HASH_A, parsed_at=PARSED_AT)
        assert doc.quality is ParseQuality.EMPTY

    def test_garbage_bytes_raise(self) -> None:
        with pytest.raises(Exception):  # noqa: B017 - any parse failure must surface, not pass silently
            parse_pdf(b"not a pdf at all", content_hash=HASH_A, parsed_at=PARSED_AT)


class TestParsedDocument:
    def test_flags_are_computed_and_serialized(self) -> None:
        doc = ParsedDocument(
            content_hash=HASH_A,
            parser_version="test_v1",
            parsed_at=PARSED_AT,
            pages=["plenty of text on this page", ""],
        )
        dumped = doc.model_dump(mode="json", exclude={"pages"})
        assert dumped["page_count"] == 2
        assert dumped["empty_page_count"] == 1
        assert dumped["total_chars"] == len("plenty of text on this page")
        assert dumped["quality"] == "partial"

    def test_text_includes_page_markers(self) -> None:
        doc = ParsedDocument(
            content_hash=HASH_A,
            parser_version="test_v1",
            parsed_at=PARSED_AT,
            pages=["first", "second"],
        )
        assert "[page 1]\nfirst" in doc.text()
        assert "[page 2]\nsecond" in doc.text()

    def test_naive_parsed_at_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ParsedDocument(
                content_hash=HASH_A,
                parser_version="test_v1",
                parsed_at=datetime(2026, 6, 11),  # no tzinfo
                pages=["text"],
            )


class FakeBackend:
    """Satisfies ParseBackend structurally."""

    def __init__(self, pdfs: dict[str, bytes], already: set[str] | None = None) -> None:
        self._pdfs = pdfs
        self._already = already or set()
        self.texts: list[ParsedDocument] = []
        self.flushes: list[list[ParsedDocument]] = []
        self.loads: list[str] = []

    def announcement_hashes(self) -> set[str]:
        return set(self._pdfs)

    def parsed_hashes(self, parser_version: str) -> set[str]:
        return self._already

    def load_pdf(self, content_hash: str) -> bytes:
        self.loads.append(content_hash)
        return self._pdfs[content_hash]

    def save_text(self, document: ParsedDocument) -> None:
        self.texts.append(document)

    def append_rows(self, documents: list[ParsedDocument]) -> None:
        self.flushes.append(list(documents))

    @property
    def saved(self) -> list[ParsedDocument]:
        """All rows that reached BigQuery, across every flush."""
        return [d for flush in self.flushes for d in flush]


class TestRun:
    def test_parses_all_pending(self) -> None:
        backend = FakeBackend({HASH_A: make_pdf("alpha"), HASH_B: make_pdf("beta")})
        summary = run(backend)
        assert {d.content_hash for d in backend.saved} == {HASH_A, HASH_B}
        assert len(summary.parsed) == 2

    def test_already_parsed_skipped_without_download(self) -> None:
        backend = FakeBackend(
            {HASH_A: make_pdf("alpha"), HASH_B: make_pdf("beta")}, already={HASH_A}
        )
        summary = run(backend)
        # Idempotency: the parsed document is never even downloaded again.
        assert backend.loads == [HASH_B]
        assert summary.already_parsed == 1
        assert [d.content_hash for d in summary.parsed] == [HASH_B]

    def test_nothing_pending_is_a_clean_noop(self) -> None:
        backend = FakeBackend({HASH_A: make_pdf("alpha")}, already={HASH_A})
        summary = run(backend)
        assert backend.loads == []
        assert summary.parsed == []
        assert backend.flushes == []  # no empty load job

    def test_rows_flush_batched_with_text_uploaded_per_document(self) -> None:
        # One load job for the batch (the 1,500 jobs/day quota lesson, second
        # offender), while text artifacts upload as each document parses.
        backend = FakeBackend({HASH_A: make_pdf("alpha"), HASH_B: make_pdf("beta")})
        run(backend)
        assert len(backend.texts) == 2
        assert [len(f) for f in backend.flushes] == [2]
