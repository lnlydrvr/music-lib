import base64
import asyncio
from pathlib import Path

import httpx
import pytest

from src.lucida import cf
from src.lucida import http as lucida_http
from src.lucida import page


FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_blob_and_parse_search_fixture():
    html = (FIXTURES / "lucida_search.html").read_text()
    assert page.extract_blob(html)["search"]["tracks"][0]["title"] == "Synthetic Track"
    parsed = page.parse_search(html)
    assert parsed == {
        "albums": [{"url": "/album/one", "title": "Synthetic Album", "artist": "Artist One", "album": "Synthetic Album"}],
        "tracks": [{"url": "/track/one", "title": "Synthetic Track", "artist": "Artist One", "album": "Synthetic Album",}],
    }


def test_parse_page_data_fixture_and_double_base64_token():
    html = (FIXTURES / "lucida_release.html").read_text()
    assert page.parse_page_data(html)["info"]["type"] == "album"
    token = base64.b64encode(base64.b64encode(b"csrf-value")).decode()
    assert page.decode_track_token(token) == "csrf-value"
    assert page.decode_track_token("plain-token") == "plain-token"


def test_parse_search_normalizes_invalid_field_types_to_empty_strings():
    html = '<script>x=[,{"type":"data","data":{"tracks":[{"url":null,"title":42,"artists":[{"name":null}],"album":{"title":false}}]},"uses":{"url":1}}];</script>'
    assert page.parse_search(html)["tracks"] == [{"url": "", "title": "", "artist": "", "album": ""}]


def test_parse_search_extracts_largest_cover_artwork_for_albums_and_tracks():
    html = '''<script>x=[,{"type":"data","data":{"tracks":[
        {"url":"https://music.amazon.com/tracks/t1","title":"Track",
         "coverArtwork":[{"url":"https://img.example/small.jpg","width":500,"height":500},
                          {"url":"https://img.example/large.jpg","width":2000,"height":2000}]}
    ],"albums":[
        {"url":"https://music.amazon.com/albums/a1","title":"Album",
         "coverArtwork":[{"url":"https://img.example/album.jpg","width":1400,"height":1391}]}
    ]},"uses":{"url":1}}];</script>'''

    parsed = page.parse_search(html)

    assert parsed["tracks"][0]["cover_url"] == "https://img.example/large.jpg"
    assert parsed["albums"][0]["cover_url"] == "https://img.example/album.jpg"


def test_parse_search_ignores_non_list_result_sections():
    html = '<script>x=[,{"type":"data","data":{"tracks":{"bad":true},"albums":null},"uses":{"url":1}}];</script>'
    assert page.parse_search(html) == {"albums": [], "tracks": []}


def test_http_get_sets_clearance_headers_and_retries(monkeypatch):
    monkeypatch.setattr(cf, "load_clearance", lambda: ("cookie-value", "Chrome/123"))
    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(**{**kwargs, "http2": False}))
    replies = [httpx.Response(503), httpx.Response(200, text="ok")]
    seen = []

    async def handler(request):
        seen.append(request)
        return replies.pop(0)

    async def run():
        async with lucida_http.LucidaClient(transport=httpx.MockTransport(handler), retry_delay=0) as client:
            return await client.get("https://lucida.to/search")
    response = asyncio.run(run())
    assert response.text == "ok"
    assert len(seen) == 2
    assert seen[-1].headers["cookie"] == "cf_clearance=cookie-value"
    assert seen[-1].headers["user-agent"] == "Chrome/123"


def test_http_get_retries_request_errors_and_reraises_after_limit(monkeypatch):
    monkeypatch.setattr(cf, "load_clearance", lambda: ("cookie-value", "Chrome/123"))
    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(**{**kwargs, "http2": False}))
    attempts = []

    async def handler(request):
        attempts.append(request)
        if len(attempts) == 1:
            raise httpx.ConnectError("temporary connection failure", request=request)
        return httpx.Response(200, text="ok")

    async def run():
        async with lucida_http.LucidaClient(transport=httpx.MockTransport(handler), retry_delay=0) as client:
            return await client.get("https://lucida.to/search")

    assert asyncio.run(run()).text == "ok"
    assert len(attempts) == 2

    failed_attempts = []

    async def failing_handler(request):
        failed_attempts.append(request)
        raise httpx.ConnectError("persistent connection failure", request=request)

    async def fail():
        async with lucida_http.LucidaClient(transport=httpx.MockTransport(failing_handler), retries=2, retry_delay=0) as client:
            await client.get("https://lucida.to/search")

    with pytest.raises(httpx.ConnectError, match="persistent connection failure"):
        asyncio.run(fail())
    assert len(failed_attempts) == 3


def test_retry_after_is_capped(monkeypatch):
    monkeypatch.setattr(cf, "load_clearance", lambda: ("cookie-value", "Chrome/123"))
    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(**{**kwargs, "http2": False}))
    replies = [httpx.Response(429, headers={"Retry-After": "999999999999"}), httpx.Response(200)]
    delays = []

    async def handler(request):
        return replies.pop(0)

    async def run():
        async with lucida_http.LucidaClient(transport=httpx.MockTransport(handler), retry_delay=0) as client:
            await client.get("https://lucida.to/search")

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(lucida_http.asyncio, "sleep", sleep)
    asyncio.run(run())
    assert delays == [lucida_http.MAX_RETRY_DELAY]


def test_http_403_raises_access_error_without_browser(monkeypatch):
    monkeypatch.setattr(cf, "load_clearance", lambda: ("cookie-value", "Chrome/123"))
    monkeypatch.setattr(cf, "acquire", lambda **_: pytest.fail("browser must not launch"))
    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(**{**kwargs, "http2": False}))

    async def handler(request):
        return httpx.Response(403)

    async def run():
        async with lucida_http.LucidaClient(transport=httpx.MockTransport(handler), retries=0) as client:
            await client.get("https://lucida.to/search")
    with pytest.raises(lucida_http.LucidaAccessRequired):
        asyncio.run(run())


def test_stream_closes_final_http_error_response(monkeypatch):
    monkeypatch.setattr(cf, "load_clearance", lambda: ("cookie-value", "Chrome/123"))
    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(**{**kwargs, "http2": False}))
    responses = []

    async def handler(request):
        response = httpx.Response(404, request=request)
        responses.append(response)
        return response

    async def run():
        async with lucida_http.LucidaClient(transport=httpx.MockTransport(handler), retries=0) as client:
            await client.stream("https://lucida.to/missing")

    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(run())
    assert responses[0].is_closed
