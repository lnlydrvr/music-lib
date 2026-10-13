"""Shared utility functions."""
from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path

#: Logger for internal diagnostics. Goes to stderr, so it never corrupts the
#: rich TUI output rendered to stdout.
logger = logging.getLogger("music-lib")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.WARNING)

# YouTube channel suffixes to strip from artist names.
# Ordered longest-first so "- Topic Audio" matches before "- Topic".
_YT_SUFFIXES = [
    "- Topic Audio",
    "- Official Audio",
    "- Topic",
    "- VEVO",
    "- Official",
    "- Music",
    "- Records",
    "- Audio",
    "Topic",
    "VEVO",
    "Official",
]


def clean_artist_name(name: str) -> str:
    """Remove YouTube channel suffixes like '- Topic', 'VEVO', etc.

    Examples:
        >>> clean_artist_name("Pink Floyd - Topic")
        'Pink Floyd'
        >>> clean_artist_name("Radiohead VEVO")
        'Radiohead'
        >>> clean_artist_name("Some Artist - Official Audio")
        'Some Artist'
        >>> clean_artist_name("Normal Artist")
        'Normal Artist'
    """
    cleaned = name.strip()
    for suffix in _YT_SUFFIXES:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    return cleaned.strip() or name


def sanitize_name(name: str) -> str:
    """Sanitize folder/file name by removing invalid characters."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "_")
    return name.strip() or "Unknown"


def nfc_path(path) -> Path:
    """Нормализовать путь в NFC (независимо от macOS NFD на диске).

    macOS хранит многие юникод-символы (напр. ペ) в декомпозированной форме NFD,
    а теги возвращают NFC. Приводим обе стороны к NFC для корректного сравнения.
    """
    if isinstance(path, Path):
        parts = [unicodedata.normalize("NFC", p) for p in path.parts]
        return Path(*parts)
    return Path(unicodedata.normalize("NFC", str(path)))
