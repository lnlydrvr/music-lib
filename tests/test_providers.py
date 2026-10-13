"""Tests for src/providers.py — multi-source metadata parsers."""
from __future__ import annotations

import pytest
from urllib.error import HTTPError

from src import providers
from src.providers import (
    ProviderRecord,
    TAGGABLE_FIELDS,
    available_sources,
    fetch_all,
    _search_itunes,
)


@pytest.fixture(autouse=True)
def _fresh_throttle_state(monkeypatch):
    """Изолировать состояние троттлинга/кулдаунов между тестами."""
    monkeypatch.setattr(providers, "_HOST_STATE", {})
    monkeypatch.setattr(providers, "_COOLDOWN_UNTIL", {})


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
    return HTTPError("http://x", code, "err", headers or {}, None)


def _install_urlopen(monkeypatch, sequence):
    """Queue of responses; an Exception instance means 'raise'."""
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        item = sequence.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)

    monkeypatch.setattr(providers.urllib.request, "urlopen", fake_urlopen)
    return calls


class TestRequest:
    def test_success(self, monkeypatch):
        _install_urlopen(monkeypatch, [b'{"results": []}'])
        assert providers._request("http://x") == {"results": []}

    def test_429_waits_retry_after_then_succeeds(self, monkeypatch):
        sleeps = []
        _install_urlopen(monkeypatch, [_http_error(429, {"Retry-After": "7"}), b'{"ok": 1}'])
        monkeypatch.setattr(providers.time, "sleep", lambda s: sleeps.append(s))
        assert providers._request("http://x") == {"ok": 1}
        assert sleeps == pytest.approx([7.0])  # ожидание кулдауна в _throttle

    def test_429_backoff_grows_without_header(self, monkeypatch):
        sleeps = []
        _install_urlopen(monkeypatch, [
            _http_error(429), _http_error(429), _http_error(429), b'{"ok": 1}',
        ])
        monkeypatch.setattr(providers.time, "sleep", lambda s: sleeps.append(s))
        assert providers._request("http://x") == {"ok": 1}
        assert sleeps == pytest.approx([5.0, 10.0, 20.0])  # экспоненциальный бэкофф

    def test_429_caps_retry_after_at_65(self, monkeypatch):
        sleeps = []
        _install_urlopen(monkeypatch, [_http_error(429, {"Retry-After": "120"}), b'{"ok": 1}'])
        monkeypatch.setattr(providers.time, "sleep", lambda s: sleeps.append(s))
        assert providers._request("http://x") == {"ok": 1}
        assert sleeps == pytest.approx([65.0])

    def test_429_gives_up_after_five_waits(self, monkeypatch):
        errors = [_http_error(429, {"Retry-After": "1"}) for _ in range(6)]
        calls = _install_urlopen(monkeypatch, errors)
        monkeypatch.setattr(providers.time, "sleep", lambda s: None)
        assert providers._request("http://x", retries=0) is None
        assert calls["n"] == 6  # 5 ожиданий + финальная попытка

    def test_429_cooldown_blocks_next_request_on_same_host(self, monkeypatch):
        """После 429 следующий запрос к хосту ждёт кулдаун, а не ловит 429."""
        sleeps = []
        calls = _install_urlopen(monkeypatch, [
            _http_error(429, {"Retry-After": "30"}), b'{"ok": 1}', b'{"ok": 2}',
        ])
        monkeypatch.setattr(providers.time, "sleep", lambda s: sleeps.append(s))
        assert providers._request("http://x") == {"ok": 1}
        assert providers._request("http://x") == {"ok": 2}
        # оба запроса дождивались один и тот же кулдаун в _throttle,
        # второй запрос не получил своего 429
        assert calls["n"] == 3
        assert sleeps == pytest.approx([30.0, 30.0])

    def test_other_http_error_uses_regular_retries(self, monkeypatch):
        sleeps = []
        _install_urlopen(monkeypatch, [_http_error(500), _http_error(500), b'{"ok": 1}'])
        monkeypatch.setattr(providers.time, "sleep", lambda s: sleeps.append(s))
        assert providers._request("http://x", retries=2) == {"ok": 1}
        assert sleeps == [1.5, 3.0]

    def test_non_throttled_host_does_not_sleep(self, monkeypatch):
        sleeps = []
        _install_urlopen(monkeypatch, [b'{"ok": 1}', b'{"ok": 2}'])
        monkeypatch.setattr(providers.time, "sleep", lambda s: sleeps.append(s))
        assert providers._request("http://unknown.host/a") == {"ok": 1}
        assert providers._request("http://unknown.host/b") == {"ok": 2}
        assert sleeps == []


class TestThrottle:
    def test_second_request_waits_min_interval(self, monkeypatch):
        sleeps = []
        monkeypatch.setattr(providers, "_HOST_MIN_INTERVAL", {"example.com": 0.5})
        monkeypatch.setattr(providers, "_HOST_STATE", {})
        monkeypatch.setattr(providers.time, "sleep", lambda s: sleeps.append(s))
        providers._throttle("http://example.com/a")
        assert sleeps == []  # первый запрос не ждёт
        providers._throttle("http://example.com/b")
        assert len(sleeps) == 1
        assert 0.4 <= sleeps[0] <= 0.5  # ~минимальный интервал

    def test_throttled_hosts_are_independent(self, monkeypatch):
        sleeps = []
        monkeypatch.setattr(providers, "_HOST_MIN_INTERVAL",
                            {"a.com": 0.5, "b.com": 0.5})
        monkeypatch.setattr(providers, "_HOST_STATE", {})
        monkeypatch.setattr(providers.time, "sleep", lambda s: sleeps.append(s))
        providers._throttle("http://a.com/1")
        providers._throttle("http://b.com/1")
        providers._throttle("http://a.com/2")
        assert len(sleeps) == 1

    def test_empty_interval_registry_is_noop(self, monkeypatch):
        monkeypatch.setattr(providers, "_HOST_MIN_INTERVAL", {})
        providers._throttle("http://a.com/1")  # не падает и ничего не делает

    def test_cooldown_applies_to_unthrottled_host_too(self, monkeypatch):
        """Кулдаун после 429 работает и для хостов без минимального интервала."""
        sleeps = []
        monkeypatch.setattr(providers.time, "sleep", lambda s: sleeps.append(s))
        providers._penalize("http://plain.host/a", 2.5)
        providers._throttle("http://plain.host/b")
        assert len(sleeps) == 1
        assert 2.0 <= sleeps[0] <= 2.5

    def test_cooldown_extends_but_not_shrinks(self, monkeypatch):
        sleeps = []
        monkeypatch.setattr(providers.time, "sleep", lambda s: sleeps.append(s))
        providers._penalize("http://c.host/a", 10.0)
        providers._penalize("http://c.host/b", 1.0)  # не сокращает кулдаун
        providers._throttle("http://c.host/c")
        assert 9.0 <= sleeps[0] <= 10.0


class TestProviderRecord:
    def test_summary(self):
        r = ProviderRecord(source="X", title="Espresso", album="Short n' Sweet", year="2024")
        assert r.summary() == "Espresso — Short n' Sweet — 2024"

    def test_summary_minimal(self):
        r = ProviderRecord(source="X", title="Espresso")
        assert r.summary() == "Espresso"

    def test_taggable_fields_has_labels(self):
        fields = {f for f, _label in TAGGABLE_FIELDS}
        assert "title" in fields
        assert "composer" in fields
        assert "publisher" in fields


class TestSearchItunes:
    def test_parses_results(self, monkeypatch):
        monkeypatch.setattr(
            providers, "_request",
            lambda *a, **k: {"results": [{
                "trackName": "Espresso", "artistName": "Sabrina Carpenter",
                "collectionName": "Short n' Sweet", "releaseDate": "2024-04-12",
                "primaryGenreName": "Поп", "trackNumber": 3, "discNumber": 1,
                "isrc": "USRC12400001", "artworkUrl100": "http://c/img/100x100bb.jpg",
            }]},
        )
        out = _search_itunes("Espresso", "Sabrina")
        assert len(out) == 1
        r = out[0]
        assert r.source == "iTunes"
        assert r.title == "Espresso"
        assert r.artist == "Sabrina Carpenter"
        assert r.album == "Short n' Sweet"
        assert r.year == "2024"
        assert r.genre == "Поп"
        assert r.track_number == "3"
        assert r.disc_number == "1"
        assert r.isrc == "USRC12400001"
        assert r.cover_url == "http://c/img/1000x1000bb.jpg"

    def test_cover_hires_noop_without_token(self):
        assert providers._itunes_cover_hires("") == ""
        assert providers._itunes_cover_hires("http://c/plain.jpg") == "http://c/plain.jpg"
        assert providers._itunes_cover_hires("http://c/100x100bb.jpg") == "http://c/1000x1000bb.jpg"

    def test_empty(self, monkeypatch):
        monkeypatch.setattr(providers, "_request", lambda *a, **k: None)
        assert _search_itunes("x") == []

    def test_no_results_key(self, monkeypatch):
        monkeypatch.setattr(providers, "_request", lambda *a, **k: {})
        assert _search_itunes("x") == []


class TestSearchDeezer:
    def test_parses_results(self, monkeypatch):
        from src.fetcher import FetchedTags

        monkeypatch.setattr("src.fetcher.search_deezer",
                            lambda *a, **k: [{"id": 1}])
        monkeypatch.setattr(
            "src.fetcher.fetch_tags",
            lambda *a, **k: FetchedTags(
                title="Espresso", artist="Sabrina Carpenter",
                album="Short n' Sweet", year="2024", genre="Поп",
                track_number="1", disc_number="1", isrc="USRC12400001",
                label="Jive", cover_url="http://c/art.jpg",
            ),
        )
        out = providers._search_deezer("Espresso", "Sabrina")
        assert len(out) == 1
        r = out[0]
        assert r.source == "Deezer"
        assert r.title == "Espresso"
        assert r.artist == "Sabrina Carpenter"
        assert r.genre == "Поп"
        assert r.publisher == "Jive"
        assert r.label == "Jive"
        assert r.cover_url == "http://c/art.jpg"

    def test_only_top_result_enriched(self, monkeypatch):
        """Детали качаются только для первого результата, остальные — из выдачи."""
        from src.fetcher import FetchedTags

        monkeypatch.setattr(
            "src.fetcher.search_deezer",
            lambda *a, **k: [
                {"id": 1, "title": "Espresso", "artist": {"name": "Sabrina Carpenter"},
                 "album": {"title": "Short n' Sweet", "cover_xl": "http://c/1.jpg"}},
                {"id": 2, "title": "Espresso (Remix)", "artist": {"name": "Sabrina Carpenter"},
                 "album": {"title": "Remixes", "cover_big": "http://c/2.jpg"}},
                {"id": 3, "title": "Please Please Please", "artist": {"name": "Sabrina Carpenter"},
                 "album": {"title": "Short n' Sweet"}},
            ],
        )
        calls = []

        def fake_fetch_tags(*a, **k):
            calls.append(k.get("track_data") or a)
            return FetchedTags(title="Espresso", artist="Sabrina Carpenter",
                               album="Short n' Sweet", year="2024", genre="Поп",
                               cover_url="http://c/1.jpg")

        monkeypatch.setattr("src.fetcher.fetch_tags", fake_fetch_tags)
        out = providers._search_deezer("Espresso", "Sabrina")
        assert len(calls) == 1  # детали только для топ-1
        assert len(out) == 3
        assert out[0].year == "2024"
        assert out[0].genre == "Поп"
        assert out[1].title == "Espresso (Remix)"
        assert out[1].album == "Remixes"
        assert out[1].cover_url == "http://c/2.jpg"
        assert out[1].year == ""  # без запросов деталей
        assert out[2].cover_url == ""

    def test_empty(self, monkeypatch):
        monkeypatch.setattr("src.fetcher.search_deezer", lambda *a, **k: [])
        monkeypatch.setattr("src.fetcher.fetch_tags", lambda *a, **k: None)
        assert providers._search_deezer("x") == []

    def test_error_returns_empty(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("net")

        monkeypatch.setattr("src.fetcher.search_deezer", boom)
        assert providers._search_deezer("x") == []


class TestSearchDiscogs:
    def _stub(self, monkeypatch, results, detail=None):
        def fake_request(url, *a, **k):
            if "/releases/" in url:
                return detail
            return results
        monkeypatch.setattr(providers, "_request", fake_request)

    def test_builds_record_from_detail(self, monkeypatch):
        self._stub(monkeypatch,
                   {"results": [{"type": "release", "id": 1,
                                 "title": "Sabrina Carpenter - Espresso",
                                 "year": "2024"}]},
                   detail={
                       "title": "Espresso",
                       "artists": [{"name": "Sabrina Carpenter"}],
                       "year": "2024",
                       "genres": ["Pop"],
                       "images": [{"type": "primary", "uri": "http://c/full.jpg"}],
                       "tracklist": [{"title": "Espresso"}],
                   })
        out = providers._search_discogs("Espresso", "Sabrina Carpenter")
        assert len(out) == 1
        r = out[0]
        assert r.source == "Discogs"
        assert r.title == "Espresso"
        assert r.artist == "Sabrina Carpenter"
        assert r.album_artist == "Sabrina Carpenter"
        assert r.album == "Espresso"
        assert r.year == "2024"
        assert r.genre == "Pop"
        assert r.cover_url == "http://c/full.jpg"

    def test_unmatched_track_falls_back_to_search_split(self, monkeypatch):
        self._stub(monkeypatch,
                   {"results": [{"type": "release", "id": 9,
                                 "title": "The Weeknd - Blinding Lights"}]},
                   detail={
                       "title": "Blinding Lights",
                       "artists": [{"name": "The Weeknd"}],
                       "tracklist": [{"title": "Blinding Lights"}],
                   })
        monkeypatch.setattr(providers, "_best_track_title", lambda *a: "")
        out = providers._search_discogs("Heartless", "The Weeknd")
        assert len(out) == 1
        assert out[0].title == "Blinding Lights"
        assert out[0].album == "Blinding Lights"

    def test_dedupes_releases(self, monkeypatch):
        def fake_detail(url, *a, **k):
            return {"title": "Espresso", "artists": [{"name": "Sabrina Carpenter"}],
                    "year": "2024", "tracklist": [{"title": "Espresso"}]}
        monkeypatch.setattr(providers, "_request", lambda u, *a, **k:
                            {"results": [{"type": "release", "id": i,
                                          "title": "Sabrina Carpenter - Espresso"}
                                         for i in range(3)]}
                            if "/releases/" not in u else fake_detail(u, *a, **k))
        out = providers._search_discogs("Espresso", "Sabrina Carpenter")
        assert len(out) == 1

    def test_skips_masters_and_failed_detail(self, monkeypatch):
        monkeypatch.setattr(
            providers, "_request",
            lambda u, *a, **k: {"results": [
                {"type": "master", "title": "X - Y", "id": 1},
                {"type": "release", "title": "X - Y", "id": 2},
            ]} if "/releases/" not in u else None,
        )
        out = providers._search_discogs("y", "x")
        assert out == []

    def test_details_capped_at_limit(self, monkeypatch):
        """Детали качаются только для топ-_DISCOGS_DETAIL_LIMIT релизов."""
        details = []

        def fake_request(url, *a, **k):
            if "/releases/" in url:
                details.append(url)
                return {"title": f"Album {len(details)}",
                        "artists": [{"name": "X"}],
                        "tracklist": [{"title": "y"}]}
            return {"results": [{"type": "release", "id": i, "title": "X - A"}
                                for i in range(4)]}

        monkeypatch.setattr(providers, "_request", fake_request)
        out = providers._search_discogs("y", "x")
        assert len(details) == providers._DISCOGS_DETAIL_LIMIT
        assert len(out) == providers._DISCOGS_DETAIL_LIMIT

    def test_empty(self, monkeypatch):
        monkeypatch.setattr(providers, "_request", lambda *a, **k: None)
        assert providers._search_discogs("x") == []

    def test_best_track_by_word_overlap(self):
        tl = [{"title": "Blinding Lights"}, {"title": "Album Cred"}]
        assert providers._best_track_title("blinding lights", tl) == "Blinding Lights"
        assert providers._best_track_title("zzz", tl) == ""
        assert providers._best_track_title("", tl) == ""


class TestFetchAll:
    def test_aggregates(self, monkeypatch):
        for name in ("_search_deezer", "_search_itunes", "_search_discogs"):
            monkeypatch.setattr(
                providers, name,
                lambda *a, _n=name: [ProviderRecord(source=_n, title="X")],
            )
        out = fetch_all("Espresso", "Sabrina", sources=["iTunes", "Deezer", "Discogs"])
        assert list(out.keys()) == ["iTunes", "Deezer", "Discogs"]

    def test_filters_by_sources(self, monkeypatch):
        for name in ("_search_deezer", "_search_itunes", "_search_discogs"):
            monkeypatch.setattr(
                providers, name,
                lambda *a, _n=name: [ProviderRecord(source=_n, title="X")],
            )
        out = fetch_all("Espresso", sources=["Discogs"])
        assert list(out.keys()) == ["Discogs"]

    def test_preserves_caller_order(self, monkeypatch):
        """Порядок sources задаёт приоритет: ключи — в порядке вызова."""
        for name in ("_search_deezer", "_search_itunes", "_search_discogs"):
            monkeypatch.setattr(
                providers, name,
                lambda *a, _n=name: [ProviderRecord(source=_n, title="X")],
            )
        out = fetch_all("Espresso", sources=["Deezer", "iTunes"])
        assert list(out.keys()) == ["Deezer", "iTunes"]

    def test_duplicate_sources_collapsed(self, monkeypatch):
        monkeypatch.setattr(
            providers, "_search_itunes",
            lambda *a: [ProviderRecord(source="iTunes", title="X")],
        )
        out = fetch_all("x", sources=["iTunes", "iTunes"])
        assert list(out.keys()) == ["iTunes"]

    def test_empty_sources_disables_all(self, monkeypatch):
        monkeypatch.setattr(providers, "_search_discogs", lambda *a: [])
        assert fetch_all("x", sources=[]) == {}

    def test_unknown_sources_ignored(self, monkeypatch):
        monkeypatch.setattr(providers, "_search_discogs", lambda *a: [])
        assert fetch_all("x", sources=["Nope"]) == {}

    def test_errors_are_skipped(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("net")

        monkeypatch.setattr(providers, "_search_deezer", boom)
        monkeypatch.setattr(providers, "_search_itunes", lambda *a: [])
        monkeypatch.setattr(providers, "_search_discogs", lambda *a: [])
        assert fetch_all("x", sources=["iTunes", "Deezer", "Discogs"]) == {}

    def test_runs_sources_in_parallel(self, monkeypatch):
        """Медленные источники не заставляют ждать друг друга: время ~max, не сумма."""
        import time as _time

        def slow_deezer(*a):
            _time.sleep(0.35)
            return [ProviderRecord(source="Deezer", title="D")]

        def slow_itunes(*a):
            _time.sleep(0.2)
            return [ProviderRecord(source="iTunes", title="I")]

        monkeypatch.setattr(providers, "_search_deezer", slow_deezer)
        monkeypatch.setattr(providers, "_search_itunes", slow_itunes)
        monkeypatch.setattr(providers, "_search_discogs", lambda *a: [])
        t0 = _time.monotonic()
        out = fetch_all("x", sources=["iTunes", "Deezer"])
        elapsed = _time.monotonic() - t0
        assert list(out.keys()) == ["iTunes", "Deezer"]  # порядок канонический
        assert elapsed < 0.55  # параллельно ~0.35, последовательно было бы 0.55+

    def test_default_sources_from_config(self, monkeypatch):
        monkeypatch.setattr(
            providers, "_search_discogs",
            lambda *a: [ProviderRecord(source="Discogs", title="D")],
        )
        monkeypatch.setattr(
            "src.config.get_metadata_sources",
            lambda: ["Discogs"],
        )
        out = fetch_all("x")
        assert list(out.keys()) == ["Discogs"]


class TestAvailableSources:
    def test_registry(self):
        assert available_sources() == ["iTunes", "Deezer", "Discogs"]
