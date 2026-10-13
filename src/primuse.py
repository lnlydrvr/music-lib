"""Sidecar-файлы для плеера Primuse.

При включённой опции (``primuse_sidecar`` в конфиге) рядом с аудиофайлом
хранятся:
- ``<Title>.lrc`` — текст песни (``lyrics_synced``, fallback на ``lyrics``);
- ``<Title>-cover.jpg`` — обложка из встроенных тегов.

Имена строятся от тега ``title`` (fallback — стем файла).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from .analytics import library_files
from .config import get_primuse_sidecar
from .utils import sanitize_name


def is_enabled() -> bool:
    """Включён ли режим Primuse."""
    try:
        return bool(get_primuse_sidecar())
    except Exception:
        return False


def sidecar_paths(audio_path: Path, title: str = "") -> tuple[Path, Path]:
    """Пути .lrc и -cover.jpg рядом с аудиофайлом по тегу title."""
    base = sanitize_name((title or "").strip() or audio_path.stem)
    parent = audio_path.parent
    return parent / f"{base}.lrc", parent / f"{base}-cover.jpg"


def _resolve_tags(audio_path: Path, tags=None):
    if tags is not None:
        return tags
    from .tagger import get_tags

    return get_tags(audio_path)


def write_sidecars(audio_path: Path, tags=None) -> dict[str, list[str]]:
    """Записать .lrc и -cover.jpg рядом с треком (если режим включён).

    Returns:
        ``{"written": [пути], "skipped": [имена]}`` — пропуск, если данных нет.
    """
    if not is_enabled():
        return {"written": [], "skipped": ["disabled"]}
    try:
        tags = _resolve_tags(audio_path, tags)
    except Exception:
        return {"written": [], "skipped": ["unreadable"]}
    title = (getattr(tags, "title", "") or "").strip()
    lrc_path, cover_path = sidecar_paths(audio_path, title)
    written: list[str] = []
    skipped: list[str] = []

    lyrics = (getattr(tags, "lyrics_synced", "") or "").strip()
    if not lyrics:
        lyrics = (getattr(tags, "lyrics", "") or "").strip()
    if lyrics:
        try:
            lrc_path.write_text(lyrics + "\n", encoding="utf-8")
            written.append(str(lrc_path))
        except OSError:
            skipped.append("lrc")
    else:
        skipped.append("lrc")

    cover_data = getattr(tags, "cover_data", None)
    if cover_data:
        try:
            cover_path.write_bytes(cover_data)
            written.append(str(cover_path))
        except OSError:
            skipped.append("cover")
    else:
        skipped.append("cover")
    return {"written": written, "skipped": skipped}


def maybe_write_sidecars(audio_path: Path, tags=None) -> dict[str, list[str]]:
    """Хук после успешной записи тегов: записать sidecar, если режим включён."""
    if not is_enabled():
        return {"written": [], "skipped": []}
    try:
        return write_sidecars(audio_path, tags)
    except Exception:
        return {"written": [], "skipped": ["error"]}


def delete_sidecars(audio_path: Path, title: str = "") -> int:
    """Удалить sidecar-файлы трека. Возвращает число удалённых."""
    candidates = set()
    try:
        lrc, cover = sidecar_paths(audio_path, title)
        candidates.add(lrc)
        candidates.add(cover)
    except Exception:
        pass
    # На случай переименования title: подчистить и по стему файла.
    try:
        lrc_s, cover_s = sidecar_paths(audio_path, audio_path.stem)
        candidates.add(lrc_s)
        candidates.add(cover_s)
    except Exception:
        pass
    deleted = 0
    for path in candidates:
        try:
            if path.is_file():
                path.unlink()
                deleted += 1
        except OSError:
            pass
    return deleted


def sync_after_move(old_audio: Path, new_audio: Path, tags=None,
                    old_title: str = "") -> dict[str, list[str]]:
    """Перенести sidecar при перемещении/переименовании трека.

    Старые файлы по прежнему title/стему удаляются, у нового пути
    записываются свежие (если режим включён).
    """
    try:
        delete_sidecars(old_audio, old_title)
    except Exception:
        pass
    if not is_enabled():
        return {"written": [], "skipped": []}
    try:
        return write_sidecars(new_audio, tags)
    except Exception:
        return {"written": [], "skipped": ["error"]}


def backfill_library(output_dir: Path, on_progress: Callable | None = None) -> dict[str, int]:
    """Создать sidecar для всей библиотеки. Возвращает счётчики."""
    result = {"wrote_lrc": 0, "wrote_cover": 0, "skipped": 0, "errors": 0}
    try:
        files = library_files(output_dir)
    except Exception:
        return result
    for i, fp in enumerate(files, 1):
        if on_progress:
            try:
                on_progress(i, len(files), fp)
            except Exception:
                pass
        try:
            res = write_sidecars(fp)
        except Exception:
            result["errors"] += 1
            continue
        written = res.get("written", [])
        if not written:
            if "disabled" in res.get("skipped", []):
                return result
            result["skipped"] += 1
            continue
        for path in written:
            if path.endswith(".lrc"):
                result["wrote_lrc"] += 1
            else:
                result["wrote_cover"] += 1
    return result


def _is_cover_sidecar(path: Path) -> bool:
    name = path.name.lower()
    return name.endswith("-cover.jpg") or name.endswith("-cover.jpeg")


def _is_lrc_sidecar(path: Path) -> bool:
    return path.suffix.lower() == ".lrc"


def preview_cleanup(output_dir: Path) -> dict:
    """Посчитать sidecar-файлы без удаления (для диалога подтверждения)."""
    lrc = covers = 0
    sample: list[str] = []
    try:
        root = output_dir.resolve()
    except OSError:
        return {"lrc": 0, "covers": 0, "sample": []}
    if not output_dir.exists():
        return {"lrc": 0, "covers": 0, "sample": []}
    try:
        entries = sorted(root.rglob("*"))
    except OSError:
        return {"lrc": 0, "covers": 0, "sample": []}
    for path in entries:
        try:
            if not path.is_file():
                continue
        except OSError:
            continue
        if _is_lrc_sidecar(path):
            lrc += 1
            if len(sample) < 10:
                sample.append(str(path))
        elif _is_cover_sidecar(path):
            covers += 1
            if len(sample) < 10:
                sample.append(str(path))
    return {"lrc": lrc, "covers": covers, "sample": sample}


def cleanup_library(output_dir: Path) -> dict[str, int]:
    """Удалить все *.lrc и *-cover.jpg в библиотеке (включая Inbox)."""
    result = {"deleted_lrc": 0, "deleted_covers": 0, "errors": 0}
    try:
        root = output_dir.resolve()
    except OSError:
        return result
    if not output_dir.exists():
        return result
    try:
        entries = sorted(root.rglob("*"))
    except OSError:
        return result
    for path in entries:
        try:
            if not path.is_file():
                continue
            try:
                path.resolve().relative_to(root)
            except ValueError:
                continue
        except OSError:
            result["errors"] += 1
            continue
        is_lrc = _is_lrc_sidecar(path)
        is_cover = _is_cover_sidecar(path)
        if not (is_lrc or is_cover):
            continue
        try:
            path.unlink()
            if is_lrc:
                result["deleted_lrc"] += 1
            else:
                result["deleted_covers"] += 1
        except OSError:
            result["errors"] += 1
    return result
