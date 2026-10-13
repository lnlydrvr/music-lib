"""Тесты плана качества: build/apply с фильтрами, конфликтами и идемпотентностью."""
from __future__ import annotations

from pathlib import Path

from src.quality import (
    apply_quality_plan,
    build_quality_plan,
    collect_quality,
)
from src.tagger import AudioTags, get_tags, set_tags


def _mp3(path: Path, tags: AudioTags) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((b"\xff\xfb\x90\x44" + b"\x00" * 413) * 4)
    assert set_tags(path, tags)
    return path


def _library(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Библиотека с двумя loose-файлами: один с лишним пробелом в теге артиста."""
    library = tmp_path / "library"
    library.mkdir()
    first = _mp3(library / "first.mp3", AudioTags(title="First Song", artist="Artist"))
    second = _mp3(library / "second.mp3", AudioTags(title="Second", artist="Artist "))
    return library, first, second


def test_plan_includes_changes_and_loose_fixes(tmp_path):
    library, first, second = _library(tmp_path)

    plan = build_quality_plan(library)

    assert plan.count > 0
    assert set(plan.files) == {first, second}
    # Оба файла лежат в корне — план предлагает перенос в Artist/…
    assert all(fix.action == "move" for fix in plan.fixes)
    assert all(fix.target.parent.name == "Artist" for fix in plan.fixes)
    assert plan.conflicts == []
    # План ничего не меняет на диске.
    assert first.exists() and second.exists()


def test_plan_filters_by_paths_and_categories(tmp_path):
    library, first, second = _library(tmp_path)

    by_paths = build_quality_plan(library, paths=[str(first)])
    assert set(by_paths.files) == {first}

    # Категория mismatch/loose — только фиксы, без изменений тегов.
    only_fixes = build_quality_plan(library, categories=["loose"])
    assert only_fixes.changes == []
    assert len(only_fixes.fixes) == 2


def test_plan_selects_concrete_changes_and_flags_duplicates(tmp_path):
    library, _first, second = _library(tmp_path)

    plan = build_quality_plan(
        library,
        change_keys=[{"path": str(second), "field": "artist"}],
    )
    assert [(c.path, c.field) for c in plan.changes] == [(second, "artist")]

    dup = build_quality_plan(library, change_keys=[
        {"path": str(second), "field": "artist"},
        {"path": str(second), "field": "artist"},
    ])
    assert dup.changes == []
    assert [(c.kind, c.field) for c in dup.conflicts] == [("duplicate_field", "artist")]
    assert dup.conflicts[0].message == {
        "code": "diagnostics.quality.duplicate_field",
        "params": {"field": "artist"},
        "message": "Field “Artist” was selected for change more than once",
    }


def test_plan_conflict_when_target_exists(tmp_path):
    library, first, _second = _library(tmp_path)
    plan = build_quality_plan(library, paths=[str(first)])
    fix = plan.fixes[0]
    fix.target.parent.mkdir(parents=True, exist_ok=True)
    fix.target.write_bytes(b"occupied")

    conflicted = build_quality_plan(library, paths=[str(first)])

    assert [c.kind for c in conflicted.conflicts] == ["target_exists"]

    res = apply_quality_plan(conflicted, library)
    assert res["applied"] == 0
    assert res["conflicts"] == 1
    assert res["results"][0]["status"] == "conflict"
    assert first.exists()  # файл не тронут


def test_apply_moves_loose_files_and_is_idempotent(tmp_path):
    library, first, second = _library(tmp_path)
    plan = build_quality_plan(library)

    res = apply_quality_plan(plan, library)

    # Элементы плана: 2 переноса + 1 изменение тега (пробел в артисте).
    assert res["applied"] == len(plan.fixes) + len(plan.changes)
    assert res["errors"] == 0
    assert not first.exists()
    moved = list(library.rglob("First Song.mp3"))
    assert len(moved) == 1 and moved[0].parent.name == "Artist"

    # Повторное применение: план пуст, ничего не ломается.
    second_round = apply_quality_plan(build_quality_plan(library), library)
    assert second_round["applied"] == 0
    assert second_round["errors"] == 0
    # Теги второго файла почищены (лишний пробел).
    moved_second = next(library.rglob("second.mp3"))
    assert get_tags(moved_second).artist == "Artist"


def test_apply_applies_tag_changes_before_fix(tmp_path):
    """Перенос должен использовать уже исправленные теги."""
    library = tmp_path / "library"
    library.mkdir()
    song = _mp3(library / "song.mp3", AudioTags(title="Song", artist="Abc ft. X"))

    plan = build_quality_plan(library, paths=[str(song)])
    feat = [c for c in plan.changes if c.field == "artist"]
    assert feat and feat[0].new_value == "Abc feat. X"
    assert len(plan.fixes) == 1

    res = apply_quality_plan(plan, library)

    assert res["errors"] == 0
    moved = list(library.rglob("Song.mp3"))
    assert len(moved) == 1
    assert moved[0].parent.name == "Abc feat. X", "цель пересчитана по обновлённым тегам"


def test_apply_uses_descriptor_for_owned_tag_write_failure(tmp_path, monkeypatch):
    library, _first, second = _library(tmp_path)
    plan = build_quality_plan(library, paths=[str(second)], categories=["whitespace"])
    monkeypatch.setattr("src.quality.set_tags", lambda _path, _tags: False)

    result = apply_quality_plan(plan, library)

    assert result["errors"] == 1
    assert result["results"][0]["error"] == {
        "code": "diagnostics.quality.write_tags_failed",
        "params": {},
        "message": "Could not write tags",
    }


def test_apply_reports_missing_file_per_path(tmp_path):
    library, first, second = _library(tmp_path)
    plan = build_quality_plan(library)
    first.unlink()

    res = apply_quality_plan(plan, library)

    assert res["errors"] == 0  # отсутствие файла — конфликт, не ошибка
    by_path = {r["path"]: r for r in res["results"]}
    assert by_path[str(first)]["status"] == "conflict"
    assert by_path[str(second)]["status"] == "applied"
    assert res["conflicts"] == 1


def test_apply_result_per_file_and_full_flow(tmp_path):
    library, first, second = _library(tmp_path)
    plan = build_quality_plan(library)

    res = apply_quality_plan(plan, library)

    assert res["files"] == 2
    statuses = sorted(r["status"] for r in res["results"])
    assert statuses == ["applied", "applied"]
    # Полный цикл: отчёт после применения чист.
    report = collect_quality(library)
    loose = [i for i in report.issues if i.category == "loose"]
    assert loose == []
