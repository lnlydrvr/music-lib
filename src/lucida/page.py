"""Parsing helpers for Lucida's SvelteKit page data."""

from __future__ import annotations

import base64
import importlib
import json
from typing import Any


START = ',{"type":"data","data":'
END = ',"uses":{"url":1}}];'


def extract_blob(html: str) -> Any:
    start = html.find(START)
    if start < 0:
        raise ValueError("Lucida page data blob was not found")
    start += len(START)
    end = html.find(END, start)
    if end < 0:
        raise ValueError("Lucida page data blob terminator was not found")
    raw = html[start:end]
    try:
        pyjson5 = importlib.import_module("pyjson5")
        return pyjson5.decode(raw)
    except ModuleNotFoundError:
        return json.loads(raw)


def _find_results(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        if "tracks" in value or "albums" in value:
            return value
        for child in value.values():
            found = _find_results(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_results(child)
            if found:
                return found
    return {}


def _artist(item: dict[str, Any]) -> str:
    artists = item.get("artists")
    if isinstance(artists, list):
        return ", ".join(name for a in artists if isinstance(a, dict) if (name := _string(a.get("name"))))
    artist = item.get("artist")
    return _string(artist.get("name")) if isinstance(artist, dict) else _string(artist)


def _map_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"url": "", "title": "", "artist": "", "album": ""}
    album = item.get("album")
    album_title = album.get("title", "") if isinstance(album, dict) else item.get(
        "album_title", item.get("title", "") if "artists" not in item else ""
    )
    cover = _cover_url(item)
    mapped = {
        "url": _string(item.get("url")),
        "title": _string(item.get("title")),
        "artist": _artist(item),
        "album": _string(album_title),
    }
    if cover:
        mapped["cover_url"] = cover
    return mapped


def _cover_url(item: dict[str, Any]) -> str:
    """Return the largest public artwork URL from Lucida metadata."""
    direct = item.get("cover_url") or item.get("cover")
    candidates: list[dict[str, Any]] = []
    if isinstance(direct, dict):
        candidates.append(direct)
    elif isinstance(direct, str):
        candidates.append({"url": direct})
    artwork = item.get("coverArtwork")
    if isinstance(artwork, list):
        candidates.extend(value for value in artwork if isinstance(value, dict))
    valid = [
        value for value in candidates
        if isinstance(value.get("url"), str) and value["url"].startswith("https://")
    ]
    if not valid:
        return ""
    selected = max(
        valid,
        key=lambda value: (
            _positive_number(value.get("width")) * _positive_number(value.get("height")),
            _positive_number(value.get("width")),
            _positive_number(value.get("height")),
        ),
    )
    return selected["url"]


def _positive_number(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def parse_search(html: str) -> dict[str, list[dict[str, Any]]]:
    results = _find_results(extract_blob(html))
    return {
        kind: [_map_item(item) for item in results[kind]] if isinstance(results.get(kind), list) else []
        for kind in ("albums", "tracks")
    }


def parse_page_data(html: str) -> dict[str, Any]:
    blob = extract_blob(html)
    if isinstance(blob, dict):
        if "info" in blob or "token" in blob:
            return blob
        return _find_page_data(blob)
    return {}


def _find_page_data(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        if "info" in value or "token" in value:
            return value
        for child in value.values():
            found = _find_page_data(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_page_data(child)
            if found:
                return found
    return {}


def decode_track_token(token: str) -> str:
    decoded = token
    try:
        for _ in range(2):
            decoded = base64.b64decode(decoded, validate=True).decode("utf-8")
        return decoded
    except (ValueError, UnicodeDecodeError, base64.binascii.Error):
        return token
