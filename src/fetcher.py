"""Fetch music metadata from Deezer."""
from __future__ import annotations

import json
import os
import random
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .utils import logger


USER_AGENT = "music-lib/0.1.0"

#: Covers smaller than this (bytes) are considered already-compressed and skipped.
COVER_BYTE_THRESHOLD = 60 * 1024

#: Кэш скачанных обложек по URL: повторное сохранение трека или соседних
#: треков альбома (пакетный редактор) не должно заново качать картинку
#: и гонять ffmpeg-сжатие. TTL консервативный, картинки не меняются.
_COVER_CACHE: dict[str, tuple[float, tuple[bytes, str]]] = {}
_COVER_CACHE_TTL = 30 * 60.0
_COVER_CACHE_LIMIT = 64
_COVER_CACHE_LOCK = threading.Lock()

#: Кэш ответов альбомных эндпоинтов Deezer по album_id: в выдаче поиска все
#: результаты обычно одного альбома, а массовое редактирование идёт по трекам
#: того же альбома — без кэша каждый раз качается одно и то же.
_ALBUM_INFO_CACHE: dict[str, tuple[str, str, str, str]] = {}
_ALBUM_TRACKS_CACHE: dict[str, dict] = {}
_ALBUM_CACHE_LIMIT = 512


def clear_deezer_album_cache() -> None:
    """Сбросить кэш альбомных запросов (для тестов и смены окружения)."""
    _ALBUM_INFO_CACHE.clear()
    _ALBUM_TRACKS_CACHE.clear()


@dataclass
class FetchedTags:
    """Tags fetched from Deezer."""

    title: str = ""
    artist: str = ""
    album: str = ""
    year: str = ""
    genre: str = ""
    track_number: str = ""
    album_artist: str = ""
    cover_url: str = ""
    disc_number: str = ""
    isrc: str = ""
    composer: str = ""
    label: str = ""
    copyright: str = ""
    duration: str = ""
    rank: str = ""
    explicit_lyrics: str = ""


def _retry_after_delay(e: urllib.error.HTTPError) -> float:
    """Пауза по ``Retry-After`` (сек): минимум 5, потолок 30 + джиттер."""
    try:
        delay = float(e.headers.get("Retry-After") or 0)
    except (TypeError, ValueError):
        delay = 0.0
    return min(max(delay, 5.0), 30.0) + random.uniform(0.0, 0.5)


def _request(url: str, retries: int = 2, timeout: int = 15) -> dict | None:
    """Make a request with retries; HTTP 429 waits ``Retry-After`` (up to 4 times)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ru"})
    attempt = 0
    waits_429 = 0
    while True:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and waits_429 < 4:
                waits_429 += 1
                time.sleep(_retry_after_delay(e))
                continue
            if attempt < retries:
                attempt += 1
                time.sleep(1.5 * attempt)
                continue
            logger.warning("Ошибка API: %s", e)
            return None
        except Exception as e:
            if attempt < retries:
                attempt += 1
                time.sleep(1.5 * attempt)
                continue
            logger.warning("Ошибка API: %s", e)
            return None


def _get_deezer_album_info(album_id: str | int) -> tuple[str, str, str, str]:
    """Get genre, year, label and copyright from Deezer album endpoint.

    Returns:
        (genre, year, label, copyright) tuple
    """
    if not album_id:
        return "", "", "", ""
    key = str(album_id)
    cached = _ALBUM_INFO_CACHE.get(key)
    if cached is not None:
        return cached
    url = f"https://api.deezer.com/album/{album_id}"
    data = _request(url, timeout=10)
    if not data:
        return "", "", "", ""
    genres = data.get("genres", {}).get("data", [])
    genre = genres[0].get("name", "") if genres else ""
    release_date = data.get("release_date", "")
    year = release_date[:4] if release_date else ""
    label = data.get("label", "")
    copyright = data.get("copyright", "")
    info = (genre, year, label, copyright)
    if len(_ALBUM_INFO_CACHE) >= _ALBUM_CACHE_LIMIT:
        _ALBUM_INFO_CACHE.clear()
    _ALBUM_INFO_CACHE[key] = info
    return info


def _get_deezer_track_number(album_id: str | int, track_title: str) -> str:
    """Get track position from Deezer album tracklist."""
    if not album_id or not track_title:
        return ""
    key = str(album_id)
    data = _ALBUM_TRACKS_CACHE.get(key)
    if data is None:
        url = f"https://api.deezer.com/album/{album_id}/tracks"
        data = _request(url, timeout=10) or {}
        if len(_ALBUM_TRACKS_CACHE) >= _ALBUM_CACHE_LIMIT:
            _ALBUM_TRACKS_CACHE.clear()
        _ALBUM_TRACKS_CACHE[key] = data
    if not data.get("data"):
        return ""
    title_lower = track_title.lower()
    for t in data["data"]:
        t_title = (t.get("title") or "").lower()
        if title_lower in t_title or t_title in title_lower:
            return str(t.get("track_position") or "")
    return ""


def search_deezer(title: str, artist: str = "") -> list[dict]:
    """Search Deezer for tracks by title and artist.

    Args:
        title: Track title
        artist: Artist name

    Returns:
        List of raw track dicts from Deezer API (up to 5)
    """
    query = f"{artist} {title}".strip() if artist else title
    params = {"q": query, "limit": "5"}
    url = f"https://api.deezer.com/search?{urllib.parse.urlencode(params)}"
    data = _request(url, timeout=10)
    if not data or not data.get("data"):
        return []
    return data["data"]


def search_deezer_artist(artist: str) -> dict | None:
    """Найти исполнителя в Deezer (первое совпадение) или None."""
    if not artist:
        return None
    params = {"q": artist.strip(), "limit": "1"}
    url = f"https://api.deezer.com/search/artist?{urllib.parse.urlencode(params)}"
    data = _request(url, timeout=10)
    if not data or not data.get("data"):
        return None
    return data["data"][0]


def deezer_artist_radio(artist: str, title: str = "", limit: int = 10) -> list[dict]:
    """Похожие треки артиста через Deezer ``artist/{id}/radio``.

    Отдаёт кандидатов с готовыми превью (30с), обложкой и альбомом.
    Может использоваться как альтернативный источник рекомендаций.

    Args:
        artist: имя исполнителя (запрос в Deezer).
        title: не используется, оставлен для единообразия интерфейса.
        limit: сколько треков запросить.

    Returns:
        Список словарей ``{name, artist: {name}, url, preview_url, cover_url, album}``.
    """
    found = search_deezer_artist(artist)
    if not found or not found.get("id"):
        return []
    url = f"https://api.deezer.com/artist/{found['id']}/radio?limit={limit}"
    data = _request(url, timeout=10)
    if not data or not data.get("data"):
        return []
    out: list[dict] = []
    for t in data["data"]:
        name = (t.get("title") or "").strip()
        art = ((t.get("artist") or {}).get("name") or "").strip()
        if not name or not art:
            continue
        album = t.get("album") or {}
        cover = (album.get("cover_medium") or album.get("cover_small") or "")
        out.append({
            "name": name,
            "artist": {"name": art},
            "url": (t.get("link") or "").strip(),
            "preview_url": (t.get("preview") or "").strip(),
            "cover_url": cover,
            "album": (album.get("title") or "").strip(),
        })
    return out


def _cover_cache_get(url: str) -> tuple[bytes, str] | None:
    with _COVER_CACHE_LOCK:
        hit = _COVER_CACHE.get(url)
        if not hit:
            return None
        ts, data = hit
        if time.monotonic() - ts > _COVER_CACHE_TTL:
            _COVER_CACHE.pop(url, None)
            return None
        return data


def _cover_cache_put(url: str, data: tuple[bytes, str]) -> None:
    with _COVER_CACHE_LOCK:
        if len(_COVER_CACHE) >= _COVER_CACHE_LIMIT:
            _COVER_CACHE.clear()
        _COVER_CACHE[url] = (time.monotonic(), data)


def download_cover(url: str) -> tuple[bytes, str]:
    """Download cover image from URL.

    Results are cached by URL: повторные сохранения того же альбома бьют в кэш,
    а не в сеть.

    Returns:
        (image_bytes, mime_type) tuple
    """
    cached = _cover_cache_get(url)
    if cached is not None:
        return cached
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()
    mime = "image/jpeg"
    if url.lower().endswith(".png"):
        mime = "image/png"
    result = (_prepare_cover(data), mime)
    _cover_cache_put(url, result)
    return result


def download_thumbnail(url: str) -> tuple[bytes, str]:
    """Download an image and pad it to a 1:1 square.

    Used for YouTube thumbnails, which are not square (16:9 / 4:3).
    Always returns JPEG bytes.
    """
    data, _ = download_cover(url)
    return _prepare_cover(_square_image(data)), "image/jpeg"


def _prepare_cover(data: bytes, max_side: int = 800, quality: int = 5) -> bytes:
    """Resize/compress a cover image to keep embedded artwork small.

    Idempotent: images already within ``max_side`` px on the longest side OR
    smaller than :const:`COVER_BYTE_THRESHOLD` are returned unchanged. Returns
    JPEG bytes via ffmpeg; on any error the original bytes are returned.
    """
    if len(data) <= COVER_BYTE_THRESHOLD:
        return data
    width, height = _image_size(data)
    if not width or not height:
        return data
    if max(width, height) <= max_side:
        return data

    suffix = ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
        tmp_in.write(data)
        in_path = tmp_in.name
    out_path = in_path + ".cover.jpg"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-nostdin", "-i", in_path,
             "-vf", f"scale='min({max_side},iw)':'min({max_side},ih)':force_original_aspect_ratio=decrease",
             "-q:v", str(quality), out_path],
            check=True,
            capture_output=True,
        )
        with open(out_path, "rb") as f:
            return f.read()
    except Exception:
        return data
    finally:
        for path in (in_path, out_path):
            try:
                os.unlink(path)
            except OSError:
                pass


def _square_image(data: bytes) -> bytes:
    """Fit an image into a 1:1 square using ffmpeg.

    The background is the image itself, blurred and cropped to fill the
    square (YouTube Music style); the sharp image is overlaid on top,
    centered, in its original aspect ratio. If the image is already
    square, or ffmpeg is unavailable/errors, the original bytes are
    returned unchanged.
    """
    width, height = _image_size(data)
    if not width or not height or width == height:
        return data

    size = max(width, height)
    suffix = ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
        tmp_in.write(data)
        in_path = tmp_in.name
    out_path = in_path + ".square.jpg"
    try:
        filter_complex = (
            f"[0:v]split[a][b];"
            f"[a]scale={size}:{size}:force_original_aspect_ratio=increase,"
            f"crop={size}:{size},"
            f"boxblur=luma_radius={size // 10}:luma_power=1:"
            f"chroma_radius={size // 20}:chroma_power=1,"
            f"eq=brightness=-0.15[bg];"
            f"[b]scale={size}:{size}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )
        subprocess.run(
            ["ffmpeg", "-y", "-nostdin", "-i", in_path,
             "-filter_complex", filter_complex, "-q:v", "2", out_path],
            check=True,
            capture_output=True,
        )
        with open(out_path, "rb") as f:
            return f.read()
    except Exception:
        return data
    finally:
        for path in (in_path, out_path):
            try:
                os.unlink(path)
            except OSError:
                pass


def _image_size(data: bytes) -> tuple[int | None, int | None]:
    """Probe image dimensions with ffprobe."""
    suffix = ".png" if data[:8] == b"\x89PNG\r\n\x1a\n" else ".jpg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
        tmp_in.write(data)
        in_path = tmp_in.name
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "json", in_path],
            check=True,
            capture_output=True,
        )
        info = json.loads(proc.stdout.decode())
        stream = info.get("streams", [{}])[0]
        return stream.get("width"), stream.get("height")
    except Exception:
        return None, None
    finally:
        try:
            os.unlink(in_path)
        except OSError:
            pass


def fetch_tags(
    title: str, artist: str = "", album: str = "", track_data: dict | None = None
) -> FetchedTags | None:
    """Fetch full metadata for a track from Deezer.

    Args:
        title: Track title (fallback if track_data not provided)
        artist: Artist name (fallback if track_data not provided)
        album: Album name (optional)
        track_data: Raw track dict from Deezer search results.
                    If provided, skips the search step.

    Returns:
        FetchedTags or None if not found
    """
    best = track_data
    if not best:
        results = search_deezer(title, artist)
        if not results:
            return None
        best = results[0]

    # Get track ID for detailed info
    track_id = best.get("id")
    album_info = best.get("album", {})
    cover_url = album_info.get("cover_xl") or album_info.get("cover_big") or ""
    album_id = album_info.get("id", "")

    # Три независимых запроса (детали трека, альбом, треклист) — параллельно.
    with ThreadPoolExecutor(max_workers=3) as ex:
        f_track = (ex.submit(_request, f"https://api.deezer.com/track/{track_id}",
                             timeout=10)
                   if track_id else None)
        f_album = ex.submit(_get_deezer_album_info, album_id)
        f_number = ex.submit(_get_deezer_track_number, album_id, best.get("title", title))
        track_detail = f_track.result() if f_track else None
        genre, year, label, copyright = f_album.result()
        track_number = f_number.result()

    # Extract ISRC and disc_number from track detail
    isrc = ""
    disc_number = ""
    duration = ""
    rank = ""
    explicit_lyrics = ""
    composer = ""
    if track_detail:
        isrc = track_detail.get("isrc") or ""
        disc_number = track_detail.get("disk_number")
        disc_number = str(disc_number) if disc_number else ""
        duration = track_detail.get("duration")
        duration = str(duration) if duration else ""
        rank = track_detail.get("rank")
        rank = str(rank) if rank else ""
        explicit_lyrics = track_detail.get("explicit_lyrics", False)
        explicit_lyrics = "Да" if explicit_lyrics else ""

        # Extract composer from contributors
        contributors = track_detail.get("contributors", [])
        composers = [
            c.get("name", "")
            for c in contributors
            if c.get("role") == "Composer" and c.get("name")
        ]
        composer = ", ".join(composers) if composers else ""

    return FetchedTags(
        title=best.get("title", title),
        artist=best.get("artist", {}).get("name", artist),
        album=album_info.get("title", ""),
        year=year,
        genre=genre,
        track_number=track_number,
        album_artist=best.get("artist", {}).get("name", ""),
        cover_url=cover_url,
        disc_number=disc_number,
        isrc=isrc,
        composer=composer,
        label=label,
        copyright=copyright,
        duration=duration,
        rank=rank,
        explicit_lyrics=explicit_lyrics,
    )
