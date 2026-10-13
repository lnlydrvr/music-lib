"""Точка входа music-lib (Web UI).

Запускает локальный FastAPI-сервер и открывает браузер.
```
python app.py                 # открывает SPA
python app.py --port 9000
python app.py --no-browser
python app.py --host 0.0.0.0  # доступ по локальной сети (телефон по Wi-Fi)
music-lib                     # после pip install -e .
```
"""
from __future__ import annotations

import argparse

from .web.server import run_server


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="music-lib",
        description="Web-интерфейс music-lib (FastAPI + SPA).",
    )
    parser.add_argument("--port", type=int, default=0,
                        help="порт сервера (0 = случайный свободный)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="адрес прослушивания (0.0.0.0 — доступ из локальной сети)")
    parser.add_argument("--no-browser", action="store_true",
                        help="не открывать браузер автоматически")
    args = parser.parse_args()
    run_server(host=args.host, port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()