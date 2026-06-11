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
    parse_announcements_html,
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

# Rows assembled from verbatim captures of announcements.do (2026-06-11):
# a price-sensitive row (note the marker img), a non-sensitive row, and a
# summer-time (AEDT) row to pin the daylight-saving conversion.
LISTING_HTML = """
<html><body><table>
<tr><th>Date</th><th></th><th>Headline</th></tr>
<tr>
 <td> 22/04/2026<br> <span class="dates-time">8:30 am</span> </td>
 <td class="pricesens" style="vertical-align: middle"> <img src="/asx/v2/markets/image/icon-price-sensitive.svg" height="12.5" width="6" class="pricesens" alt="asterix" title="price sensitive"> </td>
 <td> <a style="text-decoration: none;" target="_blank" href="/asx/v2/statistics/displayAnnouncement.do?display=pdf&amp;idsId=03084954"> Quarterly Activities Report<br> <img src="/asx/v2/markets/image/pdf_icon.png" height="16" width="16"> <span class="page">11 pages </span> <span class="filesize"> 138.6KB </span> </a> </td>
</tr>
<tr>
 <td> 01/06/2026<br> <span class="dates-time">12:09 pm</span> </td>
 <td class="pricesens" style="vertical-align: middle"> </td>
 <td> <a style="text-decoration: none;" target="_blank" href="/asx/v2/statistics/displayAnnouncement.do?display=pdf&amp;idsId=03099693"> Initial Director's Interest Notice<br> <img src="/asx/v2/markets/image/pdf_icon.png" height="16" width="16"> <span class="page">2 pages </span> <span class="filesize"> 203.8KB </span> </a> </td>
</tr>
<tr>
 <td> 17/02/2026<br> <span class="dates-time">9:30 am</span> </td>
 <td class="pricesens" style="vertical-align: middle"> <img src="/asx/v2/markets/image/icon-price-sensitive.svg" height="12.5" width="6" class="pricesens" alt="asterix" title="price sensitive"> </td>
 <td> <a style="text-decoration: none;" target="_blank" href="/asx/v2/statistics/displayAnnouncement.do?display=pdf&amp;idsId=03060974"> Half Year Results<br> <img src="/asx/v2/markets/image/pdf_icon.png" height="16" width="16"> <span class="page">58 pages </span> <span class="filesize"> 2.1MB </span> </a> </td>
</tr>
</table></body></html>
"""

# The load-bearing fragment of the captured terms interstitial.
INTERSTITIAL_HTML = """
<html><body>
<form name="showAnnouncementPDFForm" method="post" action="/asx/v2/statistics/announcementTerms.do">
<input value="Decline" onclick="window.close();return false;" type="submit">
<input value="Agree and proceed" type="submit">
<input name="pdfURL" value="https://announcements.asx.com.au/asxpdf/20260422/pdf/06yb6mn8by7pkb.pdf" type="hidden">
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
    """Happy-path fake of every endpoint."""
    if request.url.host == "asx.api.markitdigital.com":
        return httpx.Response(200, json=ANNOUNCEMENTS_PAYLOAD)
    if request.url.path == "/asx/v2/statistics/announcements.do":
        return httpx.Response(200, text=LISTING_HTML, headers={"content-type": "text/html"})
    if request.url.path == "/asx/v2/statistics/displayAnnouncement.do":
        return httpx.Response(200, text=INTERSTITIAL_HTML, headers={"content-type": "text/html"})
    if request.url.host == "announcements.asx.com.au":
        return httpx.Response(200, content=PDF_BYTES, headers={"content-type": "application/pdf"})
    raise AssertionError(f"unexpected request: {request.url}")


class TestParseAnnouncementsHtml:
    def test_parses_captured_rows(self) -> None:
        rows = parse_announcements_html(LISTING_HTML)
        assert len(rows) == 3  # header row skipped
        quarterly = rows[0]
        assert quarterly.ids_id == "03084954"
        assert quarterly.headline == "Quarterly Activities Report"
        assert quarterly.price_sensitive is True
        assert quarterly.pages == 11
        assert quarterly.file_size == "138.6KB"

    def test_winter_time_converts_as_aest(self) -> None:
        # 22/04/2026 8:30 am Sydney is AEST (UTC+10) -> 21/04 22:30 UTC.
        # Matches the JSON API's timestamp for the same announcement.
        rows = parse_announcements_html(LISTING_HTML)
        assert rows[0].announced_at == datetime(2026, 4, 21, 22, 30, tzinfo=UTC)

    def test_summer_time_converts_as_aedt(self) -> None:
        # 17/02/2026 9:30 am Sydney is AEDT (UTC+11) -> 16/02 22:30 UTC.
        # The daylight-saving switch is exactly the off-by-one-hour bug that
        # corrupts event studies, so both offsets are pinned.
        rows = parse_announcements_html(LISTING_HTML)
        assert rows[2].announced_at == datetime(2026, 2, 16, 22, 30, tzinfo=UTC)

    def test_non_sensitive_row(self) -> None:
        rows = parse_announcements_html(LISTING_HTML)
        assert rows[1].price_sensitive is False
        assert rows[1].headline == "Initial Director's Interest Notice"

    def test_mangled_row_raises_api_changed(self) -> None:
        mangled = LISTING_HTML.replace("22/04/2026", "April 22nd")
        with pytest.raises(AsxApiChangedError, match="row no longer matches"):
            parse_announcements_html(mangled)

    def test_pageless_html_parses_to_empty(self) -> None:
        assert parse_announcements_html("<html><body>nothing here</body></html>") == []


class TestGetAnnouncementsHtml:
    def test_fetches_and_parses_listing(self) -> None:
        with make_client(httpx.MockTransport(standard_handler)) as client:
            rows = client.get_announcements_html("BHP", year=2026)
        assert [r.ids_id for r in rows] == ["03084954", "03099693", "03060974"]

    def test_ticker_and_year_in_query(self) -> None:
        seen: list[dict[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(dict(request.url.params))
            return httpx.Response(200, text=LISTING_HTML, headers={"content-type": "text/html"})

        with make_client(httpx.MockTransport(handler)) as client:
            client.get_announcements_html("bhp", year=2025)
        assert seen == [{"by": "asxCode", "asxCode": "BHP", "timeframe": "Y", "year": "2025"}]

    def test_unrecognizable_page_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, text="<html>totally redesigned</html>", headers={"content-type": "text/html"}
            )

        with make_client(httpx.MockTransport(handler)) as client:
            with pytest.raises(AsxApiChangedError, match="zero rows"):
                client.get_announcements_html("BHP", year=2026)


class TestGetAnnouncementsJson:
    def test_parses_live_captured_payload(self) -> None:
        with make_client(httpx.MockTransport(standard_handler)) as client:
            announcements = client.get_announcements("BHP")
        assert len(announcements) == 2
        first = announcements[0]
        assert first.headline == "Quarterly Activities Report"
        assert first.is_price_sensitive is True
        assert first.date == datetime(2026, 4, 21, 22, 30, 48, tzinfo=UTC)

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
    def test_resolves_interstitial_and_downloads(self) -> None:
        with make_client(httpx.MockTransport(standard_handler)) as client:
            url, content = client.fetch_pdf("03084954")
        assert url.endswith("06yb6mn8by7pkb.pdf")
        assert content == PDF_BYTES

    def test_direct_pdf_response_short_circuits(self) -> None:
        # If ASX ever serves the PDF straight from the first hop, take the win.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=PDF_BYTES, headers={"content-type": "application/pdf"}
            )

        with make_client(httpx.MockTransport(handler)) as client:
            _, content = client.fetch_pdf("03084954")
        assert content == PDF_BYTES

    def test_interstitial_without_pdf_url_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, text="<html>redesigned page</html>", headers={"content-type": "text/html"}
            )

        with make_client(httpx.MockTransport(handler)) as client:
            with pytest.raises(AsxApiChangedError, match="no pdfURL input"):
                client.fetch_pdf("03084954")

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
                client.fetch_pdf("03084954")


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
