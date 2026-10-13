"""Tests for src/search.py (YouTube search + playlist extraction)."""
from __future__ import annotations

import pytest

from src.search import PlaylistEntry, SearchResult, YouTubeSearch


class FakeYDL:
    """YoutubeDL stand-in returning canned extract_info data."""

    instances: list["FakeYDL"] = []
    data: dict | None = None
    raise_on_extract: Exception | None = None

    def __init__(self, opts=None):
        self.opts = opts or {}
        self.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=False):
        if self.raise_on_extract is not None:
            raise self.raise_on_extract
        return self.data


@pytest.fixture
def fake_ydl(monkeypatch):
    FakeYDL.data = None
    FakeYDL.raise_on_extract = None
    FakeYDL.instances = []
    monkeypatch.setattr("src.search.YoutubeDL", FakeYDL)
    monkeypatch.setattr("src.search.time.sleep", lambda *_: None)
    return FakeYDL


ENTRY = {
    "id": "v1",
    "title": "First Song",
    "duration": 200,
    "uploader": "Artist - Topic",
    "thumbnail": "http://t/1.jpg",
    "url": "http://yt/watch?v=v1",
}


class TestSearchResultDataclass:
    def test_fields(self):
        assert SearchResult(info=object(), index=3).index == 3


class TestYouTubeSearch:
    def test_search_maps_entries(self, fake_ydl):
        FakeYDL.data = {
            "entries": [
                dict(ENTRY),
                {"id": "v2", "title": "Two", "duration": 300, "uploader": "B"},
            ]
        }
        results = YouTubeSearch(max_results=10).search("query")
        assert len(results) == 2
        assert [r.index for r in results] == [1, 2]
        assert results[0].info.id == "v1"
        assert results[0].info.webpage_url == "http://yt/watch?v=v1"
        assert results[0].info.thumbnail == "http://t/1.jpg"
        assert results[1].info.title == "Two"

    def test_search_skips_none_entries(self, fake_ydl):
        FakeYDL.data = {"entries": [dict(ENTRY), None, dict(ENTRY)]}
        results = YouTubeSearch().search("q")
        assert len(results) == 2

    def test_search_empty(self, fake_ydl):
        FakeYDL.data = {}
        assert YouTubeSearch().search("q") == []

    def test_search_exception_returns_empty(self, fake_ydl):
        FakeYDL.raise_on_extract = RuntimeError("network")
        assert YouTubeSearch().search("q") == []

    def test_search_defaults(self, fake_ydl):
        FakeYDL.data = {"entries": [dict(ENTRY)]}
        YouTubeSearch().search("q")
        YouTubeSearch(max_results=5).search("q")
        assert len(FakeYDL.instances) == 2
        assert FakeYDL.instances[-1].opts == {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "default_search": "ytsearch",
        }

    def test_fetch_playlist_uses_url_field(self, fake_ydl):
        FakeYDL.data = {"title": "PL", "entries": [dict(ENTRY)]}
        entries = YouTubeSearch().fetch_playlist("http://yt/playlist")
        assert len(entries) == 1
        assert entries[0].index == 1
        assert entries[0].info.webpage_url == "http://yt/watch?v=v1"

    def test_fetch_playlist_builds_url_from_id(self, fake_ydl):
        FakeYDL.data = {"title": "PL", "entries": [{"id": "abc", "title": "T"}]}
        entries = YouTubeSearch().fetch_playlist("http://yt/playlist")
        assert entries[0].info.webpage_url == "https://www.youtube.com/watch?v=abc"
        assert entries[0].info.duration == 0
        assert entries[0].info.uploader == "Unknown"

    def test_fetch_playlist_falls_back_to_channel(self, fake_ydl):
        FakeYDL.data = {
            "entries": [{"id": "a", "title": "T", "channel": "Band", "upload_date": "20240202"}],
        }
        entries = YouTubeSearch().fetch_playlist("u")
        assert entries[0].info.uploader == "Band"
        assert entries[0].info.upload_date == "20240202"

    def test_fetch_playlist_empty(self, fake_ydl):
        FakeYDL.data = {}
        assert YouTubeSearch().fetch_playlist("u") == []

    def test_fetch_playlist_exception(self, fake_ydl):
        FakeYDL.raise_on_extract = RuntimeError("x")
        s = YouTubeSearch()
        assert s.fetch_playlist("u") == []
        assert s.last_error == "x"