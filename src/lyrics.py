"""Fetch song lyrics from LRCLIB (lrclib.net)."""
from __future__ import annotations

import urllib.request
import urllib.parse
import json
import time
import threading
from dataclasses import dataclass

from .utils import logger


USER_AGENT = "music-lib/0.1.0"
BASE_URL = "https://lrclib.net"
_NOT_FOUND = object()
_CACHE_TTL = 300.0
_cache: dict[tuple[str, str, str, int], tuple[float, LyricsResult | None]] = {}
_cache_lock = threading.Lock()
_request_lock = threading.Lock()


@dataclass
class LyricsResult:
    """Lyrics fetched from LRCLIB."""

    track_name: str = ""
    artist_name: str = ""
    album_name: str = ""
    duration: int = 0
    plain_lyrics: str = ""
    synced_lyrics: str = ""


def _request(url: str, retries: int = 2, timeout: int = 15,
             return_not_found: bool = False) -> dict | list | object | None:
    """Make a request with retries and rate-limit handling."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    # Один общий gate: параллельные batch-запросы не превращают cache-miss в
    # burst, а Retry-After удерживает следующие запросы до конца cooldown.
    with _request_lock:
        for attempt in range(retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    if attempt >= retries:
                        logger.warning("Ошибка API: %s", e)
                        return None
                    try:
                        retry_after = max(0, int(e.headers.get("Retry-After", 5)))
                    except (TypeError, ValueError):
                        retry_after = 5
                    time.sleep(retry_after)
                    continue
                if e.code == 404:
                    return _NOT_FOUND if return_not_found else None
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                logger.warning("Ошибка API: %s", e)
                return None
            except Exception as e:
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                logger.warning("Ошибка API: %s", e)
                return None
    return None


def fetch_lyrics(
    track_name: str,
    artist_name: str = "",
    album_name: str = "",
    duration: int = 0,
) -> LyricsResult | None:
    """Fetch lyrics by track metadata (exact match via /api/get).

    Args:
        track_name: Track title (required)
        artist_name: Artist name (recommended)
        album_name: Album name (optional, improves match)
        duration: Duration in seconds (optional, improves match)

    Returns:
        LyricsResult or None if not found
    """
    key = (track_name, artist_name, album_name, int(duration or 0))
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and cached[0] > now:
            return cached[1]
        if cached:
            del _cache[key]

    params: dict[str, str | int] = {"track_name": track_name}
    if artist_name:
        params["artist_name"] = artist_name
    if album_name:
        params["album_name"] = album_name
    if duration:
        params["duration"] = duration

    url = f"{BASE_URL}/api/get?{urllib.parse.urlencode(params)}"
    data = _request(url, return_not_found=True)
    if data is _NOT_FOUND:
        with _cache_lock:
            _cache[key] = (now + _CACHE_TTL, None)
        return None
    if not data or not isinstance(data, dict) or data.get("instrumental"):
        return None

    result = LyricsResult(
        track_name=data.get("trackName", ""),
        artist_name=data.get("artistName", ""),
        album_name=data.get("albumName", ""),
        duration=data.get("duration", 0),
        plain_lyrics=data.get("plainLyrics") or "",
        synced_lyrics=data.get("syncedLyrics") or "",
    )
    with _cache_lock:
        _cache[key] = (now + _CACHE_TTL, result)
    return result
