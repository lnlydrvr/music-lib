"""Health-check музыкальной библиотеки.

Проверяет целостность и консистентность библиотеки и собирает найденные
проблемы по категориям:

* ``missing`` — незаполненные теги (artist/title/album/genre/year/cover ...);
* ``unreadable`` — файлы, которые не удалось прочитать (битые/повреждённые);
* ``duplicates`` — точные (MD5) и семантические (artist + title) дубликаты;
* ``mismatch`` — имя файла не совпадает с тегом ``title``;
* ``loose`` — файлы, лежащие в корне библиотеки, вне структуры Artist/Album.

Наличие текстов (lyrics) не проверяется. ``fix_issues`` исправляет категории
``mismatch`` и ``loose`` (переименование/перемещение файлов).

Модуль не зависит от UI: ``scan_items`` читает файлы, ``collect_issues`` считает
проблемы по чистым записям (тестируемо без файловой системы), ``render_health``
рисует отчёт через rich.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from .tagger import get_tags
from .messages import format_message, message as diagnostic_message

#: Поля тегов, для которых считаем незаполненность (категория «missing»).
#: Формат: (имя атрибута, русская подпись). Тексты (lyrics) не проверяем.
MISSING_FIELDS = (
    ("artist", "Исполнитель"),
    ("title", "Название"),
    ("album", "Альбом"),
    ("genre", "Жанр"),
    ("year", "Год"),
    ("cover", "Обложка"),
)


@dataclass
class HealthItem:
    """Одна запись библиотеки со всем, что нужно для health-check."""

    path: Path
    artist: str = ""
    title: str = ""
    album: str = ""
    year: str = ""
    genre: str = ""
    lyrics: str = ""
    cover: bool = False
    read_ok: bool = True
    md5: str = ""
    disc_number: str = ""


@dataclass
class HealthIssue:
    """Одна найденная проблема."""

    category: str
    path: Path
    message: str | dict = field(default_factory=dict)


_FIELD_LABELS = {
    "artist": "Artist", "title": "Title", "album": "Album", "genre": "Genre",
    "year": "Year", "cover": "Cover",
}


def _message(code: str, params: dict | None = None, fallback: str = "") -> dict:
    return diagnostic_message(code, params, fallback=fallback)


@dataclass
class HealthReport:
    """Результат health-check библиотеки."""

    total: int = 0
    issues: list[HealthIssue] = field(default_factory=list)
    issues_by_category: dict[str, list[HealthIssue]] = field(default_factory=dict)
    score: int = 100

    def count(self, category: str) -> int:
        return len(self.issues_by_category.get(category, []))


def _norm(value: str) -> str:
    """Нормализовать строку для сравнения («есть/нет» и для поиска дублей)."""
    return (value or "").strip().lower()


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


#: Символы, запрещённые в именах файлов (заменяются на «_» при сохранении).
_INVALID_CHARS_RE = re.compile(r'[<>:"/\\|?*]+')


def _name_norm(value: str) -> str:
    """Имя файла/тег title в сравнимой форме.

    Имя файла получается из тега через ``sanitize_name`` — запрещённые символы
    заменяются на «_». Чтобы не флагать такие совпадения, применяем ту же замену
    к обеим сторонам (регистр и пробелы по краям не учитываются).
    """
    return _nfc(_norm(_INVALID_CHARS_RE.sub("_", value)))


def _parse_disc_num(value: str) -> int | None:
    """Разобрать номер диска из «N/T».

    Подкаталог Disc N создаём только при явном указании общего числа дисков
    больше одного (напр. «1/2»). Одиночные значения («1», «2/1») и пустые —
    single-disc, остаются в плоской структуре.
    """
    v = (value or "").strip()
    if not v:
        return None
    m = re.search(r"(\d+)\s*/\s*(\d+)", v)
    if m:
        num, total = int(m.group(1)), int(m.group(2))
        if total > 1:
            return num
        return None
    return None


def _md5(path: Path) -> str:
    """MD5-хеш файла (пустая строка, если не читается)."""
    try:
        h = hashlib.md5()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def _scan_item(path: Path) -> HealthItem:
    """Прочитать теги и MD5 одного файла в HealthItem."""
    try:
        tags = get_tags(path)
    except Exception:
        return HealthItem(path=path, read_ok=False)

    title = (tags.title or "").strip() or path.stem
    return HealthItem(
        path=path,
        artist=(tags.artist or "").strip(),
        title=title,
        album=(tags.album or "").strip(),
        year=(tags.year or "").strip(),
        genre=(tags.genre or "").strip(),
        lyrics=(tags.lyrics or "").strip(),
        cover=bool(tags.cover_data),
        read_ok=True,
        md5=_md5(path),
        disc_number=(tags.disc_number or "").strip(),
    )


def scan_items(output_dir: Path, include_inbox: bool = False) -> list[HealthItem]:
    """Просканировать библиотеку в список HealthItem (включая битые файлы).

    Файлы во временной папке ``Inbox`` в библиотеку не входят, если
    ``include_inbox`` не передан как True.
    """
    from .analytics import library_files

    items: list[HealthItem] = []
    for path in library_files(output_dir, include_inbox=include_inbox):
        items.append(_scan_item(path))
    return items


def collect_issues(items: list[HealthItem], output_dir: Path | None = None) -> HealthReport:
    """Посчитать проблемы по чистым записям (без файловой системы).

    ``output_dir`` используется для определения loose-файлов (в корне
    библиотеки). Если не передан, корень выводится из путей файлов.
    """
    report = HealthReport(total=len(items))
    issues: list[HealthIssue] = []
    by_cat: dict[str, list[HealthIssue]] = {}

    # 1. Битые / нечитаемые файлы.
    for item in items:
        if not item.read_ok:
            _add(by_cat, "unreadable", HealthIssue(
                "unreadable", item.path, _message(
                    "diagnostics.health.unreadable", fallback="Could not read file"),
            ))

    # 2. Незаполненные теги.
    for item in items:
        if not item.read_ok:
            continue
        for name, _label in MISSING_FIELDS:
            if name == "cover":
                present = item.cover
            else:
                present = bool(_norm(getattr(item, name)))
            if not present:
                _add(by_cat, "missing", HealthIssue(
                    "missing", item.path, _message(
                        "diagnostics.health.missing_tag", {"field": name},
                        fallback=f'Missing tag “{_FIELD_LABELS.get(name, name)}”'),
                ))

    # 3. Дубликаты: точные (MD5) и семантические (artist + title).
    # Точный дубликат перекрывает семантический — файл не считаем дважды.
    # Семантический ключ учитывает album и disc_number — одинаковое название
    # на разных дисках/альбомах это не дубликат.
    duplicated_paths: set[Path] = set()
    seen_md5: dict[str, list[HealthItem]] = {}
    for item in items:
        if item.read_ok and item.md5:
            seen_md5.setdefault(item.md5, []).append(item)
    for paths in seen_md5.values():
        if len(paths) < 2:
            continue
        best = max(paths, key=lambda p: p.path.stat().st_size
                   if p.path.exists() else 0)
        for item in paths:
            if item is best:
                continue
            duplicated_paths.add(item.path)
            _add(by_cat, "duplicates", HealthIssue(
                "duplicates", item.path,
                _message("diagnostics.health.exact_duplicate", fallback="Exact duplicate (MD5 matches another file)"),
            ))

    seen_sem: dict[tuple[str, str, str, str], list[HealthItem]] = {}
    for item in items:
        if not item.read_ok or item.path in duplicated_paths:
            continue
        key = (_norm(item.artist), _norm(item.album),
               _norm(item.disc_number), _norm(item.title))
        if key[0] and key[3]:
            seen_sem.setdefault(key, []).append(item)
    for key, paths in seen_sem.items():
        if len(paths) < 2:
            continue
        best = max(paths, key=lambda p: p.path.stat().st_size
                   if p.path.exists() else 0)
        for item in paths:
            if item is best:
                continue
            _add(by_cat, "duplicates", HealthIssue(
                "duplicates", item.path,
                _message("diagnostics.health.semantic_duplicate", {"title": key[3]}, fallback=f'Semantic duplicate “{key[3]}”'),
            ))

    # 4. Имя файла не совпадает с тегом title.
    for item in items:
        if not item.read_ok:
            continue
        stem = item.path.stem
        title = item.title
        if not _norm(title):
            continue
        if _name_norm(stem) != _name_norm(title):
            _add(by_cat, "mismatch", HealthIssue(
                "mismatch", item.path,
                _message("diagnostics.health.filename_mismatch", {"filename": stem, "title": item.title}, fallback=f'Filename “{stem}” differs from title tag “{item.title}”'),
            ))

    # 5. Loose-файлы в корне библиотеки (вне структуры Artist/Album).
    root = output_dir if output_dir is not None else _common_root(items)
    for item in items:
        if not item.read_ok:
            continue
        if root is not None and item.path.parent == root:
            _add(by_cat, "loose", HealthIssue(
                "loose", item.path, _message("diagnostics.health.loose_file", fallback="File is at library root, outside Artist/Album folders"),
            ))

    # Собираем сводку.
    for cat_list in by_cat.values():
        issues.extend(cat_list)
    issues.sort(key=lambda i: (i.path, i.category))
    report.issues = issues
    report.issues_by_category = by_cat

    # Оценка здоровья: 100 минус штрафы за каждую категорию.
    report.score = _score(report, by_cat)
    return report


def _add(by_cat: dict[str, list[HealthIssue]], category: str, issue: HealthIssue) -> None:
    by_cat.setdefault(category, []).append(issue)


def run_health_check(output_dir: Path, include_inbox: bool = False) -> HealthReport:
    """Просканировать библиотеку и собрать отчёт health-check.

    ``include_inbox`` — учитывать и файлы, ещё не перемещённые из ``Inbox``.
    """
    items = scan_items(output_dir, include_inbox=include_inbox)
    return collect_issues(items, output_dir=output_dir)


def fix_issues(output_dir: Path) -> tuple[int, int]:
    """Исправить расхождения имён и структуры.

    Для каждого пригодного к чтению файла переименовывает/перемещает его так,
    чтобы имя совпадало с тегом ``title`` и файл лежал в структуре
    ``Artist[/Album]``. Покрывает категории ``mismatch`` (имя ≠ тег) и ``loose``
    (файл в корне). Возвращает (исправлено, ошибок).
    """
    from .utils import sanitize_name

    fixed = 0
    errors = 0
    for item in scan_items(output_dir):
        if not item.read_ok:
            continue
        artist = item.artist.strip() or "Неизвестный исполнитель"
        album = item.album.strip()
        title = item.title.strip()
        disc = item.disc_number.strip()
        target_dir = output_dir / sanitize_name(artist)
        if album and album != artist:
            target_dir = target_dir / sanitize_name(album)
        # Multi-disc: кладём треки в подкаталог Disc N, чтобы одинаковые названия
        # на разных дисках не коллизировали. Single-disc — плоская структура.
        disc_num = _parse_disc_num(disc)
        if disc_num is not None:
            target_dir = target_dir / f"Disc {disc_num}"
        target = target_dir / f"{sanitize_name(title)}{item.path.suffix.lower()}"

        if _nfc(str(item.path)) == _nfc(str(target)):
            continue
        if target.exists():
            errors += 1
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            item.path.rename(target)
            fixed += 1
        except Exception:
            errors += 1
    return fixed, errors


def _common_root(items: list[HealthItem]) -> Path | None:
    """Общий корневой каталог всех файлов (для проверки loose-файлов)."""
    if not items:
        return None
    root = items[0].path.parent
    for item in items[1:]:
        parent = item.path.parent
        while parent != root and root not in parent.parents:
            root = root.parent
    return root


def _score(report: HealthReport, by_cat: dict[str, list[HealthIssue]]) -> int:
    """Считаем оценку здоровья от 100 (чем меньше проблем — тем лучше)."""
    penalties = {
        "unreadable": 8,
        "missing": 1,
        "duplicates": 3,
        "mismatch": 2,
        "loose": 2,
    }
    score = 100
    for category, penalty in penalties.items():
        score -= len(by_cat.get(category, [])) * penalty
    return max(0, score)


# --- Вывод ---------------------------------------------------------------


def render_health(report: HealthReport, console, max_preview: int = 20) -> None:
    """Нарисовать отчёт health-check в переданную rich-консоль."""
    from rich.table import Table

    _render_summary(report, console)

    order = ["unreadable", "missing", "duplicates", "mismatch", "loose"]
    labels = {
        "unreadable": "Unreadable files",
        "missing": "Missing tags",
        "duplicates": "Duplicates",
        "mismatch": "Filename differs from title tag",
        "loose": "Files outside artist/album folders",
    }
    for category in order:
        issues = report.issues_by_category.get(category, [])
        if not issues:
            continue
        table = Table(title=f"{labels[category]} ({len(issues)})")
        table.add_column("File", style="bold")
        table.add_column("Problem", style="dim")
        for issue in issues[:max_preview]:
            table.add_row(issue.path.name, format_message(issue.message))
        if len(issues) > max_preview:
            table.add_row("…", f"and {len(issues) - max_preview} more")
        console.print(table)
        console.print()


def _render_summary(report: HealthReport, console) -> None:
    from rich.table import Table

    labels = {
        "unreadable": "Unreadable files",
        "missing": "Missing tags",
        "duplicates": "Duplicates",
        "mismatch": "Filename differs from tag",
        "loose": "Files outside artist folders",
    }
    table = Table(title="Library health check")
    table.add_column("Category", style="green")
    table.add_column("Issues", justify="right")

    table.add_row("Tracks checked", str(report.total))
    for category, label in labels.items():
        count = report.count(category)
        color = "red" if count else "green"
        table.add_row(label, f"[{color}]{count}[/{color}]")
    total = len(report.issues)
    table.add_row("Total issues", str(total))
    table.add_row("Health", f"[bold]{report.score}%[/bold]")
    console.print(table)
    console.print()
