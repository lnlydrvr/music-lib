"""Tests for src/lint.py — lint diagnostics on track records."""
from __future__ import annotations

from io import StringIO
from pathlib import Path

from rich.console import Console

from src.lint import (
    LintIssue,
    LintReport,
    categorize,
    lint_library,
    render_lint,
)
from src.analytics import TrackRecord


def _rec(
    path: str = "a.mp3",
    artist: str = "Artist",
    album: str = "Album",
    title: str = "Song",
    year: str = "2020",
    genre: str = "Rock",
    album_artist: str = "",
    track_number: str = "",
    disc_number: str = "",
) -> TrackRecord:
    return TrackRecord(
        path=Path(path),
        artist=artist,
        album=album,
        title=title,
        year=year,
        genre=genre,
        album_artist=album_artist,
        track_number=track_number,
        disc_number=disc_number,
    )


class TestCategorize:
    def test_empty(self):
        report = categorize([])
        assert report.total == 0
        assert report.issues == []
        assert all(v == 0 for v in report.issues_by_category.values())

    def test_clean_library(self):
        records = [
            _rec("a.mp3", artist="Pink Floyd", album="Dark Side", title="Time"),
            _rec("b.mp3", artist="Pink Floyd", album="Dark Side", title="Money"),
        ]
        report = categorize(records)
        assert report.issues == []

    def test_whitespace_trailing(self):
        report = categorize([_rec(path="a.mp3", artist="Artist ")], )
        ws = report.issues_by_category.get("whitespace", [])
        assert len(ws) == 1
        assert ws[0].message == {
            "code": "diagnostics.lint.whitespace",
            "params": {"field": "artist", "value": "Artist"},
            "message": '“Artist”: extra spaces in “Artist”',
        }

    def test_whitespace_double_space(self):
        report = categorize([_rec(path="a.mp3", title="A  B")])
        assert report.count("whitespace") == 1

    def test_whitespace_nbsp(self):
        report = categorize([_rec(path="a.mp3", album="A\xa0B")])
        assert report.count("whitespace") == 1

    def test_case_artist(self):
        records = [
            _rec("a.mp3", artist="Pink Floyd", album="X"),
            _rec("b.mp3", artist="Pink Floyd", album="Y"),
            _rec("c.mp3", artist="pink floyd", album="Z"),
        ]
        report = categorize(records)
        case = report.issues_by_category.get("case", [])
        assert len(case) == 1
        assert case[0].message["params"]["variant"] == "pink floyd"

    def test_case_album(self):
        records = [
            _rec("a.mp3", artist="A", album="Dark Side"),
            _rec("b.mp3", artist="A", album="dark side"),
        ]
        report = categorize(records)
        case = report.issues_by_category.get("case", [])
        assert len(case) == 1
        assert any(i.message["code"] == "diagnostics.lint.album_case" for i in case)

    def test_feat_non_canonical(self):
        for bad in ("A ft. B", "A featuring B", "A (ft B)"):
            report = categorize([_rec(path="a.mp3", title=bad)])
            assert report.count("feat") == 1, bad

    def test_feat_with_word_not_flagged(self):
        # «with» — обычное слово названия, а не фит-маркер.
        report = categorize([_rec(path="a.mp3", title="Stand Here With Me")])
        assert report.count("feat") == 0

    def test_feat_canonical_ok(self):
        report = categorize([_rec(path="a.mp3", title="A feat. B")])
        assert report.count("feat") == 0

    def test_tracknum_duplicate(self):
        records = [
            _rec("a.mp3", artist="A", album="Alb", track_number="1"),
            _rec("b.mp3", artist="A", album="Alb", track_number="1"),
        ]
        report = categorize(records)
        tn = report.issues_by_category.get("tracknum", [])
        assert len(tn) == 2

    def test_tracknum_non_numeric(self):
        report = categorize([_rec(path="a.mp3", track_number="ABC")])
        assert report.count("tracknum") == 1

    def test_album_artist_conflict(self):
        records = [
            _rec("a.mp3", artist="A", album="Alb", album_artist="VA"),
            _rec("b.mp3", artist="A", album="Alb", album_artist="A"),
        ]
        report = categorize(records)
        assert report.count("album_artist") == 2

    def test_genre_conflict(self):
        records = [
            _rec("a.mp3", artist="A", album="Alb", genre="Rock"),
            _rec("b.mp3", artist="A", album="Alb", genre="Pop"),
        ]
        report = categorize(records)
        assert report.count("genre") == 2

    def test_year_invalid(self):
        assert categorize([_rec("a.mp3", year="abcd")]).count("year") == 1
        assert categorize([_rec("a.mp3", year="0")]).count("year") == 1
        assert categorize([_rec("a.mp3", year="9999")]).count("year") == 1
        assert categorize([_rec("a.mp3", year="2020")]).count("year") == 0

    def test_multidisc_no_false_positives(self):
        records = [
            _rec("d1t1.mp3", artist="A", album="Alb", track_number="1", disc_number="1"),
            _rec("d1t2.mp3", artist="A", album="Alb", track_number="2", disc_number="1"),
            _rec("d2t1.mp3", artist="A", album="Alb", track_number="1", disc_number="2"),
            _rec("d2t2.mp3", artist="A", album="Alb", track_number="2", disc_number="2"),
        ]
        report = categorize(records)
        assert report.count("tracknum") == 0

    def test_multidisc_real_tracknum_duplicate(self):
        records = [
            _rec("d1t1a.mp3", artist="A", album="Alb", track_number="1", disc_number="1"),
            _rec("d1t1b.mp3", artist="A", album="Alb", track_number="1", disc_number="1"),
        ]
        report = categorize(records)
        assert report.count("tracknum") == 2

    def test_disc_non_numeric(self):
        report = categorize([_rec(path="a.mp3", disc_number="ABC")])
        assert report.count("tracknum") == 1
        assert report.issues[0].message["code"] == "diagnostics.lint.invalid_disc_number"

    def test_disc_numeric_with_total(self):
        records = [
            _rec("a.mp3", artist="A", album="Alb", track_number="1", disc_number="1/2"),
            _rec("b.mp3", artist="A", album="Alb", track_number="2", disc_number="2/2"),
        ]
        report = categorize(records)
        assert report.count("tracknum") == 0


class TestLintLibrary:
    def test_scan_and_lint(self, tmp_path):
        from src.tagger import AudioTags, set_tags
        from conftest import MP3_FRAME

        p = tmp_path / "a.mp3"
        p.write_bytes(MP3_FRAME * 4)
        set_tags(p, AudioTags(title="Song", artist="Pink Floyd", album="Dark Side",
                              genre="Rock", year="2020", track_number="01"))
        report = lint_library(tmp_path)
        assert report.total == 1
        # "01" — валидный номер, год ок, регистр один — проблем быть не должно
        # кроме отсутствующих опц. полей, которые lint не проверяет
        assert report.issues == []

    def test_render(self, tmp_path, monkeypatch):
        from src.tagger import AudioTags, set_tags
        from conftest import MP3_FRAME

        p = tmp_path / "a.mp3"
        p.write_bytes(MP3_FRAME * 4)
        set_tags(p, AudioTags(title="Song", artist="Artist ", album="X"))
        report = lint_library(tmp_path)
        out = StringIO()
        console = Console(file=out, width=120, force_terminal=True)
        render_lint(report, console)
        text = out.getvalue()
        assert "Tag check" in text
        assert "Extra whitespace" in text

    def test_render_accepts_legacy_string_verbatim(self):
        report = LintReport(
            total=1,
            issues=[LintIssue("year", Path("song.mp3"), "old diagnostic")],
            issues_by_category={"year": [LintIssue("year", Path("song.mp3"), "old diagnostic")]},
        )
        out = StringIO()
        render_lint(report, Console(file=out, width=120, force_terminal=True))
        assert "old diagnostic" in out.getvalue()
