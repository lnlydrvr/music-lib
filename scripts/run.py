"""Лаунчер обычного запуска: при необходимости собирает фронтенд и запускает приложение.

python scripts/run.py [--port N] [--host H] [--no-browser]
"""
from __future__ import annotations

import subprocess
import sys

from launcher_lib import (ensure_npm, need_build, need_npm_install,
                          print_logo, project_root, run_cmd)


def chromium_installed() -> bool:
    """Check for Playwright's Chromium without importing optional packages."""
    try:
        from src.lucida.cf import chromium_installed as check_chromium

        return check_chromium()
    except Exception:
        return False


def playwright_installed() -> bool:
    """Check if the Playwright CLI dependency is available for installation."""
    try:
        from importlib.util import find_spec

        return find_spec("playwright") is not None
    except (ImportError, ValueError):
        return False


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    print_logo()
    root = project_root()
    frontend = root / "frontend"

    npm = ensure_npm()
    if npm is None:
        return 1

    if need_npm_install(frontend):
        print("Устанавливаю зависимости фронтенда (npm ci)…")
        code = run_cmd([npm, "ci"], frontend)
        if code != 0:
            return code

    if need_build(root):
        print("Собираю фронтенд (npm run build)…")
        code = run_cmd([npm, "run", "build"], frontend)
        if code != 0:
            return code
    else:
        print("Фронтенд актуален — сборка не нужна.")

    if not chromium_installed() and playwright_installed():
        print("Устанавливаю Chromium для Lucida (если установка не удастся, запуск продолжится)…")
        code = run_cmd(
            [sys.executable, "-m", "playwright", "install", "chromium"], root
        )
        if code != 0:
            print("Не удалось установить Chromium; продолжаю запуск приложения.")

    return subprocess.call([sys.executable, str(root / "app.py"), *argv],
                           cwd=str(root))


if __name__ == "__main__":
    sys.exit(main())
