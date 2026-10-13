"""Сервисный слой операций над библиотекой.

Чистые функции без rich/console-вывода: сортировка в Artist/Album,
группировка дубликатов, пакетное обновление текстов, применение метаданных
из источников. Используется API-роутами Web UI.
"""
from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path

from .analytics import library_files
from .config import inbox_dir
from .lyrics import fetch_lyrics
from .tagger import AudioTags, Tagger, get_tags, set_tags
from .utils import sanitize_name

#: Системные/временные файлы-мусор (macOS), не влияющие на «пустоту» папки.
JUNK_FILES = {".DS_Store", "Thumbs.db", "desktop.ini", ".DS_Store.lock"}


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# --- Сортировка -------------------------------------------------------


def _sort_target(output_dir: Path, filepath: Path, tags: AudioTags) -> Path:
    """Целевой путь файла в структуре Artist/Album (без сторонних эффектов)."""
    artist = (tags.artist or "").strip() or "Неизвестный исполнитель"
    album = (tags.album or "").strip()
    title = (tags.title or filepath.stem).strip()
    if album and album != artist:
        target_dir = output_dir / sanitize_name(artist) / sanitize_name(album)
    else:
        target_dir = output_dir / sanitize_name(artist)
    return target_dir / f"{sanitize_name(title)}{filepath.suffix}"


def plan_sort_library(output_dir: Path) -> list[tuple[Path, Path]]:
    """План раскладки по папкам: пары (откуда, куда) без перемещения.

    Та же логика цели, что у ``sort_library``; файлы уже на месте и
    конфликты «цель занята» в план не попадают.
    """
    plan: list[tuple[Path, Path]] = []
    for filepath in library_files(output_dir):
        try:
            tags = get_tags(filepath)
        except Exception:
            continue
        target = _sort_target(output_dir, filepath, tags)
        if _nfc(str(filepath)) == _nfc(str(target)):
            continue
        if target.exists():
            continue
        plan.append((filepath, target))
    return plan


def sort_library(output_dir: Path) -> tuple[int, int]:
    """Разложить файлы по Artist/Album и удалить пустые папки.

    Returns:
        (перемещено, удалено папок)
    """
    moved = 0
    for filepath in library_files(output_dir):
        try:
            tags = get_tags(filepath)
        except Exception:
            continue
        target = _sort_target(output_dir, filepath, tags)
        if _nfc(str(filepath)) == _nfc(str(target)):
            try:
                from .primuse import maybe_write_sidecars

                maybe_write_sidecars(filepath, tags)
            except Exception:
                pass
            continue
        if target.exists():
            continue
        old_title = (tags.title or "").strip()
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            filepath.rename(target)
            moved += 1
            try:
                from .primuse import sync_after_move

                sync_after_move(filepath, target, tags=tags, old_title=old_title)
            except Exception:
                pass
        except OSError:
            pass
    removed = delete_empty_dirs(output_dir)
    return moved, removed


def delete_empty_dirs(output_dir: Path) -> int:
    """Удалить пустые папки библиотеки (не трогая Inbox и корень).

    Папка считается пустой, если в ней нет ничего, кроме «мусорных» файлов
    (.DS_Store и т.п.), которые удаляются вместе с папкой.
    """
    removed = 0
    inbox = inbox_dir(output_dir)
    dirs = sorted(
        (p for p in output_dir.rglob("*") if p.is_dir()
         and not any(part.startswith(".") for part in p.relative_to(output_dir).parts)),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for path in dirs:
        if path == output_dir or path == inbox or inbox in path.parents:
            continue
        try:
            entries = list(path.iterdir())
        except OSError:
            continue
        real = [e for e in entries if e.name not in JUNK_FILES]
        if real:
            continue
        for e in entries:
            try:
                if e.is_file():
                    e.unlink()
            except OSError:
                pass
        try:
            path.rmdir()
            removed += 1
        except OSError:
            pass
    return removed


# --- Дедупликация ------------------------------------------------------


def dedup_groups(mode: str, output_dir: Path) -> list[list[Path]]:
    """Группы дубликатов (все файлы группы). mode: ``md5`` | ``semantic``.

    Дубликаты ищутся по всей библиотеке вместе с ``Inbox`` — в Inbox обычно
    лежат свежескачанные копии треков, которые уже есть в библиотеке.
    """
    if mode == "md5":
        return _md5_groups(output_dir)
    return _semantic_groups(output_dir)


def best_in_group(paths: list[Path], mode: str) -> Path:
    """Лучший файл в дубликатной группе (остальные — кандидаты на удаление)."""
    if mode == "md5":
        return max(paths, key=lambda p: p.stat().st_size if p.exists() else 0)
    return max(paths, key=_tag_score)


def dedup_label(path: Path) -> str:
    try:
        tags = get_tags(path)
        title = tags.title or path.stem
        artist = tags.artist or "—"
    except Exception:
        title, artist = path.stem, "—"
    return f"{title}  ·  {artist}  ·  {path.name}"


def _md5_groups(output_dir: Path) -> list[list[Path]]:
    groups: dict[str, list[Path]] = {}
    for fp in library_files(output_dir, include_inbox=True):
        try:
            h = hashlib.md5()
            with open(fp, "rb") as f:
                while chunk := f.read(8192):
                    h.update(chunk)
            groups.setdefault(h.hexdigest(), []).append(fp)
        except Exception:
            pass
    return [paths for paths in groups.values() if len(paths) > 1]


_SEM_STOP = {
    "the", "a", "an", "and", "or", "of", "in", "on", "for", "to", "at", "with",
    "feat", "featuring", "ft", "vs", "remastered", "remaster", "single", "mix", "remix",
    "version", "edit", "live", "acoustic", "demo", "bonus", "track", "radio",
    "more", "love", "time", "world", "night", "day", "dance", "rock", "pop",
    "music", "white", "black", "red", "green", "blue", "gold", "silver",
}


def _tokenize(s: str) -> frozenset[str]:
    text = _nfc(s or "").lower()
    for ch in "_-—–/\\()[]{},.;:'\"!?&|+*":
        text = text.replace(ch, " ")
    return frozenset(t for t in text.split()
                     if len(t) > 1 and t not in _SEM_STOP)


def _tokens_overlap(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _semantic_groups(output_dir: Path) -> list[list[Path]]:
    records: list[tuple[frozenset[str], Path]] = []
    for fp in library_files(output_dir, include_inbox=True):
        try:
            tags = get_tags(fp)
        except Exception:
            continue
        title_tok = _tokenize(tags.title or fp.stem)
        if title_tok:
            records.append((title_tok, fp))

    def is_dup(a: tuple[frozenset[str], Path], b: tuple[frozenset[str], Path]) -> bool:
        return _tokens_overlap(a[0], b[0]) >= 0.66

    parent = list(range(len(records)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            if is_dup(records[i], records[j]):
                union(i, j)

    groups: dict[int, list[Path]] = {}
    for i, (_, fp) in enumerate(records):
        groups.setdefault(find(i), []).append(fp)
    return [paths for paths in groups.values() if len(paths) > 1]


def _tag_score(path: Path) -> int:
    score = 0
    try:
        tags = get_tags(path)
        for val in (tags.title, tags.artist, tags.album, tags.album_artist,
                    tags.year, tags.genre, tags.track_number, tags.isrc):
            if val:
                score += 1
        if tags.cover_data:
            score += 2
        if tags.lyrics and tags.lyrics.strip():
            score += 1
    except Exception:
        pass
    try:
        score += path.stat().st_size
    except Exception:
        pass
    return score


# --- Тексты ------------------------------------------------------------


def _lyrics_fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def collect_lyrics_candidates(output_dir: Path) -> tuple[list[dict], int, int]:
    """Собрать треки без LRC без полного analytics-сканирования."""
    candidates: list[dict] = []
    errors = 0
    files = library_files(output_dir)
    for filepath in files:
        try:
            tagger = Tagger(filepath)
            tags = tagger.read()
            duration = int(getattr(getattr(tagger._file, "info", None), "length", 0) or 0)
            fingerprint = _lyrics_fingerprint(filepath)
        except Exception:
            errors += 1
            continue
        if ((tags.lyrics_synced and tags.lyrics_synced.strip())
                or (tags.lyrics and tags.lyrics.strip())):
            continue
        candidates.append({
            "path": str(filepath),
            "title": (tags.title or "").strip(),
            "artist": (tags.artist or "").strip(),
            "album": (tags.album or "").strip(),
            "duration": duration,
            "has_plain": bool(tags.lyrics and tags.lyrics.strip()),
            "fingerprint": fingerprint,
        })
    return candidates, errors, len(files)


def update_all_lyrics(output_dir: Path, on_progress=None,
                      candidates: list[dict] | None = None) -> dict[str, int]:
    """Загрузить синхронные тексты (LRC) для треков без них через LRCLIB.

    Обрабатывает треки, у которых нет синхронизированного текста; обычный
    текст записывается только если его ещё нет. ``on_progress(i, total, path)``
    вызывается перед обработкой каждого файла.

    Returns:
        ``{"updated": int, "skipped": int, "has_lyrics": int, "errors": int}``
    """
    if candidates is None:
        candidates, _errors, _total = collect_lyrics_candidates(output_dir)
    result = {"updated": 0, "skipped": 0, "has_lyrics": 0, "errors": 0}

    for i, candidate in enumerate(candidates, 1):
        filepath = Path(str(candidate.get("path") or ""))
        if on_progress:
            on_progress(i, len(candidates), filepath)
        try:
            if not filepath.is_relative_to(output_dir):
                result["skipped"] += 1
                continue
            tags = get_tags(filepath)
        except Exception:
            result["errors"] += 1
            continue

        title = (tags.title or "").strip()
        artist = (tags.artist or "").strip()
        if not title:
            result["skipped"] += 1
            continue
        if ((tags.lyrics_synced and tags.lyrics_synced.strip())
                or (tags.lyrics and tags.lyrics.strip())):
            result["has_lyrics"] += 1
            continue
        try:
            if _lyrics_fingerprint(filepath) != candidate.get("fingerprint"):
                result["skipped"] += 1
                continue
        except Exception:
            result["errors"] += 1
            continue

        duration = int(candidate.get("duration") or 0)

        try:
            lyrics = fetch_lyrics(title, artist, (tags.album or "").strip(), duration)
        except Exception:
            result["errors"] += 1
            continue
        if lyrics and (getattr(lyrics, "synced_lyrics", "") or getattr(lyrics, "plain_lyrics", "")):
            try:
                tags = get_tags(filepath)
                if ((tags.lyrics_synced and tags.lyrics_synced.strip())
                        or (tags.lyrics and tags.lyrics.strip())):
                    result["has_lyrics"] += 1
                    continue
                if _lyrics_fingerprint(filepath) != candidate.get("fingerprint"):
                    result["skipped"] += 1
                    continue
            except Exception:
                result["errors"] += 1
                continue
            if getattr(lyrics, "synced_lyrics", ""):
                tags.lyrics_synced = lyrics.synced_lyrics
            if getattr(lyrics, "plain_lyrics", "") and not (tags.lyrics and tags.lyrics.strip()):
                tags.lyrics = lyrics.plain_lyrics
            if set_tags(filepath, tags):
                result["updated"] += 1
                try:
                    from .primuse import maybe_write_sidecars

                    maybe_write_sidecars(filepath, tags)
                except Exception:
                    pass
            else:
                result["errors"] += 1
        else:
            result["skipped"] += 1
    return result


# --- Метаданные из источников -------------------------------------------


def apply_meta_fields(
    path: Path,
    fields: dict[str, str],
    source: str = "",
    cover_url: str = "",
    thumbnail_url: str = "",
) -> AudioTags | None:
    """Применить выбранные поля тегов из источника к файлу.

    Аналог ``MetaFetch._on_tags``: берёт только принятые поля
    (``fields``), сохраняет текущие для остальных, подтягивает обложку
    из ``cover_url`` (фолбэк — ``thumbnail_url``).

    Returns:
        Новые теги при успехе, иначе None.
    """
    try:
        current = get_tags(path)
    except Exception:
        return None

    cover_data = current.cover_data
    cover_mime = current.cover_mime
    try:
        if cover_url:
            from .fetcher import download_cover
            cover_data, cover_mime = download_cover(cover_url)
    except Exception:
        pass
    if not cover_data and thumbnail_url:
        try:
            from .tagger import apply_cover_from_url
            # Записываем обложку сразу, чтобы вернуть корректный AudioTags.
            apply_cover_from_url(path, thumbnail_url)
            current = get_tags(path)
            cover_data, cover_mime = current.cover_data, current.cover_mime
        except Exception:
            pass

    new = AudioTags(
        title=fields.get("title", current.title),
        artist=fields.get("artist", current.artist),
        album=fields.get("album", current.album),
        year=fields.get("year", current.year),
        genre=fields.get("genre", current.genre),
        track_number=fields.get("track_number", current.track_number),
        album_artist=fields.get("album_artist", current.album_artist),
        disc_number=fields.get("disc_number", current.disc_number),
        isrc=fields.get("isrc", current.isrc),
        composer=fields.get("composer", current.composer),
        publisher=(fields.get("publisher", "") or fields.get("label", "")
                   or current.publisher),
        comment=current.comment, lyrics=current.lyrics,
        lyrics_synced=current.lyrics_synced,
        copyright=current.copyright,
        cover_data=cover_data, cover_mime=cover_mime,
    )
    if set_tags(path, new):
        try:
            from .primuse import maybe_write_sidecars

            maybe_write_sidecars(path, new)
        except Exception:
            pass
        return new
    return None
