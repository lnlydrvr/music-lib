# Lucida Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Lucida" tab to the Discover screen that searches Qobuz and Amazon through lucida.to and downloads selected albums/tracks into the library, using a client we own from scratch (no dependency on the `lucidadl` package).

**Architecture:** A new first-party Python package `src/lucida/` talks to lucida.to over `httpx` carrying a Cloudflare `cf_clearance` cookie harvested by Playwright. Clearance acquisition is the only place a browser runs. Downloads stream into a temp directory and are ingested into the library through the existing `pipeline.move_to_library`. A FastAPI router exposes status/setup/search/download, and a React screen renders search results with per-item download.

**Tech Stack:** Python 3, FastAPI, `httpx[http2]`, `playwright` (+ Chromium), `pyjson5`, pytest; React 19, TypeScript, Vite, i18next, Vitest.

**Status:** v1, agreed with product owner.

## Scope

- Services in v1: **Qobuz and Amazon** (with Amazon country fallbacks).
- **No playlists** in v1.
- Cloudflare handled by **our** Playwright + Chromium; **fail-fast** when clearance is missing/expired, with an explicit "Prepare access" button (the browser never opens by itself).
- SvelteKit data blob parsed with **`pyjson5`**, hidden behind `page.py` so it can be swapped for a hand-rolled parser later.
- Search UI: **search + result list** (albums first, then tracks); download by the selected item's `url`.
- Tags: **native, left untouched** (nothing rewritten, `comment` included).
- Output: **temp → library** via `pipeline.move_to_library`; if the target file exists, skip. No `.m3u8` archive.

## Decisions and external risk

- The repository is private; downloading via Qobuz/Amazon ripping is a deliberate, accepted decision.
- External risk does **not** disappear by owning the client: lucida.to's undocumented API and Cloudflare can still change. Owning the code removes third-party churn and side effects (for example `~/.local/share/lucidadl`) and gives us one module to fix.
- Cloudflare requires a real browser. `playwright` + Chromium remain our dependencies.

## Global Constraints

- The server listens on `127.0.0.1` by default; do not change this.
- No secrets, cookies, or user data in the repository. Clearance and logs live in the user config directory.
- New user-facing frontend text uses statically typed `t()` keys in `frontend/src/locales/en.json` with translations in every supported locale in the same change.
- New backend-owned user messages use `src.messages.message(code, params, fallback=...)`.
- The browser must never launch implicitly during search or download; only the explicit `setup` action (visible window) may launch it.
- UI changes must preserve light and dark themes, keyboard focus, touch target sizes, and `prefers-reduced-motion`.
- Keep English `docs/en/PRODUCT.md` and Russian `docs/ru/PRODUCT.md` in sync (AGENTS.md). Russian interface copy is authored through the `sasha` skill.
- Required checks: `pytest`, `cd frontend && npm test`, `cd frontend && npm run build`, `python scripts/check_locales.py`, `python scripts/check_copy.py`, `cd frontend && npm run check:i18n-keys`.

## Review Focus

1. **Implicit browser launch** — a stale clearance during a run must raise `LucidaAccessRequired`, never open a window. Cover with a test that asserts no Playwright call happens on 403.
2. **Result/download mismatch** — downloads must use the selected item's `url`, not a re-resolved text query. Cover with a test that the `url` handed to `/api/load` equals the searched item's `url`.
3. **Import-time side effects** — importing our package must not create directories or import Playwright/httpx at module load. `available()` uses `importlib.util.find_spec` only.
4. **Ingest safety** — existing library files are skipped, partial/failed downloads are removed from temp, and a failed item never reports success.
5. **Localization round-trip** — new RU/EN keys pass the locale, copy, and i18n-key checks.

---

## File map and ownership

### New files

- `src/lucida/__init__.py` — public adapter used by the app: `available`, `status`, `search`, `download`, `setup`.
- `src/lucida/paths.py` — app-data paths for `clearance.json` and `run.log` under the music-lib config directory.
- `src/lucida/cf.py` — Playwright clearance acquisition plus `load_clearance`/`save_clearance`.
- `src/lucida/http.py` — `httpx` client, headers (Cookie + Chrome UA), retries, `403 -> LucidaAccessRequired`.
- `src/lucida/page.py` — SvelteKit blob extraction (`pyjson5`), search-result parsing, release-page parsing, single-track token decode.
- `src/lucida/download.py` — `POST /api/load` + poll + stream to disk.
- `src/lucida/services.py` — service normalization and country defaults (`qobuz -> NL`, `amazon -> ""`), fallback storefronts.
- `src/lucida/ingest.py` — move temp files into the library via `pipeline.move_to_library`, skip-if-exists.
- `frontend/src/views/LucidaScreen.tsx` — the tab screen.
- `tests/test_lucida.py` — client unit tests.
- `frontend/tests/lucidaScreen.test.tsx` — screen tests.

### Existing files to modify

- `pyproject.toml` — add `httpx[http2]`, `playwright`, `pyjson5`.
- `src/config.py` — settings keys and getters `lucida_service`, `lucida_country`, `lucida_jobs`.
- `src/web/routes.py` — new `lucida` router.
- `src/web/jobs.py` — reuse `JobManager` for setup/search/download streaming.
- `src/messages.py` — access/error/unavailable message codes (RU + EN).
- `src/downloader.py` / `src/pipeline.py` — reuse `move_to_library`; no new archive logic.
- `frontend/src/views/DiscoverScreen.tsx` — add the `lucida` tab.
- `frontend/src/views/SettingsScreen.tsx` — default service setting.
- `frontend/src/locales/en.json`, `frontend/src/locales/ru.json` — new keys.
- `frontend/tests/i18n.test.ts` — locale parity.
- `docs/en/PRODUCT.md`, `docs/ru/PRODUCT.md` — private legal framing and scope (Qobuz/Amazon, no playlists).

---

## Protocol reference (what `src/lucida/` must implement)

All lucida.to calls run over `httpx` with the `cf_clearance` cookie and a Chrome UA.

1. **Clearance** (`cf.py`): launch a persistent, headed Chromium; navigate to `https://lucida.to/`; wait until the challenge disappears (detect via title, `cf-chl-widget`, `window._cf_chl_opt`, `enable javascript and cookies to continue`); read the `cf_clearance` cookie and `navigator.userAgent`; save and close. `setup` uses a visible window; there is no hidden/auto path in v1.
2. **Blob extraction** (`page.py`): the SvelteKit data blob is delimited by `,{"type":"data","data":` and `,"uses":{"url":1}}];`; parse the slice with `pyjson5`.
3. **Search** (`page.py`): `GET https://lucida.to/search?service=&country=&query=`; find the node holding `tracks`/`albums`; map to `{url, title, artist, album}` (artist joins `artists[].name`, album from `album.title`).
4. **Release page** (`page.py`): `GET https://lucida.to/?url=<svc_url>&country=`; returns page data with `info` (`type` is `track` or `album`), `info.tracks` for albums, and `token` for single tracks. A single-track `token` is base64-decoded twice to yield `csrf`. For Amazon, try storefronts `"", "US", "GB", "JP"` and require tracks with a usable `csrf`.
5. **Start download** (`download.py`): `POST https://lucida.to/api/load?url=/api/fetch/stream/v2` with body `{account:{id:cc|"auto",type:"country"},compat:false,downscale:"original",handoff:true,metadata:true,private:false,token:{expiry,primary,secondary},upload:{enabled:false},url}`; response yields `{handoff, server}`.
6. **Poll and stream** (`download.py`): `GET https://<server>.lucida.to/api/fetch/request/<handoff>` returns JSON with `status`/`message`; on `completed`, `GET .../download` streams the file; extension from `content-type` (fall back to `content-disposition`).

Retry policy: bounded backoff on `429`/`5xx`, honoring `Retry-After`; a `403` raises `LucidaAccessRequired` (no refresh). A stall threshold aborts the poll.

---

## Tasks

### Task 1: Package skeleton and paths

- [ ] Create `src/lucida/__init__.py`, `paths.py`, `services.py`.
- [ ] `paths.py` resolves the music-lib config dir and exposes `CLEARANCE_PATH` and `LOG_PATH`; it must not create directories at import time.
- [ ] `services.py` defines `normalize_service`, `default_country` (`qobuz -> "NL"`, `amazon -> ""`), and `AMAZON_STOREFRONTS = ["", "US", "GB", "JP"]`.
- [ ] Fully lazy: no import of `httpx`, `playwright`, or `pyjson5` at module load.

### Task 2: Cloudflare clearance (`cf.py`)

- [ ] `chromium_installed()` uses Playwright only when explicitly called.
- [ ] `acquire(visible: bool)` launches a persistent Chromium (headed), navigates to lucida.to, waits out the challenge, harvests `cf_clearance` + UA, saves to `CLEARANCE_PATH`, closes.
- [ ] `load_clearance()` / `save_clearance()` read/write a JSON `{cf_clearance, ua, ts}` file; missing/invalid returns `(None, None)`.
- [ ] Surface `BrowserClosed`/`RuntimeError` as an access error message.

### Task 3: HTTP client and page parsing (`http.py`, `page.py`)

- [ ] `http.py`: `AsyncClient(http2=True)`, headers with `Cookie: cf_clearance=...` and Chrome UA, `GET` with retries; `403` raises `LucidaAccessRequired`.
- [ ] `page.py`: `extract_blob(html)` with the documented delimiters; `parse_search(html)`; `parse_page_data(html)`; `decode_track_token(token)` (double base64, tolerant of non-base64).
- [ ] Capture HTML fixtures for a search page and a release page in `tests/fixtures/` to drive tests without network.

### Task 4: Download orchestration (`download.py`)

- [ ] `start_download(track, expiry, country)` builds the exact `/api/load` body and returns `(handoff, server)`.
- [ ] `run_job(handoff, server, dest_dir, name, on_status, on_bytes)` polls, streams to `dest_dir`, resolves extension, and writes atomically (`.part` then rename); removes `.part` on failure.
- [ ] Retries and stall handling per the protocol reference.

### Task 5: Adapter and ingest (`__init__.py`, `ingest.py`)

- [ ] `available()` uses `importlib.util.find_spec("playwright")` (Chromium presence via `cf.chromium_installed()` when requested) and performs no imports with side effects.
- [ ] `status()` returns `{available, access_ready, chromium_ready, service}` using `load_clearance()` — no browser.
- [ ] `search(query, service)` returns `{albums, tracks}`; raises `LucidaAccessRequired` when clearance is absent.
- [ ] `download(url, kind, service, jobs, progress)` resolves the release page, expands album tracks, downloads each with bounded concurrency, then ingests.
- [ ] `ingest.py` moves each temp file into the library with `pipeline.move_to_library`; returns per-item `ok`/`skip`/`fail`; never reports success without a file.

### Task 6: FastAPI router (`src/web/routes.py`, `src/messages.py`)

- [ ] `GET /api/lucida/status` → status payload.
- [ ] `POST /api/lucida/setup` → background job running `cf.acquire(visible=True)`.
- [ ] `GET /api/lucida/search?q=&service=` → `{albums, tracks}`; maps access errors to structured message codes.
- [ ] `POST /api/lucida/download` → background job `{url, kind, service}` streaming progress through `JobManager`.
- [ ] Add RU + EN message codes for unavailable/access-required/failed states.

### Task 7: Settings (`src/config.py`)

- [ ] Add `lucida_service` (`qobuz`|`amazon`, default `qobuz`), `lucida_country` (optional), `lucida_jobs` (int, default 3) with getters following existing config patterns.

### Task 8: Frontend screen and tab

- [ ] `DiscoverScreen.tsx`: add `"lucida"` to `TABS` and render `<LucidaScreen/>`.
- [ ] `LucidaScreen.tsx`: status line + "Prepare access" button (setup job); service selector; search field; results (albums first, then tracks) with a download action per item; progress via `useOps`/`startJob`. Disable with an explanatory message when unavailable/access is missing.
- [ ] `SettingsScreen.tsx`: default Lucida service.
- [ ] Add RU + EN locale keys (author RU copy via the `sasha` skill).

### Task 9: Tests

- [ ] `tests/test_lucida.py`: fixture-driven search/page parse; token decode; `/api/load` → poll → stream with a mocked transport; `403` raises `LucidaAccessRequired` with no Playwright call; Amazon storefront fallback; ingest skip-if-exists; `available()` performs no import side effects.
- [ ] `tests/test_web_api.py` / `tests/test_web_jobs.py`: status, search error codes, setup and download jobs.
- [ ] `frontend/tests/lucidaScreen.test.tsx` and `frontend/tests/i18n.test.ts` key parity.

### Task 10: Documentation and dependency manifest

- [ ] `pyproject.toml`: add `httpx[http2]`, `playwright`, `pyjson5`.
- [ ] `docs/en/PRODUCT.md` + `docs/ru/PRODUCT.md`: private legal framing and scope (Qobuz/Amazon, no playlists, fail-fast access).
- [ ] Note the `playwright install chromium` step in the run instructions.

---

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| lucida.to API changes | Isolated in `page.py`/`download.py`; the tab degrades to "service unavailable" instead of crashing the app. |
| Cloudflare requires a browser | `cf.py` + Playwright (headed); explicit setup button; fail-fast at runtime. |
| Host without a desktop session | `status` reports unavailable; the tab is disabled with an explanation. |
| Amazon storefronts/tokens | Storefront fallback `"", "US", "GB", "JP"`, require a usable `csrf`. |
| JSON5 parsing | `pyjson5` behind `page.py`, replaceable with a hand-rolled parser. |
| Implicit browser launch | `403` raises `LucidaAccessRequired`; tested that no Playwright call occurs. |
