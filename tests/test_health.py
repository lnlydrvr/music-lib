"""Tests for src/health.py — health-check aggregation and rendering."""
from __future__ import annotations

from io import StringIO
from pathlib import Path

from rich.console import Console

from src.health import (
    HealthItem,
    HealthIssue,
    HealthReport,
    collect_issues,
    scan_items,
    run_health_check,
    fix_issues,
    render_health,
)
from src.tagger import AudioTags, set_tags

from conftest import MP3_FRAME


def _item(
    path: str = "Artist/Album/Song.mp3",
    artist: str = "Artist",
    title: str = "Song",
    album: str = "Album",
    year: str = "2010",
    genre: str = "Rock",
    lyrics: str = "lyrics",
    cover: bool = True,
    read_ok: bool = True,
    md5: str = "0" * 32,
    disc_number: str = "",
) -> HealthItem:
    return HealthItem(
        path=Path(path),
        artist=artist,
        title=title,
        album=album,
        year=year,
        genre=genre,
        lyrics=lyrics,
        cover=cover,
        read_ok=read_ok,
        md5=md5,
        disc_number=disc_number,
    )


class TestCollectIssues:
    def test_empty(self):
        report = collect_issues([], output_dir=Path("/lib"))
        assert report.total == 0
        assert report.issues == []
        assert report.score == 100
        assert report.count("missing") == 0

    def test_healthy_file(self):
        report = collect_issues([_item()], output_dir=Path("."))
        assert report.total == 1
        assert report.issues == []
        assert report.score == 100

    def test_unreadable(self):
        report = collect_issues([_item(read_ok=False)], output_dir=Path("."))
        assert report.count("unreadable") == 1
        assert report.issues[0].message == {
            "code": "diagnostics.health.unreadable", "params": {},
            "message": "Could not read file",
        }
        assert report.score < 100

    def test_missing_tags(self):
        report = collect_issues([_item(lyrics="", cover=False)], output_dir=Path("."))
        missing = report.issues_by_category.get("missing", [])
        labels = {i.message["params"]["field"] for i in missing}
        assert "cover" in labels
        # тексты (lyrics) не проверяем
        assert "lyrics" not in labels

    def test_md5_duplicates(self):
        a = _item("a.mp3", md5="abc")
        b = _item("b.mp3", md5="abc")
        # создаём файлы с размерами, чтобы определить "лучший" (больший)
        Path("a.mp3").write_bytes(b"x")
        Path("b.mp3").write_bytes(b"xxxx")
        try:
            report = collect_issues([a, b], output_dir=Path("."))
            dup = report.issues_by_category.get("duplicates", [])
            assert len(dup) == 1
            assert dup[0].path == Path("a.mp3")
        finally:
            Path("a.mp3").unlink(missing_ok=True)
            Path("b.mp3").unlink(missing_ok=True)

    def test_semantic_duplicates(self):
        a = _item("a.mp3", artist="Artist", title="Song")
        b = _item("b.mp3", artist="Artist", title="Song")
        Path("a.mp3").write_bytes(b"x")
        Path("b.mp3").write_bytes(b"xxxx")
        try:
            report = collect_issues([a, b], output_dir=Path("."))
            dup = report.issues_by_category.get("duplicates", [])
            assert len(dup) == 1
        finally:
            Path("a.mp3").unlink(missing_ok=True)
            Path("b.mp3").unlink(missing_ok=True)

    def test_semantic_no_duplicate_across_discs(self):
        # одинаковое название на разных дисках — не дубликат
        a = _item("d1.mp3", artist="Artist", album="Alb", title="Intro",
                  disc_number="1/2", md5="1" * 32)
        b = _item("d2.mp3", artist="Artist", album="Alb", title="Intro",
                  disc_number="2/2", md5="2" * 32)
        Path("d1.mp3").write_bytes(b"x")
        Path("d2.mp3").write_bytes(b"xxxx")
        try:
            report = collect_issues([a, b], output_dir=Path("."))
            assert report.count("duplicates") == 0
        finally:
            Path("d1.mp3").unlink(missing_ok=True)
            Path("d2.mp3").unlink(missing_ok=True)

    def test_semantic_no_duplicate_across_albums(self):
        # одинаковое название в разных альбомах — не дубликат
        a = _item("a.mp3", artist="Artist", album="Alb1", title="Theme", md5="1" * 32)
        b = _item("b.mp3", artist="Artist", album="Alb2", title="Theme", md5="2" * 32)
        Path("a.mp3").write_bytes(b"x")
        Path("b.mp3").write_bytes(b"xxxx")
        try:
            report = collect_issues([a, b], output_dir=Path("."))
            assert report.count("duplicates") == 0
        finally:
            Path("a.mp3").unlink(missing_ok=True)
            Path("b.mp3").unlink(missing_ok=True)

    def test_semantic_duplicate_same_disc(self):
        # тот же альбом и тот же диск, одинаковое название — дубликат
        a = _item("a.mp3", artist="Artist", album="Alb", title="Song",
                  disc_number="1/2", md5="1" * 32)
        b = _item("b.mp3", artist="Artist", album="Alb", title="Song",
                  disc_number="1/2", md5="2" * 32)
        Path("a.mp3").write_bytes(b"x")
        Path("b.mp3").write_bytes(b"xxxx")
        try:
            report = collect_issues([a, b], output_dir=Path("."))
            assert report.count("duplicates") == 1
        finally:
            Path("a.mp3").unlink(missing_ok=True)
            Path("b.mp3").unlink(missing_ok=True)

    def test_filename_mismatch(self):
        report = collect_issues([_item(path="Wrong.mp3", title="Song")], output_dir=Path("."))
        mismatch = report.issues_by_category.get("mismatch", [])
        assert len(mismatch) == 1

    def test_filename_mismatch_ignores_sanitized_chars(self):
        # имя из тега через sanitize_name: / и " заменены на _
        report = collect_issues([_item(
            path='Cheat Code (Из т_с _Мажор 2_).mp3',
            title='Cheat Code (Из т/с "Мажор 2")',
        )], output_dir=Path("."))
        assert report.count("mismatch") == 0

    def test_filename_mismatch_still_flags_real_diff(self):
        report = collect_issues([_item(
            path="Cheat Code (Из т_с _Мажор 2_).mp3",
            title="Cheat Code Другое Название",
        )], output_dir=Path("."))
        assert report.count("mismatch") == 1

    def test_loose_in_root(self):
        report = collect_issues([_item(path="Song.mp3")], output_dir=Path("."))
        loose = report.issues_by_category.get("loose", [])
        assert len(loose) == 1

    def test_score_clamped(self):
        # много проблем — не должно уйти в минус
        items = [_item(f"{i}.mp3", md5="x") for i in range(50)]
        Path.mkdir(Path("."), exist_ok=True)
        for i in items:
            i.path.write_bytes(b"x")
        try:
            report = collect_issues(items, output_dir=Path("."))
            assert report.score >= 0
        finally:
            for i in items:
                i.path.unlink(missing_ok=True)


class TestScan:
    def _stub(self, tmp: Path, name: str, tags: dict | None = None) -> Path:
        path = tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(MP3_FRAME * 4)
        if tags:
            set_tags(path, AudioTags(**tags))
        return path

    def test_scan_ignores_non_audio(self, tmp_path):
        tmp_path.joinpath("notes.txt").write_text("hello")
        items = scan_items(tmp_path)
        assert items == []

    def test_scan_excludes_inbox(self, tmp_path):
        self._stub(tmp_path, "One.mp3", dict(title="One", artist="Artist"))
        self._stub(tmp_path / "Inbox", "pending.mp3", dict(title="Temp", artist="B"))
        items = scan_items(tmp_path)
        assert len(items) == 1
        assert items[0].path.name == "One.mp3"

    def test_run_health_check(self, tmp_path):
        self._stub(tmp_path, "One.mp3", dict(
            title="One", artist="Artist", lyrics="", album="",
        ))
        report = run_health_check(tmp_path)
        assert report.total == 1
        assert report.count("missing") > 0
        assert report.count("loose") == 1  # в корне
        assert report.count("unreadable") == 0

    def test_render_output(self, tmp_path):
        self._stub(tmp_path, "a.mp3", dict(title="A", artist="Artist", lyrics=""))
        report = run_health_check(tmp_path)
        out = StringIO()
        console = Console(file=out, width=120, force_terminal=True)
        render_health(report, console)
        text = out.getvalue()
        assert "Library health check" in text
        assert "Missing tags" in text
        assert "а" in text.lower() or "a" in text

    def test_render_accepts_legacy_string_and_prints_english_descriptor_fallback(self):
        report = HealthReport(
            total=1,
            issues=[HealthIssue("missing", Path("song.mp3"), "Legacy issue")],
            issues_by_category={"missing": [HealthIssue("missing", Path("song.mp3"), "Legacy issue")]},
            score=99,
        )
        out = StringIO()
        render_health(report, Console(file=out, width=120, force_terminal=True))
        text = out.getvalue()
        assert "Library health check" in text
        assert "Legacy issue" in text
        assert "Missing tags" in text


class TestFix:
    def _stub(self, tmp: Path, name: str, tags: dict | None = None) -> Path:
        path = tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(MP3_FRAME * 4)
        if tags:
            set_tags(path, AudioTags(**tags))
        return path

    def test_loose_gets_moved_and_renamed(self, tmp_path):
        # файл в корне с именем, не совпадающим с тегом title
        self._stub(tmp_path, "BadName.mp3", dict(
            title="Real Title", artist="Artist", album="Album X",
        ))
        fixed, errors = fix_issues(tmp_path)
        assert fixed == 1
        assert errors == 0
        target = tmp_path / "Artist" / "Album X" / "Real Title.mp3"
        assert target.exists()
        assert not (tmp_path / "BadName.mp3").exists()

    def test_already_ok_untouched(self, tmp_path):
        self._stub(tmp_path / "Artist" / "Album", "Song.mp3", dict(
            title="Song", artist="Artist", album="Album",
        ))
        fixed, errors = fix_issues(tmp_path)
        assert fixed == 0
        assert errors == 0

    def test_after_fix_report_clean(self, tmp_path):
        self._stub(tmp_path, "Loose.mp3", dict(
            title="Song", artist="Artist", album="Album", genre="Rock", year="2020",
        ))
        assert run_health_check(tmp_path).count("loose") == 1
        fix_issues(tmp_path)
        assert run_health_check(tmp_path).count("loose") == 0
        assert run_health_check(tmp_path).count("mismatch") == 0

    def test_fix_multidisc_goes_to_disc_subdir(self, tmp_path):
        # одинаковое название на двух дисках — оба сохраняются, без коллизии
        self._stub(tmp_path, "Loose1.mp3", dict(
            title="Intro", artist="Artist", album="Alb", disc_number="1/2",
        ))
        self._stub(tmp_path, "Loose2.mp3", dict(
            title="Intro", artist="Artist", album="Alb", disc_number="2/2",
        ))
        fixed, errors = fix_issues(tmp_path)
        assert fixed == 2
        assert errors == 0
        assert (tmp_path / "Artist" / "Alb" / "Disc 1" / "Intro.mp3").exists()
        assert (tmp_path / "Artist" / "Alb" / "Disc 2" / "Intro.mp3").exists()

    def test_fix_single_disc_flat(self, tmp_path):
        # disc_number "1" без указания общего числа — плоская структура
        self._stub(tmp_path, "Loose.mp3", dict(
            title="Song", artist="Artist", album="Album", disc_number="1",
        ))
        fixed, errors = fix_issues(tmp_path)
        assert fixed == 1
        assert errors == 0
        assert (tmp_path / "Artist" / "Album" / "Song.mp3").exists()
        assert not (tmp_path / "Artist" / "Album" / "Disc 1").exists()
