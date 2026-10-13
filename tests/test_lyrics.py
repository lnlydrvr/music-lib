"""Tests for src/lyrics.py (LRCLIB API client)."""
from __future__ import annotations

import threading

from urllib.error import HTTPError

from src import lyrics
from src.lyrics import fetch_lyrics


class FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _http_error(code: int, headers: dict | None = None):
    return HTTPError("http://lrclib.net", code, "err", headers or {}, None)


def _install_urlopen(monkeypatch, sequence):
    """Queue of responses; an Exception instance means 'raise'."""
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        item = sequence.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)

    monkeypatch.setattr(lyrics.urllib.request, "urlopen", fake_urlopen)
    return calls


class TestRequest:
    def test_concurrent_requests_are_serialized(self, monkeypatch):
        active = 0
        maximum = 0
        lock = threading.Lock()
        release = threading.Event()

        def fake_urlopen(req, timeout=None):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            release.wait(1)
            with lock:
                active -= 1
            return FakeResponse(b'{"ok": 1}')

        monkeypatch.setattr(lyrics.urllib.request, "urlopen", fake_urlopen)
        threads = [threading.Thread(target=lyrics._request, args=("http://x",)) for _ in range(2)]
        for thread in threads:
            thread.start()
        release.set()
        for thread in threads:
            thread.join()

        assert maximum == 1

    def test_success(self, monkeypatch):
        _install_urlopen(monkeypatch, [b'{"hit": true}'])
        assert lyrics._request("http://x") == {"hit": True}

    def test_429_waits_and_succeeds(self, monkeypatch):
        sleeps = []
        _install_urlopen(monkeypatch, [_http_error(429, {"Retry-After": "2"}), b'{"ok": 1}'])
        monkeypatch.setattr(lyrics.time, "sleep", lambda s: sleeps.append(s))
        assert lyrics._request("http://x", retries=1) == {"ok": 1}
        assert sleeps == [2]

    def test_429_on_last_attempt_does_not_sleep(self, monkeypatch):
        sleeps = []
        _install_urlopen(monkeypatch, [_http_error(429, {"Retry-After": "2"})])
        monkeypatch.setattr(lyrics.time, "sleep", lambda s: sleeps.append(s))
        assert lyrics._request("http://x", retries=0) is None
        assert sleeps == []

    def test_malformed_retry_after_uses_safe_default(self, monkeypatch):
        sleeps = []
        _install_urlopen(monkeypatch, [_http_error(429, {"Retry-After": "later"}), b'{"ok": 1}'])
        monkeypatch.setattr(lyrics.time, "sleep", lambda s: sleeps.append(s))
        assert lyrics._request("http://x", retries=1) == {"ok": 1}
        assert sleeps == [5]

    def test_404_returns_none(self, monkeypatch):
        calls = _install_urlopen(monkeypatch, [_http_error(404)])
        assert lyrics._request("http://x") is None
        assert calls["n"] == 1

    def test_other_http_error_retries_then_none(self, monkeypatch):
        sleeps = []
        _install_urlopen(monkeypatch, [_http_error(500), _http_error(500), _http_error(500)])
        monkeypatch.setattr(lyrics.time, "sleep", lambda s: sleeps.append(s))
        assert lyrics._request("http://x") is None
        assert sleeps == [1.5, 3.0]

    def test_generic_exception_retries_then_none(self, monkeypatch):
        sleeps = []
        _install_urlopen(monkeypatch, [OSError("a"), OSError("b"), OSError("c")])
        monkeypatch.setattr(lyrics.time, "sleep", lambda s: sleeps.append(s))
        assert lyrics._request("http://x") is None
        assert len(sleeps) == 2


class TestFetchLyrics:
    def test_success_is_cached_by_exact_duration(self, monkeypatch):
        calls = []
        _patch_request(monkeypatch, lambda url: calls.append(url) or {
            "trackName": "Song", "syncedLyrics": "[00:01] line",
        })
        assert fetch_lyrics("Song", "Artist", "Album", 100) is not None
        assert fetch_lyrics("Song", "Artist", "Album", 100) is not None
        assert fetch_lyrics("Song", "Artist", "Album", 101) is not None
        assert len(calls) == 2

    def test_not_found_is_cached_but_transient_empty_response_is_not(self, monkeypatch):
        calls = []
        _patch_request(monkeypatch, lambda url: calls.append(url) or None)
        assert fetch_lyrics("Song") is None
        assert fetch_lyrics("Song") is None
        assert len(calls) == 2

    def test_confirmed_not_found_is_cached(self, monkeypatch):
        calls = []
        _patch_request(monkeypatch, lambda url: calls.append(url) or lyrics._NOT_FOUND)
        assert fetch_lyrics("Song") is None
        assert fetch_lyrics("Song") is None
        assert len(calls) == 1

    def test_returns_result(self, monkeypatch):
        _patch_request(monkeypatch, {
            "trackName": "Song", "artistName": "Artist", "albumName": "Album",
            "duration": 200, "plainLyrics": "la la", "syncedLyrics": "[00:01.00] la",
        })
        out = fetch_lyrics("Song", "Artist", "Album", 200)
        assert out is not None
        assert out.track_name == "Song"
        assert out.plain_lyrics == "la la"
        assert out.synced_lyrics == "[00:01.00] la"
        assert out.duration == 200

    def test_instrumental_returns_none(self, monkeypatch):
        _patch_request(monkeypatch, {"instrumental": True})
        assert fetch_lyrics("Song") is None

    def test_no_data_returns_none(self, monkeypatch):
        _patch_request(monkeypatch, None)
        assert fetch_lyrics("Song") is None

    def test_empty_lyrics_fields_coerced(self, monkeypatch):
        _patch_request(monkeypatch, {"trackName": "T", "duration": 3, "plainLyrics": None})
        out = fetch_lyrics("Song")
        assert out is not None
        assert out.plain_lyrics == ""
        assert out.synced_lyrics == ""


def _patch_request(monkeypatch, result):
    lyrics._cache.clear()
    monkeypatch.setattr(
        lyrics, "_request",
        lambda url, *a, **k: result(url) if callable(result) else result,
    )
