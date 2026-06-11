"""Thin client for ASX's undocumented announcement endpoints.

Verified live on 2026-06-11 (see BUILD_LOG for the probe transcript). Two
sources exist, and they are NOT equivalent:

- HTML listing (source of truth) — GET www.asx.com.au/asx/v2/statistics/
  announcements.do?by=asxCode&asxCode={ticker}&timeframe=Y&year={year}
  returns the FULL calendar year: release time (Australia/Sydney local),
  price-sensitive marker, headline, and the idsId that resolves to the PDF.
- JSON API (recent-5 only) — GET asx.api.markitdigital.com/asx-research/1.0/
  companies/{ticker}/announcements returns ONLY the 5 most recent items;
  pagination and fromDate/toDate are accepted but ignored.

  ⚠ The JSON documentKey's middle segment LOOKS like an idsId but is not:
  for BHP's 2026-04-21 quarterly it gave 03081111, whose interstitial
  resolves to a DIFFERENT document (dated 2026-04-09); the HTML page's
  idsId 03084954 is correct. Never derive PDF identity from documentKey.

PDF retrieval (two hops from an idsId):
1. GET www.asx.com.au/asx/v2/statistics/displayAnnouncement.do
   ?display=pdf&idsId={idsId} -> an HTML terms interstitial whose hidden
   <input name="pdfURL"> holds the real URL.
2. GET announcements.asx.com.au/asxpdf/.../*.pdf -> the bytes.

Because every endpoint is undocumented and can change without notice, this
module is deliberately paranoid: every response is schema-validated and any
surprise raises AsxApiChangedError with enough context to diagnose the
drift. Polite by construction: a shared rate limiter sits in front of EVERY
request, the User-Agent identifies the project, and transient failures back
off exponentially.
"""

import re
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup, Tag
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

ANNOUNCEMENTS_JSON_URL = (
    "https://asx.api.markitdigital.com/asx-research/1.0/companies/{ticker}/announcements"
)
ANNOUNCEMENTS_HTML_URL = "https://www.asx.com.au/asx/v2/statistics/announcements.do"
DISPLAY_ANNOUNCEMENT_URL = "https://www.asx.com.au/asx/v2/statistics/displayAnnouncement.do"

# ASX publishes announcement times in Sydney local time; zoneinfo handles
# the AEST/AEDT daylight-saving switch for us.
SYDNEY = ZoneInfo("Australia/Sydney")

# Matches the hidden input on the terms interstitial. Attribute-order
# tolerant; tested against a captured copy of the real page.
_PDF_URL_PATTERN = re.compile(r'<input[^>]*name="pdfURL"[^>]*value="([^"]+)"', re.IGNORECASE)
_IDS_ID_PATTERN = re.compile(r"idsId=(\d+)")

_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


class AsxApiChangedError(Exception):
    """The undocumented API did something we don't recognize.

    Raised instead of letting a KeyError/ValidationError escape so that the
    ingestion job fails with a message that says WHAT drifted, not just that
    something was None three frames away from the actual problem.
    """


class HtmlAnnouncement(BaseModel):
    """One row of the announcements.do HTML listing — the source of truth."""

    model_config = ConfigDict(frozen=True)

    ids_id: str = Field(pattern=r"^\d+$")
    announced_at: AwareDatetime
    price_sensitive: bool
    headline: str = Field(min_length=1)
    pages: int | None = None
    file_size: str | None = None


class RawAnnouncement(BaseModel):
    """One item from the JSON endpoint (recent-5 only; see module docstring).

    `alias_generator=to_camel` maps our snake_case field names onto the API's
    camelCase keys (document_key <- documentKey) so the model reads like our
    codebase while validating their wire format. `extra="ignore"` means NEW
    fields appearing upstream don't break us; missing REQUIRED fields still
    fail loudly.

    ⚠ document_key is an opaque identifier ONLY — its middle segment is not
    a usable idsId (verified: resolves to the wrong document). PDF identity
    always comes from the HTML listing.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, frozen=True)

    announcement_type: str
    date: AwareDatetime
    document_key: str = Field(pattern=r"^\d+-\d+-[A-Z0-9]+$")
    headline: str
    is_price_sensitive: bool
    # Present but observed empty on the live API; kept so we notice if ASX
    # ever starts populating it (cheaper than the interstitial hop).
    url: str = ""


def parse_announcements_html(html: str) -> list[HtmlAnnouncement]:
    """Parse the announcements.do listing into typed rows.

    Captured row shape (2026-06-11):
        <td> 22/04/2026<br> <span class="dates-time">8:30 am</span> </td>
        <td class="pricesens"> <img ... title="price sensitive"> </td>
        <td> <a href="...displayAnnouncement.do?display=pdf&idsId=03084954">
             Quarterly Activities Report<br> ...
             <span class="page">11 pages </span>
             <span class="filesize"> 138.6KB </span> </a> </td>
    """
    soup = BeautifulSoup(html, "html.parser")
    announcements: list[HtmlAnnouncement] = []
    for row in soup.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        link = row.find("a", href=_IDS_ID_PATTERN)
        if not isinstance(link, Tag):
            continue  # header/spacer rows have no announcement link

        try:
            ids_match = _IDS_ID_PATTERN.search(str(link["href"]))
            assert ids_match is not None  # guaranteed by the find() filter

            cells = row.find_all("td")
            date_text = " ".join(cells[0].get_text(" ", strip=True).split())
            announced_at = datetime.strptime(date_text, "%d/%m/%Y %I:%M %p").replace(tzinfo=SYDNEY)

            sensitive_img = row.find("img", attrs={"title": "price sensitive"})

            # Headline is the link's leading text node (before the <br>).
            headline = link.find(string=True)
            pages_span = link.find("span", class_="page")
            size_span = link.find("span", class_="filesize")
            pages_text = pages_span.get_text(strip=True) if pages_span else ""
            pages_match = re.match(r"(\d+)", pages_text)

            announcements.append(
                HtmlAnnouncement(
                    ids_id=ids_match.group(1),
                    announced_at=announced_at,
                    price_sensitive=sensitive_img is not None,
                    headline=str(headline).strip() if headline else "",
                    pages=int(pages_match.group(1)) if pages_match else None,
                    file_size=size_span.get_text(strip=True) if size_span else None,
                )
            )
        except (ValidationError, ValueError, IndexError, KeyError) as exc:
            raise AsxApiChangedError(
                f"announcements.do row no longer matches the expected shape: {exc}\n"
                f"row: {str(row)[:500]!r}"
            ) from exc
    return announcements


class RateLimiter:
    """Enforces a minimum interval between consecutive requests.

    `clock` and `sleep` are injectable (defaulting to the real ones) so tests
    can verify pacing logic without actually sleeping — the standard trick
    for making time-dependent code testable.

    Uses time.monotonic, not time.time: the monotonic clock can't jump
    backwards (NTP sync, DST) and is the only correct choice for measuring
    intervals.
    """

    def __init__(
        self,
        min_interval_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._min_interval = min_interval_seconds
        self._clock = clock
        self._sleep = sleep
        self._last_request_at: float | None = None

    def wait(self) -> None:
        if self._last_request_at is not None:
            remaining = self._min_interval - (self._clock() - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = self._clock()


class AsxClient:
    """Rate-limited, fail-loud client for the announcement chain."""

    def __init__(
        self,
        *,
        user_agent: str,
        request_interval_seconds: float = 3.0,
        max_attempts: int = 4,
        backoff_base_seconds: float = 1.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._limiter = RateLimiter(request_interval_seconds, sleep=sleep)
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base_seconds
        self._sleep = sleep
        self._client = httpx.Client(
            headers={"User-Agent": user_agent, "Accept": "application/json, text/html, */*"},
            timeout=30.0,
            follow_redirects=True,
            transport=transport,
        )

    def __enter__(self) -> "AsxClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------- requests

    def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """One GET through the limiter, with exponential backoff on transients.

        Retryable: network-level errors and 429/5xx (the server hiccuped).
        NOT retryable: other 4xx — those mean the API changed or our request
        is wrong, and retrying would just hammer ASX with the same mistake.
        """
        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            if attempt > 0:
                # 1s, 2s, 4s, ... — doubling gives the server room to recover.
                self._sleep(self._backoff_base * 2 ** (attempt - 1))
            self._limiter.wait()
            try:
                response = self._client.get(url, params=params)
            except httpx.TransportError as exc:
                last_error = exc
                continue
            if response.status_code in _RETRYABLE_STATUSES:
                last_error = AsxApiChangedError(
                    f"GET {url} -> HTTP {response.status_code} (retryable)"
                )
                continue
            if response.is_error:
                raise AsxApiChangedError(
                    f"GET {url} -> HTTP {response.status_code}; the endpoint may have moved"
                )
            return response
        raise AsxApiChangedError(
            f"GET {url} failed after {self._max_attempts} attempts: {last_error}"
        )

    # ----------------------------------------------- listing (source of truth)

    def get_announcements_html(self, ticker: str, *, year: int) -> list[HtmlAnnouncement]:
        """Full-year announcement listing for one ticker, newest first."""
        response = self._get(
            ANNOUNCEMENTS_HTML_URL,
            params={"by": "asxCode", "asxCode": ticker.upper(), "timeframe": "Y", "year": year},
        )
        announcements = parse_announcements_html(response.text)
        if not announcements and "announcements" not in response.text.lower():
            raise AsxApiChangedError(
                f"announcements.do for {ticker}/{year} parsed to zero rows and does not look "
                f"like an announcements page; first 500 bytes: {response.text[:500]!r}"
            )
        return announcements

    # ------------------------------------------------- JSON metadata (recent 5)

    def get_announcements(self, ticker: str, *, items_per_page: int = 50) -> list[RawAnnouncement]:
        """Recent announcement metadata for one ticker (JSON endpoint).

        The live API returns AT MOST the 5 newest items no matter what —
        itemsPerPage, page, fromDate and toDate are all ignored. Useful for
        forward polling; useless for backfill (use get_announcements_html).
        """
        url = ANNOUNCEMENTS_JSON_URL.format(ticker=ticker.upper())
        response = self._get(url, params={"page": 0, "itemsPerPage": items_per_page})
        try:
            items = response.json()["data"]["items"]
            return [RawAnnouncement.model_validate(item) for item in items]
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise AsxApiChangedError(
                f"announcements payload for {ticker} no longer matches the expected shape: "
                f"{exc}\nfirst 500 bytes: {response.text[:500]!r}"
            ) from exc

    # ------------------------------------------- PDF: resolve + download

    def fetch_pdf(self, ids_id: str) -> tuple[str, bytes]:
        """Resolve the interstitial for an idsId and download the PDF.

        Returns (pdf_url, pdf_bytes). Tolerates ASX simplifying things on us:
        if the first hop ever serves the PDF directly (or redirects to it),
        we take it and skip the interstitial parse.
        """
        response = self._get(DISPLAY_ANNOUNCEMENT_URL, params={"display": "pdf", "idsId": ids_id})
        if response.headers.get("content-type", "").startswith("application/pdf"):
            return str(response.url), response.content

        match = _PDF_URL_PATTERN.search(response.text)
        if match is None:
            raise AsxApiChangedError(
                f"interstitial for idsId={ids_id} contains no pdfURL input; "
                f"first 500 bytes: {response.text[:500]!r}"
            )
        pdf_url = match.group(1)

        pdf_response = self._get(pdf_url)
        content_type = pdf_response.headers.get("content-type", "")
        if not content_type.startswith("application/pdf"):
            raise AsxApiChangedError(
                f"expected application/pdf from {pdf_url}, got {content_type!r}"
            )
        return pdf_url, pdf_response.content
