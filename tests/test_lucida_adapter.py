import asyncio
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

import src.lucida as lucida
from src.lucida import download
from src.lucida.http import LucidaAccessRequired


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def json(self):
        return self.text


class FakeClient:
    def __init__(self):
        self.urls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def get(self, url):
        self.urls.append(url)
        return FakeResponse("<release-page>")


class CountryResponseClient(FakeClient):
    def __init__(self, pages):
        super().__init__()
        self.pages = pages

    async def get(self, url):
        self.urls.append(url)
        country = parse_qs(urlsplit(url).query).get("country", [""])[0]
        return FakeResponse(self.pages[country])


def test_status_checks_clearance_and_chromium_without_launching_browser(monkeypatch):
    calls = []
    monkeypatch.setattr(lucida.importlib.util, "find_spec", lambda name: object())

    import src.lucida.cf as cf

    monkeypatch.setattr(cf, "load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(cf, "chromium_installed", lambda: calls.append("checked") or True)
    monkeypatch.setattr(cf, "acquire", lambda: pytest.fail("status must not launch a browser"))

    assert lucida.status("Qobuz") == {
        "available": True,
        "access_ready": True,
        "chromium_ready": True,
        "service": "qobuz",
    }
    assert calls == ["checked"]


def test_search_uses_clearance_and_returns_parsed_results(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(lucida, "_load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(lucida, "_client", lambda: client)
    monkeypatch.setattr(lucida, "_parse_search", lambda html: {"albums": [{"title": "Album"}], "tracks": []})

    assert lucida.search("A & B", "qobuz") == {"albums": [{"title": "Album"}], "tracks": []}
    query = parse_qs(urlsplit(client.urls[0]).query)
    assert query == {"service": ["qobuz"], "country": ["NL"], "query": ["A & B"]}


def test_release_preview_returns_sanitized_album_metadata_without_tokens(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(lucida, "_load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(lucida, "_client", lambda: client)
    monkeypatch.setattr(lucida, "_parse_page_data", lambda _html: {
        "info": {"type": "album", "title": "Blue", "artist": "Miles",
                 "cover_url": "https://images.example/cover.jpg", "csrf": "secret",
                 "tracks": [{"title": "So What", "url": "secret", "csrf": "secret",
                             "number": 1, "duration": 562}]},
        "token": "secret", "expiry": 123,
    })

    result = lucida.release_preview("https://www.qobuz.com/album/x", "qobuz")

    assert result == {"title": "Blue", "artist": "Miles", "cover_url": "https://images.example/cover.jpg",
                      "tracks": [{"number": 1, "title": "So What", "duration": 562}], "track_count": 1}
    assert "secret" not in str(result)


def test_release_preview_replaces_token_like_track_number_with_ordinal(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(lucida, "_load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(lucida, "_client", lambda: client)
    monkeypatch.setattr(lucida, "_parse_page_data", lambda _html: {
        "info": {"tracks": [{"title": "Track", "number": "csrf-token-123"}]},
    })

    result = lucida.release_preview("https://www.qobuz.com/album/x", "qobuz")

    assert result["tracks"] == [{"number": 1, "title": "Track"}]


def test_download_progress_reports_terminal_count_and_total(monkeypatch, tmp_path):
    client = FakeClient()
    monkeypatch.setattr(lucida, "_load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(lucida, "_client", lambda: client)
    monkeypatch.setattr(lucida, "_resolve_output_dir", lambda: tmp_path)
    monkeypatch.setattr(lucida, "_parse_page_data", lambda _html: {"info": {"type": "album", "tracks": [
        {"url": "https://www.qobuz.com/one", "title": "One", "csrf": "one"},
        {"url": "https://www.qobuz.com/two", "title": "Two", "csrf": "two"},
    ]}})
    monkeypatch.setattr(lucida, "_start_download", lambda *_args, **_kwargs: asyncio.sleep(0, result=("h", "s")))

    async def run_job(*_args, **_kwargs):
        raise RuntimeError("provider detail")

    monkeypatch.setattr(lucida, "_run_job", run_job)
    events = []
    result = lucida.download("https://www.qobuz.com/album", "album", jobs=1, progress=events.append)

    assert [item["status"] for item in result["items"]] == ["fail", "fail"]
    assert [(e["done"], e["total"], e["percent"]) for e in events if e["type"] == "item"] == [(1, 2, 50), (2, 2, 100)]


def test_download_progress_completes_for_missing_url_and_out_of_order_items(monkeypatch, tmp_path):
    client = FakeClient()
    monkeypatch.setattr(lucida, "_load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(lucida, "_client", lambda: client)
    monkeypatch.setattr(lucida, "_resolve_output_dir", lambda: tmp_path)
    monkeypatch.setattr(lucida, "_parse_page_data", lambda _html: {"info": {"type": "album", "tracks": [
        {"title": "Invalid", "csrf": "unused"},
        {"url": "https://www.qobuz.com/slow", "title": "Slow", "csrf": "slow"},
        {"url": "https://www.qobuz.com/fast", "title": "Fast", "csrf": "fast"},
    ]}})

    async def start(track, *_args, **_kwargs):
        if track["csrf"] == "slow":
            await asyncio.sleep(0.02)
        raise RuntimeError("provider failure")

    monkeypatch.setattr(lucida, "_start_download", start)
    events = []

    result = lucida.download("https://www.qobuz.com/album", "album", jobs=3, progress=events.append)

    item_events = [event for event in events if event["type"] == "item"]
    assert len(result["items"]) == 3
    assert len(item_events) == 3
    assert sorted(event["done"] for event in item_events) == [1, 2, 3]
    assert item_events[-1]["done"] == item_events[-1]["total"] == 3
    assert item_events[-1]["percent"] == 100
    assert item_events[0]["url"] != "https://www.qobuz.com/slow"


def test_empty_release_is_unavailable_not_success(monkeypatch, tmp_path):
    monkeypatch.setattr(lucida, "_load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(lucida, "_client", FakeClient)
    monkeypatch.setattr(lucida, "_resolve_output_dir", lambda: tmp_path)
    monkeypatch.setattr(lucida, "_parse_page_data", lambda _html: {"info": {"type": "album", "tracks": []}})

    with pytest.raises(lucida.LucidaReleaseUnavailable):
        lucida.download("https://www.qobuz.com/album", "album")


def test_search_uses_explicit_country_over_service_default(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(lucida, "_load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(lucida, "_client", lambda: client)
    monkeypatch.setattr(lucida, "_parse_search", lambda _html: {"albums": [], "tracks": []})

    assert lucida.search("A & B", "qobuz", country="US") == {"albums": [], "tracks": []}
    assert parse_qs(urlsplit(client.urls[0]).query)["country"] == ["US"]


def test_search_requires_existing_clearance_without_creating_a_client(monkeypatch):
    monkeypatch.setattr(lucida, "_load_clearance", lambda: (None, None))
    monkeypatch.setattr(lucida, "_client", lambda: pytest.fail("client must not be created"))

    with pytest.raises(lucida.LucidaAccessRequired):
        lucida.search("query", "qobuz")


def test_expired_clearance_fails_status_search_and_download_without_browser(monkeypatch):
    monkeypatch.setattr(lucida, "_load_clearance", lambda: (None, None))
    monkeypatch.setattr(lucida, "available", lambda: False)
    assert lucida.status() == {"available": False, "access_ready": False, "chromium_ready": False, "service": "qobuz"}
    with pytest.raises(LucidaAccessRequired):
        lucida.search("query")
    with pytest.raises(LucidaAccessRequired):
        lucida.download("https://www.qobuz.com/album/x", "track")


def test_public_search_propagates_http_403_without_acquiring_browser_access(monkeypatch):
    import httpx
    from src.lucida import cf
    from src.lucida.http import LucidaClient, LucidaAccessRequired

    monkeypatch.setattr(cf, "load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(cf, "acquire", lambda **_kwargs: pytest.fail("search must not acquire browser access"))
    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(**{**kwargs, "http2": False}))

    async def forbidden(_request):
        return httpx.Response(403)

    monkeypatch.setattr(lucida, "_client", lambda: LucidaClient(
        transport=httpx.MockTransport(forbidden), retries=0,
    ))

    with pytest.raises(LucidaAccessRequired, match="expired"):
        lucida.search("query", "qobuz")


def test_download_expands_album_with_bounded_concurrency_and_keeps_selected_url(monkeypatch, tmp_path):
    client = FakeClient()
    selected_url = "https://www.qobuz.com/releases/album?a=1&b=2"
    active = 0
    peak = 0
    calls = []
    output_dir = tmp_path / "library"

    monkeypatch.setattr(lucida, "_load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(lucida, "_client", lambda: client)
    monkeypatch.setattr(lucida, "_resolve_output_dir", lambda: output_dir)
    monkeypatch.setattr(lucida, "_parse_page_data", lambda html: {
        "info": {"type": "album", "tracks": [
            {"url": "https://www.qobuz.com/tracks/one", "title": "One", "artist": "Artist", "csrf": "one"},
            {"url": "https://www.qobuz.com/tracks/two", "title": "Two", "artist": "Artist", "csrf": "two"},
            {"url": "https://www.qobuz.com/tracks/three", "title": "Three", "artist": "Artist", "csrf": "three"},
        ]},
        "expiry": 123,
    })

    async def start(track, expiry, country, *, client):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        calls.append((track["url"], expiry, country))
        return (track["csrf"], "server")

    async def run_job(handoff, server, dest_dir, name, on_status, on_bytes, *, client):
        path = Path(dest_dir) / f"{handoff}.flac"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"native-tags-stay-untouched")
        return path

    def ingest(path, out):
        return {"status": "ok", "path": str(out / "Artist" / path.name), "inbox_path": str(path)}

    monkeypatch.setattr(lucida, "_start_download", start)
    monkeypatch.setattr(lucida, "_run_job", run_job)
    monkeypatch.setattr(lucida, "_ingest", ingest)

    result = lucida.download(selected_url, "album", "qobuz", jobs=2)

    assert parse_qs(urlsplit(client.urls[0]).query)["url"] == [selected_url]
    assert peak == 2
    assert calls == [
        ("https://www.qobuz.com/tracks/one", 123, "NL"),
        ("https://www.qobuz.com/tracks/two", 123, "NL"),
        ("https://www.qobuz.com/tracks/three", 123, "NL"),
    ]
    assert [item["status"] for item in result["items"]] == ["ok", "ok", "ok"]


def test_download_uses_explicit_country_over_service_default(monkeypatch, tmp_path):
    client = FakeClient()
    monkeypatch.setattr(lucida, "_load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(lucida, "_client", lambda: client)
    monkeypatch.setattr(lucida, "_resolve_output_dir", lambda: tmp_path)
    monkeypatch.setattr(lucida, "_parse_page_data", lambda _html: {"info": {"title": "Single", "url": "https://www.qobuz.com/track", "csrf": "token"}})

    assert len(lucida.download("https://www.qobuz.com/track", "track", "qobuz", country="US")["items"]) == 1
    assert parse_qs(urlsplit(client.urls[0]).query)["country"] == ["US"]


def test_amazon_album_uses_first_storefront_with_usable_track_tokens(monkeypatch, tmp_path):
    client = CountryResponseClient({"": "default", "US": "us", "GB": "gb", "JP": "jp"})
    monkeypatch.setattr(lucida, "_load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(lucida, "_client", lambda: client)
    monkeypatch.setattr(lucida, "_resolve_output_dir", lambda: tmp_path)
    monkeypatch.setattr(lucida, "_parse_page_data", lambda page: {
        "info": {"type": "album", "tracks": [{
            "url": "https://www.qobuz.com/track", "title": "Track",
            "csrf": "" if page == "default" else "usable-token",
        }]},
    })
    countries = []

    async def start(track, _expiry, country, *, client):
        countries.append(country)
        return (track["csrf"], "server")

    async def run_job(_handoff, _server, destination, _name, _status, _bytes, *, client):
        path = Path(destination) / "track.flac"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"audio")
        return path

    monkeypatch.setattr(lucida, "_start_download", start)
    monkeypatch.setattr(lucida, "_run_job", run_job)
    monkeypatch.setattr(lucida, "_ingest", lambda path, _out: {"status": "ok", "path": str(path), "inbox_path": str(path)})

    result = lucida.download("https://music.amazon.com/album", "album", "amazon")

    assert [parse_qs(urlsplit(url).query, keep_blank_values=True)["country"] for url in client.urls] == [[""], ["US"]]
    assert countries == ["US"]
    assert result["items"][0]["status"] == "ok"


def test_amazon_album_uses_explicit_country_without_storefront_fallback(monkeypatch, tmp_path):
    client = CountryResponseClient({"GB": "gb"})
    monkeypatch.setattr(lucida, "_load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(lucida, "_client", lambda: client)
    monkeypatch.setattr(lucida, "_resolve_output_dir", lambda: tmp_path)
    monkeypatch.setattr(lucida, "_parse_page_data", lambda _page: {"info": {"type": "album", "tracks": [{"url": "https://www.qobuz.com/track", "title": "Track", "csrf": "token"}]}})

    result = lucida.download("https://www.qobuz.com/album", "album", "amazon", country="GB")
    assert len(result["items"]) == 1
    assert [parse_qs(urlsplit(url).query, keep_blank_values=True)["country"] for url in client.urls] == [["GB"]]


def test_amazon_album_with_no_usable_storefront_never_starts_download(monkeypatch, tmp_path):
    client = CountryResponseClient({"": "default", "US": "us", "GB": "gb", "JP": "jp"})
    monkeypatch.setattr(lucida, "_load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(lucida, "_client", lambda: client)
    monkeypatch.setattr(lucida, "_resolve_output_dir", lambda: tmp_path)
    monkeypatch.setattr(lucida, "_parse_page_data", lambda _page: {
        "info": {"type": "album", "tracks": [{
            "url": "https://www.qobuz.com/track", "title": "Track", "csrf": "",
        }]},
    })
    monkeypatch.setattr(
        lucida, "_start_download", lambda *_args, **_kwargs: pytest.fail("unusable storefront must not start downloads")
    )

    with pytest.raises(lucida.LucidaReleaseUnavailable):
        lucida.download("https://www.qobuz.com/album", "album", "amazon")
    assert [parse_qs(urlsplit(url).query, keep_blank_values=True)["country"] for url in client.urls] == [
        [""], ["US"], ["GB"], ["JP"],
    ]


@pytest.mark.parametrize("jobs", [0, 9, 3.0, True, "many"])
def test_direct_download_rejects_invalid_jobs_before_access(jobs, monkeypatch):
    monkeypatch.setattr(lucida, "_require_access", lambda: pytest.fail("invalid jobs must fail before access"))

    with pytest.raises(ValueError, match="jobs"):
        lucida.download("https://example.test/album", "album", jobs=jobs)


def test_download_reports_failed_track_and_continues_album(monkeypatch, tmp_path):
    client = FakeClient()
    monkeypatch.setattr(lucida, "_load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(lucida, "_client", lambda: client)
    monkeypatch.setattr(lucida, "_resolve_output_dir", lambda: tmp_path)
    monkeypatch.setattr(lucida, "_parse_page_data", lambda html: {
        "info": {"type": "album", "tracks": [
            {"url": "https://www.qobuz.com/fails", "title": "Fails", "csrf": "bad"},
            {"url": "https://www.qobuz.com/works", "title": "Works", "csrf": "good"},
        ]},
    })

    async def start(track, expiry, country, *, client):
        if track["csrf"] == "bad":
            raise RuntimeError("remote failure")
        return ("good", "server")

    async def run_job(handoff, server, dest_dir, name, on_status, on_bytes, *, client):
        path = Path(dest_dir) / "complete.flac"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"complete")
        return path

    monkeypatch.setattr(lucida, "_start_download", start)
    monkeypatch.setattr(lucida, "_run_job", run_job)
    monkeypatch.setattr(lucida, "_ingest", lambda path, out: {"status": "skip", "path": str(path), "inbox_path": str(path)})

    result = lucida.download("https://www.qobuz.com/album", "album", "qobuz", jobs=1)

    assert [(item["url"], item["status"]) for item in result["items"]] == [
        ("https://www.qobuz.com/fails", "fail"),
        ("https://www.qobuz.com/works", "skip"),
    ]
    assert result["items"][0]["error"] == "lucida_item_failed"


def test_download_propagates_access_error_and_cancels_peers(monkeypatch, tmp_path):
    client = FakeClient()
    monkeypatch.setattr(lucida, "_load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(lucida, "_client", lambda: client)
    monkeypatch.setattr(lucida, "_resolve_output_dir", lambda: tmp_path)
    monkeypatch.setattr(lucida, "_parse_page_data", lambda _html: {"info": {"type": "album", "tracks": [
        {"url": "https://www.qobuz.com/track/1", "title": "one", "csrf": "1"},
        {"url": "https://www.qobuz.com/track/2", "title": "two", "csrf": "2"},
    ]}, "expiry": 1})

    async def start(track, *_args, **_kwargs):
        raise LucidaAccessRequired("expired")

    monkeypatch.setattr(lucida, "_start_download", start)
    with pytest.raises(LucidaAccessRequired):
        lucida.download("https://www.qobuz.com/album/x", "album", jobs=2)


@pytest.mark.parametrize("url", [
    "https://www.qobuz.com/us-en/album/example/123",
    "https://music.amazon.com/albums/B000/example",
])
def test_start_download_accepts_supported_provider_urls(url):
    client = FakeClient()
    async def post(_url, **_kwargs):
        return FakeResponse({"handoff": "h-1", "server": "s-1"})
    client.post = post
    asyncio.run(download.start_download({"url": url, "csrf": "csrf"}, 1, "US", client=client))


def test_start_download_rejects_attacker_provider_host():
    with pytest.raises(ValueError, match="supported"):
        asyncio.run(download.start_download({"url": "https://qobuz.com.attacker.test/track", "csrf": "csrf"}, 1, "US", client=FakeClient()))


def test_download_rejects_attacker_release_url_before_request(monkeypatch):
    monkeypatch.setattr(lucida, "_load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(lucida, "_client", lambda: pytest.fail("attacker URL must not reach Lucida"))

    with pytest.raises(ValueError, match="supported"):
        lucida.download("https://qobuz.com.attacker.test/album", "album")


def test_download_progress_callback_failure_does_not_abort_album(monkeypatch, tmp_path):
    client = FakeClient()
    monkeypatch.setattr(lucida, "_load_clearance", lambda: ("clearance", "agent"))
    monkeypatch.setattr(lucida, "_client", lambda: client)
    monkeypatch.setattr(lucida, "_resolve_output_dir", lambda: tmp_path)
    monkeypatch.setattr(lucida, "_parse_page_data", lambda html: {
        "info": {"type": "album", "tracks": [
            {"url": "https://www.qobuz.com/one", "title": "One", "csrf": "one"},
            {"url": "https://www.qobuz.com/two", "title": "Two", "csrf": "two"},
        ]},
    })

    async def start(track, expiry, country, *, client):
        return (track["csrf"], "server")

    async def run_job(handoff, server, dest_dir, name, on_status, on_bytes, *, client):
        path = Path(dest_dir) / f"{handoff}.flac"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"complete")
        on_status("downloaded")
        on_bytes(8)
        return path

    monkeypatch.setattr(lucida, "_start_download", start)
    monkeypatch.setattr(lucida, "_run_job", run_job)
    monkeypatch.setattr(lucida, "_ingest", lambda path, out: {
        "status": "ok", "path": str(out / path.name), "inbox_path": str(path), "error": ""
    })

    def broken_progress(event):
        raise RuntimeError(f"progress failed: {event['type']}")

    result = lucida.download("https://www.qobuz.com/album", "album", progress=broken_progress)

    assert [item["status"] for item in result["items"]] == ["ok", "ok"]


def test_ingest_preserves_complete_inbox_file_when_library_move_skips_or_fails(monkeypatch, tmp_path):
    from src.lucida.ingest import ingest

    inbox = tmp_path / "Inbox"
    inbox.mkdir()
    audio = inbox / "complete.flac"
    audio.write_bytes(b"complete audio")

    import src.pipeline as pipeline

    monkeypatch.setattr(pipeline, "move_to_library_result", lambda path, out: type(
        "Result", (), {"status": "conflict", "path": None, "error": ""}
    )())
    skipped = ingest(audio, tmp_path)
    assert skipped == {"status": "skip", "path": str(audio), "inbox_path": str(audio), "error": ""}
    assert audio.read_bytes() == b"complete audio"

    monkeypatch.setattr(pipeline, "move_to_library_result", lambda path, out: type(
        "Result", (), {"status": "failed", "path": None, "error": "disk error"}
    )())
    failed = ingest(audio, tmp_path)
    assert failed["status"] == "fail"
    assert failed["path"] == str(audio)
    assert failed["error"] == "ingest_failed"
    assert audio.read_bytes() == b"complete audio"


def test_download_submodule_then_public_adapter_keeps_callable_module_api():
    import subprocess
    import sys

    script = """
import importlib
module = importlib.import_module('src.lucida.download')
public = importlib.import_module('src.lucida')
assert public.download is module
assert callable(public.download)
assert public.download.start_download is module.start_download
"""
    subprocess.run([sys.executable, "-c", script], check=True)


def test_ingest_never_reports_ok_for_missing_download(tmp_path):
    from src.lucida.ingest import ingest

    result = ingest(tmp_path / "Inbox" / "missing.flac", tmp_path)

    assert result["status"] == "fail"
    assert result["path"] == ""
