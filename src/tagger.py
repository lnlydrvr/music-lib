"""Audio tag reader/writer using mutagen."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mutagen import File
from mutagen.id3 import (
    ID3,
    TIT2,
    TPE1,
    TPE2,
    TALB,
    TDRC,
    APIC,
    COMM,
    USLT,
    SYLT,
    ID3NoHeaderError,
)
from mutagen.mp4 import MP4Tags, MP4Cover
from mutagen.flac import Picture
from mutagen.mp3 import EasyMP3

from .utils import logger

#: Ключ Vorbis-комментария для синхронизированного текста (LRC).
#: Обычный текст пишется в ``UNSYNCEDLYRICS`` (старые файлы — в ``lyrics``).
_FLAC_SYNCED_KEY = "LYRICS"
_FLAC_PLAIN_KEY = "UNSYNCEDLYRICS"
#: Freeform-атом MP4 с синхронизированным текстом (LRC).
_M4A_SYNCED_KEY = "----:com.apple.iTunes:SYLT"

#: Один или несколько таймкодов ``[mm:ss.xx]`` в начале строки LRC.
_LRC_TIME_RE = re.compile(r"\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]")


def _lrc_to_sylt(lrc: str) -> list[tuple[str, int]]:
    """LRC → список ``(text, time_ms)`` в порядке, который ждёт SYLT."""
    items: list[tuple[str, int]] = []
    for raw in (lrc or "").splitlines():
        stamps = list(_LRC_TIME_RE.finditer(raw))
        if not stamps:
            continue
        text = raw[stamps[-1].end():].strip()
        for m in stamps:
            minutes = int(m.group(1))
            seconds = int(m.group(2))
            frac = m.group(3) or ""
            millis = int(frac.ljust(3, "0")[:3]) if frac else 0
            items.append((text, (minutes * 60 + seconds) * 1000 + millis))
    return items


def _sylt_to_lrc(items: list[tuple[str, int]]) -> str:
    """Список ``(text, time_ms)`` → текст LRC."""
    lines = []
    for text, millis in sorted(items, key=lambda x: x[1]):
        total = max(0, int(millis))
        minutes, rem = divmod(total, 60000)
        seconds, ms = divmod(rem, 1000)
        lines.append(f"[{minutes:02d}:{seconds:02d}.{ms // 10:02d}] {text}")
    return "\n".join(lines)


def _looks_lrc(text: str) -> bool:
    """Есть ли в тексте хотя бы один таймкод LRC."""
    return bool(text) and _LRC_TIME_RE.search(text) is not None


@dataclass
class AudioTags:
    """Standard audio tags."""

    title: str = ""
    artist: str = ""
    album: str = ""
    year: str = ""
    track_number: str = ""
    genre: str = ""
    comment: str = ""
    album_artist: str = ""
    cover_data: bytes | None = None
    cover_mime: str = ""
    disc_number: str = ""
    isrc: str = ""
    composer: str = ""
    publisher: str = ""
    copyright: str = ""
    lyrics: str = ""
    lyrics_synced: str = ""


class Tagger:
    """Read and write audio tags for various formats."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self._file: Any = None
        self._load()

    def _load(self) -> None:
        """Load the audio file."""
        suffix = self.filepath.suffix.lower()

        if suffix == ".mp3":
            try:
                self._file = EasyMP3(str(self.filepath))
            except ID3NoHeaderError:
                self._file = File(str(self.filepath))
                self._file.add_tags()
        elif suffix == ".flac":
            self._file = File(str(self.filepath))
        elif suffix in (".m4a", ".aac", ".mp4"):
            self._file = File(str(self.filepath))
        else:
            self._file = File(str(self.filepath))

    def read(self) -> AudioTags:
        """Read all tags from the file."""
        tags = AudioTags()

        if self._file is None:
            return tags

        tags_dict = self._file.tags or {}

        # MP3 (ID3)
        if isinstance(self._file, EasyMP3):
            tags.title = self._get_tag(tags_dict, "title")
            tags.album_artist = self._get_tag(tags_dict, "albumartist")
            tags.artist = self._get_tag(tags_dict, "artist")
            tags.album = self._get_tag(tags_dict, "album")
            tags.year = self._get_tag(tags_dict, "date")
            tags.track_number = self._get_tag(tags_dict, "tracknumber")
            tags.genre = self._get_tag(tags_dict, "genre")
            tags.disc_number = self._get_tag(tags_dict, "discnumber")
            tags.isrc = self._get_tag(tags_dict, "isrc")
            tags.composer = self._get_tag(tags_dict, "composer")
            tags.publisher = self._get_tag(tags_dict, "organization")
            tags.copyright = self._get_tag(tags_dict, "copyright")

            # Cover art + comment — use raw ID3 since EasyID3 doesn't expose them
            try:
                id3 = ID3(str(self.filepath))
                for key in id3:
                    if key.startswith("APIC"):
                        pic = id3[key]
                        tags.cover_data = pic.data
                        tags.cover_mime = pic.mime
                        break
                for key in id3:
                    if key.startswith("COMM"):
                        tags.comment = id3[key].text[0]
                        break
                for key in id3:
                    if key.startswith("USLT"):
                        tags.lyrics = id3[key].text
                        break
                for key in id3:
                    if key.startswith("SYLT"):
                        tags.lyrics_synced = _sylt_to_lrc(id3[key].text)
                        break
            except Exception:
                pass

        # FLAC
        elif self.filepath.suffix.lower() == ".flac":
            tags.title = self._get_tag(tags_dict, "title")
            tags.artist = self._get_tag(tags_dict, "artist")
            tags.album = self._get_tag(tags_dict, "album")
            tags.album_artist = self._get_tag(tags_dict, "albumartist")
            tags.year = self._get_tag(tags_dict, "date")
            tags.track_number = self._get_tag(tags_dict, "tracknumber")
            tags.genre = self._get_tag(tags_dict, "genre")
            tags.disc_number = self._get_tag(tags_dict, "discnumber")
            tags.isrc = self._get_tag(tags_dict, "isrc")
            tags.composer = self._get_tag(tags_dict, "composer")
            tags.publisher = self._get_tag(tags_dict, "publisher")
            tags.copyright = self._get_tag(tags_dict, "copyright")
            tags.comment = self._get_tag(tags_dict, "comment")
            raw_unsynced = self._get_tag(tags_dict, _FLAC_PLAIN_KEY)
            raw_lyrics = self._get_tag(tags_dict, _FLAC_SYNCED_KEY)
            if raw_unsynced:
                tags.lyrics = raw_unsynced
                tags.lyrics_synced = raw_lyrics
            elif _looks_lrc(raw_lyrics):
                tags.lyrics_synced = raw_lyrics
            else:
                tags.lyrics = raw_lyrics

            # Cover art
            if hasattr(self._file, "pictures") and self._file.pictures:
                pic = self._file.pictures[0]
                tags.cover_data = pic.data
                tags.cover_mime = pic.mime

        # M4A/AAC
        elif self.filepath.suffix.lower() in (".m4a", ".aac", ".mp4"):
            tags.title = self._get_tag(tags_dict, "\xa9nam")
            tags.artist = self._get_tag(tags_dict, "\xa9ART")
            tags.album = self._get_tag(tags_dict, "\xa9alb")
            tags.album_artist = self._get_tag(tags_dict, "aART")
            tags.year = self._get_tag(tags_dict, "\xa9day")
            tags.track_number = self._get_m4a_track(tags_dict.get("trkn"))
            tags.genre = self._get_tag(tags_dict, "\xa9gen")
            tags.composer = self._get_tag(tags_dict, "\xa9wrt")
            # "pub" is a 3-byte atom — mutagen pads short atoms to 4 bytes.
            tags.publisher = self._get_tag(tags_dict, "pub") or self._get_tag(
                tags_dict, "pub\x00"
            )
            tags.copyright = self._get_tag(tags_dict, "\xa9cmt")
            tags.comment = self._get_tag(tags_dict, "\xa9cmt")
            tags.disc_number = self._get_m4a_disk(tags_dict.get("disk"))
            tags.lyrics = self._get_tag(tags_dict, "\xa9lyr")
            synced = tags_dict.get(_M4A_SYNCED_KEY)
            if synced:
                try:
                    first = synced[0] if isinstance(synced, list) else synced
                    tags.lyrics_synced = bytes(first).decode("utf-8", "replace")
                except Exception:
                    tags.lyrics_synced = ""

            # Cover art
            if "covr" in tags_dict:
                cover = tags_dict["covr"]
                if cover:
                    tags.cover_data = bytes(cover[0])
                    tags.cover_mime = "image/jpeg"

        return tags

    def _get_tag(self, tags_dict: dict, key: str) -> str:
        """Extract a single tag value."""
        value = tags_dict.get(key)
        if value is None:
            return ""
        if isinstance(value, list) and value:
            return str(value[0])
        return str(value)

    @staticmethod
    def _get_m4a_track(value: Any) -> str:
        """Номер трека MP4 trkn как 'N' или 'N/T'."""
        try:
            if not value:
                return ""
            num, total = value[0]
            num, total = int(num), int(total)
        except Exception:
            return ""
        if not num:
            return ""
        if total:
            return f"{num}/{total}"
        return str(num)

    @staticmethod
    def _get_m4a_disk(value: Any) -> str:
        """Номер диска MP4 disk как 'N' или 'N/T'."""
        try:
            if not value:
                return ""
            num, total = value[0]
            num, total = int(num), int(total)
        except Exception:
            return ""
        if not num:
            return ""
        if total:
            return f"{num}/{total}"
        return str(num)

    def write(self, tags: AudioTags) -> bool:
        """Write tags to the file.

        Args:
            tags: AudioTags to write

        Returns:
            True if successful
        """
        if self._file is None:
            return False

        try:
            # MP3 (ID3) — _write_mp3_tags does its own id3.save()
            if isinstance(self._file, EasyMP3):
                self._write_mp3_tags(tags)
                return True

            # FLAC
            elif self.filepath.suffix.lower() == ".flac":
                self._write_flac_tags(tags)

            # M4A/AAC
            elif self.filepath.suffix.lower() in (".m4a", ".aac", ".mp4"):
                self._write_m4a_tags(tags)

            self._file.save()
            return True

        except Exception as e:
            logger.warning("Ошибка записи тегов: %s", e)
            return False

    @staticmethod
    def _text(value: Any) -> str:
        """Coerce a tag value to text, guarding against None/non-str input.

        Prevents type errors (e.g. "can't concat int to bytes") when a field
        somehow holds an int or other non-string instead of a string.
        """
        if value is None:
            return ""
        return value if isinstance(value, str) else str(value)

    def _write_mp3_tags(self, tags: AudioTags) -> None:
        """Write tags to MP3 file.

        Uses raw ID3 for everything because EasyID3 doesn't recognize USLT/COMM.
        Calling id3.save() after self._file.save() would overwrite EasyMP3's
        write, and vice-versa — so we do a single raw ID3 save here and skip
        the self._file.save() in write().
        """
        if not self._file.tags:
            try:
                self._file.add_tags()
            except Exception:
                pass

        try:
            id3 = ID3(str(self.filepath))
        except ID3NoHeaderError:
            id3 = ID3()

        # Text frames via EasyID3 names → raw ID3 keys
        id3.delall("TIT2")
        id3.delall("TPE1")
        id3.delall("TPE2")
        id3.delall("TALB")
        id3.delall("TDRC")
        id3.delall("TRCK")
        id3.delall("TCON")
        id3.delall("TPOS")
        id3.delall("TSRC")
        id3.delall("TCOM")
        id3.delall("TPUB")
        id3.delall("TCOP")

        from mutagen.id3 import TCON, TRCK, TPOS, TSRC, TPUB, TCOM, TCOP

        title = self._text(tags.title)
        artist = self._text(tags.artist)
        album = self._text(tags.album)
        album_artist = self._text(tags.album_artist)
        year = self._text(tags.year)
        track_number = self._text(tags.track_number)
        genre = self._text(tags.genre)
        disc_number = self._text(tags.disc_number)
        isrc = self._text(tags.isrc)
        composer = self._text(tags.composer)
        publisher = self._text(tags.publisher)
        copyright_ = self._text(tags.copyright)
        comment = self._text(tags.comment)
        lyrics = self._text(tags.lyrics)
        lyrics_synced = self._text(tags.lyrics_synced)

        if title:
            id3.add(TIT2(encoding=3, text=title))
        if artist:
            id3.add(TPE1(encoding=3, text=artist))
        if album:
            id3.add(TALB(encoding=3, text=album))
        if album_artist:
            id3.add(TPE2(encoding=3, text=album_artist))
        if year:
            id3.add(TDRC(encoding=3, text=year))
        if track_number:
            id3.add(TRCK(encoding=3, text=track_number))
        if genre:
            id3.add(TCON(encoding=3, text=genre))
        if disc_number:
            id3.add(TPOS(encoding=3, text=disc_number))
        if isrc:
            id3.add(TSRC(encoding=3, text=isrc))
        if composer:
            id3.add(TCOM(encoding=3, text=composer))
        if publisher:
            id3.add(TPUB(encoding=3, text=publisher))
        if copyright_:
            id3.add(TCOP(encoding=3, text=copyright_))

        # COMM + USLT + SYLT
        id3.delall("COMM")
        id3.delall("USLT")
        id3.delall("SYLT")
        if comment:
            id3.add(COMM(encoding=3, lang="eng", desc="", text=comment))
        if lyrics:
            id3.add(USLT(encoding=3, lang="eng", desc="", text=lyrics))
        if lyrics_synced:
            sylt = _lrc_to_sylt(lyrics_synced)
            if sylt:
                id3.add(SYLT(encoding=3, lang="eng", format=2, type=1,
                             desc="", text=sylt))

        # Cover art — only replace if new cover_data provided
        if tags.cover_data:
            id3.delall("APIC")
            mime = tags.cover_mime or "image/jpeg"
            id3.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=tags.cover_data))

        id3.save(str(self.filepath))

    def _write_flac_tags(self, tags: AudioTags) -> None:
        """Write tags to FLAC file."""
        if not self._file.tags:
            self._file.add_tags()

        title = self._text(tags.title)
        artist = self._text(tags.artist)
        album = self._text(tags.album)
        album_artist = self._text(tags.album_artist)
        year = self._text(tags.year)
        track_number = self._text(tags.track_number)
        genre = self._text(tags.genre)
        disc_number = self._text(tags.disc_number)
        isrc = self._text(tags.isrc)
        composer = self._text(tags.composer)
        publisher = self._text(tags.publisher)
        copyright_ = self._text(tags.copyright)
        comment = self._text(tags.comment)
        lyrics = self._text(tags.lyrics)
        lyrics_synced = self._text(tags.lyrics_synced)

        self._file["title"] = title
        self._file["artist"] = artist
        self._file["album"] = album
        self._file["albumartist"] = album_artist
        self._file["date"] = year
        self._file["tracknumber"] = track_number
        self._file["genre"] = genre
        self._file["discnumber"] = disc_number
        self._file["isrc"] = isrc
        self._file["composer"] = composer
        self._file["publisher"] = publisher
        self._file["copyright"] = copyright_
        self._file["comment"] = comment
        # Синхронизированный текст — LYRICS, обычный — UNSYNCEDLYRICS.
        # Старый ключ plain-текста (``lyrics``) перезаписывается, поэтому
        # сначала убираем его, чтобы не смешивать с синхро-версией.
        for key in ("lyrics", "unsyncedlyrics"):
            if key in self._file:
                del self._file[key]
        if lyrics_synced:
            self._file[_FLAC_SYNCED_KEY] = lyrics_synced
        if lyrics:
            self._file[_FLAC_PLAIN_KEY] = lyrics

        # Cover art
        if tags.cover_data:
            pic = Picture()
            pic.type = 3
            pic.data = tags.cover_data
            pic.mime = tags.cover_mime or "image/jpeg"

            self._file.clear_pictures()
            self._file.add_picture(pic)

    def _write_m4a_tags(self, tags: AudioTags) -> None:
        """Write tags to M4A/AAC file."""
        if not self._file.tags:
            self._file.add_tags()

        title = self._text(tags.title)
        artist = self._text(tags.artist)
        album_artist = self._text(tags.album_artist)
        album = self._text(tags.album)
        year = self._text(tags.year)
        genre = self._text(tags.genre)
        composer = self._text(tags.composer)
        publisher = self._text(tags.publisher)
        comment = self._text(tags.comment)
        lyrics = self._text(tags.lyrics)
        lyrics_synced = self._text(tags.lyrics_synced)

        self._file["\xa9nam"] = title
        self._file["\xa9ART"] = artist
        self._file["aART"] = album_artist
        self._file["\xa9alb"] = album
        self._file["\xa9day"] = year
        self._file["\xa9gen"] = genre
        self._file["\xa9wrt"] = composer
        self._file["pub"] = publisher
        self._file["\xa9cmt"] = comment
        trkn = self._parse_m4a_track(self._text(tags.track_number))
        if trkn:
            self._file["trkn"] = trkn
        elif "trkn" in self._file:
            del self._file["trkn"]
        disk = self._parse_m4a_disk(self._text(tags.disc_number))
        if disk:
            self._file["disk"] = disk
        elif "disk" in self._file:
            del self._file["disk"]
        if lyrics:
            self._file["\xa9lyr"] = lyrics
        if _M4A_SYNCED_KEY in self._file:
            del self._file[_M4A_SYNCED_KEY]
        if lyrics_synced:
            self._file[_M4A_SYNCED_KEY] = lyrics_synced.encode("utf-8")

        # Cover art
        if tags.cover_data:
            fmt = (
                MP4Cover.FORMAT_PNG
                if (tags.cover_mime or "").lower() == "image/png"
                else MP4Cover.FORMAT_JPEG
            )
            self._file["covr"] = [MP4Cover(tags.cover_data, imageformat=fmt)]

    @staticmethod
    def _parse_m4a_track(value: str) -> list[tuple[int, int]]:
        """Номер трека "N" или "N/T" в кортеж MP4 trkn."""
        value = "" if value is None else str(value)
        num_text, _, total_text = value.partition("/")
        try:
            num = int(num_text.strip())
        except ValueError:
            return []
        try:
            total = int(total_text.strip()) if total_text.strip() else 0
        except ValueError:
            total = 0
        if num <= 0:
            return []
        return [(num, total)]

    @staticmethod
    def _parse_m4a_disk(value: str) -> list[tuple[int, int]]:
        """Номер диска "N" или "N/T" в кортеж MP4 disk."""
        value = "" if value is None else str(value)
        num_text, _, total_text = value.partition("/")
        try:
            num = int(num_text.strip())
        except ValueError:
            return []
        try:
            total = int(total_text.strip()) if total_text.strip() else 0
        except ValueError:
            total = 0
        if num <= 0:
            return []
        return [(num, total)]

    def set_cover(self, image_path: Path) -> bool:
        """Set cover art from an image file.

        Args:
            image_path: Path to image file

        Returns:
            True if successful
        """
        if not image_path.exists():
            return False

        try:
            data = image_path.read_bytes()
            mime = "image/jpeg"
            if image_path.suffix.lower() == ".png":
                mime = "image/png"

            if isinstance(self._file, EasyMP3):
                id3 = ID3(str(self.filepath))
                # Remove existing cover art
                for key in list(id3.keys()):
                    if key.startswith("APIC"):
                        del id3[key]
                id3.add(
                    APIC(encoding=3, mime=mime, type=3, desc="Cover", data=data)
                )
                id3.save()
                return True

            elif self.filepath.suffix.lower() == ".flac":
                pic = Picture()
                pic.type = 3
                pic.data = data
                pic.mime = mime
                self._file.clear_pictures()
                self._file.add_picture(pic)
                self._file.save()
                return True

            elif self.filepath.suffix.lower() in (".m4a", ".aac", ".mp4"):
                if not self._file.tags:
                    self._file.add_tags()
                fmt = (
                    MP4Cover.FORMAT_PNG
                    if mime == "image/png"
                    else MP4Cover.FORMAT_JPEG
                )
                self._file["covr"] = [MP4Cover(data, imageformat=fmt)]
                self._file.save()
                return True

        except Exception as e:
            logger.warning("Ошибка установки обложки: %s", e)

        return False


def get_tags(filepath: Path) -> AudioTags:
    """Convenience function to read tags from a file."""
    return Tagger(filepath).read()


def set_tags(filepath: Path, tags: AudioTags) -> bool:
    """Convenience function to write tags to a file."""
    return Tagger(filepath).write(tags)


def apply_cover_from_url(filepath: Path, url: str | None) -> bool:
    """Embed an image from a URL as cover art if the file has no cover yet.

    Used as a fallback source (e.g. YouTube thumbnail) when the primary
    metadata source (Deezer) provides no cover art.

    Returns True if a cover was written.
    """
    if not url:
        return False
    tags = get_tags(filepath)
    if tags.cover_data:
        return False
    try:
        from .fetcher import download_thumbnail

        cover_data, cover_mime = download_thumbnail(url)
    except Exception:
        return False
    if not cover_data:
        return False
    tags.cover_data = cover_data
    tags.cover_mime = cover_mime
    return set_tags(filepath, tags)
