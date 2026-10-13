"""Лаунчер обычного запуска: при необходимости собирает фронтенд и запускает приложение.

python scripts/run.py [--port N] [--host H] [--no-browser]
"""
from __future__ import annotations

import subprocess
import sys

from launcher_lib import (ensure_npm, need_build, need_npm_install,
                          print_logo, project_root, run_cmd)


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

    return subprocess.call([sys.executable, str(root / "app.py"), *argv],
                           cwd=str(root))


if __name__ == "__main__":
    sys.exit(main())
