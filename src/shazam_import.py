"""Импорт распознанного аудио из файла Shazam.

Файл — обычный текст: в каждой строке одно распознанное аудио в формате
``Название - Исполнитель`` (например, то, что копирует мобильный Shazam).
Пустые строки и строки-комментарии (начинающиеся с ``#``) игнорируются.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from rich.table import Table

if TYPE_CHECKING:
    from rich.console import Console


@dataclass
class ShazamEntry:
    """Одно распознанное аудио, прочитанное из файла Shazam."""

    index: int
    line_number: int
    title: str
    artist: str

    @property
    def query(self) -> str:
        """Поисковый запрос для YouTube: ``Название Исполнитель``."""
        if self.artist:
            return f"{self.title} {self.artist}"
        return self.title

    @property
    def display(self) -> str:
        """Человекочитаемое представление ``Исполнитель — Название``."""
        return f"{self.artist} — {self.title}" if self.artist else self.title


def parse_shazam_file(path: Path) -> list[ShazamEntry]:
    """Прочитать файл Shazam и вернуть список распознанных треков.

    Каждая непустая строка (кроме комментариев ``#``) трактуется как
    ``Название - Исполнитель``. Если разделитель `` - `` отсутствует, вся
    строка считается названием. При ошибке чтения возвращается пустой список.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    entries: list[ShazamEntry] = []
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        title, artist = _split_title_artist(line)
        if not title:
            continue
        entries.append(
            ShazamEntry(
                index=len(entries) + 1,
                line_number=line_number,
                title=title,
                artist=artist,
            )
        )
    return entries


def remove_shazam_lines(path: Path, line_numbers: set[int]) -> int:
    """Удалить строки с указанными номерами из Shazam-файла.

    Файл переписывается целиком; строки-комментарии и пустые сохраняются как
    есть. Возвращает количество удалённых строк (0 при ошибке чтения/записи).
    """
    if not line_numbers:
        return 0
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    ends_newline = text.endswith("\n")
    lines = text.splitlines()
    kept = [line for i, line in enumerate(lines, 1) if i not in line_numbers]
    removed = len(lines) - len(kept)
    if removed == 0:
        return 0
    out = "\n".join(kept)
    if kept and ends_newline:
        out += "\n"
    try:
        path.write_text(out, encoding="utf-8")
    except OSError:
        return 0
    return removed


def find_youtube_matches(
    entries: list[ShazamEntry],
    search: Callable[[str], list],
) -> list[tuple[ShazamEntry, list]]:
    """Найти для каждого трека совпадения на YouTube.

    Сначала ищет по полному запросу ``Название Исполнитель``. Если результатов
    нет, повторяет поиск по одному названию — полный запрос иногда возвращает
    пустоту на YouTube, хотя трек существует.
    """
    matches: list[tuple[ShazamEntry, list]] = []
    for e in entries:
        found = search(e.query)
        if not found and e.artist:
            found = search(e.title)
        matches.append((e, found))
    return matches


#: Порог схожести названия, при котором результат считается точным совпадением
#: и скачивается без подтверждения пользователя.
CONFIDENT_SCORE = 0.75


def _norm(value: str) -> str:
    """Нормализовать строку для сравнения: нижний регистр, без знаков препинания."""
    return re.sub(r"[^A-Za-z0-9\u0080-\uffff]", "", value.casefold())


def _similarity(a: str, b: str) -> float:
    """Схожесть двух названий: 1.0 при точном совпадении/вложении, иначе difflib."""
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def score_match(entry: ShazamEntry, result) -> float:
    """Насколько найденный результат YouTube близок к треку по названию."""
    return _similarity(entry.title, result.info.title)


def is_confident(entry: ShazamEntry, result) -> bool:
    """Точное совпадение названия — скачивать без подтверждения."""
    return result is not None and score_match(entry, result) >= CONFIDENT_SCORE


def resolve_match(entry: ShazamEntry, found: list, console: Console, ask: Callable) -> object | None:
    """Выбрать результат YouTube для скачивания.

    Точное совпадение по названию возвращается сразу. Иначе (названия
    отличаются, транслитерация, сборники и т.п.) показывается список кандидатов
    и пользователь выбирает номер (или пропускает трек). Возвращает ``None``,
    если трек нужно пропустить.
    """
    best = found[0]
    if is_confident(entry, best):
        return best

    table = Table(title=f"Уточните результат: {entry.display}")
    table.add_column("#", style="dim", width=4)
    table.add_column("Название")
    table.add_column("Канал", style="dim")
    table.add_column("Ссылка", style="dim")
    for i, result in enumerate(found, 1):
        info = result.info
        table.add_row(
            str(i),
            info.title,
            info.uploader,
            info.webpage_url or f"https://www.youtube.com/watch?v={info.id}",
        )
    console.print(table)

    raw = ask(
        "Какой результат скачать",
        default="1",
        hint="номер, 0/q = пропустить",
        cancel="",
    )
    if raw is None:
        return None
    raw = raw.strip()
    if raw in ("", "0", "q", "Q", "quit"):
        return None
    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(found):
            return found[n - 1]
    return None


def resolve_selected(
    matches: list[tuple[ShazamEntry, list]],
    selected: set[int],
    console: Console,
    ask: Callable,
) -> list[tuple[ShazamEntry, object]]:
    """Для выбранных номеров треков определить итоговый результат YouTube.

    Сомнительные совпадения уточняются у пользователя; пропущенные треки из
    результата исключаются.
    """
    resolved: list[tuple[ShazamEntry, object]] = []
    for i, (entry, found) in enumerate(matches, 1):
        if i not in selected or not found:
            continue
        result = resolve_match(entry, found, console, ask)
        if result is not None:
            resolved.append((entry, result))
    return resolved


def _split_title_artist(line: str) -> tuple[str, str]:
    """Разделить ``Название - Исполнитель`` на название и исполнителя.

    Деление идёт по последнему вхождению `` - `` (с пробелами вокруг), чтобы
    названия, содержащие дефис (например ``Crazy - Videos``), не разбивались.
    """
    parts = line.rsplit(" - ", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return line, ""


def append_shazam_lines(path: Path, lines: list[str]) -> tuple[int, int]:
    """Дописать строки «Название - Исполнитель» в шазам-файл (дедуп по строке).

    Комментарии ``#`` и пустые строки игнорируются. Возвращает
    ``(добавлено, пропущено)``. Файл создаётся при первой записи.
    """
    incoming: list[str] = []
    for raw in lines:
        line = (raw or "").strip()
        if not line or line.startswith("#"):
            continue
        if line not in incoming:
            incoming.append(line)
    try:
        existing_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        existing_text = ""
    existing = {
        line.strip()
        for line in existing_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    fresh = [line for line in incoming if line not in existing]
    if fresh:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            if existing_text and not existing_text.endswith("\n"):
                fh.write("\n")
            fh.write("\n".join(fresh) + "\n")
    return len(fresh), len(incoming) - len(fresh)


def migrate_shazam_default(custom: Path, output_dir: Path) -> int:
    """Однократный перенос строк из дефолтного ``.system/shazam.txt`` в кастом.

    Вызывается при сохранении кастомного пути в настройках: содержимое
    дефолтного файла дописывается в кастомный с дедупом, чтобы шазамы
    не «раздвоились» между двумя файлами. Возвращает число перенесённых.
    """
    from .config import SHAZAM_DEFAULT_NAME, system_dir

    default = system_dir(output_dir) / SHAZAM_DEFAULT_NAME
    try:
        if not default.is_file() or default.resolve() == custom.resolve():
            return 0
        lines = default.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return 0
    added, _ = append_shazam_lines(custom, lines)
    return added
