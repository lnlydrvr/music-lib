"""Tests for the unified library quality API."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.web.routes as routes
from src.tagger import AudioTags, set_tags
from src.web.server import create_app

pytestmark = pytest.mark.usefixtures("isolated_home")


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    import src.config as config
    home = tmp_path / "home"
    cfgdir = home / ".config" / "music-lib"
    cfgdir.mkdir(parents=True)
    monkeypatch.setattr(config, "CONFIG_DIR", cfgdir)
    monkeypatch.setattr(config, "CONFIG_PATH", cfgdir / "config.json")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))


@pytest.fixture
def client(tmp_path, monkeypatch):
    out = tmp_path / "library"
    out.mkdir()
    song = out / "song.mp3"
    song.write_bytes((b"\xff\xfb\x90\x44" + b"\x00" * 413) * 4)
    assert set_tags(song, AudioTags(title="Song", artist="Artist"))
    monkeypatch.setattr(routes, "_out_dir", lambda: out)
    return TestClient(create_app())


def test_quality_endpoint_returns_unified_issues_and_changes(client):
    response = client.get("/api/library/quality")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["counts"]["missing"] >= 1
    assert data["issues"]
    assert all("category" in issue and "path" in issue for issue in data["issues"])
    missing = next(issue for issue in data["issues"] if issue["message"].get("params", {}).get("field") == "cover")
    assert missing["message"]["code"] == "diagnostics.health.missing_tag"
    assert missing["message"]["params"]["field"] == "cover"
    assert "changes" in data
    assert len(data["tracks"]) == 1
    assert data["tracks"][0]["problem_count"] == len(data["tracks"][0]["issues"])
    assert data["tracks"][0]["path"] == data["issues"][0]["path"]
    assert data["tracks"][0]["title"] == "Song"
    assert data["tracks"][0]["artist"] == "Artist"
    assert data["tracks"][0]["album"] == ""


def test_quality_endpoint_accepts_inbox_flag(client, tmp_path):
    out = routes._out_dir()
    inbox = out / "Inbox"
    inbox.mkdir()
    song = inbox / "inbox.mp3"
    song.write_bytes((b"\xff\xfb\x90\x44" + b"\x00" * 413) * 4)
    assert set_tags(song, AudioTags(title="Inbox", artist="Artist"))

    response = client.get("/api/library/quality", params={"include_inbox": 1})

    assert response.json()["total"] == 2
    assert any(issue["inbox"] for issue in response.json()["issues"])


def test_quality_plan_endpoint_returns_dto_without_touching_files(client):
    before = (routes._out_dir() / "song.mp3").read_bytes()

    response = client.post("/api/library/quality/plan", json={})

    assert response.status_code == 200
    data = response.json()
    assert data["counts"]["fixes"] == 1  # loose-файл в корне библиотеки
    assert data["fixes"][0]["action"] == "move"
    assert data["fixes"][0]["to"].endswith("Artist/Song.mp3")
    assert data["conflicts"] == []
    assert (routes._out_dir() / "song.mp3").read_bytes() == before


def test_quality_plan_endpoint_filters_by_paths(client, tmp_path):
    out = routes._out_dir()
    other = out / "other.mp3"
    other.write_bytes((b"\xff\xfb\x90\x44" + b"\x00" * 413) * 4)
    assert set_tags(other, AudioTags(title="Other", artist="Artist"))

    response = client.post(
        "/api/library/quality/plan",
        json={"paths": [str(other)]},
    )

    data = response.json()
    assert data["files"] == [str(other)]


def test_quality_apply_endpoint_returns_per_file_results(client):
    response = client.post("/api/library/quality/apply", json={})

    assert response.status_code == 200
    data = response.json()
    assert data["files"] == 1
    assert data["results"][0]["status"] == "applied"
    assert data["results"][0]["to"].endswith("Artist/Song.mp3")
    assert not (routes._out_dir() / "song.mp3").exists()
    assert (routes._out_dir() / "Artist" / "Song.mp3").exists()

    # Повторное применение идемпотентно.
    again = client.post("/api/library/quality/apply", json={}).json()
    assert again["applied"] == 0
    assert again["errors"] == 0


def test_quality_apply_reports_conflict_but_applies_rest(client, tmp_path):
    out = routes._out_dir()
    other = out / "other.mp3"
    other.write_bytes((b"\xff\xfb\x90\x44" + b"\x00" * 413) * 4)
    assert set_tags(other, AudioTags(title="Other ", artist="Artist"))

    plan = client.post("/api/library/quality/plan", json={}).json()
    occupied = None
    for fix in plan["fixes"]:
        if fix["path"].endswith("song.mp3"):
            occupied = Path(fix["to"])
    occupied.parent.mkdir(parents=True, exist_ok=True)
    occupied.write_bytes(b"occupied")

    response = client.post("/api/library/quality/apply", json={})

    data = response.json()
    assert data["conflicts"] == 1
    by_path = {r["path"]: r for r in data["results"]}
    assert by_path[[p for p in by_path if p.endswith("song.mp3")][0]]["status"] == "conflict"
    assert by_path[str(other)]["status"] == "applied"


def test_quality_plan_detects_duplicate_field_selection(client, tmp_path):
    out = routes._out_dir()
    other = out / "other.mp3"
    other.write_bytes((b"\xff\xfb\x90\x44" + b"\x00" * 413) * 4)
    assert set_tags(other, AudioTags(title="Other ", artist="Artist"))

    response = client.post("/api/library/quality/plan", json={
        "changes": [
            {"path": str(other), "field": "title"},
            {"path": str(other), "field": "title"},
        ],
    })

    data = response.json()
    assert data["conflicts"][0]["kind"] == "duplicate_field"
    assert data["conflicts"][0]["field"] == "title"
    assert data["conflicts"][0]["message"]["code"] == "diagnostics.quality.duplicate_field"
    assert all(c["path"] != str(other) for c in data["changes"])
