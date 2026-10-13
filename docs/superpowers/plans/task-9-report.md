# Task 9 partial-batch review-fix report

## 2026-10-15 — reviewer findings resolved

- `SearchScreen` stores result data (`query`, engine, and items), not rendered
  localized heading/note strings. The result chrome is now derived during render,
  so it updates immediately after a locale change while provider track data remains
  verbatim.
- Search metaflow confirmation, progress stages, completion/error fallbacks,
  archive/completion toasts, and batch job title/result messages now use catalog
  descriptors. Batch counts use ICU pluralization.
- `search.playlist` is ICU pluralized: English defines `one`/`other`; Russian
  defines `one`/`few`/`many`/`other`.
- YouTube Music album and playlist detail counts use `ytm.tracks.count` rather
  than Russian template literals.
- YTM downloads now require a `YtmDownloadTarget`. Its `archiveName` is generated
  only from an immutable entity kind and stable provider ID (`ytm-<kind>-<id>`),
  while the localized job title remains separate. Album, artist, playlist, radio,
  track, and YouTube fallback callers have migrated; no localized or provider
  display text reaches the filesystem-facing archive field.
- Added regressions for loaded Search result chrome after locale switch, English
  and Russian playlist plurals, YTM track-count plurals, and stable-ID archive
  request names with descriptor-backed localized job titles.

## Verification — 2026-10-15

- `cd frontend && npm test -- ytmDownload.test.ts searchScreen.test.tsx` — 28 passed.
- `cd frontend && npm test` — 258 passed, 1 pre-existing unrelated failure:
  `tests/editorDialogs.test.tsx > runMetaflow > после диалога молча обновляет
  текст (LRCLIB); отмена → false` expects a localized progress string but
  receives the current `"metadata"` stage identifier.
- `cd frontend && npm run build` — passed (`tsc --noEmit` and Vite production build).

## 2026-10-15 — target contract and metaflow completion

- `MetaflowStage` is now explicit (`"metadata" | "lyrics"`) and is converted to
  `RenderableMessage` only by `metaflowStageMessage`. Both `SearchScreen` and
  `MiscScreen` use that adapter before setting operation progress, so UI state
  remains locale-reactive rather than storing rendered Russian strings.
- `YtmDownloadTarget` now exposes `{ kind, providerId, title }`. The archive
  filename is private to `ytmDownload` and is constructed exclusively from the
  target kind plus URL-encoded stable provider ID. All target creators, including
  the single-track search flow, now use that contract.
- Added regressions for typed metaflow stage descriptors and an adversarial
  localized album title containing `/`; the request archive remains
  `ytm-album-MPREb_012345`.

## Verification — 2026-10-15 (completion)

- `cd frontend && npm test -- searchScreen.test.tsx ytmDownload.test.ts editorDialogs.test.tsx miscScreen.test.tsx ytmCards.test.tsx` — 49 passed.
- `cd frontend && npm test` — 260 passed.
- `cd frontend && npm run build` — passed (`tsc --noEmit` and Vite production build).
- `pytest` — 763 passed (2 third-party deprecation warnings from FastAPI/Starlette test-client dependencies).

## 2026-10-15 — download target regression follow-up

- `DownloadAllButton` regression now passes the required `target` object and
  clicks the real button. It verifies that the handler receives the supplied
  target and only tracks absent from the local library.
- Added an adversarial stable-ID case: `../a/b` is emitted as
  `ytm-album-..%2Fa%2Fb`, so separator characters cannot become archive-path
  segments.
- Renamed the `TracksTab` radio-download callback argument to `target`; it is
  a `YtmDownloadTarget`, not a playlist name. The download-module comment now
  records the stable-ID and URL-encoding boundary.

## Verification — 2026-10-15 (follow-up)

- `cd frontend && npm test -- ytmDownload.test.ts` — 12 passed.
- `cd frontend && npm run build` — passed (`tsc --noEmit` and Vite production
  build).

## 2026-10-15 — YTM cards type regression

- The reusable playlist download target in `ytmCards.test.tsx` now uses
  `satisfies YtmDownloadTarget`, preserving the literal `"playlist"` kind
  required by the download-target contract while checking the complete object
  shape.

## Verification — 2026-10-15 (YTM cards type regression)

- `cd frontend && npm test -- ytmCards.test.tsx` — 11 passed.
- `cd frontend && npm run build` — passed (`tsc --noEmit` and Vite production
  build).

## 2026-10-15 — remaining top-level settings, Shazam, menu, and recommendations batch

- Migrated the app-owned visible copy in `MenuScreen`, Shazam (`MiscScreen`),
  recommendations, the settings form, and settings browse fallback to the EN/RU
  catalogs. Provider names, paths, filenames, track/artist/account data, browser
  names, and unrecognized exceptions remain verbatim data.
- `MiscScreen` no longer classifies an unconfigured Shazam file by Russian
  substring; it uses the stable `jobs.shazam.file_missing` message code. Its
  staged pipeline accepts `RenderableMessage` labels, so localized stage labels
  are resolved when rendered rather than captured when the operation starts.
- Recommendation generation stores numeric result descriptors (`library`,
  `total`) and catalog-backed progress/action descriptors. Switching locale now
  updates an already populated recommendation result while preserving provider
  title and artist values. Settings Primuse completion results also retain
  descriptors instead of rendered Russian summaries.
- Migrated the high-level YouTube Music settings card status/form/action copy
  added in this pass; OAuth completion progress is catalog-backed. The card is
  **not fully closed**: its browser account discovery, cookie-check/age-check
  result renderers, confirmation dialogs, placeholders, and several help texts
  still have app-owned literals and remain explicit Task 9 candidates below.
- Catalog-tree and ICU-parameter parity is covered by `i18n.test.ts`; added
  loaded-state locale-switch/data-invariance regressions for recommendations and
  settings.

## Candidate scan and unclosed scope

Command: `rg -n '>[А-Яа-я]|"[А-Яа-я][^"]*"|` + "`[^`]*[А-Яа-я]" + "`' src/views/{MenuScreen,MiscScreen,RecommendScreen,SettingsScreen}.tsx src/views/settings/{YtmCard,parts}.tsx src/features/{ytm,editor} -g '*.{ts,tsx}'`.

- `views/settings/YtmCard.tsx`: unclosed application copy at account labels and
  progress (103–114), extract/remove/auth flows (149–212), browser-cookie
  controls/help/labels (241–447), cookie-delete confirmation (453–465), and
  `YtChecks` states/results (477–562). Account name/handle, browser/profile
  names, Page ID, returned errors, and provider titles in those regions are data
  exclusions, not catalog candidates.
- `features/editor/useMetaSources.ts` (104, 139, 152),
  `features/editor/TrackEditorDialog.tsx` (36, 54–55), and
  `features/editor/BatchEditorDialog.tsx` (38, 42, 121, 140, 143–147,
  182–201, 216) remain candidate-bearing related editor files. This batch did
  not migrate them.
- The scan also sees comments and the native `Русский` locale autonym in
  `SettingsScreen`; both are intentional exclusions. It is not an exhaustive
  source-wide clearance and does not close other previously mapped YTM/editor
  files.

## Verification — 2026-10-15 (remaining UI families batch)

- `cd frontend && npm test -- miscScreen.test.tsx recommendScreen.test.tsx settingsScreen.test.tsx menu.test.tsx i18n.test.ts` — 49 passed.
- `cd frontend && npm test` — 263 passed.
- `cd frontend && npm run build` — passed (`tsc --noEmit` and Vite production build).

## 2026-10-15 — YTM authorization, settings helpers, and editor dialogs

- Completed the remaining application-owned copy in `YtmCard`: browser-account
  discovery, extraction, authorization/cookie deletion confirmations, cookie
  and age checks, OAuth/header fallback, labels, placeholders, help text, and
  button/ARIA text now resolve through the EN/RU catalogs. Browser names,
  profiles, account names/handles, Page IDs, provider titles, paths, and raw
  server errors remain data and are rendered verbatim.
- Browser account state now stores raw `AccountCandidate` data rather than a
  pre-rendered option label. The option label is built during render, so an
  already discovered account list follows an immediate locale switch without
  changing the provider account data.
- Migrated the remaining imperative editor dialogs (`TrackEditorDialog` and
  `BatchEditorDialog`) and metadata-source warning helpers. Dialog titles and
  actions are translated when opened; completion/error toasts carry stable
  `RenderableMessage` descriptors, allowing the toast renderer to resolve them
  in the active locale instead of preserving Russian strings in operation state.
- Added catalog parity for the YTM authorization/checks and editor dialog/batch
  namespaces in both locales. The focused source scan of `YtmCard`, settings
  helpers, and the migrated editor helpers returned no application-owned
  Cyrillic literals.
- Added a regression that mounts the loaded settings screen in Russian, changes
  locale to English, and verifies the YTM authorization controls rerender while
  the browser data remains mounted. Updated metadata/editor tests to assert the
  descriptor contract rather than rendered Russian implementation strings.

## Verification — 2026-10-15 (YTM/editor completion)

- `cd frontend && npm test -- settingsScreen.test.tsx ytmCards.test.tsx editorDialogs.test.tsx trackEditor.test.tsx` — 35 passed.
- `cd frontend && npm test` — 264 passed.
- `cd frontend && npm run build` — passed (`tsc --noEmit` and Vite production build).
- `cd frontend && rg -n '>[А-Яа-я]|"[А-Яа-я][^"]*"|` + "`[^`]*[А-Яа-я]`" + `' src/views/settings/YtmCard.tsx src/views/settings/parts.tsx src/features/editor/useMetaSources.ts src/features/editor/TrackEditorDialog.tsx src/features/editor/BatchEditorDialog.tsx || true` — no matches.

## 2026-10-15 — deferred fallback and progress accessibility follow-up

- Added a deferred browser-extract regression for a response without
  `account.name`. The UI retains the `settings.ytm.browser_accounts.unknown`
  descriptor, renders its Russian fallback, and rerenders it in English after a
  locale switch instead of retaining a rendered string.
- Added an accessibility regression for `ProgressBar`: its `progressbar` role
  has the catalog-backed accessible name in Russian and English, while the
  bounded numeric value remains exposed through `aria-valuenow`.
- Removed the unused `translateRef` from `DialogProvider`; no code reads it.

## Verification — 2026-10-15 (deferred fallback/accessibility follow-up)

- `cd frontend && npm test -- settingsScreen.test.tsx i18n.test.tsx` — 2 files,
  26 tests passed.
- `cd frontend && npm run build` — passed (`tsc --noEmit` and Vite production
  build).

## 2026-10-15 — scoped reviewer follow-up

- The `ProgressBar` locale regression now keeps a reference to the initially
  mounted `progressbar`, changes the locale, awaits the English accessible-name
  query, and asserts that same node has updated. It no longer calls `rerender`,
  so the test covers the `useTranslation` subscription rather than a fresh mount.
- Renamed the `DialogProvider` default-label test to match its actual coverage:
  it verifies locale-sensitive defaults only and does not claim to exercise
  caller-provided labels.

## Verification — 2026-10-15 (scoped reviewer follow-up)

- `cd frontend && npm test -- i18n.test.tsx dialogs.test.tsx` — 3 files,
  35 tests passed.
- `cd frontend && npm test` — 35 files, 270 tests passed.
- `cd frontend && npm run build` — passed (`tsc --noEmit` and Vite production
  build).

## 2026-10-15 — Task 9 reviewer closure follow-up

- `QualityScreen` plan confirmation now stores only `RenderableMessage`
  descriptors for the title and actions; the body is a locale-reactive React
  component. An already-open plan dialog updates its heading, sections, table
  headers, and action labels after a locale switch.
- `SearchScreen` operation stages are static descriptor arrays and `Pipeline`
  resolves their labels at render time. The audit found no other `startOp`
  consumer that snapshots `t()` stage labels: `MiscScreen` already passes
  descriptors, and the remaining consumers start unstaged progress panels.
- Removed `CAT_LABELS_RU` and `CAUSE_LABELS_RU`. Known diagnostic categories
  are catalog entries and known normalization causes have explicit
  `quality.cause.*` entries in EN/RU. Unknown IDs deliberately remain raw data
  rather than becoming an opaque missing-key string.
- `QueueItem` now subscribes through `useTranslation`, so mounted descriptor
  titles and status text rerender when the locale changes.
- Added `common.empty_value` and migrated the application placeholder in
  `TrackRow`, Search rows, and the YouTube fallback detail row. The same em dash
  remains where it is data formatting outside this scope.
- Lyrics-batch per-file progress is now the ICU descriptor
  `quality.lyrics_item_progress` with `completed`, `total`, and raw `path`
  data; it no longer stores an interpolated string in operation state.
- Backend descriptor validation now scans all direct `message(...)` producers
  under `src/`: every call must name `fallback`; literal fallbacks must be
  nonblank. The helper continues to reject blank dynamic values at runtime.
- Technical exclusions recorded in the localization ledger: `cookies.txt`,
  `client_id`, and `client_secret` are protocol/file identifiers, not
  translatable product copy.

## Audit closure state

The eight reviewer findings are closed. This does **not** claim Task 9's full
historical source inventory is closed: the report's earlier candidate scan is
the authoritative record of any unrelated remaining scope.

## 2026-10-15 — fallback-catalog scanner reviewer follow-up

- The backend fallback scanner now follows lexical scope for imported
  `message` helpers. It validates supported `src.messages`/`messages` imports
  and aliases, including the relative `diagnostic_message` aliases in
  `health`, `lint`, and `quality`, but does not mistake same-named parameters
  or locally defined functions for descriptor producers.
- Added parameterized regressions for direct, aliased, legacy `messages`, and
  unrelated imports, plus parameter, local-function, and nested-shadow cases.

## Verification — 2026-10-15 (fallback-catalog scanner follow-up)

- `pytest tests/test_job_catalogs.py` — 15 passed.
- `pytest` — 777 passed; 2 pre-existing third-party deprecation warnings from
  FastAPI/Starlette test-client dependencies.
