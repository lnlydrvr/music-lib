"""YouTube search functionality using yt-dlp."""
from __future__ import annotations

import time
from dataclasses import dataclass

from yt_dlp import YoutubeDL

from .downloader import VideoInfo
from .utils import logger

#: Кэш прямых аудио-URL для превью: url -> (expires_at, direct_url).
_PREVIEW_CACHE: dict[str, tuple[float, str]] = {}
_PREVIEW_TTL = 3600.0


def _cookie_candidates() -> list[dict]:
    """Кандидаты cookie-опций (файл/браузер из конфига → safari+chrome).

    Запомненный рабочий источник ставится первым (sticky-source)."""
    from . import ytcookies as _ytc

    try:
        from .config import get_youtube_browser, get_youtube_cookies_file

        cookiefile = get_youtube_cookies_file()
        cookiefile_s = str(cookiefile) if cookiefile else None
        browser = get_youtube_browser() or None
    except Exception:
        cookiefile_s, browser = None, None
    base = _ytc.cookie_opt_candidates(browser=browser, cookiefile=cookiefile_s)
    return _ytc.preferred_first(base, _ytc.get_preferred_source())


def resolve_preview(url: str, timeout: float = 20.0) -> str:
    """Прямой URL аудио-потока для превью (с TTL-кэшем).

    Args:
        url: видео URL YouTube.
        timeout: socket-таймаут на экстракцию.

    Returns:
        Прямой URL лучшего аудио-формата.

    Raises:
        ValueError: не удалось получить поток.
    """
    from . import ytcookies as _ytc

    now = time.monotonic()
    cached = _PREVIEW_CACHE.get(url)
    if cached and cached[0] > now:
        return cached[1]

    errors: list[Exception] = []
    data = None
    last_success = False
    winning_opt: dict = {}
    for cookie_opt in _cookie_candidates():
        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
            "socket_timeout": timeout,
        }
        opts.update(cookie_opt)
        try:
            with YoutubeDL(opts) as ydl:
                data = ydl.extract_info(url, download=False)
            last_success = True
            winning_opt = cookie_opt
            break
        except Exception as e:
            errors.append(e)
            last_success = False
            continue
    if not last_success:
        raise ValueError(
            f"Не удалось получить поток: {_ytc.pick_error(errors)}"
        ) from (errors[-1] if errors else None)
    _ytc.remember_working_source(winning_opt)

    direct = (data or {}).get("url") or ""
    if not direct:
        for f in (data or {}).get("formats") or []:
            if f.get("url"):
                direct = f["url"]
                break
    if not direct:
        raise ValueError("Нет аудио-потока для превью")

    _PREVIEW_CACHE[url] = (time.monotonic() + _PREVIEW_TTL, direct)
    return direct


@dataclass
class PlaylistEntry:
    """A single entry in a playlist."""

    info: VideoInfo
    index: int


@dataclass
class SearchResult:
    """A single search result."""

    info: VideoInfo
    index: int


class YouTubeSearch:
    """Search YouTube for videos."""

    _MAX_RETRIES = 3

    def __init__(self, max_results: int = 10):
        self.max_results = max_results
        self.last_error = ""

    def search(self, query: str) -> list[SearchResult]:
        """Search YouTube for a query.

        Args:
            query: Search query string

        Returns:
            List of SearchResult objects
        """
        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "default_search": "ytsearch",
        }

        results = []

        try:
            with YoutubeDL(opts) as ydl:
                search_url = f"ytsearch{self.max_results}:{query}"
                data = ydl.extract_info(search_url, download=False)

                if data and "entries" in data:
                    for i, entry in enumerate(data["entries"], 1):
                        if entry:
                            info = VideoInfo(
                                id=entry.get("id", ""),
                                title=entry.get("title", "Unknown"),
                                duration=entry.get("duration", 0),
                                uploader=entry.get("uploader", "Unknown"),
                                thumbnail=entry.get("thumbnail"),
                                webpage_url=entry.get("url", ""),
                            )
                            results.append(SearchResult(info=info, index=i))

        except Exception as e:
            logger.warning("Ошибка поиска: %s", e)

        return results

    def fetch_playlist(self, url: str) -> list[PlaylistEntry]:
        """Extract playlist entries from a YouTube playlist URL.

        Перебирает источники cookies (safari → chrome → без cookies):
        Safari на macOS часто отдаёт пустые cookies, Chrome — запасной.

        Args:
            url: YouTube playlist URL

        Returns:
            List of PlaylistEntry objects
        """
        from . import ytcookies as _ytc

        def _extract(cookie_opt: dict) -> list[PlaylistEntry]:
            opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
            }
            opts.update(cookie_opt)
            entries = []
            with YoutubeDL(opts) as ydl:
                data = ydl.extract_info(url, download=False)
                if data and "entries" in data:
                    for i, entry in enumerate(data["entries"], 1):
                        if entry:
                            video_url = entry.get("url") or entry.get("webpage_url", "")
                            if not video_url and entry.get("id"):
                                video_url = f"https://www.youtube.com/watch?v={entry['id']}"
                            info = VideoInfo(
                                id=entry.get("id", ""),
                                title=entry.get("title", "Unknown"),
                                duration=entry.get("duration") or 0,
                                uploader=entry.get("uploader") or entry.get("channel") or "Unknown",
                                thumbnail=entry.get("thumbnail"),
                                webpage_url=video_url,
                                upload_date=entry.get("upload_date") or "",
                            )
                            entries.append(PlaylistEntry(info=info, index=i))
            return entries

        errors: list[Exception] = []

        candidates = _cookie_candidates()[: self._MAX_RETRIES]
        for attempt, cookie_opt in enumerate(candidates):
            try:
                entries = _extract(cookie_opt)
                _ytc.remember_working_source(cookie_opt)
                return entries
            except Exception as e:
                errors.append(e)
                logger.warning(
                    "Ошибка загрузки плейлиста (%s, попытка %s/%s): %s",
                    _ytc.describe_source(cookie_opt),
                    attempt + 1, len(candidates), e,
                )
                if attempt < len(candidates) - 1:
                    time.sleep(1.5 * (attempt + 1))

        self.last_error = _ytc.pick_error(errors)
        return []
