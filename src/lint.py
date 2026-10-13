"""Lint музыкальной библиотеки — диагностика проблем в тегах без изменения файлов.

Модуль не зависит от UI: ``lint_library`` читает теги через ``scan_library``,
``categorize`` считает проблемы по чистым записям (тестируемо без файловой
системы), ``render_lint`` рисует отчёт через rich.

Категории проблем:

* ``whitespace`` — лишние/сдвоенные/неразрывные пробелы в значениях тегов;
* ``case`` — непоследовательный регистр исполнителя/альбома;
* ``feat`` — разнобой в форматировании фитов (ft./featuring/...);
* ``tracknum`` — некорректные или повторяющиеся номера треков/дисков;
* ``album_artist`` — противоречивый Album Artist внутри одного альбома;
* ``genre`` — разные жанры у треков одного альбома;
* ``year`` — некорректный год/дата.

Все функции чисто диагностические: ничего не пишут на диск. Нормализация —
отдельный этап (см. plan).
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .analytics import TrackRecord, scan_library
from .messages import format_message, message as diagnostic_message

#: Значения, которые проверяем на пробелы/регистр (имя атрибута, подпись).
_TEXT_FIELDS = (
    ("artist", "Исполнитель"),
    ("album", "Альбом"),
    ("title", "Название"),
    ("genre", "Жанр"),
    ("year", "Год"),
    ("track_number", "№ трека"),
    ("disc_number", "№ диска"),
)

#: Регэкспы вариантов написания фитов (без учёта регистра).
#: Слово «with» сознательно не считается фит-маркером: оно слишком часто
#: является частью названия («Stand Here With Me», «I Wanna Dance with
#: Somebody») — та же логика, что в ytmusic._FEATURE_INLINE_RE.
_FEAT_TOKEN = re.compile(r"\b(?:ft\.?|feat(?:uring)?\.?)\b", re.IGNORECASE)

#: Каноническое написание фитов: «feat.» (с точкой, как в "feat. B").
_FEAT_CANONICAL_RE = re.compile(r"\bfeat\.", re.IGNORECASE)
_FEAT_CANONICAL = "feat."

_YEAR_RE = re.compile(r"^\d{4}$")


@dataclass
class LintIssue:
    """Одна найденная проблема в тегах."""

    category: str
    path: Path
    message: str | dict = field(default_factory=dict)


_FIELD_LABELS = {
    "artist": "Artist", "album": "Album", "title": "Title", "genre": "Genre",
    "year": "Year", "track_number": "Track number", "disc_number": "Disc number",
}


def _message(code: str, params: dict | None = None, fallback: str = "") -> dict:
    return diagnostic_message(code, params, fallback=fallback)


@dataclass
class LintReport:
    """Результат lint-проверки библиотеки."""

    total: int = 0
    issues_by_category: dict[str, list[LintIssue]] = field(default_factory=dict)
    issues: list[LintIssue] = field(default_factory=list)

    def count(self, category: str) -> int:
        return len(self.issues_by_category.get(category, []))


def _add(by_cat: dict[str, list[LintIssue]], category: str, issue: LintIssue) -> None:
    by_cat.setdefault(category, []).append(issue)


def _norm(value: str) -> str:
    """Нормализовать строку для сравнения «есть/нет»."""
    return (value or "").strip()


def _key(value: str) -> str:
    """Lowercase-ключ для группировки написаний."""
    return _norm(value).lower()


def _has_bad_whitespace(value: str) -> bool:
    """Есть ли лишние/сдвоенные/неразрывные пробелы."""
    if "\xa0" in value:
        return True
    stripped = value.strip()
    if stripped != value:
        return True
    return bool(re.search(r"  +", stripped))


def _value_is_feat(value: str) -> bool:
    """Содержит ли значение фит-конструкцию (хоть как-то)."""
    return bool(_FEAT_TOKEN.search(value))


def _feat_not_canonical(value: str) -> bool:
    """Есть ли фит-конструкция, но не в каноническом виде «feat.»."""
    if not _value_is_feat(value):
        return False
    return not _FEAT_CANONICAL_RE.search(value)


def _parse_track_num(value: str) -> int | None:
    """Разобрать номер трека/диска в целое (None, если не число)."""
    v = _norm(value)
    if not v:
        return None
    m = re.search(r"\d+", v)
    if not m:
        return None
    return int(m.group(0))


def _plausible_year(value: str) -> bool:
    """Правдоподобный ли год: 4 цифры, не 0, не сильно в будущем."""
    v = _norm(value)
    if not v:
        return True
    if not _YEAR_RE.match(v):
        return False
    y = int(v)
    if y <= 0:
        return False
    if y > date.today().year + 1:
        return False
    return True


def categorize(records: list[TrackRecord]) -> LintReport:
    """Посчитать lint-проблемы по чистым записям (без файловой системы)."""
    report = LintReport(total=len(records))
    by_cat: dict[str, list[LintIssue]] = {}

    # --- Whitespace во всех текстовых полях. ---
    for rec in records:
        for name, _label in _TEXT_FIELDS:
            value = getattr(rec, name)
            if _has_bad_whitespace(value or ""):
                _add(by_cat, "whitespace", LintIssue(
                    "whitespace", rec.path,
                    _message("diagnostics.lint.whitespace", {"field": name, "value": value.strip()[:40]}, fallback=f'“{_FIELD_LABELS.get(name, name)}”: extra spaces in “{value.strip()[:40]}”'),
                ))

    # --- Регистр исполнителей и альбомов. ---
    # Для каждого ключа (lowercase) считаем варианты написания; самый частый
    # считаем каноническим, остальные — случаи непоследовательного регистра.
    artist_groups: dict[str, Counter[str]] = {}
    album_groups: dict[tuple[str, str], Counter[str]] = {}
    for rec in records:
        if rec.artist:
            artist_groups.setdefault(_key(rec.artist), Counter())[rec.artist] += 1
        if rec.album and rec.artist:
            key = (_key(rec.artist), rec.album)
            album_groups.setdefault((_key(rec.album), _key(rec.artist)), Counter())[rec.album] += 1

    # Исполнитель.
    for key, counts in artist_groups.items():
        if len(counts) < 2:
            continue
        canonical = counts.most_common(1)[0][0]
        for variant, _c in counts.items():
            if variant == canonical:
                continue
            _add(by_cat, "case", LintIssue(
                "case", _first_path_for_artist(records, variant),
                _message("diagnostics.lint.artist_case", {"variant": variant, "canonical": canonical}, fallback=f'Artist capitalization “{variant}” differs from “{canonical}”'),
            ))

    # Альбом (в контексте исполнителя).
    for (album_key, artist_key), counts in album_groups.items():
        if len(counts) < 2:
            continue
        canonical = counts.most_common(1)[0][0]
        for variant, _c in counts.items():
            if variant == canonical:
                continue
            rec = next(
                (r for r in records
                 if _key(r.album) == album_key and _key(r.artist) == artist_key
                 and r.album == variant),
                None,
            )
            if rec is None:
                continue
            _add(by_cat, "case", LintIssue(
                "case", rec.path,
                _message("diagnostics.lint.album_case", {"variant": variant, "canonical": canonical}, fallback=f'Album capitalization “{variant}” differs from “{canonical}”'),
            ))

    # --- Форматирование фитов. ---
    for rec in records:
        for value in (rec.title, rec.artist):
            if value and _feat_not_canonical(value):
                _add(by_cat, "feat", LintIssue(
                    "feat", rec.path,
                    _message("diagnostics.lint.feat", {"value": value[:40]}, fallback=f'Nonstandard featured artist in “{value[:40]}” (use “{_FEAT_CANONICAL}”)'),
                ))

    # --- Номера треков/дисков внутри альбома. ---
    # Треки группируются по (artist, album, disc_number) — повтор track_number
    # на разных дисках нормален и не флагается.
    disc_tracknums: dict[tuple[str, str, str], Counter[int | None]] = {}
    for rec in records:
        if not (rec.artist and rec.album):
            continue
        dk = _key(rec.disc_number) if rec.disc_number else ""
        key = (_key(rec.artist), _key(rec.album), dk)
        disc_tracknums.setdefault(key, Counter())[_parse_track_num(rec.track_number)] += 1

    for rec in records:
        if rec.artist and rec.album:
            dk = _key(rec.disc_number) if rec.disc_number else ""
            key = (_key(rec.artist), _key(rec.album), dk)
            tn = _parse_track_num(rec.track_number)
            if tn is not None and disc_tracknums[key][tn] > 1:
                _add(by_cat, "tracknum", LintIssue(
                    "tracknum", rec.path,
                    _message("diagnostics.lint.duplicate_track_number", {"value": rec.track_number}, fallback=f'“{rec.track_number}”: duplicate album track number'),
                ))
            if (rec.track_number or "").strip() and tn is None:
                _add(by_cat, "tracknum", LintIssue(
                    "tracknum", rec.path,
                    _message("diagnostics.lint.invalid_track_number", {"value": rec.track_number}, fallback=f'“{rec.track_number}”: invalid track number'),
                ))
            if (rec.disc_number or "").strip() and _parse_track_num(rec.disc_number) is None:
                _add(by_cat, "tracknum", LintIssue(
                    "tracknum", rec.path,
                    _message("diagnostics.lint.invalid_disc_number", {"value": rec.disc_number}, fallback=f'“{rec.disc_number}”: invalid disc number'),
                ))

    # --- Album Artist противоречив внутри альбома. ---
    album_aa: dict[tuple[str, str], set[str]] = {}
    for rec in records:
        if rec.artist and rec.album:
            album_aa.setdefault((_key(rec.artist), _key(rec.album)), set()).add(_norm(rec.album_artist))
    for rec in records:
        if not (rec.artist and rec.album):
            continue
        key = (_key(rec.artist), _key(rec.album))
        variants = {v for v in album_aa[key] if v}
        if len(variants) > 1 and _norm(rec.album_artist):
            _add(by_cat, "album_artist", LintIssue(
                "album_artist", rec.path,
                _message("diagnostics.lint.album_artist_conflict", {"value": rec.album_artist}, fallback=f'Album Artist “{rec.album_artist}” conflicts with other tracks in the album'),
            ))

    # --- Жанры внутри альбома. ---
    album_genres: dict[tuple[str, str], set[str]] = {}
    for rec in records:
        if rec.artist and rec.album and rec.genre:
            album_genres.setdefault((_key(rec.artist), _key(rec.album)), set()).add(_norm(rec.genre))
    for rec in records:
        if not (rec.artist and rec.album and rec.genre):
            continue
        key = (_key(rec.artist), _key(rec.album))
        genres = album_genres[key]
        if len(genres) > 1:
            _add(by_cat, "genre", LintIssue(
                "genre", rec.path,
                _message("diagnostics.lint.genre_conflict", {"value": rec.genre, "others": ", ".join(sorted(genres))}, fallback=f'Genre “{rec.genre}” differs from other album tracks ({", ".join(sorted(genres))})'),
            ))

    # --- Год. ---
    for rec in records:
        if rec.year and not _plausible_year(rec.year):
            _add(by_cat, "year", LintIssue(
                "year", rec.path,
                _message("diagnostics.lint.invalid_year", {"value": rec.year}, fallback=f'Invalid year “{rec.year}”'),
            ))

    issues: list[LintIssue] = []
    for cat_list in by_cat.values():
        issues.extend(cat_list)
    issues.sort(key=lambda i: (i.path, i.category))
    report.issues = issues
    report.issues_by_category = by_cat
    return report


def _first_path_for_artist(records: list[TrackRecord], artist: str) -> Path:
    """Первый путь записи с данным исполнителем (для отчёта)."""
    for r in records:
        if _norm(r.artist) == _norm(artist):
            return r.path
    return records[0].path if records else Path("")


def lint_library(output_dir: Path, include_inbox: bool = False) -> LintReport:
    """Просканировать библиотеку и посчитать lint-проблемы.

    ``include_inbox`` — учитывать и файлы в ``Inbox``.
    """
    records, _errors = scan_library(output_dir, include_inbox=include_inbox)
    return categorize(records)


# --- Вывод ---------------------------------------------------------------


def render_lint(report: LintReport, console, max_preview: int = 20) -> None:
    """Нарисовать отчёт lint-проверки в переданную rich-консоль."""
    from rich.table import Table

    order = ["whitespace", "case", "feat", "tracknum", "album_artist", "genre", "year"]
    labels = {
        "whitespace": "Extra whitespace",
        "case": "Capitalization",
        "feat": "Featured artist format",
        "tracknum": "Track/disc numbers",
        "album_artist": "Album artist",
        "genre": "Album genres",
        "year": "Year",
    }

    table = Table(title="Tag check")
    table.add_column("Category", style="green")
    table.add_column("Issues", justify="right")
    table.add_row("Tracks checked", str(report.total))
    for category in order:
        count = report.count(category)
        color = "red" if count else "green"
        table.add_row(labels[category], f"[{color}]{count}[/{color}]")
    table.add_row("Total issues", str(len(report.issues)))
    console.print(table)
    console.print()

    for category in order:
        issues = report.issues_by_category.get(category, [])
        if not issues:
            continue
        t = Table(title=f"{labels[category]} ({len(issues)})")
        t.add_column("File", style="bold")
        t.add_column("Problem", style="dim")
        for issue in issues[:max_preview]:
            t.add_row(issue.path.name, format_message(issue.message))
        if len(issues) > max_preview:
            t.add_row("…", f"and {len(issues) - max_preview} more")
        console.print(t)
        console.print()
