"""Batch audio compression (re-encode in place to the target format/bitrate).

Целевой формат/битрейт приходят из настроек (``default_format`` /
``default_quality``): lossy-таргеты (mp3/m4a/opus) перекодируют с указанным
битрейтом, ``flac`` — lossless без битрейта (quality игнорируется).

Идемпотентность: lossy-таргет не трогает файлы уже ниже/около целевого
битрейта (``LOSSLESS_RATIO``); lossless-таргет пропускает уже lossless
исходники (FLAC/WAV). Lossy → lossless не восстанавливает качество, но
настройка авторитетна — такие файлы остаются кандидатами.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from mutagen import File

from .tagger import get_tags, set_tags

#: A lossy file is considered "already small enough" if its bitrate is at most
#: this many times the target — leaves headroom so we don't re-compress files
#: that are essentially at target already.
LOSSLESS_RATIO = 1.2

LOSSLESS_SUFFIXES = {".flac", ".wav"}

#: Lossless-таргет: битрейт не задаётся, кодирование без потерь.
LOSSLESS_FORMAT = "flac"

#: Целевой формат → (ffmpeg codec, расширение файла). Ключи совпадают
#: со значениями ``AudioFormat`` (default_format в настройках).
FORMAT_PROFILES: dict[str, tuple[str, str]] = {
    "flac": ("flac", ".flac"),
    "mp3": ("libmp3lame", ".mp3"),
    "m4a": ("aac", ".m4a"),
    "opus": ("libopus", ".opus"),
}

#: Legacy-маппинг (когда ``target_format`` не задан): целевой формат
#: выводится из расширения исходника.
_LEGACY_TARGET_BY_SUFFIX = {
    ".flac": "mp3",
    ".wav": "mp3",
    ".mp3": "mp3",
    ".m4a": "m4a",
    ".aac": "m4a",
    ".mp4": "m4a",
}


def _is_lossless(path: Path) -> bool:
    return path.suffix.lower() in LOSSLESS_SUFFIXES


def _normalize_format(target_format: str | None) -> str | None:
    """Привести имя формата к каноническому виду (None для неизвестного)."""
    if not target_format:
        return None
    fmt = str(target_format).strip().lower()
    return fmt if fmt in FORMAT_PROFILES else None


def _target_from_source(path: Path) -> str:
    """Legacy-таргет по расширению исходника (без ``target_format``)."""
    return _LEGACY_TARGET_BY_SUFFIX.get(path.suffix.lower(), "mp3")


def read_bitrate(path: Path) -> int:
    """Return the bitrate (bps, 0 if unknown) of an audio file."""
    try:
        audio = File(str(path))
        if audio is None:
            return 0
        info = getattr(audio, "info", None)
        if info is None:
            return 0
        bitrate = int(getattr(info, "bitrate", 0) or 0)
        if not bitrate:
            bitrate = int(getattr(info, "bitrate_kbps", 0) or 0) * 1000
        return bitrate
    except Exception:
        return 0


def should_compress(
    path: Path,
    target_quality: int,
    bitrate: int | None = None,
    target_format: str | None = None,
) -> bool:
    """Return True if `path` should be re-encoded to `target_quality` kbps.

    Lossless-таргет (``flac``): lossy исходники — кандидаты (настройка
    авторитетна), уже lossless FLAC/WAV пропускаются. Lossy-таргет (или
    legacy-вызов без формата): lossless всегда кандидаты, lossy — только
    если текущий битрейт выше ``target * LOSSLESS_RATIO``.
    """
    if _normalize_format(target_format) == LOSSLESS_FORMAT:
        if _is_lossless(path):
            return False
        if bitrate is None:
            bitrate = read_bitrate(path)
        return bitrate > 0
    if _is_lossless(path):
        return True
    if bitrate is None:
        bitrate = read_bitrate(path)
    if not bitrate:
        return False
    return bitrate > int(target_quality * 1000 * LOSSLESS_RATIO)


def estimate_size(
    path: Path,
    target_quality: int,
    duration: float | None = None,
    target_format: str | None = None,
) -> int:
    """Estimate the compressed size in bytes using duration and bitrate.

    Для lossless-таргета честной оценки по битрейту нет — возвращаем 0
    (UI показывает «—»).
    """
    if _normalize_format(target_format) == LOSSLESS_FORMAT:
        return 0
    if duration is None:
        audio = File(str(path))
        if audio is None:
            return 0
        info = getattr(audio, "info", None)
        if info is None:
            return 0
        duration = float(getattr(info, "length", 0) or 0)
    if not duration:
        return 0
    return int(duration * target_quality * 1000 / 8)


def _compress_to_temp(
    path: Path,
    target_quality: int,
    codec: str,
    suffix: str,
    lossless: bool = False,
) -> Path:
    """Re-encode `path` to a temporary file with the given ffmpeg codec.

    Lossless-таргет не получает ``-b:a``: битрейт — параметр lossy-кодеков.
    ``-vn`` отключает встроенные обложки (attached pic): теги/обложку мы
    восстанавливаем сами через tagger, а ffmpeg не тратит время на их
    перекодирование и не падает на нестандартных картинках.
    """
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    tmp = Path(tmp_path)
    cmd = ["ffmpeg", "-y", "-nostdin", "-i", str(path), "-vn", "-codec:a", codec]
    if not lossless:
        cmd += ["-b:a", f"{target_quality}k"]
    cmd.append(str(tmp))
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        tmp.unlink(missing_ok=True)
        raise
    return tmp


def compress_file(
    path: Path,
    target_quality: int,
    target_format: str | None = None,
) -> Path | None:
    """Re-encode audio to `target_format` at `target_quality` kbps.

    ``target_format`` — один из flac/mp3/m4a/opus (значение ``default_format``
    из настроек); без него действует legacy-поведение (таргет по исходнику).
    Возвращает новый путь, или None если файл пропущен/не перекодировался.
    Конфликт целевого пути (смена расширения на уже существующее имя) ничего
    не затирает: исходник и существующий файл остаются как были.
    """
    if target_format is not None:
        fmt = _normalize_format(target_format)
        if fmt is None:
            # Неизвестный формат — пропускаем, а не перекодируем во что-то другое.
            return None
    else:
        fmt = _target_from_source(path)

    if not should_compress(path, target_quality, target_format=fmt):
        return None

    codec, suffix = FORMAT_PROFILES[fmt]
    tags = get_tags(path)
    try:
        tmp = _compress_to_temp(
            path, target_quality, codec, suffix,
            lossless=(fmt == LOSSLESS_FORMAT),
        )
    except Exception:
        return None

    new_path = path.with_suffix(suffix)
    try:
        same_file = new_path.exists() and new_path.samefile(path)
    except OSError:
        same_file = False

    if new_path.exists() and not same_file:
        # Целевое имя занято другим файлом — не затираем ни его, ни исходник.
        tmp.unlink(missing_ok=True)
        return None
    try:
        tmp.replace(new_path)
    except OSError:
        tmp.unlink(missing_ok=True)
        return None

    if not same_file:
        try:
            path.unlink()
        except OSError:
            pass

    try:
        set_tags(new_path, tags)
    except Exception:
        pass

    return new_path


def compress_covers(path: Path) -> bool:
    """Re-compress an embedded cover if it is larger than the thresholds.

    Returns True if the cover was re-encoded and written.
    """
    from .fetcher import _prepare_cover

    tags = get_tags(path)
    if not tags.cover_data:
        return False
    new_cover = _prepare_cover(tags.cover_data)
    if new_cover == tags.cover_data:
        return False
    tags.cover_data = new_cover
    tags.cover_mime = "image/jpeg"
    return set_tags(path, tags)
