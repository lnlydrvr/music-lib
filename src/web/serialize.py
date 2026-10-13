"""Сериализация моделей в JSON-совместимые словари для API."""
from __future__ import annotations

from pathlib import Path

from ..analytics import TrackRecord
from ..providers import ProviderRecord
from ..tagger import AudioTags
from ..ytmusic import YTMTrack, pick_thumbnail

AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".ogg", ".wav", ".aac", ".wma"}


def track_to_dict(rec: TrackRecord) -> dict:
    return {
        "path": str(rec.path),
        "artist": rec.artist,
        "album": rec.album,
        "title": rec.title,
        "year": rec.year,
        "genre": rec.genre,
        "album_artist": rec.album_artist,
        "isrc": rec.isrc,
        "composer": rec.composer,
        "track_number": rec.track_number,
        "disc_number": rec.disc_number,
        "size_bytes": rec.size_bytes,
        "duration_seconds": rec.duration_seconds,
        "bitrate": rec.bitrate,
        "mtime": rec.mtime,
        "has_lyrics": bool(rec.lyrics or rec.lyrics_synced),
        "has_synced_lyrics": bool(rec.lyrics_synced),
        "has_cover": bool(rec.cover),
        "ext": rec.path.suffix.lower(),
    }


def tags_to_dict(tags: AudioTags, name: str = "") -> dict:
    return {
        "name": name,
        "title": tags.title,
        "artist": tags.artist,
        "album": tags.album,
        "year": tags.year,
        "track_number": tags.track_number,
        "genre": tags.genre,
        "comment": tags.comment,
        "album_artist": tags.album_artist,
        "disc_number": tags.disc_number,
        "isrc": tags.isrc,
        "composer": tags.composer,
        "publisher": tags.publisher,
        "copyright": tags.copyright,
        "has_cover": bool(tags.cover_data),
        "cover_mime": tags.cover_mime or "",
        "cover_url": _cover_url(tags),
        "has_lyrics": bool(tags.lyrics and tags.lyrics.strip()),
        "has_synced_lyrics": bool(tags.lyrics_synced and tags.lyrics_synced.strip()),
        "lyrics": tags.lyrics or "",
        "synced_lyrics": tags.lyrics_synced or "",
    }


def record_to_dict(rec: ProviderRecord) -> dict:
    return {
        "source": rec.source,
        "title": rec.title,
        "artist": rec.artist,
        "album": rec.album,
        "year": rec.year,
        "genre": rec.genre,
        "track_number": rec.track_number,
        "album_artist": rec.album_artist,
        "disc_number": rec.disc_number,
        "isrc": rec.isrc,
        "composer": rec.composer,
        "publisher": rec.publisher,
        "label": rec.label,
        "cover_url": rec.cover_url,
        "summary": rec.summary(),
    }


def _cover_url(tags: AudioTags) -> str:
    # Обложка берётся отдельным эндпоинтом /api/cover?path=..., здесь только флаг.
    return ""


def ytm_track_to_dict(track: YTMTrack, in_library: bool = False) -> dict:
    """YTMTrack → JSON для экрана YouTube Music (с флагом дедупа)."""
    return {
        "video_id": track.video_id,
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "year": track.year,
        "track_number": track.track_number,
        "cover_url": track.cover_url,
        "duration": track.duration,
        "video_type": track.video_type,
        "in_library": in_library,
    }


def ytm_album_to_dict(raw: dict) -> dict:
    """Сырой альбом ytmusicapi (список) → JSON."""
    artists = [str(a.get("name") or "") for a in raw.get("artists") or []
               if isinstance(a, dict)]
    return {
        "id": str(raw.get("browseId") or ""),
        "title": str(raw.get("title") or ""),
        "artist": ", ".join(n for n in artists if n),
        "year": raw.get("year"),
        "track_count": raw.get("trackCount"),
        "cover_url": _pick(raw.get("thumbnails")),
    }


def ytm_playlist_to_dict(raw: dict) -> dict:
    """Сырой плейлист ytmusicapi (список) → JSON."""
    return {
        "id": str(raw.get("playlistId") or ""),
        "title": str(raw.get("title") or ""),
        "count": raw.get("count"),
        "cover_url": _pick(raw.get("thumbnails")),
        "description": str(raw.get("description") or ""),
    }


def ytm_artist_to_dict(raw: dict, local_count: int = 0) -> dict:
    """Сырой исполнитель ytmusicapi (подписка) → JSON.

    ``local_count`` — сколько файлов этого исполнителя есть в библиотеке.
    """
    return {
        "id": str(raw.get("browseId") or ""),
        "name": str(raw.get("artist") or ""),
        "subscribers": str(raw.get("subscribers") or ""),
        "cover_url": _pick(raw.get("thumbnails")),
        "local_count": local_count,
    }


def _pick(thumbnails) -> str:
    return pick_thumbnail(thumbnails)


def duration_seconds(path: Path) -> int:
    try:
        from mutagen import File as MFile

        audio = MFile(str(path))
        if audio and audio.info and hasattr(audio.info, "length"):
            return int(audio.info.length)
    except Exception:
        pass
    return 0