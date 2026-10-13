"""Unified read-only quality report for the existing music library."""
from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from pathlib import Path

from .config import inbox_dir
from .health import _parse_disc_num, run_health_check
from .lint import lint_library
from .normalize import NormalizationChange, normalize_library
from .tagger import get_tags, set_tags
from .messages import format_message, message as diagnostic_message

#: Категории health, исправляемые автоматически (переименование/перенос).
FIX_CATEGORIES = ("mismatch", "loose")


@dataclass
class QualityIssue:
    category: str
    path: Path
    message: str | dict
    severity: str = "warning"
    auto_fixable: bool = False
    inbox: bool = False


@dataclass
class QualityReport:
    total: int = 0
    issues: list[QualityIssue] = dataclass_field(default_factory=list)
    changes: list[NormalizationChange] = dataclass_field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.category] = counts.get(issue.category, 0) + 1
        return counts

    def count(self, category: str) -> int:
        return self.counts.get(category, 0)

    def tracks(self) -> list[dict]:
        """Group all issues and planned changes by file path."""
        grouped: dict[Path, dict] = {}
        for issue in self.issues:
            item = grouped.setdefault(issue.path, {
                "path": issue.path,
                "issues": [],
                "changes": [],
            })
            item["issues"].append(issue)
        for change in self.changes:
            item = grouped.setdefault(change.path, {
                "path": change.path,
                "issues": [],
                "changes": [],
            })
            item["changes"].append(change)
        result = []
        for path, item in sorted(grouped.items(), key=lambda pair: str(pair[0])):
            issues = item["issues"]
            title = artist = album = ""
            try:
                tags = get_tags(path)
                title = (tags.title or path.stem).strip()
                artist = (tags.artist or "").strip()
                album = (tags.album or "").strip()
            except Exception:
                title = path.stem
            result.append({
                "path": str(path),
                "title": title,
                "artist": artist,
                "album": album,
                "problem_count": len(issues),
                "categories": sorted({issue.category for issue in issues}),
                "inbox": any(issue.inbox for issue in issues),
                "issues": issues,
                "changes": item["changes"],
            })
        return result


def collect_quality(output_dir: Path, include_inbox: bool = False) -> QualityReport:
    """Combine health, lint, and normalization into one report.

    Existing diagnostics remain the source of truth; this module only gives
    them a common shape and exposes the normalization plan alongside issues.
    """
    health = run_health_check(output_dir, include_inbox=include_inbox)
    lint = lint_library(output_dir, include_inbox=include_inbox)
    plan = normalize_library(output_dir, include_inbox=include_inbox)
    inbox = inbox_dir(output_dir)

    issues: list[QualityIssue] = []
    for category, category_items in health.issues_by_category.items():
        for item in category_items:
            issues.append(QualityIssue(
                category=category,
                path=item.path,
                message=item.message,
                severity="error" if category in {"unreadable", "duplicates"} else "warning",
                auto_fixable=category in {"mismatch", "loose"},
                inbox=inbox in item.path.parents,
            ))
    for category, category_items in lint.issues_by_category.items():
        for item in category_items:
            issues.append(QualityIssue(
                category=category,
                path=item.path,
                message=item.message,
                auto_fixable=category in {
                    "whitespace", "case", "feat", "tracknum", "album_artist", "genre", "year",
                },
                inbox=inbox in item.path.parents,
            ))

    # Normalization scans raw tags, so it also catches whitespace that the
    # regular analytics scanner intentionally trims before linting.
    for change in plan.changes:
        category = change.cause
        issues.append(QualityIssue(
            category=category,
            path=change.path,
            message=_message("diagnostics.quality.change", {"field": change.field, "old": change.old_value, "new": change.new_value}, fallback=f'{_FIELD_LABELS.get(change.field, change.field)}: “{change.old_value}” → “{change.new_value}”'),
            auto_fixable=True,
            inbox=inbox in change.path.parents,
        ))

    issues.sort(key=lambda item: (
        str(item.path), item.category,
        item.message.get("code", "") if isinstance(item.message, dict) else "",
        format_message(item.message),
    ))
    return QualityReport(
        total=health.total,
        issues=issues,
        changes=plan.changes,
    )


# --- План изменений: файлы, изменения, конфликты ---------------------------


@dataclass
class QualityFix:
    """Автоисправление расположения/имени файла (категории mismatch/loose)."""

    path: Path
    #: rename — имя в той же папке; move — перенос в Artist[/Album][/Disc N].
    action: str
    category: str
    target: Path
    message: dict = dataclass_field(default_factory=dict)


@dataclass
class QualityConflict:
    """Препятствие для конкретного элемента плана (блокирует только его)."""

    path: Path
    #: missing — файла нет; target_exists — целевой путь занят;
    #: duplicate_field — одно поле выбрано для изменения повторно.
    kind: str
    field: str = ""
    target: str = ""
    message: dict = dataclass_field(default_factory=dict)


_FIELD_LABELS = {
    "artist": "Artist", "title": "Title", "album": "Album", "album_artist": "Album artist",
    "genre": "Genre", "year": "Year", "cover": "Cover", "track_number": "Track number",
    "disc_number": "Disc number", "isrc": "ISRC", "composer": "Composer", "publisher": "Publisher / Label", "comment": "Comment",
}


def _message(code: str, params: dict | None = None, fallback: str = "") -> dict:
    return diagnostic_message(code, params, fallback=fallback)


@dataclass
class QualityPlan:
    """Единый план: затронутые файлы, изменения тегов, авто-фиксы и конфликты."""

    files: list[Path] = dataclass_field(default_factory=list)
    changes: list[NormalizationChange] = dataclass_field(default_factory=list)
    fixes: list[QualityFix] = dataclass_field(default_factory=list)
    conflicts: list[QualityConflict] = dataclass_field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.changes) + len(self.fixes)


def _nfc_str(value) -> str:
    import unicodedata

    return unicodedata.normalize("NFC", str(value))


def _fix_target(path: Path, output_dir: Path) -> Path | None:
    """Целевой путь auto-fix по текущим тегам (как fix_issues); None — уже на месте."""
    from .utils import sanitize_name

    try:
        tags = get_tags(path)
    except Exception:
        return None
    artist = (tags.artist or "").strip() or "Неизвестный исполнитель"
    album = (tags.album or "").strip()
    title = (tags.title or "").strip() or path.stem
    target_dir = output_dir / sanitize_name(artist)
    if album and album != artist:
        target_dir = target_dir / sanitize_name(album)
    disc_num = _parse_disc_num(tags.disc_number or "")
    if disc_num is not None:
        target_dir = target_dir / f"Disc {disc_num}"
    target = target_dir / f"{sanitize_name(title)}{path.suffix.lower()}"
    if _nfc_str(target) == _nfc_str(path):
        return None
    return target


def build_quality_plan(
    output_dir: Path,
    include_inbox: bool = False,
    paths: list[str] | None = None,
    categories: list[str] | None = None,
    change_keys: list[dict] | None = None,
) -> QualityPlan:
    """Построить план изменений по отчёту, ничего не меняя в файлах.

    ``paths`` — ограничить файлами; ``categories`` — причинами изменений
    (cause) и категориями авто-фиксов (mismatch/loose); ``change_keys`` —
    конкретными изменениями ``[{"path", "field"}]`` (пустой/отсутствующий
    фильтр означает «всё»).
    """
    report = collect_quality(output_dir, include_inbox=include_inbox)
    path_filter = {str(p) for p in paths} if paths else None
    cat_filter = set(categories) if categories else None

    def path_ok(p: Path) -> bool:
        return path_filter is None or str(p) in path_filter

    def cat_ok(c: str) -> bool:
        return cat_filter is None or c in cat_filter

    # --- Изменения тегов (с проверкой повторного изменения поля). ---
    keys: set[tuple[str, str]] | None = None
    duplicate_keys: set[tuple[str, str]] = set()
    if change_keys is not None:
        raw_keys = [
            (str(k.get("path") or ""), str(k.get("field") or "")) for k in change_keys
        ]
        keys = set(raw_keys)
        duplicate_keys = {k for k in keys if raw_keys.count(k) > 1}

    changes: list[NormalizationChange] = []
    seen_fields: set[tuple[str, str]] = set()
    for change in report.changes:
        if not path_ok(change.path) or not cat_ok(change.cause):
            continue
        key = (str(change.path), change.field)
        if keys is not None and key not in keys:
            continue
        if key in duplicate_keys or key in seen_fields:
            continue
        seen_fields.add(key)
        changes.append(change)
    conflicts: list[QualityConflict] = [
        QualityConflict(
            path=Path(path_str), kind="duplicate_field", field=fld,
            message=_message("diagnostics.quality.duplicate_field", {"field": fld}, fallback=f'Field “{_FIELD_LABELS.get(fld, fld)}” was selected for change more than once'),
        )
        for path_str, fld in sorted(duplicate_keys)
    ]

    # --- Авто-фиксы расположения (mismatch/loose), один на файл. ---
    fix_cats: dict[Path, set[str]] = {}
    for issue in report.issues:
        if issue.category not in FIX_CATEGORIES:
            continue
        if not path_ok(issue.path) or not cat_ok(issue.category):
            continue
        fix_cats.setdefault(issue.path, set()).add(issue.category)
    fixes: list[QualityFix] = []
    for fix_path in sorted(fix_cats, key=str):
        target = _fix_target(fix_path, output_dir)
        if target is None:
            continue
        fixes.append(QualityFix(
            path=fix_path,
            action="rename" if target.parent == fix_path.parent else "move",
            category="+".join(sorted(fix_cats[fix_path])),
            target=target,
            message=_message("diagnostics.quality.fix_move", {"filename": fix_path.name, "target": str(target)}, fallback=f'“{fix_path.name}” → “{target}”'),
        ))

    # --- Конфликты: отсутствие файла и занятый целевой путь. ---
    seen_missing: set[str] = set()
    for change in changes:
        key = str(change.path)
        if key in seen_missing or change.path.exists():
            continue
        seen_missing.add(key)
        conflicts.append(QualityConflict(
            path=change.path, kind="missing", message=_message("diagnostics.quality.file_missing", fallback="File not found"),
        ))
    for fix in fixes:
        if not fix.path.exists():
            if str(fix.path) not in seen_missing:
                seen_missing.add(str(fix.path))
                conflicts.append(QualityConflict(
                    path=fix.path, kind="missing", message=_message("diagnostics.quality.file_missing", fallback="File not found"),
                ))
        elif _nfc_str(fix.target) != _nfc_str(fix.path) and fix.target.exists():
            conflicts.append(QualityConflict(
                path=fix.path, kind="target_exists", target=str(fix.target),
                message=_message("diagnostics.quality.target_exists", {"filename": fix.target.name}, fallback=f"Target path occupied: {fix.target.name}"),
            ))

    files = sorted({c.path for c in changes} | {f.path for f in fixes}, key=str)
    return QualityPlan(files=files, changes=changes, fixes=fixes, conflicts=conflicts)


def apply_quality_plan(plan: QualityPlan, output_dir: Path) -> dict:
    """Применить план идемпотентно; конфликт блокирует только свой элемент.

    Возвращает результат по каждому файлу: статус, сколько элементов применено,
    пропущено (уже в нужном состоянии), ошибок и список конфликтов.
    """
    blocked = {
        (str(c.path), c.kind, c.field) for c in plan.conflicts
    }

    def is_blocked(p: Path, kind: str, fld: str = "") -> bool:
        return (str(p), kind, fld) in blocked

    changes_by_path: dict[Path, list[NormalizationChange]] = {}
    for change in plan.changes:
        changes_by_path.setdefault(change.path, []).append(change)
    fixes_by_path: dict[Path, list[QualityFix]] = {}
    for fix in plan.fixes:
        fixes_by_path.setdefault(fix.path, []).append(fix)

    results: list[dict] = []
    for path in sorted(set(changes_by_path) | set(fixes_by_path), key=str):
        entry: dict = {
            "path": str(path),
            "status": "skipped",
            "applied": 0,
            "skipped": 0,
            "errors": 0,
            "conflicts": [
                {"kind": c.kind, "field": c.field, "target": c.target, "message": c.message}
                for c in plan.conflicts if c.path == path
            ],
        }
        if not path.exists():
            entry["status"] = "conflict"
            results.append(entry)
            continue

        # 1. Точечные изменения тегов (заблокированные полями-конфликтами — мимо).
        field_map: dict[str, str] = {}
        for change in changes_by_path.get(path, []):
            if is_blocked(path, "duplicate_field", change.field):
                continue
            if change.old_value == change.new_value:
                entry["skipped"] += 1
                continue
            field_map[change.field] = change.new_value
        if field_map:
            try:
                tags = get_tags(path)
                changed = 0
                for fld, value in field_map.items():
                    if getattr(tags, fld, None) == value:
                        entry["skipped"] += 1  # идемпотентность: уже применено
                        continue
                    setattr(tags, fld, value)
                    changed += 1
                if changed and not set_tags(path, tags):
                    entry["errors"] += 1
                    entry["error"] = _message("diagnostics.quality.write_tags_failed", fallback="Could not write tags")
                elif changed:
                    entry["applied"] += changed
            except Exception as exc:
                entry["errors"] += 1
                entry["error"] = str(exc)

        # 2. Перенос/переименование: цель пересчитывается по обновлённым тегам.
        if not is_blocked(path, "missing") and not is_blocked(path, "target_exists"):
            for _fix in fixes_by_path.get(path, []):
                target = _fix_target(path, output_dir)
                if target is None:
                    entry["skipped"] += 1  # уже на месте
                    break
                if target.exists() and _nfc_str(target) != _nfc_str(path):
                    entry["conflicts"].append({
                        "kind": "target_exists", "field": "",
                        "target": str(target), "message": _message("diagnostics.quality.target_occupied", fallback="Target path occupied"),
                    })
                    break
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    path.rename(target)
                    entry["applied"] += 1
                    entry["to"] = str(target)
                except OSError as exc:
                    entry["errors"] += 1
                    entry["error"] = str(exc)
                break

        if entry["errors"]:
            entry["status"] = "error"
        elif entry["applied"]:
            entry["status"] = "applied"
        elif entry["conflicts"]:
            entry["status"] = "conflict"
        results.append(entry)

    return {
        "results": results,
        "applied": sum(e["applied"] for e in results),
        "skipped": sum(e["skipped"] for e in results),
        "errors": sum(e["errors"] for e in results),
        "conflicts": sum(1 for e in results if e["status"] == "conflict"),
        "files": len(results),
    }
