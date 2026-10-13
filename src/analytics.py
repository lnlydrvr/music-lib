"""Аналитика музыкальной библиотеки — сканирование, агрегация, вывод.

Модуль не зависит от UI: ``scan_library`` читает файлы и теги, ``aggregate``
считает статистику по чистым записям (тестируемо без файловой системы),
``render_stats`` рисует готовые таблицы через rich.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .tagger import Tagger

#: Аудиоформаты, которые считаются частью библиотеки (для сканирования).
AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".ogg", ".wav", ".aac", ".wma"}

TOP_N = 10
MISSING_FILE_PREVIEW = 3

#: Поля тегов, для которых считаем полноту данных.
FILL_FIELDS = (
    ("title", "Название"),
    ("genre", "Жанр"),
    ("year", "Год"),
    ("album", "Альбом"),
    ("album_artist", "Album Artist"),
    ("composer", "Композитор"),
    ("isrc", "ISRC"),
    ("lyrics", "Текст"),
    ("cover", "Обложка"),
)

_STR_FIELDS = {name for name, _label in FILL_FIELDS if name != "cover"}


@dataclass
class TrackRecord:
    """Одна запись библиотеки со всем, что нужно для аналитики."""

    path: Path
    artist: str = ""
    album: str = ""
    title: str = ""
    year: str = ""
    genre: str = ""
    album_artist: str = ""
    isrc: str = ""
    composer: str = ""
    track_number: str = ""
    disc_number: str = ""
    lyrics: str = ""
    lyrics_synced: str = ""
    cover: bool = False
    size_bytes: int = 0
    duration_seconds: int = 0
    bitrate: int = 0  # кбит/с, 0 — не определяется
    mtime: float = 0.0
    stream_duration: float = field(default=0.0, repr=False)
    stream_bitrate: int = field(default=0, repr=False)


@dataclass
class LibraryStats:
    """Сводная статистика библиотеки."""

    total: int = 0
    errors: int = 0
    artists: int = 0
    albums: int = 0
    total_seconds: int = 0
    total_size: int = 0
    formats: dict[str, int] = field(default_factory=dict)
    top_artists: list[tuple[str, int]] = field(default_factory=list)
    top_albums: list[tuple[str, int]] = field(default_factory=list)
    top_genres: list[tuple[str, int]] = field(default_factory=list)
    years: dict[str, int] = field(default_factory=dict)
    min_year: str = ""
    max_year: str = ""
    months: list[tuple[str, int]] = field(default_factory=list)
    missing: dict[str, int] = field(default_factory=dict)
    missing_files: dict[str, list[str]] = field(default_factory=dict)
    longest: list[TrackRecord] = field(default_factory=list)


def _value(value: str) -> str:
    """Нормализовать значение тега для проверки «есть/нет»."""
    return (value or "").strip()


def _year4(year: str | None) -> str:
    """Извлечь год (первые 4 цифры) из значения тега 'year', иначе ''."""
    match = re.match(r"(\d{4})", (year or "").strip())
    return match.group(1) if match else ""


def _scan_file(path: Path) -> TrackRecord:
    """Прочитать теги и метаданные одного файла в TrackRecord."""
    tagger = Tagger(path)
    tags = tagger.read()
    stat = path.stat()
    audio = tagger._file
    stream_duration = _stream_duration(audio)
    duration = int(stream_duration)
    stream_bitrate = _stream_bitrate(audio)

    record = TrackRecord(
        path=path,
        artist=_value(tags.artist),
        album=_value(tags.album),
        title=_value(tags.title) or path.stem,
        year=_value(tags.year),
        genre=_value(tags.genre),
        album_artist=_value(tags.album_artist),
        isrc=_value(tags.isrc),
        composer=_value(tags.composer),
        track_number=_value(tags.track_number),
        disc_number=_value(tags.disc_number),
        lyrics=_value(tags.lyrics),
        lyrics_synced=_value(tags.lyrics_synced),
        cover=bool(tags.cover_data),
        size_bytes=stat.st_size,
        duration_seconds=duration,
        bitrate=_file_bitrate(path, duration, audio, stat.st_size, stream_bitrate),
        stream_duration=stream_duration,
        stream_bitrate=stream_bitrate,
        mtime=stat.st_mtime,
    )
    return record


def _file_duration(path: Path, audio=None) -> int:
    """Длительность файла в секундах (0, если не читается)."""
    try:
        if audio is None:
            audio = Tagger(path)._file
        return int(_stream_duration(audio))
    except Exception:
        pass
    return 0


def _stream_duration(audio) -> float:
    try:
        info = getattr(audio, "info", None) if audio is not None else None
        return float(getattr(info, "length", 0) or 0) if info else 0.0
    except Exception:
        return 0.0


def _stream_bitrate(audio) -> int:
    try:
        info = getattr(audio, "info", None) if audio is not None else None
        if not info:
            return 0
        bitrate = int(getattr(info, "bitrate", 0) or 0)
        if not bitrate:
            bitrate = int(getattr(info, "bitrate_kbps", 0) or 0) * 1000
        return bitrate
    except Exception:
        return 0


def _file_bitrate(
    path: Path, duration: int, audio=None, size: int | None = None,
    bitrate: int | None = None,
) -> int:
    """Битрейт файла в кбит/с (0, если не определяется).

    Сначала пробуем mutagen (точно для CBR/VBR-заголовков MP3/AAC),
    иначе оцениваем по размеру и длительности (подходит для FLAC/Vorbis).
    """
    try:
        if bitrate is None:
            bitrate = _stream_bitrate(audio if audio is not None else Tagger(path)._file)
        if bitrate:
            return int(bitrate // 1000)
    except Exception:
        pass
    try:
        if duration > 0:
            if size is None:
                size = path.stat().st_size
            return int(size * 8 / duration // 1000)
    except Exception:
        pass
    return 0


def library_files(output_dir: Path, include_inbox: bool = False) -> list[Path]:
    """Все аудиофайлы библиотеки, отсортированные по пути.

    Исключает промежуточную папку ``Inbox`` — файлы в ней ещё не обработаны и
    не считаются частью «чистой» библиотеки. Если ``include_inbox`` True —
    файлы в ``Inbox`` тоже включаются. Скрытые папки (``.system`` и прочие
    точечные) не сканируются — там служебные файлы, а не музыка.
    """
    from .config import inbox_dir

    inbox = inbox_dir(output_dir)
    files = []
    for path in output_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue
        if inbox in path.parents and not include_inbox:
            continue
        if any(part.startswith(".") for part in path.relative_to(output_dir).parts[:-1]):
            continue
        files.append(path)
    return sorted(files, key=str)


def scan_library(output_dir: Path, include_inbox: bool = False) -> tuple[list[TrackRecord], int]:
    """Сканировать библиотеку: вернуть (records, число ошибок чтения).

    Файлы во временной папке ``Inbox`` в состав библиотеки не входят, если
    ``include_inbox`` не передан как True.
    """
    records: list[TrackRecord] = []
    errors = 0
    for path in library_files(output_dir, include_inbox=include_inbox):
        try:
            records.append(_scan_file(path))
        except Exception:
            errors += 1
    return records, errors


def scan_directory(folder: Path) -> tuple[list[TrackRecord], int]:
    """Сканировать произвольную папку рекурсивно (без исключений)."""
    records: list[TrackRecord] = []
    errors = 0
    files = sorted(
        (p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS),
        key=str,
    )
    for path in files:
        try:
            records.append(_scan_file(path))
        except Exception:
            errors += 1
    return records, errors


def aggregate(records: list[TrackRecord]) -> LibraryStats:
    """Посчитать статистику по чистым записям (без файловой системы)."""
    stats = LibraryStats(total=len(records))

    artists: set[str] = set()
    albums: set[tuple[str, str]] = set()
    genres: Counter[str] = Counter()
    artist_counter: Counter[str] = Counter()
    album_counter: Counter[str] = Counter()
    years: Counter[str] = Counter()
    missing: dict[str, int] = {name: 0 for name, _label in FILL_FIELDS}

    total_seconds = 0
    total_size = 0

    for rec in records:
        total_seconds += rec.duration_seconds
        total_size += rec.size_bytes
        stats.formats[rec.path.suffix.lower()] = (
            stats.formats.get(rec.path.suffix.lower(), 0) + 1
        )

        if rec.artist:
            artists.add(rec.artist.lower())
            artist_counter[rec.artist] += 1

        if rec.album:
            key = (rec.artist.lower(), rec.album)
            albums.add(key)
            label = f"{rec.artist} — {rec.album}" if rec.artist else rec.album
            album_counter[label] += 1

        if rec.genre:
            genres[rec.genre] += 1

        year = _year4(rec.year)
        if year:
            years[year] += 1

        for name in _STR_FIELDS:
            if name == "lyrics":
                present = _value(rec.lyrics) or _value(rec.lyrics_synced)
            else:
                present = _value(getattr(rec, name))
            if not present:
                missing[name] += 1
                stats.missing_files.setdefault(name, [])
                if len(stats.missing_files[name]) < MISSING_FILE_PREVIEW:
                    stats.missing_files[name].append(rec.path.name)
        if not rec.cover:
            missing["cover"] += 1
            stats.missing_files.setdefault("cover", [])
            if len(stats.missing_files["cover"]) < MISSING_FILE_PREVIEW:
                stats.missing_files["cover"].append(rec.path.name)

    stats.artists = len(artists)
    stats.albums = len(albums)
    stats.total_seconds = total_seconds
    stats.total_size = total_size
    stats.top_artists = artist_counter.most_common(TOP_N)
    stats.top_albums = album_counter.most_common(TOP_N)
    stats.top_genres = genres.most_common(TOP_N)
    stats.years = dict(sorted(years.items()))
    if stats.years:
        keys = list(stats.years)
        stats.min_year, stats.max_year = keys[0], keys[-1]

    months: Counter[str] = Counter()
    for rec in records:
        if rec.mtime:
            months[datetime.fromtimestamp(rec.mtime).strftime("%Y-%m")] += 1
    stats.months = months.most_common(12)
    stats.months.sort(key=lambda m: m[0])

    stats.missing = missing
    stats.longest = sorted(
        [rec for rec in records if rec.duration_seconds > 0],
        key=lambda r: r.duration_seconds,
        reverse=True,
    )[:TOP_N]
    return stats


def collect_stats(output_dir: Path) -> LibraryStats:
    """Просканировать библиотеку и посчитать статистику."""
    records, errors = scan_library(output_dir)
    stats = aggregate(records)
    stats.errors = errors
    return stats


# --- Вывод ---------------------------------------------------------------


def _fmt_bytes(size: int) -> str:
    """Форматировать размер файла: B / MB / GB."""
    mb = size / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb:.1f} MB"


def _fmt_seconds(total: int) -> str:
    """Число секунд → 'чч:мм' / 'дд ч чч:мм'."""
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days} д {hours} ч {minutes} м"
    return f"{hours}:{minutes:02d} ч"


def _bar(value: int, maximum: int, width: int = 16) -> str:
    """Простая гистограмма из символов █ (есть минимум 1 у ненулевого)."""
    if not maximum or value <= 0:
        return ""
    blocks = max(1, round(value / maximum * width))
    return "█" * blocks


def render_stats(stats: LibraryStats, console) -> None:
    """Нарисовать все таблицы статистики в переданную rich-консоль."""
    _render_overview(stats, console)
    _render_top(stats, console)
    _render_years(stats, console)
    _render_months(stats, console)
    _render_fill(stats, console)
    _render_longest(stats, console)


def _render_overview(stats: LibraryStats, console) -> None:
    from rich.table import Table

    table = Table(title="Обзор")
    table.add_column("Показатель", style="green")
    table.add_column("Значение")

    table.add_row("Треков", str(stats.total))
    table.add_row("Исполнителей", str(stats.artists))
    table.add_row("Альбомов", str(stats.albums))
    table.add_row("Общее время", _fmt_seconds(stats.total_seconds))
    table.add_row("Размер", _fmt_bytes(stats.total_size))
    formats = ", ".join(
        f"{ext.lstrip('.').upper()}: {count}" for ext, count in sorted(stats.formats.items())
    )
    table.add_row("Форматы", formats or "—")
    if stats.errors:
        table.add_row("Ошибки чтения", f"[red]{stats.errors}[/red]")
    console.print(table)
    console.print()


def _render_top(stats: LibraryStats, console) -> None:
    from rich.table import Table

    def _block(entries: list[tuple[str, int]], title: str) -> None:
        if not entries:
            return
        table = Table(title=title)
        table.add_column("#", style="dim", width=4)
        table.add_column("Название", style="bold")
        table.add_column("Треков", justify="right")
        for i, (name, count) in enumerate(entries, 1):
            table.add_row(str(i), name, str(count))
        console.print(table)
        console.print()

    _block(stats.top_artists, "Топ исполнителей")
    _block(stats.top_albums, "Топ альбомов")
    _block(stats.top_genres, "Топ жанров")


def _render_years(stats: LibraryStats, console) -> None:
    from rich.table import Table

    if not stats.years:
        return
    maximum = max(stats.years.values())
    table = Table(title="Годы релизов")
    table.add_column("Год", style="green")
    table.add_column("Треков", justify="right")
    table.add_column("", style="green")
    for year, count in stats.years.items():
        table.add_row(year, str(count), _bar(count, maximum))
    console.print(table)
    if stats.min_year and stats.max_year:
        span = int(stats.max_year) - int(stats.min_year) + 1
        console.print(f"[dim]Охват: {stats.min_year}–{stats.max_year} ({span} лет)[/dim]")
    console.print()


def _render_months(stats: LibraryStats, console) -> None:
    from rich.table import Table

    if not stats.months:
        return
    maximum = max(c for _, c in stats.months)
    table = Table(title="Пополнение по месяцам")
    table.add_column("Месяц", style="green")
    table.add_column("Треков", justify="right")
    table.add_column("", style="green")
    for month, count in stats.months:
        table.add_row(month, str(count), _bar(count, maximum))
    console.print(table)
    console.print()


def _render_fill(stats: LibraryStats, console) -> None:
    from rich.table import Table

    table = Table(title="Полнота тегов")
    table.add_column("Поле", style="green")
    table.add_column("Заполнено", justify="right")
    table.add_column("Нет", justify="right")

    for name, label in FILL_FIELDS:
        missing = stats.missing.get(name, 0)
        present = stats.total - missing
        if missing:
            table.add_row(label, str(present), f"[red]{missing}[/red]")
        else:
            table.add_row(label, str(present), "[dim]0[/dim]")
    console.print(table)
    console.print()
    _render_missing_files(stats, console)


def _render_missing_files(stats: LibraryStats, console) -> None:
    from rich.table import Table

    rows = [(name, label) for name, label in FILL_FIELDS if stats.missing.get(name, 0) > 0]
    if not rows:
        return
    table = Table(title="Где не хватает данных")
    table.add_column("Поле", style="green")
    table.add_column("Примеры файлов", style="dim")
    for name, label in rows:
        files = stats.missing_files.get(name, [])
        preview = ", ".join(files) if files else "—"
        table.add_row(label, preview)
    console.print(table)
    console.print()


def _render_longest(stats: LibraryStats, console) -> None:
    if not stats.longest:
        return
    from rich.table import Table

    table = Table(title="Самые длинные треки")
    table.add_column("#", style="dim", width=4)
    table.add_column("Название", style="bold")
    table.add_column("Исполнитель")
    table.add_column("Длительность", justify="right")
    for i, rec in enumerate(stats.longest, 1):
        title = rec.title or rec.path.name
        dur = f"{rec.duration_seconds // 60}:{rec.duration_seconds % 60:02d}"
        table.add_row(str(i), title, rec.artist or "—", dur)
    console.print(table)
    console.print()
