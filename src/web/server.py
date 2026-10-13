"""FastAPI app + запуск локального сервера."""

from __future__ import annotations

import threading
import webbrowser
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .routes import core, library, misc, search_rt, ytm

#: Имя каталога собранного React SPA (для тестов подменяется на несуществующий).
_DIST_DIRNAME = "dist"

#: Страница-подсказка, когда dist не собран (dev-checkout без Node):
#: API работает, но UI отдавать нечего.
_HINT_HTML = {
    "en": """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>music-lib — frontend not built</title>
<style>
  body { background: #111418; color: #dfe3e8; font: 15px/1.6 system-ui, sans-serif;
         display: flex; min-height: 100vh; margin: 0; align-items: center;
         justify-content: center; }
  main { max-width: 34rem; padding: 2rem; }
  h1 { font-size: 1.2rem; margin: 0 0 .75rem; }
  code { background: #1d232b; border-radius: 6px; padding: .15rem .45rem;
         font-size: .9em; }
  pre { background: #1d232b; border-radius: 8px; padding: .9rem 1rem;
        overflow-x: auto; }
  pre code { background: none; padding: 0; }
</style>
</head>
<body>
<main>
  <h1>Frontend not built</h1>
  <p>The API works, but the interface has not been built. Run the launcher to
  build it automatically:</p>
  <pre><code>python scripts/run.py</code></pre>
  <p>Or build it manually: <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>.
  For development, run <code>python scripts/dev.py</code> (Vite, live reload).</p>
</main>
</body>
</html>
""",
    "ru": """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>music-lib — фронтенд не собран</title>
<style>
  body { background: #111418; color: #dfe3e8; font: 15px/1.6 system-ui, sans-serif;
         display: flex; min-height: 100vh; margin: 0; align-items: center;
         justify-content: center; }
  main { max-width: 34rem; padding: 2rem; }
  h1 { font-size: 1.2rem; margin: 0 0 .75rem; }
  code { background: #1d232b; border-radius: 6px; padding: .15rem .45rem;
         font-size: .9em; }
  pre { background: #1d232b; border-radius: 8px; padding: .9rem 1rem;
        overflow-x: auto; }
  pre code { background: none; padding: 0; }
</style>
</head>
<body>
<main>
  <h1>Фронтенд не собран</h1>
  <p>API работает, но интерфейс ещё не собран. Запустите лаунчер —
  он соберёт UI автоматически:</p>
  <pre><code>python scripts/run.py</code></pre>
  <p>Или вручную: <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>.
  Для разработки — <code>python scripts/dev.py</code> (Vite, обновление на лету).</p>
</main>
</body>
</html>
""",
}


def _hint_language(accept_language: str | None) -> str:
    """Choose a supported standalone-page language from Accept-Language."""
    candidates: list[tuple[float, int, str]] = []
    for index, item in enumerate((accept_language or "").split(",")):
        parts = [part.strip() for part in item.split(";")]
        tag = parts[0].lower()
        if not tag:
            continue
        quality = 1.0
        for parameter in parts[1:]:
            name, separator, value = parameter.partition("=")
            if name.strip().lower() != "q" or not separator:
                continue
            try:
                quality = float(value.strip())
            except ValueError:
                quality = 0.0
        if not 0 < quality <= 1:
            continue
        language = tag.split("-", 1)[0]
        if language in _HINT_HTML:
            candidates.append((-quality, index, language))
    return min(candidates)[2] if candidates else "en"


def _spa_root() -> Path | None:
    """Корень статики SPA: собранный React-dist (``npm run build`` в frontend/).

    Dist нет (dev-checkout без Node) — ``None``: API продолжает работать,
    а на ``/`` отдаётся страница-подсказка со статусом 503.
    """
    dist = Path(__file__).parent / _DIST_DIRNAME
    return dist if dist.is_dir() else None


def create_app() -> FastAPI:
    """Собрать приложение: API-роуты + статика SPA из dist."""
    app = FastAPI(title="music-lib", docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(core)
    app.include_router(library)
    app.include_router(search_rt)
    app.include_router(misc)
    app.include_router(ytm)

    spa_root = _spa_root()
    if spa_root is not None:
        app.mount("/", StaticFiles(directory=str(spa_root), html=True), name="spa")
    else:

        @app.get("/", include_in_schema=False)
        def spa_build_hint(request: Request) -> HTMLResponse:
            language = _hint_language(request.headers.get("accept-language"))
            return HTMLResponse(
                _HINT_HTML[language],
                status_code=503,
                headers={"Content-Language": language, "Vary": "Accept-Language"},
            )

    return app


def _lan_ips() -> list[str]:
    """Вернуть локальные IPv4-адреса (для доступа с телефона по Wi-Fi)."""
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return [s.getsockname()[0]]
    except OSError:
        return []
    finally:
        s.close()


def _print_qr(url: str) -> None:
    """Напечатать QR-код в терминал (для перехода с телефона)."""
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception:
        pass  # QR-код — опция, без него продолжаем работать


def run_server(host: str = "127.0.0.1", port: int = 0, open_browser: bool = True) -> None:
    """Запустить uvicorn на заданном адресе и (опционально) открыть браузер."""
    import socket

    if port == 0:
        with socket.socket() as s:
            s.bind((host, 0))
            port = s.getsockname()[1]

    browser_url = f"http://127.0.0.1:{port}/"
    if host in ("0.0.0.0", "::"):
        ips = _lan_ips()
        print("music-lib: слушаем все интерфейсы.")
        if ips:
            print("Доступ по локальной сети (телефон в том же Wi-Fi):")
            for ip in ips:
                url = f"http://{ip}:{port}/"
                print(f"  {url}")
                print("  Сканируйте QR-код:")
                _print_qr(url)
        else:
            print("Локальные адреса не найдены — проверьте сеть.")
        print("Внимание: сервер без авторизации. Используйте только в доверенной сети!")
    else:
        browser_url = f"http://{host}:{port}/"
        print(f"music-lib: {browser_url}")

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(browser_url)).start()

    import uvicorn

    uvicorn.run(create_app(), host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run_server()
