"""Wrapper around yt-dlp for downloading audio."""
from __future__ import annotations

import enum
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from yt_dlp import YoutubeDL

from .config import resolve_output_dir, inbox_dir
from .utils import sanitize_name, logger


class AudioFormat(enum.Enum):
    """Supported audio formats."""

    FLAC = "flac"
    MP3 = "mp3"
    AAC = "m4a"
    OPUS = "opus"

    @classmethod
    def all(cls) -> list[str]:
        return [fmt.value for fmt in cls]

    @classmethod
    def source_selector(cls, source: str | None) -> str:
        """Формат-селектор yt-dlp для исходного аудиопотока.

        ``opus`` — берём нативный Opus (251); если его нет, падаем на лучший
        m4a, затем на любой лучший аудиопоток. ``m4a`` — наоборот, сначала
        m4a (AAC), затем любой лучший. ``None`` — старое поведение
        (``bestaudio/best``).
        """
        if source == "opus":
            return "bestaudio[acodec=opus]/bestaudio[ext=m4a]/bestaudio/best"
        if source == "m4a":
            return "bestaudio[ext=m4a]/bestaudio/best"
        return "bestaudio/best"

    @classmethod
    def ydl_opts(
        cls,
        fmt: str,
        quality: int | None = None,
        source: str | None = None,
    ) -> dict[str, Any]:
        """Get yt-dlp options for a specific format.

        Args:
            fmt: Output format (flac, mp3, m4a, opus)
            quality: Target bitrate in kbps (ignored for lossless FLAC).
            source: Предпочитаемый исходный поток (``opus``/``m4a``/``None``).
        """
        base = {
            "format": cls.source_selector(source),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": fmt,
                }
            ],
        }
        if quality and fmt != cls.FLAC.value:
            base["postprocessors"][0]["preferredquality"] = str(quality)
        return base


@dataclass
class VideoInfo:
    """Metadata about a video/audio."""

    id: str
    title: str
    duration: int
    uploader: str
    thumbnail: str | None = None
    webpage_url: str = ""
    description: str = ""
    upload_date: str = ""
    view_count: int = 0

    @classmethod
    def from_ydl(cls, data: dict[str, Any]) -> VideoInfo:
        return cls(
            id=data.get("id", ""),
            title=data.get("title", "Unknown"),
            duration=data.get("duration") or 0,
            uploader=data.get("uploader", "Unknown"),
            thumbnail=data.get("thumbnail"),
            webpage_url=data.get("webpage_url", ""),
            description=data.get("description", ""),
            upload_date=data.get("upload_date", ""),
            view_count=data.get("view_count", 0),
        )


@dataclass
class DownloadProgress:
    """Progress information for a download."""

    filename: str = ""
    status: str = ""
    total_bytes: int = 0
    downloaded_bytes: int = 0
    speed: float = 0
    eta: int = 0


@dataclass
class DownloadResult:
    """Result of a download operation."""

    success: bool
    filepath: Path | None = None
    error: str | None = None
    info: VideoInfo | None = None


#: Каталог для m3u8-архивов скачиваний (внутри библиотеки, не аудио → не сканируется).
_ARCHIVE_DIR_NAME = "Плейлисты"


def archive_dir(output_dir: Path) -> Path:
    """Каталог m3u8-архивов внутри библиотеки."""
    return output_dir / _ARCHIVE_DIR_NAME


def archive_path(output_dir: Path, name: str) -> Path:
    """Путь к .m3u8-архиву по имени плейлиста (имя санитизируется)."""
    safe = sanitize_name(name) or "Плейлист"
    if not safe.lower().endswith(".m3u8"):
        safe += ".m3u8"
    return archive_dir(output_dir) / safe


def append_m3u8(path: Path, filepath: Path, title: str = "", duration: int | None = None) -> bool:
    """Добавить запись в .m3u8-архив (без дублей по пути).

    Формат: ``#EXTM3U`` на первой строке, затем для каждого трека заголовок
    ``#EXTINF:<duration>,<title>`` и абсолютный путь к файлу.
    """
    try:
        target = filepath.resolve()
    except OSError:
        target = filepath.absolute()
    line = str(target)
    try:
        if path.is_file():
            existing = path.read_text(encoding="utf-8").splitlines()
        else:
            existing = []
        if line in existing:
            return False
        if not existing or existing[0] != "#EXTM3U":
            existing = ["#EXTM3U"]
        extinf = "#EXTINF:"
        extinf += f"{int(duration)}," if duration else "-1,"
        extinf += title or target.name
        existing.append(extinf)
        existing.append(line)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(existing) + "\n", encoding="utf-8")
        return True
    except OSError:
        return False


_YTMUSIC_RE = re.compile(
    r"https?://music\.youtube\.com/watch(?:\?v|=)([A-Za-z0-9_-]+)"
)


def _normalize_url(url: str) -> str:
    """Convert YouTube Music URLs to standard YouTube URLs."""
    m = _YTMUSIC_RE.match(url)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    return url


class Downloader:
    """Main downloader class wrapping yt-dlp."""

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or resolve_output_dir()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        inbox_dir(self.output_dir).mkdir(parents=True, exist_ok=True)
        self._info_error = ""
        self._last_cookie_opts: dict[str, Any] = {}

    @staticmethod
    def _base_opts() -> dict[str, Any]:
        return {
            "quiet": True,
            "no_warnings": True,
            "cookiesfrombrowser": ("safari",),
        }

    def _cookie_candidates(self) -> list[dict[str, Any]]:
        """Кандидаты cookie-опций: файл/браузер из конфига → дефолт safari+chrome.

        Запомненный рабочий источник (sticky-source) ставится первым, чтобы
        не тратить попытку на заведомо битые cookies."""
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

    _MAX_INFO_RETRIES = 3

    def _get_info(self, url: str) -> VideoInfo | None:
        """Fetch video metadata without downloading.

        Перебирает источники cookies (safari → chrome → без cookies,
        либо файл/браузер из конфига): Safari на macOS часто отдаёт пустые
        cookies (TCC), а age-gate видео без авторизованных cookies не отдаётся
        вообще — старый фолбэк «без cookies» такие видео никогда не чинил.
        """
        from . import ytcookies as _ytc

        url = _normalize_url(url)
        errors: list[Exception] = []

        candidates = self._cookie_candidates()[: self._MAX_INFO_RETRIES]
        for attempt, cookie_opt in enumerate(candidates):
            try:
                opts = self._base_opts()
                opts.pop("cookiesfrombrowser", None)
                opts.pop("cookiefile", None)
                opts.update(cookie_opt)
                with YoutubeDL(opts) as ydl:
                    data = ydl.extract_info(url, download=False)
                    if data:
                        self._last_cookie_opts = dict(cookie_opt)
                        _ytc.remember_working_source(cookie_opt)
                        return VideoInfo.from_ydl(data)
            except Exception as e:
                errors.append(e)
                logger.warning(
                    "Ошибка получения информации (%s, попытка %s/%s): %s",
                    _ytc.describe_source(cookie_opt),
                    attempt + 1, len(candidates), e,
                )
                if attempt < len(candidates) - 1:
                    time.sleep(1.5 * (attempt + 1))

        if errors:
            self._info_error = _ytc.pick_error(errors)
        return None

    def _progress_hook(self, d: dict[str, Any], callback: Callable | None) -> None:
        """Internal progress hook for yt-dlp."""
        if callback is None:
            return

        progress = DownloadProgress(
            filename=d.get("filename", ""),
            status=d.get("status", ""),
            total_bytes=d.get("total_bytes", 0) or d.get("total_bytes_estimate", 0),
            downloaded_bytes=d.get("downloaded_bytes", 0),
            speed=d.get("speed", 0) or 0,
            eta=d.get("eta", 0) or 0,
        )
        callback(progress)

    def _build_output_template(self, info: VideoInfo, fmt: str) -> str:
        """Build output path for yt-dlp inside the intermediate Inbox folder.

        Скачивание идёт во временную папку ``Inbox``; финальная структура
        Artist/Album формируется позже (перенос в библиотеку после обработки).
        """
        title = sanitize_name(info.title)

        inbox = inbox_dir(self.output_dir)
        return str(inbox / f"{title}.%(ext)s")

    def download(
        self,
        url: str,
        fmt: str = "m4a",
        quality: int | None = None,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
        source: str | None = None,
    ) -> DownloadResult:
        """Download audio from URL.

        Args:
            url: Video/audio URL
            fmt: Output format (flac, mp3, m4a, opus)
            quality: Target bitrate in kbps (ignored for FLAC)
            progress_callback: Optional callback for progress updates
            source: Предпочитаемый исходный поток (``opus``/``m4a``/``None``)

        Returns:
            DownloadResult with status and filepath
        """
        try:
            url = _normalize_url(url)
            info = self._get_info(url)
            if info is None:
                detail = f" ({self._info_error})" if self._info_error else ""
                return DownloadResult(
                    success=False,
                    error=f"Не удалось получить информацию о видео{detail}",
                )

            opts = self._base_opts()
            opts.pop("cookiesfrombrowser", None)
            opts.pop("cookiefile", None)
            opts.update(self._last_cookie_opts or {})
            opts.update(AudioFormat.ydl_opts(fmt, quality, source))
            opts["outtmpl"] = self._build_output_template(info, fmt)
            opts["progress_hooks"] = [
                lambda d: self._progress_hook(d, progress_callback)
            ]

            with YoutubeDL(opts) as ydl:
                ydl.download([url])

            expected_path = Path(self._build_output_template(info, fmt)).with_suffix(
                f".{fmt}"
            )
            if expected_path.exists():
                return DownloadResult(success=True, filepath=expected_path, info=info)

            return DownloadResult(
                success=False, error="Файл не найден после скачивания", info=info
            )

        except Exception as e:
            from . import ytcookies as _ytc

            return DownloadResult(success=False, error=_ytc.friendly_error(e))

    def download_many(
        self,
        urls: list[str],
        fmt: str = "m4a",
        max_workers: int = 4,
        quality: int | None = None,
        progress_callback: Callable[[str, DownloadProgress], None] | None = None,
        source: str | None = None,
    ) -> list[DownloadResult]:
        """Download multiple audio URLs in parallel.

        Args:
            urls: List of video/audio URLs
            fmt: Output format (flac, mp3, m4a, opus)
            max_workers: Maximum parallel downloads
            quality: Target bitrate in kbps (ignored for FLAC)
            progress_callback: Callback(url, progress) for progress updates
            source: Предпочитаемый исходный поток (``opus``/``m4a``/``None``)

        Returns:
            List of DownloadResult in the same order as input URLs
        """
        if not urls:
            return []

        results: list[DownloadResult | None] = [None] * len(urls)
        lock = threading.Lock()

        def _download_one(index: int, url: str) -> None:
            def _on_progress(p: DownloadProgress) -> None:
                if progress_callback:
                    progress_callback(url, p)

            result = self.download(
                url, fmt, quality, _on_progress, source=source
            )
            with lock:
                results[index] = result

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_download_one, i, url): i
                for i, url in enumerate(urls)
            }
            for future in as_completed(futures):
                future.result()

        return [r for r in results if r is not None]
