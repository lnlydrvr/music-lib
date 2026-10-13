"""Общие помощники для YouTube-cookies (yt-dlp) и age-gate ошибок.

Чистый модуль без зависимостей от yt-dlp: строит кандидатов опций
(``cookiesfrombrowser`` / ``cookiefile`` / без cookies) и распознаёт
ошибку возрастного ограничения YouTube.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

#: Порядок браузеров по умолчанию: Safari (старый дефолт) → Chrome (запасной).
DEFAULT_BROWSERS: tuple[str, ...] = ("safari", "chrome")

#: Подсказка при age-gate: возвращается вместо сырого текста yt-dlp.
AGE_GATE_HINT = (
    "Возрастное ограничение YouTube: нужны cookies браузера с аккаунтом 18+. "
    "Войдите в YouTube в Safari/Chrome и повторите, либо укажите файл cookies "
     "(MUSIC_LIB_COOKIES_FILE или youtube_cookies_file в конфиге)."
)

#: Имена cookies, означающие залогиненный аккаунт YouTube.
AUTH_COOKIE_NAMES = frozenset({
    "SID", "HSID", "SSID", "APISID", "SAPISID", "LOGIN_INFO",
    "__Secure-1PSID", "__Secure-3PSID", "__Secure-1PAPISID", "__Secure-3PAPISID",
})


def is_age_gate_error(err: BaseException | str) -> bool:
    """True, если ошибка — требование подтвердить возраст."""
    text = str(err).lower()
    return "sign in to confirm your age" in text


#: Подсказка, когда аккаунт залогинен, но сам не проходит проверку возраста.
AGE_BLOCKED_HINT = (
    "YouTube отклонил даже залогиненный аккаунт: в нём нет подтверждённых 18+ "
    "(дата рождения/проверка возраста). Решение: войти в браузер другим аккаунтом "
    "Google с подтверждёнными 18+ и повторить, либо загрузить его cookies.txt."
)


def is_age_blocked_error(err: BaseException | str) -> bool:
    """True, если аккаунт залогинен, но YouTube режет контент по возрасту."""
    text = str(err).lower()
    return "this content is age-restricted" in text and "sign in" not in text


def probe_reason(err: BaseException | str) -> str:
    """Классификация исхода age-probe: ok невозможен по ошибке; gate/blocked/other."""
    if is_age_gate_error(err):
        return "gate"
    if is_age_blocked_error(err):
        return "blocked"
    return "other"


def pick_error(errors: list[BaseException]) -> str:
    """Лучший текст из ошибок попыток: blocked > gate > последняя.

    Если хоть одна попытка дошла до «залогинен, но мал» — cookies работают,
    дело в возрасте аккаунта; иначе — классический «войдите».
    """
    if not errors:
        return ""
    for e in errors:
        if is_age_blocked_error(e):
            return friendly_error(e)
    for e in errors:
        if is_age_gate_error(e):
            return friendly_error(e)
    return friendly_error(errors[-1])


def _browser_store_exists(browser: str) -> bool:
    """Дешёвая проверка (без чтения): есть ли файл хранилища браузера."""
    home = Path(os.path.expanduser("~"))
    candidates: list[Path] = []
    if browser == "safari":
        candidates = [
            home / "Library/Cookies/Cookies.binarycookies",
            home / "Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies",
        ]
    elif browser in ("chrome", "chromium", "edge"):
        mapping = {
            "chrome": ("Google/Chrome", "google-chrome"),
            "chromium": ("Chromium", "chromium"),
            "edge": ("Microsoft Edge", "microsoft-edge"),
        }
        mac_dir, linux_dir = mapping[browser]
        candidates = [
            home / "Library/Application Support" / mac_dir / "Default/Cookies",
            home / "Library/Application Support" / mac_dir / "Cookies",
            home / ".config" / linux_dir / "Default/Cookies",
        ]
    elif browser == "firefox":
        candidates = [home / "Library/Application Support/Firefox",
                      home / ".mozilla/firefox"]
    else:
        return True
    try:
        return any(p.exists() for p in candidates)
    except OSError:
        return False


def friendly_error(err: BaseException | str) -> str:
    """Человекочитаемый текст ошибки с подсказкой про cookies при age-gate."""
    if is_age_gate_error(err):
        return f"{AGE_GATE_HINT} ({err})"
    if is_age_blocked_error(err):
        return f"{AGE_BLOCKED_HINT} ({err})"
    return str(err)


def discover_safari_profiles() -> list[tuple[str, str]]:
    """Хранилища cookies профилей Safari: [(метка, путь)].

    yt-dlp читает только дефолтное хранилище, а залогиненный аккаунт часто
    лежит в профиле (WebsiteDataStore/<uuid>/Cookies). Возвращает только
    существующие файлы; метка — первые 8 символов uuid профиля.
    """
    home = Path(os.path.expanduser("~"))
    base = (home / "Library/Containers/com.apple.Safari/Data/Library"
            / "WebKit/WebsiteDataStore")
    found: list[tuple[str, str]] = []
    try:
        entries = sorted(base.iterdir())
    except OSError:
        return []
    for entry in entries:
        cookie_file = entry / "Cookies" / "Cookies.binarycookies"
        try:
            is_file = cookie_file.is_file()
        except OSError:
            continue
        if is_file:
            found.append((entry.name[:8].upper(), str(cookie_file)))
    return found


def _default_safari_store() -> str | None:
    """Путь дефолтного хранилища Safari (первый существующий)."""
    home = Path(os.path.expanduser("~"))
    for p in (
        home / "Library/Cookies/Cookies.binarycookies",
        home / "Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies",
    ):
        try:
            if p.is_file():
                return str(p)
        except OSError:
            continue
    return None


def profile_has_yt_auth(cookie_file: str) -> bool:
    """True, если в хранилище Safari(-профиля) есть auth-cookies YouTube."""
    try:
        from yt_dlp.cookies import parse_safari_cookies

        with open(cookie_file, "rb") as fh:
            jar = parse_safari_cookies(fh.read())
        names = {c.name for c in jar if "youtube.com" in (c.domain or "")}
        return bool(names & AUTH_COOKIE_NAMES)
    except Exception:
        return False


def _safari_sources() -> list[dict[str, Any]]:
    """Источники Safari: сначала те, где есть вход, потом дефолт (если есть)."""
    default = _default_safari_store()
    default_auth = bool(default) and profile_has_yt_auth(default)
    sources = [
        {"cookiesfrombrowser": ("safari", path)}
        for _, path in discover_safari_profiles()
        if profile_has_yt_auth(path)
    ]
    if default:
        default_opt = {"cookiesfrombrowser": ("safari",)}
        if default_auth:
            sources.insert(0, default_opt)
        else:
            sources.append(default_opt)
    return sources


def cookie_opt_candidates(
    browser: str | None = None,
    cookiefile: str | None = None,
) -> list[dict[str, Any]]:
    """Список фрагментов ydl-опций для перебора (по одному на попытку).

    - cookiefile задан → [файл, без cookies];
    - browser задан → [этот браузер (+профили Safari), без cookies];
    - иначе → [safari, safari-профили со входом, chrome, без cookies].
    """
    if cookiefile:
        return [{"cookiefile": cookiefile}, {}]
    if browser:
        browser = browser.strip().lower()
        if browser:
            if browser == "safari":
                return _safari_sources() + [{}]
            # Явный чужой браузер — первый, профили Safari со входом — rescue.
            return ([{"cookiesfrombrowser": (browser,)}]
                    + _safari_sources() + [{}])
    profiles = [
        {"cookiesfrombrowser": ("safari", path)}
        for _, path in discover_safari_profiles()
        if profile_has_yt_auth(path)
    ]
    browsers = [
        {"cookiesfrombrowser": (name,)}
        for name in DEFAULT_BROWSERS
        if _browser_store_exists(name)
    ]
    return profiles + browsers + [{}]


def describe_source(opt: dict[str, Any]) -> str:
    """Короткая метка источника cookies для логов."""
    if "cookiefile" in opt:
        return f"файл {opt['cookiefile']}"
    browser = opt.get("cookiesfrombrowser")
    if browser:
        if isinstance(browser, (list, tuple)) and len(browser) > 1 and browser[1]:
            label = str(browser[1]).split("WebsiteDataStore/")[-1].split("/")[0][:8].upper()
            return f"safari:профиль {label}"
        name = browser[0] if isinstance(browser, (list, tuple)) else browser
        return str(name)
    return "без cookies"


def preferred_first(
    candidates: list[dict[str, Any]],
    prefer: str | None = None,
) -> list[dict[str, Any]]:
    """Переставить запомненный рабочий источник первым (sticky-source).

    Неизвестная/устаревшая метка игнорируется, порядок остальных сохраняется.
    """
    if not prefer:
        return candidates
    prefer = str(prefer).strip()
    head = [c for c in candidates if describe_source(c) == prefer]
    if not head:
        return candidates
    rest = [c for c in candidates if describe_source(c) != prefer]
    return head + rest


def get_preferred_source() -> str:
    """Метка sticky-источника из конфига (пусто — нет). Ошибки → пусто."""
    try:
        from .config import get_youtube_cookie_source

        return get_youtube_cookie_source()
    except Exception:
        return ""


def remember_working_source(opt: dict[str, Any]) -> None:
    """Запомнить удачный источник cookies. Ошибки записи игнорируются."""
    try:
        from .config import set_youtube_cookie_source

        set_youtube_cookie_source(describe_source(opt))
    except Exception:
        pass
