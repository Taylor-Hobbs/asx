"""PDF -> text with parse-quality flags.

Native-text extraction only (pdfplumber). OCR fallback is deliberately NOT
built yet — the Q1 corpus is recent filings from large caps, which are born
digital. The quality flags below are what will *tell us* when OCR becomes
necessary: a document classified EMPTY is a scanned filing.

Parser output is versioned (PARSER_VERSION) the same way prompts are:
extraction accuracy depends on parse quality, so an eval run is only
reproducible if it can name the exact parser that produced its text. A
better parser later = a new version string = new records, never overwrites.
"""

import io
from enum import StrEnum

import pdfplumber
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, computed_field

PARSER_VERSION = "pdfplumber_v1"

# A page yielding fewer characters than this is "empty" — either genuinely
# blank or a scanned image. 20 chars allows for page numbers and stray marks
# while still catching image-only pages.
EMPTY_PAGE_CHAR_THRESHOLD = 20


class ParseQuality(StrEnum):
    """Document-level verdict, derived from per-page results.

    GOOD    — every page produced text; extraction can trust the parse.
    PARTIAL — some pages empty (mixed scan, or decorative pages); extraction
              may work but source-span audits should be careful.
    EMPTY   — no page produced text: a scanned filing, the OCR queue.
    """

    GOOD = "good"
    PARTIAL = "partial"
    EMPTY = "empty"


class ParsedDocument(BaseModel):
    """Parsed text plus the flags that describe how trustworthy it is.

    The flag fields are @computed_field properties: derived from `pages`,
    impossible to set inconsistently, but still included in model_dump() —
    so the BigQuery row and the GCS JSON carry them without us maintaining
    two copies of the logic.
    """

    model_config = ConfigDict(frozen=True)

    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    parser_version: str = Field(min_length=1)
    parsed_at: AwareDatetime
    pages: list[str]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def page_count(self) -> int:
        return len(self.pages)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def empty_page_count(self) -> int:
        return sum(1 for p in self.pages if len(p.strip()) < EMPTY_PAGE_CHAR_THRESHOLD)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_chars(self) -> int:
        return sum(len(p) for p in self.pages)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def quality(self) -> ParseQuality:
        if not self.pages or self.empty_page_count == self.page_count:
            return ParseQuality.EMPTY
        if self.empty_page_count > 0:
            return ParseQuality.PARTIAL
        return ParseQuality.GOOD

    def text(self) -> str:
        """Whole-document text with page breaks marked.

        The page markers let extraction quote a source span AND name its
        page, which feeds SourcedField.page for auditability.
        """
        return "\n\n".join(f"[page {i + 1}]\n{page}" for i, page in enumerate(self.pages))


def parse_pdf(pdf_bytes: bytes, *, content_hash: str, parsed_at: AwareDatetime) -> ParsedDocument:
    """Extract native text from every page. Deterministic for given bytes."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = [(page.extract_text() or "") for page in pdf.pages]
    return ParsedDocument(
        content_hash=content_hash,
        parser_version=PARSER_VERSION,
        parsed_at=parsed_at,
        pages=pages,
    )
