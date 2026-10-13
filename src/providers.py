"""Поиск метаданных трека по музыкальным источникам.

iTunes Search API — основной источник, Deezer (``src/fetcher.py``) и Discogs —
фолбэки. Включённые источники задаются настройкой ``metadata_sources``.
Каждый источник возвращает список :class:`ProviderRecord` —
нормализованное представление тегов, после чего пользователь может выбрать,
какое значение взять для каждого тега отдельно.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .utils import logger

USER_AGENT = "music-lib/0.1.0"

#: Минимальный интервал между запросами к хосту, сек (лимиты без токена:
#: iTunes Search ~20 req/min, Discogs 60 req/min).
_HOST_MIN_INTERVAL = {
    "itunes.apple.com": 3.5,
    "api.discogs.com": 1.1,
}
_HOST_STATE: dict[str, float] = {}
#: Кулдаун хоста после 429 (monotonic-время, до которого все ждут).
_COOLDOWN_UNTIL: dict[str, float] = {}
_HOST_LOCKS: dict[str, threading.Lock] = {}
_HOST_LOCKS_GUARD = threading.Lock()

#: Обработка 429: до 5 ожиданий, экспоненциальный бэкофф 5→10→20→40→65 с
#: (Retry-After уважается, если больше). Кулдаун iTunes за 429 держится
#: ~минуту — коротких ретраев не хватает, хост надо дождаться целиком.
_429_MAX_WAITS = 5
_429_BASE_DELAY = 5.0
_429_MAX_DELAY = 65.0


def _host_of(url: str) -> str:
    return urllib.parse.urlsplit(url).netloc


def _host_lock(host: str) -> threading.Lock:
    with _HOST_LOCKS_GUARD:
        return _HOST_LOCKS.setdefault(host, threading.Lock())


def _throttle(url: str) -> None:
    """Пакетные запросы не должны упираться в rate limit хоста.

    Под общим на хост замком: ждём кулдаун после 429 (если был), затем
    держим минимальный интервал между запросами. Хосты не блокируют
    друг друга.
    """
    host = _host_of(url)
    interval = _HOST_MIN_INTERVAL.get(host)
    with _host_lock(host):
        now = time.monotonic()
        until = _COOLDOWN_UNTIL.get(host, 0.0)
        if until > now:
            time.sleep(until - now)
            now = time.monotonic()
        if interval:
            wait = _HOST_STATE.get(host, 0.0) + interval - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
        _HOST_STATE[host] = now


def _penalize(url: str, delay: float) -> None:
    """Поставить хост на кулдаун после 429.

    Все последующие запросы к хосту (в т.ч. от следующих треков пакета)
    подождут в ``_throttle`` — вместо каскада одинаковых 429.
    """
    host = _host_of(url)
    with _host_lock(host):
        until = time.monotonic() + delay
        if until > _COOLDOWN_UNTIL.get(host, 0.0):
            _COOLDOWN_UNTIL[host] = until


def _429_backoff(e: urllib.error.HTTPError, nth: int) -> float:
    """Задержка перед повтором после N-го подряд 429 (сек)."""
    try:
        after = float(e.headers.get("Retry-After") or 0)
    except (TypeError, ValueError):
        after = 0.0
    backoff = _429_BASE_DELAY * (2 ** (nth - 1))
    return min(max(after, backoff), _429_MAX_DELAY)


@dataclass
class ProviderRecord:
    """Нормализованный набор тегов, полученный от одного источника."""

    source: str
    title: str = ""
    artist: str = ""
    album: str = ""
    year: str = ""
    genre: str = ""
    track_number: str = ""
    album_artist: str = ""
    disc_number: str = ""
    isrc: str = ""
    composer: str = ""
    publisher: str = ""
    label: str = ""
    cover_url: str = ""

    def summary(self) -> str:
        """Короткое описание записи для списка выбора."""
        parts = [self.title]
        if self.album:
            parts.append(self.album)
        if self.year:
            parts.append(self.year)
        return " — ".join(parts)


#: Поля-теги, которые пользователь может выбрать по одному в UI.
TAGGABLE_FIELDS = [
    ("title", "Название"),
    ("artist", "Исполнитель"),
    ("album", "Альбом"),
    ("year", "Год"),
    ("genre", "Жанр"),
    ("track_number", "Трек №"),
    ("album_artist", "Альбом-исполнитель"),
    ("disc_number", "Диск №"),
    ("isrc", "ISRC"),
    ("composer", "Композитор"),
    ("publisher", "Издатель"),
    ("label", "Лейбл"),
]

#: Реестр источников: канонический порядок и функции поиска.
_PROVIDER_FUNCS = {
    "iTunes": "_search_itunes",
    "Deezer": "_search_deezer",
    "Discogs": "_search_discogs",
}
_PROVIDER_NAMES = list(_PROVIDER_FUNCS)


def available_sources() -> list[str]:
    """Все доступные источники метаданных в каноническом порядке."""
    return list(_PROVIDER_NAMES)


def _request(url: str, retries: int = 2, timeout: int = 15,
             headers: dict | None = None) -> dict | None:
    """Запрос с ретраями, возвращает распарсенный JSON (dict) или None.

    HTTP 429 обрабатывается отдельно: хост ставится на кулдаун
    (экспоненциальный бэкофф, ``Retry-After`` уважается), и повторная
    попытка ждёт его в ``_throttle`` — до 5 ожиданий независимо от
    ``retries``. Так пакетное редактирование переживает лимит
    iTunes/Discogs: следующие треки ждут окончания кулдауна, а не
    валятся с тем же 429.
    """
    hdrs = {"User-Agent": USER_AGENT, "Accept-Language": "ru"}
    if headers:
        hdrs.update(headers)
    attempt = 0
    waits_429 = 0
    while True:
        try:
            _throttle(url)
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and waits_429 < _429_MAX_WAITS:
                waits_429 += 1
                _penalize(url, _429_backoff(e, waits_429))
                continue
            if attempt < retries:
                attempt += 1
                time.sleep(1.5 * attempt)
                continue
            logger.warning("Ошибка источника %s: %s", _host_of(url), e)
            return None
        except Exception as e:
            if attempt < retries:
                attempt += 1
                time.sleep(1.5 * attempt)
                continue
            logger.warning("Ошибка источника %s: %s", _host_of(url), e)
            return None


def _search_deezer(title: str, artist: str = "") -> list[ProviderRecord]:
    """Поиск в Deezer через существующий fetcher.

    Детали (ISRC, номер, жанр, лейбл) добываются только для лучшего
    совпадения: ``fetch_tags`` делает до трёх запросов на результат,
    и обогащение всех пяти занимало ~11 с. Остальные записи собираются
    из поисковой выдачи (название/артист/альбом/обложка) без запросов.
    """
    try:
        from .fetcher import fetch_tags, search_deezer

        results = search_deezer(title, artist) or []
    except Exception as e:
        logger.warning("Ошибка Deezer: %s", e)
        return []
    records: list[ProviderRecord] = []
    for i, item in enumerate(results):
        if i == 0:
            fetched = fetch_tags(title, artist, track_data=item)
            if fetched is None:
                continue
            records.append(
                ProviderRecord(
                    source="Deezer",
                    title=fetched.title,
                    artist=fetched.artist,
                    album=fetched.album,
                    year=fetched.year,
                    genre=fetched.genre,
                    track_number=fetched.track_number,
                    album_artist=fetched.album_artist,
                    disc_number=fetched.disc_number,
                    isrc=fetched.isrc,
                    composer=fetched.composer,
                    publisher=fetched.label,
                    label=fetched.label,
                    cover_url=fetched.cover_url,
                )
            )
            continue
        album = item.get("album") or {}
        records.append(
            ProviderRecord(
                source="Deezer",
                title=item.get("title") or "",
                artist=(item.get("artist") or {}).get("name") or "",
                album=album.get("title") or "",
                cover_url=album.get("cover_xl") or album.get("cover_big") or "",
            )
        )
    return records


def _search_itunes(title: str, artist: str = "") -> list[ProviderRecord]:
    """Поиск в iTunes Search API (Apple), без авторизации.

    Параметр ``lang=ru_RU`` заставляет Apple отдавать локаль-специфичные
    данные (например, жанр ``Pop`` -> ``Поп``).
    """
    query = f"{artist} {title}".strip() if artist else title
    params = {
        "term": query,
        "media": "music",
        "entity": "song",
        "lang": "ru_RU",
        "limit": "5",
    }
    url = f"https://itunes.apple.com/search?{urllib.parse.urlencode(params)}"
    data = _request(url, retries=1, timeout=10)
    if not data:
        return []
    records: list[ProviderRecord] = []
    for r in data.get("results", []):
        records.append(
            ProviderRecord(
                source="iTunes",
                title=r.get("trackName") or "",
                artist=r.get("artistName") or "",
                album=r.get("collectionName") or "",
                year=_first4(_release_year(r)),
                genre=r.get("primaryGenreName") or "",
                track_number=_i4num(r.get("trackNumber")),
                disc_number=_i4num(r.get("discNumber")),
                isrc=r.get("isrc") or "",
                cover_url=_itunes_cover_hires(r.get("artworkUrl100") or ""),
            )
        )
    return records


#: Сколько релизов Discogs обогащать деталями ``/releases/{id}``: каждый
#: такой запрос стоит 1.1 с троттлинга (лимит 1 req/s без токена),
#: альтернативы глубже двух редко кому нужны.
_DISCOGS_DETAIL_LIMIT = 2


def _search_discogs(title: str, artist: str = "") -> list[ProviderRecord]:
    """Поиск в Discogs API (публичный, без токена).

    Поиск по ``/database/search`` возвращает ``title`` вида
    «Исполнитель - Название», поэтому лучшие релизы добиваем деталями
    ``/releases/{id}``: там чистый ``title`` альбома, артисты, год, жанры,
    full-size обложка и ``tracklist`` (по нему подбираем запрос к названию
    трека). Детали — только для топ-:data:`_DISCOGS_DETAIL_LIMIT` совпадений.
    Дубли (одинаковые title/album/год) схлопываем, лимит 1 req/s без токена.
    """
    query = f"{artist} {title}".strip() if artist else title
    params = {
        "q": query,
        "type": "release",
        "per_page": "4",
    }
    url = f"https://api.discogs.com/database/search?{urllib.parse.urlencode(params)}"
    data = _request(url, retries=2, timeout=15, headers={
        "User-Agent": "music-lib/0.1.0 (https://github.com/music-lib)",
    })
    if not data:
        return []
    records: list[ProviderRecord] = []
    seen: set[tuple] = set()
    for r in data.get("results", []):
        if r.get("type") == "master" or not r.get("id"):
            continue
        if len(records) >= _DISCOGS_DETAIL_LIMIT:
            break
        detail = _request(
            f"https://api.discogs.com/releases/{r['id']}",
            retries=2, timeout=15,
        )
        if not detail:
            continue
        album = (detail.get("title") or "").strip()
        artists = ", ".join(
            (a.get("name") or "").strip() for a in detail.get("artists") or []
            if (a.get("name") or "").strip()
        )
        year = str(detail.get("year") or "")[:4]
        genres = detail.get("genres") or []
        track_title = _best_track_title(title, detail.get("tracklist") or [])
        if not track_title:
            raw = r.get("title") or ""
            sep = raw.find(" - ")
            track_title = raw[sep + 3:].strip() if sep >= 0 else raw.strip()
        cover = _discogs_cover(detail.get("images") or [])
        key = (track_title.lower(), artists.lower(), album.lower(), year)
        if key in seen:
            continue
        seen.add(key)
        records.append(
            ProviderRecord(
                source="Discogs",
                title=track_title,
                artist=artists,
                album_artist=artists,
                album=album,
                year=year,
                genre=genres[0] if genres else "",
                cover_url=cover,
            )
        )
    return records


def _best_track_title(query: str, tracklist: list) -> str:
    """Найти в tracklist трек, лучше всего совпадающий с запросом.

    Сравнение по набору слов (без регистра); вернуть название трека или "".
    """
    qw = {w for w in _norm(query).split() if w}
    if not qw:
        return ""
    best, best_score = "", 0
    for t in tracklist:
        raw = (t.get("title") or "").strip()
        if not raw:
            continue
        tw = {w for w in _norm(raw).split() if w}
        score = len(qw & tw)
        if score > best_score:
            best, best_score = raw, score
    return best


def _norm(s: str) -> str:
    return "".join(ch for ch in (s or "").lower() if ch.isalnum() or ch.isspace()).strip()


def _discogs_cover(images: list) -> str:
    """Обложка: primary-изображение, иначе первое."""
    if not images:
        return ""
    for img in images:
        if img.get("type") == "primary" and img.get("uri"):
            return img["uri"]
    return images[0].get("uri") or ""


def _itunes_cover_hires(url: str) -> str:
    """Поднять превью iTunes (artworkUrl100, 100x100) до высокого разрешения.

    iTunes-арт хранит размер в URL как токен ``100x100bb`` — заменяем его
    на ``1000x1000bb``, чтобы скачивалась полноразмерная обложка.
    """
    if not url or "100x100bb" not in url:
        return url
    return url.replace("100x100bb", "1000x1000bb")


def _release_year(r: dict) -> str:
    raw = r.get("releaseDate") or ""
    return raw[:4] if raw else ""


def _first4(s: str) -> str:
    s = (s or "").strip()
    return s[:4] if s else ""


def _i4num(v) -> str:
    return str(v) if v else ""


def fetch_all(title: str, artist: str = "",
              sources: list[str] | None = None) -> dict[str, list[ProviderRecord]]:
    """Запросить источники метаданных и вернуть {source: [records]}.

    ``sources=None`` — берутся включённые из конфига; пустой ``sources=[]`` —
    ни один источник не опрашивается (все выключены). Имена фильтруются по
    реестру, порядок — как в ``sources`` (порядок из настроек задаёт
    приоритет). Источники опрашиваются параллельно:
    общее время равно самому медленному, а не сумме.
    """
    if sources is None:
        from .config import get_metadata_sources
        sources = get_metadata_sources()
    names = list(dict.fromkeys(
        name for name in sources if name in _PROVIDER_FUNCS
    ))
    if not names:
        return {}

    def search(name: str) -> list[ProviderRecord]:
        fn = globals().get(_PROVIDER_FUNCS[name])
        if fn is None:
            return []
        return fn(title, artist)

    results: dict[str, list[ProviderRecord]] = {}
    with ThreadPoolExecutor(max_workers=min(len(names), 4)) as ex:
        futures = {name: ex.submit(search, name) for name in names}
        for name in names:
            try:
                recs = futures[name].result()
            except Exception as e:
                logger.warning("Ошибка источника %s: %s", name, e)
                recs = []
            if recs:
                results[name] = recs
    return results
