"""Нормализация тегов библиотеки: приведение к единому виду с безопасным применением.

Модуль строит *план* изменений (``plan_normalizations`` — чистая, тестируемая)
и умеет применять его (``apply_plan``). План описывает точечные изменения
полей, ничего не меняя до вызова применения.

Что нормализуем (созвучно lint-категориям):

* ``whitespace`` — лишние/сдвоенные/неразрывные пробелы;
* ``feat`` — разнобой фитов (ft./featuring/...) → канонический ``feat.``;
* ``case`` — регистр исполнителя и альбома по самому частому варианту в библиотеке;
* ``tracknum`` — ``01`` → ``1``, уборка мусора вокруг номера;
* ``genre`` — единый жанр для треков одного альбома (по самому частому);
* ``album_artist`` — единый Album Artist для треков одного альбома.

Риск минимизирован: пустые значения не заполняются навязчиво, выравниваем
только существующие (для case) и только противоречия (для genre/album_artist),
а регистр — по фактическому большинству в библиотеке.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .analytics import TrackRecord
from .tagger import get_tags, set_tags
from .lint import _FEAT_TOKEN, _FEAT_CANONICAL, _FEAT_CANONICAL_RE

#: Глобальное сопоставление похожих жанров к единому виду.
#: Ключ — строка в нижнем регистре с убранными лишними пробелами.
_GLOBAL_GENRE_MAP: dict[str, str] = {
    "альтернативная музыка": "Альтернатива",
    "rap/hip hop": "Хип-хоп",
    "рэп": "Хип-хоп",
    "фильмы/игры": "Саундтреки",
    "аниме": "Саундтреки",
    "видеоигра": "Саундтреки",
    "танцевальная музыка": "Танцевальная",
    "электронная музыка": "Электроника",
}

#: Поля-кандидаты на нормализацию (имя атрибута, подпись).
_WHITESPACE_FIELDS = (
    ("artist", "Исполнитель"),
    ("album", "Альбом"),
    ("title", "Название"),
    ("genre", "Жанр"),
    ("year", "Год"),
    ("track_number", "№ трека"),
    ("disc_number", "№ диска"),
    ("album_artist", "Album Artist"),
)

#: Поля, участвующие в выравнивании регистра/жанра/album-artist.
_STR_FIELDS = ("artist", "album", "genre", "album_artist",
               "year", "track_number", "disc_number")


@dataclass
class NormalizationChange:
    """Точечное изменение одного поля одного файла."""

    field: str
    path: Path
    old_value: str
    new_value: str
    #: Категория (для группировки в UI): whitespace/feat/case/track_number/
    #: disc_number/genre/album_artist.
    cause: str = "case"


@dataclass
class NormalizationPlan:
    """Список изменений для применения."""

    changes: list[NormalizationChange] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.changes)


def _clean_whitespace(s: str) -> str:
    """Убрать лишние пробелы: \xa0→пробел, сжать, обрезать."""
    s = s.replace("\xa0", " ")
    return " ".join(s.split())


def _normalize_feat(s: str) -> str:
    """Привести фит-конструкцию к каноническому виду ``feat.``."""
    if not _FEAT_TOKEN.search(s):
        return s
    if _FEAT_CANONICAL_RE.search(s):
        return s
    # Порядок важен: сначала длинные/явные, затем короткие.
    # Слово «with» не переписываем — слишком часто это часть названия
    # («Stand Here With Me»), а не фит-маркер (см. комментарий в lint.py).
    out = re.sub(r"\bfeaturing\b", "feat.", s, flags=re.IGNORECASE)
    out = re.sub(r"\bft\b\.?", "feat.", out, flags=re.IGNORECASE)
    out = re.sub(r"\bfeat\b\s*\.?", "feat.", out, flags=re.IGNORECASE)
    # Прибрать пробелы и возможный отступ перед точкой.
    out = re.sub(r"\s+", " ", out).strip()
    out = re.sub(r"\bfeat\s+\.", "feat.", out, flags=re.IGNORECASE)
    return out


def _clean_track_num(s: str) -> str:
    """Номер трека/диска: оставить число, убрать "01"→"1" и мусор."""
    v = _clean_whitespace(s)
    m = re.match(r"\s*(\d{1,4})\b", v)
    if not m:
        return v
    return str(int(m.group(1)))


def _canonical_genre(value: str, mapping: dict[str, str] | None = None) -> str | None:
    """Вернуть канонический жанр из глобальной карты или None."""
    mapping = mapping or _GLOBAL_GENRE_MAP
    key = _clean_whitespace(value).lower()
    canonical = mapping.get(key)
    if not canonical:
        return None
    if _clean_whitespace(value).lower() == canonical.lower():
        return None
    return canonical


def _most_common(values: list[str]) -> str:
    """Самый частый непустой вариант (первый по словарю при равенстве)."""
    counts = Counter(v for v in values if v)
    if not counts:
        return ""
    return max(
        (v for v, _c in counts.items()),
        key=lambda v: (counts[v], -sorted(values).index(v)),
    )


def plan_normalizations(records: list[TrackRecord]) -> NormalizationPlan:
    """Построить план нормализации по чистым записям (без файловой системы)."""
    plan = NormalizationPlan()
    existing: set[tuple] = set()

    def _add(field: str, rec: TrackRecord, old: str, new: str, cause: str) -> None:
        key = (field, rec.path)
        if key in existing:
            return
        existing.add(key)
        plan.changes.append(NormalizationChange(
            field=field, path=rec.path, old_value=old, new_value=new,
            cause=cause,
        ))

    # --- Локальные: пробелы, фиты, номера. ---
    for rec in records:
        for name in _STR_FIELDS:
            value = getattr(rec, name) or ""
            cleaned = _clean_whitespace(value)
            if cleaned != value:
                _add(name, rec, value, cleaned, "whitespace")

        for name in ("title", "artist"):
            value = getattr(rec, name) or ""
            fixed = _normalize_feat(value)
            if fixed != value:
                _add(name, rec, value, fixed, "feat")

        for name in ("track_number", "disc_number"):
            value = getattr(rec, name) or ""
            cleaned = _clean_track_num(value)
            if cleaned != value:
                _add(name, rec, value, cleaned,
                     "track_number" if name == "track_number" else "disc_number")

    # --- Регистр исполнителя и альбома (по библиотеке). ---
    artist_counts: dict[str, Counter[str]] = {}
    album_counts: dict[tuple[str, str], Counter[str]] = {}
    for rec in records:
        if rec.artist:
            artist_counts.setdefault(rec.artist.lower(), Counter())[rec.artist] += 1
        if rec.artist and rec.album:
            key = (rec.artist.lower(), rec.album.lower())
            album_counts.setdefault(key, Counter())[rec.album] += 1

    for rec in records:
        if rec.artist:
            counts = artist_counts[rec.artist.lower()]
            canonical = _most_common(list(counts))
            if canonical and rec.artist != canonical:
                _add("artist", rec, rec.artist, canonical, "case")
        if rec.artist and rec.album:
            key = (rec.artist.lower(), rec.album.lower())
            counts = album_counts[key]
            canonical = _most_common(list(counts))
            if canonical and rec.album != canonical:
                _add("album", rec, rec.album, canonical, "case")

    # --- Жанр и Album Artist внутри альбома (по самому частому). ---
    album_genre: dict[tuple[str, str], str] = {}
    album_aa: dict[tuple[str, str], str] = {}
    for rec in records:
        if not (rec.artist and rec.album):
            continue
        key = (rec.artist.lower(), rec.album.lower())
        album_genre.setdefault(key, _most_common([
            r.genre for r in _album_records(records, rec.artist, rec.album)
        ]))
        album_aa.setdefault(key, _most_common([
            r.album_artist for r in _album_records(records, rec.artist, rec.album)
        ]))

    for rec in records:
        if not (rec.artist and rec.album):
            continue
        key = (rec.artist.lower(), rec.album.lower())
        can_genre = album_genre[key]
        if can_genre and rec.genre and _clean_whitespace(rec.genre) != can_genre:
            _add("genre", rec, rec.genre, can_genre, "genre")
        can_aa = album_aa[key]
        if can_aa and rec.album_artist and _clean_whitespace(rec.album_artist) != can_aa:
            _add("album_artist", rec, rec.album_artist, can_aa, "album_artist")

    # --- Глобальные жанры (по карте синонимов). ---
    for rec in records:
        if not rec.genre:
            continue
        canonical = _canonical_genre(rec.genre)
        if canonical:
            _add("genre", rec, rec.genre, canonical, "global_genre")

    return plan


def _album_records(records: list[TrackRecord], artist: str, album: str) -> list[TrackRecord]:
    """Записи того же альбома (по artist.lower/album.lower)."""
    return [
        r for r in records
        if r.artist.lower() == artist.lower() and r.album.lower() == album.lower()
    ]


def apply_plan(plan: NormalizationPlan, causes: list[str] | None = None) -> tuple[int, int]:
    """Применить план к файлам: читает текущие теги, меняет поля, пишет.

    ``causes`` — фильтр по категории изменений (whitespace/case/feat/...):
    применяются только изменения с указанными cause. ``None``/пустой список —
    весь план. Возвращает (изменено, ошибок).
    """
    from collections import defaultdict

    changes = plan.changes
    if causes:
        keep = set(causes)
        changes = [c for c in changes if c.cause in keep]

    by_path: dict[Path, dict[str, str]] = defaultdict(dict)
    for change in changes:
        if change.old_value != change.new_value:
            by_path[change.path][change.field] = change.new_value

    applied = 0
    errors = 0
    for path, field_map in by_path.items():
        try:
            tags = get_tags(path)
            for field, value in field_map.items():
                setattr(tags, field, value)
            if set_tags(path, tags):
                applied += 1
            else:
                errors += 1
        except Exception:
            errors += 1
    return applied, errors


def normalize_library(output_dir: Path, include_inbox: bool = False) -> NormalizationPlan:
    """Просканировать и построить план нормализации (без применения).

    Читает сырые теги (без уборки пробелов, в отличие от ``scan_library``),
    чтобы план мог исправить в том числе ведущие/хвостовые пробелы.
    ``include_inbox`` — учитывать и файлы в ``Inbox``.
    """
    from .analytics import library_files

    records: list[TrackRecord] = []
    for path in library_files(output_dir, include_inbox=include_inbox):
        try:
            tags = get_tags(path)
        except Exception:
            continue
        records.append(TrackRecord(
            path=path,
            artist=tags.artist or "",
            album=tags.album or "",
            title=tags.title or "",
            year=tags.year or "",
            genre=tags.genre or "",
            album_artist=tags.album_artist or "",
            track_number=tags.track_number or "",
            disc_number=tags.disc_number or "",
        ))
    return plan_normalizations(records)


def plan_global_genre_normalizations(
    records: list[TrackRecord],
    mapping: dict[str, str] | None = None,
) -> NormalizationPlan:
    """Построить план глобальной нормализации жанров по всей библиотеке."""
    plan = NormalizationPlan()
    for rec in records:
        if not rec.genre:
            continue
        canonical = _canonical_genre(rec.genre, mapping)
        if canonical:
            plan.changes.append(NormalizationChange(
                field="genre",
                path=rec.path,
                old_value=rec.genre,
                new_value=canonical,
                cause="global_genre",
            ))
    return plan


def normalize_global_genres(
    output_dir: Path,
    mapping: dict[str, str] | None = None,
) -> NormalizationPlan:
    """Просканировать библиотеку и построить план глобальной нормализации жанров."""
    from .analytics import library_files

    records: list[TrackRecord] = []
    for path in library_files(output_dir):
        try:
            tags = get_tags(path)
        except Exception:
            continue
        records.append(TrackRecord(
            path=path,
            artist=tags.artist or "",
            album=tags.album or "",
            title=tags.title or "",
            year=tags.year or "",
            genre=tags.genre or "",
            album_artist=tags.album_artist or "",
            track_number=tags.track_number or "",
            disc_number=tags.disc_number or "",
        ))
    return plan_global_genre_normalizations(records, mapping=mapping)


# --- Вывод ---------------------------------------------------------------


def render_plan(plan: NormalizationPlan, console, max_preview: int = 40) -> None:
    """Нарисовать план изменений в rich-консоль."""
    field_labels = {
        "artist": "Artist",
        "album": "Album",
        "title": "Title",
        "genre": "Genre",
        "album_artist": "Album Artist",
        "year": "Year",
        "track_number": "Track number",
        "disc_number": "Disc number",
    }

    console.print(f"[bold]Changes:[/bold] {plan.count}")
    for i, change in enumerate(plan.changes[:max_preview], 1):
        label = field_labels.get(change.field, change.field)
        console.print(f"{i:>3}. {change.path.name}")
        console.print(f"      [{label}] «{change.old_value}» → «{change.new_value}»")
    if plan.count > max_preview:
        console.print(f"   … and {plan.count - max_preview} more")
