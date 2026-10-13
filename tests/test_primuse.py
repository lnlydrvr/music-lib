"""Тесты Primuse sidecar (.lrc + -cover.jpg)."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import src.config as config
import src.primuse as primuse
import src.web.routes as routes
from src.tagger import AudioTags, set_tags
from src.web.server import create_app


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    cfgdir = home / ".config" / "music-lib"
    monkeypatch.setattr(config, "CONFIG_DIR", cfgdir)
    monkeypatch.setattr(config, "CONFIG_PATH", cfgdir / "config.json")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    return home


@pytest.fixture
def output_dir(tmp_path) -> Path:
    out = tmp_path / "library"
    out.mkdir()
    return out


def _enable():
    config.save_config({config.PRIMUSE_SIDECAR_KEY: True})


def _tags(**kw):
    base = dict(title="Моя Песня", artist="A", lyrics_synced="[00:01.00] la",
                lyrics="plain", cover_data=b"JPEGDATA", cover_mime="image/jpeg")
    base.update(kw)
    return SimpleNamespace(**base)


class TestGetter:
    def test_default_disabled(self, isolated_home):
        assert config.get_primuse_sidecar() is False

    def test_reads_true(self, isolated_home):
        config.save_config({config.PRIMUSE_SIDECAR_KEY: True})
        assert config.get_primuse_sidecar() is True

    def test_string_values(self, isolated_home):
        config.save_config({config.PRIMUSE_SIDECAR_KEY: "yes"})
        assert config.get_primuse_sidecar() is True
        config.save_config({config.PRIMUSE_SIDECAR_KEY: "0"})
        assert config.get_primuse_sidecar() is False


class TestNaming:
    def test_from_title(self, tmp_path):
        audio = tmp_path / "song.mp3"
        lrc, cover = primuse.sidecar_paths(audio, "Моя Песня")
        assert lrc.name == "Моя Песня.lrc"
        assert cover.name == "Моя Песня-cover.jpg"
        assert lrc.parent == tmp_path

    def test_sanitize(self, tmp_path):
        audio = tmp_path / "song.mp3"
        lrc, cover = primuse.sidecar_paths(audio, 'a/b:c*?Title"')
        assert "/" not in lrc.name and ":" not in lrc.name
        assert cover.name.endswith("-cover.jpg")

    def test_fallback_stem(self, tmp_path):
        audio = tmp_path / "mystem.mp3"
        lrc, cover = primuse.sidecar_paths(audio, "")
        assert lrc.name == "mystem.lrc"
        assert cover.name == "mystem-cover.jpg"


class TestWrite:
    def test_disabled_noop(self, isolated_home, tmp_path):
        audio = tmp_path / "s.mp3"
        audio.write_bytes(b"x")
        res = primuse.write_sidecars(audio, _tags())
        assert res["written"] == []

    def test_writes_both(self, isolated_home, tmp_path):
        _enable()
        audio = tmp_path / "s.mp3"
        audio.write_bytes(b"x")
        res = primuse.write_sidecars(audio, _tags(title="Hit"))
        assert (tmp_path / "Hit.lrc").read_text(encoding="utf-8").startswith("[00:01.00]")
        assert (tmp_path / "Hit-cover.jpg").read_bytes() == b"JPEGDATA"
        assert len(res["written"]) == 2

    def test_fallback_plain(self, isolated_home, tmp_path):
        _enable()
        audio = tmp_path / "s.mp3"
        audio.write_bytes(b"x")
        primuse.write_sidecars(audio, _tags(title="P", lyrics_synced="", lyrics="plain text"))
        assert (tmp_path / "P.lrc").read_text(encoding="utf-8").strip() == "plain text"

    def test_skip_empty(self, isolated_home, tmp_path):
        _enable()
        audio = tmp_path / "s.mp3"
        audio.write_bytes(b"x")
        res = primuse.write_sidecars(audio, _tags(title="E", lyrics_synced="",
                                                  lyrics="", cover_data=None))
        assert res["written"] == []
        assert not (tmp_path / "E.lrc").exists()
        assert not (tmp_path / "E-cover.jpg").exists()

    def test_synced_preferred(self, isolated_home, tmp_path):
        _enable()
        audio = tmp_path / "s.mp3"
        audio.write_bytes(b"x")
        primuse.write_sidecars(audio, _tags(title="S"))
        assert "la" in (tmp_path / "S.lrc").read_text(encoding="utf-8")


class TestDeleteSync:
    def test_delete(self, isolated_home, tmp_path):
        _enable()
        audio = tmp_path / "s.mp3"
        audio.write_bytes(b"x")
        primuse.write_sidecars(audio, _tags(title="Hit"))
        assert primuse.delete_sidecars(audio, "Hit") == 2
        assert not (tmp_path / "Hit.lrc").exists()

    def test_sync_after_move(self, isolated_home, tmp_path):
        _enable()
        old = tmp_path / "old.mp3"
        new = tmp_path / "sub" / "new.mp3"
        new.parent.mkdir()
        old.write_bytes(b"x")
        new.write_bytes(b"x")
        (tmp_path / "Old.lrc").write_text("x", encoding="utf-8")
        primuse.sync_after_move(old, new, tags=_tags(title="New"), old_title="Old")
        assert not (tmp_path / "Old.lrc").exists()
        assert (new.parent / "New.lrc").exists()


class TestCleanup:
    def test_cleanup_all_including_inbox(self, tmp_path):
        out = tmp_path / "lib"
        inbox = out / "Inbox"
        inbox.mkdir(parents=True)
        (out / "A.lrc").write_text("x", encoding="utf-8")
        (out / "A-cover.jpg").write_bytes(b"j")
        (inbox / "B.lrc").write_text("x", encoding="utf-8")
        (inbox / "B-cover.JPG").write_bytes(b"j")
        (out / "cover.jpg").write_bytes(b"keep")
        (out / "folder.jpg").write_bytes(b"keep")
        (out / "song.mp3").write_bytes(b"keep")
        (out / "notes.txt").write_text("keep", encoding="utf-8")
        res = primuse.cleanup_library(out)
        assert res["deleted_lrc"] == 2
        assert res["deleted_covers"] == 2
        assert (out / "cover.jpg").exists()
        assert (out / "folder.jpg").exists()
        assert (out / "song.mp3").exists()

    def test_preview_no_delete(self, tmp_path):
        out = tmp_path / "lib"
        out.mkdir()
        (out / "A.lrc").write_text("x", encoding="utf-8")
        prev = primuse.preview_cleanup(out)
        assert prev["lrc"] == 1
        assert (out / "A.lrc").exists()


def _mp3_stub(path: Path, title="Song"):
    frame = b"\xff\xfb\x90\x44" + b"\x00" * 413
    path.write_bytes(frame * 4)
    tags = AudioTags(title=title, artist="Artist", album="Album", year="2020",
                     lyrics_synced="[00:01.00] la", cover_data=b"JPEGDATA",
                     cover_mime="image/jpeg")
    assert set_tags(path, tags)


class TestWebAPI:
    @pytest.fixture
    def client(self, output_dir, monkeypatch):
        monkeypatch.setattr(routes, "_out_dir", lambda: output_dir)
        return TestClient(create_app())

    def test_settings_roundtrip(self, isolated_home, client):
        assert client.get("/api/settings").json()["primuse_sidecar"] is False
        r = client.put("/api/settings", json={"primuse_sidecar": True})
        assert r.status_code == 200
        assert client.get("/api/settings").json()["primuse_sidecar"] is True
        r = client.put("/api/settings", json={"primuse_sidecar": "yes"})
        assert client.get("/api/settings").json()["primuse_sidecar"] is True

    def test_tags_apply_creates_sidecar(self, isolated_home, client, output_dir):
        _enable()
        p = output_dir / "song.mp3"
        _mp3_stub(p, title="HitSong")
        r = client.post("/api/tags/apply", json={"path": str(p), "fields": {"genre": "Pop"}})
        assert r.status_code == 200
        assert (output_dir / "HitSong.lrc").exists()
        assert (output_dir / "HitSong-cover.jpg").exists()

    def test_backfill_and_cleanup(self, isolated_home, client, output_dir):
        import time

        _enable()
        _mp3_stub(output_dir / "a.mp3", title="SongA")
        job = client.post("/api/primuse/backfill").json()["job_id"]
        deadline = time.time() + 5
        while time.time() < deadline:
            st = client.get(f"/api/jobs/{job}").json()
            if st["status"] == "done":
                break
        assert (output_dir / "SongA.lrc").exists()
        prev = client.get("/api/primuse/cleanup/preview").json()
        assert prev["lrc"] >= 1
        job2 = client.post("/api/primuse/cleanup").json()["job_id"]
        deadline = time.time() + 5
        while time.time() < deadline:
            st = client.get(f"/api/jobs/{job2}").json()
            if st["status"] == "done":
                assert st["result"]["deleted_lrc"] >= 1
                break
        assert not (output_dir / "SongA.lrc").exists()
