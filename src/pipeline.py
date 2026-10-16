"""Инкапсулированные шаги пайплайна скачивания.

После попадания файла в папку ``Inbox`` экраны запускают цепочку:
1. Теги из YouTube (прямая запись).
2. Мультиисточниковый фетч тегов (iTunes/Deezer) — через модалки.
3. Лирикс через LRCLIB.
4. Перенос файла в библиотеку (Artist/Album).

Здесь собраны блокирующие шаги (лирикс и перенос), которые не зависят от
модальной цепочки интерфейса и переиспользуются экранами поиска и Shazam.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from .lyrics import fetch_lyrics
from .tagger import get_tags, set_tags
from .utils import sanitize_name


def fetch_and_apply_lyrics(filepath: Path) -> bool:
    """Загрузить текст песни через LRCLIB по текущим тегам и записать его.

    Синхронизированный текст (LRC с таймкодами) пишется в отдельный тег, а
    обычный — только если его ещё нет (чтобы не затирать ручные правки).

    Returns:
        True, если текст найден и записан; иначе False.
    """
    try:
        tags = get_tags(filepath)
    except Exception:
        return False
    title = (tags.title or "").strip()
    artist = (tags.artist or "").strip()
    album = (tags.album or "").strip()
    if not title:
        return False
    if tags.lyrics_synced and tags.lyrics_synced.strip():
        return False
    try:
        lyrics = fetch_lyrics(title, artist, album)
    except Exception:
        return False
    if not lyrics:
        return False
    if getattr(lyrics, "synced_lyrics", ""):
        tags.lyrics_synced = lyrics.synced_lyrics
    if getattr(lyrics, "plain_lyrics", "") and not (tags.lyrics and tags.lyrics.strip()):
        tags.lyrics = lyrics.plain_lyrics
    if not tags.lyrics_synced and not tags.lyrics:
        return False
    try:
        ok = bool(set_tags(filepath, tags))
    except Exception:
        return False
    if ok:
        try:
            from .primuse import maybe_write_sidecars

            maybe_write_sidecars(filepath, tags)
        except Exception:
            pass
    return ok


def apply_metadata_from_sources(filepath: Path, title: str, artist: str = "",
                                thumbnail_url: str = "") -> bool:
    """Авто-применение тегов и обложки из первого найденного источника.

    Неинтерактивный вариант для пакетных флоу (Shazam): берёт первую запись
    из iTunes/Deezer, применяет её теги и обложку к файлу. Если источники
    пусты/недоступны — пробует обложку из YouTube-превью.

    Returns:
        True, если применены теги или обложка; иначе False.
    """
    from .providers import fetch_all
    from .tagger import AudioTags, apply_cover_from_url

    tags = get_tags(filepath)
    records: list = []
    try:
        results = fetch_all(title, artist)
        records = [rec for recs in results.values() for rec in recs]
    except Exception:
        records = []

    applied = False
    if records:
        rec = records[0]
        new = AudioTags(
            title=rec.title or tags.title,
            artist=rec.artist or tags.artist,
            album=rec.album or tags.album,
            year=rec.year or tags.year,
            genre=rec.genre or tags.genre,
            track_number=rec.track_number or tags.track_number,
            album_artist=rec.album_artist or tags.album_artist,
            disc_number=rec.disc_number or tags.disc_number,
            isrc=rec.isrc or tags.isrc,
            composer=rec.composer or tags.composer,
            publisher=(
                rec.publisher or rec.label or tags.publisher
            ),
            comment=tags.comment, lyrics=tags.lyrics,
            lyrics_synced=tags.lyrics_synced,
            cover_data=tags.cover_data, cover_mime=tags.cover_mime,
            copyright=getattr(tags, "copyright", ""),
        )
        if rec.cover_url:
            try:
                from .fetcher import download_cover
                new.cover_data, new.cover_mime = download_cover(rec.cover_url)
            except Exception:
                pass
        if set_tags(filepath, new):
            applied = True
        tags = new

    if not tags.cover_data and thumbnail_url:
        try:
            if apply_cover_from_url(filepath, thumbnail_url):
                applied = True
        except Exception:
            pass

    if applied:
        try:
            from .primuse import maybe_write_sidecars

            maybe_write_sidecars(filepath)
        except Exception:
            pass
    return applied


def _existing_artist_dir(output_dir: Path, artist: str) -> str | None:
    """Найти папку существующего артиста по транслит-неточному совпадению.

    Чтобы скачанный «Valentin Strykalo» лёг в уже имеющуюся папку
    «Валентин Стрыкало», а не создавал дубль-латиницу. Сравнение через
    :func:`src.ytmusic.norm` (кириллица→латиница, только буквы/цифры).
    """
    try:
        from .ytmusic import norm as norm_name
    except Exception:
        return None
    try:
        wanted = norm_name(artist)
    except Exception:
        return None
    if not wanted:
        return None
    try:
        entries = sorted(p.name for p in output_dir.iterdir() if p.is_dir())
    except OSError:
        return None
    for name in entries:
        try:
            if norm_name(name) == wanted:
                return name
        except Exception:
            continue
    return None


def _library_path(filepath: Path, output_dir: Path) -> Path:
    """Вычислить целевой путь в библиотеке (Artist/Album/Title.ext)."""
    try:
        tags = get_tags(filepath)
    except Exception:
        tags = None
    artist = (tags.artist if tags else "").strip() or "Неизвестный исполнитель"
    album = (tags.album if tags else "").strip()
    title = (tags.title if tags else "").strip() or filepath.stem

    artist_dir = _existing_artist_dir(output_dir, artist) or sanitize_name(artist)
    if album and album != artist:
        target_dir = output_dir / artist_dir / sanitize_name(album)
    else:
        target_dir = output_dir / artist_dir
    return target_dir / f"{sanitize_name(title)}{filepath.suffix}"


@dataclass(frozen=True)
class MoveToLibraryResult:
    """Typed outcome of moving an Inbox file into the library."""

    status: str
    path: Path | None = None
    error: str = ""


def move_to_library_result(filepath: Path, output_dir: Path) -> MoveToLibraryResult:
    """Переместить файл из Inbox в библиотеку по текущим тегам.

    Sidecar Primuse (.lrc + -cover.jpg) переносятся вместе с треком.

    Returns:
        ``moved`` with the target path, ``conflict`` when the target exists, or
        ``failed`` with the filesystem error. The source is retained on failure.
    """
    try:
        old_tags = get_tags(filepath)
        old_title = (old_tags.title or "").strip()
    except Exception:
        old_title = ""
    target = _library_path(filepath, output_dir)
    if _nfc(target) == _nfc(filepath):
        try:
            from .primuse import maybe_write_sidecars

            maybe_write_sidecars(filepath)
        except Exception:
            pass
        return MoveToLibraryResult("moved", filepath)
    if target.exists():
        return MoveToLibraryResult("conflict")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        os.link(filepath, target)
    except FileExistsError:
        return MoveToLibraryResult("conflict")
    except OSError as exc:
        return MoveToLibraryResult("failed", error=str(exc))
    try:
        filepath.unlink()
    except OSError as exc:
        return MoveToLibraryResult(
            "published_source_retained",
            target,
            error="published_source_retained",
        )
    try:
        from .primuse import sync_after_move

        sync_after_move(filepath, target, old_title=old_title)
    except Exception:
        pass
    return MoveToLibraryResult("moved", target)


def move_to_library(filepath: Path, output_dir: Path) -> Path | None:
    """Compatibility wrapper preserving the legacy path-or-None contract."""
    result = move_to_library_result(filepath, output_dir)
    return result.path if result.status == "moved" else None


def _nfc(s) -> str:
    import unicodedata

    return unicodedata.normalize("NFC", str(s))
