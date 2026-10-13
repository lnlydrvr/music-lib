"""Общие помощники лаунчеров scripts/run.py и scripts/dev.py."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

NPM_INSTALL_HINT = (
    "npm не найден. Для сборки фронтенда нужен Node.js:\n"
    "  macOS:   brew install node  (или https://nodejs.org)\n"
    "  Linux:   sudo apt install nodejs npm  (или dnf install nodejs npm)\n"
    "  Windows: winget install OpenJS.NodeJS  (или https://nodejs.org)"
)


LOGO = r"""
                     _           _ _ _
 _ __ ___  _   _ ___(_) ___     | (_) |__
| '_ ` _ \| | | / __| |/ __|____| | | '_ \
| | | | | | |_| \__ \ | (_|_____| | | |_) |
|_| |_| |_|\__,_|___/_|\___|    |_|_|_.__/
"""


def print_logo() -> None:
    """Напечатать ASCII-лого music-lib."""
    print(LOGO, flush=True)


def project_root() -> Path:
    """Корень репозитория (каталог с pyproject.toml)."""
    return Path(__file__).resolve().parent.parent


def find_npm() -> str | None:
    """Путь к npm (Windows: npm.cmd) или None."""
    return shutil.which("npm") or shutil.which("npm.cmd")


def ensure_npm() -> str | None:
    """npm или None — с подсказкой по установке в stderr."""
    npm = find_npm()
    if npm is None:
        print(NPM_INSTALL_HINT, file=sys.stderr)
    return npm


def run_cmd(cmd: list[str], cwd: Path) -> int:
    """Прогнать команду в каталоге, вернуть код завершения."""
    print(f"$ {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(cwd))


def need_npm_install(frontend: Path) -> bool:
    """Нужен ли `npm ci`: node_modules нет или lock-файл новее установки."""
    node_modules = frontend / "node_modules"
    if not node_modules.is_dir():
        return True
    marker = node_modules / ".package-lock.json"
    lock = frontend / "package-lock.json"
    if not marker.is_file():
        return True
    return lock.is_file() and lock.stat().st_mtime > marker.stat().st_mtime


def _build_inputs(frontend: Path) -> list[Path]:
    files = [
        frontend / "index.html",
        frontend / "package.json",
        frontend / "package-lock.json",
        frontend / "vite.config.ts",
        frontend / "tsconfig.json",
    ]
    src = frontend / "src"
    if src.is_dir():
        files.extend(p for p in src.rglob("*") if p.is_file())
    return [f for f in files if f.is_file()]


def need_build(root: Path) -> bool:
    """Нужна ли сборка: dist/index.html нет или исходники фронтенда новее."""
    marker = root / "src" / "web" / "dist" / "index.html"
    if not marker.is_file():
        return True
    stamp = marker.stat().st_mtime
    return any(p.stat().st_mtime > stamp for p in _build_inputs(root / "frontend"))
