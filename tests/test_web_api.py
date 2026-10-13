"""Тесты Web API (FastAPI + TestClient): изолированный HOME, tmp-библиотека.

Сетевые операции (download, search, lyrics, shazam, радио YouTube Music) стабаются
через monkeypatch — никакой реальной сети.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import src.web.routes as routes
from src.tagger import AudioTags, set_tags
from src.web.jobs import jobs
from src.web.server import create_app

pytestmark = pytest.mark.usefixtures("isolated_home")


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    import src.config as config
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    cfgdir = home / ".config" / "music-lib"
    monkeypatch.setattr(config, "CONFIG_DIR", cfgdir)
    monkeypatch.setattr(config, "CONFIG_PATH", cfgdir / "config.json")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))


@pytest.fixture
def output_dir(tmp_path) -> Path:
    out = tmp_path / "library"
    out.mkdir()
    return out


@pytest.fixture
def client(output_dir, monkeypatch) -> TestClient:
    monkeypatch.setattr(routes, "_out_dir", lambda: output_dir)
    return TestClient(create_app())


@pytest.fixture
def mp3(tmp_path, output_dir) -> Path:
    frame = b"\xff\xfb\x90\x44" + b"\x00" * 413
    p = output_dir / "song.mp3"
    p.write_bytes(frame * 4)
    tags = AudioTags(title="Song", artist="Artist", album="Album", year="2020")
    assert set_tags(p, tags)
    return p


def wait_job(client: TestClient, job_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = client.get(f"/api/jobs/{job_id}").json()
        if st["status"] in ("done", "error"):
            return st
        time.sleep(0.05)
    raise AssertionError(f"Задача не завершилась: {job_id}")


# --- Состояние / настройки ------------------------------------------------


def test_state_counts(client, mp3):
    data = client.get("/api/state").json()
    assert data["tracks"] == 1
    assert data["artists"] == 1
    assert data["output_dir"]


def test_album_nfo_returns_review_and_styles(client, mp3):
    """Данные album.nfo читаются из папки трека и XML-сущности декодируются."""
    (mp3.parent / "album.nfo").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
        <album>
          <review>Поп и R&amp;B</review>
          <style>поп</style>
          <style>R&amp;B</style>
        </album>""",
        encoding="utf-8",
    )

    response = client.get("/api/library/album-nfo", params={"path": str(mp3)})

    assert response.status_code == 200
    assert response.json() == {"review": "Поп и R&B", "styles": ["поп", "R&B"]}


def test_home_aggregate(client, mp3):
    data = client.get("/api/home").json()
    assert data["state"]["tracks"] == 1
    assert data["genres"] == []  # у mp3-стаба жанр не задан
    assert data["artists"] == [{"name": "Artist", "count": 1, "pct": 100.0}]  # фолбэк на Artist
    assert data["recent"]  # по mtime
    assert data["recent"][0]["title"] == "Song"
    assert data["health"]["total"] == 1
    assert data["shazam"] == {"configured": False, "count": 0, "file": ""}


def test_home_genres(client, mp3):
    song2 = mp3.parent / "song2.mp3"
    frame = b"\xff\xfb\x90\x44" + b"\x00" * 413
    song2.write_bytes(frame * 4)
    from src.tagger import set_tags
    set_tags(song2, AudioTags(title="Song 2", artist="Artist", genre="Rock", album_artist="Album Artist"))
    data = client.get("/api/home").json()
    assert data["genres"] == [{"name": "Rock", "count": 1, "pct": 50.0}]
    assert data["artists"] == [
        {"name": "Artist", "count": 1, "pct": 50.0},
        {"name": "Album Artist", "count": 1, "pct": 50.0},
    ]


def test_home_artists_uses_album_artist(client, mp3, monkeypatch):
    frame = b"\xff\xfb\x90\x44" + b"\x00" * 413
    p = mp3.parent / "album.mp3"
    p.write_bytes(frame * 4)
    from src.tagger import set_tags
    set_tags(p, AudioTags(title="Album cut", artist="Performer", album_artist="Album Artist"))
    set_tags(mp3, AudioTags(title="Solo", artist="Soloist"))
    data = client.get("/api/home").json()
    assert data["artists"][0]["name"] == "Album Artist", \
        "при наличии Album Artist берётся он"
    assert any(a["name"] == "Soloist" for a in data["artists"]), \
        "без Album Artist берётся Artist"


def test_home_cached(client, mp3, monkeypatch):
    calls = {"n": 0}
    real = routes.collect_quality
    def counting(out, include_inbox=False):
        calls["n"] += 1
        return real(out, include_inbox=include_inbox)
    monkeypatch.setattr(routes, "collect_quality", counting)
    client.get("/api/home")
    client.get("/api/home")
    assert calls["n"] == 1, "второй запрос /api/home должен браться из кэша"


def test_settings_get(client):
    data = client.get("/api/settings").json()
    assert data["default_format"] in data["formats"]
    assert data["source_format"] in data["source_formats"]
    assert set(data["source_formats"]) == {"m4a", "opus"}
    assert data["language"] is None


def test_settings_language_choice_and_omitted_update_preserves_it(client):
    assert client.put("/api/settings", json={"language": "ru"}).status_code == 200
    assert client.get("/api/settings").json()["language"] == "ru"

    assert client.put("/api/settings", json={"default_quality": 128}).status_code == 200
    assert client.get("/api/settings").json()["language"] == "ru"

    assert client.put("/api/settings", json={"language": "en"}).status_code == 200
    assert client.get("/api/settings").json()["language"] == "en"


def test_settings_concurrent_updates_preserve_both_fields(client, monkeypatch):
    """Interleaved requests must not lose an unrelated settings update."""
    import src.config as config

    real_save = config.save_config
    first_save_started = __import__("threading").Event()
    release_first_save = __import__("threading").Event()
    calls = 0

    def interleaved_save(value):
        nonlocal calls
        calls += 1
        if calls == 1:
            first_save_started.set()
            assert release_first_save.wait(timeout=2)
        real_save(value)

    monkeypatch.setattr(config, "save_config", interleaved_save)

    with ThreadPoolExecutor(max_workers=2) as pool:
        language = pool.submit(routes.api_put_settings, {"language": "ru"})
        assert first_save_started.wait(timeout=2)
        quality = pool.submit(routes.api_put_settings, {"default_quality": 128})
        release_first_save.set()
        assert language.result(timeout=2)["status"] == "ok"
        assert quality.result(timeout=2)["status"] == "ok"

    assert config.load_config() == {"language": "ru", "default_quality": 128}


def test_settings_invalid_language_returns_structured_error(client):
    response = client.put("/api/settings", json={"language": "de"})

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "code": "api.errors.invalid_setting",
        "params": {"key": "language"},
        "message": "Invalid value: language",
    }


def test_settings_invalid_persisted_language_is_reported_as_unset(client):
    import src.config as config

    config.save_config({config.LANGUAGE_KEY: "de"})

    assert client.get("/api/settings").json()["language"] is None


def test_settings_put_validates(client):
    r = client.put("/api/settings", json={"default_quality": 9999})
    assert r.status_code == 400
    r = client.put("/api/settings", json={"default_quality": 128})
    assert r.status_code == 200
    assert client.get("/api/settings").json()["default_quality"] == 128


def test_settings_put_bad_format(client):
    assert client.put("/api/settings", json={"default_format": "wav"}).status_code == 400


def test_settings_put_source_format(client):
    assert client.put("/api/settings", json={"source_format": "flac"}).status_code == 400
    assert client.put("/api/settings", json={"source_format": "opus"}).status_code == 200
    assert client.get("/api/settings").json()["source_format"] == "opus"
    assert client.put("/api/settings", json={"source_format": "m4a"}).status_code == 200
    assert client.get("/api/settings").json()["source_format"] == "m4a"


def test_settings_get_metadata_sources(client):
    data = client.get("/api/settings").json()
    assert "metadata_sources" in data
    assert "metadata_sources_order" in data
    assert "metadata_sources_available" in data
    assert "iTunes" in data["metadata_sources_available"]
    assert isinstance(data["metadata_sources"], list)
    assert isinstance(data["metadata_sources_order"], list)


def test_settings_put_metadata_sources(client):
    r = client.put("/api/settings", json={"metadata_sources": ["Discogs", "iTunes"]})
    assert r.status_code == 200
    data = client.get("/api/settings").json()
    # порядок из payload сохраняется (задаёт приоритет подстановки тегов)
    assert data["metadata_sources"] == ["Discogs", "iTunes"]


def test_settings_put_metadata_unknown(client):
    r = client.put("/api/settings", json={"metadata_sources": ["Nope"]})
    assert r.status_code == 400


def test_settings_put_metadata_not_list(client):
    r = client.put("/api/settings", json={"metadata_sources": "iTunes"})
    assert r.status_code == 400


def test_settings_put_metadata_order(client):
    r = client.put("/api/settings", json={"metadata_sources_order": ["Deezer", "iTunes"]})
    assert r.status_code == 200
    data = client.get("/api/settings").json()
    # недостающий известный источник дописывается в конец
    assert data["metadata_sources_order"] == ["Deezer", "iTunes", "Discogs"]


def test_settings_put_metadata_order_keeps_enabled(client):
    client.put("/api/settings", json={"metadata_sources": ["Discogs"]})
    client.put("/api/settings", json={"metadata_sources_order": ["iTunes", "Discogs", "Deezer"]})
    data = client.get("/api/settings").json()
    # порядок и включённость независимы
    assert data["metadata_sources_order"] == ["iTunes", "Discogs", "Deezer"]
    assert data["metadata_sources"] == ["Discogs"]


def test_settings_put_metadata_order_unknown(client):
    r = client.put("/api/settings", json={"metadata_sources_order": ["Nope"]})
    assert r.status_code == 400


def test_settings_put_metadata_order_not_list(client):
    r = client.put("/api/settings", json={"metadata_sources_order": "iTunes"})
    assert r.status_code == 400


def test_settings_name_translit(client):
    data = client.get("/api/settings").json()
    assert data["name_translit"] == "auto"
    assert client.put("/api/settings", json={"name_translit": "wat"}).status_code == 400
    assert client.put("/api/settings", json={"name_translit": "cyrillic"}).status_code == 200
    assert client.get("/api/settings").json()["name_translit"] == "cyrillic"
    assert client.put("/api/settings", json={"name_translit": "latin"}).status_code == 200
    assert client.get("/api/settings").json()["name_translit"] == "latin"


def test_settings_put_metadata_empty(client):
    r = client.put("/api/settings", json={"metadata_sources": []})
    assert r.status_code == 200
    assert client.get("/api/settings").json()["metadata_sources"] == []


def test_settings_youtube_defaults(client):
    data = client.get("/api/settings").json()
    assert data["youtube_browser"] == "safari"
    assert data["youtube_browsers"] == ["safari", "chrome", "chromium", "firefox", "edge"]
    assert data["youtube_cookies_set"] is False
    assert data["youtube_cookies_file"] == ""


def test_settings_put_youtube_browser(client):
    r = client.put("/api/settings", json={"youtube_browser": "chrome"})
    assert r.status_code == 200
    assert client.get("/api/settings").json()["youtube_browser"] == "chrome"
    assert client.put("/api/settings", json={"youtube_browser": "Nope"}).status_code == 400
    assert client.put("/api/settings", json={"youtube_browser": "brave"}).status_code == 400
    r = client.put("/api/settings", json={"youtube_browser": ""})
    assert r.status_code == 200
    assert client.get("/api/settings").json()["youtube_browser"] == "safari"


VALID_COOKIES = (
    "# Netscape HTTP Cookie File\n"
    ".youtube.com\tTRUE\t/\tTRUE\t1893456000\tSID\tabc123\n"
    ".google.com\tTRUE\t/\tTRUE\t1893456000\tNID\txyz\n"
)


def test_cookies_upload_flow(client):
    assert client.post("/api/settings/cookies", json={"content": "hello"}).status_code == 400
    assert client.post(
        "/api/settings/cookies",
        json={"content": ".example.com\tTRUE\t/\tTRUE\t1\tSID\tabc"},
    ).status_code == 400
    r = client.post("/api/settings/cookies", json={"content": VALID_COOKIES})
    assert r.status_code == 200
    assert r.json()["lines"] == 2
    data = client.get("/api/settings").json()
    assert data["youtube_cookies_set"] is True
    assert data["youtube_cookies_file"].endswith("youtube.txt")
    assert client.delete("/api/settings/cookies").status_code == 200
    assert client.get("/api/settings").json()["youtube_cookies_set"] is False


def test_cookies_check_selected_browser(client, monkeypatch):
    import yt_dlp.cookies as ytcookies

    class FakeCookie:
        def __init__(self, name, domain):
            self.name = name
            self.domain = domain

    def fake_extract(browser, profile=None):
        if profile:
            return [FakeCookie("SID", ".youtube.com")]
        if browser == "safari":
            return [FakeCookie("SID", ".youtube.com"),
                    FakeCookie("PREF", ".youtube.com"),
                    FakeCookie("NID", ".google.com")]
        if browser == "chrome":
            return []
        raise RuntimeError("no db")

    monkeypatch.setattr(ytcookies, "extract_cookies_from_browser", fake_extract)
    monkeypatch.setattr("src.ytcookies.discover_safari_profiles",
                        lambda: [("D7B4ACE1", "/prof/cookies")])

    data = client.post("/api/settings/cookies/check", json={"browser": "chrome"}).json()
    assert data["browser"] == "chrome"
    assert [b["browser"] for b in data["browsers"]] == ["chrome"]
    assert data["browsers"][0]["status"] == "empty"

    data = client.post("/api/settings/cookies/check", json={"browser": "safari"}).json()
    by_name = {b["browser"]: b for b in data["browsers"]}
    assert set(by_name) == {"safari", "safari:профиль D7B4ACE1"}
    assert by_name["safari"]["auth"] is True
    assert by_name["safari"]["cookies"] == 2
    assert by_name["safari:профиль D7B4ACE1"]["auth"] is True

    data = client.post("/api/settings/cookies/check", json={}).json()
    assert data["browser"] == "safari"  # пустое тело = настроенный (дефолт safari)

    unknown = client.post("/api/settings/cookies/check", json={"browser": "nope"})
    assert unknown.status_code == 400
    assert unknown.json()["detail"] == {
        "code": "api.errors.unknown_browser",
        "params": {"browser": "nope", "available": "safari, chrome, chromium, firefox, edge"},
        "message": "Unknown browser: nope (available: safari, chrome, chromium, firefox, edge)",
    }


def test_verify_age_flow(client, monkeypatch):
    import yt_dlp

    import src.ytcookies as ytc

    cands = [{"cookiesfrombrowser": ("safari", "/p1")},
             {"cookiesfrombrowser": ("safari",)},
             {}]
    monkeypatch.setattr(ytc, "cookie_opt_candidates", lambda **kw: list(cands))

    calls = {"n": 0}

    class FakeYDL:
        def __init__(self, opts=None):
            self.opts = opts or {}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download=False):
            calls["n"] += 1
            assert "PY4V9eD0-F8" in url
            if calls["n"] == 1:
                raise RuntimeError("Sign in to confirm your age")
            if calls["n"] == 2:
                raise RuntimeError("Sorry, this content is age-restricted")
            return {"title": "Age Vid"}

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)
    data = client.post("/api/settings/cookies/verify-age", json={}).json()
    assert data["verified_18"] is True
    assert [c["reason"] for c in data["checks"]] == ["gate", "blocked", "ok"]
    assert data["checks"][2]["title"] == "Age Vid"
    assert calls["n"] == 3

    assert client.post("/api/settings/cookies/verify-age",
                       json={"video_id": "bad"}).status_code == 400


# --- Теги / обложка / текст -----------------------------------------------


@pytest.fixture(autouse=True)
def _clear_meta_cache():
    routes.meta_cache_clear()
    yield
    routes.meta_cache_clear()


def test_tags_404(client):
    assert client.get("/api/tags", params={"path": "/nope.mp3"}).status_code == 404


def test_tags_get_put(client, mp3):
    tags = client.get("/api/tags", params={"path": str(mp3)}).json()
    assert tags["title"] == "Song"
    fields = {"title": "New Title", "year": "2021"}
    r = client.put("/api/tags", json={"path": str(mp3), "fields": fields})
    assert r.status_code == 200
    assert r.json()["title"] == "New Title"
    # год-ерунда отклоняется
    assert client.put("/api/tags", json={"path": str(mp3),
                                         "fields": {"year": "abcd"}}).status_code == 400
    # track_number должен быть числом
    assert client.put("/api/tags", json={"path": str(mp3),
                                          "fields": {"track_number": "x"}}).status_code == 400


def test_tags_apply_returns_structured_validation_descriptors(client, mp3):
    response = client.post("/api/tags/apply", json={
        "path": str(mp3),
        "fields": {"year": "twenty", "track_number": "one"},
    })

    assert response.status_code == 400
    assert response.json() == {
        "detail": {
            "code": "api.errors.check_fields",
            "params": {},
            "message": "Check the fields",
        },
        "errors": {
            "year": {
                "code": "api.fields.year_four_digits",
                "params": {},
                "message": "Year must be four digits, e.g. 2024",
            },
            "track_number": {
                "code": "api.fields.integer_required",
                "params": {},
                "message": "Must be an integer",
            },
        },
    }


def test_owned_file_errors_use_stable_descriptors(client):
    response = client.get("/api/tags", params={"path": "/nope.mp3"})

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "code": "api.errors.file_not_found",
        "params": {"path": "/nope.mp3"},
        "message": "File not found: /nope.mp3",
    }


def test_cover_and_lyrics_missing(client, mp3):
    tags = client.get("/api/tags", params={"path": str(mp3)}).json()
    assert tags["has_cover"] is False
    assert client.get("/api/cover", params={"path": str(mp3)}).status_code == 404
    r = client.get("/api/lyrics/missing")
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["missing"][0]["path"] == str(mp3)


def test_lyrics_missing_uses_light_candidates_and_returns_snapshot(client, mp3, monkeypatch):
    calls = {"scan": 0}

    def scan_library_forbidden(_out):
        calls["scan"] += 1
        raise AssertionError("analytics scan не нужен")

    monkeypatch.setattr(routes, "scan_library", scan_library_forbidden)
    data = client.get("/api/lyrics/missing").json()

    assert calls["scan"] == 0
    assert data["missing"][0]["path"] == str(mp3)
    assert isinstance(data["snapshot"], str)


def test_lyrics_view(client, mp3):
    r = client.get("/api/lyrics", params={"path": str(mp3)})
    assert r.status_code == 200
    assert r.json()["lyrics"] == ""
    assert r.json()["synced_lyrics"] == ""


def test_lyrics_update_single(client, mp3, monkeypatch):
    monkeypatch.setattr(routes, "fetch_and_apply_lyrics", lambda fp: True)
    r = client.post("/api/lyrics/update", json={"path": str(mp3)})
    assert r.status_code == 200
    assert r.json()["updated"] is True


def test_lyrics_update_all_job(client, mp3, monkeypatch):
    monkeypatch.setattr(
        routes.services, "update_all_lyrics",
        lambda out, on_progress=None: {"updated": 1, "skipped": 0,
                                       "has_lyrics": 0, "errors": 0})
    r = client.post("/api/lyrics/update-all")
    assert r.status_code == 200
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "done"
    assert st["result"]["updated"] == 1


def test_lyrics_update_all_uses_candidates_from_snapshot(client, mp3, monkeypatch):
    snapshot = client.get("/api/lyrics/missing").json()["snapshot"]
    received = {}

    def update(out, on_progress=None, candidates=None):
        received["candidates"] = candidates
        return {"updated": 0, "skipped": 1, "has_lyrics": 0, "errors": 0}

    monkeypatch.setattr(routes.services, "update_all_lyrics", update)
    response = client.post("/api/lyrics/update-all", json={"snapshot": snapshot})
    status = wait_job(client, response.json()["job_id"])

    assert status["status"] == "done"
    assert received["candidates"] is not None
    assert received["candidates"][0]["path"] == str(mp3)


# --- Библиотека ------------------------------------------------------------


def test_library_list(client, mp3):
    items = client.get("/api/library").json()
    assert len(items) == 1
    assert items[0]["title"] == "Song"
    assert items[0]["path"] == str(mp3)


def test_library_sort_path_uses_relative_path_order(client, output_dir):
    paths = []
    for artist, title in [("Zulu", "First"), ("Alpha", "Second")]:
        p = output_dir / f"{artist}.mp3"
        p.write_bytes((b"\xff\xfb\x90\x44" + b"\x00" * 413) * 4)
        assert set_tags(p, AudioTags(title=title, artist=artist))
        paths.append(p)

    items = client.get("/api/library", params={"sort": "path"}).json()

    assert [Path(item["path"]).name for item in items] == ["Alpha.mp3", "Zulu.mp3"]


def test_library_sort_title_is_case_insensitive_and_stable(client, output_dir):
    for filename, title, artist in [("z.mp3", "beta", "Zulu"), ("a.mp3", "Alpha", "Zulu")]:
        p = output_dir / filename
        p.write_bytes((b"\xff\xfb\x90\x44" + b"\x00" * 413) * 4)
        assert set_tags(p, AudioTags(title=title, artist=artist))

    items = client.get("/api/library", params={"sort": "title"}).json()

    assert [item["title"] for item in items] == ["Alpha", "beta"]


def test_library_sort_job(client, mp3, monkeypatch):
    monkeypatch.setattr(routes.services, "sort_library", lambda out: (1, 2))
    r = client.post("/api/library/sort")
    assert r.status_code == 200
    st = wait_job(client, r.json()["job_id"])
    assert st["result"]["moved"] == 1
    assert st["result"]["removed_dirs"] == 2


def test_library_sort_plan(client, mp3):
    """План раскладки: файл с тегами вне Artist/Album попадает в переносы."""
    from src.tagger import set_tags
    set_tags(mp3, AudioTags(title="Song", artist="Artist", album="Album"))
    r = client.post("/api/library/sort/plan")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert not data["truncated"]
    move = data["moves"][0]
    assert move["from"] == str(mp3)
    assert move["to"] == str(mp3.parent / "Artist" / "Album" / "Song.mp3")
    assert not (mp3.parent / "Artist").exists(), "план ничего не перемещает"


def test_library_sort_plan_empty_when_sorted(client, mp3):
    """Файл уже на своём месте (Inbox не считаем) — план пуст."""
    artist_dir = mp3.parent / "Artist"
    artist_dir.mkdir()
    moved = artist_dir / "Song.mp3"
    mp3.rename(moved)
    from src.tagger import set_tags
    set_tags(moved, AudioTags(title="Song", artist="Artist"))
    data = client.post("/api/library/sort/plan").json()
    assert data["total"] == 0
    assert data["moves"] == []


def test_library_track_delete(client, mp3):
    r = client.delete("/api/library/track", params={"path": str(mp3)})
    assert r.status_code == 200
    assert not mp3.exists()
    r = client.delete("/api/library/track", params={"path": str(mp3)})
    assert r.status_code == 404


def test_dedup_delete(client, mp3, monkeypatch):
    other = mp3.parent / "dup.mp3"
    other.write_bytes(b"\xff\xfb\x90\x44" + b"\x00" * 413 * 4)
    monkeypatch.setattr(routes.services, "dedup_groups", lambda mode, out: [[mp3, other]])
    monkeypatch.setattr(routes.services, "best_in_group", lambda paths, mode: mp3)
    monkeypatch.setattr(routes.services, "dedup_label", lambda p: p.name)

    r = client.post("/api/library/dedup", json={"mode": "md5"})
    assert r.status_code == 200
    groups = r.json()["groups"]
    assert groups[0]["best"] == str(mp3)
    assert len(groups[0]["files"]) == 2

    r = client.post("/api/library/dedup/delete", json={"paths": [str(other)]})
    assert r.status_code == 200
    assert r.json()["deleted"] == 1
    assert not other.exists()


def test_merge(client, mp3, monkeypatch):
    frame = b"\xff\xfb\x90\x44" + b"\x00" * 413
    mp3_2 = mp3.parent / "song2.mp3"
    mp3_2.write_bytes(frame * 8)
    set_tags(mp3_2, AudioTags(title="Song 2", artist="Artist", album="Album"))
    r = client.post("/api/library/merge", json={
        "paths": [str(mp3), str(mp3_2)],
        "album": "Comp", "album_artist": "Various Artists"})
    assert r.status_code == 200
    assert r.json()["merged"] == 2
    tags = client.get("/api/tags", params={"path": str(mp3)}).json()
    assert tags["album"] == "Comp"
    assert tags["album_artist"] == "Various Artists"
    assert tags["track_number"] == "1"


def test_merge_albums_scan_and_apply(client, mp3, monkeypatch):
    frame = b"\xff\xfb\x90\x44" + b"\x00" * 413
    mp3_2 = mp3.parent / "song2.mp3"
    mp3_3 = mp3.parent / "song3.mp3"
    mp3_4 = mp3.parent / "song4.mp3"
    mp3_2.write_bytes(frame * 8)
    mp3_3.write_bytes(frame * 8)
    mp3_4.write_bytes(frame * 8)
    set_tags(mp3, AudioTags(title="Song 1", artist="Artist", album="Album"))
    set_tags(mp3_2, AudioTags(title="Song 2", artist="Artist", album="Album"))
    set_tags(mp3_3, AudioTags(title="Song 3", artist="Artist B", album="Album"))
    set_tags(mp3_4, AudioTags(title="Song 4", artist="Artist", album="Solo"))

    s = client.post("/api/library/merge-albums/scan", json={})
    assert s.status_code == 200
    groups = s.json()["groups"]
    assert len(groups) == 1
    g = groups[0]
    assert g["album"] == "Album"
    assert g["mixed"] is True
    assert {f["artist"] for f in g["files"]} >= {"Artist", "Artist B"} and len(g["files"]) == 3

    a = client.post("/api/library/merge-albums/apply", json={"groups": [{
        "paths": [f["path"] for f in g["files"]],
        "album": "Album", "album_artist": "Various Artists",
    }]})
    assert a.status_code == 200
    assert a.json()["merged"] == 3
    tags = client.get("/api/tags", params={"path": str(mp3_3)}).json()
    assert tags["album_artist"] == "Various Artists"
    assert tags["track_number"] == "3"

    s2 = client.post("/api/library/merge-albums/scan", json={})
    assert s2.json()["groups"] == []


# --- Отчёты ----------------------------------------------------------------


def test_health_lint_normalize_client(client, mp3):
    h = client.get("/api/health").json()
    assert h["total"] == 1
    assert 0 <= h["score"] <= 100
    l = client.get("/api/lint").json()
    assert l["total"] == 1
    n = client.get("/api/normalize/plan").json()
    assert n["count"] == 0


def test_reports_include_inbox(client, mp3, output_dir):
    inbox = output_dir / "Inbox"
    inbox.mkdir()
    p = inbox / "raw.mp3"
    frame = b"\xff\xfb\x90\x44" + b"\x00" * 413
    p.write_bytes(frame * 4)
    assert set_tags(p, AudioTags(title="Raw  Music", artist="  Raw  Artist  ",
                                 album="", year="3000", track_number="abc"))

    base = client.get("/api/lint").json()
    assert base["total"] == 1  # Inbox не учитывается по умолчанию
    with_inbox = client.get("/api/lint", params={"include_inbox": 1}).json()
    assert with_inbox["total"] == 2
    paths = [i["path"] for items in with_inbox["issues"].values() for i in items]
    assert str(p) in paths  # проблемы Inbox-файла видны

    h = client.get("/api/health", params={"include_inbox": 1}).json()
    assert h["total"] == 2
    assert h["counts"].get("missing", 0) >= 2  # artist/album у raw-файла

    n = client.get("/api/normalize/plan", params={"include_inbox": 1}).json()
    assert n["count"] >= 1
    raw = [c for c in n["changes"] if c["path"] == str(p)]
    assert raw and raw[0]["cause"] == "whitespace"


def test_normalize_apply_include_inbox(client, mp3, output_dir, monkeypatch):
    seen = {"flag": False}

    monkeypatch.setattr(routes, "normalize_library",
                        lambda out, include_inbox=False: (seen.__setitem__("flag", include_inbox), None) and None)
    monkeypatch.setattr(routes, "apply_plan", lambda plan, causes=None: (1, 0))
    r = client.post("/api/normalize/apply", json={"include_inbox": True})
    assert r.status_code == 200
    assert r.json() == {"applied": 1, "errors": 0}
    assert seen["flag"] is True


def test_health_fix(client, mp3, monkeypatch):
    monkeypatch.setattr(routes, "fix_issues", lambda out: (1, []))
    r = client.post("/api/health/fix", json={})
    assert r.status_code == 200
    assert r.json() == {"fixed": 1, "errors": []}


def test_normalize_apply_causes(client, mp3, monkeypatch):
    applied = {"applied": 0, "errors": 0}

    def fake_apply(plan, causes=None):
        applied["causes"] = causes
        return (2, 1)

    monkeypatch.setattr(routes, "apply_plan", fake_apply)
    r = client.post("/api/normalize/apply", json={"causes": ["feat", "case"]})
    assert r.status_code == 200
    assert applied["causes"] == ["feat", "case"]
    assert r.json() == {"applied": 2, "errors": 1}

    r = client.post("/api/normalize/apply", json={})
    assert applied["causes"] is None
    assert r.json() == {"applied": 2, "errors": 1}


def test_compress_list(client, mp3):
    r = client.get("/api/compress/list")
    assert r.status_code == 200
    assert r.json()["audio"][0]["path"] == str(mp3)
    assert r.json()["covers"] == 0


def test_compress_list_lossy_target_default(client, mp3):
    # Дефолт m4a+256: mp3-стаб 128k уже ниже порога — сжатие не нужно.
    item = client.get("/api/compress/list").json()["audio"][0]
    assert item["compress"] is False
    assert item["estimate_bytes"] > 0


def test_compress_list_lossless_target(client, mp3):
    client.put("/api/settings", json={"default_format": "flac"})
    item = client.get("/api/compress/list").json()["audio"][0]
    # lossy исходник при lossless-таргете — кандидат; оценка по битрейту невозможна
    assert item["compress"] is True
    assert item["estimate_bytes"] == 0


def test_compress_job_uses_settings(client, mp3, monkeypatch):
    client.put("/api/settings", json={"default_format": "opus", "default_quality": 128})
    seen = {}

    def fake_compress(path, quality, target_format=None):
        seen.update(path=path, quality=quality, format=target_format)
        return path  # not None → done

    monkeypatch.setattr(routes, "compress_file", fake_compress)
    r = client.post("/api/compress", json={"mode": "audio", "paths": [str(mp3)]})
    assert r.status_code == 200
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "done"
    assert st["result"]["done"] == 1
    assert seen == {"path": mp3, "quality": 128, "format": "opus"}


# --- Поиск / скачивание ------------------------------------------------


def test_search(client, monkeypatch):
    class Info:
        id = "x1"; title = "Hit"; uploader = "C"; duration = 100
        thumbnail = "http://thumb/x.jpg"; upload_date = "20240101"
        webpage_url = "https://youtu.be/x1"

    class Result:
        info = Info()
        index = 1

    seen = {}

    class FakeSearch:
        def __init__(self, max_results=10):
            seen["max_results"] = max_results

        def search(self, q):
            return [Result()]

    monkeypatch.setattr(routes, "YouTubeSearch", FakeSearch)
    r = client.get("/api/search", params={"q": "test"})
    assert r.status_code == 200
    assert r.json()[0]["title"] == "Hit"
    assert seen["max_results"] == 10


def test_search_limit(client, monkeypatch):
    seen = {}

    class FakeSearch:
        def __init__(self, max_results=10):
            seen["max_results"] = max_results

        def search(self, q):
            return []

    monkeypatch.setattr(routes, "YouTubeSearch", FakeSearch)
    r = client.get("/api/search", params={"q": "test", "limit": 25})
    assert r.status_code == 200
    assert seen["max_results"] == 25


def test_preview_ok(client, monkeypatch):
    monkeypatch.setattr("src.search.resolve_preview", lambda url: "https://cdn/direct.m4a")
    r = client.get("/api/preview", params={"url": "https://youtu.be/x1"})
    assert r.status_code == 200
    assert r.json() == {"url": "https://cdn/direct.m4a"}


def test_preview_missing(client, monkeypatch):
    monkeypatch.setattr("src.search.resolve_preview",
                        lambda url: (_ for _ in ()).throw(ValueError("нет потока")))
    r = client.get("/api/preview", params={"url": "https://youtu.be/x1"})
    assert r.status_code == 404
    assert "нет потока" in r.json()["detail"]


def test_download_single(client, mp3, monkeypatch):
    class Info:
        id = "v1"; title = "V"; uploader = "U"; duration = 5
        thumbnail = ""; upload_date = ""; webpage_url = "https://youtu.be/v1"

    class Res:
        success = True
        error = ""
        filepath = mp3
        info = Info()

    class FakeDownloader:
        def __init__(self, out):
            pass

        def download(self, url, fmt, quality, progress_callback=None, source=None):
            return Res()

    monkeypatch.setattr(routes, "Downloader", FakeDownloader)
    monkeypatch.setattr(routes, "apply_cover_from_url", lambda *a, **k: None)
    r = client.post("/api/download", json={"url": "https://youtu.be/v1", "move": True})
    assert r.status_code == 200
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "done"
    assert st["result"]["filepath"] == str(mp3)


def test_download_single_passes_source(client, mp3, monkeypatch):
    seen = {}

    class Info:
        id = "v1"; title = "V"; uploader = "U"; duration = 5
        thumbnail = ""; upload_date = ""; webpage_url = "https://youtu.be/v1"

    class Res:
        success = True
        error = ""
        filepath = mp3
        info = Info()

    class FakeDownloader:
        def __init__(self, out):
            pass

        def download(self, url, fmt, quality, progress_callback=None, source=None):
            seen["source"] = source
            return Res()

    asset = client.put("/api/settings", json={"source_format": "opus"})
    assert asset.status_code == 200
    monkeypatch.setattr(routes, "Downloader", FakeDownloader)
    monkeypatch.setattr(routes, "apply_cover_from_url", lambda *a, **k: None)
    r = client.post("/api/download", json={"url": "https://youtu.be/v1"})
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "done"
    assert seen["source"] == "opus"


def test_download_batch_reports_aggregate_progress(client, monkeypatch):
    from types import SimpleNamespace

    progress = SimpleNamespace(status="downloading", total_bytes=100,
                               downloaded_bytes=50)

    class FakeDownloader:
        def __init__(self, out):
            pass

        def download_many(self, urls, fmt, quality, max_workers,
                          progress_callback, source=None):
            progress_callback(urls[0], progress)
            progress_callback(urls[1], progress)
            return [SimpleNamespace(success=False, filepath=None, error="нет")
                    for _ in urls]

    monkeypatch.setattr(routes, "Downloader", FakeDownloader)
    response = client.post("/api/download/batch", json={
        "urls": ["https://youtu.be/one", "https://youtu.be/two"],
    })
    job_id = response.json()["job_id"]
    assert wait_job(client, job_id)["status"] == "done"
    events = [e for e in jobs.get(job_id).events if e["type"] == "progress"]
    assert [e["percent"] for e in events[:2]] == [25.0, 50.0]
    assert events[0]["msg"].startswith("[1/2]")
    assert events[1]["msg"].startswith("[2/2]")


def test_download_batch_counts_finished_worker_before_other_callbacks(client, monkeypatch):
    from types import SimpleNamespace

    downloading = SimpleNamespace(status="downloading", total_bytes=100,
                                  downloaded_bytes=50)
    finished = SimpleNamespace(status="finished", total_bytes=100,
                               downloaded_bytes=100)

    class FakeDownloader:
        def __init__(self, out):
            pass

        def download_many(self, urls, fmt, quality, max_workers,
                          progress_callback, source=None):
            progress_callback(urls[0], downloading)
            progress_callback(urls[0], finished)
            progress_callback(urls[1], downloading)
            return [SimpleNamespace(success=False, filepath=None, error="нет")
                    for _ in urls]

    monkeypatch.setattr(routes, "Downloader", FakeDownloader)
    response = client.post("/api/download/batch", json={
        "urls": ["https://youtu.be/one", "https://youtu.be/two"],
    })
    job_id = response.json()["job_id"]
    assert wait_job(client, job_id)["status"] == "done"
    events = [e for e in jobs.get(job_id).events if e["type"] == "progress"]
    percents = [e["percent"] for e in events]
    assert percents[:3] == [25.0, 50.0, 75.0]
    assert percents[-1] == 100.0
    assert percents == sorted(percents)


def test_ytmusic_download_reports_item_progress_as_batch_progress(client, monkeypatch):
    from types import SimpleNamespace

    progress = SimpleNamespace(status="downloading", total_bytes=100,
                               downloaded_bytes=50)

    class FakeDownloader:
        def __init__(self, out):
            pass

        def download(self, url, fmt, quality, progress_callback=None, source=None):
            progress_callback(progress)
            return SimpleNamespace(success=False, filepath=None, error="нет")

    monkeypatch.setattr(routes, "Downloader", FakeDownloader)
    response = client.post("/api/ytmusic/download", json={
        "items": [
            {"video_id": "v1", "title": "One", "artist": "A"},
            {"video_id": "v2", "title": "Two", "artist": "B"},
        ],
    })
    job_id = response.json()["job_id"]
    assert wait_job(client, job_id)["status"] == "done"
    events = [e for e in jobs.get(job_id).events if e["type"] == "progress"]
    assert [e["percent"] for e in events if "MB" in e["msg"]] == [25.0, 75.0]


def test_fetch_apply(client, mp3, monkeypatch):
    def boom(*a, **k):
        raise OSError("сеть недоступна")

    monkeypatch.setattr("src.fetcher.download_cover", boom)
    monkeypatch.setattr("src.tagger.apply_cover_from_url", boom)
    r = client.post("/api/fetch/apply", json={
        "path": str(mp3), "fields": {"title": "New", "artist": "X"},
        "source": "itunes", "cover_url": "http://cover.jpg", "thumbnail_url": "",
    })
    assert r.status_code == 200
    tags = r.json()
    assert tags["title"] == "New"
    assert tags["artist"] == "X"


def test_tags_apply_fields_and_comment(client, mp3):
    r = client.post("/api/tags/apply", json={
        "path": str(mp3),
        "fields": {"title": "T2", "comment": "привет", "publisher": "LabelX"},
    })
    assert r.status_code == 200
    tags = r.json()
    assert tags["title"] == "T2"
    assert tags["comment"] == "привет"
    assert tags["publisher"] == "LabelX"
    # пустое поле очищает тег (replace-семантика)
    r = client.post("/api/tags/apply", json={"path": str(mp3), "fields": {"artist": ""}})
    assert r.status_code == 200
    assert r.json()["artist"] == ""


def test_tags_apply_cover_disabled(client, mp3, monkeypatch):
    calls = []

    def fake_cover(url):
        calls.append(url)
        return b"img", "image/png"

    monkeypatch.setattr("src.fetcher.download_cover", fake_cover)
    r = client.post("/api/tags/apply", json={
        "path": str(mp3), "fields": {"title": "No cover"},
        "cover_url": "http://cover.jpg", "apply_cover": False,
    })
    assert r.status_code == 200
    assert calls == []
    assert r.json()["has_cover"] is False


def test_tags_apply_cover_enabled(client, mp3, monkeypatch):
    monkeypatch.setattr("src.fetcher.download_cover", lambda url: (b"img", "image/png"))
    r = client.post("/api/tags/apply", json={
        "path": str(mp3), "fields": {"title": "With cover"},
        "cover_url": "http://cover.jpg", "apply_cover": True,
    })
    assert r.status_code == 200
    assert r.json()["has_cover"] is True
    assert r.json()["cover_mime"] == "image/png"


def test_tags_apply_uploaded_cover(client, mp3):
    """Загруженная картинка записывается как обложка без обращения к сети."""
    r = client.post("/api/tags/apply", json={
        "path": str(mp3), "fields": {},
        "cover_data": "iVBORw0KGgo=", "cover_mime": "image/png",
    })
    assert r.status_code == 200
    assert r.json()["has_cover"] is True
    assert r.json()["cover_mime"] == "image/png"
    assert client.get("/api/cover", params={"path": str(mp3)}).content == b"\x89PNG\r\n\x1a\n"


def test_tags_apply_cover_from_other_track(client, mp3, output_dir, monkeypatch):
    """«Обложка для альбома»: байты берутся из другого трека, без сети."""
    def boom(*a, **k):
        raise OSError("сеть недоступна")

    monkeypatch.setattr("src.fetcher.download_cover", boom)
    other = output_dir / "with_cover.mp3"
    other.write_bytes(mp3.read_bytes())
    assert set_tags(other, AudioTags(title="WithCover",
                                     cover_data=b"JPEGDATA", cover_mime="image/jpeg"))
    r = client.post("/api/tags/apply", json={
        "path": str(mp3), "fields": {},
        "cover_from": str(other), "apply_cover": True,
    })
    assert r.status_code == 200
    tags = r.json()
    assert tags["has_cover"] is True
    assert tags["cover_mime"] == "image/jpeg"
    assert tags["title"] == "Song", "теги не трогаются"
    assert client.get("/api/cover", params={"path": str(mp3)}).content == b"JPEGDATA"


def test_tags_apply_cover_from_missing_file_keeps_current(client, mp3, output_dir):
    r = client.post("/api/tags/apply", json={
        "path": str(mp3), "fields": {},
        "cover_from": str(output_dir / "nope.mp3"), "apply_cover": True,
    })
    assert r.status_code == 200
    assert r.json()["has_cover"] is False


def test_tags_apply_validation_errors(client, mp3):
    r = client.post("/api/tags/apply", json={
        "path": str(mp3), "fields": {"year": "abcd", "track_number": "x"},
    })
    assert r.status_code == 400
    body = r.json()
    assert "errors" in body
    assert "year" in body["errors"]
    assert "track_number" in body["errors"]
    # файл не изменён
    tags = client.get("/api/tags", params={"path": str(mp3)}).json()
    assert tags["year"] == "2020"


# --- Meta (fetch/meta + кэш) --------------------------------------------------


def test_fetch_meta_caches_by_title_artist(client, mp3, output_dir, monkeypatch):
    from src.providers import ProviderRecord

    calls = []

    def fake_fetch_all(title, artist, sources=None):
        calls.append((title, artist))
        return {"iTunes": [ProviderRecord(source="iTunes", title=title,
                                          artist=artist, album="Album")]}

    monkeypatch.setattr(routes, "fetch_all", fake_fetch_all)
    r1 = client.post("/api/fetch/meta", json={"path": str(mp3)})
    assert r1.status_code == 200
    assert r1.json()["records"][0]["title"] == "Song"
    assert r1.json()["query"] == "Song"
    # тот же файл — сеть не дёргается
    client.post("/api/fetch/meta", json={"path": str(mp3)})
    # другой файл с теми же тегами — тоже из кэша
    p2 = output_dir / "copy.mp3"
    frame = b"\xff\xfb\x90\x44" + b"\x00" * 413
    p2.write_bytes(frame * 4)
    set_tags(p2, AudioTags(title="Song", artist="Artist"))
    r2 = client.post("/api/fetch/meta", json={"path": str(p2)})
    assert r2.status_code == 200
    assert r2.json()["records"][0]["title"] == "Song"
    assert len(calls) == 1
    # изменили теги → новый ключ → запрос к источникам
    set_tags(mp3, AudioTags(title="Other Song", artist="Artist"))
    r3 = client.post("/api/fetch/meta", json={"path": str(mp3)})
    assert r3.status_code == 200
    assert r3.json()["records"][0]["title"] == "Other Song"
    assert len(calls) == 2


def test_fetch_meta_no_title_skips_sources(client, output_dir, monkeypatch):
    from src.providers import ProviderRecord

    calls = []

    def fake_fetch_all(title, artist, sources=None):
        calls.append(title)
        return {"iTunes": [ProviderRecord(source="iTunes", title=title)]}

    monkeypatch.setattr(routes, "fetch_all", fake_fetch_all)
    p = output_dir / "untitled.mp3"
    frame = b"\xff\xfb\x90\x44" + b"\x00" * 413
    p.write_bytes(frame * 4)
    set_tags(p, AudioTags(title="", artist="Artist"))
    r = client.post("/api/fetch/meta", json={"path": str(p)})
    assert r.status_code == 200
    assert r.json()["records"] == []
    assert calls == []


def test_fetch_meta_sources_filter_and_per_source_cache(client, mp3, monkeypatch):
    """Фильтр sources: каждый источник качается один раз, порядок — как в запросе."""
    from src.providers import ProviderRecord

    calls = []

    def fake_fetch_all(title, artist, sources=None):
        calls.append(list(sources or []))
        return {s: [ProviderRecord(source=s, title=title)] for s in (sources or [])}

    monkeypatch.setattr(routes, "fetch_all", fake_fetch_all)
    routes.meta_cache_clear()
    r1 = client.post("/api/fetch/meta", json={"path": str(mp3), "sources": ["iTunes"]})
    assert r1.status_code == 200
    assert [rec["source"] for rec in r1.json()["records"]] == ["iTunes"]
    assert calls == [["iTunes"]]
    # второй источник + уже закэшированный — сеть только для нового
    r2 = client.post("/api/fetch/meta",
                     json={"path": str(mp3), "sources": ["Deezer", "iTunes"]})
    assert [rec["source"] for rec in r2.json()["records"]] == ["Deezer", "iTunes"]
    assert calls == [["iTunes"], ["Deezer"]]
    # всё в кэше — сеть не дёргается
    client.post("/api/fetch/meta",
                json={"path": str(mp3), "sources": ["iTunes", "Deezer"]})
    assert calls == [["iTunes"], ["Deezer"]]
    # неизвестные источники отфильтровываются
    r3 = client.post("/api/fetch/meta", json={"path": str(mp3), "sources": ["Nope"]})
    assert r3.json()["records"] == []
    assert len(calls) == 2
    # sources не список — 400
    r4 = client.post("/api/fetch/meta", json={"path": str(mp3), "sources": "iTunes"})
    assert r4.status_code == 400


def test_fetch_meta_caches_empty_result(client, mp3, monkeypatch):
    """Пустой ответ источника кэшируется — повторный запрос не бьёт по сети."""
    calls = []

    def fake_fetch_all(title, artist, sources=None):
        calls.append(list(sources or []))
        return {s: [] for s in (sources or [])}

    monkeypatch.setattr(routes, "fetch_all", fake_fetch_all)
    routes.meta_cache_clear()
    r1 = client.post("/api/fetch/meta", json={"path": str(mp3), "sources": ["iTunes"]})
    assert r1.json()["records"] == []
    r2 = client.post("/api/fetch/meta", json={"path": str(mp3), "sources": ["iTunes"]})
    assert r2.json()["records"] == []
    assert len(calls) == 1


# --- Shazam -----------------------------------------------------------------


def test_shazam_scan_without_file(client, monkeypatch):
    monkeypatch.setattr(routes, "get_shazam_file", lambda: None)
    r = client.post("/api/shazam/scan", json={})
    assert r.status_code == 200
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "error"
    assert st["error"]["code"] == "jobs.shazam.file_missing"


def test_shazam_scan_matches_via_ytmusic(client, monkeypatch, tmp_path):
    """Матчинг идёт через search_songs YT Music: video_id/обложка/альбом в выдаче."""
    import src.ytmusic as ytm

    p = tmp_path / "shazam.txt"
    p.write_text("Song - Artist\n", encoding="utf-8")
    monkeypatch.setattr(routes, "get_shazam_file", lambda: p)
    monkeypatch.setattr(
        ytm, "search_songs",
        lambda query, limit=10: [ytm.YTMTrack(
            video_id="yt1", title="Song", artist="Artist",
            album="Alb", cover_url="cov")])
    r = client.post("/api/shazam/scan", json={})
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "done"
    found = st["result"]["entries"][0]["found"]
    assert found and found[0]["video_id"] == "yt1"
    assert found[0]["cover_url"] == "cov"
    assert found[0]["album"] == "Alb"
    assert found[0]["url"] == "https://www.youtube.com/watch?v=yt1"
    progress = [event for event in jobs.get(r.json()["job_id"]).events if event["type"] == "progress"]
    assert progress[0]["message"]["code"] == "jobs.shazam.scanning"
    assert progress[0]["msg"] == "Searching for 1 tracks in YouTube Music…"


def test_shazam_scan_falls_back_to_youtube(client, monkeypatch, tmp_path):
    """Ошибка YT Music → обычный поиск yt-dlp, как раньше."""
    import src.ytmusic as ytm

    class Info:
        id = "x1"; title = "Song"; uploader = "C"; duration = 100
        thumbnail = "http://thumb/x.jpg"
        webpage_url = "https://youtu.be/x1"

    class Result:
        info = Info()
        index = 1

    class FakeSearch:
        def __init__(self, max_results=10):
            pass

        def search(self, q):
            return [Result()]

    p = tmp_path / "shazam.txt"
    p.write_text("Song - Artist\n", encoding="utf-8")
    monkeypatch.setattr(routes, "get_shazam_file", lambda: p)

    def boom(query, limit=10):
        raise RuntimeError("YT Music недоступен")

    monkeypatch.setattr(ytm, "search_songs", boom)
    monkeypatch.setattr(routes, "YouTubeSearch", FakeSearch)
    r = client.post("/api/shazam/scan", json={})
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "done"
    found = st["result"]["entries"][0]["found"]
    assert found and found[0]["id"] == "x1"
    assert found[0]["video_id"] == ""
    assert found[0]["cover_url"] == "http://thumb/x.jpg"


def test_shazam_download_reports_aggregate_progress(client, monkeypatch, tmp_path):
    from types import SimpleNamespace

    p = tmp_path / "shazam.txt"
    p.write_text("One - Artist\nTwo - Artist\n", encoding="utf-8")
    monkeypatch.setattr(routes, "get_shazam_file", lambda: p)
    found = [
        SimpleNamespace(info=SimpleNamespace(
            webpage_url="https://youtu.be/one", id="one")),
        SimpleNamespace(info=SimpleNamespace(
            webpage_url="https://youtu.be/two", id="two")),
    ]
    monkeypatch.setattr(
        routes, "find_youtube_matches",
        lambda entries, search: [(entry, [found[entry.index - 1]]) for entry in entries],
    )

    progress = SimpleNamespace(status="downloading", total_bytes=100,
                               downloaded_bytes=50)

    class FakeDownloader:
        def __init__(self, out):
            pass

        def download_many(self, urls, fmt, quality, max_workers,
                          progress_callback, source=None):
            for url in urls:
                progress_callback(url, progress)
            return [SimpleNamespace(success=False, filepath=None, error="нет")
                    for _ in urls]

    monkeypatch.setattr(routes, "Downloader", FakeDownloader)
    response = client.post("/api/shazam/download", json={
        "selection": {"1": 0, "2": 0},
    })
    job_id = response.json()["job_id"]
    assert wait_job(client, job_id)["status"] == "done"
    events = [e for e in jobs.get(job_id).events if e["type"] == "progress"]
    assert [e["percent"] for e in events[:2]] == [25.0, 50.0]


def test_shazam_remove(client, monkeypatch, tmp_path):
    p = tmp_path / "shazam.txt"
    p.write_text("Title - Artist\n# comment\n\nAnother - Band\n", encoding="utf-8")
    monkeypatch.setattr(routes, "get_shazam_file", lambda: p)
    r = client.post("/api/shazam/remove", json={"line_number": 1})
    assert r.status_code == 200
    assert r.json()["removed"] == 1
    assert "Title - Artist" not in p.read_text(encoding="utf-8")
    assert "Another - Band" in p.read_text(encoding="utf-8")


def test_shazam_remove_bad_line(client):
    r = client.post("/api/shazam/remove", json={"line_number": 0})
    assert r.status_code == 400


def test_fs_browse(client, mp3):
    r = client.get("/api/fs/browse", params={"dir": str(mp3.parent)})
    assert r.status_code == 200
    assert r.json()["path"] == str(mp3.parent)


def test_fs_pick_returns_path(client, monkeypatch):
    import src.native_picker as np

    called = {}
    monkeypatch.setattr(np, "pick_path",
                        lambda kind, start=None: called.update(
                            kind=kind, start=start) or "/Users/x/Music")
    out = client.post("/api/fs/pick", json={"kind": "folder", "start": "/Users/x"})
    assert out.status_code == 200
    assert out.json()["path"] == "/Users/x/Music"
    assert called["kind"] == "folder"
    assert called["start"] == "/Users/x"


def test_fs_pick_cancel_and_invalid(client, monkeypatch):
    import src.native_picker as np

    monkeypatch.setattr(np, "pick_path", lambda kind, start=None: None)
    r = client.post("/api/fs/pick", json={"kind": "folder"})
    assert r.status_code == 200
    assert r.json()["path"] is None
    assert client.post("/api/fs/pick", json={"kind": "nope"}).status_code == 400
    assert client.post("/api/fs/pick", json={"kind": "file"}).status_code == 200


def test_fs_pick_file_defaults_to_parent_dir(client, monkeypatch):
    import src.native_picker as np

    got = {}
    monkeypatch.setattr(np, "_macos_pick",
                        lambda kind, start: got.update(kind=kind, start=start) or "/picked")
    r = client.post("/api/fs/pick", json={"kind": "file", "start": "/a/b/track.mp3"})
    assert r.status_code == 200
    assert r.json()["path"] == "/picked"
    assert got["start"] == "/a/b"


def test_native_picker_default_location(tmp_path):
    from src.native_picker import default_location

    assert default_location("file", "/a/b/track.mp3") == "/a/b"
    assert default_location("file", None) is None
    assert default_location("folder", str(tmp_path)) == str(tmp_path)


# --- Рекомендации по библиотеке ---------------------------------------------


def _save_config(**kw):
    from src.config import load_config, save_config

    cfg = load_config()
    cfg.update(kw)
    save_config(cfg)


def _stub_ytm_network(monkeypatch):
    """Радио YouTube Music — без сети (авторизован + стаб поиска/радио)."""
    import src.ytmusic as ytm
    monkeypatch.setattr(ytm, "connected", lambda: True)
    monkeypatch.setattr(
        ytm, "search_songs",
        lambda query, limit=10: [ytm.YTMTrack(video_id="seed-vid",
                                              title="Song", artist="Artist")])
    monkeypatch.setattr(
        ytm, "watch_playlist",
        lambda video_id, limit=25: [ytm.YTMTrack(video_id="cand-vid",
                                                 title="Cand-Song",
                                                 artist="Other-Artist",
                                                 album="Alb",
                                                 cover_url="cov")])


def _no_ytm_feedback(monkeypatch):
    calls = {"LIKE": 0, "DISLIKE": 0}

    def fake(artist, title, rating=None):
        if rating is None:
            from src.config import get_feedback_action

            rating = "LIKE" if get_feedback_action() == "like" else "library"
        calls[rating] = calls.get(rating, 0) + 1

    monkeypatch.setattr(routes, "_ytm_feedback", fake)
    return calls


def test_recommend_generate(client, mp3, monkeypatch):
    _stub_ytm_network(monkeypatch)

    r = client.post("/api/recommend/generate")
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "done"
    assert st["result"]["library_count"] == 1
    assert st["result"]["seeds"] == 1
    assert len(st["result"]["items"]) == 1
    item = st["result"]["items"][0]
    assert item["artist"] == "Other-Artist"
    assert item["title"] == "Cand-Song"
    assert item["url"] == "https://www.youtube.com/watch?v=cand-vid"
    assert item["cover_url"] == "cov"
    assert "video_id" in item
    assert not any("status" in i for i in st["result"]["items"])


@pytest.mark.parametrize(
    ("last_error", "expected_detail"),
    [
        ("", {
            "code": "api.errors.empty_playlist",
            "params": {},
            "message": "Playlist is empty",
        }),
        ("provider unavailable", "Плейлист пуст (provider unavailable)"),
    ],
)
def test_playlist_empty_response_keeps_provider_reason_or_uses_owned_descriptor(
    client, monkeypatch, last_error, expected_detail,
):
    """Empty extraction must not discard a provider reason or invent one."""

    class EmptyPlaylistSearch:
        def __init__(self):
            self.last_error = last_error

        def fetch_playlist(self, url):
            return []

    monkeypatch.setattr(routes, "YouTubeSearch", EmptyPlaylistSearch)

    response = client.get("/api/playlist", params={"url": "https://example.test/list"})

    assert response.status_code == 404
    assert response.json()["detail"] == expected_detail


def test_recommend_generate_requires_ytmusic(client, mp3, monkeypatch):
    r = client.post("/api/recommend/generate")
    assert r.status_code == 400
    assert r.json()["detail"] == {
        "code": "api.errors.ytm_connection_required",
        "params": {},
        "message": "Connect YouTube Music (Settings → YouTube Music)",
    }


def test_recommend_generate_calls_radio_each_run(client, mp3, monkeypatch):
    """Каждый прогон заново лезет в радио YouTube Music (нет кэша)."""
    calls = {"search": 0, "radio": 0}
    import src.ytmusic as ytm

    def search(query, limit=10):
        calls["search"] += 1
        return [ytm.YTMTrack(video_id="v", title="Song", artist="Artist")]

    def radio(video_id, limit=25):
        calls["radio"] += 1
        return [ytm.YTMTrack(video_id="c", title="C", artist="Other")]

    monkeypatch.setattr(ytm, "connected", lambda: True)
    monkeypatch.setattr(ytm, "search_songs", search)
    monkeypatch.setattr(ytm, "watch_playlist", radio)

    wait_job(client, client.post("/api/recommend/generate").json()["job_id"])
    st2 = wait_job(client, client.post("/api/recommend/generate").json()["job_id"])
    assert st2["result"]["library_count"] == 1
    assert calls["search"] == 2
    assert calls["radio"] == 2


def test_recommend_generate_empty_library(client, monkeypatch):
    _stub_ytm_network(monkeypatch)
    r = client.post("/api/recommend/generate")
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "done"
    assert st["result"] == {"items": [], "seeds": 0, "library_count": 0, "total": 0}


def _rec_library_track(output_dir: Path, name: str, artist: str, title: str) -> None:
    """Mp3-стаб с заданными тегами — для библиотеки из нескольких сидов."""
    frame = b"\xff\xfb\x90\x44" + b"\x00" * 413
    p = output_dir / f"{name}.mp3"
    p.write_bytes(frame * 4)
    assert set_tags(p, AudioTags(title=title, artist=artist, album="Album", year="2020"))


def _rec_events(job_id: str) -> list[dict]:
    """Progress-события задачи с kind=recommendations (snapshot-ы сидов)."""
    return [e for e in jobs.get(job_id).events
            if e.get("type") == "progress" and e.get("kind") == "recommendations"]


#: Строгий shape snapshot-события: type/msg/kind + ровно семь полей snapshot-а
#: (никаких лишних ключей — например, percent — быть не должно).
_REC_SNAPSHOT_EVENT_KEYS = {
    "type", "msg", "kind",
    "seed_index", "seed_count", "seed", "items", "seeds",
    "library_count", "total",
}


def test_recommend_generate_streams_snapshots(client, output_dir, monkeypatch):
    """Каждый обработанный сид публикуется событием kind=recommendations."""
    import src.ytmusic as ytm

    _rec_library_track(output_dir, "a", "A1", "T1")
    _rec_library_track(output_dir, "b", "A2", "T2")

    def search(query, limit=10):
        return [ytm.YTMTrack(video_id=f"vid-{query}", title=query, artist=query)]

    def radio(video_id, limit=25):
        tag = video_id.removeprefix("vid-")
        return [ytm.YTMTrack(video_id=f"cand-{tag}", title=f"C-{tag}",
                             artist=f"Other-{tag}", cover_url="cov")]

    monkeypatch.setattr(ytm, "connected", lambda: True)
    monkeypatch.setattr(ytm, "search_songs", search)
    monkeypatch.setattr(ytm, "watch_playlist", radio)

    r = client.post("/api/recommend/generate")
    job_id = r.json()["job_id"]
    st = wait_job(client, job_id)
    assert st["status"] == "done"

    evs = _rec_events(job_id)
    assert len(evs) == 2, "по одному snapshot на каждого сида"
    first, second = evs
    for ev in evs:
        # строгий shape: type=progress, msg, kind + все семь полей snapshot-а
        assert set(ev) == _REC_SNAPSHOT_EVENT_KEYS | {"message"}
        assert ev["type"] == "progress"
        assert ev["kind"] == "recommendations"
        assert isinstance(ev["msg"], str) and ev["msg"]
    assert first["msg"] == "Processed seed 1 of 2"
    assert second["msg"] == "Processed seed 2 of 2"
    assert first["seed_index"] == 1
    assert second["seed_index"] == 2
    for ev in evs:
        assert ev["seed_count"] == 2
        assert ev["seeds"] == 2
        assert ev["library_count"] == 2
        assert ev["total"] == len(ev["items"])
        assert ev["seed"] in {"A1 — T1", "A2 — T2"}
    assert first["seed"] != second["seed"], "сид-подписи различаются"
    # накопительный items: первый кандидат не меняется, второй добавляется в хвост
    assert len(first["items"]) == 1
    assert len(second["items"]) == 2
    assert second["items"][0] == first["items"][0]
    # обычный progress (сканирование) доставляется как прежде, без kind
    assert any(e.get("type") == "progress" and "kind" not in e
               for e in jobs.get(job_id).events)
    # итоговый DTO — строго четыре прежних ключа, items == последнему snapshot
    assert set(st["result"]) == {"items", "seeds", "library_count", "total"}
    assert st["result"]["items"] == second["items"]
    assert st["result"]["seeds"] == 2
    assert st["result"]["library_count"] == 2
    assert st["result"]["total"] == 2


def test_recommend_generate_snapshot_on_radio_error_and_empty(client, output_dir, monkeypatch):
    """Сбой радио одного сида и пустой ответ другого дают snapshot и не ломают job."""
    import src.ytmusic as ytm

    _rec_library_track(output_dir, "a", "A1", "T1")
    _rec_library_track(output_dir, "b", "A2", "T2")

    def search(query, limit=10):
        return [ytm.YTMTrack(video_id=f"vid-{query}", title=query, artist=query)]

    def radio(video_id, limit=25):
        if "A1" in video_id:
            raise RuntimeError("radio down")
        return []

    monkeypatch.setattr(ytm, "connected", lambda: True)
    monkeypatch.setattr(ytm, "search_songs", search)
    monkeypatch.setattr(ytm, "watch_playlist", radio)

    r = client.post("/api/recommend/generate")
    job_id = r.json()["job_id"]
    st = wait_job(client, job_id)
    assert st["status"] == "done"

    evs = _rec_events(job_id)
    assert len(evs) == 2, "и сбой, и пустой ответ завершают сид snapshot-ом"
    for ev in evs:
        # строгий shape действует и для snapshot-ов сбоя/пустого радио
        assert set(ev) == _REC_SNAPSHOT_EVENT_KEYS | {"message"}
        assert ev["type"] == "progress"
        assert ev["kind"] == "recommendations"
        assert ev["items"] == []
        assert ev["total"] == 0
        assert ev["seed_index"] in (1, 2)
        assert ev["seed_count"] == 2
    assert st["result"] == {"items": [], "seeds": 2, "library_count": 2, "total": 0}


def test_recommend_generate_empty_library_no_snapshot_events(client, monkeypatch):
    """Пустая библиотека (ноль сидов) не публикует recommendation-событий."""
    _stub_ytm_network(monkeypatch)
    r = client.post("/api/recommend/generate")
    job_id = r.json()["job_id"]
    st = wait_job(client, job_id)
    assert st["status"] == "done"
    assert st["result"] == {"items": [], "seeds": 0, "library_count": 0, "total": 0}
    assert _rec_events(job_id) == []


def test_recommend_apply_sends_like(client, mp3, monkeypatch):
    _stub_ytm_network(monkeypatch)
    feedback = _no_ytm_feedback(monkeypatch)

    st = wait_job(client, client.post("/api/recommend/generate").json()["job_id"])
    item = st["result"]["items"][0]

    r = client.post("/api/recommend/apply",
                    json={"artist": item["artist"], "title": item["title"]})
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert feedback["LIKE"] == 1, "лайк должен уйти в YT Music"
    assert feedback["DISLIKE"] == 0


def test_recommend_apply_library_mode_saves(monkeypatch):
    """Настройка library: apply сохраняет трек в библиотеку YT, не лайкает."""
    from src.config import FEEDBACK_ACTION_KEY

    _save_config(**{FEEDBACK_ACTION_KEY: "library"})
    feedback = _no_ytm_feedback(monkeypatch)

    r = routes.api_recommend_apply({"artist": "A", "title": "B"})
    assert r == {"status": "ok"}
    assert feedback["library"] == 1
    assert feedback["LIKE"] == 0


def test_recommend_apply_requires_artist_title(client, mp3, monkeypatch):
    r = client.post("/api/recommend/apply", json={})
    assert r.status_code == 400
    assert r.json()["detail"] == {
        "code": "api.errors.artist_title_required",
        "params": {},
        "message": "artist and title are required",
    }


def test_recommend_dislike_sends_dislike(client, mp3, monkeypatch):
    _stub_ytm_network(monkeypatch)
    feedback = _no_ytm_feedback(monkeypatch)

    st = wait_job(client, client.post("/api/recommend/generate").json()["job_id"])
    item = st["result"]["items"][0]

    r = client.post("/api/recommend/dislike",
                    json={"artist": item["artist"], "title": item["title"]})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert feedback["DISLIKE"] == 1
    assert feedback["LIKE"] == 0


# --- YouTube Music ---------------------------------------------------------


def _ytm_auth_file() -> Path:
    import src.config as config
    return config.CONFIG_DIR / "ytmusic_auth.json"


def test_ytmusic_status_disconnected(client):
    data = client.get("/api/ytmusic/status").json()
    assert data["connected"] is False
    assert data["mode"] == ""
    assert data["account"] is None
    assert data["account_error"] == ""


def test_ytmusic_status_connected(client, monkeypatch):
    import src.ytmusic as ytm
    monkeypatch.setattr(ytm, "connected", lambda: True)
    monkeypatch.setattr(ytm, "auth_mode", lambda: "browser")
    monkeypatch.setattr(ytm, "account_info",
                        lambda: {"name": "Тест", "email": "a@b.c"})
    data = client.get("/api/ytmusic/status").json()
    assert data["connected"] is True
    assert data["mode"] == "browser"
    assert data["account"]["name"] == "Тест"
    assert data["account_error"] == ""


def test_ytmusic_status_account_error(client, monkeypatch):
    import src.ytmusic as ytm
    monkeypatch.setattr(ytm, "connected", lambda: True)
    monkeypatch.setattr(ytm, "auth_mode", lambda: "browser")
    monkeypatch.setattr(ytm, "account_info", lambda: (_ for _ in ()).throw(
        ytm.YTMusicError("токен протух")))
    data = client.get("/api/ytmusic/status").json()
    assert data["connected"] is True
    assert "токен протух" in data["account_error"]


def test_ytmusic_settings_defaults(client):
    data = client.get("/api/settings").json()
    assert data["ytmusic_connected"] is False
    assert data["ytmusic_mode"] == ""
    assert data["ytmusic_auth_file"].endswith("ytmusic_auth.json")


def test_ytmusic_browser_bad_headers(client):
    r = client.post("/api/ytmusic/auth/browser", json={"headers_raw": "foo"})
    assert r.status_code == 400
    assert "заголовк" in r.json()["detail"]


def test_ytmusic_browser_auth_writes(client, monkeypatch):
    import src.ytmusic as ytm
    called = {}

    def fake_write(text):
        called["text"] = text
        _ytm_auth_file().parent.mkdir(parents=True, exist_ok=True)
        _ytm_auth_file().write_text(
            '{"cookie": "c", "x-goog-authuser": "0"}', encoding="utf-8")

    monkeypatch.setattr(ytm, "write_browser_auth", fake_write)
    headers = "Cookie: c\nX-Goog-AuthUser: 0\n"
    r = client.post("/api/ytmusic/auth/browser", json={"headers_raw": headers})
    assert r.status_code == 200
    assert called["text"] == headers
    assert _ytm_auth_file().is_file()


def test_ytmusic_delete_auth(client, monkeypatch):
    import src.ytmusic as ytm
    path = _ytm_auth_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"cookie": "c"}', encoding="utf-8")
    monkeypatch.setattr(ytm, "get_auth_file", lambda: path)
    r = client.delete("/api/ytmusic/auth")
    assert r.status_code == 200
    assert not path.exists()


def test_ytmusic_auth_browsers(client, monkeypatch):
    import src.ytmusic as ytm
    monkeypatch.setattr(ytm, "available_browsers", lambda: [
        {"name": "chrome", "profiles": ["Default", "Profile 1"]},
    ])
    data = client.get("/api/ytmusic/auth/browsers").json()
    assert data["browsers"][0]["name"] == "chrome"
    assert data["browsers"][0]["profiles"] == ["Default", "Profile 1"]


def test_ytmusic_browser_extract_job(client, monkeypatch):
    import src.ytmusic as ytm

    def fake_extract(browser, profile=None, authuser=None, page_id=None, client_factory=None):
        _ytm_auth_file().parent.mkdir(parents=True, exist_ok=True)
        _ytm_auth_file().write_text(
            '{"cookie": "c", "x-goog-authuser": "1"}', encoding="utf-8")
        assert browser == "chrome" and profile == "Default"
        return {"account": {"name": "lnlydrvr"}, "authuser": 1,
                "browser": "chrome", "profile": "Default", "likes": 0,
                "page_id": None}

    monkeypatch.setattr(ytm, "extract_browser_headers", fake_extract)
    monkeypatch.setattr(ytm, "account_info",
                        lambda: {"name": "lnlydrvr", "handle": "@lnlydrvr"})
    r = client.post("/api/ytmusic/auth/browser/extract",
                    json={"browser": "chrome", "profile": "Default"})
    assert r.status_code == 200
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "done"
    res = st["result"]
    assert res["ok"] is True
    assert res["account"]["name"] == "lnlydrvr"
    assert res["authuser"] == 1
    assert _ytm_auth_file().is_file()


def test_ytmusic_browser_extract_job_error(client, monkeypatch):
    import src.ytmusic as ytm

    def fake_extract(browser, profile=None, authuser=None, page_id=None, client_factory=None):
        raise ytm.YTMusicError("Keychain: Chrome Safe Storage")

    monkeypatch.setattr(ytm, "extract_browser_headers", fake_extract)
    r = client.post("/api/ytmusic/auth/browser/extract", json={"browser": "chrome"})
    assert r.status_code == 200
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "error"
    assert "Keychain" in st["error"]


def test_ytmusic_browser_extract_requires_browser(client):
    r = client.post("/api/ytmusic/auth/browser/extract", json={})
    assert r.status_code == 400
    assert r.json()["detail"] == {
        "code": "api.errors.browser_required", "params": {}, "message": "Select a browser",
    }


def test_ytmusic_browser_extract_with_authuser(client, monkeypatch):
    import src.ytmusic as ytm

    calls = {}

    def fake_extract(browser, profile=None, authuser=None, page_id=None, client_factory=None):
        calls["authuser"] = authuser
        calls["page_id"] = page_id
        _ytm_auth_file().parent.mkdir(parents=True, exist_ok=True)
        _ytm_auth_file().write_text(
            '{"cookie": "c", "x-goog-authuser": "1"}', encoding="utf-8")
        return {"account": {"name": "roman"}, "authuser": 1,
                "browser": browser, "profile": None, "likes": 4,
                "page_id": page_id}

    monkeypatch.setattr(ytm, "extract_browser_headers", fake_extract)
    monkeypatch.setattr(ytm, "account_info", lambda: {"name": "roman"})
    r = client.post("/api/ytmusic/auth/browser/extract",
                    json={"browser": "chrome", "authuser": 1})
    assert r.status_code == 200
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "done"
    assert calls["authuser"] == 1
    assert st["result"]["authuser"] == 1


def test_ytmusic_browser_extract_with_page_id(client, monkeypatch):
    import src.ytmusic as ytm

    calls = {}

    def fake_extract(browser, profile=None, authuser=None, page_id=None,
                     client_factory=None):
        calls["page_id"] = page_id
        _ytm_auth_file().parent.mkdir(parents=True, exist_ok=True)
        _ytm_auth_file().write_text(
            '{"cookie": "c", "x-goog-authuser": "0"}', encoding="utf-8")
        return {"account": {"name": "lnlydrvr"}, "authuser": 0,
                "browser": browser, "profile": None, "likes": 77,
                "page_id": page_id}

    monkeypatch.setattr(ytm, "extract_browser_headers", fake_extract)
    monkeypatch.setattr(ytm, "account_info", lambda: {"name": "lnlydrvr"})
    r = client.post("/api/ytmusic/auth/browser/extract",
                    json={"browser": "zen", "page_id": "103430112380821682108"})
    assert r.status_code == 200
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "done"
    assert calls["page_id"] == "103430112380821682108"
    assert st["result"]["page_id"] == "103430112380821682108"


def test_ytmusic_browser_extract_bad_authuser(client):
    r = client.post("/api/ytmusic/auth/browser/extract",
                    json={"browser": "chrome", "authuser": "не число"})
    assert r.status_code == 400
    assert r.json()["detail"] == {
        "code": "api.errors.invalid_authuser", "params": {}, "message": "Invalid authuser",
    }


def test_ytmusic_browser_accounts_job(client, monkeypatch):
    import src.ytmusic as ytm

    monkeypatch.setattr(ytm, "browser_accounts", lambda browser, profile=None: [
        {"authuser": 1, "account": {"name": "lnlydrvr", "handle": "@lnlydrvr"},
         "likes": 77},
        {"authuser": 0, "account": {"name": "roman"}, "likes": 4},
    ])
    r = client.post("/api/ytmusic/auth/browser/accounts",
                    json={"browser": "zen", "profile": "abc.Default"})
    assert r.status_code == 200
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "done"
    cands = st["result"]["candidates"]
    assert cands[0]["authuser"] == 1
    assert cands[0]["account"]["name"] == "lnlydrvr"


def test_ytmusic_browser_accounts_requires_browser(client):
    r = client.post("/api/ytmusic/auth/browser/accounts", json={})
    assert r.status_code == 400
    assert r.json()["detail"] == {
        "code": "api.errors.browser_required", "params": {}, "message": "Select a browser",
    }


def test_ytmusic_oauth_job(client, monkeypatch):
    import threading

    import src.ytmusic as ytm

    started = threading.Event()

    def fake_oauth(client_id, client_secret, on_pending=None, open_browser=True,
                   timeout=600.0):
        started.set()
        if on_pending:
            on_pending("https://example.com/verify?user_code=ABC")
        assert client_id == "cid" and client_secret == "sec"

    monkeypatch.setattr(ytm, "oauth_authorize", fake_oauth)
    monkeypatch.setattr(ytm, "account_info",
                        lambda: {"name": "Тест", "email": "a@b.c"})
    r = client.post("/api/ytmusic/auth/oauth",
                    json={"client_id": "cid", "client_secret": "sec"})
    assert r.status_code == 200
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "done"
    assert st["result"]["account"]["name"] == "Тест"
    # событие с ссылкой подтверждения появилось в SSE-потоке
    events = jobs.get(r.json()["job_id"]).events
    assert any(e.get("type") == "progress" and e.get("auth_url") for e in events)


def test_ytmusic_oauth_requires_credentials(client):
    r = client.post("/api/ytmusic/auth/oauth",
                    json={"client_id": "", "client_secret": ""})
    assert r.status_code == 400


def test_ytmusic_oauth_rejects_second(client, monkeypatch):
    import threading

    import src.ytmusic as ytm

    release = threading.Event()

    def fake_oauth(client_id, client_secret, on_pending=None, open_browser=True,
                   timeout=600.0):
        release.wait(timeout=5)

    monkeypatch.setattr(ytm, "oauth_authorize", fake_oauth)
    r1 = client.post("/api/ytmusic/auth/oauth",
                     json={"client_id": "cid", "client_secret": "sec"})
    assert r1.status_code == 200
    r2 = client.post("/api/ytmusic/auth/oauth",
                     json={"client_id": "cid", "client_secret": "sec"})
    assert r2.status_code == 409
    release.set()
    wait_job(client, r1.json()["job_id"])


def test_ytmusic_liked_dedup(client, monkeypatch, mp3):
    import src.ytmusic as ytm
    monkeypatch.setattr(ytm, "liked_songs", lambda limit=100: [
        ytm.YTMTrack(video_id="v1", title="Song", artist="Artist"),
        ytm.YTMTrack(video_id="v2", title="Чего-то нет", artist="Nobody"),
    ])
    data = client.get("/api/ytmusic/liked").json()
    tracks = data["tracks"]
    assert tracks[0]["in_library"] is True, "совпадает с mp3-стабом в библиотеке"
    assert tracks[1]["in_library"] is False
    assert tracks[0]["video_id"] == "v1"
    assert tracks[0]["title"] == "Song"


def test_ytmusic_library_songs_endpoint(client, monkeypatch, mp3):
    import src.ytmusic as ytm
    monkeypatch.setattr(ytm, "library_songs", lambda limit=100: [
        ytm.YTMTrack(video_id="l1", title="Song", artist="Artist"),
        ytm.YTMTrack(video_id="l2", title="Из библиотеки", artist="Nobody"),
    ])
    tracks = client.get("/api/ytmusic/library_songs").json()["tracks"]
    assert tracks[0]["video_id"] == "l1"
    assert tracks[0]["in_library"] is True, "совпадает с mp3-стабом в библиотеке"
    assert tracks[1]["in_library"] is False


def test_ytmusic_albums_and_album(client, monkeypatch, mp3):
    import src.ytmusic as ytm
    set_tags(mp3, AudioTags(title="Song", artist="Artist", album="Альбом"))
    monkeypatch.setattr(ytm, "library_albums", lambda limit=100: [{
        "browseId": "A1", "title": "Альбом",
        "artists": [{"name": "Artist"}], "year": 2020, "trackCount": 1,
        "thumbnails": [{"url": "https://c/art", "width": 100}],
    }])
    monkeypatch.setattr(ytm, "get_album", lambda browse_id: {
        "title": "Альбом", "artists": [{"name": "Artist"}], "year": 2020,
        "thumbnails": [{"url": "https://c/art", "width": 100}],
        "tracks": [{
            "videoId": "v1", "title": "Song",
            "artists": [{"name": "Artist"}], "trackNumber": 3,
        }, {
            "videoId": "", "title": "NoVideo",
            "artists": [{"name": "Artist"}],
        }],
    })
    al = client.get("/api/ytmusic/albums").json()["albums"]
    assert al[0]["id"] == "A1"
    assert al[0]["artist"] == "Artist"
    assert al[0]["cover_url"] == "https://c/art"
    ab = client.get("/api/ytmusic/album", params={"browse_id": "A1"}).json()
    assert ab["title"] == "Альбом"
    assert ab["track_count"] == 1, "треки без videoId пропускаются"
    t = ab["tracks"][0]
    assert t["in_library"] is True
    assert t["track_number"] == 3


def test_ytmusic_album_track_match_requires_same_album(client, monkeypatch, mp3):
    import src.ytmusic as ytm
    monkeypatch.setattr(ytm, "get_album", lambda browse_id: {
        "title": "Chocolate Starfish And The Hot Dog Flavored Water",
        "artists": [{"name": "Artist"}],
        "tracks": [{
            "videoId": "v1", "title": "Song",
            "artists": [{"name": "Artist"}],
        }],
    })
    # The local file has the same artist/title, but belongs to another album.
    data = client.get("/api/ytmusic/album", params={"browse_id": "A1"}).json()
    assert data["tracks"][0]["in_library"] is False


def test_ytmusic_playlists_and_playlist(client, monkeypatch, mp3):
    import src.ytmusic as ytm
    monkeypatch.setattr(ytm, "library_playlists", lambda limit=100: [{
        "playlistId": "PL1", "title": "Главный", "count": 2,
        "thumbnails": [{"url": "https://c/pl", "width": 80}],
    }])
    monkeypatch.setattr(ytm, "get_playlist", lambda playlist_id: {
        "title": "Главный", "description": "описание",
        "thumbnails": [{"url": "https://c/pl", "width": 80}],
        "tracks": [{
            "videoId": "v1", "title": "Song", "artists": [{"name": "Artist"}],
        }, {
            "videoId": "v2", "title": "Other", "artists": [{"name": "Artist"}],
        }],
    })
    pls = client.get("/api/ytmusic/playlists").json()["playlists"]
    assert pls[0]["id"] == "PL1"
    assert pls[0]["count"] == 2
    pl = client.get("/api/ytmusic/playlist",
                    params={"playlist_id": "PL1"}).json()
    assert pl["track_count"] == 2
    assert [t["in_library"] for t in pl["tracks"]] == [True, False]


def test_ytmusic_albums_local_count(client, monkeypatch, mp3):
    import src.ytmusic as ytm
    monkeypatch.setattr(ytm, "library_albums", lambda limit=100: [{
        "browseId": "A1", "title": "Album", "artists": [{"name": "Artist"}],
        "trackCount": 2, "thumbnails": [{"url": "https://c/art", "width": 100}],
    }])
    al = client.get("/api/ytmusic/albums").json()["albums"]
    assert al[0]["in_library_tracks"] == 1, "mp3-стаб: 1 файл альбома Album/Artist"
    assert al[0]["in_library"] is True
    assert al[0]["track_count"] == 2


def test_ytmusic_albums_track_count_from_detail(client, monkeypatch, mp3):
    import src.ytmusic as ytm
    monkeypatch.setattr(ytm, "library_albums", lambda limit=100: [{
        "browseId": "A_DETAIL", "title": "Album", "artists": [{"name": "Artist"}],
        "thumbnails": [{"url": "https://c/art", "width": 100}],
    }])
    monkeypatch.setattr(ytm, "get_album", lambda browse_id: {
        "title": "Album", "artists": [{"name": "Artist"}],
        "thumbnails": [{"url": "https://c/art", "width": 100}],
        "trackCount": 4,
        "tracks": [{
            "videoId": "v1", "title": "Song", "artists": [{"name": "Artist"}],
        }, {
            "videoId": "v2", "title": "Song2", "artists": [{"name": "Artist"}],
        }],
    })
    al = client.get("/api/ytmusic/albums").json()["albums"]
    assert al[0]["track_count"] == 4, ("trackCount берётся из деталей "
                                       "альбома, если в списке его нет")


def test_ytmusic_playlists_local_archive(client, monkeypatch, mp3):
    import src.ytmusic as ytm
    monkeypatch.setattr(ytm, "library_playlists", lambda limit=100: [{
        "playlistId": "PL1", "title": "Главный", "count": 10,
        "thumbnails": [{"url": "https://c/pl", "width": 80}],
    }, {
        "playlistId": "PL2", "title": "Новый", "count": 3,
        "thumbnails": [{"url": "https://c/p2", "width": 80}],
    }])
    m3u = mp3.parent / "Плейлисты" / "Главный.m3u8"
    m3u.parent.mkdir(parents=True, exist_ok=True)
    m3u.write_text(
        "#EXTM3U\n#EXTINF:-1,Song\n/abs/song.mp3\n#EXTINF:-1,Two\n/abs/two.mp3\n",
        encoding="utf-8")
    pls = client.get("/api/ytmusic/playlists").json()["playlists"]
    assert pls[0]["local_count"] == 2, "записи локального .m3u8"
    assert pls[0]["in_library"] is True
    assert pls[1]["local_count"] == 0
    assert pls[1]["in_library"] is False


def test_ytmusic_artists_and_artist(client, monkeypatch, mp3):
    import src.ytmusic as ytm
    monkeypatch.setattr(ytm, "library_artists", lambda limit=100: [{
        "browseId": "UC1", "artist": "Artist", "subscribers": "2.9K",
        "thumbnails": [{"url": "https://c/art", "width": 100}],
    }, {
        "browseId": "UC2", "artist": "Nobody",
        "thumbnails": [{"url": "https://c/nob", "width": 100}],
    }])
    monkeypatch.setattr(ytm, "get_artist", lambda browse_id: {
        "name": "Artist", "subscribers": "2.9K",
        "thumbnails": [{"url": "https://c/art", "width": 100}],
        "topSongs": [{
            "videoId": "v1", "title": "Song", "artists": [{"name": "Artist"}],
        }, {
            "videoId": "v2", "title": "Other", "artists": [{"name": "Artist"}],
        }],
        "albums": [{
            "browseId": "A1", "title": "Альбом", "artists": [{"name": "Artist"}],
            "trackCount": 1, "thumbnails": [{"url": "https://c/a1", "width": 100}],
        }],
    })
    arts = client.get("/api/ytmusic/artists").json()["artists"]
    assert arts[0]["id"] == "UC1"
    assert arts[0]["name"] == "Artist"
    assert arts[0]["subscribers"] == "2.9K"
    assert arts[0]["local_count"] == 1, "mp3-стаб: файл исполнителя Artist"
    assert arts[1]["local_count"] == 0
    d = client.get("/api/ytmusic/artist", params={"browse_id": "UC1"}).json()
    assert d["name"] == "Artist"
    assert d["top_songs"][0]["in_library"] is True
    assert d["top_songs"][1]["in_library"] is False
    assert d["albums"][0]["track_count"] == 1
    assert d["albums"][0]["in_library_tracks"] == 0


def test_ytmusic_download_job(client, monkeypatch, mp3):
    from pathlib import Path
    from types import SimpleNamespace

    import src.ytmusic as ytm

    seen = []

    class FakeDownloader:
        def __init__(self, out):
            self.out = out

        def download(self, url, fmt, quality, progress_callback=None, source=None):
            seen.append(url)
            p = mp3 if len(seen) == 1 else self.out / f"dl{len(seen)}.mp3"
            if not p.exists():
                p.write_bytes((b"\xff\xfb\x90\x44" + b"\x00" * 413) * 4)
            return SimpleNamespace(success=True, error="", filepath=p, info=None)

    from types import SimpleNamespace

    monkeypatch.setattr(routes, "Downloader", FakeDownloader)
    monkeypatch.setattr("src.tagger.apply_cover_from_url", lambda *a, **k: None)
    r = client.post("/api/ytmusic/download", json={
        "items": [{
            "video_id": "v1", "title": "Song", "artist": "Artist",
            "album": "Альбом", "year": 2020, "track_number": 1,
            "cover_url": "",
        }, {
            "video_id": "v2", "title": "Missing", "artist": "Nobody",
        }],
        "playlist": "Лайки",
        "move": True,
    })
    assert r.status_code == 200
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "done"
    res = st["result"]
    res = st["result"]
    assert res["ok"] == 2
    paths = [i["path"] for i in res["items"]]
    assert all(p and Path(p).exists() for p in paths), "файлы переехали в библиотеку"
    assert any("Song" in p for p in paths), "теги применены, файл переименован"
    # архив .m3u8 создан и содержит записанный трек (по конечному пути)
    arch = Path(res["archive"])
    assert arch.exists() and arch.name == "Лайки.m3u8"
    assert any(p in arch.read_text(encoding="utf-8") for p in paths)


def test_ytmusic_download_failure_reported(client, monkeypatch, mp3):
    import src.ytmusic as ytm

    class BadRes:
        success = False
        error = "возрастное ограничение"
        filepath = None
        info = None

    class FakeDownloader:
        def __init__(self, out):
            pass

        def download(self, url, fmt, quality, progress_callback=None, source=None):
            return BadRes()

    monkeypatch.setattr(routes, "Downloader", FakeDownloader)
    r = client.post("/api/ytmusic/download", json={
        "items": [{"video_id": "v1", "title": "X", "artist": "Y"}],
        "playlist": "Лайки",
    })
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "done"
    res = st["result"]
    assert res["ok"] == 0 and res["errors"] == 1
    assert res["items"][0]["error"] == "возрастное ограничение"


def test_ytmusic_download_requires_items(client):
    r = client.post("/api/ytmusic/download", json={"items": []})
    assert r.status_code == 400
    assert client.post("/api/ytmusic/download", json={}).status_code == 400


def test_settings_no_clips_default_and_put(client):
    s = client.get("/api/settings").json()
    assert s["ytmusic_no_clips"] is True
    assert client.put("/api/settings", json={"ytmusic_no_clips": False}).status_code == 200
    assert client.get("/api/settings").json()["ytmusic_no_clips"] is False
    assert client.put("/api/settings", json={"ytmusic_no_clips": True}).status_code == 200
    assert client.get("/api/settings").json()["ytmusic_no_clips"] is True


def test_ytmusic_download_resolves_audio_version(client, monkeypatch, mp3):
    from pathlib import Path
    from types import SimpleNamespace

    import src.ytmusic as ytm

    used = {}

    class FakeDownloader:
        def __init__(self, out):
            pass

        def download(self, url, fmt, quality, progress_callback=None, source=None):
            used["url"] = url
            p = mp3 if not mp3.exists() else mp3
            return SimpleNamespace(success=True, error="", filepath=p, info=None)

    monkeypatch.setattr(routes, "Downloader", FakeDownloader)
    monkeypatch.setattr("src.tagger.apply_cover_from_url", lambda *a, **k: None)
    monkeypatch.setattr(ytm, "find_audio_version", lambda track: ytm.track_from_dict({
        "videoId": "atv9", "title": track.title, "artist": track.artist,
        "videoType": ytm.ATV_TYPE}))
    r = client.post("/api/ytmusic/download", json={
        "items": [{"video_id": "clip1", "title": "Song", "artist": "Artist",
                   "video_type": "MUSIC_VIDEO_TYPE_OMV"}],
        "playlist": "Лайки", "move": False, "no_clips": True,
    })
    st = wait_job(client, r.json()["job_id"])
    assert st["status"] == "done"
    res = st["result"]
    assert res["items"][0]["video_id"] == "atv9", "videoId подменён на аудиоверсию"
    assert res["items"][0]["kept_clip"] is False
    assert "watch?v=atv9" in used["url"]


def test_ytmusic_download_keeps_clip_when_no_audio(client, monkeypatch, mp3):
    from types import SimpleNamespace

    import src.ytmusic as ytm

    class FakeDownloader:
        def __init__(self, out):
            pass

        def download(self, url, fmt, quality, progress_callback=None, source=None):
            return SimpleNamespace(success=True, error="", filepath=mp3, info=None)

    monkeypatch.setattr(routes, "Downloader", FakeDownloader)
    monkeypatch.setattr("src.tagger.apply_cover_from_url", lambda *a, **k: None)
    monkeypatch.setattr(ytm, "find_audio_version", lambda track: None)
    r = client.post("/api/ytmusic/download", json={
        "items": [{"video_id": "clip1", "title": "Song", "artist": "Artist",
                   "video_type": "MUSIC_VIDEO_TYPE_OMV"}],
        "playlist": "Лайки", "move": False, "no_clips": True,
    })
    st = wait_job(client, r.json()["job_id"])
    res = st["result"]
    assert res["items"][0]["video_id"] == "clip1", "фолбэк на клип: аудиоверсия не найдена"
    assert res["items"][0]["kept_clip"] is True
    assert res["items"][0]["path"] == str(mp3)


def test_ytmusic_download_no_clips_false_uses_clip(client, monkeypatch, mp3):
    from types import SimpleNamespace

    import src.ytmusic as ytm

    class FakeDownloader:
        def __init__(self, out):
            pass

        def download(self, url, fmt, quality, progress_callback=None, source=None):
            return SimpleNamespace(success=True, error="", filepath=mp3, info=None)

    monkeypatch.setattr(routes, "Downloader", FakeDownloader)
    monkeypatch.setattr("src.tagger.apply_cover_from_url", lambda *a, **k: None)
    monkeypatch.setattr(ytm, "find_audio_version",
                        lambda track: (_ for _ in ()).throw(AssertionError("не должны искать")))
    r = client.post("/api/ytmusic/download", json={
        "items": [{"video_id": "clip1", "title": "Song", "artist": "Artist",
                   "video_type": "MUSIC_VIDEO_TYPE_OMV"}],
        "playlist": "Лайки", "move": False, "no_clips": False,
    })
    st = wait_job(client, r.json()["job_id"])
    res = st["result"]
    assert res["items"][0]["video_id"] == "clip1"


def test_ytmusic_search_dedup(client, monkeypatch, mp3):
    import src.ytmusic as ytm
    monkeypatch.setattr(ytm, "search_songs", lambda q, limit=10: [
        ytm.YTMTrack(video_id="v1", title="Song", artist="Artist"),
        ytm.YTMTrack(video_id="v2", title="New", artist="Band"),
    ])
    data = client.get("/api/ytmusic/search", params={"q": "Artist Song"}).json()
    tracks = data["tracks"]
    assert tracks[0]["in_library"] is True
    assert tracks[1]["in_library"] is False
    assert tracks[0]["video_id"] == "v1"


def test_ytmusic_search_without_connection(client, monkeypatch):
    import src.ytmusic as ytm
    monkeypatch.setattr(ytm, "search_songs",
                        lambda q, limit=10: (_ for _ in ()).throw(
                            ytm.YTMusicError("нет ответа")))
    r = client.get("/api/ytmusic/search", params={"q": "x"})
    assert r.status_code == 502
    assert "нет ответа" in r.json()["detail"]


def test_ytmusic_radio(client, monkeypatch, mp3):
    import src.ytmusic as ytm
    monkeypatch.setattr(ytm, "watch_playlist", lambda video_id, limit=25: [
        ytm.YTMTrack(video_id="r1", title="Song", artist="Artist"),
        ytm.YTMTrack(video_id="r2", title="Radio other", artist="Band"),
    ])
    data = client.get("/api/ytmusic/radio",
                      params={"video_id": "seed"}).json()
    tracks = data["tracks"]
    assert tracks[0]["in_library"] is True
    assert tracks[1]["in_library"] is False


def test_ytm_feedback_rates_song(monkeypatch):
    import threading

    import src.web.routes as routes
    import src.ytmusic as ytm

    done = threading.Event()
    rated = []
    monkeypatch.setattr(ytm, "connected", lambda: True)
    monkeypatch.setattr(ytm, "search_songs",
                        lambda q, limit=3: [ytm.YTMTrack(video_id="v9",
                                                         title="T", artist="A")])
    monkeypatch.setattr(ytm, "rate_song",
                        lambda vid, rating: (rated.append((vid, rating)) or done.set()))
    routes._ytm_feedback("A", "T", "LIKE")
    assert done.wait(timeout=3)
    assert rated == [("v9", "LIKE")]


def test_ytm_feedback_silent_when_offline(monkeypatch):
    import threading

    import src.web.routes as routes
    import src.ytmusic as ytm

    called = []
    monkeypatch.setattr(ytm, "connected", lambda: False)

    def track():
        called.append(1)

    monkeypatch.setattr(ytm, "search_songs",
                        lambda q, limit=3: (called.append(1), [])[1])
    routes._ytm_feedback("A", "T", "LIKE")
    time.sleep(0.3)
    assert called == []


def test_ytm_feedback_library_action(monkeypatch):
    """Настройка library: принятая рекомендация сохраняется в библиотеку YT."""
    import src.web.routes as routes
    import src.ytmusic as ytm
    from src.config import FEEDBACK_ACTION_KEY

    _save_config(**{FEEDBACK_ACTION_KEY: "library"})
    monkeypatch.setattr(ytm, "connected", lambda: True)
    hit = ytm.YTMTrack(video_id="v9", title="T", artist="A", feedback_token="tok-1")
    monkeypatch.setattr(ytm, "search_songs", lambda q, limit=3: [hit])
    added, rated = [], []
    monkeypatch.setattr(ytm, "add_to_library", lambda t: added.append(t))
    monkeypatch.setattr(ytm, "rate_song",
                        lambda vid, rating: rated.append((vid, rating)))

    routes._ytm_feedback_sync("A", "T")
    assert [t.video_id for t in added] == ["v9"]
    assert added[0].feedback_token == "tok-1"
    assert rated == [], "при режиме библиотеки лайк не ставится"


def test_ytm_feedback_explicit_rating_overrides_setting(monkeypatch):
    import src.web.routes as routes
    import src.ytmusic as ytm
    from src.config import FEEDBACK_ACTION_KEY

    _save_config(**{FEEDBACK_ACTION_KEY: "library"})
    monkeypatch.setattr(ytm, "connected", lambda: True)
    monkeypatch.setattr(ytm, "search_songs",
                        lambda q, limit=3: [ytm.YTMTrack(video_id="v9",
                                                         title="T", artist="A")])
    added, rated = [], []
    monkeypatch.setattr(ytm, "add_to_library", lambda t: added.append(t))
    monkeypatch.setattr(ytm, "rate_song",
                        lambda vid, rating: rated.append((vid, rating)))

    routes._ytm_feedback_sync("A", "T", "DISLIKE")
    assert rated == [("v9", "DISLIKE")]
    assert added == [], "дизлайк всегда идёт как оценка"


def test_ytm_feedback_library_error_swallowed(monkeypatch):
    import threading

    import src.web.routes as routes
    import src.ytmusic as ytm
    from src.config import FEEDBACK_ACTION_KEY

    _save_config(**{FEEDBACK_ACTION_KEY: "library"})
    monkeypatch.setattr(ytm, "connected", lambda: True)
    monkeypatch.setattr(ytm, "search_songs",
                        lambda q, limit=3: [ytm.YTMTrack(video_id="v9",
                                                         title="T", artist="A")])
    rated = []

    def boom(t):
        raise ytm.YTMusicError("нет токена")

    monkeypatch.setattr(ytm, "add_to_library", boom)
    monkeypatch.setattr(ytm, "rate_song",
                        lambda vid, rating: rated.append((vid, rating)))

    routes._ytm_feedback("A", "T")  # в фоне: ошибка не выплывает
    time.sleep(0.3)
    assert rated == []


def test_settings_feedback_action_roundtrip(client):
    from src.config import FEEDBACK_ACTION_KEY

    assert client.get("/api/settings").json()[FEEDBACK_ACTION_KEY] == "like"
    r = client.put("/api/settings", json={FEEDBACK_ACTION_KEY: "library"})
    assert r.status_code == 200
    assert client.get("/api/settings").json()[FEEDBACK_ACTION_KEY] == "library"
    r = client.put("/api/settings", json={FEEDBACK_ACTION_KEY: "thumbs_up"})
    assert r.status_code == 400


def test_settings_search_source_roundtrip(client):
    from src.config import SEARCH_SOURCE_KEY

    assert client.get("/api/settings").json()[SEARCH_SOURCE_KEY] == "youtube_music"
    r = client.put("/api/settings", json={SEARCH_SOURCE_KEY: "youtube"})
    assert r.status_code == 200
    assert client.get("/api/settings").json()[SEARCH_SOURCE_KEY] == "youtube"
    r = client.put("/api/settings", json={SEARCH_SOURCE_KEY: "rutube"})
    assert r.status_code == 400
    # мусорное значение не сохранилось
    assert client.get("/api/settings").json()[SEARCH_SOURCE_KEY] == "youtube"


def test_jobs_list_for_downloads_dock(client):
    # Док загрузок: статус отдаёт created_at, список — последние сверху.
    r = client.post("/api/library/sort")
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    st = wait_job(client, job_id)
    assert st["created_at"] > 0
    items = client.get("/api/jobs", params={"limit": 10}).json()
    assert any(j["id"] == job_id for j in items)
    assert items[0]["created_at"] >= items[-1]["created_at"]


# --- Статика SPA: по умолчанию отдаётся собранный React-dist, ---------------
# --- без dist — страница-подсказка 503 ---------------------------------------


def test_spa_serves_react_dist_by_default():
    import src.web.server as server

    dist = Path(server.__file__).parent / "dist"
    assert (dist / "index.html").is_file(), "соберите фронтенд: npm run build в frontend/"
    with TestClient(server.create_app()) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert '<div id="root">' in r.text


@pytest.mark.parametrize(
    ("accept_language", "language", "heading"),
    [
        ("ru", "ru", "Фронтенд не собран"),
        ("en", "en", "Frontend not built"),
        (None, "en", "Frontend not built"),
        ("de, fr;q=0.9", "en", "Frontend not built"),
        ("de;q=1, ru;q=0.4, en;q=0.8", "en", "Frontend not built"),
        ("ru;q=0, en;q=0.5", "en", "Frontend not built"),
        ("ru-RU;q=0.2, en-US;q=0.8", "en", "Frontend not built"),
        ("ru;q=nan, en;q=0.8", "en", "Frontend not built"),
    ],
)
def test_spa_without_dist_negotiates_build_hint_language(
    monkeypatch, accept_language, language, heading,
):
    import src.web.server as server

    monkeypatch.setattr(server, "_DIST_DIRNAME", "dist-missing")
    with TestClient(server.create_app()) as c:
        headers = {"Accept-Language": accept_language} if accept_language else {}
        r = c.get("/", headers=headers)
        assert r.status_code == 503
        assert r.headers["content-language"] == language
        assert r.headers["vary"] == "Accept-Language"
        assert f'<html lang="{language}">' in r.text
        assert heading in r.text
        assert "npm run build" in r.text
        # API работает и без dist
        assert c.get("/api/jobs").status_code == 200
