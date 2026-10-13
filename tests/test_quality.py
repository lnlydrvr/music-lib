"""Tests for the unified library quality report."""
from __future__ import annotations

from pathlib import Path

from src.quality import collect_quality
from src.tagger import AudioTags, set_tags


def _mp3(path: Path, tags: AudioTags) -> Path:
    path.write_bytes((b"\xff\xfb\x90\x44" + b"\x00" * 413) * 4)
    assert set_tags(path, tags)
    return path


def test_quality_report_combines_diagnostics_and_fix_plan(tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    song = _mp3(
        library / "song.mp3",
        AudioTags(
            # «with» больше не фит-маркер (часть названия), берём явный «ft.»
            title="Song", artist="Artist ft. Guest", album="Album", year="2020",
            genre="Rock",
        ),
    )

    report = collect_quality(library)

    assert report.total == 1
    assert report.counts["loose"] == 1
    assert report.counts["missing"] == 1  # обложка
    assert any(i.category == "feat" and i.path == song for i in report.issues)
    change_issue = next(i for i in report.issues if i.category == "feat" and i.path == song)
    assert change_issue.message["code"] == "diagnostics.lint.feat"
    assert any(c.path == song and c.field == "artist" for c in report.changes)


def test_quality_report_can_include_inbox(tmp_path):
    library = tmp_path / "library"
    inbox = library / "Inbox"
    inbox.mkdir(parents=True)
    _mp3(inbox / "song.mp3", AudioTags(title="Song", artist="Artist"))

    without_inbox = collect_quality(library)
    with_inbox = collect_quality(library, include_inbox=True)

    assert without_inbox.total == 0
    assert with_inbox.total == 1
    assert with_inbox.issues[0].inbox is True
