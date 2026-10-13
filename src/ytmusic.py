"""Доступ к YouTube Music через ytmusicapi.

Персональная сессия пользователя хранится в файле авторизации (по умолчанию
``~/.config/music-lib/ytmusic_auth.json``). Файл создаётся одним из двух
способов, и в обоих случаях содержимое туда кладёт сам пользователь:

* вставка заголовков запроса из браузера — аналог cookies.txt, но для
  Music API (``setup(headers_raw=...)``);
* OAuth device flow — client_id/client_secret приложения YouTube Data API,
  подтверждение в браузере, токен с автообновлением.

Серверного логина по паролю нет. Модуль тянет только вставленные данные,
поэтому файл безопасен локально. Все сетевые обращения идут через ленивый
клиент :class:`ytmusicapi.YTMusic`, закэшированный по пути+mtime файла.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

#: Кэш клиента: ключ (путь файла, mtime) → экземпляр YTMusic.
_CLIENT_CACHE: dict[tuple, Any] = {}


class YTMusicError(Exception):
    """Ошибка интеграции с YouTube Music (авторизация или запрос)."""


@dataclass
class YTMTrack:
    """Одна песня из YouTube Music (для скачивания и тегов).

    Нормализованное представление — поля остаются пустыми, если источник
    их не отдал (альбом, год, номер трека и т.п.).
    """

    video_id: str
    title: str
    artist: str
    album: str = ""
    year: int | None = None
    track_number: int | None = None
    cover_url: str = ""
    duration: int | None = None
    video_type: str = ""
    feedback_token: str = ""
    """Токен «добавить в библиотеку» из поиска песен (для edit_song_library_status)."""


def pick_thumbnail(thumbnails: Any, max_width: int = 296) -> str:
    """Лучший URL обложки из ответа ytmusicapi.

    ``thumbnails`` приходит списком ``{"url", "width", "height"}`` (иногда
    одиночным объектом). Берётся самая крупная превью шириной ``<= max_width``;
    если все больше порога — самая маленькая. Так не тянем гигантские картинки.
    """
    if isinstance(thumbnails, dict):
        thumbnails = [thumbnails]
    if not isinstance(thumbnails, list):
        return ""
    entries: list[tuple[int, str]] = []
    for item in thumbnails:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not url:
            continue
        try:
            width = int(item.get("width"))
        except (TypeError, ValueError):
            width = 0
        entries.append((width, str(url)))
    if not entries:
        return ""
    within = sorted((w, u) for (w, u) in entries if 0 < w <= max_width)
    if within:
        return within[-1][1]
    over = sorted((w, u) for (w, u) in entries if w > max_width)
    if over:
        return over[0][1]
    return entries[-1][1]


def track_from_dict(raw: Any) -> YTMTrack:
    """Нормализовать элемент в YTMTrack.

    Принимает и сырые ответы ytmusicapi (``videoId``/``trackNumber``), и уже
    сериализованные словари экрана (``video_id``/``track_number``).
    """
    if not isinstance(raw, dict):
        raw = {}
    video_id = str(raw.get("videoId") or raw.get("video_id") or "")
    title = str(raw.get("title") or "").strip()

    artist = ""
    artists = raw.get("artists")
    if isinstance(artists, list):
        names = [
            str(a.get("name") or "").strip()
            for a in artists if isinstance(a, dict)
        ]
        artist = ", ".join(n for n in names if n)
    elif isinstance(artists, str):
        artist = artists.strip()
    artist = artist or str(raw.get("artist") or "").strip() or "Неизвестный исполнитель"

    album = ""
    album_raw = raw.get("album")
    if isinstance(album_raw, dict):
        album = str(album_raw.get("name") or "").strip()
    elif isinstance(album_raw, str):
        album = album_raw.strip()

    def _optional_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return YTMTrack(
        video_id=video_id,
        title=title,
        artist=artist,
        album=album,
        year=_optional_int(raw.get("year")),
        track_number=_optional_int(raw.get("trackNumber") or raw.get("track_number")),
        cover_url=(pick_thumbnail(raw.get("thumbnails"))
                   or pick_thumbnail(raw.get("thumbnail"))
                   or str(raw.get("cover_url") or "")),
        duration=_optional_int(raw.get("duration")),
        video_type=str(raw.get("videoType") or raw.get("video_type") or ""),
        feedback_token=_feedback_token_add(raw),
    )


def _feedback_token_add(raw: dict[str, Any]) -> str:
    """Достать токен «добавить в библиотеку» из сырого результата поиска.

    Поиск песен отдаёт ``feedbackTokens: {"add": ..., "remove": ...}``
    (реже плоскую форму ``feedbackTokenAdd``).
    """
    tokens = raw.get("feedbackTokens")
    if isinstance(tokens, dict):
        return str(tokens.get("add") or "").strip()
    return str(raw.get("feedbackTokenAdd") or "").strip()


_OAUTH_MARKERS = ("access_token", "refresh_token", "client_id")


def auth_mode_from_data(data: Any) -> str:
    """Тип файла авторизации: ``oauth``, ``browser`` или пустая строка."""
    if not isinstance(data, dict):
        return ""
    if all(data.get(key) for key in _OAUTH_MARKERS):
        return "oauth"
    if any(key.lower() in ("authorization", "cookie") for key in data):
        return "browser"
    return ""


def _err_text(error: Exception) -> str:
    """Пригодный для показа текст ошибки запроса к ytmusicapi."""
    msg = " ".join(str(a) for a in error.args) if getattr(error, "args", None) else ""
    return (msg or type(error).__name__).strip() or "Ошибка запроса к YouTube Music"


# --- Путь к файлу авторизации -----------------------------------------


def get_auth_file() -> Path:
    """Путь к файлу авторизации (из конфига или дефолт)."""
    from .config import get_ytmusic_auth_file

    return get_ytmusic_auth_file()


def read_auth_data() -> dict | None:
    """Содержимое файла авторизации как dict, или None при ошибке чтения."""
    try:
        with open(get_auth_file(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def auth_mode() -> str:
    """Чем авторизованы: ``oauth``, ``browser`` или пустая строка."""
    return auth_mode_from_data(read_auth_data())


def connected() -> bool:
    """Есть ли сохранённый и распознанный файл авторизации."""
    return bool(auth_mode())


def clear_auth() -> None:
    """Удалить файл авторизации и сбросить кэш клиента."""
    try:
        get_auth_file().unlink(missing_ok=True)
    except OSError:
        pass
    invalidate_client()


# --- Клиент ------------------------------------------------------------


def invalidate_client() -> None:
    """Сбросить кэш клиента (после записи/удаления файла авторизации)."""
    _CLIENT_CACHE.clear()


def _client_key() -> tuple | None:
    path = get_auth_file()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    return (str(path), mtime)


def get_client() -> Any:
    """Ленивый клиент ytmusicapi (кэш по пути+mtime файла).

    OAuth-файл требует передачи ``oauth_credentials`` (client_id/client_secret
    дописываются при авторизации); BROWSER-файл должен содержать заголовок
    ``authorization`` с маркером ``SAPISIDHASH``, иначе ytmusicapi примет его
    за OAuth JSON.

    Returns:
        :class:`ytmusicapi.YTMusic` или None, если авторизации нет.

    Raises:
        YTMusicError: OAuth-файл устарел (нет client_id/client_secret).
    """
    if not connected():
        return None
    key = _client_key()
    client = _CLIENT_CACHE.get(key) if key else None
    if client is None:
        from ytmusicapi import OAuthCredentials, YTMusic

        data = read_auth_data()
        auth_path = str(get_auth_file())
        if auth_mode_from_data(data) == "oauth":
            cid = (data or {}).get("client_id")
            secret = (data or {}).get("client_secret")
            if not cid or not secret:
                raise YTMusicError(
                    "OAuth-файл не содержит client_id/client_secret — пройдите "
                    "OAuth-настройку заново в разделе «Настройки»")
            client = YTMusic(auth=auth_path,
                             oauth_credentials=OAuthCredentials(cid, secret))
        else:
            client = YTMusic(auth=auth_path)
        if key:
            _CLIENT_CACHE[key] = client
    return client


def require_client() -> Any:
    """Клиент ytmusicapi или :class:`YTMusicError`, если не подключены."""
    client = get_client()
    if client is None:
        raise YTMusicError(
            "YouTube Music не подключён: настройте вход в разделе «Настройки»")
    return client


def account_info() -> dict:
    """Информация о подключённом аккаунте ({} без авторизации).

    Нормализует ключи ytmusicapi (``accountName``/``channelHandle``/
    ``accountPhotoUrl``) в ``name``/``handle``/``photo_url`` для UI.

    Raises:
        YTMusicError: при ошибке запроса (просроченные cookies и т.п.).
    """
    client = get_client()
    if client is None:
        return {}
    try:
        raw = client.get_account_info()
    except Exception as e:
        raise YTMusicError(_err_text(e)) from e
    return _normalize_account(raw)


# --- Авторизация: заголовки браузера ----------------------------------


def validate_browser_headers(text: str) -> str | None:
    """Проверить вставленные заголовки запроса. Возвращает текст ошибки или None.

    Требования минимальные (как у ``ytmusicapi.setup``): непустой текст и
    обязательные заголовки ``Cookie`` и ``X-Goog-AuthUser``.
    """
    if not text or not text.strip():
        return "Заголовки пусты"
    if len(text) > 1_000_000:
        return "Заголовки больше 1 МБ"
    keys = [
        line.split(":")[0].strip().lower()
        for line in text.splitlines()
        if ":" in line
    ]
    if not keys:
        return "Не похоже на заголовки (нужен формат «Заголовок: значение»)"
    for need in ("cookie", "x-goog-authuser"):
        if need not in keys:
            return (f"Нет обязательного заголовка «{need}». Скопируйте запрос к "
                    "https://music.youtube.com из DevTools: Network → "
                    "GET /browse → Request Headers")
    return None


def write_browser_auth(headers_raw: str) -> None:
    """Сохранить файл авторизации из вставленных заголовков браузера.

    Raises:
        YTMusicError: заголовки не прошли проверку или не сохранились.
    """
    error = validate_browser_headers(headers_raw)
    if error:
        raise YTMusicError(error)
    path = get_auth_file()
    try:
        from ytmusicapi import setup

        if not headers_raw.endswith("\n"):
            headers_raw += "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        setup(headers_raw=headers_raw, filepath=str(path))
    except Exception as e:
        raise YTMusicError(f"Ошибка сохранения авторизации: {_err_text(e)}") from e
    invalidate_client()


# --- Извлечение кук из браузера (через yt-dlp) -------------------------

#: User-Agent и Origin для сессии, собранной из кук браузера.
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
_BROWSER_ORIGIN = "https://music.youtube.com"
_BROWSER_MAX_AUTHUSER = 5

#: Эндпоинт листинга каналов аккаунта (личный + страничные/brand Google Pages).
_YOUTUBE_ORIGIN = "https://www.youtube.com"
_YOUTUBE_SWITCHER_URL = _YOUTUBE_ORIGIN + "/getAccountSwitcherEndpoint"

#: Относительные пути к профилям Chromium-браузеров.
_BROWSER_ROOTS = {
    "chrome": "Google/Chrome",
    "chromium": "Chromium",
    "edge": "Microsoft Edge",
    "brave": "BraveSoftware/Brave-Browser",
    "vivaldi": "Vivaldi",
    "opera": "com.operasoftware.Opera",
    "whale": "Naver/Naver Whale",
}

#: Zen — форк Firefox: профили в <root>/zen/Profiles/*.profile, куки в cookies.sqlite.
_ZEN_ROOT = "zen"


def _browser_roots_dir() -> Path:
    """Корень, где лежат профили браузеров (macOS: ~/Library/Application Support)."""
    import sys

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path.home() / ".config"


def available_browsers() -> list[dict]:
    """Доступные для чтения браузеры: ``[{"name", "profiles"}]``."""
    roots = _browser_roots_dir()
    out: list[dict] = []
    for name, rel in _BROWSER_ROOTS.items():
        prof_root = roots / rel
        if not prof_root.is_dir():
            continue
        profiles = [
            d.name for d in sorted(prof_root.iterdir())
            if d.is_dir() and (d.name == "Default" or d.name.startswith("Profile "))
        ]
        out.append({"name": name, "profiles": profiles or ["Default"]})
    zen_dirs = _zen_profile_dirs()
    if zen_dirs:
        out.append({"name": "zen", "profiles": [d.name for d in zen_dirs]})
    return out


def _zen_profile_dirs() -> list:
    """Каталоги профилей Zen: ``<root>/zen/Profiles/*.profile``."""
    prof_root = _browser_roots_dir() / _ZEN_ROOT / "Profiles"
    if not prof_root.is_dir():
        return []
    return sorted(d for d in prof_root.iterdir() if d.is_dir())


def _zen_profile_dir(profile: str | None = None) -> Path:
    dims = _zen_profile_dirs()
    if not dims:
        raise YTMusicError(
            f"Не найден профиль Zen (~/Library/Application Support/{_ZEN_ROOT}/Profiles)")
    for d in dims:
        if not profile or d.name == profile:
            return d
    raise YTMusicError(f"Профиль Zen «{profile}» не найден")


def _read_browser_cookies(browser: str, profile: str | None = None):
    """Куки профиля браузера. Chromium читается через yt-dlp (Keychain),
    Zen — форк Firefox, куки читаем из cookies.sqlite напрямую."""
    if browser == "zen":
        return _read_firefox_cookies(_zen_profile_dir(profile), browser)

    from yt_dlp import cookies as ytdlp_cookies

    return ytdlp_cookies.extract_cookies_from_browser(browser, profile=profile)


def _read_firefox_cookies(profile_dir: Path, browser: str) -> list:
    """Куки из ``cookies.sqlite`` профиля Firefox-семейства (хост, имя, значение)."""
    db = profile_dir / "cookies.sqlite"
    if not db.is_file():
        raise YTMusicError(
            f"Профиль {browser} не содержит cookies.sqlite — войдите на "
            "music.youtube.com и запустите браузер хотя бы раз")
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True, timeout=3)
    except sqlite3.Error as exc:
        raise YTMusicError(f"Не открыть куки {browser}: {exc}") from exc
    try:
        rows = [
            SimpleNamespace(domain=str(host or ""), name=str(name), value=str(value or ""))
            for host, name, value in con.execute("SELECT host, name, value FROM moz_cookies")
            if name
        ]
    except sqlite3.Error as exc:
        raise YTMusicError(f"Не прочитать куки {browser}: {exc}") from exc
    finally:
        con.close()
    if not rows:
        raise YTMusicError(f"В профиле {browser} нет кук music.youtube.com")
    return rows


def _cookies_header(jar) -> str:
    """Cookie-заголовок для music.youtube.com из jar браузера.

    Берутся куки доменов, покрывающих music.youtube.com; при дублях по имени
    побеждает запись с самым конкретным доменом.
    """
    best: dict[str, tuple[int, str]] = {}
    for ck in jar:
        domain = str(getattr(ck, "domain", "") or "").lower().lstrip(".")
        if not (domain.endswith("youtube.com") or domain.endswith("google.com")):
            continue
        name = str(getattr(ck, "name", "") or "")
        value = str(getattr(ck, "value", "") or "")
        if not name:
            continue
        score = 2 if "music.youtube.com" in domain else (1 if domain.endswith("youtube.com") else 0)
        if score >= best.get(name, (-1, ""))[0]:
            best[name] = (score, value)
    return "; ".join(f"{n}={v}" for n, (_, v) in best.items())


def _normalize_account(raw: Any) -> dict:
    """Сырые данные аккаунта ytmusicapi → ``{name, handle, photo_url}``."""
    if not isinstance(raw, dict):
        return {}
    return {
        "name": str(raw.get("accountName") or raw.get("name") or ""),
        "handle": str(raw.get("channelHandle") or raw.get("handle") or ""),
        "photo_url": str(raw.get("accountPhotoUrl") or raw.get("photoUrl") or ""),
    }


def _make_auth_client(headers: dict):
    from ytmusicapi import YTMusic

    return YTMusic(auth=headers)


def _auth_payload(client) -> dict:
    try:
        return _normalize_account(client.get_account_info())
    except Exception:
        return {}


def _liked_count(client) -> int:
    try:
        data = client.get_liked_songs(limit=100)
        return int((data or {}).get("trackCount") or 0) if isinstance(data, dict) else 0
    except Exception:
        return 0


def _simple_text(value: Any) -> str:
    """``{simpleText}`` или склейка ``{runs:[{text}]}`` в Ютубовом style."""
    if not isinstance(value, dict):
        return ""
    st = value.get("simpleText")
    if st:
        return str(st)
    runs = value.get("runs") or []
    return "".join(str(r.get("text") or "") for r in runs if isinstance(r, dict))


def _photo_url(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    for thumb in value.get("thumbnails") or []:
        if isinstance(thumb, dict) and thumb.get("url"):
            return str(thumb["url"])
    return ""


def _youtube_json_get(url: str, cookie: str, ua: str = _BROWSER_UA) -> dict:
    """GET по кукам сессии (тот же набор, что у music.youtube.com)."""
    req = urllib.request.Request(url, headers={
        "Cookie": cookie,
        "User-Agent": ua,
        "Origin": _YOUTUBE_ORIGIN,
        "Referer": _YOUTUBE_ORIGIN + "/",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = resp.read().decode("utf-8", "replace")
    except Exception as e:
        raise YTMusicError(f"Не получить данные YouTube: {_err_text(e)}") from e
    if text.startswith(")]}'"):
        text = text[4:].lstrip()
    try:
        data = json.loads(text)
    except ValueError as e:
        raise YTMusicError(f"Не распознать ответ YouTube: {_err_text(e)}") from e
    return data if isinstance(data, dict) else {}


def _switcher_channels(cookie: str, ua: str | None = None) -> list[dict]:
    """Каналы аккаунта: ``[{account, handle, photo_url, page_id, session}]``.

    Личный профиль — без ``page_id``; страничные (brand) аккаунты Google Pages
    (``...@pages.plusgoogle.com``) — с ``page_id``, который и есть значение
    заголовка ``X-Goog-PageId``.
    """
    data = _youtube_json_get(_YOUTUBE_SWITCHER_URL, cookie, ua or _BROWSER_UA)
    payload = data.get("data") or {}
    if not isinstance(payload, dict):
        return []
    out: list[dict] = []
    for action in payload.get("actions") or []:
        menu = (action.get("getMultiPageMenuAction") or {}).get("menu") or {}
        renderer = menu.get("multiPageMenuRenderer") or {}
        for section in renderer.get("sections") or []:
            section_renderer = section.get("accountSectionListRenderer") or {}
            for content in section_renderer.get("contents") or []:
                items = (content.get("accountItemSectionRenderer") or {}).get("contents") or []
                for item in items:
                    acc = item.get("accountItem") or {}
                    row = {
                        "account": _simple_text(acc.get("accountName")) or "",
                        "handle": _simple_text(acc.get("channelHandle")) or "",
                        "photo_url": _photo_url(acc.get("accountPhoto")) or "",
                        "page_id": None,
                        "session": None,
                    }
                    select = (acc.get("serviceEndpoint") or {}).get("selectActiveIdentityEndpoint") or {}
                    for token in select.get("supportedTokens") or []:
                        pid = (token.get("pageIdToken") or {}).get("pageId")
                        sidx = (token.get("sessionIndexToken") or {}).get("sessionIndex")
                        if pid:
                            row["page_id"] = str(pid)
                        if sidx is not None:
                            try:
                                row["session"] = int(sidx)
                            except (TypeError, ValueError):
                                pass
                    if row["account"]:
                        out.append(row)
    out.sort(key=lambda r: (0 if not r["page_id"] else 1, str(r["account"] or "").lower()))
    return out


def _authuser_client(cookie: str, au: int, client_factory=None,
                     page_id: str | None = None):
    """Клиент ytmusicapi для конкретного ``X-Goog-AuthUser`` (и ``X-Goog-PageId``)."""
    make = client_factory or _make_auth_client
    headers: dict[str, str] = {
        "cookie": cookie,
        "x-goog-authuser": str(au),
        "origin": _BROWSER_ORIGIN,
        "authorization": "SAPISIDHASH 0_probe",  # пересчитывается каждый запрос
    }
    if page_id:
        headers["x-goog-pageid"] = page_id
    return make(headers)


def _authuser_candidates(cookie: str, client_factory=None) -> list[dict]:
    """Все распознанные аккаунты в куках: ``[{authuser, account, likes}]``.

    Отсортированы по числу лайков (больше — выше), при равенстве — младший
    authuser первым.
    """
    out: list[dict] = []
    for au in range(_BROWSER_MAX_AUTHUSER):
        try:
            client = _authuser_client(cookie, au, client_factory)
            liked = _liked_count(client)
            account = _auth_payload(client)
        except Exception:
            continue
        if account or liked:
            out.append({"authuser": au, "account": account, "likes": liked})
    out.sort(key=lambda c: (-c["likes"], c["authuser"]))
    return out


def _probe_authuser(cookie: str, client_factory=None) -> tuple[int, dict]:
    """Подобрать ``X-Goog-AuthUser`` под куки (0..N).

    Куки привязаны к аккаунту, поэтому рабочих авторизаций обычно одна-две.
    Выбираем профиль с наибольшим числом лайков; на равенстве — младший authuser.

    Returns:
        (authuser, account) — нормализованный аккаунт.

    Raises:
        YTMusicError: ни один профиль не распознан.
    """
    candidates = _authuser_candidates(cookie, client_factory)
    if not candidates:
        raise YTMusicError(
            "По кукам браузера не удалось определить аккаунт. Войдите на "
            "music.youtube.com (учётка lnlydrvr — аватар сверху-справа) и обновите страницу")
    top = candidates[0]
    return top["authuser"], top["account"]


def _cookie_for_browser(browser: str, profile: str | None = None) -> str:
    """Cookie-заголовок music.youtube.com из кук профиля браузера."""
    browser = str(browser or "").strip().lower()
    if not browser:
        raise YTMusicError("Не указан браузер")
    profile = str(profile).strip() if profile else None
    try:
        jar = _read_browser_cookies(browser, profile)
    except Exception as e:
        raise YTMusicError(f"Не прочитать куки {browser}: {_err_text(e)}") from e
    cookie = _cookies_header(jar)
    if "__Secure-3PAPISID" not in cookie:
        raise YTMusicError(
            "В куках браузера нет __Secure-3PAPISID: зайдите на music.youtube.com "
            "в этом браузере под нужным аккаунтом и обновите страницу")
    return cookie


def _brand_channels(cookie: str, au: int, client_factory=None) -> list[dict]:
    """Страничные (brand) каналы профиля ``au`` профиля.

    Returns:
        ``[{authuser, account, likes, page_id}]`` — с ``page_id`` из account
        switcher (эндпоинт работает с теми же куками). ``page_id`` и есть
        значение заголовка ``X-Goog-PageId``.
    """
    try:
        channels = _switcher_channels(cookie)
    except Exception:
        return []
    out: list[dict] = []
    for ch in channels:
        pid = ch["page_id"]
        if not pid:
            continue
        account = {"name": ch["account"], "handle": ch["handle"],
                   "photo_url": ch["photo_url"]}
        liked = 0
        try:
            client = _authuser_client(cookie, au, client_factory, page_id=pid)
            liked = _liked_count(client)
        except Exception:
            pass
        out.append({"authuser": au, "account": account, "likes": liked,
                    "page_id": pid})
    return out


def browser_accounts(browser: str, profile: str | None = None,
                     client_factory=None) -> list[dict]:
    """Аккаунты, распознанные в куках профиля браузера.

    Личные профили (:func:`_authuser_candidates`) плюс страничные (brand)
    каналы Google Pages — каждый с ``page_id`` для ``X-Goog-PageId``.

    Returns:
        ``[{authuser, account, likes, page_id?}]``, отсортировано по лайкам.
    """
    cookie = _cookie_for_browser(browser, profile)
    merged: list[dict] = []
    seen: set[tuple[int, str]] = set()
    for c in _authuser_candidates(cookie, client_factory=client_factory):
        merged.append(c)
        if c.get("page_id"):
            continue
        for b in _brand_channels(cookie, c["authuser"],
                                 client_factory=client_factory):
            key = (b["authuser"], str(b.get("page_id") or ""))
            if key in seen:
                continue
            seen.add(key)
            merged.append(b)
    merged.sort(key=lambda c: (-c["likes"], c["authuser"]))
    return merged


def extract_browser_headers(browser: str, profile: str | None = None,
                            authuser: int | None = None,
                            page_id: str | None = None,
                            client_factory=None) -> dict:
    """Извлечь авторизацию из кук браузера и сохранить файл авторизации.

    Шаги: чтение кук профиля (yt-dlp, macOS может спросить доступ к Keychain),
    сборка Cookie-заголовка для music.youtube.com, выбор ``X-Goog-AuthUser``:
    переданный ``authuser`` или подбор по лайкам (:func:`_probe_authuser`).

    ``page_id`` — ``X-Goog-PageId`` для страничных (brand) аккаунтов Google
    Pages (например ``...@pages.plusgoogle.com``). Только с этим заголовком
    ytmusicapi (который передаёт наши заголовки как есть) видит бренд-канал.

    Returns:
        Словарь ``{account, authuser, browser, profile}``.

    Raises:
        YTMusicError: браузер/профиль не найден, в куках нет ``__Secure-3PAPISID``
            или аккаунт не распознан.
    """
    cookie = _cookie_for_browser(browser, profile)
    browser = str(browser or "").strip().lower()
    profile = str(profile).strip() if profile else None
    page_id = str(page_id or "").strip() or None
    if authuser is not None:
        au = int(authuser)
        if au < 0 or au >= _BROWSER_MAX_AUTHUSER:
            raise YTMusicError(f"authuser {au} вне диапазона 0..{_BROWSER_MAX_AUTHUSER - 1}")
        liked, account = 0, {}
        try:
            client = _authuser_client(cookie, au, client_factory)
            liked = _liked_count(client)
            account = _auth_payload(client)
        except Exception:
            pass
        if not account and not liked:
            raise YTMusicError(
                f"Аккаунт authuser={au} не распознан по кукам браузера. "
                "Обновите music.youtube.com под нужной учёткой и повторите")
    else:
        au, account = _probe_authuser(cookie, client_factory=client_factory)
        liked = 0
    lines = [
        f"Cookie: {cookie}",
        f"X-Goog-AuthUser: {au}",
        f"Origin: {_BROWSER_ORIGIN}",
        f"User-Agent: {_BROWSER_UA}",
        "Authorization: SAPISIDHASH 0_probe",
    ]
    if page_id:
        lines.append(f"X-Goog-PageId: {page_id}")
    write_browser_auth("\n".join(lines) + "\n")
    return {"account": account, "authuser": au,
            "browser": browser, "profile": profile,
            "likes": liked, "page_id": page_id}


# --- Авторизация: OAuth device flow ------------------------------------


def oauth_authorize(client_id: str, client_secret: str,
                    on_pending: Callable[[str], None] | None = None,
                    open_browser: bool = True,
                    timeout: float = 600.0) -> None:
    """Прогнать OAuth device flow и сохранить токен в файл авторизации.

    Получает код устройства, открывает страницу подтверждения в браузере
    (если ``open_browser``), затем опрашивает сервер Google, пока пользователь
    не подтвердит доступ. ``on_pending`` получает ссылку подтверждения —
    сервисный слой показывает её пользователю (SSE).

    Raises:
        YTMusicError: OAuth не начался, пользователь не подтвердил за отведённое
            время или токен не сохранился.
    """
    from ytmusicapi import OAuthCredentials
    from ytmusicapi.auth.oauth.token import RefreshingToken

    try:
        creds = OAuthCredentials(client_id, client_secret)
        code = creds.get_code()
    except Exception as e:
        raise YTMusicError(f"Не удалось начать OAuth: {_err_text(e)}") from e

    device_code = str(code.get("device_code") or "")
    url = f"{code.get('verification_url')}?user_code={code.get('user_code')}"
    if not device_code or not url.strip("="):
        raise YTMusicError("OAuth: пустой код устройства от Google")
    if on_pending:
        on_pending(url)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    interval = max(2, int(code.get("interval") or 5))
    expires_in = max(60, int(code.get("expires_in") or 3600))
    deadline = time.monotonic() + min(timeout, expires_in - 60)

    raw: dict | None = None
    while time.monotonic() < deadline:
        try:
            candidate = creds.token_from_code(device_code)
        except Exception:
            candidate = None
        if isinstance(candidate, dict) and candidate.get("access_token") \
                and candidate.get("refresh_token"):
            raw = candidate
            break
        time.sleep(interval)

    if raw is None:
        raise YTMusicError(
            "OAuth: не дождались подтверждения в браузере (время вышло)")

    refresh_expires = raw.get("refresh_token_expires_in", raw.get("expires_in"))
    token = RefreshingToken(
        credentials=creds,
        access_token=raw["access_token"],
        refresh_token=raw["refresh_token"],
        scope=raw.get("scope", ""),
        token_type=raw.get("token_type", "Bearer"),
        expires_in=int(refresh_expires or 0),
    )
    token.update(raw)
    path = get_auth_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        token.local_cache = path
    except OSError as e:
        raise YTMusicError(f"OAuth: не сохранить токен: {e}") from e
    # Для перезагрузки токена ytmusicapi требует oauth_credentials —
    # храним client_id/client_secret рядом с токеном.
    try:
        with open(path, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
        if isinstance(saved, dict):
            saved["client_id"] = client_id
            saved["client_secret"] = client_secret
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(saved, fh, indent=True)
    except (OSError, ValueError) as e:
        raise YTMusicError(f"OAuth: не сохранить токен: {e}") from e
    invalidate_client()


# --- Запросы данных -----------------------------------------------------


def liked_songs(limit: int = 100) -> list[YTMTrack]:
    """Понравившиеся песни аккаунта (нормализованные)."""
    client = require_client()
    try:
        data = client.get_liked_songs(limit=limit)
    except Exception as e:
        raise YTMusicError(_err_text(e)) from e
    tracks = data.get("tracks") if isinstance(data, dict) else None
    return [track_from_dict(t) for t in tracks or []]


def library_albums(limit: int = 100) -> list[dict]:
    """Альбомы в библиотеке пользователя (сырые элементы ytmusicapi)."""
    client = require_client()
    try:
        return client.get_library_albums(limit=limit) or []
    except Exception as e:
        raise YTMusicError(_err_text(e)) from e


def get_album(browse_id: str) -> dict:
    """Полный альбом по browseId (с треклистом в ``tracks``)."""
    client = require_client()
    try:
        return client.get_album(browse_id) or {}
    except Exception as e:
        raise YTMusicError(_err_text(e)) from e


def library_playlists(limit: int = 100) -> list[dict]:
    """Плейлисты в библиотеке пользователя."""
    client = require_client()
    try:
        return client.get_library_playlists(limit=limit) or []
    except Exception as e:
        raise YTMusicError(_err_text(e)) from e


def library_artists(limit: int = 100) -> list[dict]:
    """Подписки/сохранённые исполнители в библиотеке пользователя."""
    client = require_client()
    try:
        return client.get_library_artists(limit=limit) or []
    except Exception as e:
        raise YTMusicError(_err_text(e)) from e


def get_playlist(playlist_id: str) -> dict:
    """Плейлист по ID (треки в ``tracks``)."""
    client = require_client()
    try:
        return client.get_playlist(playlist_id) or {}
    except Exception as e:
        raise YTMusicError(_err_text(e)) from e


def get_artist(browse_id: str) -> dict:
    """Исполнитель по browseId (``topSongs`` и ``albums`` в ответе)."""
    client = require_client()
    try:
        return client.get_artist(browse_id) or {}
    except Exception as e:
        raise YTMusicError(_err_text(e)) from e


def watch_playlist(video_id: str, limit: int = 25) -> list[YTMTrack]:
    """Радио/похожие треки для песни (radio по videoId)."""
    client = require_client()
    try:
        data = client.get_watch_playlist(videoId=video_id, limit=limit)
    except Exception as e:
        raise YTMusicError(_err_text(e)) from e
    tracks = data.get("tracks") if isinstance(data, dict) else None
    return [track_from_dict(t) for t in tracks or []]


def search_songs(query: str, limit: int = 10) -> list[YTMTrack]:
    """Поиск песен на YouTube Music (работает и с авторизацией, и без)."""
    client = get_client()
    if client is None:
        from ytmusicapi import YTMusic

        client = YTMusic()
    try:
        results = client.search(query=query, filter="songs", limit=limit)
    except Exception as e:
        raise YTMusicError(_err_text(e)) from e
    return [track_from_dict(t) for t in results or []]


# --- Дедуп по библиотеке -------------------------------------------------


ATV_TYPE = "MUSIC_VIDEO_TYPE_ATV"
"""Тип видео «Artist Topic» — авто-сгенерированная аудиоверсия (без клипа/цензуры)."""


def is_clip(track: YTMTrack) -> bool:
    """Клип ли это (не аудиоверсия Topic-канала).

    Пустой ``video_type`` считаем «не известно» → не клип (не мешаем скачивать).
    """
    return bool(track.video_type) and track.video_type != ATV_TYPE


def find_audio_version(track: YTMTrack, limit: int = 5) -> YTMTrack | None:
    """Найти аудиоверсию (Topic, без клипа) для трека иначе.

    Ищем в YouTube Music по исполнителю+названию и отдаём первую запись типа
    ``MUSIC_VIDEO_TYPE_ATV`` с совпадающим ключом. Возвращает трек с новым
    ``video_id`` (одноимённые каталог-поля сохраняются) или None.
    """
    if not track.video_id or not track.artist or not track.title:
        return None
    if track.video_type == ATV_TYPE:
        return track
    try:
        hits = search_songs(f"{track.artist} {track.title}".strip(), limit=limit)
    except Exception:
        return None
    key = _catalog_key(track)
    for hit in hits:
        if not hit.video_id or hit.video_type != ATV_TYPE:
            continue
        if _catalog_key(hit) != key:
            continue
        replaced = track_from_dict({
            "videoId": hit.video_id,
            "videoType": hit.video_type,
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "year": track.year,
            "trackNumber": track.track_number,
            "thumbnails": [{"url": track.cover_url}] if track.cover_url else None,
            "duration": track.duration,
        })
        return replaced
    return None


_CYR_TO_LAT = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
})


def _norm(value: str) -> str:
    """Нормализовать строку для сравнения: только буквы/цифры, без регистра.

    Убираются пробелы, пунктуация и типографские тире (em-dash и т.п.),
    чтобы ``The Doors — The End`` совпадал с ``the doors - the end!``.
    Кириллица транслитерируется в латиницу, чтобы локальная запись
    «Валентин Стрыкало» совпадала с подпиской YT Music «Valentin Strykalo».
    """
    s = (value or "").lower()
    return "".join(ch for ch in s.translate(_CYR_TO_LAT) if ch.isalnum())


def norm(value: str) -> str:
    """Публичный алиас :func:`_norm` для построения ключей вне модуля."""
    return _norm(value)


def norm_title(value: str) -> str:
    """Публичный алиас :func:`_norm_title` для сравнения названий вне модуля."""
    return _norm_title(value)


#: Фиче-маркеры: упоминания гостевых исполнителей, не меняющие название песни.
_FEATURE_PAREN_RE = re.compile(
    r"\([^)]*(?:feat\.?|ft\.?|featuring|with)\b[^)]*\)", flags=re.IGNORECASE
)
#: Инлайн-форма ``feat.`` допустима, а «with» — нет: «I Wanna Dance with
#: Somebody» почти наверняка не фича, а часть названия.
_FEATURE_INLINE_RE = re.compile(r"(?:feat\.?|ft\.?|featuring)\b", flags=re.IGNORECASE)


def _norm_title(value: str) -> str:
    """Нормализовать название, игнорируя фичи (feat./ft.).

    Используется для сопоставления версий внутри каталога YT Music
    (:func:`find_audio_version`) и в рекомендациях (публичный
    :func:`norm_title`); дедуп с библиотекой фичи не игнорирует.
    """
    s = value or ""
    s = _FEATURE_PAREN_RE.sub("", s)
    i = _FEATURE_INLINE_RE.search(s)
    if i:
        s = s[: i.start()].rstrip(" ,.;:-–—(|/&")
    return _norm(s)


def _catalog_key(track: YTMTrack) -> tuple[str, str]:
    """Ключ (artist, title) для сопоставления версий внутри каталога YT Music.

    В отличие от :func:`track_key` (дедуп с библиотекой) фичи игнорируются:
    клип «Song (feat. X)» и Topic-версия «Song» — одна песня.
    """
    return _norm(track.artist), _norm_title(track.title)


def track_key(track: YTMTrack) -> tuple[str, str]:
    """Нормализованный ключ (artist, title) для сравнения с библиотекой.

    Латиница и кириллица сравниваются без регистра и лишней пунктуации
    (``The Doors — The End`` ~ ``the doors - the end!``). Фичи не игнорируются:
    «Good Life» и «Good Life (feat. T-Pain)» — разные треки. Поле ``album``
    не участвует: совпадения ищем и среди видео/синглов, и среди альбомных
    версий.
    """
    return _norm(track.artist), _norm(track.title)


def library_keys(records: list) -> set[tuple[str, str]]:
    """Ключи (artist, title) всех записей библиотеки для дедупа.

    ``records`` — результат ``scan_library()``/``scan_directory()``
    (объекты с полями ``artist``/``title``).
    """
    keys: set[tuple[str, str]] = set()
    for rec in records:
        artist = str(getattr(rec, "artist", "") or "")
        title = str(getattr(rec, "title", "") or "") or str(
            getattr(getattr(rec, "path", None), "stem", "")
        )
        if artist and title:
            keys.add((_norm(artist), _norm(title)))
    return keys


def library_album_counts(records: list) -> dict[tuple[str, str], int]:
    """Сколько файлов локальной библиотеки приходится на каждый альбом.

    Ключ — ``(norm(альбом), norm(альбом-исполнитель))``, как группирует и
    экран «Альбомы». Используется для пометки «N/M в библиотеке» на YT-альбомах.
    """
    counts: dict[tuple[str, str], int] = {}
    for rec in records:
        album = str(getattr(rec, "album", "") or "")
        artist = str(getattr(rec, "album_artist", "") or "") or str(
            getattr(rec, "artist", "") or ""
        )
        if album and artist:
            key = (_norm(album), _norm(artist))
            counts[key] = counts.get(key, 0) + 1
    return counts


def library_album_track_keys(records: list) -> set[tuple[str, str, str]]:
    """Ключи (альбом, исполнитель, трек) локальных записей для треклистов альбомов."""
    keys: set[tuple[str, str, str]] = set()
    for rec in records:
        album = str(getattr(rec, "album", "") or "")
        artist = str(getattr(rec, "album_artist", "") or "") or str(
            getattr(rec, "artist", "") or ""
        )
        title = str(getattr(rec, "title", "") or "")
        if album and artist and title:
            keys.add((_norm(album), _norm(artist), _norm_title(title)))
    return keys


def track_in_album_library(
    track: YTMTrack, album: str, keys: set[tuple[str, str, str]],
) -> bool:
    """Есть ли трек в локальной библиотеке именно в указанном альбоме."""
    return bool(album and keys and (
        _norm(album), _norm(track.artist), _norm_title(track.title)
    ) in keys)


def library_artist_counts(records: list) -> dict[str, int]:
    """Сколько файлов локальной библиотеки приходится на каждого исполнителя."""
    counts: dict[str, int] = {}
    for rec in records:
        artist = str(getattr(rec, "artist", "") or "")
        if artist:
            key = _norm(artist)
            counts[key] = counts.get(key, 0) + 1
    return counts


def track_in_library(track: YTMTrack, keys: set[tuple[str, str]]) -> bool:
    """Есть ли трек в библиотеке (по нормализованному ключу)."""
    if not keys:
        return False
    return track_key(track) in keys


_RATING_NAMES = ("LIKE", "DISLIKE", "INDIFFERENT")


def rate_song(video_id: str, rating: str = "INDIFFERENT") -> None:
    """Поставить лайк/дизлайк песне в аккаунте (только с авторизацией).

    ``rating`` — ``LIKE``, ``DISLIKE`` или ``INDIFFERENT`` (снятие оценки).

    Raises:
        YTMusicError: не подключены или запрос не удался.
    """
    client = require_client()
    rating_name = str(rating).upper()
    if rating_name not in _RATING_NAMES:
        raise YTMusicError(f"Некорректная оценка: {rating}")
    try:
        from ytmusicapi.models.content.enums import LikeStatus

        client.rate_song(video_id, getattr(LikeStatus, rating_name))
    except Exception as e:
        raise YTMusicError(_err_text(e)) from e


def add_to_library(track: YTMTrack) -> None:
    """Добавить песню в библиотеку YT Music (только с авторизацией).

    Нужен токен из поиска песен (:attr:`YTMTrack.feedback_token`) — без него
    API не позволяет добавить трек.

    Raises:
        YTMusicError: нет токена, не подключены или запрос не удался.
    """
    client = require_client()
    token = str(track.feedback_token or "").strip()
    if not token:
        raise YTMusicError("Нет токена добавления в библиотеку (нужен поиск песен)")
    try:
        client.edit_song_library_status([token])
    except Exception as e:
        raise YTMusicError(_err_text(e)) from e


def library_songs(limit: int = 500) -> list[YTMTrack]:
    """Песни из библиотеки YT Music (лайки сюда не входят, только авторизация)."""
    client = require_client()
    try:
        results = client.get_library_songs(limit=limit)
    except Exception as e:
        raise YTMusicError(_err_text(e)) from e
    return [track_from_dict(t) for t in results or []]
