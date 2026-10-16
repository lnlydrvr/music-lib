"""Конфигурация приложения: каталог вывода и настройки по умолчанию.

Приоритет разрешения каталога вывода:
1. Явный override (CLI-флаг ``--output-dir``).
2. Переменная окружения ``MUSIC_LIB_DIR`` (старая ``MUSIC_DL_DIR`` — fallback).
3. Значение из конфиг-файла ``~/.config/music-lib/config.json``.
4. Автоопределённый дефолт: iCloud-папка, если она существует и доступна
   на запись, иначе ``~/Music``.

Старый конфиг ``~/.config/music-dl/config.json`` однократно мигрирует
в новое расположение при первом чтении/записи.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import threading
from importlib import resources
from pathlib import Path
from typing import Any, Callable

DEFAULT_FORMAT = "m4a"
DEFAULT_QUALITY = 256

#: Persisted UI locale chosen by the user. Its absence is meaningful: the
#: frontend then selects a browser-supported locale or English.
LANGUAGE_KEY = "language"
_LOCALE_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "frontend" / "src" / "locales" / "registry.json"


def _load_locale_registry() -> Any:
    """Load the source-tree registry or the copy bundled into installed wheels."""
    try:
        return json.loads(_LOCALE_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        try:
            bundled = resources.files("src").joinpath("locale_registry.json")
            return json.loads(bundled.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError, ModuleNotFoundError):
            return None


def _registered_languages() -> tuple[str, ...]:
    try:
        entries = _load_locale_registry()
        codes = tuple(entry["code"] for entry in entries if isinstance(entry, dict) and isinstance(entry.get("code"), str))
        return codes or ("en", "ru")
    except (TypeError, KeyError):
        return ("en", "ru")


SUPPORTED_LANGUAGES = _registered_languages()
DEFAULT_LANGUAGE = "en"

#: Предпочитаемый исходный аудиопоток yt-dlp: ``opus`` (нативный 251 с
#: фолбэком на лучший m4a) или ``m4a`` (AAC с фолбэком на лучший).
SOURCE_FORMAT_KEY = "source_format"
DEFAULT_SOURCE_FORMAT = "m4a"
SOURCE_FORMATS = ("m4a", "opus")

#: Ключ конфига для пути к файлу Shazam (импорт распознанного аудио).
SHAZAM_FILE_KEY = "shazam_file"

#: Ключ конфига: включённые источники метаданных (список имён).
METADATA_SOURCES_KEY = "metadata_sources"
DEFAULT_METADATA_SOURCES = ["iTunes", "Deezer", "Discogs"]

#: Ключ конфига: полный порядок источников метаданных (включая выключенные) —
#: задаётся перетаскиванием в настройках, определяет приоритет подстановки
#: тегов (первые источники выигрывают).
METADATA_SOURCES_ORDER_KEY = "metadata_sources_order"

#: Ключ конфига: sidecar-файлы для плеера Primuse (.lrc + -cover.jpg).
PRIMUSE_SIDECAR_KEY = "primuse_sidecar"

#: Ключ конфига: язык отображения имён исполнителей/альбомов для совпавших
#: пар «локальная кириллица + YT-латиница» (см. ``_norm`` в ytmusic.py):
#: ``auto`` (как в оригинале), ``cyrillic`` (только такие пары → кириллица),
#: ``latin`` (только такие пары → латиница).
NAME_TRANSLIT_KEY = "name_translit"
NAME_TRANSLITS = ("auto", "cyrillic", "latin")
DEFAULT_NAME_TRANSLIT = "auto"

#: Ключ конфига: файл cookies YouTube (Netscape cookies.txt) для yt-dlp.
YOUTUBE_COOKIES_FILE_KEY = "youtube_cookies_file"

#: Ключ конфига: браузер для `cookiesfrombrowser` (safari/chrome/chromium/firefox/edge).
YOUTUBE_BROWSER_KEY = "youtube_browser"

#: Браузеры, разрешённые для `youtube_browser` (safari ищет и в профилях).
YOUTUBE_BROWSERS = ("safari", "chrome", "chromium", "firefox", "edge")

#: Ключ конфига: последний рабочий источник YouTube-cookies (sticky-source).
#: Хранит метку из `ytcookies.describe_source` ("safari", "safari:профиль …",
#: "без cookies", "файл …"). При следующем запросе этот источник пробуется
#: первым, чтобы не тратить время на заведомо битые cookies и не шуметь
#: в логах. Невалидное/устаревшее значение игнорируется.
YOUTUBE_COOKIE_SOURCE_KEY = "youtube_cookie_source"

#: Ключ конфига: путь к файлу авторизации YouTube Music (ytmusicapi). По
#: умолчанию — ``~/.config/music-lib/ytmusic_auth.json``.
YTMUSIC_AUTH_FILE_KEY = "ytmusic_auth_file"

#: Ключ конфига: избегать скачивания клипов в YouTube Music (искать аудиоверсии Topic).
YTMUSIC_NO_CLIPS_KEY = "ytmusic_no_clips"

#: Ключ конфига: чем отмечать принятую рекомендацию в аккаунте YT Music —
#: ``like`` (лайк, сильный сигнал для радио) или ``library`` (сохранение
#: в библиотеку, слабый сигнал).
FEEDBACK_ACTION_KEY = "ytm_feedback_action"
FEEDBACK_ACTIONS = ("like", "library")
DEFAULT_FEEDBACK_ACTION = "like"

#: Ключ конфига: основной источник поиска и скачивания в веб-интерфейсе —
#: ``youtube_music`` (поиск и теги из YT Music, файл всё равно через yt-dlp)
#: или ``youtube`` (обычный поиск yt-dlp).
SEARCH_SOURCE_KEY = "search_source"
SEARCH_SOURCES = ("youtube_music", "youtube")
DEFAULT_SEARCH_SOURCE = "youtube_music"

#: Lucida download source and optional storefront country. Country is unset by
#: default so the adapter retains the service-specific default.
LUCIDA_SERVICE_KEY = "lucida_service"
LUCIDA_SERVICES = ("qobuz", "amazon")
DEFAULT_LUCIDA_SERVICE = "qobuz"
LUCIDA_COUNTRY_KEY = "lucida_country"

#: Number of concurrent Lucida download jobs. Keep this deliberately bounded:
#: each worker streams media and an excessive value degrades local networking.
LUCIDA_JOBS_KEY = "lucida_jobs"
DEFAULT_LUCIDA_JOBS = 3
MIN_LUCIDA_JOBS = 1
MAX_LUCIDA_JOBS = 8

#: Скрытая системная папка внутри библиотеки (дефолтный шазам-файл и
#: прочее служебное состояние). Переживает чистку контента библиотеки.
SYSTEM_DIR_NAME = ".system"
SHAZAM_DEFAULT_NAME = "shazam.txt"

CONFIG_DIR = Path.home() / ".config" / "music-lib"
CONFIG_PATH = CONFIG_DIR / "config.json"

# Settings updates originate from request handlers and background workers. The
# lock protects a complete load → modify → save transaction in this process.
_config_lock = threading.RLock()


def _legacy_config_path() -> Path:
    """Путь к конфигу до ребрендинга (music-dl). Вычисляется динамически,
    чтобы уважать подменённый ``Path.home`` в тестах."""
    return Path.home() / ".config" / "music-dl" / "config.json"


def _env(name: str) -> str:
    """Переменная ``MUSIC_LIB_<name>`` с fallback на старую ``MUSIC_DL_<name>``."""
    return (
        os.environ.get(f"MUSIC_LIB_{name}")
        or os.environ.get(f"MUSIC_DL_{name}")
        or ""
    )


def _read_legacy_config() -> dict[str, Any]:
    """Прочитать старый конфиг music-dl напрямую (без копирования)."""
    try:
        with open(_legacy_config_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _migrate_legacy_config() -> None:
    """Однократно скопировать старый конфиг music-dl в новое расположение.

    Ничего не делает, если новый конфиг уже есть или старого нет.
    Ошибки игнорируются — конфиг не должен ронять приложение.
    """
    with _config_lock:
        try:
            legacy = _legacy_config_path()
            if CONFIG_PATH.is_file() or not legacy.is_file():
                return
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix=f".{CONFIG_PATH.name}.", dir=CONFIG_DIR)
            try:
                with os.fdopen(fd, "wb") as target, open(legacy, "rb") as source:
                    shutil.copyfileobj(source, target)
                    target.flush()
                    os.fsync(target.fileno())
                os.replace(temp_name, CONFIG_PATH)
            except BaseException:
                try:
                    os.unlink(temp_name)
                except OSError:
                    pass
                raise
        except OSError:
            pass

_ICLOUD_DIR = (
    Path.home()
    / "Library/Mobile Documents/com~apple~CloudDocs/Музыка"
)


def cloud_dir_available() -> bool:
    """Проверить, доступен ли iCloud-каталог (существует и доступен на запись)."""
    if sys.platform != "darwin":
        return False
    try:
        return _ICLOUD_DIR.is_dir() and os.access(_ICLOUD_DIR, os.W_OK)
    except OSError:
        return False


def default_output_dir() -> Path:
    """Автоопределённый каталог по умолчанию: iCloud или ~/Music."""
    if cloud_dir_available():
        return _ICLOUD_DIR
    return Path.home() / "Music"


def load_config() -> dict[str, Any]:
    """Прочитать конфиг-файл. При отсутствии/ошибке вернуть пустой словарь."""
    _migrate_legacy_config()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def save_config(config: dict[str, Any]) -> None:
    """Записать конфиг-файл, создав при необходимости родительскую папку.

    При первой записи старый конфиг music-dl подмешивается как база,
    чтобы точечное сохранение (например sticky-источник cookies)
    не теряло перенесённые настройки.
    """
    with _config_lock:
        if not CONFIG_PATH.is_file():
            config = {**_read_legacy_config(), **config}
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{CONFIG_PATH.name}.", dir=CONFIG_DIR)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(config, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temp_name, CONFIG_PATH)
        except BaseException:
            try:
                os.unlink(temp_name)
            except OSError:
                pass
            raise


def update_config(update: Callable[[dict[str, Any]], Any]) -> Any:
    """Apply ``update`` to the latest config and persist it atomically.

    The callback runs under a process-local reentrant lock, so independent
    settings mutations cannot overwrite each other between read and write.
    """
    with _config_lock:
        cfg = load_config()
        result = update(cfg)
        save_config(cfg)
        return result


def normalize_path_input(raw: str) -> str:
    """Нормализовать введённый путь из командной строки/терминала.

    Убирает окружающие кавычки и shell-экранирование (обратный слэш перед
    пробелом/тильдой), чтобы пути вида "Mobile Documents" или ``'…'``,
    вставленные из терминала, корректно парсились.
    """
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        raw = raw[1:-1]
    return raw.replace("\\ ", " ").replace("\\~", "~")


INBOX_DIR_NAME = "Inbox"


def resolve_output_dir(override: Path | None = None) -> Path:
    """Определить каталог вывода по приоритету из докстроки модуля.

    Явно заданные источники (флаг/env/конфиг) возвращаются как есть — папка
    создаётся при первом скачивании (``Downloader`` делает ``mkdir``). Авто-
    дефолт выбирает только существующую и доступную папку.
    """
    if override is not None:
        return override.expanduser().resolve()
    env = _env("DIR")
    if env:
        return Path(env).expanduser().resolve()
    cfg_path = load_config().get("output_dir")
    if cfg_path:
        return Path(cfg_path).expanduser().resolve()
    return default_output_dir().expanduser().resolve()


def inbox_dir(output_dir: Path) -> Path:
    """Путь к промежуточной папке ``Inbox`` внутри каталога вывода.

    Скачивание идёт именно сюда; после обработки (теги, лирикс) файл
    перемещается в библиотеку (Artist/Album). Папка создаётся при первом
    скачивании в :class:`src.downloader.Downloader`.
    """
    return output_dir / INBOX_DIR_NAME


def get_settings() -> dict[str, Any]:
    """Настройки по умолчанию с подстановкой значений из конфига."""
    cfg = load_config()
    return {
        "output_dir": resolve_output_dir(),
        "default_format": cfg.get("default_format", DEFAULT_FORMAT),
        "default_quality": int(cfg.get("default_quality", DEFAULT_QUALITY)),
    }


def get_saved_language() -> str | None:
    """Return the valid persisted locale, or ``None`` when it is unset.

    This intentionally differs from :func:`get_language`: API serialization
    must preserve the distinction between no explicit choice and saved English.
    """
    value = load_config().get(LANGUAGE_KEY)
    return value if isinstance(value, str) and value in SUPPORTED_LANGUAGES else None


def get_language() -> str:
    """Return a safe effective locale for internal callers."""
    return get_saved_language() or DEFAULT_LANGUAGE


def get_source_format() -> str:
    """Предпочитаемый исходный поток yt-dlp (``opus`` или ``m4a``)."""
    raw = load_config().get(SOURCE_FORMAT_KEY, DEFAULT_SOURCE_FORMAT)
    value = str(raw).strip().lower() if raw else DEFAULT_SOURCE_FORMAT
    return value if value in SOURCE_FORMATS else DEFAULT_SOURCE_FORMAT


def get_name_translit() -> str:
    """Режим отображения имён для совпавших пар (``auto``/``cyrillic``/``latin``)."""
    raw = load_config().get(NAME_TRANSLIT_KEY, DEFAULT_NAME_TRANSLIT)
    value = str(raw).strip().lower() if raw else DEFAULT_NAME_TRANSLIT
    return value if value in NAME_TRANSLITS else DEFAULT_NAME_TRANSLIT


def get_metadata_sources() -> list[str]:
    """Включённые источники метаданных (список имён, канонический порядок).

    Пустой список в конфиге — все источники выключены; отсутствие ключа —
    дефолтный набор.
    """
    cfg = load_config()
    raw = cfg.get(METADATA_SOURCES_KEY)
    if isinstance(raw, list):
        names: list[str] = []
        for value in raw:
            name = str(value).strip()
            if name and name not in names:
                names.append(name)
        return names
    return list(DEFAULT_METADATA_SOURCES)


def get_metadata_sources_order() -> list[str]:
    """Полный порядок источников метаданных (включая выключенные).

    Сохранённый порядок фильтруется по живому реестру (источник мог
    исчезнуть), недостающие известные источники дописываются в конец.
    Ключа нет или тип не список — канонический порядок реестра.
    """
    from .providers import available_sources

    registry = available_sources()
    raw = load_config().get(METADATA_SOURCES_ORDER_KEY)
    if not isinstance(raw, list):
        return list(registry)
    order: list[str] = []
    for value in raw:
        name = str(value).strip()
        if name in registry and name not in order:
            order.append(name)
    order.extend(n for n in registry if n not in order)
    return order


def get_shazam_file() -> Path | None:
    """Путь к файлу Shazam из конфига, или None если не задан.

    Возвращает расширенный (``~``) и абсолютный путь.
    """
    raw = load_config().get(SHAZAM_FILE_KEY)
    if not raw:
        return None
    return Path(str(raw)).expanduser().resolve()


def get_primuse_sidecar() -> bool:
    """Включён ли режим Primuse (sidecar .lrc + -cover.jpg)."""
    raw = load_config().get(PRIMUSE_SIDECAR_KEY, False)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def get_youtube_cookies_file() -> Path | None:
    """Файл cookies YouTube (cookies.txt) из env/config, или None."""
    raw = _env("COOKIES_FILE") or load_config().get(
        YOUTUBE_COOKIES_FILE_KEY
    )
    if not raw:
        return None
    return Path(str(raw)).expanduser()


def get_youtube_browser() -> str:
    """Браузер для `cookiesfrombrowser` (env/config, иначе safari)."""
    raw = _env("BROWSER") or load_config().get(
        YOUTUBE_BROWSER_KEY
    )
    return str(raw).strip().lower() if raw else "safari"


def get_youtube_cookie_source() -> str:
    """Метка последнего рабочего источника cookies (sticky-source)."""
    raw = load_config().get(YOUTUBE_COOKIE_SOURCE_KEY)
    return str(raw).strip() if raw else ""


def set_youtube_cookie_source(source: str) -> None:
    """Запомнить рабочий источник cookies. Ошибки записи игнорируются."""
    try:
        update_config(lambda cfg: cfg.__setitem__(YOUTUBE_COOKIE_SOURCE_KEY, str(source)))
    except OSError:
        pass


def get_ytmusic_auth_file() -> Path:
    """Файл авторизации YouTube Music (из конфига или дефолт).

    Возвращает расширенный (``~``) путь к JSON-файлу ytmusicapi (headers
    браузера или OAuth-токен). Дефолт — рядом с конфигом.
    """
    raw = load_config().get(YTMUSIC_AUTH_FILE_KEY)
    if raw:
        return Path(str(raw)).expanduser()
    return CONFIG_DIR / "ytmusic_auth.json"


def get_ytmusic_no_clips() -> bool:
    """Избегать ли клипов при скачивании (искать аудиоверсии Topic)."""
    raw = load_config().get(YTMUSIC_NO_CLIPS_KEY, True)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    return str(raw).strip().lower() not in ("0", "false", "no", "off")


def get_feedback_action() -> str:
    """Чем отмечать принятую рекомендацию: ``like`` или ``library``."""
    raw = load_config().get(FEEDBACK_ACTION_KEY, DEFAULT_FEEDBACK_ACTION)
    value = str(raw).strip().lower() if raw else DEFAULT_FEEDBACK_ACTION
    return value if value in FEEDBACK_ACTIONS else DEFAULT_FEEDBACK_ACTION


def system_dir(output_dir: Path | None = None) -> Path:
    """Скрытая папка ``.system`` внутри библиотеки (или явно заданного каталога)."""
    root = output_dir if output_dir is not None else resolve_output_dir()
    return root / SYSTEM_DIR_NAME


def resolve_shazam_file(output_dir: Path | None = None) -> Path:
    """Активный файл Shazam: настроенный путь или дефолт ``.system/shazam.txt``.

    Кастомный путь из конфига всегда сильнее; дефолт живёт в системной папке
    библиотеки и создаётся при первой записи — поэтому приём шазам-списков
    работает сразу, без предварительной настройки.
    """
    custom = get_shazam_file()
    if custom is not None:
        return custom
    return system_dir(output_dir) / SHAZAM_DEFAULT_NAME


def get_search_source() -> str:
    """Основной источник поиска: ``youtube_music`` или ``youtube``."""
    raw = load_config().get(SEARCH_SOURCE_KEY, DEFAULT_SEARCH_SOURCE)
    value = str(raw).strip().lower() if raw else DEFAULT_SEARCH_SOURCE
    return value if value in SEARCH_SOURCES else DEFAULT_SEARCH_SOURCE


def get_lucida_service() -> str:
    """Lucida service (``qobuz`` or ``amazon``), with a safe default."""
    raw = load_config().get(LUCIDA_SERVICE_KEY, DEFAULT_LUCIDA_SERVICE)
    value = str(raw).strip().lower() if isinstance(raw, str) else DEFAULT_LUCIDA_SERVICE
    return value if value in LUCIDA_SERVICES else DEFAULT_LUCIDA_SERVICE


def get_lucida_country() -> str | None:
    """Optional normalized Lucida storefront country, or ``None`` when unset."""
    raw = load_config().get(LUCIDA_COUNTRY_KEY)
    if not isinstance(raw, str):
        return None
    if not raw.isascii():
        return None
    value = raw.strip().upper()
    return value if re.fullmatch(r"[A-Z]{2}", value, flags=re.ASCII) else None


def get_lucida_jobs() -> int:
    """Bounded concurrent Lucida download jobs, defaulting to three."""
    value = parse_lucida_jobs(load_config().get(LUCIDA_JOBS_KEY, DEFAULT_LUCIDA_JOBS))
    return value if value is not None else DEFAULT_LUCIDA_JOBS


def parse_lucida_jobs(raw: Any) -> int | None:
    """Return a bounded Lucida worker count, or ``None`` for invalid input."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        value = raw
    elif isinstance(raw, str):
        try:
            value = int(raw)
        except ValueError:
            return None
    else:
        return None
    return value if MIN_LUCIDA_JOBS <= value <= MAX_LUCIDA_JOBS else None
