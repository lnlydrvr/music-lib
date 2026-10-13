"""Тесты интеграции с YouTube Music (ytmusicapi).

Чистые функции (обложка, нормализация трека, типы авторизации, валидация
заголовков) проверяются напрямую; сеть и тяжёлые зависимости (YTMusic,
OAuthCredentials, setup) стабаются monkeypatch'ем.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.config as config
import src.ytmusic as ytmusic
import ytmusicapi


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    cfgdir = home / ".config" / "music-lib"
    monkeypatch.setattr(config, "CONFIG_DIR", cfgdir)
    monkeypatch.setattr(config, "CONFIG_PATH", cfgdir / "config.json")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    return home


def write_auth(home: Path, data: dict) -> Path:
    cfgdir = home / ".config" / "music-lib"
    cfgdir.mkdir(parents=True, exist_ok=True)
    path = cfgdir / "ytmusic_auth.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# --- Чистые функции ------------------------------------------------------


def test_pick_thumbnail():
    assert ytmusic.pick_thumbnail(None) == ""
    assert ytmusic.pick_thumbnail([]) == ""
    assert ytmusic.pick_thumbnail({"url": "x", "width": 480}) == "x"
    assert ytmusic.pick_thumbnail([
        {"url": "a", "width": 60},
        {"url": "b", "width": 200},
        {"url": "c", "width": 480},
    ]) == "b", "берётся самая крупная не больше порога"
    assert ytmusic.pick_thumbnail([{"url": "c", "width": 600}]) == "c"
    assert ytmusic.pick_thumbnail([{"url": "a"}, {"url": "b"}]) == "b"


def test_track_from_dict_full():
    track = ytmusic.track_from_dict({
        "videoId": "v1", "title": "  Title  ",
        "artists": [{"name": "A"}, {"name": "B"}],
        "album": {"name": "Alb"}, "year": "2021", "trackNumber": "3",
        "duration": 210, "thumbnails": [{"url": "c", "width": 100}],
    })
    assert track.video_id == "v1"
    assert track.title == "Title"
    assert track.artist == "A, B"
    assert track.album == "Alb"
    assert track.year == 2021
    assert track.track_number == 3
    assert track.duration == 210
    assert track.cover_url == "c"


def test_track_from_dict_video_type():
    track = ytmusic.track_from_dict({
        "videoId": "v1", "title": "T", "artist": "A",
        "videoType": "MUSIC_VIDEO_TYPE_OMV",
    })
    assert track.video_type == "MUSIC_VIDEO_TYPE_OMV"
    assert ytmusic.is_clip(track) is True
    assert ytmusic.is_clip(ytmusic.track_from_dict({
        "videoId": "v2", "title": "T", "artist": "A",
        "videoType": ytmusic.ATV_TYPE})) is False
    assert ytmusic.is_clip(ytmusic.track_from_dict({"videoId": "v3"})) is False


def test_track_from_dict_radio_thumbnail_singular():
    """radio (watch_playlist) отдаёт thumbnail, а не thumbnails."""
    track = ytmusic.track_from_dict({
        "videoId": "v1", "title": "T", "artist": "A",
        "thumbnail": [{"url": "c", "width": 60, "height": 60}],
    })
    assert track.cover_url == "c"


def test_find_audio_version_already_atv():
    track = ytmusic.track_from_dict({"videoId": "v1", "title": "T", "artist": "A",
                                     "videoType": ytmusic.ATV_TYPE})
    assert ytmusic.find_audio_version(track) is track


def test_find_audio_version_search(monkeypatch):
    track = ytmusic.track_from_dict({"videoId": "clip", "title": "The End!",
                                     "artist": "Doors",
                                     "videoType": "MUSIC_VIDEO_TYPE_OMV"})
    monkeypatch.setattr(ytmusic, "search_songs", lambda q, limit=5: [
        ytmusic.track_from_dict({"videoId": "atv1", "title": "The End",
                                 "artist": "Doors",
                                 "videoType": "MUSIC_VIDEO_TYPE_UGC"}),
        ytmusic.track_from_dict({"videoId": "atv2", "title": "The End",
                                 "artist": "Doors",
                                 "videoType": ytmusic.ATV_TYPE}),
    ])
    alt = ytmusic.find_audio_version(track)
    assert alt is not None
    assert alt.video_id == "atv2"
    assert alt.video_type == ytmusic.ATV_TYPE


def test_find_audio_version_no_match(monkeypatch):
    track = ytmusic.track_from_dict({"videoId": "clip", "title": "The End",
                                     "artist": "Doors",
                                     "videoType": "MUSIC_VIDEO_TYPE_OMV"})
    monkeypatch.setattr(ytmusic, "search_songs", lambda q, limit=5: [])
    assert ytmusic.find_audio_version(track) is None


def test_find_audio_version_skips_weak_input(monkeypatch):
    track = ytmusic.track_from_dict({"videoId": "clip", "videoType": "MUSIC_VIDEO_TYPE_OMV"})
    monkeypatch.setattr(ytmusic, "search_songs", lambda q, limit=5: (_ for _ in ()).throw(AssertionError))
    assert ytmusic.find_audio_version(track) is None


def test_track_from_dict_missing():
    track = ytmusic.track_from_dict({})
    assert track.artist == "Неизвестный исполнитель"
    assert not track.title and not track.video_id
    assert track.year is None
    assert track.track_number is None
    assert track.duration is None


def test_track_from_dict_not_dict():
    track = ytmusic.track_from_dict("junk")
    assert track.artist == "Неизвестный исполнитель"


def test_auth_mode_detection():
    oauth = {"access_token": "a", "refresh_token": "r", "client_id": "c"}
    assert ytmusic.auth_mode_from_data(oauth) == "oauth"
    assert ytmusic.auth_mode_from_data({"authorization": "a", "cookie": "b"}) == "browser"
    assert ytmusic.auth_mode_from_data({"foo": 1}) == ""
    assert ytmusic.auth_mode_from_data(None) == ""


def test_validate_browser_headers():
    assert ytmusic.validate_browser_headers("") is not None
    assert ytmusic.validate_browser_headers("привет как дела") is not None
    assert ytmusic.validate_browser_headers("Cookie: a") is not None
    good = "accept: x\nauthorization: a\ncookie: c\nx-goog-authuser: 0"
    assert ytmusic.validate_browser_headers(good) is None
    assert ytmusic.validate_browser_headers(
        "Cookie: a\nX-Goog-AuthUser: 0\nContent-Type: text") is None


# --- Состояние авторизации ----------------------------------------------


def test_connected_false_without_file(isolated_home):
    assert ytmusic.connected() is False
    assert ytmusic.auth_mode() == ""
    assert ytmusic.account_info() == {}
    assert ytmusic.get_client() is None


def test_connected_browser(isolated_home):
    write_auth(isolated_home, {"Authorization": "a", "Cookie": "c"})
    assert ytmusic.connected() is True
    assert ytmusic.auth_mode() == "browser"


def test_connected_oauth(isolated_home):
    write_auth(isolated_home, {
        "access_token": "at", "refresh_token": "rt",
        "client_id": "cid", "client_secret": "sec",
    })
    assert ytmusic.connected() is True
    assert ytmusic.auth_mode() == "oauth"


def test_read_auth_data_bad_json(isolated_home):
    path = isolated_home / ".config/music-lib/ytmusic_auth.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")
    assert ytmusic.read_auth_data() is None
    assert ytmusic.connected() is False


def test_get_auth_file_default(isolated_home, monkeypatch):
    from src import config as _cfg
    monkeypatch.setattr(_cfg, "CONFIG_DIR",
                        isolated_home / ".config/music-lib")
    assert ytmusic.get_auth_file() == \
        isolated_home / ".config/music-lib/ytmusic_auth.json"


def test_get_auth_file_override(isolated_home, monkeypatch):
    from src import config as _cfg
    cfg = {"ytmusic_auth_file": "custom/auth.json"}
    monkeypatch.setattr(_cfg, "load_config", lambda: cfg)
    assert ytmusic.get_auth_file() == Path("custom/auth.json")


# --- Клиент и запросы ----------------------------------------------------


class FakeYTMusic:
    """Замена ytmusicapi.YTMusic: методы из handlers, __init__ без сети."""

    def __init__(self, auth=None, handlers=None):
        self.auth = auth
        self.handlers = handlers or {}

    def __getattr__(self, name):
        if name in self.handlers:
            return self.handlers[name]
        raise AttributeError(name)


@pytest.fixture
def fake_client(isolated_home, monkeypatch, request):
    """Записать browser-файл авторизации и подменить get_client фейком."""
    write_auth(isolated_home, {"Authorization": "a", "Cookie": "c"})
    handlers = getattr(request, "param", {}) or {}
    fake = FakeYTMusic(handlers=handlers)
    monkeypatch.setattr(ytmusic, "get_client", lambda: fake)
    monkeypatch.setattr(ytmusicapi, "YTMusic", FakeYTMusic)
    return fake


def test_get_client_caches(isolated_home, monkeypatch):
    write_auth(isolated_home, {"Authorization": "a", "Cookie": "c"})
    monkeypatch.setattr(ytmusicapi, "YTMusic", FakeYTMusic)
    ytmusic.invalidate_client()
    first = ytmusic.get_client()
    second = ytmusic.get_client()
    assert first is second, "повторный вызов должен брать клиент из кэша"
    ytmusic.clear_auth()
    assert ytmusic.get_client() is None


def test_require_client_raises(isolated_home):
    with pytest.raises(ytmusic.YTMusicError):
        ytmusic.require_client()


class _RecYTMusic:
    def __init__(self, **kw):
        self.kw = kw


def test_get_client_oauth_passes_credentials(isolated_home, monkeypatch):
    write_auth(isolated_home, {
        "access_token": "at", "refresh_token": "rt",
        "client_id": "cid", "client_secret": "sec",
    })
    monkeypatch.setattr(ytmusicapi, "YTMusic", _RecYTMusic)
    ytmusic.invalidate_client()
    client = ytmusic.get_client()
    assert isinstance(client, _RecYTMusic)
    assert client.kw["auth"] == str(ytmusic.get_auth_file())
    creds = client.kw["oauth_credentials"]
    assert creds.client_id == "cid"
    assert creds.client_secret == "sec"


def test_get_client_oauth_missing_secret(isolated_home, monkeypatch):
    write_auth(isolated_home, {
        "access_token": "at", "refresh_token": "rt",
        "client_id": "cid",
    })
    monkeypatch.setattr(ytmusicapi, "YTMusic", _RecYTMusic)
    ytmusic.invalidate_client()
    with pytest.raises(ytmusic.YTMusicError, match="client_id|client_secret"):
        ytmusic.get_client()


@pytest.mark.parametrize("fake_client", [
    {
        "get_liked_songs": lambda limit=100: {
            "tracks": [{
                "videoId": "v1", "title": "Песня",
                "artists": [{"name": "Исполнитель"}],
                "album": {"name": "Альбом"},
                "year": 2001, "trackNumber": 1, "duration": 60,
                "thumbnails": [{"url": "c1", "width": 90}],
            }],
        },
    },
], indirect=True)
def test_liked_songs_maps(fake_client):
    tracks = ytmusic.liked_songs(limit=5)
    assert len(tracks) == 1
    track = tracks[0]
    assert track.video_id == "v1"
    assert track.artist == "Исполнитель"
    assert track.title == "Песня"
    assert track.year == 2001
    assert track.cover_url == "c1"


@pytest.mark.parametrize("fake_client", [
    {"get_liked_songs": lambda limit=100: (_ for _ in ()).throw(
        ytmusicapi.YTMusicError("bad"))},
], indirect=True)
def test_liked_songs_wraps_error(fake_client):
    with pytest.raises(ytmusic.YTMusicError):
        ytmusic.liked_songs()


@pytest.mark.parametrize("fake_client", [
    {"get_account_info": lambda: {"name": "Аккаунт", "email": "a@b.c"}},
], indirect=True)
def test_account_info_connected(fake_client):
    info = ytmusic.account_info()
    assert info["name"] == "Аккаунт"


@pytest.mark.parametrize("fake_client", [
    {"search": lambda query, filter=None, limit=10: [
        {"videoId": "s1", "title": "Найдено",
         "artists": [{"name": "Арт"}], "thumbnails": {"url": "t", "width": 50}},
    ]},
], indirect=True)
def test_search_songs_maps(fake_client):
    tracks = ytmusic.search_songs("query", limit=5)
    assert tracks[0].video_id == "s1"
    assert tracks[0].title == "Найдено"
    assert tracks[0].cover_url == "t"


def test_search_songs_without_auth(isolated_home, monkeypatch):
    monkeypatch.setattr(ytmusicapi, "YTMusic", FakeYTMusic)
    fake = FakeYTMusic(handlers={
        "search": lambda query, filter=None, limit=10: [
            {"videoId": "s1", "title": "X", "artists": []},
        ]})
    monkeypatch.setattr(ytmusic, "_CLIENT_CACHE", {})
    monkeypatch.setattr(
        ytmusic, "get_client", lambda: None, raising=False)
    found_instances = []
    original = FakeYTMusic

    class _Build(original):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.handlers = {"search": fake.handlers["search"]}
            found_instances.append(self)

    monkeypatch.setattr(ytmusicapi, "YTMusic", _Build)
    tracks = ytmusic.search_songs("нет авторизации")
    assert tracks[0].video_id == "s1"
    assert found_instances, "без авторизации должен создаваться YTMusic()"


def test_rate_song_bad_rating(isolated_home):
    with pytest.raises(ytmusic.YTMusicError):
        ytmusic.rate_song("v1", "MAYBE")


@pytest.mark.parametrize("fake_client", [
    {"rate_song": lambda video_id, rating: None},
], indirect=True)
def test_rate_song_maps_rating(fake_client, monkeypatch):
    import ytmusicapi.models.content.enums as enums
    monkeypatch.setattr(enums, "LikeStatus", SimpleNamespace(
        LIKE="L", DISLIKE="D", INDIFFERENT="I"))
    fake_client.rate_song_calls = []
    calls = []

    def recorder(video_id, rating):
        calls.append((video_id, rating))

    fake_client.handlers["rate_song"] = recorder
    ytmusic.rate_song("v1", "LIKE")
    assert calls == [("v1", "L")]


# --- Добавление в библиотеку -----------------------------------------------


def test_track_from_dict_feedback_tokens():
    raw = {"videoId": "v1", "title": "T", "artists": [{"name": "A"}],
           "feedbackTokens": {"add": "tok-add", "remove": "tok-rm"}}
    assert ytmusic.track_from_dict(raw).feedback_token == "tok-add"
    flat = ytmusic.track_from_dict(
        {"videoId": "v2", "title": "T2", "feedbackTokenAdd": "tok-flat"})
    assert flat.feedback_token == "tok-flat"
    none = ytmusic.track_from_dict({"videoId": "v3", "title": "T3"})
    assert none.feedback_token == ""


@pytest.mark.parametrize("fake_client", [
    {"search": lambda query, filter=None, limit=10: [
        {"videoId": "s1", "title": "Найдено", "artists": [{"name": "Арт"}],
         "feedbackTokens": {"add": "add-1"}},
    ]},
], indirect=True)
def test_search_songs_keeps_feedback_token(fake_client):
    tracks = ytmusic.search_songs("query", limit=5)
    assert tracks[0].feedback_token == "add-1"


@pytest.mark.parametrize("fake_client", [
    {"edit_song_library_status": lambda tokens: {"success": True}},
], indirect=True)
def test_add_to_library_sends_token(fake_client):
    calls = []

    def recorder(tokens):
        calls.append(list(tokens))
        return {"success": True}

    fake_client.handlers["edit_song_library_status"] = recorder
    ytmusic.add_to_library(ytmusic.YTMTrack(
        video_id="v1", title="T", artist="A", feedback_token="tok"))
    assert calls == [["tok"]]


@pytest.mark.parametrize("fake_client", [{}], indirect=True)
def test_add_to_library_requires_token(fake_client):
    with pytest.raises(ytmusic.YTMusicError, match="токен"):
        ytmusic.add_to_library(
            ytmusic.YTMTrack(video_id="v1", title="T", artist="A"))


@pytest.mark.parametrize("fake_client", [
    {"edit_song_library_status": lambda tokens: (_ for _ in ()).throw(
        ytmusicapi.YTMusicError("bad"))},
], indirect=True)
def test_add_to_library_wraps_error(fake_client):
    with pytest.raises(ytmusic.YTMusicError):
        ytmusic.add_to_library(ytmusic.YTMTrack(
            video_id="v1", title="T", artist="A", feedback_token="tok"))


@pytest.mark.parametrize("fake_client", [
    {"get_library_songs": lambda limit=100: [{
        "videoId": "l1", "title": "Из библиотеки",
        "artists": [{"name": "Исполнитель"}],
        "album": {"name": "Альбом"}, "year": 2002,
        "thumbnails": [{"url": "c2", "width": 90}],
    }]},
], indirect=True)
def test_library_songs_maps(fake_client):
    tracks = ytmusic.library_songs(limit=5)
    assert len(tracks) == 1
    track = tracks[0]
    assert track.video_id == "l1"
    assert track.title == "Из библиотеки"
    assert track.artist == "Исполнитель"
    assert track.cover_url == "c2"


@pytest.mark.parametrize("fake_client", [
    {"get_library_songs": lambda limit=100: (_ for _ in ()).throw(
        ytmusicapi.YTMusicError("bad"))},
], indirect=True)
def test_library_songs_wraps_error(fake_client):
    with pytest.raises(ytmusic.YTMusicError):
        ytmusic.library_songs()


# --- Запись авторизации --------------------------------------------------


def test_write_browser_auth_invalid(isolated_home, monkeypatch):
    monkeypatch.setattr(ytmusicapi, "setup", lambda **kw: kw)
    with pytest.raises(ytmusic.YTMusicError) as exc:
        ytmusic.write_browser_auth("Smth: без Cookies")
    assert "cookie" in str(exc.value).lower()


def test_write_browser_auth_writes(isolated_home, monkeypatch):
    good = "Cookie: c\nX-Goog-AuthUser: 0\nAuthorization: a\n"
    written = {}

    def fake_setup(headers_raw=None, filepath=None):
        written["filepath"] = filepath
        written["raw"] = headers_raw
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        Path(filepath).write_text(json.dumps(
            {"cookie": "c", "x-goog-authuser": "0"}), encoding="utf-8")

    monkeypatch.setattr(ytmusicapi, "setup", fake_setup)
    ytmusic.write_browser_auth(good)
    assert written["raw"] == good
    assert Path(written["filepath"]).is_file()
    assert ytmusic.connected() is True
    assert ytmusic.auth_mode() == "browser"


def test_clear_auth(isolated_home):
    path = write_auth(isolated_home, {"Authorization": "a", "Cookie": "c"})
    assert path.is_file()
    ytmusic.clear_auth()
    assert not path.exists()
    assert ytmusic.connected() is False


# --- Извлечение кук из браузера -----------------------------------------


def _jar(*triples):
    return [SimpleNamespace(domain=d, name=n, value=v)
            for d, n, v in triples]


def test_cookies_header_prefers_specific_domain():
    header = ytmusic._cookies_header(_jar(
        (".youtube.com", "SID", "one"),
        (".music.youtube.com", "SID", "two"),
        (".music.youtube.com", "__Secure-3PAPISID", "p3"),
        (".facebook.com", "fbsr", "no"),
    ))
    assert "__Secure-3PAPISID=p3" in header
    assert "SID=two" in header, "конкретный домен music.youtube.com важнее"
    assert "SID=one" not in header
    assert "fbsr" not in header


def test_available_browsers_detects_profiles(tmp_path, monkeypatch):
    roots = tmp_path / "AppSupport"
    chrome = roots / "Google" / "Chrome"
    (chrome / "Default").mkdir(parents=True)
    (chrome / "Profile 1").mkdir()
    (chrome / "System Profile").mkdir()
    (chrome / "Local State").write_text("{}", encoding="utf-8")
    (roots / "BraveSoftware" / "Brave-Browser" / "Default").mkdir(parents=True)
    monkeypatch.setattr(ytmusic, "_browser_roots_dir", lambda: roots)
    found = {b["name"]: b["profiles"] for b in ytmusic.available_browsers()}
    assert found.get("chrome") == ["Default", "Profile 1"]
    assert found.get("brave") == ["Default"]
    assert "edge" not in found, "не установленный браузер не светится"


class _ProbeClient:
    def __init__(self, account, liked):
        self._account = account
        self._liked = liked

    def get_account_info(self):
        return {"accountName": self._account["name"]}

    def get_liked_songs(self, limit=100):
        return {"trackCount": self._liked}


def test_probe_authuser_one_working():
    def factory(headers):
        au = int(headers["x-goog-authuser"])
        if au == 1:
            return _ProbeClient({"name": "lnlydrvr"}, 42)
        raise RuntimeError("не этот профиль")
    au, account = ytmusic._probe_authuser("c=1", client_factory=factory)
    assert au == 1
    assert account["name"] == "lnlydrvr"


def test_probe_authuser_prefers_most_likes():
    def factory(headers):
        au = int(headers["x-goog-authuser"])
        if au in (0, 2):
            return _ProbeClient({"name": f"acc{au}"}, au * 10)
        raise RuntimeError
    au, account = ytmusic._probe_authuser("c", client_factory=factory)
    assert au == 2
    assert account["name"] == "acc2"


def test_probe_authuser_none():
    with pytest.raises(ytmusic.YTMusicError):
        ytmusic._probe_authuser(
            "c", client_factory=lambda h: (_ for _ in ()).throw(RuntimeError))


def test_authuser_candidates_sorted_by_likes():
    def factory(headers):
        au = int(headers["x-goog-authuser"])
        if au == 0:
            return _ProbeClient({"name": "roman"}, 1)
        if au == 2:
            return _ProbeClient({"name": "lnlydrvr"}, 9)
        raise RuntimeError
    cands = ytmusic._authuser_candidates("c", client_factory=factory)
    assert [c["authuser"] for c in cands] == [2, 0]
    assert cands[0]["account"]["name"] == "lnlydrvr"
    assert cands[0]["likes"] == 9


def test_browser_accounts_lists_candidates(tmp_path, monkeypatch):
    bat = Path(tmp_path) / "jar"
    bat.mkdir()
    jar = _jar(
        (".music.youtube.com", "__Secure-3PAPISID", "p3"),
        (".youtube.com", "SID", "sid"),
    )
    monkeypatch.setattr(ytmusic, "_read_browser_cookies",
                        lambda browser, profile=None: jar)
    monkeypatch.setattr(ytmusic, "_switcher_channels",
                        lambda cookie, ua=None: [])

    def factory(headers):
        au = int(headers["x-goog-authuser"])
        if au == 0:
            return _ProbeClient({"name": "roman"}, 4)
        if au == 1:
            return _ProbeClient({"name": "lnlydrvr"}, 77)
        raise RuntimeError

    cands = ytmusic.browser_accounts("chrome", client_factory=factory)
    assert cands[0]["authuser"] == 1
    assert cands[0]["account"]["name"] == "lnlydrvr"


def test_browser_accounts_includes_brand_channel(tmp_path, monkeypatch):
    monkeypatch.setattr(ytmusic, "_read_browser_cookies",
                        lambda browser, profile=None: _jar(
                            (".music.youtube.com", "__Secure-3PAPISID", "p3")))
    monkeypatch.setattr(ytmusic, "_switcher_channels",
                        lambda cookie, ua=None: [
                            {"account": "Roman Kolosov", "handle": "@roman",
                             "photo_url": "pic", "page_id": None, "session": 0},
                            {"account": "lnlydrvr", "handle": "@lnlydrvr",
                             "photo_url": "pic2", "page_id": "112725185991379222784",
                             "session": None},
                        ])

    def factory(headers):
        au = int(headers["x-goog-authuser"])
        page = headers.get("x-goog-pageid")
        if au == 0 and not page:
            return _ProbeClient({"name": "Roman Kolosov"}, 3)
        if au == 0 and page == "112725185991379222784":
            return _ProbeClient({"name": "lnlydrvr"}, 77)
        raise RuntimeError

    cands = ytmusic.browser_accounts("chrome", client_factory=factory)
    brand = [c for c in cands if c.get("page_id")]
    assert len(brand) == 1
    assert brand[0]["account"]["name"] == "lnlydrvr"
    assert brand[0]["page_id"] == "112725185991379222784"
    assert brand[0]["likes"] == 77
    assert cands[0] is brand[0], "страничный канал с максимумом лайков — первым"


def test_switcher_channels_parses_brand_page_id(monkeypatch):
    def account_item(name, handle, photo, tokens):
        return {"accountItem": {
            "accountName": {"simpleText": name},
            "channelHandle": {"simpleText": handle},
            "accountPhoto": {"thumbnails": [{"url": photo}]},
            "serviceEndpoint": {"selectActiveIdentityEndpoint": {
                "supportedTokens": tokens}},
        }}

    def mk(contents):
        return {"code": "SUCCESS", "data": {"actions": [
            {"getMultiPageMenuAction": {"menu": {
                "multiPageMenuRenderer": {"sections": [
                    {"accountSectionListRenderer": {"contents": [
                        {"accountItemSectionRenderer": {"contents": contents}},
                    ]}},
                ]}}}}]}}

    data = mk([
        account_item("Roman Kolosov", "@roman", "pic1",
                     [{"sessionIndexToken": {"sessionIndex": 0}}]),
        account_item("lnlydrvr", "@lnlydrvr", "pic2",
                     [{"pageIdToken": {"pageId": "112725185991379222784"}}]),
    ])
    monkeypatch.setattr(ytmusic, "_youtube_json_get",
                        lambda url, cookie, ua="": data)
    chans = ytmusic._switcher_channels("c")
    assert chans[0]["account"] == "Roman Kolosov"
    assert chans[0]["page_id"] is None
    assert chans[0]["session"] == 0
    brand = chans[1]
    assert brand["account"] == "lnlydrvr"
    assert brand["handle"] == "@lnlydrvr"
    assert brand["page_id"] == "112725185991379222784"


def test_switcher_channels_breaks_on_garbage(monkeypatch):
    def boom(url, cookie, ua=""):
        raise OSError("no such host")
    monkeypatch.setattr(ytmusic, "_youtube_json_get", boom)
    with pytest.raises(OSError):
        ytmusic._switcher_channels("c")

    monkeypatch.setattr(ytmusic, "_youtube_json_get",
                        lambda url, cookie, ua="": {"data": {"actions": []}})
    assert ytmusic._switcher_channels("c") == []


def test_brand_channels_swallows_switcher_errors(monkeypatch):
    monkeypatch.setattr(ytmusic, "_switcher_channels",
                        lambda cookie, ua=None: (_ for _ in ()).throw(OSError))
    assert ytmusic._brand_channels("c", 0) == []


def test_browser_accounts_no_session(tmp_path, monkeypatch):
    monkeypatch.setattr(ytmusic, "_read_browser_cookies",
                        lambda browser, profile=None: _jar())
    with pytest.raises(ytmusic.YTMusicError, match="PAPISID"):
        ytmusic.browser_accounts("chrome")


def test_extract_browser_headers_forced_authuser(isolated_home, monkeypatch):
    jar = _jar((".music.youtube.com", "__Secure-3PAPISID", "p3"))
    monkeypatch.setattr(ytmusic, "_read_browser_cookies",
                        lambda browser, profile=None: jar)
    written = {}

    def fake_setup(headers_raw=None, filepath=None):
        written["raw"] = headers_raw
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        Path(filepath).write_text(json.dumps(
            {"cookie": "x", "x-goog-authuser": "2"}), encoding="utf-8")

    monkeypatch.setattr(ytmusicapi, "setup", fake_setup)

    def factory(headers):
        assert headers["x-goog-authuser"] == "2"
        return _ProbeClient({"name": "roman"}, 3)

    res = ytmusic.extract_browser_headers("chrome", authuser=2,
                                          client_factory=factory)
    assert res["authuser"] == 2
    assert res["account"]["name"] == "roman"
    assert "X-Goog-AuthUser: 2" in written["raw"]


def test_extract_browser_headers_with_page_id(isolated_home, monkeypatch):
    jar = _jar((".music.youtube.com", "__Secure-3PAPISID", "p3"))
    monkeypatch.setattr(ytmusic, "_read_browser_cookies",
                        lambda browser, profile=None: jar)
    written = {}

    def fake_setup(headers_raw=None, filepath=None):
        written["raw"] = headers_raw
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        Path(filepath).write_text(json.dumps(
            {"cookie": "x", "x-goog-authuser": "0", "x-goog-pageid": "42"}),
            encoding="utf-8")

    monkeypatch.setattr(ytmusicapi, "setup", fake_setup)

    def factory(headers):
        return _ProbeClient({"name": "lnlydrvr"}, 77)

    res = ytmusic.extract_browser_headers("chrome", page_id="103430112380821682108",
                                          client_factory=factory)
    assert res["page_id"] == "103430112380821682108"
    assert "X-Goog-PageId: 103430112380821682108" in written["raw"]


def test_extract_browser_headers_forced_authuser_invalid(isolated_home, monkeypatch):
    jar = _jar((".music.youtube.com", "__Secure-3PAPISID", "p3"))
    monkeypatch.setattr(ytmusic, "_read_browser_cookies",
                        lambda browser, profile=None: jar)
    with pytest.raises(ytmusic.YTMusicError, match="authuser"):
        ytmusic.extract_browser_headers(
            "chrome", authuser=3,
            client_factory=lambda h: (_ for _ in ()).throw(RuntimeError))


def test_extract_browser_headers_forced_authuser_bad_value(isolated_home, monkeypatch):
    monkeypatch.setattr(ytmusic, "_read_browser_cookies",
                        lambda browser, profile=None: _jar(
                            (".music.youtube.com", "__Secure-3PAPISID", "p3")))
    with pytest.raises(ytmusic.YTMusicError, match="диапазон"):
        ytmusic.extract_browser_headers(
            "chrome", authuser=99,
            client_factory=lambda h: _ProbeClient({"name": "a"}, 1))


def test_extract_browser_headers_writes_auth(isolated_home, monkeypatch):
    jar = _jar(
        (".music.youtube.com", "__Secure-3PAPISID", "p3"),
        (".music.youtube.com", "SID", "sid"),
    )
    monkeypatch.setattr(ytmusic, "_read_browser_cookies",
                        lambda browser, profile=None: jar)
    written = {}

    def fake_setup(headers_raw=None, filepath=None):
        written["raw"] = headers_raw
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        Path(filepath).write_text(json.dumps(
            {"cookie": "x", "x-goog-authuser": "0"}), encoding="utf-8")

    monkeypatch.setattr(ytmusicapi, "setup", fake_setup)

    def factory(headers):
        assert headers["x-goog-authuser"] == "0"
        return _ProbeClient({"name": "lnlydrvr"}, 7)

    res = ytmusic.extract_browser_headers("chrome", client_factory=factory)
    assert res["authuser"] == 0
    assert res["account"]["name"] == "lnlydrvr"
    assert res["browser"] == "chrome"
    assert written["raw"], "записали заголовки в файл авторизации"
    assert "__Secure-3PAPISID=p3" in written["raw"]
    assert "X-Goog-AuthUser: 0" in written["raw"]
    # без authorization-заголовка ytmusicapi принимает файл за OAuth JSON
    assert "SAPISIDHASH" in written["raw"]
    assert ytmusic.connected() is True


def test_extract_browser_headers_no_session(isolated_home, monkeypatch):
    monkeypatch.setattr(ytmusic, "_read_browser_cookies",
                        lambda browser, profile=None: _jar())
    with pytest.raises(ytmusic.YTMusicError, match="PAPISID"):
        ytmusic.extract_browser_headers("chrome")


def test_extract_browser_headers_read_error(monkeypatch):
    monkeypatch.setattr(ytmusic, "_read_browser_cookies",
                        lambda browser, profile=None:
                        (_ for _ in ()).throw(OSError("no keychain")))
    with pytest.raises(ytmusic.YTMusicError, match="(?i)не прочитать"):
        ytmusic.extract_browser_headers("chrome")


def _zen_profile_dir(tmp_path, monkeypatch) -> Path:
    import sqlite3

    root = tmp_path / "AppSupport" / "zen" / "Profiles"
    prof = root / "abcd1234.Default (release)"
    prof.mkdir(parents=True)
    con = sqlite3.connect(prof / "cookies.sqlite")
    con.execute(
        "CREATE TABLE moz_cookies (host TEXT, name TEXT, value TEXT)")
    con.executemany(
        "INSERT INTO moz_cookies (host, name, value) VALUES (?, ?, ?)",
        [
            (".music.youtube.com", "__Secure-3PAPISID", "zen_p3"),
            (".music.youtube.com", "SID", "zen_sid"),
            (".google.com", "NID", "nid"),
            ("example.com", "tracking", "x"),
        ])
    con.commit()
    con.close()
    monkeypatch.setattr(ytmusic, "_zen_profile_dirs", lambda: [prof])
    return prof


def test_available_browsers_detects_zen(tmp_path, monkeypatch):
    _zen_profile_dir(tmp_path, monkeypatch)
    found = {b["name"]: b["profiles"] for b in ytmusic.available_browsers()}
    assert found.get("zen") == ["abcd1234.Default (release)"]


def test_extract_browser_headers_from_zen(tmp_path, monkeypatch, isolated_home):
    _zen_profile_dir(tmp_path, monkeypatch)
    written = {}

    def fake_setup(headers_raw=None, filepath=None):
        written["raw"] = headers_raw
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        Path(filepath).write_text(
            json.dumps({"cookie": "x", "x-goog-authuser": "0"}), encoding="utf-8")

    monkeypatch.setattr(ytmusicapi, "setup", fake_setup)
    monkeypatch.setattr(
        ytmusic, "_probe_authuser",
        lambda cookie, client_factory=None: (0, {"name": "lnlydrvr", "handle": "@lnlydrvr"}))

    res = ytmusic.extract_browser_headers("zen")
    assert res["browser"] == "zen"
    assert res["account"]["name"] == "lnlydrvr"
    assert written["raw"]
    assert "__Secure-3PAPISID=zen_p3" in written["raw"]
    assert "SID=zen_sid" in written["raw"]
    assert "SAPISIDHASH" in written["raw"]
    assert ytmusic.connected() is True


def test_zen_no_profile_dir(tmp_path, monkeypatch):
    roots = tmp_path / "AppSupport"
    roots.mkdir()
    monkeypatch.setattr(ytmusic, "_browser_roots_dir", lambda: roots)
    with pytest.raises(ytmusic.YTMusicError, match="(?i)zen"):
        ytmusic._read_browser_cookies("zen")


def test_zen_no_cookies_file(tmp_path, monkeypatch):
    prof = tmp_path / "Profiles" / "abc.default"
    prof.mkdir(parents=True)
    monkeypatch.setattr(ytmusic, "_zen_profile_dirs", lambda: [prof])
    with pytest.raises(ytmusic.YTMusicError, match="cookies.sqlite"):
        ytmusic._read_browser_cookies("zen")


# --- OAuth device flow ---------------------------------------------------


class FakeCreds:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.polls = 0

    def get_code(self):
        return {
            "verification_url": "https://example.com/verify",
            "user_code": "ABC-123",
            "device_code": "dc1",
            "interval": 1,
            "expires_in": 3600,
        }

    def token_from_code(self, device_code):
        self.polls += 1
        if self.polls < 2:
            return {"error": "authorization_pending"}
        return {
            "access_token": "at", "refresh_token": "rt",
            "expires_in": 3600, "scope": "youtube",
            "token_type": "Bearer",
        }


class FakeToken:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.path = None

    def update(self, raw):
        self.raw = raw

    @property
    def local_cache(self):
        return self.path

    @local_cache.setter
    def local_cache(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # как RefreshingToken.store_token(): только поля токена, без client_id/secret
        self.path.write_text(json.dumps({
            "access_token": "at", "refresh_token": "rt",
            "expires_at": 1, "expires_in": 3600,
            "scope": "youtube", "token_type": "Bearer",
        }), encoding="utf-8")


def test_oauth_authorize_ok(isolated_home, monkeypatch):
    monkeypatch.setattr(ytmusicapi, "OAuthCredentials", FakeCreds)
    monkeypatch.setattr("ytmusicapi.auth.oauth.token.RefreshingToken", FakeToken)
    urls = []
    opened = []
    monkeypatch.setattr(ytmusic, "webbrowser",
                        SimpleNamespace(open=lambda u: opened.append(u)))
    ytmusic.oauth_authorize(
        "cid", "sec", on_pending=lambda u: urls.append(u), open_browser=True)
    assert urls and urls[0].startswith("https://example.com/verify")
    assert opened == urls, "браузер должен открыть ссылку подтверждения"
    assert ytmusic.connected() and ytmusic.auth_mode() == "oauth"
    data = ytmusic.read_auth_data()
    assert data["access_token"] == "at"
    # для перезагрузки токена должны сохраниться клиентские кредакты
    assert data["client_id"] == "cid"
    assert data["client_secret"] == "sec"


def test_oauth_authorize_timeout(isolated_home, monkeypatch):
    class Never(FakeCreds):
        def token_from_code(self, device_code):
            self.polls += 1
            return {"error": "authorization_pending"}

    monkeypatch.setattr(ytmusicapi, "OAuthCredentials", Never)
    monkeypatch.setattr("ytmusicapi.auth.oauth.token.RefreshingToken", FakeToken)
    started = time.monotonic()
    with pytest.raises(ytmusic.YTMusicError) as exc:
        ytmusic.oauth_authorize("cid", "sec", timeout=0.3, open_browser=False)
    assert "дождались" in str(exc.value)
    assert time.monotonic() - started < 5, "таймаут не должен быть долгим"


def test_oauth_authorize_bad_creds(isolated_home, monkeypatch):
    class BadCreds:
        def get_code(self):
            raise ValueError("401 Unauthorized")

    monkeypatch.setattr(ytmusicapi, "OAuthCredentials", BadCreds)
    with pytest.raises(ytmusic.YTMusicError) as exc:
        ytmusic.oauth_authorize("idx", "sec", open_browser=False)
    assert "OAuth" in str(exc.value)


# --- Дедуп по библиотеке --------------------------------------------------


def _rec(artist="", title="", path=""):
    return SimpleNamespace(artist=artist, title=title,
                           path=Path(path) if path else None)


def test_track_key_normalizes_punctuation():
    keys = {
        ytmusic.track_key(ytmusic.YTMTrack(
            video_id="v", title="The End!", artist="The Doors — 1967")),
        ytmusic.track_key(ytmusic.YTMTrack(
            video_id="v", title="the end", artist="The Doors 1967")),
    }
    assert len(keys) == 1, "пунктуация и регистр не должны различать ключи"


def test_library_keys_from_records():
    records = [
        _rec("Pink Floyd", "Shine On"),
        _rec("PINK FLOYD", "shine on you crazy diamond"),
        _rec("", "", "/some/path/Inbox/123.mp3"),
    ]
    keys = ytmusic.library_keys(records)
    assert ("pinkfloyd", "shineon") in keys
    assert ("pinkfloyd", "shineonyoucrazydiamond") in keys


def test_track_in_library_matches_variants():
    keys = ytmusic.library_keys([_rec("The Beatles", "Yesterday")])
    hits = ytmusic.YTMTrack(video_id="v", title="Yesterday!",
                            artist="The Beatles")
    assert ytmusic.track_in_library(hits, keys) is True


def test_track_in_library_miss_and_empty():
    keys = ytmusic.library_keys([_rec("Beatles", "Yesterday")])
    miss = ytmusic.YTMTrack(video_id="v", title="Something", artist="Beatles")
    assert ytmusic.track_in_library(miss, keys) is False
    assert ytmusic.track_in_library(miss, set()) is False


def test_track_key_distinguishes_features():
    """Дедуп с библиотекой фичи не игнорирует: «Good Life» и
    «Good Life (feat. T-Pain)» — разные треки."""
    no_feat = ytmusic.track_key(ytmusic.YTMTrack(
        video_id="v", title="Good Life", artist="Kanye West"))
    for title in ("Good Life (feat. T-Pain)",
                  "Good Life (ft. T-Pain)",
                  "Good Life (featuring T-Pain)",
                  "Good Life (with T-Pain)",
                  "Good Life feat. T-Pain",
                  "Good Life - feat. T-Pain"):
        assert ytmusic.track_key(ytmusic.YTMTrack(
            video_id="v", title=title, artist="Kanye West")) != no_feat


def test_norm_title_strips_features():
    """norm_title (рекомендации) фичи по-прежнему игнорирует."""
    assert ytmusic.norm_title("Good Life (feat. T-Pain)") == \
        ytmusic.norm_title("Good Life")
    assert ytmusic.norm_title("Good Life feat. T-Pain") == \
        ytmusic.norm_title("Good Life")


def test_track_title_with_is_part_of_title():
    keys = ytmusic.library_keys([
        _rec("Whitney Houston", "I Wanna Dance with Somebody")])
    t = ytmusic.YTMTrack(video_id="v", title="I Wanna Dance with Somebody",
                         artist="Whitney Houston")
    assert ytmusic.track_in_library(t, keys) is True
    assert ytmusic.track_key(t)[1] == "iwannadancewithsomebody"


def test_track_in_library_counts_features_e2e():
    keys = ytmusic.library_keys([_rec("Kanye West", "Good Life")])
    for title in ("Good Life (feat. T-Pain)", "Good Life feat. T-Pain"):
        yt = ytmusic.YTMTrack(video_id="v", title=title, artist="Kanye West")
        assert ytmusic.track_in_library(yt, keys) is False


def test_library_keys_path_stem_fallback():
    keys = ytmusic.library_keys([
        _rec("A", "", path="/lib/A/song_name.flac"),
        _rec("B", "Real Title", path="/lib/B/other.flac"),
    ])
    assert ("a", "songname") in keys, "title из имени файла, если тега нет"
    assert ("b", "realtitle") in keys


def test_norm_transliterates_cyrillic():
    assert ytmusic.norm("Валентин Стрыкало") == "valentinstrykalo"
    assert ytmusic.norm("Valentin Strykalo") == "valentinstrykalo"
    assert ytmusic.norm("The Doors — The End") == "thedoorstheend"
    assert ytmusic.norm("Съешь ещё Щец") == "sesheshcheshchets"


def test_normalized_keys_match_across_scripts():
    cyr = ytmusic.track_key(ytmusic.YTMTrack(
        video_id="v", title="Что случилось?", artist="Валентин Стрыкало"))
    lat = ytmusic.track_key(ytmusic.YTMTrack(
        video_id="v", title="Что случилось?", artist="Valentin Strykalo"))
    assert cyr == lat, "кириллица и латиница дают одинаковый ключ"


def test_artist_counts_merge_scripts():
    records = [
        _rec("Валентин Стрыкало", "T1"),
        _rec("Valentin Strykalo", "T2"),
    ]
    counts = ytmusic.library_artist_counts(records)
    assert counts["valentinstrykalo"] == 2, "обе записи сливаются в один ключ"


def test_album_counts_merge_scripts():
    records = [
        SimpleNamespace(artist="Валентин Стрыкало", album="Развлечение"),
        SimpleNamespace(artist="Valentin Strykalo", album="Развлечение"),
    ]
    counts = ytmusic.library_album_counts(records)
    assert counts[("razvlechenie", "valentinstrykalo")] == 2