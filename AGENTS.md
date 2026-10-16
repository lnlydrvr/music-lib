# AI Agent Instructions

## Before you start

- Read the root `README.md` for the user workflow and
  [`docs/en/PRODUCT.md`](docs/en/PRODUCT.md) for product scope and principles.
- For UI changes, consult [`docs/en/DESIGN.md`](docs/en/DESIGN.md) and
  `frontend/src/styles.css`. CSS is the source of truth for exact design-token
  values.
- Treat `docs/en/PRODUCT.md` and `docs/en/DESIGN.md` as the source of truth for
  product and design documentation. Whenever you change either English
  document, update its Russian counterpart in `docs/ru/` to keep both versions
  in sync.
- Check `git status` before editing. Do not overwrite or remove unfamiliar user
  changes.
- Follow existing code conventions and avoid adding dependencies without a
  clear need.

## Project commands

### Install and run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
playwright install chromium  # optional; the launcher attempts this for Lucida
python scripts/run.py
```

For frontend development, install dependencies and start the dev server:

```bash
cd frontend
npm ci
npm run dev
```

The `python scripts/run.py` launcher installs frontend dependencies and builds
the UI when needed. It also attempts to install Playwright Chromium if the
Python package is available and the browser is missing; failure to install it
does not prevent app startup. Lucida access preparation requires a visible
browser and a local graphical session. Running `python app.py` directly requires
the `src/web/dist` directory to have been built in advance.

### Checks

```bash
pytest
cd frontend && npm test
cd frontend && npm run build
python scripts/check_locales.py
python scripts/check_copy.py
cd frontend && npm run check:i18n-keys
```

`npm run build` type-checks TypeScript and creates a production build.

## Localization authoring

- New user-facing frontend text must use a statically typed `t()` key from
  `frontend/src/locales/en.json` and have a translation in every supported
  locale in the same change. Do not translate track metadata, paths, provider
  responses, technical identifiers, or test fixture data.
- New backend-owned user messages must use `src.messages.message(code, params,
  fallback=...)`; keep the structured code and parameters stable and supply a
  readable fallback for non-UI clients. Logs are not UI messages.
- Before submitting localization work, run `python scripts/check_locales.py`,
  `python scripts/check_copy.py`, and `cd frontend && npm run check:i18n-keys`.
  The copy guardrail intentionally scans only JSX text/user-facing attributes
  and calls bound to known message constructors; it follows imports and local
  shadowing so unrelated same-named functions are ignored. Any reported
  candidate must be translated, added as a documented data/technical exemption,
  or left visible in the validation report.

## Architecture

- `src/` — Python logic for downloads, search, metadata, tags, configuration,
  recommendations, and the Lucida adapter in `src/lucida/`.
- `src/web/` — FastAPI routes, API serialization, and background jobs.
- `frontend/src/` — React and TypeScript UI; Vite builds it into `src/web/dist`.
- `scripts/run.py` — app launcher; `scripts/dev.py` — development startup for
  FastAPI and Vite.
- `tests/` — Python and API tests; `frontend/tests/` — component and frontend
  logic tests.

### Main Python modules

| Module | Purpose |
| --- | --- |
| `config.py` | Configuration, library path, and default settings. |
| `downloader.py`, `search.py` | Search through yt-dlp and audio downloads. |
| `fetcher.py`, `providers.py` | Fetch metadata and cover art from external sources. |
| `tagger.py`, `lyrics.py` | Read and write audio tags and handle lyrics. |
| `pipeline.py`, `services.py` | Operation pipelines and library services. |
| `health.py`, `lint.py`, `normalize.py`, `quality.py` | Library diagnostics and building/applying fix plans. |
| `ytmusic.py`, `recommend.py`, `shazam_import.py` | YouTube Music integration, recommendations, and Shazam list import. |
| `lucida/` | Lucida service adapters, access preparation, search, download, and library ingestion. |
| `web/routes.py`, `web/jobs.py`, `web/serialize.py` | API routes, background jobs, and response serialization. |

For implementation details, consult the relevant source and tests. This table
intentionally does not duplicate module APIs.

## Important conventions

- The server listens on `127.0.0.1` by default. Do not change this without an
  explicit requirement; the app has no built-in authentication for network
  access.
- The library directory is resolved in this order: `MUSIC_LIB_DIR`, the legacy
  `MUSIC_DL_DIR`, `~/.config/music-lib/config.json`, then an available iCloud
  folder or `~/Music`.
- The launcher may attempt a Playwright Chromium installation for Lucida; this
  is optional for the rest of the application. The user must explicitly prepare
  Lucida access in the visible browser.
- Do not add secrets or user data to the repository. Configuration, cookies,
  and YouTube Music authorization must remain in user directories.
- Bulk library changes must provide a reviewable plan before they are applied.
  Handle conflicts per item and preserve idempotency where the operation
  supports it.
- External services may throttle requests or become unavailable. Follow the
  existing timeout, retry, and throttling mechanisms.
- UI changes must preserve light and dark themes, keyboard focus, touch target
  sizes, and `prefers-reduced-motion` support.
- Do not claim the project is licensed: there is no `LICENSE` file yet.
