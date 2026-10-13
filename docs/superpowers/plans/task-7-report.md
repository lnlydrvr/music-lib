# Task 7 review-fix report

## 2026-10-15 — reviewer findings resolved

- Completed both frontend job catalogs with every route-produced `jobs.*` code
  from the frozen key map (lines 247–295). Corrected existing job labels to
  their frozen EN/RU wording and added matching ICU arguments for progress,
  batch, Shazam, recommendation, compression, Primuse, lyrics, and auth
  descriptors.
- Added a backend regression that extracts `jobs.*` literals from
  `src/web/routes.py`, requires each to be an EN/RU catalog leaf, and compares
  ICU argument names across locales. This prevents a producer from shipping an
  unrenderable descriptor.
- `YtmDownloadResult.items[].error` now accepts `RenderableMessage`. Search
  does not construct `Error` from a descriptor: known descriptors and legacy
  strings are passed unchanged to the toast boundary. Its YouTube Music progress
  prefers `d.message` and falls back to legacy `d.msg`.
- Recommendation failures retain `RenderableMessage` in component state and
  resolve it during render. The disconnected-account view is selected only from
  `JobError.renderableMessage.code`, never from localized Russian prose.
- Added consumer regressions for known and legacy YTM result errors, plus a
  recommendation snapshot descriptor whose `{index, total}` payload survives a
  Russian-to-English locale switch and renders in the new locale.

## Verification — 2026-10-15

- `pytest tests/test_job_catalogs.py tests/test_web_jobs.py -q` — 3 passed.
- `cd frontend && npm test -- searchScreen.test.tsx recommendScreen.test.tsx i18n.test.ts jobs.test.ts` — 57 passed.
- `pytest` — 759 passed; two existing upstream TestClient/httpx deprecation
  warnings.
- `cd frontend && npm test` — 35 files, 245 tests passed.
- `cd frontend && npm run build` — passed (`tsc --noEmit` and Vite production
  build).

## 2026-10-15 — re-review findings resolved

- All three non-YouTube-Music download progress callbacks in `SearchScreen`
  now prefer canonical `d.message` and fall back to legacy `d.msg`.
- Added a Search regression for a structured canonical-only progress message;
  it verifies that the localized progress label is rendered.
- Recommendation disconnected-account detection now also examines the
  `RenderableMessage` returned by `asRenderableMessage(e)`. This covers the
  `ApiError` thrown by the initial `POST /api/recommend/generate`, before a
  background job exists, while retaining the explicit `JobError` path.
- Added a regression with a rejected `startJob` carrying the actual `ApiError`;
  it verifies the connected-state empty view and the Settings action.

## Verification — 2026-10-15 (re-review)

- `cd frontend && npm test -- searchScreen.test.tsx recommendScreen.test.tsx`
  — 2 files, 29 tests passed.
- `cd frontend && npm run build` — passed (`tsc --noEmit` and Vite production
  build).

## 2026-10-15 — catalog checker false-positive fix

- The fallback checker now starts with no recognized call names and adds names
  only for explicit `message` imports from `messages` or `src.messages`.
  A local function named `message`, or an identically named helper from another
  module, is no longer treated as the descriptor factory.
- Added a regression fixture with a local `def message(..., fallback='')` and a
  blank fallback call; it produces no finding. Direct and aliased
  `src.messages` import fixtures remain covered.
- Sorted standard-library imports in `tests/test_job_catalogs.py`.

## Verification — 2026-10-15 (catalog checker false-positive fix)

- `pytest tests/test_job_catalogs.py` — 6 passed.
- `pytest` — 768 passed; two upstream FastAPI/Starlette TestClient/httpx and
  AnyIO deprecation warnings.
