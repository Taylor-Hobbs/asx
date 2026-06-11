"""Thin client for ASX's undocumented announcement endpoints.

Verified live on 2026-06-11 (see BUILD_LOG). The chain has three hops:

1. Metadata — GET asx.api.markitdigital.com/asx-research/1.0/companies/
   {ticker}/announcements -> JSON. NOTE: the `url` field in items is empty;
   the PDF must be resolved via hop 2. The pyasx-era endpoint
   (www.asx.com.au/asx/1/...) is dead (404).
2. Resolve — GET www.asx.com.au/asx/v2/statistics/displayAnnouncement.do
   ?display=pdf&idsId={middle segment of documentKey} -> an HTML terms
   interstitial whose hidden <input name="pdfURL"> holds the real PDF URL.
3. Download — GET announcements.asx.com.au/asxpdf/.../*.pdf -> the bytes.

Because every hop is undocumented and can change without notice, this module
is deliberately paranoid: every response is schema-validated and any surprise
raises AsxApiChangedError with enough context to diagnose the drift. Polite
by construction: a shared rate limiter sits in front of EVERY request, the
User-Agent identifies the project, and transient failures back off
exponentially.
"""

import re
import time
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

ANNOUNCEMENTS_URL = (
    "https://asx.api.markitdigital.com/asx-research/1.0/companies/{ticker}/announcements"
)
DISPLAY_ANNOUNCEMENT_URL = "https://www.asx.com.au/asx/v2/statistics/displayAnnouncement.do"

# Matches the hidden input on the terms interstitial. Attribute-order
# tolerant; tested against a captured copy of the real page.
_PDF_URL_PATTERN = re.compile(r'<input[^>]*name="pdfURL"[^>]*value="([^"]+)"', re.IGNORECASE)

_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


class AsxApiChangedError(Exception):
    """The undocumented API did something we don't recognize.

    Raised instead of letting a KeyError/ValidationError escape so that the
    ingestion job fails with a message that says WHAT drifted, not just that
    something was None three frames away from the actual problem.
    """


class RawAnnouncement(BaseModel):
    """One item from the announcements endpoint, exactly as ASX shapes it.

    `alias_generator=to_camel` maps our snake_case field names onto the API's
    camelCase keys (document_key <- documentKey) so the model reads like our
    codebase while validating their wire format. `extra="ignore"` means NEW
    fields appearing upstream don't break us; missing REQUIRED fields still
    fail loudly.
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

    @property
    def ids_id(self) -> str:
        """Middle segment of documentKey — the legacy idsId used by hop 2."""
        return self.document_key.split("-")[1]


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
    """Rate-limited, fail-loud client for the three-hop announcement chain."""

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

    # ------------------------------------------------------------ hop 1: list

    def get_announcements(self, ticker: str, *, items_per_page: int = 50) -> list[RawAnnouncement]:
        """Fetch announcement metadata for one ticker.

        NOTE: live API treats itemsPerPage as a suggestion (asked for 3,
        got 5), so callers must filter/limit on their side.
        """
        url = ANNOUNCEMENTS_URL.format(ticker=ticker.upper())
        response = self._get(url, params={"page": 0, "itemsPerPage": items_per_page})
        try:
            items = response.json()["data"]["items"]
            return [RawAnnouncement.model_validate(item) for item in items]
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise AsxApiChangedError(
                f"announcements payload for {ticker} no longer matches the expected shape: "
                f"{exc}\nfirst 500 bytes: {response.text[:500]!r}"
            ) from exc

    # ------------------------------------------- hops 2 + 3: resolve + download

    def fetch_pdf(self, announcement: RawAnnouncement) -> tuple[str, bytes]:
        """Resolve the interstitial and download the PDF. Returns (url, bytes).

        Tolerates ASX simplifying things on us: if hop 2 ever serves the PDF
        directly (or redirects to it), we take it and skip the interstitial
        parse.
        """
        response = self._get(
            DISPLAY_ANNOUNCEMENT_URL, params={"display": "pdf", "idsId": announcement.ids_id}
        )
        if response.headers.get("content-type", "").startswith("application/pdf"):
            return str(response.url), response.content

        match = _PDF_URL_PATTERN.search(response.text)
        if match is None:
            raise AsxApiChangedError(
                f"interstitial for idsId={announcement.ids_id} contains no pdfURL input; "
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
