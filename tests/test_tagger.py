"""Tests for src/tagger.py — tag read/write across MP3 / FLAC / M4A."""
from __future__ import annotations

import pytest

from src.tagger import (
    AudioTags,
    Tagger,
    apply_cover_from_url,
    get_tags,
    set_tags,
)

COVER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def tagged_data() -> AudioTags:
    return AudioTags(
        title="Title", artist="Artist", album="Album", album_artist="Various",
        year="2001", track_number="3/12", genre="Rock", comment="nice",
        disc_number="1/2", isrc="ISRC", composer="Composer",
        publisher="Label", copyright="(c) 2001", lyrics="line1\nline2",
        lyrics_synced="[00:01.00] line1\n[00:05.00] line2",
        cover_data=COVER, cover_mime="image/png",
    )


class TestMp3Roundtrip:
    def test_full_roundtrip(self, audio_files, tagged_data):
        path = audio_files["mp3"]
        assert Tagger(path).write(tagged_data) is True
        read = Tagger(path).read()
        assert read.title == "Title"
        assert read.artist == "Artist"
        assert read.album == "Album"
        assert read.album_artist == "Various"
        assert read.year == "2001"
        assert read.track_number == "3/12"
        assert read.genre == "Rock"
        assert read.disc_number == "1/2"
        assert read.isrc == "ISRC"
        assert read.composer == "Composer"
        assert read.publisher == "Label"
        assert read.copyright == "(c) 2001"
        assert read.comment == "nice"
        assert read.lyrics == "line1\nline2"
        assert read.lyrics_synced == "[00:01.00] line1\n[00:05.00] line2"
        assert read.cover_data == COVER
        assert read.cover_mime == "image/png"


class TestFlacRoundtrip:
    def test_full_roundtrip(self, audio_files, tagged_data):
        path = audio_files["flac"]
        assert Tagger(path).write(tagged_data) is True
        read = Tagger(path).read()
        assert read.title == "Title"
        assert read.artist == "Artist"
        assert read.album == "Album"
        assert read.album_artist == "Various"
        assert read.year == "2001"
        assert read.track_number == "3/12"
        assert read.genre == "Rock"
        assert read.disc_number == "1/2"
        assert read.isrc == "ISRC"
        assert read.composer == "Composer"
        assert read.publisher == "Label"
        assert read.copyright == "(c) 2001"
        assert read.comment == "nice"
        assert read.lyrics == "line1\nline2"
        assert read.lyrics_synced == "[00:01.00] line1\n[00:05.00] line2"
        assert read.cover_data == COVER
        assert read.cover_mime == "image/png"

    def test_legacy_plain_key_reads_as_plain(self, audio_files):
        """Старые файлы хранили обычный текст в ключе 'lyrics'."""
        from mutagen.flac import FLAC

        path = audio_files["flac"]
        flac = FLAC(str(path))
        flac["lyrics"] = "legacy plain"
        flac.save()
        read = Tagger(path).read()
        assert read.lyrics == "legacy plain"
        assert read.lyrics_synced == ""


class TestM4aRoundtrip:
    def test_full_roundtrip(self, audio_files):
        path = audio_files["m4a"]
        tags = AudioTags(
            title="T", artist="A", album="Ab", album_artist="AA", year="2020",
            track_number="3/12", disc_number="1/2", genre="Pop",
            composer="C", publisher="P", comment="cmt", lyrics="lyrics",
            lyrics_synced="[00:01.00] la\n[00:02.00] lo",
            cover_data=COVER, cover_mime="image/png",
        )
        assert Tagger(path).write(tags) is True
        read = Tagger(path).read()
        assert read.title == "T"
        assert read.artist == "A"
        assert read.album == "Ab"
        assert read.album_artist == "AA"
        assert read.year == "2020"
        assert read.track_number == "3/12"
        assert read.disc_number == "1/2"
        assert read.genre == "Pop"
        assert read.composer == "C"
        assert read.publisher == "P"
        assert read.lyrics == "lyrics"
        assert read.lyrics_synced == "[00:01.00] la\n[00:02.00] lo"
        assert read.comment == "cmt"
        assert read.cover_data == COVER

    def test_parse_helpers(self):
        assert Tagger._parse_m4a_track("3/12") == [(3, 12)]
        assert Tagger._parse_m4a_track("5") == [(5, 0)]
        assert Tagger._parse_m4a_track("abc") == []
        assert Tagger._parse_m4a_disk("1/2") == [(1, 2)]
        assert Tagger._parse_m4a_disk("1") == [(1, 0)]
        assert Tagger._parse_m4a_disk("0/2") == []
        assert Tagger._parse_m4a_track(None) == []
        assert Tagger._parse_m4a_track(7) == [(7, 0)]
        assert Tagger._parse_m4a_disk(None) == []
        assert Tagger._get_m4a_track([(3, 12)]) == "3/12"
        assert Tagger._get_m4a_track([(3, 0)]) == "3"
        assert Tagger._get_m4a_track([(0, 0)]) == ""
        assert Tagger._get_m4a_track(None) == ""
        assert Tagger._get_m4a_disk([(1, 2)]) == "1/2"
        assert Tagger._get_m4a_disk([(1, 0)]) == "1"
        assert Tagger._get_m4a_disk([(0, 0)]) == ""

    def test_total_is_kept_and_empty_removes_key(self, audio_files):
        """'7/17' пишется как [(7,17)] и читается как '7/17'; пусто удаляет ключи."""
        from mutagen.mp4 import MP4

        path = audio_files["m4a"]
        assert Tagger(path).write(AudioTags(track_number="7/17", disc_number="2/3")) is True
        raw = MP4(str(path)).tags
        assert list(raw.get("trkn", [])) == [(7, 17)]
        assert list(raw.get("disk", [])) == [(2, 3)]
        assert Tagger(path).read().track_number == "7/17"
        assert Tagger(path).read().disc_number == "2/3"

        assert Tagger(path).write(AudioTags()) is True
        raw = MP4(str(path)).tags
        assert "trkn" not in (raw or {})
        assert "disk" not in (raw or {})
        assert Tagger(path).read().track_number == ""
        assert Tagger(path).read().disc_number == ""

    def test_int_fields_are_coerced(self, audio_files):
        """Non-str field values must not crash the write (was 'can't concat int to bytes')."""
        path = audio_files["m4a"]
        tags = AudioTags(
            title="T", artist="A", album="Ab", year=2011, genre="Поп",
            track_number=0, disc_number=3, publisher=None, comment=0,
        )
        assert Tagger(path).write(tags) is True
        read = Tagger(path).read()
        assert read.year == "2011"
        assert read.disc_number == "3"
        assert read.comment == "0"
        assert read.publisher == ""

    def test_int_fields_are_coerced_mp3(self, audio_files):
        path = audio_files["mp3"]
        tags = AudioTags(title="T", artist="A", year=2011, genre="Поп", disc_number=3)
        assert Tagger(path).write(tags) is True
        read = Tagger(path).read()
        assert read.year == "2011"
        assert read.disc_number == "3"


class TestSetCover:
    def test_mp3(self, audio_files, tmp_path):
        img = tmp_path / "cover.jpg"
        img.write_bytes(COVER)
        path = audio_files["mp3"]
        assert Tagger(path).set_cover(img) is True
        read = Tagger(path).read()
        assert read.cover_data == COVER

    def test_flac(self, audio_files, tmp_path):
        img = tmp_path / "cover.png"
        img.write_bytes(COVER)
        path = audio_files["flac"]
        assert Tagger(path).set_cover(img) is True
        assert Tagger(path).read().cover_data == COVER

    def test_m4a(self, audio_files, tmp_path):
        img = tmp_path / "cover.jpg"
        img.write_bytes(COVER)
        path = audio_files["m4a"]
        assert Tagger(path).set_cover(img) is True
        assert Tagger(path).read().cover_data == COVER

    def test_missing_image(self, audio_files, tmp_path):
        path = audio_files["mp3"]
        assert Tagger(path).set_cover(tmp_path / "nope.jpg") is False


class TestFallbacks:
    def test_unknown_suffix_reads_empty(self, tmp_path):
        p = tmp_path / "x.txt"
        p.write_text("hello")
        tags = Tagger(p).read()
        assert tags.title == ""
        assert tags.artist == ""

    def test_unknown_suffix_write_false(self, tmp_path):
        p = tmp_path / "x.txt"
        p.write_text("hello")
        assert Tagger(p).write(AudioTags(title="T")) is False

    def test_unknown_suffix_set_cover_false(self, tmp_path):
        p = tmp_path / "x.txt"
        p.write_text("hello")
        img = tmp_path / "c.jpg"
        img.write_bytes(COVER)
        assert Tagger(p).set_cover(img) is False

    def test_convenience_functions(self, mp3_stub):
        tags = AudioTags(title="S", artist="A", album="Al")
        assert set_tags(mp3_stub, tags) is True
        read = get_tags(mp3_stub)
        assert read.title == "S"
        assert read.artist == "A"


class TestApplyCoverFromUrl:
    def test_no_url(self):
        assert apply_cover_from_url("whatever.mp3", None) is False

    def test_existing_cover_kept(self, monkeypatch):
        monkeypatch.setattr(
            "src.tagger.get_tags",
            lambda _p: AudioTags(cover_data=b"have", cover_mime="image/jpeg"),
        )
        assert apply_cover_from_url("x.mp3", "http://cover.jpg") is False

    def test_applies_when_missing(self, monkeypatch):
        calls = {}

        def fake_thumbnail(url):
            calls["url"] = url
            return b"new", "image/jpeg"

        import src.tagger as tagger_mod
        import src.fetcher as fetcher_mod

        monkeypatch.setattr(
            "src.tagger.get_tags", lambda _p: AudioTags(title="T", artist="A")
        )
        monkeypatch.setattr(fetcher_mod, "download_thumbnail", fake_thumbnail)
        monkeypatch.setattr(
            "src.tagger.set_tags",
            lambda _p, tags: calls.update(tags=tags) or True,
        )
        assert apply_cover_from_url("x.mp3", "http://cover.jpg") is True
        assert calls["url"] == "http://cover.jpg"
        assert calls["tags"].cover_data == b"new"
        assert calls["tags"].cover_mime == "image/jpeg"

    def test_thumbnail_error_returns_false(self, monkeypatch):
        import src.fetcher as fetcher_mod

        monkeypatch.setattr(
            "src.tagger.get_tags", lambda _p: AudioTags(title="T", artist="A")
        )
        monkeypatch.setattr(
            fetcher_mod, "download_thumbnail", lambda url: (_ for _ in ()).throw(RuntimeError)
        )
        assert apply_cover_from_url("x.mp3", "http://cover.jpg") is False