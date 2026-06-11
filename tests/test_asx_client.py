"""Tests for the ASX client.

No test touches the network. httpx.MockTransport routes every request to an
in-process handler, and the fixtures below are VERBATIM captures from the
live API (2026-06-11) — so "does our parser match reality" is pinned to a
known-real sample, and schema drift shows up as a deliberate fixture update
in review, never a silent behavior change.
"""

import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from asx_engine.ingestion.asx_client import (
    AsxApiChangedError,
    AsxClient,
    RateLimiter,
    RawAnnouncement,
)

# Captured live 2026-06-11, trimmed to two items.
ANNOUNCEMENTS_PAYLOAD: dict[str, Any] = {
    "data": {
        "displayName": "BHP GROUP LIMITED",
        "issueType": "CS",
        "items": [
            {
                "announcementType": "QUARTERLY ACTIVITIES REPORT",
                "date": "2026-04-21T22:30:48.000Z",
                "documentKey": "2924-03081111-3A691768",
                "fileSize": "132KB",
                "headline": "Quarterly Activities Report",
                "isPriceSensitive": True,
                "url": "",
            },
            {
                "announcementType": "COMPANY ADMINISTRATION",
                "date": "2026-05-12T23:38:53.000Z",
                "documentKey": "2924-03089593-3A693216",
                "fileSize": "99KB",
                "headline": "BHP Board Update",
                "isPriceSensitive": False,
                "url": "",
            },
        ],
        "symbol": "BHP",
        "xid": "60947",
    }
}

# The load-bearing fragment of the captured terms interstitial.
INTERSTITIAL_HTML = """
<html><body>
<form name="showAnnouncementPDFForm" method="post" action="/asx/v2/statistics/announcementTerms.do">
<input value="Decline" onclick="window.close();return false;" type="submit">
<input value="Agree and proceed" type="submit">
<input name="pdfURL" value="https://announcements.asx.com.au/asxpdf/20260409/pdf/06yb6mn8by7pkb.pdf" type="hidden">
</form>
</body></html>
"""

PDF_BYTES = b"%PDF-1.7 fake-but-shaped-right"


def make_client(handler: httpx.MockTransport) -> AsxClient:
    """Client wired for tests: mock transport, no pacing, no real sleeping."""
    return AsxClient(
        user_agent="test-agent",
        request_interval_seconds=0,
        backoff_base_seconds=0,
        transport=handler,
        sleep=lambda _: None,
    )


def standard_handler(request: httpx.Request) -> httpx.Response:
    """Happy-path fake of all three hops."""
    if request.url.host == "asx.api.markitdigital.com":
        return httpx.Response(200, json=ANNOUNCEMENTS_PAYLOAD)
    if request.url.path == "/asx/v2/statistics/displayAnnouncement.do":
        return httpx.Response(200, text=INTERSTITIAL_HTML, headers={"content-type": "text/html"})
    if request.url.host == "announcements.asx.com.au":
        return httpx.Response(200, content=PDF_BYTES, headers={"content-type": "application/pdf"})
    raise AssertionError(f"unexpected request: {request.url}")


class TestGetAnnouncements:
    def test_parses_live_captured_payload(self) -> None:
        with make_client(httpx.MockTransport(standard_handler)) as client:
            announcements = client.get_announcements("BHP")
        assert len(announcements) == 2
        first = announcements[0]
        assert first.headline == "Quarterly Activities Report"
        assert first.is_price_sensitive is True
        assert first.date == datetime(2026, 4, 21, 22, 30, 48, tzinfo=UTC)
        assert first.ids_id == "03081111"

    def test_ticker_is_uppercased_in_url(self) -> None:
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.url.path)
            return httpx.Response(200, json=ANNOUNCEMENTS_PAYLOAD)

        with make_client(httpx.MockTransport(handler)) as client:
            client.get_announcements("bhp")
        assert seen == ["/asx-research/1.0/companies/BHP/announcements"]

    def test_missing_required_field_raises_api_changed(self) -> None:
        broken = json.loads(json.dumps(ANNOUNCEMENTS_PAYLOAD))
        del broken["data"]["items"][0]["documentKey"]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=broken)

        with make_client(httpx.MockTransport(handler)) as client:
            with pytest.raises(AsxApiChangedError, match="no longer matches"):
                client.get_announcements("BHP")

    def test_restructured_payload_raises_api_changed(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"announcements": []})  # renamed envelope

        with make_client(httpx.MockTransport(handler)) as client:
            with pytest.raises(AsxApiChangedError):
                client.get_announcements("BHP")

    def test_extra_fields_are_tolerated(self) -> None:
        # New upstream fields must NOT break ingestion (additive drift is fine).
        extended = json.loads(json.dumps(ANNOUNCEMENTS_PAYLOAD))
        extended["data"]["items"][0]["brandNewField"] = "surprise"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=extended)

        with make_client(httpx.MockTransport(handler)) as client:
            assert len(client.get_announcements("BHP")) == 2


class TestRetryPolicy:
    def test_retries_transient_500_then_succeeds(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] < 3:
                return httpx.Response(500)
            return httpx.Response(200, json=ANNOUNCEMENTS_PAYLOAD)

        with make_client(httpx.MockTransport(handler)) as client:
            announcements = client.get_announcements("BHP")
        assert calls["n"] == 3
        assert len(announcements) == 2

    def test_hard_404_fails_immediately_no_retry(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(404)

        with make_client(httpx.MockTransport(handler)) as client:
            with pytest.raises(AsxApiChangedError, match="HTTP 404"):
                client.get_announcements("BHP")
        # Retrying a 404 would hammer ASX with a request we know is wrong.
        assert calls["n"] == 1

    def test_exhausted_retries_raise_with_context(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        with make_client(httpx.MockTransport(handler)) as client:
            with pytest.raises(AsxApiChangedError, match="after 4 attempts"):
                client.get_announcements("BHP")

    def test_backoff_delays_double(self) -> None:
        sleeps: list[float] = []

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        client = AsxClient(
            user_agent="test-agent",
            request_interval_seconds=0,
            backoff_base_seconds=1.0,
            transport=httpx.MockTransport(handler),
            sleep=sleeps.append,
        )
        with client, pytest.raises(AsxApiChangedError):
            client.get_announcements("BHP")
        assert sleeps == [1.0, 2.0, 4.0]  # doubling, no sleep before attempt 1


class TestFetchPdf:
    def announcement(self) -> RawAnnouncement:
        return RawAnnouncement.model_validate(ANNOUNCEMENTS_PAYLOAD["data"]["items"][0])

    def test_resolves_interstitial_and_downloads(self) -> None:
        with make_client(httpx.MockTransport(standard_handler)) as client:
            url, content = client.fetch_pdf(self.announcement())
        assert url.endswith("06yb6mn8by7pkb.pdf")
        assert content == PDF_BYTES

    def test_direct_pdf_response_short_circuits(self) -> None:
        # If ASX ever serves the PDF straight from hop 2, take the win.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=PDF_BYTES, headers={"content-type": "application/pdf"}
            )

        with make_client(httpx.MockTransport(handler)) as client:
            _, content = client.fetch_pdf(self.announcement())
        assert content == PDF_BYTES

    def test_interstitial_without_pdf_url_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, text="<html>redesigned page</html>", headers={"content-type": "text/html"}
            )

        with make_client(httpx.MockTransport(handler)) as client:
            with pytest.raises(AsxApiChangedError, match="no pdfURL input"):
                client.fetch_pdf(self.announcement())

    def test_non_pdf_download_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "announcements.asx.com.au":
                return httpx.Response(
                    200, text="<html>error page</html>", headers={"content-type": "text/html"}
                )
            return httpx.Response(
                200, text=INTERSTITIAL_HTML, headers={"content-type": "text/html"}
            )

        with make_client(httpx.MockTransport(handler)) as client:
            with pytest.raises(AsxApiChangedError, match="expected application/pdf"):
                client.fetch_pdf(self.announcement())


class TestRateLimiter:
    def test_spaces_requests_to_min_interval(self) -> None:
        # Fake clock + recorded sleeps: pacing logic verified in microseconds
        # of real time. now[0] advances only when we say so.
        now = [100.0]
        sleeps: list[float] = []
        limiter = RateLimiter(3.0, clock=lambda: now[0], sleep=sleeps.append)

        limiter.wait()  # first request: no predecessor, no sleep
        now[0] += 1.0  # only 1s of the 3s interval has passed
        limiter.wait()
        assert sleeps == [2.0]

    def test_no_sleep_when_interval_already_elapsed(self) -> None:
        now = [100.0]
        sleeps: list[float] = []
        limiter = RateLimiter(3.0, clock=lambda: now[0], sleep=sleeps.append)

        limiter.wait()
        now[0] += 10.0
        limiter.wait()
        assert sleeps == []
