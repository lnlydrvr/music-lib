"""Public, side-effect-free adapter for Lucida search and downloads.

The public functions deliberately import the HTTP and browser-facing pieces only
when invoked.  Importing ``src.lucida`` therefore neither starts Chromium nor
creates an HTTP client.
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import math
import time
import re
from pathlib import Path
from urllib.parse import urlencode

from .services import AMAZON_STOREFRONTS, default_country, normalize_service


BASE_URL = "https://lucida.to"


class LucidaReleaseUnavailable(Exception):
    """No selected release page contained fetchable tracks."""


def _load_clearance():
    return importlib.import_module("src.lucida.cf").load_clearance()


def _client():
    return importlib.import_module("src.lucida.http").LucidaClient()


def _parse_search(html: str):
    return importlib.import_module("src.lucida.page").parse_search(html)


def _parse_page_data(html: str):
    return importlib.import_module("src.lucida.page").parse_page_data(html)


def _cover_url(item: dict) -> str:
    return importlib.import_module("src.lucida.page")._cover_url(item)


def _decode_track_token(token: str):
    return importlib.import_module("src.lucida.page").decode_track_token(token)


def _start_download(*args, **kwargs):
    return importlib.import_module("src.lucida.download").start_download(*args, **kwargs)


def _run_job(*args, **kwargs):
    return importlib.import_module("src.lucida.download").run_job(*args, **kwargs)


def _resolve_output_dir():
    return importlib.import_module("src.config").resolve_output_dir()


def _inbox_dir(output_dir: Path):
    return importlib.import_module("src.config").inbox_dir(output_dir)


def _ingest(path: Path, output_dir: Path):
    return importlib.import_module("src.lucida.ingest").ingest(path, output_dir)


def _report_progress(progress, event: dict) -> None:
    """User callbacks are observational and must not abort a download."""
    if progress is None:
        return
    try:
        progress(event)
    except Exception:
        pass


def _access_error(message: str):
    return importlib.import_module("src.lucida.http").LucidaAccessRequired(message)


def available(check_chromium: bool = False) -> bool:
    """Return whether Playwright is installed, optionally requiring Chromium.

    ``find_spec`` is intentionally the only optional-dependency operation in
    the normal path.  Chromium inspection is opt-in and never launches it.
    """
    installed = importlib.util.find_spec("playwright") is not None
    if not installed or not check_chromium:
        return installed
    return bool(importlib.import_module("src.lucida.cf").chromium_installed())


def status(service: str = "qobuz") -> dict[str, object]:
    """Report local Lucida readiness without acquiring browser access."""
    normalized = normalize_service(service)
    clearance, _ = _load_clearance()
    installed = available()
    chromium_ready = bool(
        installed and importlib.import_module("src.lucida.cf").chromium_installed()
    )
    return {
        "available": installed,
        "access_ready": bool(clearance),
        "chromium_ready": chromium_ready,
        "service": normalized,
    }


def _require_access() -> None:
    clearance, _ = _load_clearance()
    if not clearance:
        raise _access_error("Lucida clearance is required.")


def _search_url(query: str, service: str, country: str) -> str:
    return f"{BASE_URL}/search?{urlencode({'service': service, 'country': country, 'query': query})}"


def _country(service: str, country: str | None) -> str:
    """Use an explicit storefront country when supplied, otherwise service default."""
    value = country.strip() if isinstance(country, str) else ""
    if value and not re.fullmatch(r"[A-Z]{2}", value):
        raise ValueError("Lucida country must be two uppercase letters")
    return value or default_country(service)


async def _search(query: str, service: str, country: str | None = None) -> dict[str, list[dict]]:
    country = _country(service, country)
    async with _client() as client:
        response = await client.get(_search_url(query, service, country))
    return _parse_search(response.text)


async def _release_preview(url: str, service: str, country: str | None = None) -> dict:
    country = _country(service, country)
    async with _client() as client:
        response = await client.get(_release_url(url, country))
    data = _parse_page_data(response.text)
    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    raw_tracks = info.get("tracks") if isinstance(info.get("tracks"), list) else []
    tracks = []
    for index, track in enumerate(raw_tracks, 1):
        if not isinstance(track, dict):
            continue
        number = track.get("number")
        if isinstance(number, bool):
            number = index
        elif isinstance(number, int):
            number = number if number >= 0 else index
        elif isinstance(number, float):
            number = int(number) if math.isfinite(number) and number >= 0 and number.is_integer() else index
        elif isinstance(number, str) and re.fullmatch(r"\d+", number.strip()):
            number = int(number.strip())
        else:
            number = index
        item = {"number": number, "title": track.get("title") if isinstance(track.get("title"), str) else ""}
        duration = track.get("duration")
        if isinstance(duration, (int, float)) and not isinstance(duration, bool):
            item["duration"] = duration
        tracks.append(item)
    cover = _cover_url(info)
    result = {
        "title": info.get("title") if isinstance(info.get("title"), str) else "",
        "artist": _artist_name(info),
        "tracks": tracks,
        "track_count": len(tracks),
    }
    if cover:
        result["cover_url"] = cover
    return result


def _artist_name(info: dict) -> str:
    artist = info.get("artist")
    if isinstance(artist, str):
        return artist
    if isinstance(artist, dict) and isinstance(artist.get("name"), str):
        return artist["name"]
    return ""


def release_preview(url: str, service: str = "qobuz", country: str | None = None) -> dict:
    """Read release metadata for inline preview; never prepares download tokens."""
    importlib.import_module("src.lucida.download")._provider_url(str(url))
    _require_access()
    return asyncio.run(_release_preview(str(url), normalize_service(service), country))


def search(query: str, service: str = "qobuz", country: str | None = None) -> dict[str, list[dict]]:
    """Search Lucida with already prepared clearance; never opens a browser."""
    _require_access()
    return asyncio.run(_search(str(query), normalize_service(service), country))


def _release_url(url: str, country: str) -> str:
    url = importlib.import_module("src.lucida.download")._provider_url(url)
    return f"{BASE_URL}/?{urlencode({'url': url, 'country': country})}"


def _tracks(data: dict, kind: str) -> list[dict]:
    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    release_type = info.get("type")
    if kind == "album" or release_type == "album":
        tracks = info.get("tracks")
        return [dict(track) for track in tracks if isinstance(track, dict)] if isinstance(tracks, list) else []
    return [dict(info)] if info else []


def _expiry(data: dict) -> int | float:
    for value in (data.get("expiry"), data.get("token_expiry"), data.get("expires")):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    token = data.get("token")
    if isinstance(token, dict):
        value = token.get("expiry")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    # Lucida accepts a timestamp; this fallback is only for page variants that
    # omit it and keeps the request contract valid without inventing a token.
    return int(time.time())


def _prepare_tracks(data: dict, kind: str) -> list[dict]:
    tracks = _tracks(data, kind)
    page_token = data.get("token")
    for track in tracks:
        if not track.get("csrf") and isinstance(page_token, str):
            track["csrf"] = _decode_track_token(page_token)
    return tracks


def _usable_release_tracks(tracks: list[dict]) -> bool:
    """Whether every release track has the data needed for a fetch request."""
    return bool(tracks) and all(
        isinstance(track.get("url"), str) and bool(track["url"].strip())
        and isinstance(track.get("csrf"), str) and bool(track["csrf"].strip())
        for track in tracks
    )


def _name(track: dict, index: int) -> str:
    raw = track.get("title")
    name = raw.strip() if isinstance(raw, str) else ""
    name = name.replace("/", "-").replace("\\", "-").replace("\x00", "")
    return name or f"Lucida track {index}"


async def _download_one(track, index, expiry, country, inbox, output_dir, client, semaphore, progress):
    url = track.get("url") if isinstance(track.get("url"), str) else ""
    result = {"url": url, "title": track.get("title", ""), "status": "fail", "path": "", "error": ""}
    if not url:
        result["error"] = "Lucida track URL is missing"
        _report_progress(progress, {"type": "item", "url": url, "status": result["status"]})
        return result
    try:
        async with semaphore:
            handoff, server = await _start_download(track, expiry, country, client=client)
            path = await _run_job(
                handoff, server, inbox, _name(track, index),
                lambda message: _report_progress(progress, {"type": "status", "url": url, "message": message}),
                lambda count: _report_progress(progress, {"type": "bytes", "url": url, "bytes": count}),
                client=client,
            )
        ingested = _ingest(path, output_dir)
        result.update(ingested)
        result["url"] = url
        result["title"] = track.get("title", "")
    except importlib.import_module("src.lucida.http").LucidaAccessRequired:
        raise
    except Exception:  # individual ordinary failures must not abort an album
        result["error"] = "lucida_item_failed"
    _report_progress(progress, {"type": "item", "url": url, "status": result["status"]})
    return result


async def _download(url, kind, service, jobs, progress, country=None):
    configured_country = country.strip() if isinstance(country, str) else ""
    use_amazon_fallback = service == "amazon" and kind == "album" and not configured_country
    candidates = AMAZON_STOREFRONTS if use_amazon_fallback else [_country(service, country)]
    async with _client() as client:
        data: dict | None = None
        tracks: list[dict] | None = None
        selected_country: str | None = None
        for candidate in candidates:
            response = await client.get(_release_url(url, candidate))
            candidate_data = _parse_page_data(response.text)
            candidate_tracks = _prepare_tracks(candidate_data, kind)
            if not use_amazon_fallback or _usable_release_tracks(candidate_tracks):
                data, tracks, selected_country = candidate_data, candidate_tracks, candidate
                break
        if data is None or tracks is None or selected_country is None:
            raise LucidaReleaseUnavailable("No usable Lucida release tracks found.")
        if not tracks:
            raise LucidaReleaseUnavailable("Lucida release contains no tracks.")
        country = selected_country
        expiry = _expiry(data)
        output_dir = Path(_resolve_output_dir())
        inbox = _inbox_dir(output_dir)
        limit = max(1, int(jobs))
        semaphore = asyncio.Semaphore(limit)
        completed = 0
        total = len(tracks)
        def item_progress(event):
            nonlocal completed
            if event.get("type") == "item":
                completed += 1
                event = {**event, "done": completed, "total": total, "percent": round(completed * 100 / total)}
            _report_progress(progress, event)
        tasks = [asyncio.create_task(_download_one(
            track, index, expiry, country, inbox, output_dir, client, semaphore, item_progress
        )) for index, track in enumerate(tracks, 1)]
        try:
            items = await asyncio.gather(*tasks)
        except importlib.import_module("src.lucida.http").LucidaAccessRequired:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
    return {"items": items}


def _download_adapter(url: str, kind: str, service: str = "qobuz", jobs: int = 3, progress=None, country: str | None = None) -> dict:
    """Download the selected release URL into Inbox and then attempt ingestion.

    Completed audio is written straight to ``Inbox``.  A skipped or failed
    library move leaves that completed file there for recovery; only ``run_job``
    owns and removes its own incomplete ``.part`` file.
    """
    from src.config import parse_lucida_jobs

    jobs = parse_lucida_jobs(jobs)
    if jobs is None:
        raise ValueError("Lucida jobs must be an integer between 1 and 8")
    importlib.import_module("src.lucida.download")._provider_url(str(url))
    _require_access()
    return asyncio.run(_download(str(url), str(kind), normalize_service(service), jobs, progress, country))


def __getattr__(name: str):
    """Keep ``src.lucida.download`` import-compatible and callable as adapter."""
    if name == "LucidaAccessRequired":
        return importlib.import_module("src.lucida.http").LucidaAccessRequired
    if name == "download":
        return importlib.import_module("src.lucida.download")
    raise AttributeError(name)
