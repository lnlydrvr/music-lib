# Task 12 — locale persistence and active-job message follow-up

## Completed scope

- Made persisted config writes safe for concurrent in-process callers: a
  reentrant transaction lock covers read-modify-write, and config replacement
  now writes a flushed temporary file before atomically replacing `config.json`.
  The settings API regression deliberately interleaves independent language and
  quality updates and verifies both are retained.
- Changed `fmtDate` to retain the browser's local timezone rather than forcing
  UTC, with subprocess regressions that exercise the real formatter under
  explicit process timezones.
- Added locale-switch regressions for descriptor-based `confirm` and `info`
  bodies, in addition to the existing title/action coverage. Descriptors are
  resolved during React rendering, so an open dialog follows an active locale
  change.
- Serialized language persistence in `SettingsScreen` with a promise chain. A
  deferred `ru → en` regression now rejects the Russian `PUT /api/settings`,
  then proves that the English request starts afterward, succeeds, remains the
  current UI selection, and is the final persisted selection.
- Updated both `MiscScreen` progress callbacks (scan and download) to prefer
  the structured `message` descriptor and fall back to legacy `msg`. Regressions
  verify descriptors reach the local progress panel in each flow.
- Added an active Downloads Dock regression: a mounted Shazam job renders in
  Russian, then rerenders its title and progress message in English after an
  active locale switch, without replacing the job record.
- No changes were made to `frontend/src/lib/jobs.ts` or
  `frontend/src/stores/downloads.ts`; the existing descriptor-based rendering
  contract was sufficient.

### Follow-up hardening

- Legacy-config migration now uses the same process-local reentrant lock as
  `save_config` and `update_config`. It copies the legacy file to a flushed,
  fsynced temporary file in the destination directory and installs it with
  `os.replace`, so an in-process update cannot observe or overwrite a partial
  migration.
- Added a deterministic threaded regression that pauses migration immediately
  before replacement while it still owns the real `RLock`. The test replaces
  `_config_lock` with a delegating context-manager wrapper that signals in the
  updater thread immediately before calling `RLock.acquire()`. It does not
  release replacement until that signal arrives, so the updater has reached
  lock acquisition and is blocked by the migration, rather than merely having
  been started. It then joins both workers, surfaces worker exceptions, and
  verifies both the legacy setting and the update survive. A second regression
  asserts that migration itself uses an in-directory temporary file and atomic
  replacement.
- Legacy literal arguments remain literal for `prompt`, `info`, and `pick`;
  their content is not treated as a localization key after a locale change.
- The UTC-midnight date regression launches child Node/Vitest processes with
  explicit `TZ` values. The fixture imports the real `fmtDate` and sets the
  application `i18n` singleton through `changeLanguage("en")`; it does not
  construct a parallel `Intl.DateTimeFormat` or mock Intl. For
  `2024-01-01T00:00:00Z`, it proves `America/Los_Angeles` yields `12/31/2023`
  and `UTC` yields `01/01/2024`.

## Verification — 2026-10-15

- Focused frontend regression: `cd frontend && npm test -- --run
  tests/settingsScreen.test.tsx` — **13 passed**. The test rejects the deferred
  RU `PUT`, resolves the queued EN `PUT`, and asserts both the persisted EN
  value and the English language select.
- Focused frontend regression: `cd frontend && npm test -- --run
  tests/settingsScreen.test.tsx tests/miscScreen.test.tsx` — **18 passed**.
- `pytest -q tests/test_web_api.py -k 'shazam_scan_matches_via_ytmusic'` —
  **1 passed**.
- `pytest -q tests/test_web_jobs.py tests/test_job_catalogs.py tests/test_locale_catalogs.py tests/test_messages.py` —
  **34 passed**.
- `cd frontend && npm test` — **36 files, 285 tests passed**. Vitest also
  emitted the pre-existing jsdom `HTMLMediaElement.play()` implementation note;
  it did not fail a test.
- `cd frontend && npm run build` — passed (`tsc --noEmit` and Vite production
  build).
- `python scripts/check_locales.py` — passed.
- `python scripts/check_copy.py` — passed within its documented scoped patterns.
- `cd frontend && npm run check:i18n-keys` — passed.
- `pytest` — **795 passed**, with two upstream Starlette/AnyIO deprecation
  warnings.
- `git diff --check` — passed.

### Additional targeted verification — 2026-10-15

- `pytest -q tests/test_config.py tests/test_web_api.py -k 'concurrent_updates
  or settings or cookies or language'` — **44 passed**. The run emitted the
  pre-existing Starlette `TestClient`/AnyIO deprecation warnings.
- `cd frontend && npm test -- --run tests/format.test.ts
  tests/dialogs.test.tsx` — **2 files, 17 tests passed**.
- `python -m py_compile src/config.py src/web/routes.py` and
  `git diff --check` — passed.

The first targeted Vitest invocation used repository-root paths while already
running from `frontend` and therefore found no files; the corrected relative
path invocation above is the authoritative result.

### Follow-up targeted verification — 2026-10-15

- `pytest -q tests/test_config.py -k 'migration'` — **2 passed**.
- `cd frontend && npm test -- --run tests/format.test.ts
  tests/dialogs.test.tsx` — **2 files, 19 tests passed**.

### Reviewer follow-up verification — 2026-10-15

- `pytest -q tests/test_config.py` — **60 passed**. The migration/update
  interleaving test now waits for the updater's lock-wrapper signal emitted
  immediately before real `RLock.acquire()` before allowing migration
  replacement, joins both workers, and asserts no worker raised.
- `cd frontend && npm test -- --run tests/format.test.ts` — **1 file, 3 tests
  passed**. The timezone assertion imports and calls `fmtDate` in child Node
  processes with `TZ=America/Los_Angeles` and `TZ=UTC`, setting locale through
  the application i18n singleton; it does not use a parallel Intl expression
  or mock Intl in those subtests.
- `git diff --check` — passed.
- `cd frontend && npm test` — **36 files, 289 tests passed; 1 fixture file, 1
  test skipped**. Vitest emitted the pre-existing jsdom
  `HTMLMediaElement.play()` implementation note; it did not fail a test.

### Redundant mock removal — 2026-10-15

- Removed the `Intl.DateTimeFormat` constructor spy/mock from
  `frontend/tests/format.test.ts`. The subprocess fixture already verifies the
  real `fmtDate` behavior in `America/Los_Angeles` and `UTC`, so the mock-based
  implementation assertion was redundant.
- `cd frontend && npm test -- --run tests/format.test.ts
  tests/format-timezone.fixture.test.ts` — **1 file, 2 tests passed; 1 fixture
  file, 1 test skipped**. `format.test.ts` runs the fixture in child processes
  with its required timezone expectations; Vitest skips the fixture's direct
  invocation because it has no `FMT_DATE_EXPECTED` value.
- `git diff --check` — passed.

## Scope note

The worktree contained broad pre-existing localization and UI changes before
this follow-up. They were not reset or overwritten. No commit was created.

## Final acceptance — 2026-10-15

- Final `pytest` — **798 passed**, 2 upstream Starlette/AnyIO deprecation warnings.
- Final `cd frontend && npm test` — **289 passed, 1 skipped**. The skip is the
  timezone fixture when run standalone; its parent test invokes it in separate
  LA and UTC processes. jsdom emitted its existing `HTMLMediaElement.play()`
  notice.
- Final `cd frontend && npm run build` — passed.
- Final `cd frontend && npm run check:i18n-keys` — passed.
- Final `python scripts/check_locales.py` and `python scripts/check_copy.py` —
  passed; copy check is scoped as documented in the I18N guides.
- Final `git diff --check` — passed.
- Independent whole-change review: no blocking, important, or minor findings.
- Historical candidate counts (778 frontend / 164 backend) are not treated as
  an occurrence-ID checklist; current source scan and its bounded limitations
  are documented in Task 1/Task 9 artifacts and `docs/{en,ru}/I18N.md`.
