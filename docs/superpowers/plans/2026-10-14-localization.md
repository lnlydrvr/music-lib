# Localization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Localize all application-owned user-facing copy in `music-lib` for English and Russian, with a catalog-based workflow that makes adding future locales a bounded catalog task.

**Architecture:** The frontend owns ICU JSON catalogs and renders both its own copy and backend-originated messages. The backend emits stable message descriptors (`code`, `params`, readable English `message`) for API errors, jobs, and diagnostics, while preserving legacy string compatibility. Locale selection is persisted in the existing settings config; guardrails validate key parity, typed keys, and new user-facing copy.

**Tech Stack:** React 19, TypeScript, Vite, i18next, react-i18next, i18next ICU formatter, FastAPI, Python JSON config, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-10-14-localization-design.md`

## Global Constraints

- First supported locales are English (`en`) and Russian (`ru`); English is the base/fallback locale.
- All application-owned user-visible copy is localized, including frontend UI and backend-originated API errors, job progress/history, and library diagnostics.
- Music metadata and other user or provider data are not translated.
- Language selection is stored in the existing user config and takes effect immediately without a page reload.
- Use standard nested ICU JSON catalogs under `frontend/src/locales/`.
- The backend emits stable message codes and JSON-compatible parameters; the frontend resolves them through the same locale catalog.
- Existing plain-string API messages remain renderable during migration and for unknown/unstructured third-party errors.
- `message` is a readable English compatibility/logging fallback, not the normal localized rendering path.
- Do not translate track/album/artist names, paths, tag values, provider labels, service responses, or other user/provider data.
- Missing-key behavior must be visible during development/tests and safe for users in production; it must not silently render an opaque key.
- Preserve keyboard focus, light/dark themes, and `prefers-reduced-motion` behavior.
- Checks must document and allow data, test fixtures, technical identifiers, provider/service names, and logs not shown to users.
- Required checks: `pytest`, `cd frontend && npm test`, `cd frontend && npm run build`, and locale validation/lint commands.

## Review Focus

1. **User/provider data mistaken for copy** — tracks, paths, tags, provider names remain verbatim; add regression assertions to diagnostics and library DTO tasks.
2. **Legacy and unknown errors** — string `detail`, string field errors, raw provider failures remain readable; cover in API client compatibility tests.
3. **Russian plural/select and interpolation** — ICU output handles zero/one/few/many and parameters safely; cover in catalog/runtime tests.
4. **Language source race** — cached language must not overwrite persisted server selection after settings load; cover startup precedence and persistence failure.
5. **Long translations and accessible controls** — selector and key actions remain visible/focusable across themes; cover with component tests and manual responsive review.

---

## File map and ownership

### New files

- `frontend/src/locales/en.json`, `frontend/src/locales/ru.json` — source and translated catalogs.
- `frontend/src/i18n/index.ts` — initialization, supported locales, language resolution/change.
- `frontend/src/i18n/messages.ts` — structured message guards and rendering helpers for non-component code.
- `src/web/messages.py` — Python message descriptor construction and JSON-safe serialization.
- `scripts/check_locales.py` — recursive locale parity, empty-value, and ICU argument/plural validation.
- `frontend/tests/i18n.test.ts` — locale runtime and catalog-facing tests.
- `tests/test_messages.py` — Python message descriptor serialization tests.
- `docs/en/I18N.md`, `docs/ru/I18N.md` — contribution and translation guide.

### Existing files grouped by responsibility

- Runtime/config: `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/tsconfig.json`, `frontend/vitest.config.ts`, `frontend/tests/setup.ts`, `src/config.py`, `src/web/routes.py` settings endpoints.
- API messages: `frontend/src/lib/api.ts`, `src/web/server.py`, `src/web/routes.py`, `tests/test_web_api.py`, `frontend/tests/api.test.ts`.
- Jobs: `src/web/jobs.py`, job-producing functions in `src/web/routes.py`, `frontend/src/lib/jobs.ts`, `frontend/src/stores/downloads.ts`, `frontend/src/components/DownloadsDock.tsx`, `frontend/src/views/SearchScreen.tsx`, `MiscScreen.tsx`, `LibraryScreen.tsx`, `QualityScreen.tsx`.
- Diagnostics/quality: `src/health.py`, `src/lint.py`, `src/quality.py`, `src/normalize.py`, quality serializers in `src/web/routes.py`, `frontend/src/views/QualityScreen.tsx`, `frontend/src/lib/diff.ts`, relevant pytest/Vitest files.
- Frontend batches: shell/navigation (`nav.ts`, `App.tsx`, `Topbar.tsx`, `Tabbar.tsx`, `MoreMenu.tsx`, `CommandPalette.tsx`, `KeymapDialog.tsx`); library (`LibraryScreen.tsx`, `views/library/**`); discover/search/recommend (`DiscoverScreen.tsx`, `SearchScreen.tsx`, `MiscScreen.tsx`, `RecommendScreen.tsx`, `features/ytm/**`); settings (`SettingsScreen.tsx`, `views/settings/**`); editor (`features/editor/**`); dialogs/player/toasts (`components/dialogs/**`, player components, `DownloadsDock.tsx`, `lib/toast.tsx`, `lib/ops.tsx`).
- Guardrails/docs: `frontend/package.json`, new ESLint config/rules if needed, `pyproject.toml` or script invocations, `AGENTS.md`, `README.md`, `docs/en/README.md`, `docs/ru/README.md`, `docs/en/PRODUCT.md`, `docs/ru/PRODUCT.md`.

## Frozen interfaces

These interfaces are established before parallel frontend/backend implementation.

### JSON message descriptor

Python helper:

```python
def message(code: str, params: dict[str, object] | None = None, *, fallback: str) -> dict[str, object]:
    return {"code": code, "params": params or {}, "message": fallback}
```

Frontend type:

```ts
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };
export interface StructuredMessage {
  code: string;
  params?: Record<string, JsonValue>;
  message?: string;
}
export type RenderableMessage = string | StructuredMessage;
```

Resolution rules: a string is shown verbatim; a known structured code is translated with ICU params; an unknown code uses readable `message`; development/tests expose missing keys visibly. Never translate arbitrary provider/OS exception strings.

HTTP response supports `detail: RenderableMessage` and `errors: Record<string, RenderableMessage>`. Existing `detail: string`, `{detail: {message: string}}`, and string `errors` remain accepted.

Jobs use `name: RenderableMessage`, `error: RenderableMessage | null`, and progress event `{type: "progress", message: RenderableMessage, percent?: number, ...}`. Keep reading legacy `msg` and string names/errors. Polling DTO and SSE payload must share those semantics.

Diagnostic and quality DTOs keep discriminators/data as-is and change only user-facing message prose to `RenderableMessage`. `path`, `field`, `value`, `old`, `new`, `target`, `category`, `kind`, and provider/user values remain unchanged.

### Locale selection

Persisted setting in server config wins. `GET /api/settings` always returns
`language: null` when there is no valid saved selection, and exactly `"en"` or
`"ru"` otherwise; do not omit the field or substitute a computed locale. At
startup, cached `localStorage` is only a provisional locale while settings load;
then apply the saved server locale. If the server returns `null`, use supported
`navigator.language`, then `en`. A failed save leaves the active locale in place
and shows a localized error.

## Implementation tasks

### Task 1: Build exhaustive copy/data inventory and freeze message/key map

**Files:**
- Create: `docs/superpowers/plans/localization-key-map.md` (temporary working artifact, later incorporated into `docs/en/I18N.md` / `docs/ru/I18N.md`).
- Read: all user-visible literals in `frontend/src/**`; producers/serializers in `src/web/routes.py`, `src/web/jobs.py`, `src/health.py`, `src/lint.py`, `src/quality.py`, `src/normalize.py`.
- Test references: `frontend/tests/**`, `tests/**`.

**Interfaces:**
- Consumes: approved design spec and the analyst inventory from the coordination stage.
- Produces: complete key list, owner, English source, Russian translation, ICU parameters, producer/transport/consumer path, and explicit data exclusions. Codes use the namespaces defined in the spec.

- [ ] **Step 1: Enumerate frontend source literals by feature batch.** Record each user-visible label, aria/title text, toast, dialog, empty state, and progress message; exclude comments, CSS, data values, IDs, and provider text.
- [ ] **Step 2: Trace backend-produced messages to API consumers.** For each owned message, record producer and consumers across HTTP, polling, SSE/history, diagnostics, and quality-plan responses.
- [ ] **Step 3: Write the code/key map.** Assign stable keys and parameter names; explicitly mark data fields that remain verbatim.
- [ ] **Step 4: Verify the map covers all identified sources.** Re-run searches for JSX text, accessibility attributes, toast strings, `HTTPException(detail=...)`, `job.push(...)`, and diagnostic message constructors; explain each excluded match.
- [ ] **Step 5: Review/freeze contract names.** Confirm frontend and backend will use `detail/errors`, `name/error/message`, and diagnostic `message` shapes specified above before parallel work starts.

**Independent check:** `rg -n 'HTTPException|detail=|\.push\(|message=|msg=' src/web src/health.py src/lint.py src/quality.py src/normalize.py` and a frontend literal scan; compare hits against the map.

### Task 2: Add backend message descriptors and language setting

**Files:**
- Create: `src/web/messages.py`, `tests/test_messages.py`.
- Modify: `src/config.py`, `src/web/routes.py`, `tests/test_config.py`, `tests/test_web_api.py`.

**Interfaces:**
- Consumes: frozen message contract from Task 1.
- Produces: `message(code, params=None, *, fallback)` helper returning JSON-safe `{"code", "params", "message"}`; validated config language functions/constants; settings API language field.

- [ ] **Step 1: Write tests for message descriptor shape.** Assert absent params become `{}`, nested JSON-compatible params are retained, and fallback/code are present.
- [ ] **Step 2: Run `pytest tests/test_messages.py -q` and confirm the new module/test fails because the helper is absent.**
- [ ] **Step 3: Implement the helper.** Reject non-JSON parameter values at call sites/tests; do not stringify arbitrary objects as user-facing data.
- [ ] **Step 4: Write config tests.** Cover default `en`, accepted `ru`, invalid persisted values falling back safely, and config round-trip with existing unrelated keys preserved.
- [ ] **Step 5: Implement `LANGUAGE_KEY`, supported locales, getter, and settings GET/PUT support.** GET returns `language: null` when unset; PUT invalid locale returns a structured error; omitted language preserves current setting. Keep any effective `en` config getter separate from persisted-choice serialization.
- [ ] **Step 6: Run `pytest tests/test_messages.py tests/test_config.py tests/test_web_api.py -q`.**

### Task 3: Establish frontend i18n runtime, catalogs, locale bootstrap, and settings switch

**Files:**
- Create: `frontend/src/locales/en.json`, `frontend/src/locales/ru.json`, `frontend/src/i18n/index.ts`, `frontend/src/i18n/messages.ts`, `frontend/tests/i18n.test.ts`.
- Modify: `frontend/package.json`, `frontend/package-lock.json`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/views/SettingsScreen.tsx`, `frontend/tests/setup.ts`, `frontend/tests/settingsScreen.test.tsx`, `frontend/tsconfig.json` if catalog typing requires it.

**Interfaces:**
- Consumes: Task 1 key map and Task 2 settings response (`language: "en" | "ru" | null`, always present).
- Produces: initialized `i18n`, `SUPPORTED_LOCALES`, `resolveMessage(value: RenderableMessage): string`, `changeLanguage(locale)`, and locale selector behavior.

- [ ] **Step 1: Add tests for locale resolution and descriptor rendering.** Cover `en`, `ru`, regional tags (`ru-RU`, `en-GB`), unsupported browser locale, legacy string, known structured key, unknown code with fallback.
- [ ] **Step 2: Run `cd frontend && npm test -- i18n.test.ts` and confirm failure.**
- [ ] **Step 3: Add dependencies and initialize i18next with ICU.** Bundle `en.json` and `ru.json`; English is fallback and source.
- [ ] **Step 4: Initialize before React render.** Set document `lang`; keep `index.html` initial lang neutral (`en`) and update after runtime resolution.
- [ ] **Step 5: Implement startup precedence.** Use localStorage as provisional locale; load `/api/settings`; persisted server locale wins; absent setting falls back to browser locale then English; handle denied localStorage without crashing.
- [ ] **Step 6: Add the Settings language selector.** Use native labels; switch immediately; persist via `PUT /api/settings`; on save failure retain active locale and display localized error.
- [ ] **Step 7: Test selection, immediate rerender, server persistence precedence, unsupported locale, storage errors, and save failure.**
- [ ] **Step 8: Run `cd frontend && npm test -- i18n.test.ts settingsScreen.test.tsx && npm run build`.**

### Task 4: Migrate shell, shared components, dialogs, jobs and notifications

**Files:**
- Modify: `frontend/src/nav.ts`, `frontend/src/components/Topbar.tsx`, `Tabbar.tsx`, `MoreMenu.tsx`, `CommandPalette.tsx`, `KeymapDialog.tsx`, `DialogProvider.tsx`, `PlayerBar.tsx`, `AudioPlayer.tsx`, `PreviewButton.tsx`, `DownloadsDock.tsx`, `frontend/src/lib/toast.tsx`, `ops.tsx`, `jobs.ts`, `frontend/src/stores/downloads.ts`, `frontend/src/components/ui/StatusLine.tsx` and matching component tests.

**Interfaces:**
- Consumes: Task 3 `useTranslation()`, `resolveMessage`, and catalogs; backend job contract from Task 6 when integrated.
- Produces: navigation/job metadata stores keys/descriptors, never rendered locale strings; components resolve at render time so active tasks update when language changes.

- [ ] **Step 1: Migrate shell labels and accessibility text** (`nav.ts` stores keys; components translate at render). Add tests for changing locale after shell mount.
- [ ] **Step 2: Migrate dialog defaults/actions, player and shared status labels.** Keep caller-provided data and labels verbatim where they are not application-owned copy.
- [ ] **Step 3: Update downloads store model.** Store structured message descriptors for title/name/progress/error; preserve legacy string records and endpoint-to-job-code fallback mapping.
- [ ] **Step 4: Update SSE/polling parser.** Accept new `message` plus legacy `msg`; normalize terminal errors to `RenderableMessage`; preserve recommendation progress payload fields.
- [ ] **Step 5: Migrate toasts/operation helpers to accept descriptors.** Resolve at display time, not when the job starts, so language switching updates visible progress/history.
- [ ] **Step 6: Update tests in `topbar`, `menu`, `commandPalette`, `dialogs`, `player`, `statusLine`, `jobs`, `downloads`, and download dock suites.** Assert rendered translations and legacy compatibility.
- [ ] **Step 7: Run focused Vitest tests for those files and `npm run build`.**

### Task 5: Migrate library, search, discover, recommendation, Shazam, and editor UI

**Files:**
- Modify: `frontend/src/views/LibraryScreen.tsx`, `frontend/src/views/library/**`, `DiscoverScreen.tsx`, `SearchScreen.tsx`, `MiscScreen.tsx`, `RecommendScreen.tsx`, `frontend/src/features/ytm/**`, `frontend/src/features/editor/**`; their existing tests.

**Interfaces:**
- Consumes: Task 3 runtime and Task 1 namespaced key map.
- Produces: all application-owned copy in these screens uses translation keys; titles/artist names/lyrics/paths/provider output remain verbatim.

- [ ] **Step 1: Migrate the library shell and tabs.** Translate labels, sort modes, empty states, aria text, actions, confirmations and toasts; do not translate records or tags.
- [ ] **Step 2: Migrate search/discover/Shazam/recommend screens.** Translate status/pipeline labels and UI copy; keep provider search results and query/seed data unchanged.
- [ ] **Step 3: Migrate YT Music cards/details and editor dialogs.** Translate actions/field labels/validation, not provider or tag values.
- [ ] **Step 4: Add locale-switch tests proving mounted screens rerender while data fields remain verbatim.**
- [ ] **Step 5: Run focused Vitest tests for library, search, recommend, misc, YTM, and editor suites.**

### Task 6: Convert backend API errors and field validation to structured messages

**Files:**
- Modify: `src/web/routes.py`, `src/web/server.py` if global handlers are needed, `frontend/src/lib/api.ts`, `frontend/tests/api.test.ts`, `tests/test_web_api.py`, editor/API tests.

**Interfaces:**
- Consumes: Task 1 frozen key map and Task 2 `message()` helper.
- Produces: HTTP `detail` and `errors` follow `RenderableMessage`; `ApiError` retains status, normalized detail, normalized field descriptors and readable `Error.message`.

- [ ] **Step 1: Extend `ApiError` tests first.** Cover structured detail, structured field errors, old string detail, `{detail:{message}}`, string field errors, unknown code fallback, unreadable body fallback.
- [ ] **Step 2: Implement API error normalization and rendering.** Keep the raw descriptor on the error; resolve at UI boundary using active locale; preserve a readable `Error.message` for logs/catches.
- [ ] **Step 3: Migrate route-owned validation and known application errors in batches using the frozen map.** Do not wrap raw provider/OS exception strings in translated codes.
- [ ] **Step 4: Convert field validation payloads to descriptor values while maintaining string compatibility for old clients.**
- [ ] **Step 5: Add route tests asserting stable codes and params plus compatibility of known legacy strings.**
- [ ] **Step 6: Run `pytest tests/test_web_api.py -q` and `cd frontend && npm test -- api.test.ts editorDialogs.test.tsx trackEditor.test.tsx`.**

### Task 7: Convert jobs across producer, history, polling and SSE

**Files:**
- Modify: `src/web/jobs.py`, job-producing code in `src/web/routes.py`, `frontend/src/lib/jobs.ts`, `frontend/src/stores/downloads.ts`, `frontend/src/components/DownloadsDock.tsx`, job-related tests in `tests/` and `frontend/tests/`.

**Interfaces:**
- Consumes: Task 1 job code map, Task 2 message helper, Task 4 frontend descriptor-aware job store.
- Produces: identical descriptor semantics in `/api/jobs`, `/api/jobs/{id}`, and SSE; supports legacy `name`, `msg`, and `error` strings.

- [ ] **Step 1: Add tests for `Job` descriptor serialization.** Verify name/progress/error shape in `to_dict()` and SSE; legacy string values still serialize and parse.
- [ ] **Step 2: Change `Job` constructor, `push`, and `fail` to accept `RenderableMessage`; serialize progress under `message`, optionally retain legacy `msg` only if compatibility tests prove a consumer requires it.**
- [ ] **Step 3: Convert application-owned job names and progress calls in routes to stable codes and JSON params.** Preserve data such as filename, count, and title as params.
- [ ] **Step 4: Convert known application exceptions at the job boundary to coded errors; leave unknown third-party exception text as readable legacy strings.**
- [ ] **Step 5: Verify polling and SSE parity, including reconnect/history restoration and changing locale while a task is active.**
- [ ] **Step 6: Run focused `pytest` job/API tests and frontend jobs/downloads suites.**

### Task 8: Convert health, lint, quality plans, and normalization diagnostics

**Files:**
- Modify: `src/health.py`, `src/lint.py`, `src/quality.py`, `src/normalize.py`, quality serializers in `src/web/routes.py`, `frontend/src/views/QualityScreen.tsx`, `frontend/src/lib/diff.ts`, related pytest and Vitest tests.

**Interfaces:**
- Consumes: Task 1 diagnostic code map and Task 2 descriptor helper.
- Produces: `HealthIssue`, `LintIssue`, `QualityIssue`, fixes/conflicts, plan/apply dictionaries carry structured user message descriptors; all discriminator/data fields remain stable and untranslated.

- [ ] **Step 1: Add unit/API tests for descriptor shape on representative missing-field, whitespace, unreadable-file, conflict, and apply-error diagnostics.** Assert values/path/field remain verbatim.
- [ ] **Step 2: Migrate domain constructors to store descriptors rather than prose strings.** Keep English fallback strings readable for logs/legacy clients.
- [ ] **Step 3: Migrate all quality serializers and nested conflict/apply result dictionaries.** Do not translate categories, kinds, paths, tag names, old/new values.
- [ ] **Step 4: Migrate QualityScreen labels, diagnostic messages, conflict summaries, plan actions and toasts to resolve catalog descriptors.**
- [ ] **Step 5: Update tests from literal prose to codes/params or rendered fixed-locale text.**
- [ ] **Step 6: Run `pytest tests/test_health.py tests/test_lint.py tests/test_normalize.py tests/test_quality.py tests/test_quality_plan.py tests/test_quality_api.py -q` and `cd frontend && npm test -- qualityScreen.test.tsx diff.test.ts`.**

### Task 9: Complete locale catalogs and migrate remaining frontend feature batches

**Files:**
- Modify: all remaining `frontend/src/**` UI files identified in Task 1 and both locale catalogs.
- Tests: remaining `frontend/tests/**` coupled to affected screens/components.

**Interfaces:**
- Consumes: frozen key map; frontend runtime; structured backend DTOs.
- Produces: no application-owned visible literal remains outside catalogs (except documented technical/data exclusions); both catalogs contain every key.

- [ ] **Step 1: Migrate remaining settings and YTM authorization UI.** Ensure provider names stay as data and native selector labels remain English/Русский.
- [ ] **Step 2: Migrate remaining skeletons, tooltips, titles, placeholders, aria-labels, and error/empty states across frontend batches.**
- [ ] **Step 3: Add English source messages and reviewed Russian translations for every frozen key.** Preserve ICU argument names and plural/select cases.
- [ ] **Step 4: Run a source scan and reconcile every hit against the key map; only documented non-user-facing/data exemptions remain.**
- [ ] **Step 5: Run all frontend tests and production build; fix truncation/wrapping issues found in selector and essential actions.**

### Task 10: Add locale validation, typed keys, and hardcoded-copy guardrails

**Files:**
- Create: `scripts/check_locales.py` and focused tests (for example `tests/test_locale_catalogs.py`).
- Modify: `frontend/package.json`, TypeScript i18next declaration file under `frontend/src/i18n/`, lint config or a focused custom checker, `AGENTS.md`.

**Interfaces:**
- Consumes: complete catalogs and key map.
- Produces: deterministic locale validation command, build-time key typing, documented lint command for frontend and backend copy.

- [ ] **Step 1: Add validator unit fixtures** for matching keys, missing/extra/empty values, mismatched ICU arguments, and plural-category mismatch.
- [ ] **Step 2: Implement recursive JSON/ICU validation.** Ensure output identifies locale, key, and problem; return non-zero for violations.
- [ ] **Step 3: Add TypeScript augmentation based on English resources and verify invalid keys fail `tsc` using a temporary negative type fixture excluded from production build or a type-level test.**
- [ ] **Step 4: Add frontend hardcoded-literal lint scoped to user-facing JSX/attributes and backend message producer lint scoped to known constructors.** Explicitly exempt data, tests, technical identifiers, provider strings, and logs.
- [ ] **Step 5: Add package/script commands and document the authoring rule in `AGENTS.md`.**
- [ ] **Step 6: Run validator, targeted lint tests, and `cd frontend && npm run build`.**

### Task 11: Update docs and repository guidance in English and Russian

**Files:**
- Create: `docs/en/I18N.md`, `docs/ru/I18N.md`.
- Modify: `README.md`, `docs/en/README.md`, `docs/ru/README.md`, `docs/en/PRODUCT.md`, `docs/ru/PRODUCT.md`, `AGENTS.md` if not completed in Task 10.

**Interfaces:**
- Consumes: final catalog conventions and actual validation commands from Tasks 3 and 10.
- Produces: synchronized guide on adding a locale and authoring frontend/backend messages.

- [ ] **Step 1: Document supported locales, catalog path, key naming, ICU interpolation/plurals, fallback, and validation commands in English.**
- [ ] **Step 2: Translate/update the Russian counterpart and verify both guides describe the same behavior.**
- [ ] **Step 3: Update README/product docs with language choice and settings behavior without duplicating implementation details.**
- [ ] **Step 4: Check links and run locale validator.**

### Task 12: Full integration QA, review, and acceptance

**Files:**
- No expected product code edits unless QA/review finds an issue.
- Inspect: full diff, backend/frontend test logs, locale validation results.

**Interfaces:**
- Consumes: completed Tasks 1–11.
- Produces: verified acceptance report and resolved blocking findings.

- [ ] **Step 1: Run all required checks:** `pytest`; `cd frontend && npm test`; `cd frontend && npm run build`; locale validator; copy lint.
- [ ] **Step 2: Exercise locale selection manually:** fresh browser with `en`, fresh browser with `ru`, unsupported locale, explicit server setting, reload/restart, denied localStorage, failed persistence.
- [ ] **Step 3: Exercise message paths:** API structured/legacy error, field error, active job progress then locale switch, polling history, SSE reconnect, job failure, health/lint/quality diagnostics and conflict plan.
- [ ] **Step 4: Verify data-preservation scenarios:** Cyrillic/Latin track names, provider labels, paths, tags, lyrics, and old/new conflict values render unchanged under both locales.
- [ ] **Step 5: Check keyboard selector operation, focus visibility, light/dark themes, narrow viewport, and reduced-motion preference.**
- [ ] **Step 6: Request independent review from `@richard-reviewer`** with this spec, frozen DTOs, test results, and explicit data-vs-message boundaries; fix blocking findings and rerun affected checks.
- [ ] **Step 7: Report completion with changed areas, test evidence, remaining known exclusions, and participating agents.**

## Self-review against the spec

- Catalog/runtime/pluralization/type safety: Tasks 3, 9, 10.
- Persisted language, precedence, immediate update, fallback: Tasks 2, 3, 12.
- HTTP errors and field errors plus legacy compatibility: Tasks 2, 6.
- Jobs, history, polling, SSE: Tasks 4, 7, 12.
- Health/lint/quality/normalization and plan conflicts: Task 8.
- User/provider data exclusions: Tasks 1, 5, 8, 12.
- All UI strings/aria/dialogs/toasts/settings/editor/player: Tasks 4, 5, 9.
- Guardrails for future copy and locale drift: Task 10.
- English/Russian docs and adding future locales: Task 11.
- Existing docs are bilingual; English product documentation changes require Russian counterpart updates.

No known spec requirements are unassigned. The planned copy-lint checks are intentionally scoped to user-facing producers rather than blanket string/Cyrillic bans, avoiding false positives on user data and provider output.
