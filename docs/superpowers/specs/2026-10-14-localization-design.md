# Localization design

## Goal and approved scope

Make `music-lib` fully localizable so that adding another language later is
primarily a catalog task rather than another application-wide refactor. The
first release supports English (`en`) and Russian (`ru`), with English as the
base/fallback locale. All user-visible application copy is localized, including
frontend UI and backend-originated API errors, job progress/history, and library
diagnostics. Music metadata and other user or provider data are not translated.

The application remains a local, single-user web app. Language selection is
stored in the existing user config and takes effect immediately without a page
reload.

## Catalog and runtime

- Use `i18next`, `react-i18next`, and ICU message formatting in the React app.
- Keep one standard nested ICU JSON catalog per locale under
  `frontend/src/locales/`, initially `en.json` and `ru.json`.
- Use stable, namespaced keys grouped by feature and message type, for example
  `nav.library`, `settings.language.label`, `api.errors.file_not_found`,
  `jobs.download.progress`, and `diagnostics.lint.missing_title`.
- Use ICU placeholders for parameters and ICU plural/select forms for messages;
  Russian plural categories must be represented correctly.
- English is the source catalog and fallback. Missing-key behavior must be
  visible during development/tests and safe for users in production; it must not
  silently render an opaque key.
- Expose translations through `useTranslation()` in components and the
  initialized i18next instance in non-component code. Dynamic navigation and
  job labels carry translation keys, not rendered strings.
- Format dates, numbers, and locale-sensitive comparisons with `Intl` using
  the active locale. Set `document.documentElement.lang` after initialization
  and on every language change.

## Locale selection and persistence

Add a validated `language` value (`en` or `ru`) to the existing JSON config and
the existing `GET/PUT /api/settings` contract. The selected language is the
persisted source of truth. On startup, use a cached localStorage value to avoid
an English flash while settings load; then apply the server setting. If there
is no saved selection, choose a supported `navigator.language` match, otherwise
English. Changing the selector updates i18next immediately and persists via
`PUT /api/settings`; handle persistence failure without reverting the active
language and inform the user in the selected locale.

The selector belongs in Settings, with native language names (English,
Русский), keyboard support, visible focus, and existing light/dark theme and
reduced-motion behavior.

## Backend message contract

The backend does not translate prose. It emits stable message codes and
JSON-compatible parameters; the frontend resolves them through the same locale
catalog. Use a shared response shape for HTTP errors, diagnostics, and jobs:

```json
{"code": "api.errors.file_not_found", "params": {"path": "..."}, "message": "File not found: ..."}
```

`message` is a readable English compatibility/logging fallback, not the normal
localized rendering path. Existing plain-string API messages remain renderable
during migration and for unknown/unstructured third-party errors. The frontend
must not attempt to translate arbitrary provider or OS exception text.

Apply the structured contract consistently to:

- FastAPI `HTTPException` details and field errors.
- Job names, progress events, errors, and stored job history/SSE events.
- User-facing health, lint, quality, and normalization diagnostics and plan
  conflict messages.

Keep parameters separate from prose (counts, paths, names, values). Codes are
stable API identifiers and must not be derived from translated text. Do not
translate track/album/artist names, paths, tag values, provider labels, service
responses, or other user/provider data. Distinguish these fields explicitly in
the inventory before migration.

## Migration and compatibility

Inventory all user-visible strings in frontend and backend before changing
contracts. Each user-facing string is assigned a stable key and appears in both
English and Russian catalogs. Migrate in bounded feature groups while keeping
the app usable at each integration point. Preserve readable string fallbacks
for plain API errors and legacy job records; structured codes should be
preferred wherever the application owns the message.

Update existing tests that assert literal prose to assert stable codes,
parameters, or rendered text under a fixed locale. Do not assert catalog
implementation details where a user-visible behavior assertion is appropriate.

## Guardrails for future strings

- Add a locale validation check that recursively compares key structure across
  catalogs and fails on missing, extra, or empty translations.
- Type translation keys from the English catalog so invalid keys fail the
  TypeScript build.
- Add lint/CI checks to flag user-facing hardcoded literals in UI and
  application-owned backend messages. Checks must allow data, test fixtures,
  technical identifiers, provider/service names, and logs that are not shown to
  users; document those boundaries rather than enforcing a naive ban on all
  Cyrillic or all string literals.
- Document the authoring rule: new frontend copy uses translation keys; new
  backend user messages use codes and parameters; every supported locale must
  be updated in the same change.

## Testing and acceptance criteria

Test at least:

1. English and Russian selection, immediate switch, and persistence across
   reload/restart.
2. Unsupported browser locale fallback and missing-key handling.
3. ICU interpolation and plural cases, including Russian plural forms.
4. Structured and legacy string API errors, field errors, jobs/SSE/history,
   diagnostics, and quality-plan conflicts.
5. Existing user data remains unchanged and visible verbatim in both locales.
6. Keyboard operation and layout in supported themes; longer translated copy
   does not hide essential actions.
7. Catalog parity/type/literal checks.

Required checks: `pytest`, `cd frontend && npm test`, `cd frontend && npm run
build`, and the locale validation/lint commands.

Definition of done: all application-owned user-visible copy is catalog-backed
in both `en` and `ru`; user/provider data is preserved; locale selection and
fallback work; API/job/diagnostic messages localize from codes and parameters;
legacy string messages remain readable; checks prevent catalog drift and new
hardcoded user copy; docs explain how to add a locale; required tests and build
pass.

## Work boundaries and sequence

1. Product owner confirms acceptance criteria and supported initial locales.
2. Analyst inventories messages vs. data, identifies all producers/consumers,
   and proposes the complete code/key map and test impact.
3. Designer specifies selector behavior and text-length/a11y constraints.
4. Coordinator freezes the response/event contract and key map.
5. Backend and frontend implementation proceed in parallel after contract
   freeze. Backend owns `src/**`; frontend owns `frontend/src/**` and frontend
   dependencies/config. No parallel edits to shared files.
6. QA exercises the acceptance scenarios and runs required checks.
7. Independent review addresses contract consistency, data-vs-message
   boundaries, compatibility, and omissions.
8. Coordinator updates English and Russian documentation and authoring
   guidance.

The estimate for the complete migration is approximately 21–40 engineering
days, subject to the message inventory and test findings. The major cost and
risk is the coordinated HTTP/SSE/history/diagnostics contract migration, not
the language selector itself.
