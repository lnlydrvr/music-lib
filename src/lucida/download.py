"""Lucida load handoff, polling, and atomic Inbox download."""

from __future__ import annotations

import asyncio
import importlib
import os
import re
import sys
import uuid
from pathlib import Path
from types import ModuleType
from urllib.parse import quote, unquote, urlsplit

from src.lucida.http import LucidaClient

BASE_URL = "https://lucida.to"
PROVIDER_HOSTS = {
    "qobuz.com", "www.qobuz.com", "open.qobuz.com",
    "amazon.com", "music.amazon.com", "music.amazon.co.uk", "music.amazon.co.jp",
}


def _provider_url(value: str) -> str:
    """Accept only absolute URLs on the two supported provider domains."""
    if not isinstance(value, str):
        raise ValueError("Lucida provider URL is required")
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Lucida provider URL must be an HTTP(S) URL")
    if parsed.hostname.lower().strip(".") not in PROVIDER_HOSTS:
        raise ValueError("Lucida provider URL must use a supported provider host")
    return value
POLL_INTERVAL = 1.0
MAX_POLLS = 300
MAX_STREAM_RETRIES = 2


def _track_value(track: dict, *names: str, default=""):
    for name in names:
        value = track.get(name)
        if value is not None:
            return value
    return default


def _first_nonempty_string(track: dict, *names: str) -> str:
    for name in names:
        value = track.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


async def start_download(track, expiry, country, *, client=None):
    """POST the documented load body and return its handoff and server."""
    track_url = _track_value(track, "url")
    token = _first_nonempty_string(track, "csrf", "token")
    if not isinstance(track_url, str):
        raise ValueError("Lucida track URL must be an HTTP(S) URL")
    track_url = track_url.strip()
    track_url = _provider_url(track_url)
    if not token:
        raise ValueError("Lucida CSRF token is required")
    account = country or "auto"
    body = {
        "account": {"id": account, "type": "country"},
        "compat": False,
        "downscale": "original",
        "handoff": True,
        "metadata": True,
        "private": False,
        "token": {
            "expiry": expiry,
            "primary": _first_nonempty_string(track, "primary") or token,
            "secondary": _track_value(track, "secondary"),
        },
        "upload": {"enabled": False},
        "url": track_url,
    }

    async def request(active_client):
        response = await active_client.post(
            f"{BASE_URL}/api/load?url=/api/fetch/stream/v2", json=body
        )
        data = response.json()
        return data["handoff"], data["server"]

    if client is not None:
        return await request(client)
    async with LucidaClient() as active_client:
        return await request(active_client)


def _extension(headers):
    content_type = headers.get("content-type", "").split(";", 1)[0].lower()
    extension = {
        "audio/flac": ".flac", "audio/x-flac": ".flac", "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a", "audio/aac": ".aac", "audio/ogg": ".ogg",
        "audio/opus": ".opus", "audio/wav": ".wav", "audio/x-wav": ".wav",
    }.get(content_type)
    if extension:
        return extension
    disposition = headers.get("content-disposition", "")
    match = re.search(r"filename\*?=(?:UTF-8''|\")?([^\";]+)", disposition, re.I)
    if match:
        suffix = Path(unquote(match.group(1).strip())).suffix
        if suffix and re.fullmatch(r"\.[A-Za-z0-9]{1,8}", suffix):
            return suffix.lower()
    return ".audio"


def _safe_basename(name) -> str:
    if not isinstance(name, str) or not name or name in {".", ".."}:
        raise ValueError("Lucida filename must be a safe basename")
    if "\x00" in name or "/" in name or "\\" in name or Path(name).is_absolute():
        raise ValueError("Lucida filename must be a safe basename")
    return name


def _publish_without_overwrite(part_path: Path, directory: Path, name: str, extension: str) -> Path:
    """Link a completed partial into the first free final path without replacement."""
    for suffix in range(10_000):
        label = name if suffix == 0 else f"{name} ({suffix})"
        final_path = directory / f"{label}{extension}"
        try:
            os.link(part_path, final_path)
        except FileExistsError:
            continue
        part_path.unlink()
        return final_path
    raise FileExistsError("Could not allocate a unique Lucida download filename")


async def run_job(
    handoff, server, dest_dir, name, on_status=None, on_bytes=None, *, client=None,
    poll_interval=POLL_INTERVAL, max_polls=MAX_POLLS,
    max_stream_retries=MAX_STREAM_RETRIES,
):
    """Poll Lucida and stream to a `.part` file before publishing atomically.

    The caller chooses the destination directory (normally the library Inbox).
    Only this job's partial file is removed on failure.
    """
    name = _safe_basename(name)
    if not isinstance(max_stream_retries, int) or isinstance(max_stream_retries, bool) or max_stream_retries < 0:
        raise ValueError("max_stream_retries must be a non-negative integer")
    if not isinstance(server, str) or not re.fullmatch(r"[A-Za-z0-9-]+", server):
        raise ValueError("Lucida server must be a hostname label")
    if not isinstance(handoff, str) or not handoff:
        raise ValueError("Lucida handoff is required")
    encoded_handoff = quote(handoff, safe="")
    directory = Path(dest_dir)
    directory.mkdir(parents=True, exist_ok=True)
    poll_url = f"https://{server}.lucida.to/api/fetch/request/{encoded_handoff}"
    download_url = f"{poll_url}/download"
    owns_client = client is None
    part_path = directory / f".{name}.{uuid.uuid4().hex}.part"
    if owns_client:
        client = LucidaClient()
    try:
        for _ in range(max_polls):
            response = await client.get(poll_url)
            state = response.json()
            status = state.get("status", "")
            message = state.get("message", status)
            if on_status:
                on_status(message)
            if status == "completed":
                break
            if status in {"failed", "error", "cancelled"}:
                raise RuntimeError(str(message or "Lucida download failed"))
            await asyncio.sleep(poll_interval)
        else:
            raise TimeoutError("Lucida download stalled while polling")

        for attempt in range(max_stream_retries + 1):
            try:
                async with await client.stream(download_url) as response:
                    extension = _extension(response.headers)
                    with part_path.open("wb") as output:
                        async for chunk in response.aiter_bytes():
                            if chunk:
                                output.write(chunk)
                                if on_bytes:
                                    on_bytes(len(chunk))
                return _publish_without_overwrite(part_path, directory, name, extension)
            except importlib.import_module("httpx").RequestError:
                part_path.unlink(missing_ok=True)
                if attempt >= max_stream_retries:
                    raise
                await asyncio.sleep(poll_interval)
    except BaseException:
        part_path.unlink(missing_ok=True)
        raise
    finally:
        if owns_client:
            await client.aclose()


class _DownloadModule(ModuleType):
    """Compatibility module exposing the public adapter as a callable."""

    def __call__(self, url, kind, service="qobuz", jobs=3, progress=None, country=None):
        from src.lucida import _download_adapter

        return _download_adapter(url, kind, service, jobs, progress, country)


sys.modules[__name__].__class__ = _DownloadModule
