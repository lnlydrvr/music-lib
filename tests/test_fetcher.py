"""Tests for src/fetcher.py (Deezer API client)."""
from __future__ import annotations

import json
import time

import pytest

from src import fetcher
from src.fetcher import (
    COVER_BYTE_THRESHOLD,
    FetchedTags,
    fetch_tags,
    search_deezer,
    download_cover,
    download_thumbnail,
)


class FakeResponse:
    def __init__(self, payload: bytes = b"{}"):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _install_urlopen(monkeypatch, sequence, sleep_seconds=None):
    """Return urlopen mock popping responses from `sequence`."""
    calls = {"n": 0, "requests": []}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        calls["requests"].append(req)
        item = sequence.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)

    monkeypatch.setattr(fetcher.urllib.request, "urlopen", fake_urlopen)
    if sleep_seconds is not None:
        sleeps = []

        def fake_sleep(sec):
            sleeps.append(sec)

        monkeypatch.setattr(fetcher.time, "sleep", fake_sleep)
        return calls, sleeps
    return calls


def _patch_request(monkeypatch, handler):
    calls = []

    def fake(url, retries=2, timeout=15):
        calls.append((url, timeout))
        return handler(url, timeout)

    monkeypatch.setattr(fetcher, "_request", fake)
    return calls


@pytest.fixture(autouse=True)
def _clear_caches():
    fetcher.clear_deezer_album_cache()
    fetcher._COVER_CACHE.clear()
    yield
    fetcher.clear_deezer_album_cache()
    fetcher._COVER_CACHE.clear()


# --- _request --------------------------------------------------------


class TestRequest:
    def test_success_parses_json(self, monkeypatch):
        calls = _install_urlopen(monkeypatch, [b'{"a": 1}'])
        assert fetcher._request("http://x") == {"a": 1}

    def test_sends_user_agent(self, monkeypatch):
        calls = _install_urlopen(monkeypatch, [b"{}"])
        fetcher._request("http://x")
        ua = {
            k.lower(): v
            for k, v in calls["requests"][0].header_items()
        }["user-agent"]
        assert ua == fetcher.USER_AGENT

    def test_retries_then_succeeds(self, monkeypatch):
        _, sleeps = _install_urlopen(
            monkeypatch, [OSError("net"), OSError("net"), b'{"ok": true}'], sleep_seconds=True
        )
        assert fetcher._request("http://x") == {"ok": True}
        assert len(sleeps) == 2
        assert sleeps == [1.5, 3.0]

    def test_all_fail_returns_none(self, monkeypatch):
        _, sleeps = _install_urlopen(
            monkeypatch, [OSError("a"), OSError("b"), OSError("c")], sleep_seconds=True
        )
        assert fetcher._request("http://x") is None
        assert len(sleeps) == 2

    def test_no_retries(self, monkeypatch):
        calls = _install_urlopen(monkeypatch, [OSError("a")])
        assert fetcher._request("http://x", retries=0) is None
        assert calls["n"] == 1

    def test_429_waits_retry_after_then_succeeds(self, monkeypatch):
        from urllib.error import HTTPError

        err = HTTPError("http://x", 429, "err", {"Retry-After": "3"}, None)
        calls, sleeps = _install_urlopen(
            monkeypatch, [err, b'{"ok": true}'], sleep_seconds=True
        )
        assert fetcher._request("http://x") == {"ok": True}
        assert calls["n"] == 2
        assert len(sleeps) == 1
        assert 5.0 <= sleeps[0] <= 5.5  # Retry-After=3 поднимается до минимума 5 + джиттер

    def test_429_gives_up_after_four_waits(self, monkeypatch):
        from urllib.error import HTTPError

        errors = [HTTPError("http://x", 429, "err", {"Retry-After": "1"}, None)
                  for _ in range(5)]
        calls = _install_urlopen(monkeypatch, errors)
        assert fetcher._request("http://x", retries=0) is None
        assert calls["n"] == 5


# --- Deezer helpers --------------------------------------------------


class TestAlbumInfo:
    def test_empty_album_id(self):
        assert fetcher._get_deezer_album_info("") == ("", "", "", "")

    def test_request_missing(self, monkeypatch):
        _patch_request(monkeypatch, lambda *a: None)
        assert fetcher._get_deezer_album_info("1") == ("", "", "", "")

    def test_full(self, monkeypatch):
        _patch_request(monkeypatch, lambda *a: {
            "genres": {"data": [{"name": "Rock"}]},
            "release_date": "2005-07-01",
            "label": "Label",
            "copyright": "(c) 2005",
            "upc": "12345",
        })
        assert fetcher._get_deezer_album_info("1") == (
            "Rock", "2005", "Label", "(c) 2005",
        )

    def test_no_genres(self, monkeypatch):
        _patch_request(monkeypatch, lambda *a: {"release_date": "1999"})
        genre, year, *_ = fetcher._get_deezer_album_info("1")
        assert genre == ""
        assert year == "1999"


class TestTrackNumber:
    def test_no_album_no_title(self):
        assert fetcher._get_deezer_track_number("", "x") == ""
        assert fetcher._get_deezer_track_number("1", "") == ""

    def test_request_missing(self, monkeypatch):
        _patch_request(monkeypatch, lambda *a: {})
        assert fetcher._get_deezer_track_number("1", "Song") == ""

    def test_match_found(self, monkeypatch):
        _patch_request(monkeypatch, lambda *a: {
            "data": [
                {"title": "Intro", "track_position": 1},
                {"title": "My Song (Remix)", "track_position": 7},
            ]
        })
        assert fetcher._get_deezer_track_number("1", "My Song") == "7"

    def test_no_match(self, monkeypatch):
        _patch_request(monkeypatch, lambda *a: {"data": [{"title": "Other"}]})
        assert fetcher._get_deezer_track_number("1", "Song") == ""


class TestSearchDeezer:
    def test_returns_tracks(self, monkeypatch):
        calls = _patch_request(monkeypatch, lambda url, t: {
            "data": [{"id": 1}, {"id": 2}]
        })
        out = search_deezer("Song", "Artist")
        assert len(out) == 2
        assert "q=Artist+Song" in calls[0][0] or "q=Artist%20Song" in calls[0][0]

    def test_artist_optional(self, monkeypatch):
        calls = _patch_request(monkeypatch, lambda url, t: {"data": []})
        search_deezer("OnlyTitle")
        assert "OnlyTitle" in calls[0][0]

    def test_empty_data(self, monkeypatch):
        _patch_request(monkeypatch, lambda url, t: {})
        assert search_deezer("x") == []


class TestDownloadCover:
    def test_jpeg(self, monkeypatch):
        _install_urlopen(monkeypatch, [b"\xff\xd8\xff\xe0"] + [b"x"] * 0)
        data, mime = download_cover("http://x/cover.jpg")
        assert mime == "image/jpeg"
        assert data == b"\xff\xd8\xff\xe0"

    def test_png_mime(self, monkeypatch):
        _install_urlopen(monkeypatch, [b"png"])
        data, mime = download_cover("http://x/cover.png")
        assert mime == "image/png"


class TestDownloadThumbnail:
    def test_squares_and_returns_jpeg(self, monkeypatch):
        calls = []

        def fake_download_cover(url):
            calls.append(url)
            return b"raw", "image/jpeg"

        monkeypatch.setattr(fetcher, "download_cover", fake_download_cover)
        monkeypatch.setattr(fetcher, "_square_image", lambda data: data + b"!")
        data, mime = download_thumbnail("http://x/t.jpg")
        assert calls == ["http://x/t.jpg"]
        assert data == b"raw!"
        assert mime == "image/jpeg"


class TestCoverCache:
    def test_same_url_downloaded_once(self, monkeypatch):
        calls = _install_urlopen(monkeypatch, [b"\xff\xd8\xff\xe0", b"second"])
        assert download_cover("http://x/a.jpg") == (b"\xff\xd8\xff\xe0", "image/jpeg")
        assert download_cover("http://x/a.jpg") == (b"\xff\xd8\xff\xe0", "image/jpeg")
        assert calls["n"] == 1

    def test_different_urls_not_shared(self, monkeypatch):
        calls = _install_urlopen(monkeypatch, [b"one", b"two"])
        assert download_cover("http://x/a.jpg")[0] == b"one"
        assert download_cover("http://x/b.jpg")[0] == b"two"
        assert calls["n"] == 2

    def test_clear_reset(self, monkeypatch):
        calls = _install_urlopen(monkeypatch, [b"one", b"two"])
        download_cover("http://x/a.jpg")
        fetcher._COVER_CACHE.clear()
        assert download_cover("http://x/a.jpg")[0] == b"two"
        assert calls["n"] == 2

    def test_ttl_expiry(self, monkeypatch):
        calls = _install_urlopen(monkeypatch, [b"one", b"two"])
        download_cover("http://x/a.jpg")
        url = "http://x/a.jpg"
        ts, data = fetcher._COVER_CACHE[url]
        fetcher._COVER_CACHE[url] = (ts - fetcher._COVER_CACHE_TTL - 1, data)
        assert download_cover(url)[0] == b"two"
        assert calls["n"] == 2


# --- offline image pipeline -------------------------------------------

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class TestPrepareCover:
    def test_small_image_passthrough(self):
        data = b"\x00" * (COVER_BYTE_THRESHOLD - 1)
        assert fetcher._prepare_cover(data) == data

    def test_exact_threshold_passthrough(self):
        data = b"\x00" * COVER_BYTE_THRESHOLD
        assert fetcher._prepare_cover(data) == data

    def test_unreadable_dimensions_passthrough(self, monkeypatch):
        data = b"\x00" * (COVER_BYTE_THRESHOLD + 1)
        monkeypatch.setattr(fetcher, "_image_size", lambda d: (None, None))
        assert fetcher._prepare_cover(data) == data

    def test_within_max_side_passthrough(self, monkeypatch):
        data = b"\x00" * (COVER_BYTE_THRESHOLD + 1)
        monkeypatch.setattr(fetcher, "_image_size", lambda d: (400, 300))
        assert fetcher._prepare_cover(data) == data

    def test_compresses(self, monkeypatch, tmp_path):
        data = b"\x00" * (COVER_BYTE_THRESHOLD + 1)

        def fake_run(cmd, **kw):
            out_path = cmd[-1]
            (tmp_path / out_path).write_bytes(b"smaller")
            return None

        monkeypatch.setattr(fetcher, "_image_size", lambda d: (1200, 800))
        monkeypatch.setattr(fetcher.subprocess, "run", fake_run)
        out = fetcher._prepare_cover(data)
        assert out == b"smaller"
        assert out != data

    def test_ffmpeg_error_passthrough(self, monkeypatch):
        data = b"\x00" * (COVER_BYTE_THRESHOLD + 1)
        monkeypatch.setattr(fetcher, "_image_size", lambda d: (1200, 800))

        def boom(cmd, **kw):
            raise FileNotFoundError("ffmpeg")

        monkeypatch.setattr(fetcher.subprocess, "run", boom)
        assert fetcher._prepare_cover(data) == data


class TestSquareImage:
    def test_already_square(self, monkeypatch):
        data = b"img"
        monkeypatch.setattr(fetcher, "_image_size", lambda d: (100, 100))
        assert fetcher._square_image(data) == data

    def test_unknown_size_passthrough(self, monkeypatch):
        data = b"img"
        monkeypatch.setattr(fetcher, "_image_size", lambda d: (None, None))
        assert fetcher._square_image(data) == data

    def test_squares_non_square(self, monkeypatch, tmp_path):
        data = b"img"
        monkeypatch.setattr(fetcher, "_image_size", lambda d: (200, 100))

        def fake_run(cmd, **kw):
            (tmp_path / cmd[-1]).write_bytes(b"square")
            return None

        monkeypatch.setattr(fetcher.subprocess, "run", fake_run)
        assert fetcher._square_image(data) == b"square"

    def test_ffmpeg_error_passthrough(self, monkeypatch):
        monkeypatch.setattr(fetcher, "_image_size", lambda d: (200, 100))

        def boom(cmd, **kw):
            raise RuntimeError

        monkeypatch.setattr(fetcher.subprocess, "run", boom)
        assert fetcher._square_image(b"data") == b"data"


class TestImageSize:
    def test_parses_probe(self, monkeypatch):
        out = json.dumps({"streams": [{"width": 640, "height": 480}]}).encode()

        def fake_run(cmd, **kw):
            class _P:
                stdout = out

            return _P()

        monkeypatch.setattr(fetcher.subprocess, "run", fake_run)
        assert fetcher._image_size(b"data") == (640, 480)

    def test_ffprobe_error(self, monkeypatch):
        def boom(cmd, **kw):
            raise FileNotFoundError

        monkeypatch.setattr(fetcher.subprocess, "run", boom)
        assert fetcher._image_size(b"data") == (None, None)


# --- fetch_tags --------------------------------------------------------

BASE_TRACK = {
    "id": 42,
    "title": "My Song",
    "artist": {"name": "Artist"},
    "album": {
        "id": 7,
        "title": "Album",
        "cover_xl": "http://c/xl.jpg",
        "cover_big": "http://c/big.jpg",
    },
}


class TestFetchTags:
    def test_not_found_returns_none(self, monkeypatch):
        monkeypatch.setattr(fetcher, "search_deezer", lambda *a: [])
        _patch_request(monkeypatch, lambda *a: {})
        assert fetch_tags("No Such Song", "Nobody") is None

    def test_search_then_fetch(self, monkeypatch):
        calls = _patch_request(monkeypatch, lambda url, t: None)
        monkeypatch.setattr(fetcher, "search_deezer", lambda *a: [dict(BASE_TRACK)])
        out = fetch_tags("My Song", "Artist")
        assert out is not None
        assert isinstance(out, FetchedTags)

    def test_maps_fields_with_detail(self, monkeypatch):
        detail = {
            "isrc": "ISRC123",
            "disk_number": 1,
            "duration": 240,
            "rank": 999,
            "explicit_lyrics": True,
            "contributors": [
                {"name": "John", "role": "Composer"},
                {"name": "Jane", "role": "Composer"},
                {"name": "Bob", "role": "Artist"},
            ],
        }
        album = {
            "genres": {"data": [{"name": "Pop"}]},
            "release_date": "2010-05-20",
            "label": "Big Label",
            "copyright": "(c) 2010",
            "upc": "0099",
        }
        tracks = {"data": [{"title": "My Song", "track_position": 4}]}

        def handler(url, t):
            if url.startswith("https://api.deezer.com/track/"):
                return detail
            if url.endswith("/tracks"):
                return tracks
            if "/album/" in url:
                return album
            return None

        _patch_request(monkeypatch, handler)
        out = fetch_tags("", "", "", track_data=BASE_TRACK)
        assert out.title == "My Song"
        assert out.artist == "Artist"
        assert out.album == "Album"
        assert out.cover_url == "http://c/xl.jpg"
        assert out.year == "2010"
        assert out.genre == "Pop"
        assert out.track_number == "4"
        assert out.isrc == "ISRC123"
        assert out.disc_number == "1"
        assert out.duration == "240"
        assert out.rank == "999"
        assert out.explicit_lyrics == "Да"
        assert out.composer == "John, Jane"
        assert out.label == "Big Label"
        assert out.copyright == "(c) 2010"

    def test_no_track_detail(self, monkeypatch):
        def handler(url, t):
            if url.endswith("/tracks"):
                return {"data": [{"title": "My Song"}]}
            if "/album/" in url:
                return {"genres": {"data": []}, "release_date": ""}
            return None

        _patch_request(monkeypatch, handler)
        out = fetch_tags("", "", "", track_data=BASE_TRACK)
        assert out.isrc == ""
        assert out.disc_number == ""
        assert out.explicit_lyrics == ""
        assert out.composer == ""

    def test_album_cover_fallback(self, monkeypatch):
        no_big = dict(BASE_TRACK)
        no_big["album"] = {"id": 7, "title": "Album", "cover_big": "http://c/big.jpg"}
        _patch_request(monkeypatch, lambda url, t: None)
        out = fetch_tags("", "", "", track_data=no_big)
        assert out.cover_url == "http://c/big.jpg"


class TestAlbumCache:
    def test_album_info_cached(self, monkeypatch):
        calls = _patch_request(monkeypatch, lambda url, t: {
            "genres": {"data": [{"name": "Rock"}]},
            "release_date": "2005-07-01",
            "label": "Label",
            "copyright": "(c) 2005",
        })
        assert fetcher._get_deezer_album_info("42") == ("Rock", "2005", "Label", "(c) 2005")
        assert fetcher._get_deezer_album_info(42) == ("Rock", "2005", "Label", "(c) 2005")
        album_calls = [u for u, _ in calls if "/album/" in u]
        assert len(album_calls) == 1

    def test_album_tracks_cached(self, monkeypatch):
        calls = _patch_request(monkeypatch, lambda url, t: {
            "data": [{"title": "My Song", "track_position": 3}]
        })
        assert fetcher._get_deezer_track_number("42", "My Song") == "3"
        assert fetcher._get_deezer_track_number("42", "Other") == ""
        track_calls = [u for u, _ in calls if u.endswith("/tracks")]
        assert len(track_calls) == 1

    def test_clear_reset(self, monkeypatch):
        calls = _patch_request(monkeypatch, lambda url, t: {
            "genres": {"data": []}, "release_date": "",
        })
        fetcher._get_deezer_album_info("42")
        fetcher.clear_deezer_album_cache()
        fetcher._get_deezer_album_info("42")
        album_calls = [u for u, _ in calls if "/album/" in u]
        assert len(album_calls) == 2


class TestFetchTagsParallel:
    def test_detail_album_tracks_run_in_parallel(self, monkeypatch):
        """Три запроса fetch_tags идут одновременно, а не друг за другом."""
        import threading

        active = set()
        peak = [0]
        lock = threading.Lock()

        def slow_handler(url, t):
            with lock:
                active.add(url)
                peak[0] = max(peak[0], len(active))
            time.sleep(0.1)
            with lock:
                active.discard(url)
            if url.endswith("/tracks"):
                return {"data": [{"title": "My Song", "track_position": 2}]}
            if "/album/" in url:
                return {"genres": {"data": [{"name": "Pop"}]}, "release_date": "2010"}
            return {"isrc": "X"}

        _patch_request(monkeypatch, slow_handler)
        out = fetch_tags("", "", "", track_data=dict(BASE_TRACK))
        assert out.track_number == "2"
        assert peak[0] >= 2