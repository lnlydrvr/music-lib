"""Оркестрация рекомендаций: радио YouTube Music → список новых треков.

Никакой БД и ранжирования нет: кандидаты берутся из персонального радио
YouTube Music (``watch_playlist`` по сидам из библиотеки), которое уже
персонализировано аккаунтом (лайки/дизлайки/история). Убираются только треки,
которые уже есть в библиотеке. Оценка пользователя уходит обратно в аккаунт
(LIKE/DISLIKE/библиотека — по настройке) — так формируются дальнейшие
рекомендации.
"""
from __future__ import annotations

import itertools
import random
from typing import Any, Callable, Iterator

from .analytics import scan_library
from .ytmusic import norm, norm_title

#: Сколько сидов из библиотеки брать под одно радио.
DEFAULT_SEED_LIMIT = 5

#: Сколько похожих треков просить из радио по одному сиду.
DEFAULT_SIMILAR_LIMIT = 50

_RADIO_FN = Callable[[dict[str, Any], int], list[dict[str, Any]]]
"""``radio_fn(seed, limit) -> [candidate dicts]`` — радио YT Music по сиду."""


def pick_seeds(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Равномерно выбрать сиды по артистам (детерминированно).

    Сначала первый трек каждого артиста, затем второй и т.д., чтобы покрыть
    максимум разных артистов и не застрять на одном жанре.
    """
    ordered = sorted(
        records,
        key=lambda r: (str(r.get("artist", "")).casefold(), str(r.get("title", "")).casefold()),
    )
    by_artist: list[list[dict[str, Any]]] = []
    for rec in ordered:
        key = str(rec.get("artist", "")).casefold()
        if not by_artist or str(by_artist[-1][0].get("artist", "")).casefold() != key:
            by_artist.append([rec])
        else:
            by_artist[-1].append(rec)
    seeds: list[dict[str, Any]] = []
    slot = 0
    while len(seeds) < limit:
        progressed = False
        for group in by_artist:
            if slot < len(group):
                seeds.append(group[slot])
                progressed = True
                if len(seeds) >= limit:
                    return seeds
        if not progressed:
            break
        slot += 1
    return seeds


def _candidate_from_ytm(raw: dict[str, Any]) -> dict[str, str]:
    """Кандидат из радио YT Music в формате ``ytm_track_to_dict``."""
    video_id = str(raw.get("video_id") or "")
    url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
    return {
        "video_id": video_id,
        "artist": str(raw.get("artist") or "").strip(),
        "title": str(raw.get("title") or "").strip(),
        "album": str(raw.get("album") or ""),
        "cover_url": str(raw.get("cover_url") or ""),
        "url": url,
    }


def _seed_label(seed: dict[str, Any]) -> str:
    """Подпись сида «Исполнитель — Название» (та же, что у кандидатов)."""
    return " — ".join(
        str(seed.get(k) or "").strip() for k in ("artist", "title") if str(seed.get(k) or "").strip()
    )


def _round_robin(per_seed: list[list[dict[str, str]]]) -> list[dict[str, str]]:
    """Чередовать кандидаты по сидам (round-robin) с дедупом между группами.

    Внутри сида порядок радио сохранён, группировки «весь радио одного сида
    подряд» нет. При совпадении ключа ``(norm(artist), norm_title(title))``
    побеждает первый встретившийся кандидат — со своими полями, включая
    ``seed``.
    """
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for chunk in itertools.zip_longest(*per_seed):
        for cand in chunk:
            if cand is None:
                continue
            key = (norm(cand["artist"]), norm_title(cand["title"]))
            if key in seen:
                continue
            seen.add(key)
            items.append(cand)
    return items


def iter_generate(
    records: list[dict[str, Any]],
    radio_fn: _RADIO_FN,
    seed_limit: int = DEFAULT_SEED_LIMIT,
    similar_limit: int = DEFAULT_SIMILAR_LIMIT,
    rng: random.Random | None = None,
) -> Iterator[dict[str, Any]]:
    """Потоковая версия :func:`generate`: snapshot после каждого сида.

    Логика та же, что у :func:`generate` (выбор и перемешивание сидов,
    фильтрация по библиотеке, дедуп, round-robin), но результат отдаётся
    инкрементально: по завершении каждого сида — включая пустой ответ и
    локально обработанную ошибку радио — yield-ится накопительный snapshot

    ``{seed_index, seed_count, seed, items, seeds, library_count, total}``,

    где ``seed_index`` — 1-based номер обработанного сида, ``seed_count`` и
    ``seeds`` — число выбранных сидов (не успешных), ``seed`` — подпись сида
    «Исполнитель — Название», ``items`` — накопленный round-robin список по
    завершённым группам (полный список, не дельта), ``total`` — ``len(items)``.
    Первый snapshot доступен потребителю до вызова радио следующего сида.
    При нуле сидов не yield-ится ничего.
    """
    rng = rng or random
    owned_titles = {
        norm_title(str(r.get("title") or ""))
        for r in records
        if str(r.get("title") or "").strip()
    }
    seeds = pick_seeds(records, seed_limit)
    rng.shuffle(seeds)

    per_seed: list[list[dict[str, str]]] = []
    for seed_index, seed in enumerate(seeds, start=1):
        seed_label = _seed_label(seed)
        try:
            raws = radio_fn(seed, similar_limit) or []
        except Exception:  # noqa: BLE001 — сбой одного сида локален
            raws = []
        group: list[dict[str, str]] = []
        group_keys: set[tuple[str, str]] = set()
        for raw in raws:
            cand = _candidate_from_ytm(raw)
            cand["seed"] = seed_label
            title = norm_title(cand["title"])
            if not title or title in owned_titles:
                continue
            key = (norm(cand["artist"]), title)
            if key in group_keys:
                continue
            group_keys.add(key)
            group.append(cand)
        if group:
            per_seed.append(group)

        items = _round_robin(per_seed)
        yield {
            "seed_index": seed_index,
            "seed_count": len(seeds),
            "seed": seed_label,
            "items": items,
            "seeds": len(seeds),
            "library_count": len(records),
            "total": len(items),
        }


def generate(
    records: list[dict[str, Any]],
    radio_fn: _RADIO_FN,
    seed_limit: int = DEFAULT_SEED_LIMIT,
    similar_limit: int = DEFAULT_SIMILAR_LIMIT,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Собрать рекомендации из персонального радио YouTube Music.

    ``records`` — скан библиотеки (``scan_library``). Сиды выбираются
    равномерно по артистам и перемешиваются (``rng`` — для воспроизводимости
    в тестах), по каждому сиду запрашивается радио; кандидаты, которые уже
    есть в библиотеке (совпадение по названию — радио любит возвращать сам
    трек сида, иногда с другим исполнителем) или повторяются, исключаются.
    Сравнение как в дедупе YT Music (:func:`ytmusic.norm_title`): без фичей,
    регистра и пунктуации — «Barry Bonds (feat. Lil Wayne)» считается тем же
    треком, что и локальный «Barry Bonds». Итоговый порядок — чередование
    кандидатов по сидам (round-robin): внутри сида порядок радио сохранён,
    но группировки «весь радио одного сида подряд» нет. Оценки («score»)
    нет — ранжирование делает аккаунт YouTube Music.

    Реализация — потребитель :func:`iter_generate`: метаданные сида из
    snapshot-ов в итог не попадают, DTO прежний.
    """
    last: dict[str, Any] | None = None
    for snapshot in iter_generate(records, radio_fn, seed_limit, similar_limit, rng):
        last = snapshot
    if last is None:  # ноль сидов — прежний пустой DTO
        return {"items": [], "seeds": 0, "library_count": len(records), "total": 0}
    return {
        "items": last["items"],
        "seeds": last["seeds"],
        "library_count": last["library_count"],
        "total": last["total"],
    }


__all__ = ["pick_seeds", "generate", "iter_generate",
           "DEFAULT_SEED_LIMIT", "DEFAULT_SIMILAR_LIMIT"]