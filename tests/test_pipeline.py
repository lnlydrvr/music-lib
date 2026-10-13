"""Tests for src/pipeline.py — лирикс + перенос файла из Inbox в библиотеку."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.pipeline import (
    apply_metadata_from_sources, fetch_and_apply_lyrics, move_to_library,
)
from src.tagger import set_tags, get_tags, AudioTags

from conftest import MP3_FRAME


def _stub(path: Path, tags: AudioTags | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(MP3_FRAME * 4)
    if tags is not None:
        set_tags(path, tags)
    return path


class TestFetchAndApplyLyrics:
    def test_no_title_returns_false(self, tmp_path, monkeypatch):
        p = _stub(tmp_path / "Inbox" / "a.mp3", AudioTags(title=""))
        called = []
        monkeypatch.setattr("src.pipeline.fetch_lyrics",
                            lambda *a, **k: called.append(1) or None)
        assert fetch_and_apply_lyrics(p) is False
        assert called == []

    def test_found_writes_lyrics(self, tmp_path, monkeypatch):
        p = _stub(tmp_path / "Inbox" / "a.mp3",
                  AudioTags(title="Song", artist="Artist"))
        from types import SimpleNamespace
        monkeypatch.setattr(
            "src.pipeline.fetch_lyrics",
            lambda *a, **k: SimpleNamespace(plain_lyrics="line 1\nline 2"),
        )
        assert fetch_and_apply_lyrics(p) is True
        assert get_tags(p).lyrics == "line 1\nline 2"

    def test_writes_synced_and_plain(self, tmp_path, monkeypatch):
        p = _stub(tmp_path / "Inbox" / "a.mp3",
                  AudioTags(title="Song", artist="Artist"))
        from types import SimpleNamespace
        monkeypatch.setattr(
            "src.pipeline.fetch_lyrics",
            lambda *a, **k: SimpleNamespace(
                plain_lyrics="line 1", synced_lyrics="[00:01.00] line 1"),
        )
        assert fetch_and_apply_lyrics(p) is True
        tags = get_tags(p)
        assert tags.lyrics == "line 1"
        assert tags.lyrics_synced == "[00:01.00] line 1"

    def test_skips_when_synced_present(self, tmp_path, monkeypatch):
        p = _stub(tmp_path / "Inbox" / "a.mp3",
                  AudioTags(title="Song", artist="Artist",
                            lyrics_synced="[00:01.00] already"))
        called = []
        monkeypatch.setattr("src.pipeline.fetch_lyrics",
                            lambda *a, **k: called.append(1) or None)
        assert fetch_and_apply_lyrics(p) is False
        assert called == []

    def test_keeps_existing_plain(self, tmp_path, monkeypatch):
        p = _stub(tmp_path / "Inbox" / "a.mp3",
                  AudioTags(title="Song", artist="Artist", lyrics="manual"))
        from types import SimpleNamespace
        monkeypatch.setattr(
            "src.pipeline.fetch_lyrics",
            lambda *a, **k: SimpleNamespace(
                plain_lyrics="lrc plain", synced_lyrics="[00:01.00] lrc"),
        )
        assert fetch_and_apply_lyrics(p) is True
        tags = get_tags(p)
        assert tags.lyrics == "manual"
        assert tags.lyrics_synced == "[00:01.00] lrc"

    def test_not_found_returns_false(self, tmp_path, monkeypatch):
        p = _stub(tmp_path / "Inbox" / "a.mp3",
                  AudioTags(title="Song", artist="Artist"))
        monkeypatch.setattr("src.pipeline.fetch_lyrics", lambda *a, **k: None)
        assert fetch_and_apply_lyrics(p) is False


class TestApplyMetadataFromSources:
    def _stub(self, tmp_path):
        return _stub(tmp_path / "Inbox" / "a.mp3")

    def _rec(self, **kw):
        from src.providers import ProviderRecord
        rec = ProviderRecord(source="iTunes")
        for k, v in kw.items():
            setattr(rec, k, v)
        return rec

    def test_no_sources_false(self, tmp_path, monkeypatch):
        p = self._stub(tmp_path)
        monkeypatch.setattr("src.providers.fetch_all",
                            lambda *a, **k: {})
        assert apply_metadata_from_sources(p, "Song", "Artist") is False

    def test_applies_first_record_tags(self, tmp_path, monkeypatch):
        p = self._stub(tmp_path)
        rec = self._rec(title="Точное название", artist="Настоящий артист",
                        album="Альбом", genre="Поп", cover_url="")
        monkeypatch.setattr("src.providers.fetch_all",
                            lambda *a, **k: {"iTunes": [rec]})
        assert apply_metadata_from_sources(p, "Song", "Artist") is True
        tags = get_tags(p)
        assert tags.title == "Точное название"
        assert tags.artist == "Настоящий артист"
        assert tags.album == "Альбом"
        assert tags.genre == "Поп"

    def test_applies_cover_from_source(self, tmp_path, monkeypatch):
        p = self._stub(tmp_path)
        rec = self._rec(title="T", artist="A", cover_url="http://x/i.png")
        monkeypatch.setattr("src.providers.fetch_all",
                            lambda *a, **k: {"iTunes": [rec]})
        monkeypatch.setattr(
            "src.fetcher.download_cover",
            lambda url: (b"\x89PNG\r\n\x1a\n" + b"\x00" * 10, "image/png"))
        assert apply_metadata_from_sources(p, "Song", "Artist") is True
        assert get_tags(p).cover_mime == "image/png"
        assert get_tags(p).cover_data

    def test_fetch_all_error_falls_back_to_thumbnail(self, tmp_path, monkeypatch):
        p = self._stub(tmp_path)
        monkeypatch.setattr("src.providers.fetch_all",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        monkeypatch.setattr("src.tagger.apply_cover_from_url",
                            lambda *a, **k: True)
        assert apply_metadata_from_sources(p, "Song", "Artist", "http://t.jpg") is True

    def test_empty_fetch_uses_thumbnail(self, tmp_path, monkeypatch):
        p = self._stub(tmp_path)
        monkeypatch.setattr("src.providers.fetch_all", lambda *a, **k: {})
        monkeypatch.setattr("src.tagger.apply_cover_from_url",
                            lambda *a, **k: True)
        assert apply_metadata_from_sources(p, "Song", "Artist", "http://t.jpg") is True


class TestMoveToLibrary:
    def test_moves_into_artist_album(self, tmp_path):
        out = tmp_path
        p = _stub(out / "Inbox" / "Old.mp3",
                  AudioTags(title="Song", artist="Artist", album="Album"))
        target = move_to_library(p, out)
        assert target == out / "Artist" / "Album" / "Song.mp3"
        assert target.exists()
        assert not p.exists()

    def test_moves_into_artist_only(self, tmp_path):
        out = tmp_path
        p = _stub(out / "Inbox" / "Old.mp3",
                  AudioTags(title="Song", artist="Artist"))
        target = move_to_library(p, out)
        assert target == out / "Artist" / "Song.mp3"

    def test_unknown_artist(self, tmp_path):
        out = tmp_path
        p = _stub(out / "Inbox" / "Old.mp3", AudioTags(title="Song"))
        target = move_to_library(p, out)
        assert target == out / "Неизвестный исполнитель" / "Song.mp3"

    def test_target_exists_returns_none(self, tmp_path):
        out = tmp_path
        p = _stub(out / "Inbox" / "Old.mp3",
                  AudioTags(title="Song", artist="Artist"))
        _stub(out / "Artist" / "Song.mp3")
        assert move_to_library(p, out) is None
        assert p.exists()

    def test_reuses_existing_artist_dir_translit(self, tmp_path):
        out = tmp_path
        (out / "Валентин Стрыкало").mkdir(parents=True)
        p = _stub(out / "Inbox" / "Old.mp3",
                  AudioTags(title="Фанк", artist="Valentin Strykalo"))
        target = move_to_library(p, out)
        assert target == out / "Валентин Стрыкало" / "Фанк.mp3"
        assert target.exists()
        assert not (out / "Valentin Strykalo").exists()

    def test_reuses_existing_artist_dir_case_insensitive(self, tmp_path):
        out = tmp_path
        (out / "Kanye West").mkdir(parents=True)
        p = _stub(out / "Inbox" / "Old.mp3",
                  AudioTags(title="Song", artist="kanye  west!"))
        target = move_to_library(p, out)
        assert target == out / "Kanye West" / "Song.mp3"

    def test_new_artist_creates_dir(self, tmp_path):
        out = tmp_path
        (out / "Валентин Стрыкало").mkdir(parents=True)
        p = _stub(out / "Inbox" / "Old.mp3",
                  AudioTags(title="Song", artist="Новый Артист"))
        target = move_to_library(p, out)
        assert target == out / "Новый Артист" / "Song.mp3"
