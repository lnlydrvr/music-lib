"""Dev-лаунчер: FastAPI и Vite одним процессом, UI обновляется на лету.

python scripts/dev.py [--port 8765] [аргументы app.py]

Открывайте http://127.0.0.1:5173/ — Vite проксирует /api на бэкенд.
Ctrl+C останавливает оба сервера.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

from launcher_lib import (ensure_npm, need_npm_install, print_logo,
                          project_root, run_cmd)

VITE_URL = "http://127.0.0.1:5173/"


def _stop(procs: list[subprocess.Popen]) -> None:
    for p in procs:
        if p.poll() is None:
            p.terminate()
    for p in procs:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    parser = argparse.ArgumentParser(
        prog="music-lib-dev",
        description="Dev-режим: FastAPI + Vite с горячей перезагрузкой UI.",
    )
    parser.add_argument("--port", type=int, default=8765,
                        help="порт API-бэкенда (по умолчанию 8765)")
    args, rest = parser.parse_known_args(argv)

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

    vite_env = os.environ.copy()
    vite_env["MUSIC_LIB_DEV_PORT"] = str(args.port)

    print(f"API: {f'http://127.0.0.1:{args.port}/'}")
    print(f"UI:  {VITE_URL} (обновляется на лету)")

    procs: list[subprocess.Popen] = []
    try:
        procs.append(subprocess.Popen(
            [sys.executable, str(root / "app.py"),
             "--port", str(args.port), "--no-browser", *rest],
            cwd=str(root),
        ))
        procs.append(subprocess.Popen([npm, "run", "dev"],
                                      cwd=str(frontend), env=vite_env))
        while True:
            for p in procs:
                code = p.poll()
                if code is not None:
                    print(f"Процесс завершился (код {code}) — останавливаю остальные.")
                    return code
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\nОстанавливаю dev-серверы…")
        return 0
    finally:
        _stop(procs)


if __name__ == "__main__":
    sys.exit(main())
