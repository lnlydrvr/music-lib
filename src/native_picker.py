"""Нативный системный диалог выбора пути для пикера в настройках.

- macOS: свой мини-хелпер на Swift (`macos_picker.swift`), собранный
  один раз в кеш. Он показывает настоящий NSOpenPanel; локализация подключается
  пустым каталогом ``<lang>.lproj`` рядом с бинарём (иначе у голого бинаря
  ``Bundle.main.preferredLocalizations`` всегда ``["en"]``, и кнопки панели
  английские даже на русской системе).
- Windows: PowerShell ``FolderBrowserDialog`` / ``OpenFileDialog``.
- Linux: zenity / kdialog.

Кастомная модалка с деревом папок неудобна на iCloud-путях и не работает
как обычный проводник. Здесь диалог открывает сама ОС на машине с сервером.
Все функции возвращают выбранный путь или ``None`` (отмена/ошибка/нет диалога).
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

#: Интерактивный диалог ОС может висеть, пока пользователь думает.
_DIALOG_TIMEOUT = 300
#: Первичная компиляция swift-хелпера медленная, терпим дольше.
_SWIFT_BUILD_TIMEOUT = 120
_MACOS_SWIFT_NAME = "macos_picker.swift"


def _swift_source() -> Path | None:
    """Путь к исходнику macOS-хелпера (живой источник или файл в wheel)."""
    local = Path(__file__).resolve().with_name(_MACOS_SWIFT_NAME)
    if local.is_file():
        return local
    package = globals().get("__package__") or "src"
    try:
        from importlib.resources import files
        trait = files(package).joinpath(_MACOS_SWIFT_NAME)
        if trait and trait.is_file():
            return Path(str(trait))
    except Exception:
        pass
    return None


def _cache_dir() -> Path:
    return Path.home() / "Library" / "Caches" / "music-lib"


@lru_cache(maxsize=16)
def _macos_helper_binary() -> Path | None:
    """Собрать swift-хелпер один раз в кеш; пересборка при изменении исходника."""
    src = _swift_source()
    if src is None or not shutil.which("swiftc"):
        return None
    digest = hashlib.sha256(src.read_bytes()).hexdigest()[:12]
    cache = _cache_dir() / ("picker-" + digest)
    _ensure_picker_lproj()
    if cache.is_file():
        return cache
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_name(cache.name + ".tmp")
    try:
        proc = subprocess.run(
            ["swiftc", "-O", "-o", str(tmp), str(src)],
            capture_output=True, text=True, timeout=_SWIFT_BUILD_TIMEOUT,
        )
        if proc.returncode != 0:
            tmp.unlink(missing_ok=True)
            return None
        os.replace(tmp, cache)
    except (OSError, subprocess.TimeoutExpired):
        tmp.unlink(missing_ok=True)
        return None
    return cache if cache.is_file() else None


@lru_cache(maxsize=1)
def _system_language() -> str | None:
    """Код системного языка (``ru``, ``en``, ...) из `defaults -g AppleLanguages`."""
    try:
        proc = subprocess.run(
            ["defaults", "read", "-g", "AppleLanguages"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    m = re.search(r'"([A-Za-z]{2,3})(?:-[A-Za-z0-9]+)?"', proc.stdout)
    return m.group(1) if m else None


def _ensure_picker_lproj() -> None:
    """Пометить каталог кеша как бандл с локализацией системного языка.

    У голого бинаря нет ресурсов, поэтому ``Bundle.main.preferredLocalizations``
    всегда ``["en"]`` и кнопки NSOpenPanel английские даже при русской системе.
    Пустой каталог ``<lang>.lproj`` рядом с бинарём регистрирует локализацию, и
    AppKit выбирает язык по системному ``AppleLanguages``.
    """
    lang = _system_language()
    if not lang:
        return
    try:
        (_cache_dir() / (lang + ".lproj")).mkdir(parents=True, exist_ok=True)
    except OSError:
        pass


def _macos_pick(kind: str, start: str | None) -> str | None:
    helper = _macos_helper_binary()
    if helper is None:
        return None
    args = [str(helper), "--kind", kind]
    if start:
        args += ["--start", start]
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=_DIALOG_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = proc.stdout.strip()
    return out or None


def _windows_pick(kind: str, start: str | None) -> str | None:
    if kind == "file":
        dlg = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$d=New-Object System.Windows.Forms.OpenFileDialog; "
            f"$d.InitialDirectory='{_powershell_quote(start)}'; "
            "if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK)"
            "{ $d.FileName }"
        )
    else:
        dlg = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$d=New-Object System.Windows.Forms.FolderBrowserDialog; "
            f"$d.SelectedPath='{_powershell_quote(start)}'; "
            "if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK)"
            "{ $d.SelectedPath }"
        )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", dlg],
            capture_output=True, text=True, timeout=_DIALOG_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = proc.stdout.strip()
    return out or None


def _powershell_quote(path: str) -> str:
    return (path or "").replace("'", "''")


def _unix_pick(kind: str, start: str | None) -> str | None:
    if shutil.which("zenity"):
        args = ["zenity", "--file-selection"]
        if kind == "folder":
            args.append("--directory")
        if start:
            args.append("--filename=" + start + ("/" if kind == "folder" else ""))
    elif shutil.which("kdialog"):
        args = ["kdialog", "--getopenfilename" if kind == "file" else "--getexistingdirectory"]
        if start:
            args.append(start)
    else:
        return None
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                              timeout=_DIALOG_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = proc.stdout.strip()
    return out or None


def default_location(kind: str, start: str | None) -> str | None:
    """Папка, в которой системный диалог откроется изначально.

    Для ``file`` на вход может прийти полный путь к файлу — тогда берём его
    каталог. Несуществующий `start` не ломает диалог: для file уходит dirname,
    для папки — сам start (как запрошено, ОС покажет ошибку стандартно).
    """
    if not start:
        return None
    path = os.path.expanduser(start)
    if os.path.isdir(path):
        return start
    if kind == "file":
        parent = os.path.dirname(path)
        return parent or None
    return start


def pick_path(kind: str = "folder", start: str | None = None) -> str | None:
    """Выбрать путь нативным диалогом. ``kind`` — ``folder`` или ``file``.

    Стартовая папка необязательна (для ``file`` можно передать и путь к файлу —
    диалог откроется в его каталоге). Отмена/ошибка/отсутствие диалога → ``None``
    (вызывающий код молча возвращается или падает в кастомный пикер).
    """
    default = default_location(kind, start)
    if sys.platform == "darwin":
        return _macos_pick(kind, default)
    if sys.platform.startswith("win"):
        return _windows_pick(kind, default)
    return _unix_pick(kind, default)