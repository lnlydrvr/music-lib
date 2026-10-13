"""Tests for focused library service operations."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from conftest import MP3_FRAME
from src import services
from src.tagger import AudioTags, set_tags


def _track(path: Path, tags: AudioTags) -> Path:
    path.write_bytes(MP3_FRAME * 4)
    assert set_tags(path, tags)
    return path


def test_collect_lyrics_candidates_reads_only_lyrics_metadata(tmp_path):
    missing = _track(tmp_path / "missing.mp3", AudioTags(title="Song", artist="Artist"))
    _track(tmp_path / "ready.mp3", AudioTags(title="Ready", lyrics_synced="[00:01] done"))
    _track(tmp_path / "plain.mp3", AudioTags(title="Plain", lyrics="done"))

    candidates, errors, total = services.collect_lyrics_candidates(tmp_path)

    assert errors == 0
    assert total == 3
    assert len(candidates) == 1
    assert candidates[0]["path"] == str(missing)
    assert candidates[0]["title"] == "Song"
    assert candidates[0]["has_plain"] is False
    assert candidates[0]["fingerprint"]


def test_update_all_lyrics_skips_plain_text_before_fetch(tmp_path, monkeypatch):
    path = _track(tmp_path / "song.mp3", AudioTags(title="Song", artist="Artist"))
    candidates, _, _ = services.collect_lyrics_candidates(tmp_path)
    assert candidates[0]["path"] == str(path)
    assert set_tags(path, AudioTags(title="Song", artist="Artist", lyrics="manual"))
    monkeypatch.setattr(services, "fetch_lyrics", lambda *args: (_ for _ in ()).throw(AssertionError("fetch")))

    result = services.update_all_lyrics(tmp_path, candidates=candidates)

    assert result == {"updated": 0, "skipped": 0, "has_lyrics": 1, "errors": 0}


def test_update_all_lyrics_snapshot_rechecks_tags_before_fetch(tmp_path, monkeypatch):
    path = _track(tmp_path / "song.mp3", AudioTags(title="Song", artist="Artist"))
    candidates, _, _ = services.collect_lyrics_candidates(tmp_path)
    assert candidates[0]["path"] == str(path)
    assert set_tags(path, AudioTags(title="Song", artist="Artist", lyrics_synced="[00:01] manual"))
    monkeypatch.setattr(services, "library_files", lambda _: (_ for _ in ()).throw(AssertionError("scan")))
    monkeypatch.setattr(services, "fetch_lyrics", lambda *args: (_ for _ in ()).throw(AssertionError("fetch")))

    result = services.update_all_lyrics(tmp_path, candidates=candidates)

    assert result == {"updated": 0, "skipped": 0, "has_lyrics": 1, "errors": 0}


def test_update_all_lyrics_snapshot_rechecks_tags_before_write(tmp_path, monkeypatch):
    path = _track(tmp_path / "song.mp3", AudioTags(title="Song", artist="Artist"))
    candidates, _, _ = services.collect_lyrics_candidates(tmp_path)

    def fetch(*args):
        assert set_tags(path, AudioTags(title="Song", artist="Artist", lyrics_synced="[00:01] manual"))
        return SimpleNamespace(synced_lyrics="[00:01] fetched", plain_lyrics="")

    monkeypatch.setattr(services, "fetch_lyrics", fetch)

    result = services.update_all_lyrics(tmp_path, candidates=candidates)

    assert result == {"updated": 0, "skipped": 0, "has_lyrics": 1, "errors": 0}
