"""Tests for src/shazam_import.py (парсер, матчинг, скоринг, remove-строк)."""
from __future__ import annotations

from io import StringIO

import pytest
from rich.console import Console

from src.shazam_import import (
    append_shazam_lines, find_youtube_matches, migrate_shazam_default,
    parse_shazam_file, ShazamEntry, remove_shazam_lines,
    score_match, is_confident, resolve_match, resolve_selected,
)


def _write(tmp_path, text):
    path = tmp_path / "shazam.txt"
    path.write_text(text, encoding="utf-8")
    return path


class TestParseShazamFile:
    def test_empty_missing_file(self, tmp_path):
        assert parse_shazam_file(tmp_path / "nope.txt") == []

    def test_simple_pairs(self, tmp_path):
        p = _write(tmp_path, "Song One - Artist One\nSong Two - Artist Two\n")
        entries = parse_shazam_file(p)
        assert len(entries) == 2
        assert entries[0] == ShazamEntry(index=1, line_number=1, title="Song One", artist="Artist One")
        assert entries[0].query == "Song One Artist One"
        assert entries[1].title == "Song Two"

    def test_skips_empty_and_comments(self, tmp_path):
        p = _write(tmp_path, "\n# comment\nSong - Artist\n\n")
        entries = parse_shazam_file(p)
        assert len(entries) == 1
        assert entries[0].line_number == 3

    def test_splits_on_last_separator(self, tmp_path):
        p = _write(tmp_path, "Crazy - Videos - Artist\n")
        entries = parse_shazam_file(p)
        assert entries[0].title == "Crazy - Videos"
        assert entries[0].artist == "Artist"

    def test_no_separator_whole_line_title(self, tmp_path):
        p = _write(tmp_path, "JustATitle\n")
        entries = parse_shazam_file(p)
        assert entries[0].title == "JustATitle"
        assert entries[0].artist == ""
        assert entries[0].query == "JustATitle"

    def test_trim_whitespace(self, tmp_path):
        p = _write(tmp_path, "  Song  -  Artist  \n")
        entries = parse_shazam_file(p)
        assert entries[0].title == "Song"
        assert entries[0].artist == "Artist"

    def test_display(self):
        e = ShazamEntry(index=1, line_number=1, title="T", artist="A")
        assert e.display == "A — T"
        assert ShazamEntry(1, 1, "T", "").display == "T"


class TestFindYoutubeMatches:
    def test_full_query_first(self):
        entries = [ShazamEntry(index=1, line_number=1, title="Song", artist="Artist")]
        calls = []

        def search(q):
            calls.append(q)
            return ["hit"] if q == "Song Artist" else []

        found = find_youtube_matches(entries, search)
        assert calls == ["Song Artist"]
        assert found == [(entries[0], ["hit"])]

    def test_fallback_to_title_when_full_query_empty(self):
        entries = [ShazamEntry(index=1, line_number=1, title="Song", artist="Artist")]
        calls = []

        def search(q):
            calls.append(q)
            return ["hit"] if q == "Song" else []

        found = find_youtube_matches(entries, search)
        assert calls == ["Song Artist", "Song"]
        assert found == [(entries[0], ["hit"])]

    def test_artist_unknown_keeps_single_query(self):
        entries = [ShazamEntry(index=1, line_number=1, title="Song", artist="")]
        calls = []

        def search(q):
            calls.append(q)
            return []

        found = find_youtube_matches(entries, search)
        assert calls == ["Song"]
        assert found == [(entries[0], [])]


class TestScoreConfidence:
    class _Info:
        def __init__(self, title, uploader="", webpage_url="", id=""):
            self.title = title
            self.uploader = uploader
            self.webpage_url = webpage_url
            self.id = id

    class _Result:
        def __init__(self, title, uploader="", webpage_url="", id=""):
            self.info = TestScoreConfidence._Info(title, uploader, webpage_url, id)

    def _entry(self, title="啓示", artist="アトラスサウンドチーム"):
        return ShazamEntry(index=1, line_number=1, title=title, artist=artist)

    def test_exact_title_is_confident(self):
        e = self._entry()
        assert is_confident(e, self._Result("啓示"))

    def test_transliteration_not_confident(self):
        e = self._entry(title="♂と♀のラムゲーム")
        assert not is_confident(e, self._Result("FVGM #48: Catherine - Lamb Game between ♂ and ♀"))

    def test_similar_but_wrong_title_not_confident(self):
        e = self._entry(title="喪失")
        assert not is_confident(e, self._Result("消失"))

    def test_similar_neighbor_confident(self):
        e = self._entry(title="Shape of You")
        assert is_confident(e, self._Result("Shape of You (Official Video)"))


class TestResolveMatch:
    def _entry(self, title="喪失"):
        return ShazamEntry(index=1, line_number=1, title=title, artist="アトラスサウンドチーム")

    def _result(self, title, url="https://youtu.be/x"):
        class Info:
            pass

        class _R:
            def __init__(self):
                self.info = Info()
                self.info.title = title
                self.info.uploader = "ch"
                self.info.webpage_url = url
                self.info.id = "x"

        return _R()

    def _render(self):
        output = StringIO()
        test_console = Console(file=output, force_terminal=True, width=100)
        return output, test_console

    def test_confident_returns_best_without_asking(self):
        e = self._entry(title="啓示")
        found = [self._result("啓示"), self._result("神秘")]
        output, console = self._render()
        calls = []
        out = resolve_match(e, found, console, lambda *a, **k: calls.append(a) or "1")
        assert out is found[0]
        assert calls == []
        assert "Уточните" not in output.getvalue()

    def test_uncertain_prompts_and_returns_picked(self):
        e = self._entry()
        found = [self._result("消失"), self._result("Beneath the Mask クリスマスバージョン")]
        output, console = self._render()
        out = resolve_match(e, found, console, lambda *a, **k: "2")
        assert out is found[1]
        assert "Уточните результат" in output.getvalue()
        assert "消失" in output.getvalue()

    def test_uncertain_skip_returns_none(self):
        e = self._entry()
        found = [self._result("消失")]
        output, console = self._render()
        assert resolve_match(e, found, console, lambda *a, **k: "0") is None
        assert resolve_match(e, found, console, lambda *a, **k: "") is None

    def test_uncertain_out_of_range_skips(self):
        e = self._entry()
        found = [self._result("消失")]
        output, console = self._render()
        assert resolve_match(e, found, console, lambda *a, **k: "9") is None

    def test_resolve_selected_filters(self):
        e1 = self._entry(title="啟示")
        e2 = self._entry(title="喪失")
        found1 = [self._result("啟示")]
        found2 = [self._result("消失"), self._result("Beneath the Mask クリスマスバージョン")]
        matches = [(e1, found1), (e2, found2)]
        output, console = self._render()
        answers = iter(["2"])
        resolved = resolve_selected(matches, {1, 2}, console, lambda *a, **k: next(answers))
        assert [e for e, _ in resolved] == [e1, e2]
        assert resolved[1][1] is found2[1]


class TestRemoveShazamLines:
    def test_removes_specified_lines(self, tmp_path):
        p = _write(tmp_path, "A\nB\nC\nD\n")
        assert remove_shazam_lines(p, {2, 4}) == 2
        assert p.read_text(encoding="utf-8") == "A\nC\n"

    def test_keeps_comments_and_empty(self, tmp_path):
        p = _write(tmp_path, "# comment\nA\n\nB\n")
        assert remove_shazam_lines(p, {2}) == 1
        assert p.read_text(encoding="utf-8") == "# comment\n\nB\n"

    def test_empty_set_noop(self, tmp_path):
        p = _write(tmp_path, "A\nB\n")
        assert remove_shazam_lines(p, set()) == 0
        assert p.read_text(encoding="utf-8") == "A\nB\n"

    def test_missing_file(self, tmp_path):
        assert remove_shazam_lines(tmp_path / "nope.txt", {1}) == 0

    def test_unknown_lines_leave_file(self, tmp_path):
        p = _write(tmp_path, "A\nB\n")
        assert remove_shazam_lines(p, {99}) == 0
        assert p.read_text(encoding="utf-8") == "A\nB\n"


class TestShazamFileHelpers:
    def test_append_creates_dedups_and_skips_comments(self, tmp_path):
        target = tmp_path / "sub" / "shazam.txt"
        # комментарий и пустая строка отбрасываются до подсчёта, дубль — skipped
        assert append_shazam_lines(target, ["A - B", "# c", "", "A - B"]) == (1, 0)
        assert target.read_text(encoding="utf-8") == "A - B\n"
        assert append_shazam_lines(target, ["C - D", "A - B"]) == (1, 1)
        assert target.read_text(encoding="utf-8") == "A - B\nC - D\n"

    def test_append_continues_file_without_trailing_newline(self, tmp_path):
        target = _write(tmp_path, "A - B")
        append_shazam_lines(target, ["C - D"])
        assert target.read_text(encoding="utf-8") == "A - B\nC - D\n"

    def test_migrate_moves_default_to_custom(self, tmp_path):
        lib = tmp_path / "lib"
        default = lib / ".system" / "shazam.txt"
        default.parent.mkdir(parents=True)
        default.write_text("A - B\nA - B\n", encoding="utf-8")
        custom = tmp_path / "custom.txt"
        custom.write_text("C - D\n", encoding="utf-8")
        assert migrate_shazam_default(custom, lib) == 1
        assert custom.read_text(encoding="utf-8") == "C - D\nA - B\n"

    def test_migrate_noop_without_default_or_same_path(self, tmp_path):
        lib = tmp_path / "lib"
        custom = tmp_path / "custom.txt"
        custom.write_text("X\n", encoding="utf-8")
        assert migrate_shazam_default(custom, lib) == 0
        default = lib / ".system" / "shazam.txt"
        default.parent.mkdir(parents=True)
        default.write_text("A - B\n", encoding="utf-8")
        assert migrate_shazam_default(default, lib) == 0

