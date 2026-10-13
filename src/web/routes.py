"""API-роуты Web UI.

Все операции над библиотекой разделены на логические группы. Долгие операции
(скачивание, batch, сжатие, пакетные тексты) запускаются как фоновые задачи
через :mod:`src.web.jobs` и стримятся в браузер по SSE.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import ssl
import tempfile
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from ..analytics import scan_directory, scan_library
from ..compress import compress_covers, compress_file, estimate_size, should_compress
from ..config import (
    CONFIG_DIR, DEFAULT_FORMAT, DEFAULT_QUALITY, FEEDBACK_ACTIONS,
    FEEDBACK_ACTION_KEY, get_feedback_action, get_metadata_sources,
    get_metadata_sources_order,
    get_name_translit, get_primuse_sidecar, get_saved_language,
    get_search_source, get_shazam_file, get_source_format, get_youtube_browser,
    get_youtube_cookies_file, get_ytmusic_no_clips,
    inbox_dir, resolve_shazam_file,
    load_config, save_config, update_config, METADATA_SOURCES_KEY,
    METADATA_SOURCES_ORDER_KEY, NAME_TRANSLITS,
    NAME_TRANSLIT_KEY, PRIMUSE_SIDECAR_KEY,
    SHAZAM_FILE_KEY, SEARCH_SOURCES, SEARCH_SOURCE_KEY,
    LANGUAGE_KEY, SUPPORTED_LANGUAGES,
    SOURCE_FORMAT_KEY,
    SOURCE_FORMATS, YOUTUBE_BROWSER_KEY, YOUTUBE_BROWSERS, YOUTUBE_COOKIES_FILE_KEY,
    YTMUSIC_AUTH_FILE_KEY, YTMUSIC_NO_CLIPS_KEY,
)
from ..downloader import (
    Downloader, append_m3u8, archive_path, AudioFormat,
)
from ..health import fix_issues, run_health_check
from ..lint import lint_library
from ..normalize import normalize_library, apply_plan
from ..pipeline import fetch_and_apply_lyrics, move_to_library
from ..providers import available_sources, fetch_all
from ..quality import apply_quality_plan, build_quality_plan, collect_quality
from ..search import YouTubeSearch
from ..shazam_import import (
    find_youtube_matches, migrate_shazam_default, parse_shazam_file,
    remove_shazam_lines, score_match,
)
from ..tagger import apply_cover_from_url, get_tags, set_tags, AudioTags
from ..utils import clean_artist_name, logger, sanitize_name
from .. import services
from .jobs import JobFailure, jobs
from .messages import message
from .serialize import (
    record_to_dict, tags_to_dict, track_to_dict,
    ytm_album_to_dict, ytm_artist_to_dict, ytm_playlist_to_dict,
    ytm_track_to_dict,
)

#: Оркестрация рекомендаций по библиотеке (радио YouTube Music).
from .. import recommend as recommend_mod

core = APIRouter()
library = APIRouter(prefix="/api")
search_rt = APIRouter(prefix="/api")
misc = APIRouter(prefix="/api")
ytm = APIRouter(prefix="/api/ytmusic")

_LYRICS_SNAPSHOT_TTL = 120.0
_lyrics_snapshots: dict[str, tuple[float, Path, list[dict]]] = {}
_lyrics_snapshots_lock = threading.Lock()


def _out_dir() -> Path:
    from ..config import resolve_output_dir
    return resolve_output_dir()


def _num_sort_key(value: str | None) -> tuple[int, int, str]:
    """Ключ числовой сортировки номеров треков/дисков.

    Числовые значения сортируются по числу (не лексикографически, где "10"
    вставало раньше "2"); пустые/нечисловые уходят в конец.
    """
    import re as _re

    text = (value or "").strip()
    match = _re.search(r"\d+", text)
    if not match:
        return (1, 0, text.lower())
    return (0, int(match.group(0)), text.lower())


def _path_or_400(value: str) -> Path:
    if not value:
        raise HTTPException(
            status_code=400,
            detail=message("api.errors.empty_path", fallback="Empty path"),
        )
    return Path(value)


def _get_file(value: str) -> Path:
    path = _path_or_400(value)
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=message(
                "api.errors.file_not_found",
                {"path": str(path)},
                fallback=f"File not found: {path}",
            ),
        )
    return path


# --- Состояние -----------------------------------------------------------


#: TTL-кэш /api/state: полный скан тегов дорогой, полл сайдбара каждые 5с
#: без кэша пересканирует библиотеку. Ключ — каталог библиотеки.
_STATE_CACHE: dict[str, dict] = {}
_STATE_CACHE_TTL = 30.0


def _state_key() -> str:
    return str(_out_dir())


@core.get("/api/state")
def api_state():
    out = _out_dir()
    key = _state_key()
    cached = _STATE_CACHE.get(key)
    if cached and time.monotonic() - cached["ts"] < _STATE_CACHE_TTL:
        return cached["data"]
    total = artists = 0
    size_mb = 0.0
    if out.exists():
        from ..analytics import library_files

        files = library_files(out)
        total = len(files)
        artists = set()
        for f in files:
            try:
                tags = get_tags(f)
                if tags.artist:
                    artists.add(tags.artist)
            except Exception:
                pass
        size_mb = sum(f.stat().st_size for f in files if f.exists()) / (1024 * 1024)
    data = {
        "output_dir": str(out),
        "tracks": total,
        "artists": len(artists),
        "size_mb": round(size_mb, 1),
    }
    _STATE_CACHE[key] = {"ts": time.monotonic(), "data": data}
    return data


#: TTL-кэш /api/home: скан библиотеки + health-check дорогие, повторные
#: рендеры Главной отдают сохранённый ответ. Ключ — каталог библиотеки.
_HOME_CACHE: dict[str, dict] = {}
_HOME_CACHE_TTL = 30.0


@core.get("/api/home")
def api_home():
    """Агрегированные данные для главной страницы: статистика, недавние треки
    и health-сводка (кэшируется на TTL)."""
    from ..analytics import aggregate, scan_library

    key = str(_out_dir())
    cached = _HOME_CACHE.get(key)
    if cached and time.monotonic() - cached["ts"] < _HOME_CACHE_TTL:
        return cached["data"]

    out = _out_dir()
    records: list = []
    errors = 0
    if out.exists():
        records, errors = scan_library(out)

    stats = aggregate(records)
    genres = [
        {"name": name, "count": count,
         "pct": round(count * 100 / stats.total, 1) if stats.total else 0}
        for name, count in stats.top_genres
    ]
    artists = []
    from collections import Counter
    aa_counter = Counter(
        (r.album_artist or "").strip() or (r.artist or "").strip()
        for r in records
    )
    for name, count in aa_counter.most_common(10):
        if not name:
            continue
        artists.append({
            "name": name, "count": count,
            "pct": round(count * 100 / stats.total, 1) if stats.total else 0,
        })

    recent = sorted((r for r in records if r.mtime), key=lambda r: r.mtime, reverse=True)[:5]
    recent_dicts = [{
        "artist": r.artist, "title": r.title, "album": r.album,
        "ext": r.path.suffix.lower(), "mtime": r.mtime, "path": str(r.path),
    } for r in recent]

    # Один источник правды с экраном «Проблемы»: тот же collect_quality,
    # то же число (len(issues)); иначе меню показывает «100% / Всё в порядке»,
    # пока «Проблемы» насчитывают N.
    health = {"total": 0, "issues": 0, "counts": {}}
    if out.exists():
        quality = collect_quality(out)
        health = {
            "total": quality.total,
            "issues": len(quality.issues),
            "counts": quality.counts,
        }

    shazam = {"configured": False, "count": 0, "file": ""}
    shazam_path = get_shazam_file()
    if shazam_path:
        shazam["configured"] = True
        shazam["file"] = str(shazam_path)
        if shazam_path.is_file():
            try:
                shazam["count"] = len(parse_shazam_file(shazam_path))
            except Exception:
                pass

    payload = {
        "state": {
            "output_dir": str(out),
            "tracks": stats.total,
            "artists": stats.artists,
            "albums": stats.albums,
            "duration_seconds": stats.total_seconds,
            "size_mb": round(stats.total_size / (1024 * 1024), 1),
        },
        "genres": genres,
        "artists": artists,
        "recent": recent_dicts,
        "health": health,
        "shazam": shazam,
        "had_errors": errors,
    }
    _HOME_CACHE[key] = {"ts": time.monotonic(), "data": payload}
    return payload


@core.get("/api/settings")
def api_get_settings():
    cfg = load_config()
    cookies_path = get_youtube_cookies_file()
    from .. import ytmusic as ytm_mod

    return {
        "output_dir": str(_out_dir()),
        "default_format": cfg.get("default_format") or DEFAULT_FORMAT,
        "default_quality": int(cfg.get("default_quality") or DEFAULT_QUALITY),
        "source_format": get_source_format(),
        "source_formats": list(SOURCE_FORMATS),
        "shazam_file": str(get_shazam_file() or ""),
        "primuse_sidecar": get_primuse_sidecar(),
        "youtube_browser": get_youtube_browser(),
        "youtube_browsers": list(YOUTUBE_BROWSERS),
        "youtube_cookies_file": str(cookies_path) if cookies_path else "",
        "youtube_cookies_set": bool(cookies_path and cookies_path.exists()),
        "ytmusic_auth_file": str(ytm_mod.get_auth_file()),
        "ytmusic_mode": ytm_mod.auth_mode(),
        "ytmusic_connected": ytm_mod.connected(),
        "ytmusic_no_clips": get_ytmusic_no_clips(),
        "ytm_feedback_action": get_feedback_action(),
        "search_source": get_search_source(),
        "name_translit": get_name_translit(),
        "metadata_sources": get_metadata_sources(),
        "metadata_sources_order": get_metadata_sources_order(),
        "metadata_sources_available": available_sources(),
        "formats": AudioFormat.all(),
        "language": get_saved_language(),
    }


@core.put("/api/settings")
def api_put_settings(payload: dict):
    def apply(cfg: dict[str, Any]) -> set[str]:
        known: set[str] = set()
        if LANGUAGE_KEY in payload and (not isinstance(payload[LANGUAGE_KEY], str) or payload[LANGUAGE_KEY] not in SUPPORTED_LANGUAGES):
            raise HTTPException(status_code=400, detail=message("api.errors.invalid_setting", {"key": LANGUAGE_KEY}, fallback="Invalid value: language"))
        for key, valid in ((LANGUAGE_KEY, SUPPORTED_LANGUAGES), (NAME_TRANSLIT_KEY, NAME_TRANSLITS), (FEEDBACK_ACTION_KEY, FEEDBACK_ACTIONS), (SEARCH_SOURCE_KEY, SEARCH_SOURCES), (SOURCE_FORMAT_KEY, SOURCE_FORMATS)):
            if key in payload:
                value = str(payload[key] or "").strip().lower()
                if value not in valid:
                    if key == SOURCE_FORMAT_KEY:
                        raise HTTPException(status_code=400, detail=message("api.errors.invalid_source_format", {"value": value}, fallback=f"Invalid source format: {value}"))
                    if key == NAME_TRANSLIT_KEY:
                        raise HTTPException(status_code=400, detail=message("api.errors.invalid_transliteration", {"value": value}, fallback=f"Invalid transliteration mode: {value}"))
                    if key == FEEDBACK_ACTION_KEY:
                        raise HTTPException(status_code=400, detail=message("api.errors.invalid_feedback", {"value": value}, fallback=f"Invalid feedback action: {value}"))
                    if key == SEARCH_SOURCE_KEY:
                        raise HTTPException(status_code=400, detail=message("api.errors.invalid_search_source", {"value": value}, fallback=f"Invalid search source: {value}"))
                    raise HTTPException(status_code=400, detail=message("api.errors.invalid_setting", {"key": key}, fallback=f"Invalid value: {key}"))
                cfg[key] = value
                known.add(key)
        for key in (PRIMUSE_SIDECAR_KEY, YTMUSIC_NO_CLIPS_KEY):
            if key in payload:
                raw = payload[key]
                if not isinstance(raw, (bool, int, float, str)):
                    raise HTTPException(status_code=400, detail=message("api.errors.invalid_setting", {"key": key}, fallback=f"Invalid value: {key}"))
                cfg[key] = bool(raw) if not isinstance(raw, str) else raw.strip().lower() in ("1", "true", "yes", "on") if key == PRIMUSE_SIDECAR_KEY else raw.strip().lower() not in ("0", "false", "no", "off")
                known.add(key)
        if YTMUSIC_AUTH_FILE_KEY in payload:
            value = str(payload[YTMUSIC_AUTH_FILE_KEY] or "").strip()
            if value: cfg[YTMUSIC_AUTH_FILE_KEY] = value
            else: cfg.pop(YTMUSIC_AUTH_FILE_KEY, None)
            known.add(YTMUSIC_AUTH_FILE_KEY)
        if YOUTUBE_BROWSER_KEY in payload:
            browser = str(payload[YOUTUBE_BROWSER_KEY] or "").strip().lower()
            if browser and browser not in YOUTUBE_BROWSERS:
                raise HTTPException(status_code=400, detail=message("api.errors.unknown_browser", {"browser": browser, "available": ", ".join(YOUTUBE_BROWSERS)}, fallback=f"Unknown browser: {browser}"))
            if browser: cfg[YOUTUBE_BROWSER_KEY] = browser
            else: cfg.pop(YOUTUBE_BROWSER_KEY, None)
            known.add(YOUTUBE_BROWSER_KEY)
        for key, caster in {"output_dir": str, "default_format": str, "default_quality": int, SHAZAM_FILE_KEY: str}.items():
            if key not in payload: continue
            try: value = caster(payload[key])
            except (TypeError, ValueError): raise HTTPException(status_code=400, detail=message("api.errors.invalid_setting", {"key": key}, fallback=f"Invalid value: {key}"))
            if key == "default_format" and value not in AudioFormat.all(): raise HTTPException(status_code=400, detail=message("api.errors.invalid_format", {"value": value}, fallback=f"Invalid format: {value}"))
            if key == "default_quality" and not 0 < value <= 512: raise HTTPException(status_code=400, detail=message("api.errors.quality_out_of_range", fallback="Quality must be between 1 and 512"))
            if key in (SHAZAM_FILE_KEY, "output_dir") and not (value := str(value).strip()): cfg.pop(key, None)
            else: cfg[key] = value
            known.add(key)
        for key, complete in ((METADATA_SOURCES_KEY, False), (METADATA_SOURCES_ORDER_KEY, True)):
            if key not in payload: continue
            value = payload[key]
            if not isinstance(value, list): raise HTTPException(status_code=400, detail=message("api.errors.expected_list", {"field": key}, fallback=f"{key} must be a list of sources"))
            known_sources, selected = available_sources(), []
            for item in value:
                name = str(item).strip()
                if name not in known_sources: raise HTTPException(status_code=400, detail=message("api.errors.unknown_source", {"source": name}, fallback=f"Unknown source: {name}"))
                if name not in selected: selected.append(name)
            cfg[key] = selected + [name for name in known_sources if complete and name not in selected]
            known.add(key)
        return known

    known = update_config(apply)
    migrated_shazam = 0
    if SHAZAM_FILE_KEY in known:
        # Кастомный путь активирован: переносим строки из дефолтного
        # .system/shazam.txt, чтобы шазамы не раздвоились между файлами.
        custom = str(payload.get(SHAZAM_FILE_KEY) or "").strip()
        if custom:
            try:
                migrated_shazam = migrate_shazam_default(
                    Path(custom).expanduser(), _out_dir())
            except OSError:
                migrated_shazam = 0
    result = {"status": "ok", "updated": sorted(known)}
    if migrated_shazam:
        result["migrated_shazam"] = migrated_shazam
    return result


#: Куда кладём загруженный cookies.txt (локально, рядом с конфигом).
def _youtube_cookies_path() -> Path:
    return CONFIG_DIR / "cookies" / "youtube.txt"


def _validate_cookies_txt(text: str) -> tuple[bool, str, int]:
    """Проверить содержимое cookies.txt (Netscape-формат). Возвращает (ok, reason, lines)."""
    if not text or not text.strip():
        return False, "пустой файл", 0
    if len(text) > 1_000_000:
        return False, "файл больше 1 МБ", 0
    data_lines = [ln for ln in text.splitlines()
                  if ln.strip() and not ln.lstrip().startswith("#")]
    if not data_lines:
        return False, "нет строк с cookies (только комментарии)", 0
    good = 0
    for ln in data_lines:
        parts = ln.split()
        if len(parts) >= 6 and "." in parts[0]:
            good += 1
    if not good:
        return False, "не похоже на cookies.txt (нужен Netscape-формат: 7 полей через таб)", 0
    blob = text.lower()
    if not any(d in blob for d in ("youtube.com", "youtu.be", "googlevideo.com", "google.com")):
        return False, "нет cookies для youtube.com — экспортируйте с открытого YouTube", 0
    return True, "", good


@core.post("/api/settings/cookies")
def api_upload_cookies(payload: dict):
    content = str((payload or {}).get("content") or "").replace("\r\n", "\n")
    ok, reason, lines = _validate_cookies_txt(content)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Некорректный cookies.txt: {reason}")
    target = _youtube_cookies_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not content.endswith("\n"):
        content += "\n"
    target.write_text(content, encoding="utf-8")
    try:
        target.chmod(0o600)
    except OSError:
        pass
    update_config(lambda cfg: cfg.__setitem__(YOUTUBE_COOKIES_FILE_KEY, str(target)))
    return {"status": "ok", "path": str(target), "lines": lines}


@core.delete("/api/settings/cookies")
def api_delete_cookies():
    update_config(lambda cfg: cfg.pop(YOUTUBE_COOKIES_FILE_KEY, None))
    try:
        _youtube_cookies_path().unlink(missing_ok=True)
    except OSError:
        pass
    return {"status": "ok"}


@core.post("/api/settings/cookies/check")
def api_check_browser_cookies(payload: dict | None = None):
    """Проверить cookies YouTube в выбранном браузере (локально, без сети).

    Проверяется только текущий выбор (`browser` в теле запроса, иначе
    настроенный `youtube_browser`): для safari — дефолтное хранилище плюс
    профили. Серверный логин по паролю/OAuth невозможен — в yt-dlp он
    отключён («Login with OAuth is no longer supported», «Login with
    password is not supported for YouTube»).
    """
    from yt_dlp.cookies import extract_cookies_from_browser

    from ..ytcookies import AUTH_COOKIE_NAMES, discover_safari_profiles

    requested = str((payload or {}).get("browser") or "").strip().lower()
    browser = requested or get_youtube_browser()
    if browser not in YOUTUBE_BROWSERS:
        raise HTTPException(
            status_code=400,
            detail=message(
                "api.errors.unknown_browser",
                {"browser": browser, "available": ", ".join(YOUTUBE_BROWSERS)},
                fallback=f"Unknown browser: {browser} (available: {', '.join(YOUTUBE_BROWSERS)})",
            ),
        )

    def _summarize(label: str, jar) -> dict:
        yt_names = {c.name for c in jar
                    if "youtube.com" in (c.domain or "")}
        if not yt_names:
            return {"browser": label, "status": "empty",
                    "cookies": 0, "auth": False, "error": ""}
        return {"browser": label, "status": "ok",
                "cookies": len(yt_names),
                "auth": bool(yt_names & AUTH_COOKIE_NAMES), "error": ""}

    def _checked(label: str, *args) -> dict:
        try:
            return _summarize(label, extract_cookies_from_browser(*args))
        except Exception as e:
            return {"browser": label, "status": "error",
                    "cookies": 0, "auth": False, "error": str(e)}

    results = [_checked(browser, browser)]
    if browser == "safari":
        for label, path in discover_safari_profiles():
            results.append(_checked(f"safari:профиль {label}", "safari", path))
    return {"browser": browser, "browsers": results}


#: Age-видео для проверки 18+ (заведомо с ограничением).
VERIFY_AGE_VIDEO_ID = "PY4V9eD0-F8"


@core.post("/api/settings/cookies/verify-age")
def api_verify_age(payload: dict | None = None):
    """Проверить 18+ запросом: тянет age-видео каждым источником по очереди.

    Вердикт на источник: ok (метаданные получены — 18+ подтверждён),
    gate (входа нет), blocked (вход есть, но аккаунт не 18+), other.
    Останавливается на первом ok.
    """
    import re

    from yt_dlp import YoutubeDL

    from .. import ytcookies as ytc

    video_id = str((payload or {}).get("video_id") or VERIFY_AGE_VIDEO_ID).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        raise HTTPException(status_code=400, detail=message("api.errors.invalid_video_id", fallback="Invalid video_id"))
    url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        from ..config import get_youtube_cookies_file

        cookiefile = get_youtube_cookies_file()
        cookiefile_s = str(cookiefile) if cookiefile else None
    except Exception:
        cookiefile_s = None
    candidates = ytc.preferred_first(
        ytc.cookie_opt_candidates(
            browser=get_youtube_browser(), cookiefile=cookiefile_s),
        ytc.get_preferred_source())

    checks = []
    for cookie_opt in candidates:
        source = ytc.describe_source(cookie_opt)
        opts = {"quiet": True, "no_warnings": True, "socket_timeout": 20,
                "format": "bestaudio/best"}
        opts.update(cookie_opt)
        try:
            with YoutubeDL(opts) as ydl:
                data = ydl.extract_info(url, download=False)
            checks.append({"source": source, "ok": True, "reason": "ok",
                           "title": (data or {}).get("title") or ""})
            break
        except Exception as e:
            reason = ytc.probe_reason(e)
            checks.append({"source": source, "ok": False, "reason": reason,
                           "error": str(e)[:200]})
    verified = any(c["ok"] for c in checks)
    return {"video_id": video_id, "verified_18": verified, "checks": checks}


@core.get("/api/fs/browse")
def api_fs_browse(dir: str = Query("", title="Каталог")):
    """Подкаталоги уровня для выбора путей в настройках."""
    base = Path(dir) if dir else _out_dir()
    if not base.exists():
        raise HTTPException(status_code=404, detail=message("api.errors.directory_not_found", {"path": str(base)}, fallback=f"Directory not found: {base}"))
    if not base.is_dir():
        raise HTTPException(status_code=400, detail=message("api.errors.not_directory", fallback="Not a directory"))
    try:
        entries = sorted(
            (p for p in base.iterdir() if p.is_dir()),
            key=lambda p: p.name,
        )
    except OSError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {
        "path": str(base),
        "parent": str(base.parent) if base.parent != base else "",
        "dirs": [{"name": p.name, "path": str(p)} for p in entries],
    }


@core.post("/api/fs/pick")
def api_fs_pick(payload: dict | None = None):
    """Открыть нативный системный диалог выбора пути (Finder/проводник).

    Вызывается из настроек: ``kind`` = ``folder`` (каталог библиотеки) или
    ``file`` (файл Shazam). Диалог открывается на машине, где
    запущен сервер, поэтому при доступе с телефона его покажет Mac.
    Отмена/ошибка/отсутствие диалога → ``{"path": null}``.
    """
    from ..native_picker import pick_path

    payload = payload or {}
    kind = str(payload.get("kind") or "folder")
    start = str(payload.get("start") or "").strip()
    if kind not in ("folder", "file"):
        raise HTTPException(status_code=400, detail=message("api.errors.invalid_pick_kind", fallback="kind must be folder or file"))
    path = pick_path(kind, start or None)
    return {"path": str(Path(path)) if path else None}


# --- YouTube Music (ytmusicapi) ----------------------------------------

#: Флаг «идёт OAuth» — конкурирующий запрос должен получить 409.
_ytm_oauth_active = False
_ytm_oauth_lock = threading.Lock()


@ytm.get("/status")
def api_ytmusic_status():
    """Статус подключения к YouTube Music + данные аккаунта (если есть)."""
    from .. import ytmusic as ytm_mod

    payload = {
        "connected": ytm_mod.connected(),
        "mode": ytm_mod.auth_mode(),
        "auth_file": str(ytm_mod.get_auth_file()),
        "account": None,
        "account_error": "",
    }
    if payload["connected"]:
        try:
            payload["account"] = ytm_mod.account_info()
        except Exception as e:
            payload["account_error"] = str(e)
    return payload


@ytm.post("/auth/browser/extract")
def api_ytmusic_auth_browser_extract(payload: dict):
    """Извлечь заголовки авторизации из кук браузера (задача + SSE).

    Читает куки профиля (yt-dlp; macOS может спросить доступ к Keychain),
    выбирает ``X-Goog-AuthUser`` (из поля ``authuser`` либо подбором по лайкам)
    и сохраняет файл авторизации.
    """
    from .. import ytmusic as ytm_mod

    browser = str((payload or {}).get("browser") or "").strip()
    profile = (payload or {}).get("profile") or None
    if isinstance(profile, str):
        profile = profile.strip() or None
    else:
        profile = None
    authuser = (payload or {}).get("authuser")
    if authuser is None or authuser == "":
        authuser = None
    else:
        try:
            authuser = int(authuser)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=message("api.errors.invalid_authuser", fallback="Invalid authuser"))
    page_id = (payload or {}).get("page_id")
    if isinstance(page_id, str):
        page_id = page_id.strip() or None
    else:
        page_id = None
    if not browser:
        raise HTTPException(status_code=400, detail=message("api.errors.browser_required", fallback="Select a browser"))

    def run(job):
        job.push(message("jobs.auth.read_cookies", fallback="Reading browser cookies…"), 15)
        res = ytm_mod.extract_browser_headers(browser, profile=profile,
                                              authuser=authuser, page_id=page_id)
        job.push(message("jobs.auth.saved_checking", fallback="Authorization saved. Checking account…"), 90)
        try:
            account = ytm_mod.account_info()
        except ytm_mod.YTMusicError:
            account = None
        return {"ok": True, "account": account or res["account"],
                "authuser": res["authuser"], "browser": res["browser"],
                "profile": res["profile"], "likes": res.get("likes", 0),
                "page_id": res.get("page_id")}

    job = jobs.submit(message("jobs.auth.extract_name", fallback="Extract browser cookies"), run)
    return {"job_id": job.id, "name": job.name}


@ytm.post("/auth/browser/accounts")
def api_ytmusic_auth_browser_accounts(payload: dict):
    """Аккаунты, распознанные в куках профиля браузера (задача + SSE).

    Пробует все ``X-Goog-AuthUser`` 0..N и возвращает список
    ``[{authuser, account, likes}]``, отсортированный по лайкам. Результат
    удобно показать в выпадающем списке перед ручным извлечением.
    """
    from .. import ytmusic as ytm_mod

    browser = str((payload or {}).get("browser") or "").strip()
    profile = (payload or {}).get("profile") or None
    if isinstance(profile, str):
        profile = profile.strip() or None
    else:
        profile = None
    if not browser:
        raise HTTPException(status_code=400, detail=message("api.errors.browser_required", fallback="Select a browser"))

    def run(job):
        job.push(message("jobs.auth.read_cookies", fallback="Reading browser cookies…"), 15)
        candidates = ytm_mod.browser_accounts(browser, profile=profile)
        job.push(message("jobs.common.done", fallback="Done"), 100)
        return {"candidates": candidates}

    job = jobs.submit(message("jobs.auth.accounts_name", fallback="Find browser accounts"), run)
    return {"job_id": job.id, "name": job.name}


@ytm.get("/auth/browsers")
def api_ytmusic_auth_browsers():
    """Браузеры, из которых можно вытянуть куки автоматически."""
    return {"browsers": _ytm_mod().available_browsers()}


@ytm.post("/auth/browser")
def api_ytmusic_auth_browser(payload: dict):
    """Сохранить авторизацию из вставленных заголовков запроса браузера."""
    from .. import ytmusic as ytm_mod

    headers_raw = str((payload or {}).get("headers_raw") or "")
    error = ytm_mod.validate_browser_headers(headers_raw)
    if error:
        raise HTTPException(status_code=400, detail=error)
    try:
        ytm_mod.write_browser_auth(headers_raw)
    except ytm_mod.YTMusicError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "auth_file": str(ytm_mod.get_auth_file())}


@ytm.delete("/auth")
def api_ytmusic_auth_delete():
    """Удалить файл авторизации YouTube Music."""
    from .. import ytmusic as ytm_mod

    ytm_mod.clear_auth()
    return {"status": "ok"}


@ytm.post("/auth/oauth")
def api_ytmusic_auth_oauth(payload: dict):
    """Запустить OAuth device flow (задача + SSE: ссылка подтверждения).

    Raises:
        409 — OAuth уже выполняется другой задачей.
    """
    from .. import ytmusic as ytm_mod

    client_id = str((payload or {}).get("client_id") or "").strip()
    client_secret = str((payload or {}).get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=400,
            detail=message("api.errors.oauth_credentials_required", fallback="Provide client_id and client_secret (YouTube Data API app)"))

    global _ytm_oauth_active
    with _ytm_oauth_lock:
        if _ytm_oauth_active:
            raise HTTPException(status_code=409,
                                detail=message("api.errors.oauth_in_progress", fallback="OAuth is already running; wait for it to finish"))
        _ytm_oauth_active = True

    def run(job):
        def on_pending(url):
            job.push(message("jobs.auth.confirmation_link", fallback="Confirmation link received"), percent=30, auth_url=url)

        try:
            job.push(message("jobs.auth.creating_session", fallback="Creating OAuth session…"), 5)
            ytm_mod.oauth_authorize(client_id, client_secret, on_pending=on_pending)
            job.push(message("jobs.auth.saved_checking", fallback="Authorization saved. Checking account…"), 90)
            try:
                account = ytm_mod.account_info()
            except ytm_mod.YTMusicError:
                account = None
            return {"account": account or None}
        finally:
            global _ytm_oauth_active
            with _ytm_oauth_lock:
                _ytm_oauth_active = False

    job = jobs.submit(message("jobs.auth.oauth_name", fallback="YouTube Music OAuth"), run)
    return {"job_id": job.id, "name": job.name}


#: TTL-кэш данных локальной библиотеки для дедупа на экране YouTube Music.
_YTM_KEYS_CACHE: dict[str, dict] = {}
_YTM_KEYS_TTL = 60.0

#: Кэш числа треков сохранённых альбомов (по browseId): в списке библиотеки
#: ytmusicapi не отдаёт trackCount — берём из деталей альбома один раз.
_YTM_ALBUM_COUNTS: dict[str, int | None] = {}


def _ytm_mod():
    from .. import ytmusic as ytm_mod

    return ytm_mod


def _ytm_library_dedup() -> dict:
    """Данные локальной библиотеки для дедупа (кэш по пути, TTL 60 c).

    Возвращает ``{"keys": ..., "albums": ..., "artists": ...}`` — ключи
    (artist, title) треков и счётчики файлов по альбомам/исполнителям.
    """
    out = _out_dir()
    key = str(out)
    cached = _YTM_KEYS_CACHE.get(key)
    if cached and time.monotonic() - cached["ts"] < _YTM_KEYS_TTL:
        return cached
    records: list = []
    if out.exists():
        records, _errors = scan_library(out)
    mod = _ytm_mod()
    data = {
        "ts": time.monotonic(),
        "keys": mod.library_keys(records),
        "album_tracks": mod.library_album_track_keys(records),
        "albums": mod.library_album_counts(records),
        "artists": mod.library_artist_counts(records),
    }
    _YTM_KEYS_CACHE[key] = data
    return data


def _ytm_album_track_count(album_id: str) -> int | None:
    """Число треков сохранённого альбома (в списке библиотеки нет trackCount)."""
    if album_id not in _YTM_ALBUM_COUNTS:
        count: int | None = None
        try:
            raw = _ytm_mod().get_album(album_id)
            count = ytm_album_to_dict(raw).get("track_count")
        except Exception:
            count = None
        _YTM_ALBUM_COUNTS[album_id] = count
    return _YTM_ALBUM_COUNTS[album_id]


def _ytm_library_keys() -> set[tuple[str, str]]:
    """Ключи (artist, title) библиотеки для пометки «в библиотеке»."""
    return _ytm_library_dedup()["keys"]


def _ytm_album_badge(d: dict) -> dict:
    """Добавить карточке альбома счётчик «N/M в библиотеке»."""
    counts = _ytm_library_dedup()["albums"]
    n = counts.get((_ytm_mod().norm(d["title"]), _ytm_mod().norm(d["artist"])), 0)
    d["in_library_tracks"] = n
    d["in_library"] = bool(n)
    return d


def _ytm_local_playlist_counts() -> dict[str, int]:
    """Сколько файлов в каждом .m3u8-архиве каталога «Плейлисты».

    Ключ — ``norm(имя файла)``, значение — число записей (файловых путей,
    строки без ``#``). Используется для пометки «N локально / M» на плейлистах.
    """
    from ..downloader import archive_dir

    adir = archive_dir(_out_dir())
    if not adir.is_dir():
        return {}
    norm = _ytm_mod().norm
    out: dict[str, int] = {}
    for f in sorted(adir.glob("*.m3u8")):
        n = 0
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    n += 1
        except OSError:
            continue
        if n:
            out[norm(f.stem)] = n
    return out


def _ytm_checked(tracks):
    """Серализовать треки с флагом «в библиотеке» (кэшированный дедуп)."""
    keys = _ytm_library_keys()
    return [ytm_track_to_dict(t, _ytm_mod().track_in_library(t, keys))
            for t in tracks]


@ytm.get("/liked")
def api_ytmusic_liked(limit: int = Query(100, ge=1, le=500)):
    """Понравившиеся песни аккаунта с пометкой «в библиотеке»."""
    try:
        tracks = _ytm_mod().liked_songs(limit=limit)
    except _ytm_mod().YTMusicError as e:
        raise HTTPException(status_code=502, detail=f"Ошибка YouTube Music: {e}")
    return {"tracks": _ytm_checked(tracks)}


@ytm.get("/library_songs")
def api_ytmusic_library_songs(limit: int = Query(100, ge=1, le=500)):
    """Песни из библиотеки аккаунта (лайки не входят) с пометкой «в библиотеке»."""
    try:
        tracks = _ytm_mod().library_songs(limit=limit)
    except _ytm_mod().YTMusicError as e:
        raise HTTPException(status_code=502, detail=f"Ошибка YouTube Music: {e}")
    return {"tracks": _ytm_checked(tracks)}


@ytm.get("/albums")
def api_ytmusic_albums(limit: int = Query(100, ge=1, le=500)):
    """Альбомы в библиотеке аккаунта со счётчиком «в локальной библиотеке»."""
    try:
        albums = _ytm_mod().library_albums(limit=limit)
    except _ytm_mod().YTMusicError as e:
        raise HTTPException(status_code=502, detail=f"Ошибка YouTube Music: {e}")
    out = []
    for a in albums:
        if not isinstance(a, dict) or not a.get("browseId"):
            continue
        d = _ytm_album_badge(ytm_album_to_dict(a))
        if d["title"]:
            if not d.get("track_count"):
                d["track_count"] = _ytm_album_track_count(str(a.get("browseId")))
            out.append(d)
    return {"albums": out}


@ytm.get("/artists")
def api_ytmusic_artists(limit: int = Query(100, ge=1, le=500)):
    """Сохранённые исполнители аккаунта со счётчиком локальных файлов."""
    try:
        artists = _ytm_mod().library_artists(limit=limit)
    except _ytm_mod().YTMusicError as e:
        raise HTTPException(status_code=502, detail=f"Ошибка YouTube Music: {e}")
    counts = _ytm_library_dedup()["artists"]
    out = []
    for a in artists:
        if not isinstance(a, dict) or not a.get("browseId"):
            continue
        d = ytm_artist_to_dict(a)
        if not d["name"]:
            continue
        d["local_count"] = counts.get(_ytm_mod().norm(d["name"]), 0)
        d["in_library"] = bool(d["local_count"])
        out.append(d)
    return {"artists": out}


@ytm.get("/artist")
def api_ytmusic_artist(browse_id: str = Query(...)):
    """Исполнитель: top-песни с пометками + альбомы со счётчиками."""
    try:
        raw = _ytm_mod().get_artist(browse_id)
    except _ytm_mod().YTMusicError as e:
        raise HTTPException(status_code=502, detail=f"Ошибка YouTube Music: {e}")
    if not isinstance(raw, dict) or not raw:
        raise HTTPException(status_code=404, detail=message("api.errors.artist_not_found", fallback="Artist not found"))
    mod = _ytm_mod()
    keys = _ytm_library_keys()
    top = []
    for i, item in enumerate(raw.get("topSongs") or [], 1):
        if not isinstance(item, dict) or not item.get("videoId"):
            continue
        track = mod.track_from_dict(item)
        track.track_number = track.track_number or i
        top.append(ytm_track_to_dict(track, mod.track_in_library(track, keys)))
    albums = []
    for a in raw.get("albums") or []:
        if not isinstance(a, dict) or not a.get("browseId"):
            continue
        d = _ytm_album_badge(ytm_album_to_dict(a))
        if d["title"]:
            albums.append(d)
    from ..ytmusic import pick_thumbnail

    return {
        "id": browse_id,
        "name": str(raw.get("name") or ""),
        "subscribers": str(raw.get("subscribers") or ""),
        "cover_url": pick_thumbnail(raw.get("thumbnails")),
        "top_songs": top,
        "albums": albums,
    }


@ytm.get("/album")
def api_ytmusic_album(browse_id: str = Query(...)):
    """Альбом с полным треклистом и пометками «в библиотеке»."""
    try:
        raw = _ytm_mod().get_album(browse_id)
    except _ytm_mod().YTMusicError as e:
        raise HTTPException(status_code=502, detail=f"Ошибка YouTube Music: {e}")
    if not isinstance(raw, dict) or not raw:
        raise HTTPException(status_code=404, detail=message("api.errors.album_not_found", fallback="Album not found"))
    album_artist = ", ".join(
        str(a.get("name") or "") for a in raw.get("artists") or []
        if isinstance(a, dict)
    )
    album_track_keys = _ytm_library_dedup()["album_tracks"]
    tracks = []
    for i, item in enumerate(raw.get("tracks") or [], 1):
        if not isinstance(item, dict):
            continue
        if not item.get("videoId"):
            continue
        track = _ytm_mod().track_from_dict(item)
        track.track_number = track.track_number or i
        if (not track.artist or track.artist == "Неизвестный исполнитель") and album_artist:
            track.artist = album_artist
        tracks.append(ytm_track_to_dict(
            track, _ytm_mod().track_in_album_library(
                track, str(raw.get("title") or ""), album_track_keys
            )
        ))
    from ..ytmusic import pick_thumbnail

    return {
        "id": browse_id,
        "title": str(raw.get("title") or ""),
        "artist": album_artist,
        "year": raw.get("year"),
        "track_count": len(tracks),
        "cover_url": pick_thumbnail(raw.get("thumbnails")),
        "tracks": tracks,
    }


@ytm.get("/playlists")
def api_ytmusic_playlists(limit: int = Query(100, ge=1, le=500)):
    """Плейлисты в библиотеке аккаунта с пометкой о локальном .m3u8-архиве."""
    try:
        playlists = _ytm_mod().library_playlists(limit=limit)
    except _ytm_mod().YTMusicError as e:
        raise HTTPException(status_code=502, detail=f"Ошибка YouTube Music: {e}")
    arcmap = _ytm_local_playlist_counts()
    out = []
    for p in playlists:
        if not isinstance(p, dict) or not p.get("playlistId"):
            continue
        d = ytm_playlist_to_dict(p)
        if not d["title"]:
            continue
        n = arcmap.get(_ytm_mod().norm(d["title"]), 0)
        d["local_count"] = n
        d["in_library"] = bool(n)
        out.append(d)
    return {"playlists": out}


@ytm.get("/playlist")
def api_ytmusic_playlist(playlist_id: str = Query(...)):
    """Плейлист с треклистом и пометками «в библиотеке»."""
    try:
        raw = _ytm_mod().get_playlist(playlist_id)
    except _ytm_mod().YTMusicError as e:
        raise HTTPException(status_code=502, detail=f"Ошибка YouTube Music: {e}")
    if not isinstance(raw, dict) or not raw:
        raise HTTPException(status_code=404, detail=message("api.errors.playlist_not_found", fallback="Playlist not found"))
    keys = _ytm_library_keys()
    tracks = []
    for i, item in enumerate(raw.get("tracks") or [], 1):
        if not isinstance(item, dict) or not item.get("videoId"):
            continue
        track = _ytm_mod().track_from_dict(item)
        tracks.append(ytm_track_to_dict(track, _ytm_mod().track_in_library(track, keys)))
    from ..ytmusic import pick_thumbnail

    return {
        "id": playlist_id,
        "title": str(raw.get("title") or ""),
        "description": str(raw.get("description") or ""),
        "track_count": len(tracks),
        "cover_url": pick_thumbnail(raw.get("thumbnails")),
        "tracks": tracks,
    }


def _ytm_tag(filepath, track, album_artist: str = "") -> None:
    """Записать чистые теги YouTube Music + обложку (независимо от yt-dlp)."""
    from ..tagger import AudioTags, apply_cover_from_url, set_tags

    artist = (track.artist or "").strip() or "Неизвестный исполнитель"
    tags = AudioTags(
        title=(track.title or "").strip() or filepath.stem,
        artist=artist,
        album=(track.album or "").strip(),
        album_artist=album_artist or artist,
        year=str(track.year) if track.year else "",
        track_number=str(track.track_number) if track.track_number else "",
        copyright="YouTube Music",
    )
    set_tags(filepath, tags)
    if track.cover_url:
        try:
            apply_cover_from_url(filepath, track.cover_url)
        except Exception:
            pass
    try:
        from ..primuse import maybe_write_sidecars

        maybe_write_sidecars(filepath, tags)
    except Exception:
        pass


@ytm.get("/search")
def api_ytmusic_search(q: str = Query(..., title="Запрос"),
                       limit: int = Query(10, ge=1, le=50, title="Число результатов")):
    """Поиск песен на YouTube Music (работает и без авторизации)."""
    try:
        tracks = _ytm_mod().search_songs(q, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка поиска: {e}")
    keys = _ytm_library_keys()
    return {"tracks": [ytm_track_to_dict(
        t, _ytm_mod().track_in_library(t, keys)) for t in tracks if t.video_id]}


@ytm.get("/radio")
def api_ytmusic_radio(video_id: str = Query(..., min_length=1),
                      limit: int = Query(25, ge=1, le=50, title="Число результатов")):
    """Радио/похожие треки по песне."""
    try:
        tracks = _ytm_mod().watch_playlist(video_id, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка радио: {e}")
    keys = _ytm_library_keys()
    return {"tracks": [ytm_track_to_dict(
        t, _ytm_mod().track_in_library(t, keys)) for t in tracks if t.video_id]}


def _ytm_progress(job, p, label: str, index: int, total: int,
                  state: dict[str, float]) -> None:
    if p.status == "downloading" and p.total_bytes:
        percent = ((index - 1) + p.downloaded_bytes / p.total_bytes) / total * 100
        state["percent"] = max(state["percent"], min(100.0, percent))
        job.push(
            message("jobs.ytm.bytes", {"label": label, "sizeMb": f"{p.downloaded_bytes/(1024*1024):.1f}"}, fallback=f"{label} — {p.downloaded_bytes/(1024*1024):.1f} MB"),
            percent=state["percent"],
        )


@ytm.post("/download")
def api_ytmusic_download(payload: dict):
    """Скачать выбранные треки YouTube Music с чистыми тегами.

    ``items`` — список элементов ``ytm_track_to_dict`` (video_id + метаданные).
    Файлы пишутся с тегами из YouTube Music, обложкой и переносятся в
    библиотеку, затем добавляются в .m3u8-архив ``Плейлисты/<playlist>.m3u8``.
    """
    items = payload.get("items") or []
    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail=message("api.errors.no_tracks", fallback="No tracks"))
    playlist = str(payload.get("playlist") or "YouTube Music").strip() or "YouTube Music"
    fmt = str(payload.get("fmt") or _fmt_default())
    quality = int(payload.get("quality") or _quality_default())
    source = str(payload.get("source") or _source_default())
    move = bool(payload.get("move", True))
    no_clips = bool(payload.get("no_clips", True))

    def run(job):
        from ..pipeline import move_to_library

        mod = _ytm_mod()
        out = _out_dir()
        dl = Downloader(out)
        arch = archive_path(out, playlist)
        results = []
        errors = 0
        progress_state = {"percent": 0.0}

        for i, item in enumerate(items, 1):
            if not isinstance(item, dict):
                continue
            track = mod.track_from_dict(item)
            if not track.video_id:
                continue
            used_video = track.video_id
            resolved_clip = False
            if no_clips and track.video_id and (track.video_type and track.video_type != mod.ATV_TYPE):
                alt = mod.find_audio_version(track)
                if alt and alt.video_id:
                    used_video = alt.video_id
                    track.video_id = alt.video_id
                    track.video_type = alt.video_type
                else:
                    resolved_clip = True
            entry = {"video_id": used_video, "title": track.title,
                     "artist": track.artist, "ok": False,
                     "path": "", "error": "",
                     "kept_clip": resolved_clip}
            label = f"{track.artist} — {track.title}" if track.title else used_video
            progress_code = "jobs.ytm.clip_missing" if resolved_clip else "jobs.ytm.item"
            progress_fallback = f"[{i}/{len(items)}] {label}" + (" (video clip — audio version not found)" if resolved_clip else "")
            job.push(message(progress_code, {"index": i, "total": len(items), "label": label}, fallback=progress_fallback),
                     percent=(i - 1) / len(items) * 100)

            url = f"https://www.youtube.com/watch?v={used_video}"
            res = dl.download(url, fmt, quality,
                              progress_callback=lambda p, l=label, n=i: _ytm_progress(
                                  job, p, l, n, len(items), progress_state),
                              source=source)
            if not res.success or not res.filepath:
                entry["error"] = res.error or message("jobs.download.failed", fallback="Download error")
                errors += 1
                results.append(entry)
                job.push(message("jobs.ytm.item_failed", {"index": i, "total": len(items), "label": label}, fallback=f"[{i}/{len(items)}] error: {label}"),
                         percent=i / len(items) * 100)
                continue

            try:
                _ytm_tag(res.filepath, track,
                         album_artist=str(item.get("album_artist") or ""))
                target = res.filepath
                if move:
                    moved = move_to_library(res.filepath, out)
                    if moved:
                        target = moved
                append_m3u8(arch, target, title=track.title, duration=track.duration)
            except Exception as e:
                entry["error"] = f"Постобработка: {e}"
                errors += 1
                results.append(entry)
                job.push(message("jobs.ytm.item_failed", {"index": i, "total": len(items), "label": label}, fallback=f"[{i}/{len(items)}] error: {label}"),
                         percent=i / len(items) * 100)
                continue
            entry.update(ok=True, path=str(target))
            results.append(entry)
            job.push(message("jobs.ytm.item_downloaded", {"index": i, "total": len(items), "label": label}, fallback=f"[{i}/{len(items)}] downloaded: {label}"),
                     percent=i / len(items) * 100)

        # Дедуп-кэш устарел — сбросить, чтобы «в библиотеке» обновилось.
        _YTM_KEYS_CACHE.pop(str(out), None)
        return {"items": results,
                "ok": sum(1 for r in results if r["ok"]),
                "errors": errors,
                "archive": str(arch) if arch.exists() else ""}

    job = jobs.submit(message("jobs.ytm.name", fallback="YouTube Music — download"), run)
    return {"job_id": job.id, "name": job.name}


# --- Поиск / скачивание --------------------------------------------------


@search_rt.get("/search")
def api_search(q: str = Query(..., title="Запрос"),
                limit: int = Query(10, ge=1, le=50, title="Число результатов")):
    try:
        results = YouTubeSearch(max_results=limit).search(q)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка поиска: {e}")
    return [
        {
            "index": r.index,
            "id": r.info.id,
            "title": r.info.title,
            "uploader": r.info.uploader,
            "duration": r.info.duration,
            "url": r.info.webpage_url or f"https://www.youtube.com/watch?v={r.info.id}",
            "thumbnail": r.info.thumbnail,
        }
        for r in results
    ]


@search_rt.get("/playlist")
def api_playlist(url: str = Query(...)):
    engine = YouTubeSearch()
    try:
        entries = engine.fetch_playlist(url) or []
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка плейлиста: {e}")
    if not entries:
        if engine.last_error:
            raise HTTPException(
                status_code=404,
                detail=f"Плейлист пуст ({engine.last_error})",
            )
        raise HTTPException(
            status_code=404,
            detail=message("api.errors.empty_playlist", fallback="Playlist is empty"),
        )
    return [
        {
            "index": e.index,
            "id": e.info.id,
            "title": e.info.title,
            "uploader": e.info.uploader,
            "duration": e.info.duration,
            "url": e.info.webpage_url or f"https://www.youtube.com/watch?v={e.info.id}",
        }
        for e in entries
    ]


@search_rt.get("/preview")
def api_preview(url: str = Query(...)):
    """Прямой аудио-URL для предпрослушивания (кэшируется на стороне поиска)."""
    from ..search import resolve_preview

    try:
        direct = resolve_preview(url)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"url": direct}


def _info_dict(res) -> dict:
    if res is None:
        return {}
    return {
        "id": res.id, "title": res.title, "uploader": res.uploader,
        "duration": res.duration, "thumbnail": res.thumbnail or "",
        "upload_date": res.upload_date, "url": res.webpage_url or "",
    }


def _apply_youtube_tags(filepath: Path, info) -> None:
    year = info.upload_date[:4] if info.upload_date else ""
    artist = clean_artist_name(info.uploader)
    tags = AudioTags(title=info.title, artist=artist,
                     album=artist, year=year)
    set_tags(filepath, tags)
    try:
        from ..primuse import maybe_write_sidecars

        maybe_write_sidecars(filepath, tags)
    except Exception:
        pass


def _run_download(job, url: str, fmt: str, quality: int, move: bool = False,
                  source: str | None = None):
    dl = Downloader(_out_dir())
    job.push(message("jobs.download.fetching_info", fallback="Fetching video information…"), 0)

    def on_progress(p):
        if p.status == "downloading" and p.total_bytes:
            job.push(
                message("jobs.download.bytes", {"sizeMb": f"{p.downloaded_bytes / (1024*1024):.1f}"}, fallback=f"Downloading… {p.downloaded_bytes / (1024*1024):.1f} MB"),
                percent=p.downloaded_bytes / p.total_bytes * 100,
            )

    result = dl.download(url, fmt, quality, progress_callback=on_progress,
                         source=source)
    if not result.success:
        if result.error:
            raise RuntimeError(result.error)
        raise JobFailure(message("jobs.download.unknown_error", fallback="Unknown error"))
    job.push(message("jobs.download.tagging", fallback="Downloaded; processing tags…"), 100)

    if result.info:
        _apply_youtube_tags(result.filepath, result.info)
        if result.info.thumbnail:
            try:
                apply_cover_from_url(result.filepath, result.info.thumbnail)
            except Exception:
                pass
        try:
            from ..primuse import maybe_write_sidecars

            maybe_write_sidecars(result.filepath)
        except Exception:
            pass

    moved_to = None
    if move:
        moved_to = move_to_library(result.filepath, _out_dir())

    return {
        "filepath": str(result.filepath),
        "in_library": str(moved_to) if moved_to else "",
        "size_bytes": result.filepath.stat().st_size if result.filepath.exists() else 0,
        "info": _info_dict(result.info),
    }


@search_rt.post("/download")
def api_download(payload: dict):
    url = str(payload.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail=message("api.errors.url_required", fallback="URL is required"))
    fmt = str(payload.get("fmt") or _fmt_default())
    quality = int(payload.get("quality") or _quality_default())
    source = str(payload.get("source") or _source_default())
    move = bool(payload.get("move", False))
    job = jobs.submit(
        message("jobs.download.name", fallback="Download"),
        lambda j: _run_download(j, url, fmt, quality, move=move, source=source),
    )
    return {"job_id": job.id, "name": job.name}


def _fmt_default() -> str:
    cfg = load_config()
    return cfg.get("default_format") or DEFAULT_FORMAT


def _quality_default() -> int:
    cfg = load_config()
    return int(cfg.get("default_quality") or DEFAULT_QUALITY)


def _source_default() -> str:
    return get_source_format()


@search_rt.post("/download/batch")
def api_download_batch(payload: dict):
    urls = [str(u).strip() for u in (payload.get("urls") or []) if str(u).strip()]
    if not urls:
        raise HTTPException(status_code=400, detail=message("api.errors.empty_url_list", fallback="URL list is empty"))
    fmt = str(payload.get("fmt") or _fmt_default())
    quality = int(payload.get("quality") or _quality_default())
    source = str(payload.get("source") or _source_default())
    move = bool(payload.get("move", True))

    def run(job):
        dl = Downloader(_out_dir())
        results = [None] * len(urls)
        progress = _BatchProgress(job, urls)

        done = dl.download_many(urls, fmt, quality=quality,
                                max_workers=4, progress_callback=progress.update,
                                source=source)
        for i, (url, res) in enumerate(zip(urls, done), 1):
            item = {"url": url, "ok": False, "error": "", "path": "", "info": {}}
            if res.success and res.filepath:
                if res.info:
                    _apply_youtube_tags(res.filepath, res.info)
                    if res.info.thumbnail:
                        try:
                            apply_cover_from_url(res.filepath, res.info.thumbnail)
                        except Exception:
                            pass
                    try:
                        from ..primuse import maybe_write_sidecars

                        maybe_write_sidecars(res.filepath)
                    except Exception:
                        pass
                target = None
                if move:
                    target = move_to_library(res.filepath, _out_dir())
                item.update(ok=True, path=str(target or res.filepath),
                            info=_info_dict(res.info))
            else:
                item["error"] = res.error or message("jobs.download.failed", fallback="Download error")
            results[i - 1] = item
            progress.complete(url, message("jobs.download.batch_item", {"index": i, "total": len(urls), "url": url[:40]}, fallback=f"[{i}/{len(urls)}] {url[:40]}..."))
        return {"items": results, "ok": sum(1 for r in results if r["ok"])}

    job = jobs.submit(message("jobs.download.batch_name", fallback="Batch download"), run)
    return {"job_id": job.id, "name": job.name}


@search_rt.get("/jobs")
def api_jobs_list(limit: int = Query(30, ge=1, le=50)):
    """Последние фоновые задачи для дока загрузок (новые сверху)."""
    return jobs.list(limit=limit)


@search_rt.get("/jobs/{job_id}/events")
def api_job_events(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=message("api.errors.job_not_found", fallback="Job not found"))
    return job.stream()


@search_rt.get("/jobs/{job_id}")
def api_job_status(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=message("api.errors.job_not_found", fallback="Job not found"))
    return job.to_dict()


# --- Библиотека -----------------------------------------------------------


@library.get("/library")
def api_library(sort: str = Query("path", title="Сортировка")):
    out = _out_dir()
    if not out.exists():
        return []
    records, _errors = scan_library(out)
    target = _quality_default()
    fmt = _fmt_default()
    items = []
    for r in records:
        d = track_to_dict(r)
        d["need_compress"] = should_compress(
            r.path, target, r.stream_bitrate, target_format=fmt)
        d["compress_size_bytes"] = estimate_size(
            r.path, target, r.stream_duration, target_format=fmt)
        items.append(d)
    if sort == "path":
        items.sort(key=lambda i: str(Path(i["path"]).relative_to(out)).casefold())
    elif sort == "title":
        items.sort(key=lambda i: ((i["title"] or "").casefold(),
                                  (i["artist"] or "").casefold(), i["path"].casefold()))
    elif sort == "artist":
        items.sort(key=lambda i: ((i["artist"] or "").casefold(),
                                  (i["title"] or "").casefold(), i["path"].casefold()))
    elif sort == "added":
        items.sort(key=lambda i: (i.get("mtime") or 0, i["path"].casefold()), reverse=True)
    elif sort == "year":
        items.sort(key=lambda i: (i.get("year") or "", (i.get("artist") or "").casefold(),
                                  (i.get("title") or "").casefold()), reverse=True)
    elif sort == "size":
        items.sort(key=lambda i: (i.get("size_bytes") or 0, i["path"].casefold()), reverse=True)
    return items


@library.get("/library/album-nfo")
def api_library_album_nfo(path: str = Query(...)):
    """Метаданные album.nfo из папки локального альбома."""
    nfo_path = _get_file(path).parent / "album.nfo"
    if not nfo_path.is_file():
        return {"review": "", "styles": []}
    try:
        root = ET.fromstring(nfo_path.read_bytes())
    except (OSError, ET.ParseError):
        return {"review": "", "styles": []}

    review = ""
    styles = []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        text = (node.text or "").strip()
        if tag == "review" and text:
            review = text
        elif tag == "style" and text:
            styles.append(text)
    return {"review": review, "styles": styles}


@library.get("/library/inbox")
def api_library_inbox():
    """Файлы во временной папке ``Inbox`` — ещё не обработанная загрузка."""
    from ..config import inbox_dir

    inbox = inbox_dir(_out_dir())
    if not inbox.exists():
        return []
    records, _ = scan_directory(inbox)
    target = _quality_default()
    fmt = _fmt_default()
    items = []
    for r in records:
        d = track_to_dict(r)
        d["need_compress"] = should_compress(
            r.path, target, r.stream_bitrate, target_format=fmt)
        d["compress_size_bytes"] = estimate_size(
            r.path, target, r.stream_duration, target_format=fmt)
        items.append(d)
    return items


def _quality_issue_dict(issue) -> dict:
    return {
        "category": issue.category,
        "path": str(issue.path),
        "message": issue.message,
        "severity": issue.severity,
        "auto_fixable": issue.auto_fixable,
        "inbox": issue.inbox,
    }


def _quality_change_dict(change) -> dict:
    return {
        "field": change.field,
        "path": str(change.path),
        "old": change.old_value,
        "new": change.new_value,
        "cause": change.cause,
    }


def _str_list(value) -> list[str] | None:
    """Строки из JSON-списка; пустое/неверное → None (без фильтра)."""
    if not isinstance(value, list):
        return None
    items = [str(v) for v in value if str(v or "").strip()]
    return items or None


def _quality_scope(payload: dict) -> dict:
    """Фильтры плана из запроса: пути, категории и конкретные изменения."""
    return {
        "include_inbox": bool(payload.get("include_inbox")),
        "paths": _str_list(payload.get("paths")),
        "categories": _str_list(payload.get("categories")),
        "change_keys": payload.get("changes") or None,
    }


@library.get("/library/quality")
def api_library_quality(include_inbox: bool = Query(False)):
    """Единый отчёт о проблемах библиотеки и план нормализации тегов."""
    report = collect_quality(_out_dir(), include_inbox=include_inbox)
    tracks = []
    for track in report.tracks():
        tracks.append({
            **track,
            "issues": [_quality_issue_dict(issue) for issue in track["issues"]],
            "changes": [_quality_change_dict(change) for change in track["changes"]],
        })
    return {
        "total": report.total,
        "counts": report.counts,
        "issues": [_quality_issue_dict(issue) for issue in report.issues],
        "changes": [_quality_change_dict(change) for change in report.changes],
        "tracks": tracks,
    }


def _quality_plan_dict(plan) -> dict:
    """DTO плана: файлы, изменения, авто-фиксы и конфликты."""
    return {
        "files": [str(p) for p in plan.files],
        "changes": [_quality_change_dict(change) for change in plan.changes],
        "fixes": [{
            "path": str(fix.path),
            "action": fix.action,
            "category": fix.category,
            "from": str(fix.path),
            "to": str(fix.target),
            "message": fix.message,
        } for fix in plan.fixes],
        "conflicts": [{
            "path": str(c.path),
            "kind": c.kind,
            "field": c.field,
            "target": c.target,
            "message": c.message,
        } for c in plan.conflicts],
        "counts": {
            "files": len(plan.files),
            "changes": len(plan.changes),
            "fixes": len(plan.fixes),
            "conflicts": len(plan.conflicts),
        },
    }


_EMPTY_PLAN = {
    "files": [], "changes": [], "fixes": [], "conflicts": [],
    "counts": {"files": 0, "changes": 0, "fixes": 0, "conflicts": 0},
}


@library.post("/library/quality/plan")
def api_library_quality_plan(payload: dict):
    """План изменений для выбранных путей/категорий — без записи в файлы."""
    out = _out_dir()
    if not out.exists():
        return dict(_EMPTY_PLAN)
    plan = build_quality_plan(out, **_quality_scope(payload))
    return _quality_plan_dict(plan)


@library.post("/library/quality/apply")
def api_library_quality_apply(payload: dict):
    """Применить план: теги и авто-фиксы; результат по каждому файлу."""
    out = _out_dir()
    if not out.exists():
        raise HTTPException(status_code=400, detail=message("api.errors.library_directory_not_found", fallback="Library directory not found"))
    plan = build_quality_plan(out, **_quality_scope(payload))
    return apply_quality_plan(plan, out)


@library.get("/tags")
def api_tags(path: str = Query(...)):
    fp = _get_file(path)
    try:
        tags = get_tags(fp)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось прочитать теги: {e}")
    return tags_to_dict(tags, name=fp.name)


_INT_FIELDS = {"track_number", "disc_number"}


def _validate_tag_fields_map(fields: dict) -> dict[str, dict[str, Any]]:
    """Привести значения к строкам, вернуть ``{field: сообщение об ошибке}``."""
    errors: dict[str, dict[str, Any]] = {}
    for field, value in fields.items():
        value = str(value or "").strip()
        fields[field] = value
        if not value:
            continue
        if field == "year" and not (len(value) == 4 and value.isdigit()):
            errors[field] = message(
                "api.fields.year_four_digits",
                fallback="Year must be four digits, e.g. 2024",
            )
        elif field in _INT_FIELDS and not value.isdigit():
            errors[field] = message(
                "api.fields.integer_required",
                fallback="Must be an integer",
            )
    return errors


def _apply_cover(current: AudioTags, cover_url: str,
                 thumbnail_url: str) -> tuple[bytes | None, str]:
    """Скачать обложку из источника (фолбэк — thumbnail). Вернуть (data, mime).

    Байты возвращаются напрямую, без промежуточной записи в файл — встраивает
    их одним сохранением ``set_tags``. Thumbnail качается, только если у трека
    ещё нет обложки: она не должна затираться при ошибке основного источника.
    """
    cover_data, cover_mime = current.cover_data, current.cover_mime
    if cover_url:
        try:
            from ..fetcher import download_cover
            cover_data, cover_mime = download_cover(cover_url)
        except Exception:
            pass
    if not cover_data and thumbnail_url:
        try:
            from ..fetcher import download_thumbnail
            cover_data, cover_mime = download_thumbnail(thumbnail_url)
        except Exception:
            pass
    return cover_data, cover_mime


def _compose_tags(current: AudioTags, fields: dict,
                  cover_data: bytes | None = None,
                  cover_mime: str = "") -> AudioTags:
    """Собрать теги: пустое значение поля очищает тег (replace-семантика)."""
    return AudioTags(
        title=fields.get("title", current.title),
        artist=fields.get("artist", current.artist),
        album=fields.get("album", current.album),
        year=fields.get("year", current.year),
        track_number=fields.get("track_number", current.track_number),
        genre=fields.get("genre", current.genre),
        comment=fields.get("comment", current.comment),
        album_artist=fields.get("album_artist", current.album_artist),
        disc_number=fields.get("disc_number", current.disc_number),
        isrc=fields.get("isrc", current.isrc),
        composer=fields.get("composer", current.composer),
        publisher=fields.get("publisher", current.publisher),
        copyright=current.copyright, lyrics=current.lyrics,
        lyrics_synced=current.lyrics_synced,
        cover_data=cover_data if cover_data is not None else current.cover_data,
        cover_mime=cover_mime or current.cover_mime,
    )


@library.put("/tags")
def api_put_tags(payload: dict):
    fp = _get_file(str(payload.get("path") or ""))
    fields = payload.get("fields") or {}
    if not isinstance(fields, dict):
        raise HTTPException(status_code=400, detail=message("api.errors.fields_must_be_object", fallback="fields must be an object"))

    errors = _validate_tag_fields_map(fields)
    if errors:
        raise HTTPException(status_code=400, detail=next(iter(errors.values())))

    current = get_tags(fp)
    new = _compose_tags(current, fields)
    if not set_tags(fp, new):
        raise HTTPException(status_code=500, detail=message("api.errors.write_tags_failed", fallback="Could not write tags"))
    try:
        from ..primuse import maybe_write_sidecars

        maybe_write_sidecars(fp, new)
    except Exception:
        pass
    return tags_to_dict(new, name=fp.name)


@library.post("/tags/apply")
def api_tags_apply(payload: dict):
    """Единое сохранение редактора: теги (replace) + опционально обложка."""
    fp = _get_file(str(payload.get("path") or ""))
    fields = payload.get("fields") or {}
    if not isinstance(fields, dict):
        raise HTTPException(status_code=400, detail=message("api.errors.fields_must_be_object", fallback="fields must be an object"))

    apply_cover = payload.get("apply_cover", True)
    cover_url = str(payload.get("cover_url") or "")
    cover_from = str(payload.get("cover_from") or "")
    thumbnail_url = str(payload.get("thumbnail_url") or "")
    uploaded_cover = str(payload.get("cover_data") or "")
    uploaded_cover_mime = str(payload.get("cover_mime") or "")

    errors = _validate_tag_fields_map(fields)
    if errors:
        return JSONResponse(
            status_code=400,
            content={
                "detail": message("api.errors.check_fields", fallback="Check the fields"),
                "errors": errors,
            },
        )

    current = get_tags(fp)
    cover_data, cover_mime = current.cover_data, current.cover_mime
    if apply_cover:
        if uploaded_cover:
            if uploaded_cover_mime not in {"image/jpeg", "image/png"}:
                raise HTTPException(status_code=400, detail=message("api.errors.cover_format", fallback="Only JPEG and PNG are supported"))
            try:
                cover_data = base64.b64decode(uploaded_cover, validate=True)
            except ValueError:
                raise HTTPException(status_code=400, detail=message("api.errors.invalid_cover", fallback="Invalid cover file"))
            if not cover_data:
                raise HTTPException(status_code=400, detail=message("api.errors.empty_cover", fallback="Cover file is empty"))
            cover_mime = uploaded_cover_mime
        # Файл не пишется — перечитывание не нужно.
        elif cover_from:
            # Обложка из другого трека (кнопка «Обложка для альбома»).
            try:
                src_tags = get_tags(_get_file(cover_from))
                if src_tags.cover_data:
                    cover_data, cover_mime = src_tags.cover_data, src_tags.cover_mime
            except Exception:
                pass
        else:
            cover_data, cover_mime = _apply_cover(current, cover_url, thumbnail_url)

    new = _compose_tags(current, fields, cover_data, cover_mime)
    if not set_tags(fp, new):
        raise HTTPException(status_code=500, detail=message("api.errors.write_tags_failed", fallback="Could not write tags"))
    try:
        from ..primuse import maybe_write_sidecars

        maybe_write_sidecars(fp, new)
    except Exception:
        pass
    return tags_to_dict(new, name=fp.name)


@library.get("/cover")
def api_cover(path: str = Query(...)):
    fp = _get_file(path)
    try:
        tags = get_tags(fp)
    except Exception:
        raise HTTPException(status_code=500, detail=message("api.errors.read_tags_failed", fallback="Could not read tags"))
    if not tags.cover_data:
        raise HTTPException(status_code=404, detail=message("api.errors.cover_not_found", fallback="No cover art"))
    return Response(content=tags.cover_data,
                    media_type=tags.cover_mime or "image/jpeg")


@library.get("/lyrics")
def api_lyrics(path: str = Query(...)):
    fp = _get_file(path)
    try:
        tags = get_tags(fp)
    except Exception:
        raise HTTPException(status_code=500, detail=message("api.errors.read_tags_failed", fallback="Could not read tags"))
    return {"path": str(fp), "lyrics": tags.lyrics or "",
            "synced_lyrics": tags.lyrics_synced or "",
            "title": tags.title, "artist": tags.artist}


@library.post("/lyrics/update")
def api_lyrics_update(payload: dict):
    """Обновить текст одного трека (или передвинуть в библиотеку после)."""
    fp = _get_file(str(payload.get("path") or ""))
    ok = fetch_and_apply_lyrics(fp)
    return {"path": str(fp), "updated": ok}


@library.get("/lyrics/missing")
def api_lyrics_missing():
    """Список треков без синхронного текста (для экрана «Тексты»)."""
    out = _out_dir()
    if not out.exists():
        return {"total": 0, "missing": []}
    candidates, _errors, total = services.collect_lyrics_candidates(out)
    snapshot = uuid.uuid4().hex
    now = time.monotonic()
    with _lyrics_snapshots_lock:
        _lyrics_snapshots.clear()
        _lyrics_snapshots[snapshot] = (now + _LYRICS_SNAPSHOT_TTL, out, candidates)
    missing = [{key: candidate[key] for key in ("path", "title", "artist", "has_plain")}
               for candidate in candidates]
    return {"total": total, "missing": missing, "snapshot": snapshot}


@library.post("/lyrics/update-all")
def api_lyrics_update_all(payload: dict | None = None):
    """Пакетно обновить тексты для треков без них (LRCLIB)."""

    def run(job):
        out = _out_dir()
        candidates = None
        snapshot = str((payload or {}).get("snapshot") or "")
        if snapshot:
            with _lyrics_snapshots_lock:
                entry = _lyrics_snapshots.get(snapshot)
                if entry and entry[0] > time.monotonic() and entry[1] == out:
                    candidates = entry[2]

        def on_progress(i, total, path):
            job.push(message("jobs.lyrics.item", {"index": i, "total": total, "filename": Path(path).name}, fallback=f"[{i}/{total}] {Path(path).name}"), percent=i / total * 100)

        kwargs = {"on_progress": on_progress}
        if candidates is not None:
            kwargs["candidates"] = candidates
        result = services.update_all_lyrics(out, **kwargs)
        return result

    job = jobs.submit(message("jobs.lyrics.name", fallback="Update lyrics"), run)
    return {"job_id": job.id, "name": job.name}


@library.post("/library/move")
def api_library_move(payload: dict):
    fp = _get_file(str(payload.get("path") or ""))
    target = move_to_library(fp, _out_dir())
    if not target:
        raise HTTPException(status_code=409,
                             detail=message("api.errors.move_failed", fallback="Could not move file (name conflict or missing tags)"))
    return {"from": str(fp), "to": str(target)}


@library.post("/library/sort/plan")
def api_library_sort_plan():
    """План раскладки по папкам: список переносов без записи в файловую систему."""
    out = _out_dir()
    plan = services.plan_sort_library(out)
    limit = 200
    moves = [{"from": str(src), "to": str(dst)} for src, dst in plan[:limit]]
    return {
        "total": len(plan),
        "moves": moves,
        "truncated": len(plan) > limit,
        "output_dir": str(out),
    }


@library.post("/library/sort")
def api_library_sort():
    job = jobs.submit(
        message("jobs.library.sort_name", fallback="Sort library"),
        lambda j: _run_sort(j),
    )
    return {"job_id": job.id, "name": job.name}


def _run_sort(job):
    out = _out_dir()
    moved, removed = services.sort_library(out)
    job.push(message("jobs.common.done", fallback="Done"))
    return {"moved": moved, "removed_dirs": removed, "output_dir": str(out)}


@library.post("/library/dedup")
def api_library_dedup(payload: dict):
    mode = str(payload.get("mode") or "md5")
    if mode not in ("md5", "semantic"):
        raise HTTPException(status_code=400, detail=message("api.errors.invalid_dedup_mode", fallback="Invalid deduplication mode"))
    groups = services.dedup_groups(mode, _out_dir())
    if not groups:
        return {"mode": mode, "groups": []}
    data = []
    for paths in groups:
        best = services.best_in_group(paths, mode) if len(paths) > 1 else paths[0]
        data.append({
            "best": str(best),
            "files": [
                {"path": str(p), "label": services.dedup_label(p), "is_best": p == best}
                for p in paths
            ],
        })
    return {"mode": mode, "groups": data}


@library.post("/library/dedup/delete")
def api_library_dedup_delete(payload: dict):
    paths = [str(p) for p in (payload.get("paths") or [])]
    deleted = 0
    errors = []
    for raw in paths:
        try:
            p = Path(raw)
            try:
                from ..primuse import delete_sidecars

                delete_sidecars(p)
            except Exception:
                pass
            p.unlink()
            deleted += 1
        except Exception as e:
            errors.append(str(e))
    return {"deleted": deleted, "errors": errors}


@library.delete("/library/track")
def api_library_track_delete(path: str = Query(...)):
    fp = _get_file(path)
    try:
        from ..primuse import delete_sidecars

        delete_sidecars(fp)
    except Exception:
        pass
    try:
        fp.unlink()
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Не удалось удалить файл: {e}")
    from ..services import delete_empty_dirs
    delete_empty_dirs(_out_dir())
    return {"deleted": str(fp)}


@library.post("/library/merge")
def api_library_merge(payload: dict):
    paths = [Path(p) for p in (payload.get("paths") or [])]
    album = str(payload.get("album") or "")
    album_artist = str(payload.get("album_artist") or "Various Artists")
    if not paths:
        raise HTTPException(status_code=400, detail=message("api.errors.no_tracks", fallback="No tracks"))
    done = 0
    for i, p in enumerate(paths, 1):
        if not p.is_file():
            continue
        try:
            tags = get_tags(p)
            tags.album = album
            tags.album_artist = album_artist
            tags.track_number = str(i)
            if set_tags(p, tags):
                done += 1
                try:
                    from ..primuse import maybe_write_sidecars

                    maybe_write_sidecars(p, tags)
                except Exception:
                    pass
        except Exception:
            pass
    return {"merged": done}


@library.post("/library/merge-albums/scan")
def api_merge_albums_scan():
    """Найти группы треков с одинаковым названием альбома (≥2 треков)."""
    records, _errors = scan_library(_out_dir())
    groups: dict[str, list] = {}
    for r in records:
        key = (r.album or "").strip().lower()
        if not key:
            continue
        groups.setdefault(key, []).append(r)
    data = []
    for key, rs in groups.items():
        if len(rs) < 2:
            continue
        single_artist = len({r.artist for r in rs if (r.artist or "").strip()}) <= 1
        aa = [r.album_artist.strip() for r in rs]
        merged = bool(aa) and len({a.lower() for a in aa}) == 1 and all(aa)
        if single_artist or merged:
            continue
        artists = sorted({r.artist for r in rs if r.artist})
        data.append({
            "album": rs[0].album,
            "artists": artists,
            "mixed": len(artists) > 1,
            "files": [
                {"path": str(r.path), "title": r.title, "artist": r.artist,
                 "track_number": r.track_number, "disc_number": r.disc_number}
                for r in sorted(rs, key=lambda r: (_num_sort_key(r.disc_number), _num_sort_key(r.track_number), (r.title or "").lower()))
            ],
        })
    data.sort(key=lambda g: (g["album"] or "").lower())
    return {"groups": data}


@library.post("/library/merge-albums/apply")
def api_merge_albums_apply(payload: dict):
    """Объединить переданные группы: проставить album/album_artist + track_number."""
    groups = payload.get("groups") or []
    if not groups:
        raise HTTPException(status_code=400, detail=message("api.errors.no_groups", fallback="No groups"))
    done = 0
    for g in groups:
        paths = [Path(p) for p in (g.get("paths") or [])]
        album = str(g.get("album") or "").strip()
        album_artist = str(g.get("album_artist") or "").strip()
        for i, p in enumerate(sorted(paths, key=str), 1):
            if not p.is_file():
                continue
            try:
                tags = get_tags(p)
                if album:
                    tags.album = album
                if album_artist:
                    tags.album_artist = album_artist
                tags.track_number = str(i)
                if set_tags(p, tags):
                    done += 1
                    try:
                        from ..primuse import maybe_write_sidecars

                        maybe_write_sidecars(p, tags)
                    except Exception:
                        pass
            except Exception:
                pass
    return {"merged": done}


#: Кэш /api/fetch/meta по (title, artist): повторное открытие редактора того же
#: трека (или соседнего трека альбома при совпадении) не должно бить по сети.
#: Результаты хранятся по источникам — редактор запрашивает их параллельно
#: по одному и рендерит по мере ответа, не дожидаясь самого медленного.
#: TTL и размер — консервативные, данные источников меняются годами, не минут.
_META_CACHE: dict[tuple[str, str], tuple[float, dict[str, list[dict]]]] = {}
_META_CACHE_TTL = 30 * 60.0
_META_CACHE_LIMIT = 256
_META_CACHE_LOCK = threading.Lock()


def _meta_cache_get(key: tuple[str, str]) -> dict[str, list[dict]] | None:
    with _META_CACHE_LOCK:
        hit = _META_CACHE.get(key)
        if not hit:
            return None
        ts, by_source = hit
        if time.monotonic() - ts > _META_CACHE_TTL:
            _META_CACHE.pop(key, None)
            return None
        return by_source


def _meta_cache_put(key: tuple[str, str], by_source: dict[str, list[dict]]) -> None:
    with _META_CACHE_LOCK:
        if len(_META_CACHE) >= _META_CACHE_LIMIT:
            _META_CACHE.clear()
        _META_CACHE[key] = (time.monotonic(), dict(by_source))


def meta_cache_clear() -> None:
    """Сбросить кэш метаданных (для тестов)."""
    with _META_CACHE_LOCK:
        _META_CACHE.clear()


@library.post("/fetch/meta")
def api_fetch_meta(payload: dict):
    fp = _get_file(str(payload.get("path") or ""))
    thumbnail = str(payload.get("thumbnail_url") or "")
    only = payload.get("sources")
    if only is not None and not isinstance(only, list):
        raise HTTPException(status_code=400, detail=message("api.errors.expected_list", {"field": "sources"}, fallback="sources must be a list of sources"))
    try:
        current = get_tags(fp)
    except Exception:
        raise HTTPException(status_code=500, detail=message("api.errors.read_tags_failed", fallback="Could not read tags"))
    if not current.title:
        return {"path": str(fp), "records": [], "thumbnail_url": thumbnail}
    known = available_sources()
    if only is None:
        wanted = [s for s in get_metadata_sources() if s in known]
    else:
        wanted = [s for s in dict.fromkeys(str(s).strip() for s in only)
                  if s in known]
    key = (current.title.strip().lower(), (current.artist or "").strip().lower())
    by_source = dict(_meta_cache_get(key) or {})
    missing = [s for s in wanted if s not in by_source]
    if missing:
        try:
            results = fetch_all(current.title, current.artist or "",
                                sources=missing)
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))
        by_source.update({
            name: [record_to_dict(rec) for rec in recs]
            for name, recs in results.items()
        })
        for name in missing:
            by_source.setdefault(name, [])
        _meta_cache_put(key, by_source)
    records = [rec for name in wanted for rec in by_source.get(name, [])]
    return {"path": str(fp), "records": records,
            "thumbnail_url": thumbnail, "query": current.title}


@library.post("/fetch/apply")
def api_fetch_apply(payload: dict):
    fp = _get_file(str(payload.get("path") or ""))
    fields = payload.get("fields") or {}
    source = str(payload.get("source") or "")
    cover_url = str(payload.get("cover_url") or "")
    thumbnail_url = str(payload.get("thumbnail_url") or "")

    new = services.apply_meta_fields(
        fp, {k: str(v) for k, v in fields.items()},
        source=source, cover_url=cover_url, thumbnail_url=thumbnail_url,
    )
    if new is None:
        raise HTTPException(status_code=500, detail=message("api.errors.write_tags_failed", fallback="Could not write tags"))
    return tags_to_dict(new, name=fp.name)


# --- Отчёты ---------------------------------------------------------------


def _issue_list_by_cat(by_cat: dict[str, list]) -> dict[str, list[dict]]:
    return {
        cat: [{"path": str(i.path), "message": i.message} for i in issues]
        for cat, issues in by_cat.items()
    }


@misc.get("/health")
def api_health(include_inbox: bool = Query(False)):
    out = _out_dir()
    if not out.exists():
        return {"total": 0, "score": 100, "issues": {}, "counts": {}}
    report = run_health_check(out, include_inbox=include_inbox)
    counts = {cat: len(issues) for cat, issues in report.issues_by_category.items()}
    return {
        "total": report.total,
        "score": report.score,
        "counts": counts,
        "issues": _issue_list_by_cat(report.issues_by_category),
    }


@misc.post("/health/fix")
def api_health_fix(payload: dict):
    """Фикс: переименование по тегам + перенос в Artist/Album."""
    fixed, errors = fix_issues(_out_dir())
    return {"fixed": fixed, "errors": errors}


@misc.get("/lint")
def api_lint(include_inbox: bool = Query(False)):
    out = _out_dir()
    if not out.exists():
        return {"total": 0, "counts": {}, "issues": {}}
    report = lint_library(out, include_inbox=include_inbox)
    counts = {cat: len(issues) for cat, issues in report.issues_by_category.items()}
    return {
        "total": report.total,
        "counts": counts,
        "issues": _issue_list_by_cat(report.issues_by_category),
    }


@misc.get("/normalize/plan")
def api_normalize_plan(include_inbox: bool = Query(False)):
    out = _out_dir()
    if not out.exists():
        return {"count": 0, "changes": []}
    plan = normalize_library(out, include_inbox=include_inbox)
    changes = [{
        "field": c.field, "path": str(c.path), "old": c.old_value,
        "new": c.new_value, "cause": c.cause,
    } for c in plan.changes]
    return {"count": plan.count, "changes": changes}


@misc.post("/normalize/apply")
def api_normalize_apply(payload: dict):
    """Применить нормализацию (все изменения или выбранные по ``causes``)."""
    out = _out_dir()
    plan = normalize_library(out, include_inbox=bool(payload.get("include_inbox")))
    causes = payload.get("causes") or None
    applied, errors = apply_plan(plan, causes=causes)
    return {"applied": applied, "errors": errors}


# --- Сжатие ----------------------------------------------------------------


@misc.get("/compress/list")
def api_compress_list():
    out = _out_dir()
    if not out.exists():
        return {"audio": [], "covers": 0}
    from ..analytics import library_files

    target = _quality_default()
    fmt = _fmt_default()
    audio = []
    covers = 0
    for f in library_files(out):
        try:
            tags = get_tags(f)
        except Exception:
            continue
        title = tags.title or f.stem
        artist = tags.artist or ""
        size = f.stat().st_size
        flag = should_compress(f, target, target_format=fmt)
        audio.append({
            "path": str(f), "title": title, "artist": artist,
            "size_bytes": size,
            "estimate_bytes": estimate_size(f, target, target_format=fmt),
            "compress": flag,
        })
        if tags.cover_data:
            covers += 1
    audio.sort(key=lambda i: (not i["compress"], i["title"].lower()))
    return {"audio": audio, "covers": covers}


@misc.post("/compress")
def api_compress(payload: dict):
    mode = str(payload.get("mode") or "audio")
    paths = [Path(p) for p in (payload.get("paths") or [])]
    if not paths:
        raise HTTPException(status_code=400, detail=message("api.errors.no_files", fallback="No files"))

    def run(job):
        target = _quality_default()
        fmt = _fmt_default()
        done = skipped = 0
        for i, p in enumerate(paths, 1):
            if not p.is_file():
                continue
            try:
                ok = (compress_file(p, target, target_format=fmt) is not None) \
                    if mode == "audio" else compress_covers(p)
            except Exception:
                ok = False
            if ok:
                done += 1
            else:
                skipped += 1
            job.push(message("jobs.compress.item", {"index": i, "total": len(paths)}, fallback=f"[{i}/{len(paths)}]"), percent=i / len(paths) * 100)
        label = message("jobs.compress.audio_result" if mode == "audio" else "jobs.compress.cover_result", fallback="Audio compressed" if mode == "audio" else "Covers recompressed")
        return {"done": done, "skipped": skipped, "label": label}

    job = jobs.submit(message("jobs.compress.name", fallback="Compression"), run)
    return {"job_id": job.id, "name": job.name}


# --- Primuse -----------------------------------------------------------------


@misc.post("/primuse/backfill")
def api_primuse_backfill():
    """Создать sidecar .lrc + -cover.jpg для всей библиотеки."""

    def run(job):
        from .. import primuse as primuse_mod

        out = _out_dir()

        def on_progress(i, total, path):
            job.push(message("jobs.primuse.backfill_item", {"index": i, "total": total, "filename": Path(path).name}, fallback=f"[{i}/{total}] {Path(path).name}"), percent=i / total * 100)

        result = primuse_mod.backfill_library(out, on_progress=on_progress)
        job.push(message("jobs.common.done", fallback="Done"), 100)
        return result

    job = jobs.submit(message("jobs.primuse.backfill_name", fallback="Primuse — sidecars"), run)
    return {"job_id": job.id, "name": job.name}


@misc.get("/primuse/cleanup/preview")
def api_primuse_cleanup_preview():
    """Посчитать sidecar-файлы без удаления."""
    from .. import primuse as primuse_mod

    return primuse_mod.preview_cleanup(_out_dir())


@misc.post("/primuse/cleanup")
def api_primuse_cleanup():
    """Удалить все *.lrc и *-cover.jpg в библиотеке (включая Inbox)."""

    def run(job):
        from .. import primuse as primuse_mod

        job.push(message("jobs.primuse.scanning", fallback="Scanning sidecar files…"), 0)
        result = primuse_mod.cleanup_library(_out_dir())
        job.push(message("jobs.common.done", fallback="Done"), 100)
        return result

    job = jobs.submit(message("jobs.primuse.cleanup_name", fallback="Primuse — cleanup"), run)
    return {"job_id": job.id, "name": job.name}


# --- Shazam ----------------------------------------------------------------


class _ShazamHitInfo:
    """Адаптер YTMTrack под форму результата yt-dlp (``.info``) для матчинга:
    ``find_youtube_matches``/``score_match`` ждут ``.info.id/.title`` и т.д."""

    def __init__(self, track) -> None:
        url = f"https://www.youtube.com/watch?v={track.video_id}"
        self.info = SimpleNamespace(
            id=track.video_id, title=track.title, uploader=track.artist,
            duration=track.duration or 0, webpage_url=url,
            video_id=track.video_id, cover_url=track.cover_url,
            album=track.album, video_type=track.video_type,
        )


def _shazam_search_fn(engine: YouTubeSearch):
    """Поиск совпадений для Shazam: сначала YouTube Music
    (чистые названия, альбомы, пометка «в библиотеке»), при ошибке —
    обычный yt-dlp поиск без авторизации."""

    def search(query: str):
        try:
            return [_ShazamHitInfo(t)
                    for t in _ytm_mod().search_songs(query, limit=5)]
        except Exception:
            return engine.search(query)

    return search


def _shazam_hit_dict(entry, result) -> dict:
    """Единая выдача совпадения для экрана (YouTube Music и yt-dlp)."""
    info = result.info
    return {
        "id": info.id,
        "video_id": getattr(info, "video_id", "") or "",
        "title": info.title,
        "uploader": info.uploader,
        "duration": info.duration,
        "url": info.webpage_url or f"https://www.youtube.com/watch?v={info.id}",
        "cover_url": getattr(info, "cover_url", "")
        or getattr(info, "thumbnail", "") or "",
        "album": getattr(info, "album", "") or "",
        "score": round(score_match(entry, result), 2),
    }


@misc.post("/shazam/scan")
def api_shazam_scan(payload: dict = None):
    out = _out_dir()

    def run(job):
        path = get_shazam_file()
        if not path or not path.exists():
            raise JobFailure(message("jobs.shazam.file_missing", fallback="Shazam file is not set or found — specify its path in Settings"))
        entries = parse_shazam_file(path)
        if not entries:
            raise JobFailure(message("jobs.shazam.empty_file", fallback="File is empty or contains no recognized tracks"))
        engine = YouTubeSearch(max_results=5)
        job.push(message("jobs.shazam.scanning", {"count": len(entries)}, fallback=f"Searching for {len(entries)} tracks in YouTube Music…"), 0)
        matches = find_youtube_matches(entries, _shazam_search_fn(engine))
        data = []
        for i, (entry, found) in enumerate(matches, 1):
            job.push(message("jobs.shazam.processed", {"index": i, "total": len(entries)}, fallback=f"Processed {i}/{len(entries)}"), percent=i / len(entries) * 100)
            data.append({
                "index": entry.index,
                "line_number": entry.line_number,
                "title": entry.title,
                "artist": entry.artist,
                "display": entry.display,
                "found": [_shazam_hit_dict(entry, r) for r in found],
            })
        return {"entries": data, "file": str(path)}

    job = jobs.submit(message("jobs.shazam.scan_name", fallback="Shazam — search"), run)
    return {"job_id": job.id, "name": job.name}


@misc.post("/shazam/remove")
def api_shazam_remove(payload: dict):
    """Удалить распознанную строку из файла (после успешного скачивания)."""
    line_number = int(payload.get("line_number") or 0)
    if line_number <= 0:
        raise HTTPException(status_code=400, detail=message("api.errors.invalid_line_number", fallback="Invalid line number"))
    src_path = get_shazam_file()
    if not src_path or not src_path.is_file():
        raise HTTPException(status_code=404, detail=message("api.errors.file_missing", fallback="File not found"))
    removed = remove_shazam_lines(src_path, {line_number})
    return {"removed": removed}


@misc.post("/shazam/download")
def api_shazam_download(payload: dict):
    """``selection``: {index: result_index} — какой результат YouTube брать."""
    selection = payload.get("selection") or {}
    if not isinstance(selection, dict) or not selection:
        raise HTTPException(status_code=400, detail=message("api.errors.nothing_selected", fallback="Nothing selected"))
    fmt = str(payload.get("fmt") or _fmt_default())
    quality = int(payload.get("quality") or _quality_default())
    src_fmt = str(payload.get("source_format") or _source_default())

    def run(job):
        src_path = get_shazam_file()
        if not src_path:
            raise JobFailure(message("jobs.shazam.file_unset", fallback="Shazam file is not set"))
        entries = parse_shazam_file(src_path)
        by_index = {e.index: e for e in entries}
        # Ищем заново: матчи не храним между запросами.
        engine = YouTubeSearch(max_results=5)
        matches = find_youtube_matches(entries, _shazam_search_fn(engine))
        urls = []
        chosen: list[tuple[int, int]] = []
        for idx_str, res_idx in selection.items():
            idx = int(idx_str)
            res = int(res_idx)
            entry = by_index.get(idx)
            if entry is None:
                continue
            for e, found in matches:
                if e.index != idx or not found or res >= len(found):
                    continue
                result = found[res]
                urls.append(result.info.webpage_url or
                            f"https://www.youtube.com/watch?v={result.info.id}")
                chosen.append((idx, entry.line_number))
                break

        dl = Downloader(_out_dir())
        progress = _BatchProgress(job, urls)
        done = dl.download_many(urls, fmt, quality=quality,
                                max_workers=4,
                                progress_callback=progress.update,
                                source=src_fmt)
        ok_indexes: set[int] = set()
        downloaded = 0
        errors = 0
        for item_no, ((idx, line_no), result) in enumerate(zip(chosen, done), 1):
            progress.complete(
                urls[item_no - 1],
                message("jobs.download.batch_complete", {"index": item_no, "total": len(urls), "label": "Shazam"}, fallback=f"[{item_no}/{len(urls)}] Shazam"),
            )
            if not result.success or not result.filepath:
                errors += 1
                continue
            downloaded += 1
            ok_indexes.add(line_no)
            if result.info:
                _apply_youtube_tags(result.filepath, result.info)
                if result.info.thumbnail:
                    try:
                        apply_cover_from_url(result.filepath, result.info.thumbnail)
                    except Exception:
                        pass
                try:
                    from ..primuse import maybe_write_sidecars

                    maybe_write_sidecars(result.filepath)
                except Exception:
                    pass
            move_to_library(result.filepath, _out_dir())

        removed = 0
        if ok_indexes:
            removed = remove_shazam_lines(src_path, ok_indexes)
        return {"downloaded": downloaded, "errors": errors,
                "removed_lines": removed}

    job = jobs.submit(message("jobs.shazam.download_name", fallback="Shazam — download"), run)
    return {"job_id": job.id, "name": job.name}


class _BatchProgress:
    """Потокобезопасный общий прогресс параллельного скачивания."""

    def __init__(self, job, urls: list[str]) -> None:
        self.job = job
        self.urls = urls
        self._positions = {url: i for i, url in enumerate(urls, 1)}
        self._progress = {url: 0.0 for url in urls}
        self._last_percent = 0.0
        self._lock = threading.Lock()

    def _push(self, url: str, msg: str | dict[str, Any]) -> None:
        percent = max(self._last_percent, min(100.0,
            sum(self._progress.values()) / len(self.urls)))
        self._last_percent = percent
        self.job.push(msg, percent=percent)

    def update(self, url, p) -> None:
        if p.status not in ("downloading", "finished") or not p.total_bytes:
            return
        name = url.split("watch?v=")[-1][:18] if "watch?v=" in url else url[:18]
        position = self._positions.get(url)
        prefix = f"[{position}/{len(self.urls)}] " if position else ""
        with self._lock:
            self._progress[url] = max(
                self._progress.get(url, 0.0),
                100.0 if p.status == "finished" else
                min(100.0, p.downloaded_bytes / p.total_bytes * 100),
            )
            if p.status == "finished":
                msg = message("jobs.download.batch_finished", {"index": position or 0, "total": len(self.urls), "name": name}, fallback=f"{prefix}{name} — finished")
            else:
                msg = message("jobs.download.batch_progress", {"index": position or 0, "total": len(self.urls), "name": name, "sizeMb": f"{p.downloaded_bytes/(1024*1024):.1f}"}, fallback=f"{prefix}{name} — {p.downloaded_bytes/(1024*1024):.1f} MB")
            self._push(url, msg)

    def complete(self, url: str, msg: str | dict[str, Any]) -> None:
        with self._lock:
            self._progress[url] = 100.0
            self._push(url, msg)


# --- Рекомендации по библиотеке --------------------------------------------


def _ytm_feedback_sync(artist: str, title: str, rating: str | None = None) -> None:
    """Синхронная часть :func:`_ytm_feedback` (без потока)."""

    import src.ytmusic as mod
    from src.config import get_feedback_action

    if not mod.connected():
        return
    hits = mod.search_songs(f"{artist} {title}".strip(), limit=3)
    hit = next((h for h in hits if h.video_id), None)
    if not hit:
        return
    action = rating or get_feedback_action()
    if action == "library":
        mod.add_to_library(hit)
    else:
        mod.rate_song(hit.video_id, action)


def _ytm_feedback(artist: str, title: str, rating: str | None = None) -> None:
    """Отметить трек в аккаунте YT Music (поиск → действие), в фоне.

    По умолчанию (``rating=None``) действие берётся из настройки
    ``ytm_feedback_action``: ``like`` — лайк (сильный сигнал для радио),
    ``library`` — сохранение в библиотеку (слабый сигнал). Явный ``rating``
    (``DISLIKE``/``LIKE``) применяется как есть. Ошибки молча глотаются:
    фидбек — необязательный побочный эффект.
    """

    def run():
        try:
            _ytm_feedback_sync(artist, title, rating)
        except Exception:
            pass

    import threading
    threading.Thread(target=run, daemon=True).start()


@misc.post("/recommend/generate")
def api_recommend_generate():
    """Персональные рекомендации: радио YouTube Music по сидам из библиотеки.

    Кандидаты уже ранжированы аккаунтом (лайки/дизлайки/история); здесь
    убираются только треки, которые уже есть в библиотеке. Фидбек из UI
    (лайк/дизлайк/библиотека) уходит обратно в аккаунт (_ytm_feedback).

    Результат стримится: после каждого обработанного сида публикуется
    progress-событие kind=recommendations с накопительным snapshot
    (items/total/seeds/seed_index/seed_count/...); итоговый job result —
    прежний DTO из четырёх ключей.
    """

    def radio_fn(seed, limit):
        query = " ".join(p for p in (str(seed.get("artist") or ""),
                                     str(seed.get("title") or "")) if p).strip()
        if not query:
            return []
        hits = ytm_mod.search_songs(query, limit=1)
        if not hits or not hits[0].video_id:
            return []
        tracks = ytm_mod.watch_playlist(hits[0].video_id, limit=limit)
        return [ytm_track_to_dict(t) for t in tracks]

    from .. import ytmusic as ytm_mod
    if not ytm_mod.connected():
        raise HTTPException(
            status_code=400,
            detail=message(
                "api.errors.ytm_connection_required",
                fallback="Connect YouTube Music (Settings → YouTube Music)",
            ),
        )

    def run(job):
        out = _out_dir()
        records, _errors = scan_library(out)
        job.push(message("jobs.recommend.scanning", fallback="Scanning library…"), 5)
        if not records:
            return {"items": [], "seeds": 0, "library_count": 0, "total": 0}
        records = [
            {"artist": r.artist or "", "title": r.title or ""} for r in records
        ]
        job.push(message("jobs.recommend.radio", fallback="YouTube Music radio…"), 20)
        # Потоковая генерация: каждый обработанный сид публикуется событием
        # kind=recommendations (полный накопительный snapshot), а job result
        # остаётся прежним DTO из четырёх ключей.
        last: dict | None = None
        for snap in recommend_mod.iter_generate(
            records,
            radio_fn,
            seed_limit=recommend_mod.DEFAULT_SEED_LIMIT,
            similar_limit=recommend_mod.DEFAULT_SIMILAR_LIMIT,
        ):
            job.push(message("jobs.recommend.seed", {"index": snap["seed_index"], "total": snap["seed_count"]}, fallback=f"Processed seed {snap['seed_index']} of {snap['seed_count']}"),
                     kind="recommendations", **snap)
            last = snap
        job.push(message("jobs.common.done", fallback="Done"), 100)
        if last is None:  # ноль сидов — прежний пустой DTO
            return {"items": [], "seeds": 0, "library_count": len(records), "total": 0}
        return {
            "items": last["items"],
            "seeds": last["seeds"],
            "library_count": last["library_count"],
            "total": last["total"],
        }

    job = jobs.submit(message("jobs.recommend.name", fallback="Recommendations"), run)
    return {"job_id": job.id, "name": job.name}


@misc.post("/recommend/apply")
def api_recommend_apply(payload: dict):
    """Принять: отметить трек в аккаунте YT Music (действие — настройка
    ``ytm_feedback_action``: лайк/библиотека)."""
    artist = str((payload or {}).get("artist") or "").strip()
    title = str((payload or {}).get("title") or "").strip()
    if not artist or not title:
        raise HTTPException(status_code=400, detail=message("api.errors.artist_title_required", fallback="artist and title are required"))
    _ytm_feedback(artist, title)
    return {"status": "ok"}


@misc.post("/recommend/dislike")
def api_recommend_dislike(payload: dict):
    """Дизлайк: поставить дизлайк в аккаунте YT Music — радио больше не вернёт трек."""
    artist = str((payload or {}).get("artist") or "").strip()
    title = str((payload or {}).get("title") or "").strip()
    if not artist or not title:
        raise HTTPException(status_code=400, detail=message("api.errors.artist_title_required", fallback="artist and title are required"))
    _ytm_feedback(artist, title, "DISLIKE")
    return {"status": "ok"}
