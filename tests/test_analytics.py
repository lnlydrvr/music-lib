"""Tests for src/analytics.py — scan, aggregation, and stats rendering."""
from __future__ import annotations

from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
import shutil

import pytest
from rich.console import Console

from src.analytics import (
    TrackRecord,
    LibraryStats,
    aggregate,
    scan_library,
    library_files,
    collect_stats,
    render_stats,
    _year4,
    _fmt_bytes,
    _fmt_seconds,
)
from src.tagger import AudioTags, set_tags

from conftest import MP3_FRAME


def _rec(
    path: str = "song.mp3",
    artist: str = "Artist",
    album: str = "Album",
    title: str = "Song",
    year: str = "2010",
    genre: str = "Rock",
    album_artist: str = "",
    composer: str = "",
    isrc: str = "",
    lyrics: str = "lyrics",
    cover: bool = True,
    duration: int = 180,
    size: int = 1024,
    mtime: float = 0.0,
) -> TrackRecord:
    return TrackRecord(
        path=Path(path),
        artist=artist,
        album=album,
        title=title,
        year=year,
        genre=genre,
        album_artist=album_artist,
        composer=composer,
        isrc=isrc,
        lyrics=lyrics,
        cover=cover,
        duration_seconds=duration,
        size_bytes=size,
        mtime=mtime,
    )


class TestYear4:
    def test_full_year(self):
        assert _year4("2024") == "2024"

    def test_dated(self):
        assert _year4("2024-03-12") == "2024"

    def test_empty_and_junk(self):
        assert _year4("") == ""
        assert _year4(None) == ""
        assert _year4("abcd") == ""


class TestFormatters:
    def test_bytes(self):
        assert _fmt_bytes(0) == "0.0 MB"
        assert _fmt_bytes(1024 * 1024) == "1.0 MB"
        assert _fmt_bytes(2 * 1024 * 1024 * 1024).endswith("GB")

    def test_seconds(self):
        assert _fmt_seconds(0) == "0:00 ч"
        assert _fmt_seconds(3661) == "1:01 ч"
        assert "д" in _fmt_seconds(90 * 86400)


class TestAggregate:
    def test_empty(self):
        stats = aggregate([])
        assert stats.total == 0
        assert stats.artists == 0
        assert stats.albums == 0
        assert stats.total_seconds == 0
        assert stats.formats == {}
        assert stats.longest == []
        # все поля полноты = 0
        assert all(v == 0 for v in stats.missing.values())

    def test_counts_and_tops(self):
        records = [
            _rec("a.mp3", artist="Artist A", album="Al1", genre="Rock", year="2000"),
            _rec("b.mp3", artist="Artist A", album="Al1", genre="Rock", year="2001"),
            _rec("c.mp3", artist="Artist B", album="Al2", genre="Jazz", year="2002"),
            _rec("d.flac", artist="Artist C", album="Al3", genre="Jazz", year="2003", cover=False),
            _rec("e.m4a", artist="Artist D", album="", genre="", year=""),
        ]
        stats = aggregate(records)
        assert stats.total == 5
        assert stats.artists == 4
        assert stats.albums == 3  # (Artist A, Al1) считается одним альбомом
        assert stats.total_seconds == 900
        assert stats.formats == {".mp3": 3, ".flac": 1, ".m4a": 1}

        assert stats.top_artists[0] == ("Artist A", 2)
        assert stats.top_genres[0] == ("Rock", 2)
        assert stats.years == {"2000": 1, "2001": 1, "2002": 1, "2003": 1}
        assert stats.min_year == "2000"
        assert stats.max_year == "2003"
        assert stats.longest[0].title == "Song"

    def test_missing_counts(self):
        records = [
            _rec("a.mp3", lyrics="", cover=False, album_artist="", isrc="", composer=""),
            _rec("b.mp3", lyrics="x", cover=True, album_artist="VA", isrc="I", composer="C"),
        ]
        stats = aggregate(records)
        assert stats.missing["lyrics"] == 1
        assert stats.missing["cover"] == 1
        assert stats.missing["album_artist"] == 1
        assert stats.missing["composer"] == 1
        assert stats.missing["isrc"] == 1
        assert stats.missing["title"] == 0
        assert stats.missing["genre"] == 0
        assert stats.missing["year"] == 0
        assert stats.missing["album"] == 0

    def test_missing_files_preview(self):
        records = [_rec(f"s{i}.mp3", lyrics="", cover=False, album_artist="") for i in range(5)]
        stats = aggregate(records)
        assert len(stats.missing_files["lyrics"]) == 3  # обрезается до 3
        assert stats.missing_files["lyrics"][0] == "s0.mp3"

    def test_artists_case_insensitive_distinct(self):
        records = [
            _rec("a.mp3", artist="Pink Floyd"),
            _rec("b.mp3", artist="pink floyd"),
        ]
        stats = aggregate(records)
        assert stats.artists == 1

    def test_months_by_mtime(self):
        t = datetime(2024, 5, 10, tzinfo=timezone.utc).timestamp()
        records = [
            _rec("a.mp3", mtime=t, year="2024"),
            _rec("b.mp3", mtime=t, year="2024"),
            _rec("c.mp3", mtime=0, year="2024"),
        ]
        stats = aggregate(records)
        assert stats.months == [("2024-05", 2)]

    def test_longest_excludes_zero(self):
        records = [
            _rec("a.mp3", duration=0),
            _rec("b.mp3", duration=300),
            _rec("c.mp3", duration=200),
        ]
        stats = aggregate(records)
        assert [r.title for r in stats.longest] == ["Song", "Song"]
        assert stats.longest[0].duration_seconds == 300


class TestScanAndCollect:
    def _stub(self, tmp: Path, name: str, tags: dict | None = None) -> Path:
        path = tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(MP3_FRAME * 4)
        if tags:
            set_tags(path, AudioTags(**tags))
        return path

    def test_scan_ignores_non_audio(self, tmp_path):
        tmp_path.joinpath("notes.txt").write_text("hello")
        records, errors = scan_library(tmp_path)
        assert records == []
        assert errors == 0

    def test_scan_opens_audio_file_once_for_tags_and_stream_info(self, tmp_path, monkeypatch):
        from src.tagger import Tagger as RealTagger
        import src.analytics as analytics

        path = self._stub(tmp_path, "once.mp3", dict(title="Once", artist="A"))
        opened = []

        def counting_tagger(filepath):
            opened.append(filepath)
            return RealTagger(filepath)

        monkeypatch.setattr(analytics, "Tagger", counting_tagger)
        records, errors = analytics.scan_library(tmp_path)

        assert errors == 0
        assert len(records) == 1
        assert opened == [path]
        assert records[0].title == "Once"
        assert records[0].bitrate > 0

    def test_scan_reuses_file_stat_for_size_and_mtime(self, tmp_path, monkeypatch):
        from src.tagger import Tagger as RealTagger
        import src.analytics as analytics

        path = self._stub(tmp_path, "once.mp3")
        stat_calls = []
        original_stat = Path.stat

        def counting_stat(filepath, *args, **kwargs):
            if filepath == path:
                stat_calls.append(filepath)
            return original_stat(filepath, *args, **kwargs)

        monkeypatch.setattr(analytics, "Tagger", lambda filepath: RealTagger(filepath))
        monkeypatch.setattr(Path, "stat", counting_stat)
        records, errors = analytics.scan_library(tmp_path)

        assert errors == 0
        assert len(records) == 1
        assert stat_calls == [path]


    def test_library_files_excludes_inbox(self, tmp_path):
        self._stub(tmp_path, "a.mp3", dict(title="Keep", artist="A"))
        inbox = tmp_path / "Inbox"
        self._stub(inbox, "pending.mp3", dict(title="Temp", artist="B"))
        files = library_files(tmp_path)
        assert [f.name for f in files] == ["a.mp3"]

    def test_library_files_includes_inbox_when_requested(self, tmp_path):
        self._stub(tmp_path, "a.mp3", dict(title="Keep", artist="A"))
        self._stub(tmp_path / "Inbox", "pending.mp3", dict(title="Temp", artist="B"))
        files = library_files(tmp_path, include_inbox=True)
        assert sorted(f.name for f in files) == ["a.mp3", "pending.mp3"]

    def test_md5_dedup_finds_copies_in_inbox(self, tmp_path):
        from src.services import dedup_groups
        a = self._stub(tmp_path, "a.mp3", dict(title="Keep", artist="A"))
        inbox = tmp_path / "Inbox"
        inbox.mkdir()
        shutil.copyfile(a, inbox / "copy.mp3")
        groups = dedup_groups("md5", tmp_path)
        assert len(groups) == 1
        assert sorted(p.name for p in groups[0]) == ["a.mp3", "copy.mp3"]

    def test_scan_excludes_inbox(self, tmp_path):
        self._stub(tmp_path, "a.mp3", dict(title="Keep", artist="A"))
        self._stub(tmp_path / "Inbox", "pending.mp3", dict(title="Temp", artist="B"))
        records, errors = scan_library(tmp_path)
        assert errors == 0
        assert len(records) == 1
        assert records[0].title == "Keep"

    def test_collect_with_stubs(self, tmp_path):
        self._stub(tmp_path, "a.mp3", dict(
            title="One", artist="Artist A", album="Album X", year="2005",
            genre="Pop", lyrics="line", album_artist="AA",
        ))
        self._stub(tmp_path / "sub", "b.mp3", dict(
            title="Two", artist="Artist A", album="Album X", year="2006", genre="Pop",
        ))
        tmp_path.joinpath("readme.txt").write_text("x")

        stats = collect_stats(tmp_path)
        assert stats.total == 2
        assert stats.errors == 0
        assert stats.artists == 1
        assert stats.albums == 1
        assert stats.formats == {".mp3": 2}
        assert stats.top_artists == [("Artist A", 2)]
        assert stats.years == {"2005": 1, "2006": 1}
        assert stats.missing["lyrics"] == 1
        assert stats.missing["cover"] == 2

    def test_render_output(self, tmp_path, monkeypatch):
        self._stub(tmp_path, "a.mp3", dict(
            title="One", artist="Artist A", album="Album X", year="2005", genre="Pop",
        ))
        stats = collect_stats(tmp_path)
        out = StringIO()
        console = Console(file=out, width=120, force_terminal=True)
        render_stats(stats, console)
        text = out.getvalue()
        assert "Обзор" in text
        assert "Топ исполнителей" in text
        assert "Годы релизов" in text
        assert "Полнота тегов" in text
        assert "1" in text  # количество треков в таблицах
