# Localization key / data map — Task 1 (open; current status below)

Source: `docs/superpowers/specs/2026-10-14-localization-design.md`, plan `docs/superpowers/plans/2026-10-14-localization.md`, task brief. This is an inventory and migration contract, **not** a completed locale catalog. The CURRENT ledger below is authoritative for closure state. Older `P` / `SOURCE_PHRASE_PENDING` lists and continuation counts are historical snapshots, not active file status. A `reviewed, unverified` file is **not closed**: every candidate still needs comparison with an occurrence row or a bounded exemption.

## CURRENT closure ledger — 2026-10-15 (Task 1 OPEN)

Scope: exactly 83 files matching `frontend/src/**/*.{ts,tsx}` plus `frontend/index.html`. Source locations in tables below are relative to `frontend/src/`. The numeric `:NNN` *map-document* references in this ledger refer to line numbers in the **pre-CURRENT-ledger snapshot**, retained as historical coordinates; use the named section and source occurrence for navigation after this insertion, not the shifted document line number. `S` = previous source occurrence rows exist but exhaustive English/Russian and conditional-branch comparison has **not** passed; `T` = previously read, explicit no-owned-copy / technical or data exemption at cited section (not an exemption for caller-provided text); `U` = occurrence rows exist but previously identified partial reconciliation remains; `H` = HTML entry audited as non-copy, with locale metadata requirement. **Only T/H are file-level audited exclusions; no S/U entry is a closure assertion.** The canonical active occurrence table is the union of the explicitly keyed tables in “Frontend catalog ownership” (baseline, shell, nested follow-up), “Continuation audit”, and the three “Continuation” tables below. Rows using slash-separated alternatives represent separate catalog keys, not concatenated catalog text. Historical paragraphs under those sections retain provenance only; their pending counts/status are superseded by this ledger. The current table is intentionally honest rather than a fabricated full occurrence table.

| Frontend file | Status | Existing occurrence rows or exact exclusion evidence |
|---|---|---|
| `App.tsx` | S | shell :249 / continuation :496 |
| `nav.ts` | S | baseline :180–186 / continuation :497–498 |
| `main.tsx` | T | continuation no-copy :555, bootstrap |
| `routes.ts` | T | continuation no-copy :555, route IDs |
| `i18n/index.ts` | T | locale-runtime bootstrap; locale IDs and storage/API identifiers, no owned rendered copy |
| `i18n/messages.ts` | T | descriptor resolver and diagnostic fallbacks; catalog keys/codes are technical identifiers |
| `components/Topbar.tsx` | S | shell :251–256 / continuation :499–504 |
| `components/Tabbar.tsx` | S | shell :257–258 / continuation :505 |
| `components/MoreMenu.tsx` | S | shell :259 / continuation :506 |
| `components/CommandPalette.tsx` | S | shell :260–265 / continuation :507 |
| `components/DownloadsDock.tsx` | S | continuation :531–539; job-name consumers :551 |
| `components/PlayerBar.tsx` | S | continuation :529–530 |
| `components/AudioPlayer.tsx` | S | continuation :524–525; clock exemption :555 |
| `components/PreviewButton.tsx` | S | continuation :526–529 |
| `components/dialogs/KeymapDialog.tsx` | S | shell :265–273 / continuation :508–509 |
| `components/dialogs/DialogProvider.tsx` | S | shell :274–276 / continuation :510–511; caller boundary :551 |
| `components/ui/Spinner.tsx` | S | shell :277 / continuation :512 |
| `components/ui/Pipeline.tsx` | S | continuation :513–519 |
| `components/ui/ProgressBar.tsx` | S | continuation :520; caller boundary :551 |
| `components/ui/QueueItem.tsx` | S | continuation :521–522; caller boundary :551 |
| `components/ui/TrackRow.tsx` | S | continuation :523; data boundary :551 |
| `components/ui/Button.tsx` | T | continuation no-copy :555, CSS/caller props |
| `components/ui/Table.tsx` | T | continuation no-copy :555, caller headers/rows |
| `components/ui/SkeletonRows.tsx` | T | continuation no-copy :555, aria-hidden geometry |
| `components/ui/Cover.tsx` | T | continuation no-copy :555, caller alt |
| `components/ui/EmptyState.tsx` | T | continuation no-copy :555, caller title/sub |
| `components/ui/Icon.tsx` | T | continuation no-copy :555, SVG |
| `components/ui/SegControl.tsx` | T | continuation no-copy :555, caller options |
| `components/ui/CollapsibleGroup.tsx` | T | continuation no-copy :555, caller title |
| `components/ui/StatusLine.tsx` | T | continuation no-copy :555, caller content |
| `views/DiscoverScreen.tsx` | S | continuation six views :645 onward |
| `views/LibraryScreen.tsx` | S | continuation six views :645 onward |
| `views/MenuScreen.tsx` | S | continuation six views :645 onward |
| `views/MiscScreen.tsx` | S | continuation six views :645 onward |
| `views/RecommendScreen.tsx` | S | continuation six views :645 onward |
| `views/SearchScreen.tsx` | S | continuation six views :645 onward |
| `views/QualityScreen.tsx` | U | nested follow-up :316–374; partial audit :446 |
| `views/SettingsScreen.tsx` | U | nested follow-up :420–444; partial audit :446 |
| `views/MenuSkeleton.tsx` | T | nested follow-up exemption :444, aria-hidden geometry |
| `views/QualitySkeleton.tsx` | T | nested follow-up exemption :444, aria-hidden geometry |
| `views/library/LibrarySkeleton.tsx` | T | nested follow-up exemption :444, aria-hidden geometry |
| `views/library/AlbumsTab.tsx` | S | continuation ten nested files :878 onward |
| `views/library/ArtistsTab.tsx` | S | continuation ten nested files :878 onward |
| `views/library/Cards.tsx` | S | continuation ten nested files :878 onward |
| `views/library/Inbox.tsx` | S | continuation ten nested files :878 onward |
| `views/library/PlaylistsTab.tsx` | S | continuation ten nested files :878 onward |
| `views/library/TracksTab.tsx` | S | continuation ten nested files :878 onward |
| `views/library/albumDetail.tsx` | S | continuation ten nested files :878 onward |
| `views/library/trackDetail.tsx` | S | continuation ten nested files :878 onward |
| `views/library/libUtils.ts` | S | continuation ten nested files :878 onward; formatting :635–641 |
| `views/library/useYtData.ts` | T | continuation no-copy :555, API/cache IDs |
| `views/settings/parts.tsx` | U | nested follow-up :415–419; partial audit :446 |
| `views/settings/YtmCard.tsx` | S | continuation ten nested files :878 onward |
| `views/settings/SettingsSkeleton.tsx` | T | nested follow-up exemption :444, aria-hidden geometry |
| `features/editor/BatchEditorDialog.tsx` | S | editor continuation :571–584 |
| `features/editor/TrackEditor.tsx` | S | editor continuation :585–608 |
| `features/editor/TrackEditorDialog.tsx` | S | editor continuation :609–612 |
| `features/editor/runMetaflow.ts` | S | continuation :549 |
| `features/editor/useMetaSources.ts` | S | continuation :547–548 |
| `features/editor/index.ts` | T | nested follow-up exemption :444, re-export |
| `features/ytm/detail.tsx` | U | nested follow-up :378–389; partial audit :446 |
| `features/ytm/cards.tsx` | U | nested follow-up :381–397; partial audit :446 |
| `features/ytm/rows.tsx` | U | nested follow-up :398–401; partial audit :446 |
| `features/ytm/badges.tsx` | U | nested follow-up :402–405; partial audit :446 |
| `features/ytm/download.ts` | U | nested follow-up :406–411; partial audit :446 |
| `features/ytm/types.ts` | T | nested follow-up exemption :411, DTOs |
| `features/ytm/settings.ts` | T | nested follow-up exemption :411, config IDs |
| `features/ytm/index.ts` | T | nested follow-up exemption :411, re-export |
| `lib/api.ts` | T | continuation no-owned-copy :551,555; HTTP statusText is platform data |
| `lib/diff.ts` | T | continuation no-copy :555, tag-value tokens |
| `lib/diff.tsx` | T | continuation no-copy :555, diff rendering |
| `lib/format.ts` | S | formatting continuation :635–641; locale-sensitive formats |
| `lib/hotkeys.ts` | T | continuation no-copy :555, key identifiers |
| `lib/jobs.ts` | S | continuation :545–546; backend descriptor transport :551 |
| `lib/ops.tsx` | T | continuation no-copy :551,555, caller stages/messages |
| `lib/prefetch.ts` | T | continuation no-copy :555, API/cache IDs |
| `lib/tags.ts` | S | editor continuation :613–631 |
| `lib/toast.tsx` | T | continuation no-copy :551,555, caller title/body |
| `stores/downloads.ts` | S | continuation :540–544 |
| `stores/player.ts` | S | continuation :529, preview fallback |
| `stores/overlays.ts` | T | continuation no-copy :555, state IDs |
| `hooks/useTheme.ts` | T | continuation no-copy :555, theme/CSS IDs |
| `hooks/useHashRoute.ts` | T | continuation no-copy :555, route IDs |
| `frontend/index.html` | H | entry HTML :279,557–559; product name only, lang must follow effective locale |

**Verification gate, not waived by prior tables:** compare *every* frontend source hit, including English-only text, against exact occurrence row or per-file exclusion; unresolved matches remain blockers. The wide scan (`rg -n 'aria-label=|title=|alt=|placeholder=|toast\(|\.confirm\(|\.prompt\(|\.info\(|\.pick\(|\.open\(|\.set\(|<[^>]+>[^<{]*[[:alpha:]]|label:|text:|sub:|heading=|message' frontend/src -g '*.ts' -g '*.tsx'`) returned **778 lines** across the earlier 81-file snapshot; it was not rerun or reconciled line-by-line after the source set reached 83 files. This is a candidate count, not 778 distinct phrases or 778 misses. In particular `U` paths above have known partial coverage. No active claim of full frontend closure is made.

**2026-10-15 confirmed-audit addendum (bounded, not full reconciliation):** `ytm.empty` is an owned generic no-results key (`Nothing found` / `Ничего не найдено`) used by `views/MenuScreen.tsx:171,195` and `views/MiscScreen.tsx:188`; all three occurrences are now catalog-backed. `components/PreviewButton.tsx` preserves `ApiError.renderableMessage` through `asRenderableMessage()` into the toast, while legacy provider strings remain verbatim. The following are bounded technical/data exemptions, not catalog keys: `client_id (YouTube Data API)` and `client_secret` in `views/settings/YtmCard.tsx` are OAuth credential identifiers; `Inbox` where it names the filesystem directory is a literal folder token; `English` and `Русский` in the language selector are self-names. These decisions close only these occurrences, not their containing `S` files or Task 1/Task 9.

## Frozen wire contract (use exactly these field names)

`RenderableMessage = string | {code: string, params?: Record<string, JsonValue>, message?: string}`; Python `message(code, params=None, *, fallback)` returns `{code, params: params or {}, message: fallback}`. Every newly produced owned descriptor **must** carry nonblank, human-readable English `message` (backend responsibility; independent of catalog availability). Known codes resolve in frontend ICU catalog in active locale; legacy string renders unchanged. For unknown/missing code, `resolveMessage(value: RenderableMessage): string` returns nonblank `value.message` verbatim, otherwise localized `common.errors.unavailable` (`Something went wrong` / `Что-то пошло не так`), NEVER the opaque `code`. In development/test also visibly report missing code (e.g. console.error with code + boundary, plus test assertion/diagnostic UI), while returning the same safe user text; telemetry/debug is not UI text. Treat invalid/blank descriptor `message` as absent; do not interpolate unknown params into fallback. Never translate arbitrary exceptions, provider text, music data. JSON parameters only (no Path/object instances). HTTP: `detail: RenderableMessage`, field validation `errors: Record<string, RenderableMessage>`; keep string `detail`, `{detail:{message:string}}`, string field errors. Jobs: `name: RenderableMessage`, `error: RenderableMessage | null`, progress `{type:"progress", message: RenderableMessage, percent?:number, ...}`; legacy `msg`, string name/error read during migration. `/api/jobs` and `/api/jobs/{id}` polling and `/api/jobs/{id}/events` SSE must agree. Diagnostics: only `message` changes type, including `issues`, nested `tracks[].issues`, `fixes`, `conflicts`, apply `results[].conflicts[].message`; do not repurpose the outer `error` on apply results without supporting legacy strings. Discriminators `kind`, `category`, `cause`, `action`, `field`, `status` stay stable as raw IDs. Codes use `nav.*`, `settings.*`, `api.errors.*`, `api.fields.*`, `jobs.<feature>.*`, `diagnostics.<health|lint|quality>.*`, plus feature namespaces (`library.*`, `quality.*`, `editor.*`, `search.*`, `discover.*`, `recommend.*`, `ytm.*`, `shazam.*`, `shell.*`, `dialogs.*`, `player.*`, `common.*`). A code is a stable identifier, not derived from a rendered phrase.

**Freeze clarifications (binding for Tasks 2–10):** `error` in new job DTOs is `null` until failure; tolerate historical `""` (current `jobs.py:32`) and strings. Progress `message` is the canonical field; on legacy events use `msg` if `message` absent, never interpret recommendation `kind`, `seed`, `items` or `total` as prose. SSE terminal `done` contains no result (fetch status); terminal `error` has `error`, followed by `end`; polling `progress` is an array with the last progress event, not a single object. Existing `JobManager.submit` catches **every** exception and uses `str(e)`; migrate known app-owned failure branches explicitly, leave unknown exceptions as readable strings. Structured errors must remain descriptors through `ApiError`, operation state, toast and editor field state until display; `Error.message` stays readable for logs, not a localization source. FastAPI-generated validation errors outside application-owned constructors are not implicitly cataloged.

**Historical ambiguity, superseded below:** legacy config without a `language` key is *unset*, not an explicit `en` selection. The binding representation is `language: null` as specified in the Canonical contract addendum below. Frontend uses supported `navigator.language`, then `en`, if server selection is unset; explicit saved `en`/`ru` always overrides cache/browser. Invalid persisted values are treated as unset. The config getter may return `en` for internal use but is not used alone to serialize saved selection. PUT without `language` preserves existing state; failed PUT leaves active language unchanged. Tests distinguish unset from saved English.

## Canonical contract addendum — Task 1 freeze / handoff (2026-10-14)

This addendum is the active contract for implementation. Earlier alternatives in the historical tables remain as evidence of prior analysis, but are not implementation instructions.

### Standalone `server.py` 503 page

- `src/web/server.py` is **web-only**. It keeps HTTP 503 and serves its own bilingual HTML; it does not use the SPA, i18next, `/api/settings`, or localStorage.
- Resolve `Accept-Language` by descending `q`; support `ru`/`ru-*` and `en`/`en-*`; skip unsupported ranges and `q=0`; use English when no supported range matches or the header is absent.
- The selected response must keep `<html lang>` and `Content-Language` aligned with the selected locale. Commands, product names, paths and other literal instructions remain data.
- The standalone page is not a CLI localization requirement. Per PM decision, `server.py` terminal output is explicitly **CLI out of scope** for Task 1 and the web localization contract.

### Owned copy versus external/OS errors

- If a branch has only an owned message, emit the exact frozen code and JSON params with a nonblank readable English `message` fallback.
- If a branch has an owned prefix plus raw provider/OS/third-party reason and no independently valid English fallback has been specified, preserve the **complete legacy string**. Do not assign a prefix code merely because the prefix itself is owned.
- Raw provider/OS/third-party text is never translated, parsed as a catalog key, or used to manufacture a code. Unknown exceptions remain readable legacy strings at the generic boundary.
- This rule supersedes the historical “either code the prefix or keep the whole string” alternatives in the old HTTP decision discussion. The current branch decisions in the table below are authoritative; unresolved branches remain open audit items, not permission to choose either behavior during implementation.

### Frozen DTO names and shapes

- HTTP: `detail: RenderableMessage`; field validation `errors: Record<string, RenderableMessage>`. Preserve legacy string `detail`, `{detail: {message: string}}`, and string field errors.
- Jobs: `name: RenderableMessage`, `error: RenderableMessage | null`, progress `{type: "progress", message: RenderableMessage, percent?: number, ...}`. Legacy `msg`, string names, and string errors are read during migration. `error` is `null` on success; historical `""` is tolerated.
- Polling `/api/jobs` and `/api/jobs/{id}` and SSE `/api/jobs/{id}/events` must agree on these names. SSE `done` has no result; terminal `error` carries `error` and is followed by `end`.
- Diagnostics: only user-facing `message` fields become `RenderableMessage`, including nested issues, fixes, conflicts and apply result conflict messages. Stable raw IDs remain `kind`, `category`, `cause`, `action`, `field`, and `status`.
- Normalize DTOs remain view-only data: `{field, path, old, new, cause}` with no `message`. The frontend may construct a temporary `diagnostics.quality.change` descriptor only while rendering; it must not write a localized sentence back into the DTO.
- Compression `result.label` is `RenderableMessage` only for the `/api/compress` result DTO; unrelated provider/music `label` fields remain data. Known owned download/apply failures use the exact frozen result/error locations; unknown result errors remain strings.
- Rich CLI output remains English-only and is not localized. When health/lint/normalize issue messages become descriptors, CLI formatters print their readable English `message` fallback; legacy strings print unchanged.

### Unset locale API representation

- `GET /api/settings` always returns `language: null` when no valid user choice is persisted. A saved choice returns exactly `"en"` or `"ru"`; do not omit the field or return a computed browser/default locale in its place.
- The config getter may return `"en"` for safe internal use, but the GET endpoint must inspect persisted config separately so the frontend can distinguish unset from explicitly saved English.
- A PUT without `language` preserves existing config, including absence. Invalid persisted values are treated as unset.

### Defaults and diagnostic field resolution

- `Various Artists` at the library prompt is an editable tag default, not a translatable UI label. Preserve it verbatim in every locale to avoid changing a written tag.
- Diagnostic field parameters carry stable raw IDs (`artist`, `title`, `album`, `album_artist`, `genre`, `year`, `cover`, `track_number`, `disc_number`, `isrc`, `composer`, `publisher`, `comment`), never prelocalized labels.
- `resolveFieldLabel(field, locale)` maps known IDs through `editor.fields.*`; an unknown ID is reported in development/tests and rendered as its raw string value, never as an opaque translation key.
- `resolveMessage(value)` preserves legacy strings, resolves known codes in the active locale, and for unknown/missing/invalid descriptors returns nonblank `value.message` verbatim when present, otherwise localized `common.errors.unavailable`. It never displays the opaque `code` or interpolates unknown params into the fallback.

### Open audit evidence and required final scan

- Frontend evidence: 83 source files plus `frontend/index.html`; the earlier 81-file wide candidate scan = **778 matching lines**. This is a line-hit count, not a phrase or miss count; it has not been rerun or reconciled line-by-line against the 83-file source set, including English-only hits.
- Backend evidence: routes/jobs/diagnostics/normalize candidate scan = **164 matching lines**, including multiline declarations and value lines. This is not 164 independent messages and is not closed branch coverage.
- Required before Task 1 can be accepted: rerun the final implementation scan for the 83-file source set and reconcile every resulting frontend hit plus every 164 backend candidate line to one exact occurrence row, bounded technical/data exclusion, or explicitly justified legacy-string branch; then validate DTO names, params, fallback text, transport parity, 503 negotiation, and EN/RU catalog/ICU parity.
- Known open anchors include `QualityScreen.tsx` conditional/prose branches, `SettingsScreen.tsx`, `views/settings/parts.tsx`, copy-bearing YTM modules, `_BatchProgress` indirect pushes, nested quality apply/diagnostic serialization, and the standalone 503 tests. These examples do not constitute a complete unmatched-hit list.

```
routes.py HTTP detail/errors → FastAPI JSON → lib/api.ts ApiError → screen/editor/toast/dialog
routes.py jobs.submit/push + jobs.py fail → jobs.py Job.events/to_dict/stream
  → /api/jobs & /api/jobs/{id} → stores/downloads.ts → DownloadsDock
  → /api/jobs/{id}/events → lib/jobs.ts waitJob/startJob → DownloadsDock + screen progress
health.py + lint.py + normalize.py → quality.py → routes.py serializers
  → /api/health, /api/lint, /api/normalize/plan, /api/library/quality[/plan|/apply]
  → QualityScreen.tsx (+ tests); path/tag/provider values pass through verbatim
```

## Concrete backend code list

### CURRENT backend transport audit status (OPEN)

The `routes.py` / `jobs.py` / health, lint, quality and normalize scan used an untruncated `rg -n 'HTTPException|detail=|JSONResponse|\.push\(|message=|msg=|jobs\.submit|errors\[|RuntimeError|\["label"\]|\["error"\]|\.fail\(' src/web src/health.py src/lint.py src/quality.py src/normalize.py`: **164 matching lines**, including both declaration and value lines on multiline calls. These are candidate lines, not independent messages. The earlier backend tables provide many candidate keys, but are **not a closed branch-by-branch contract**. In particular, remove all alternatives in the old HTTP decision paragraph and in the formatting/quality/YTM tables before implementation. For the following identified branches the current contract is explicit (not a request to translate unknown exception text):

| Producer occurrence | Current decision | Transport / consumer |
|---|---|---|
| `routes.py:467` | frozen legacy full original `detail` string with raw `reason`; `api.errors.invalid_cookies` is **not assigned** to this branch | HTTP → `lib/api.ts` → settings error UI |
| `routes.py:609,757,761,1329,2199` | frozen legacy raw `detail` string | HTTP → `lib/api.ts` → calling UI |
| `routes.py:927,937,947,966,987,1024,1066,1088,1145,1158,1283,1304,1704,2033` | frozen legacy complete `detail` with owned Russian prefix and raw external/OS reason; no prefix code is assigned until an English fallback independent of exception language is specified | HTTP → `lib/api.ts` → screen/dialog/toast |
| `routes.py:1307` | `api.errors.empty_playlist` for no provider error; when `engine.last_error` is present, frozen legacy complete `detail` with suffix; `api.errors.empty_playlist_reason` is **not assigned** to this branch | HTTP → `lib/api.ts` → YTM playlist UI |
| `routes.py:1787,1819–1822` | `api.fields.year_four_digits` / `api.fields.integer_required` in `detail` or `errors[field]` respectively; 1819 response `detail` = `api.errors.check_fields`; keep field name as raw ID | HTTP → `lib/api.ts` → editor field state |
| `routes.py:1235,1471` | known absent `res.error`: `jobs.download.failed`; present unknown `res.error`: legacy string | job `result.items[].error` → Search/YTM/Misc UI |
| `routes.py:1252` | frozen legacy whole postprocessing error with raw exception; `jobs.download.postprocess_failed` is **not assigned** to this branch | job `result.items[].error` → Search/YTM UI |
| `routes.py:1372` | owned missing-result fallback `jobs.download.unknown_error`; present `result.error` stays legacy; capture at job boundary before generic `jobs.py:131` | `Job.error` → polling/SSE → downloads/screen |
| `routes.py:2467–2471,2518` | owned known job failures `jobs.shazam.file_missing`, `jobs.shazam.empty_file`, `jobs.shazam.file_unset` respectively; handle explicitly before generic catch | `Job.error` → polling/SSE/history |
| `jobs.py:131` | frozen legacy `str(e)` only for *unknown* exceptions; do not turn into an opaque or generic code | `Job.error` → polling/SSE/history |
| `quality.py:371` | owned `diagnostics.quality.write_tags_failed`; `:376,398` frozen legacy raw `str(exc)` | nested apply `results[].error` → QualityScreen |

All other owned direct job submit/push and diagnostics rows remain candidate mappings in the tables below; **do not interpret this decision table as certification that all 164 matches have been paired with code/params/fallback**. Additional checks must include `_BatchProgress.update/complete` indirect pushes, `result.label`, `result.items[].error`, and nested quality conflict/apply. `server.py:20–50,77–79` is a standalone 503 HTML response: EN/RU heading/title/paragraph variants, `Accept-Language` descending `q`, skip unsupported and `q=0`, English default, correct `<html lang>` and `Content-Language`; tests include explicit `ru`, `en`, default, unsupported and q-values. This is part of the current contract and is not served through SPA settings. `health.py:370–415`, `lint.py:310–343`, `normalize.py:361–376` render Rich CLI prose; CLI is not localized, but formatters print a descriptor's readable English `message` fallback (legacy strings unchanged), never a Python dict. Full backend closure is blocked by the unreconciled lines.

Notation: each row `code | EN source (ICU) | RU (ICU) | params | producer` ; owner = backend producer, translation owner = frontend catalogs. All params are data, not separately translated. Same code may serve multiple locations. Fallback English is produced with params resolved (not an ICU expression). API rows travel through `detail` to `lib/api.ts`; `api.fields.*` through `errors[field]` to editor validation. Source line references are pre-migration.

| Code | EN | RU | Params | Producer: `src/web/routes.py` lines |
|---|---|---|---|---|
| api.errors.empty_path | Empty path | Пустой путь | — | 105 |
| api.errors.file_not_found | File not found: {path} | Файл не найден: {path} | path | 112; plain variant at 2500 uses separate code below |
| api.errors.file_missing | File not found | Файл не найден | — | 2500 |
| api.errors.expected_list | {field} must be a list of sources | {field} должен быть списком источников | field (technical request key) | 294,310,2178 |
| api.errors.unknown_source | Unknown source: {source} | Неизвестный источник: {source} | source | 301,317 |
| api.errors.invalid_setting | Invalid value: {key} | Некорректное значение: {key} | key | 334,346,401; new language validation |
| api.errors.invalid_transliteration | Invalid transliteration mode: {value} | Неверный режим транслитерации: {value} | value | 359 |
| api.errors.invalid_feedback | Invalid feedback action: {value} | Неверное действие фидбека: {value} | value | 366 |
| api.errors.invalid_search_source | Invalid search source: {value} | Неверный источник поиска: {value} | value | 373 |
| api.errors.unknown_browser | Unknown browser: {browser} (available: {available}) | Неизвестный браузер: {browser} (доступны: {available}) | browser, available | 383,514; available is technical browser list |
| api.errors.invalid_format | Invalid format: {value} | Неверный формат: {value} | value | 403 |
| api.errors.invalid_source_format | Invalid source format: {value} | Неверный формат источника: {value} | value | 406 |
| api.errors.quality_out_of_range | Quality must be between 1 and 512 | Качество вне диапазона (1..512) | — | 408 |
| api.errors.invalid_cookies | Invalid cookies.txt: {reason} | Некорректный cookies.txt: {reason} | reason (untrusted, verbatim) | historical proposal only; not assigned to routes.py:467, which remains full legacy string |
| api.errors.invalid_video_id | Invalid video_id | Некорректный video_id | — | 560 |
| api.errors.directory_not_found | Directory not found: {path} | Каталог не найден: {path} | path | 600 |
| api.errors.not_directory | Not a directory | Не каталог | — | 602 |
| api.errors.invalid_pick_kind | kind must be folder or file | kind должен быть folder|file | — | 632 |
| api.errors.invalid_authuser | Invalid authuser | Неверный authuser | — | 687 |
| api.errors.browser_required | Select a browser | Укажите браузер | — | 694,731 |
| api.errors.oauth_credentials_required | Provide client_id and client_secret (YouTube Data API app) | Укажите client_id и client_secret (приложение YouTube Data API) | — | 788 |
| api.errors.oauth_in_progress | OAuth is already running; wait for it to finish | OAuth уже запущен: дождитесь завершения | — | 794 |
| api.errors.artist_not_found | Artist not found | Исполнитель не найден | — | 989 |
| api.errors.album_not_found | Album not found | Альбом не найден | — | 1026 |
| api.errors.playlist_not_found | Playlist not found | Плейлист не найден | — | 1090 |
| api.errors.no_tracks | No tracks | Нет треков | — | 1185,2045 |
| api.errors.empty_playlist | Playlist is empty{reason} | Плейлист пуст{reason} | reason (optional provider suffix; if unsafe retain legacy string) | 1307 |
| api.errors.url_required | URL is required | Нет URL | — | 1405 |
| api.errors.empty_url_list | URL list is empty | Список URL пуст | — | 1435 |
| api.errors.job_not_found | Job not found | Задача не найдена | — | 1490,1498 |
| api.errors.library_directory_not_found | Library directory not found | Каталог библиотеки не найден | — | 1693 |
| api.errors.read_tags_failed | Could not read tags | Не удалось прочитать теги | — | 1867,1880,2182; 1704 has raw exception, see exclusions |
| api.errors.fields_must_be_object | fields must be an object | fields — словарь | — | 1783,1808 |
| api.errors.write_tags_failed | Could not write tags | Не удалось записать теги | — | 1792,1851,2225 |
| api.errors.check_fields | Check the fields | Проверьте поля | — | 1821 (`JSONResponse.detail`) |
| api.fields.year_four_digits | Year must be four digits, e.g. 2024 | Год должен состоять из 4 цифр, например 2024 | — | 1720 |
| api.fields.integer_required | Must be an integer | Должно быть целым числом | — | 1722 |
| api.errors.cover_format | Only JPEG and PNG are supported | Поддерживаются JPEG и PNG | — | 1829 |
| api.errors.invalid_cover | Invalid cover file | Некорректный файл обложки | — | 1833 |
| api.errors.empty_cover | Cover file is empty | Файл обложки пуст | — | 1835 |
| api.errors.cover_not_found | No cover art | Нет обложки | — | 1869 |
| api.errors.move_failed | Could not move file (name conflict or missing tags) | Не удалось перенести (конфликт имени или нет тегов) | — | 1944 |
| api.errors.invalid_dedup_mode | Invalid deduplication mode | Неверный режим дедупликации | — | 1983 |
| api.errors.delete_file_failed | Could not delete file: {reason} | Не удалось удалить файл: {reason} | reason raw OS exception: prefer legacy until classified | 2033 |
| api.errors.no_groups | No groups | Нет групп | — | 2107 |
| api.errors.no_files | No files | Нет файлов | — | 2338 |
| api.errors.invalid_line_number | Invalid line number | Некорректный номер строки | — | 2497 |
| api.errors.nothing_selected | Nothing selected | Ничего не выбрано | — | 2510 |
| api.errors.ytm_connection_required | Connect YouTube Music (Settings → YouTube Music) | Подключите YouTube Music (настройки → YouTube Music) | — | 2694 |
| api.errors.artist_title_required | artist and title are required | Нужны artist и title | — | 2740,2751 |

Provider/OS-origin errors at 609,757,761,927–1088,1145,1158,1283,1304,1329,1704,2199 are **not** translated as entire strings. **Historical decision evidence:** an earlier proposal listed two possible treatments for an owned prefix plus external failure. The active addendum resolves that ambiguity: use a code only where the branch has an independently valid English fallback; otherwise preserve the whole legacy string. Do not encode arbitrary exception text into a catalog key. Also check route 1821 `errors` map and 1787 first-error `detail` share the same field code. API test impact: `frontend/tests/api.test.ts`, `trackEditor.test.tsx`, `editorDialogs.test.tsx`; `tests/test_web_api.py`, `test_quality_api.py`.

**Historical HTTP decision evidence:** this paragraph recorded alternatives before the contract was frozen. The active addendum above is binding: known owned-only branches use descriptors; owned-prefix plus raw provider/OS reason remains a complete legacy string unless an independently valid English fallback is specified. Preserve the existing `api.errors.empty_playlist` and field-validation DTO differences recorded in the current branch table. HTTP status codes stay unchanged. Run a multiline `detail=` scan (including 2178) before closing Task 6.

Job entries: producer = `src/web/routes.py`; transport = submit response `name`, `jobs.py:to_dict` (history/status), `jobs.py:stream` (SSE); consumers = `frontend/src/lib/jobs.ts`, `stores/downloads.ts`, `components/DownloadsDock.tsx`, screen callbacks (`RecommendScreen`, `SearchScreen`, `MiscScreen`, `LibraryScreen`, `QualityScreen`, `SettingsScreen`). Params passed through safely as JSON values.

| Code | EN | RU | Params | Producer references |
|---|---|---|---|---|
| jobs.auth.extract_name | Extract browser cookies | Извлечение кук браузера | — | 710 |
| jobs.auth.accounts_name | Find browser accounts | Поиск аккаунтов в браузере | — | 739 |
| jobs.auth.oauth_name | YouTube Music OAuth | OAuth YouTube Music | — | 815 |
| jobs.auth.read_cookies | Reading browser cookies… | Читаю куки браузера… | — | 697,734 |
| jobs.auth.saved_checking | Authorization saved. Checking account… | Авторизация сохранена. Проверяем аккаунт… | — | 700,804 |
| jobs.auth.confirmation_link | Confirmation link received | Ссылка для подтверждения получена | — | 799 (`auth_url` extra is data) |
| jobs.auth.creating_session | Creating OAuth session… | Создание OAuth-сессии… | — | 802 |
| jobs.ytm.name | YouTube Music — download | YouTube Music — скачивание | — | 1270 |
| jobs.ytm.item | [{index}/{total}] {label} | [{index}/{total}] {label} | index,total,label, optional clip flag via separate `jobs.ytm.clip_missing` | 1225 |
| jobs.ytm.clip_missing | [{index}/{total}] {label} (video clip — audio version not found) | [{index}/{total}] {label} (клип — аудиоверсия не найдена) | index,total,label | 1225–1227 |
| jobs.ytm.bytes | {label} — {sizeMb} MB | {label} — {sizeMb} МБ | label,sizeMb | 1169 |
| jobs.ytm.item_failed | [{index}/{total}] error: {label} | [{index}/{total}] ошибка: {label} | index,total,label | 1238,1255 |
| jobs.ytm.item_downloaded | [{index}/{total}] downloaded: {label} | [{index}/{total}] скачано: {label} | index,total,label | 1260 |
| jobs.download.name | Download | Скачивание | — | 1411 |
| jobs.download.batch_name | Batch download | Пакетное скачивание | — | 1476 |
| jobs.download.fetching_info | Fetching video information… | Получение информации о видео... | — | 1360 |
| jobs.download.bytes | Downloading… {sizeMb} MB | Скачивание... {sizeMb} МБ | sizeMb | 1364 |
| jobs.download.tagging | Downloaded; processing tags… | Скачано, обработка тегов... | — | 1373 |
| jobs.download.batch_progress | [{index}/{total}] {name} — {sizeMb} MB | [{index}/{total}] {name} — {sizeMb} МБ | index,total,name,sizeMb | `_BatchProgress.update`:2602–2616 |
| jobs.download.batch_finished | [{index}/{total}] {name} — finished | [{index}/{total}] {name} — завершено | index,total,name | 2614 |
| jobs.download.batch_item | [{index}/{total}] {url}… | [{index}/{total}] {url}… | index,total,url | 1473 |
| jobs.download.unknown_error | Unknown error | Неизвестная ошибка | — | 1372 fallback only; raw `result.error` legacy |
| jobs.download.failed | Download error | Ошибка скачивания | — | 1235,1471 fallback item `error` (result DTO; Task 7 must normalize owned fallback) |
| jobs.download.postprocess_failed | Post-processing failed: {reason} | Ошибка обработки после скачивания: {reason} | reason (raw exception verbatim) | historical proposal only; not assigned to routes.py:1252, which remains full legacy string |
| jobs.download.batch_complete | [{index}/{total}] {label} | [{index}/{total}] {label} | index,total,label (URL slice or `Shazam` data/token) | 1473 and 2551–2554 via `_BatchProgress.complete`; old `jobs.download.batch_item` covers URL-only case but NOT Shazam |
| jobs.lyrics.name | Update lyrics | Обновление текстов | — | 1934 |
| jobs.lyrics.item | [{index}/{total}] {filename} | [{index}/{total}] {filename} | index,total,filename | 1926 |
| jobs.library.sort_name | Sort library | Сортировка библиотеки | — | 1965 |
| jobs.compress.name | Compression | Сжатие | — | 2360 |
| jobs.compress.item | [{index}/{total}] | [{index}/{total}] | index,total | 2356 |
| jobs.compress.audio_result | Audio compressed | Сжато аудио | — | 2357 result `label` (currently prose) |
| jobs.compress.cover_result | Covers recompressed | Пережато обложек | — | 2357 result `label` |
| jobs.primuse.backfill_name | Primuse — sidecars | Primuse — sidecar | — | 2383 |
| jobs.primuse.cleanup_name | Primuse — cleanup | Primuse — очистка | — | 2407 |
| jobs.primuse.scanning | Scanning sidecar files… | Сканирование sidecar-файлов... | — | 2402 |
| jobs.primuse.backfill_item | [{index}/{total}] {filename} | [{index}/{total}] {filename} | index,total,filename | 2377 |
| jobs.shazam.scan_name | Shazam — search | Shazam — поиск | — | 2488 |
| jobs.shazam.download_name | Shazam — download | Shazam — скачивание | — | 2581 |
| jobs.shazam.scanning | Searching for {count, plural, one {# track} other {# tracks}} in YouTube Music… | Поиск {count, plural, one {# трека} few {# треков} many {# треков} other {# трека}} в YouTube Music… | count | 2473 |
| jobs.shazam.processed | Processed {index}/{total} | Обработан {index}/{total} | index,total | 2477 |
| jobs.shazam.file_missing | Shazam file is not set or found — specify its path in Settings | Файл Shazam не задан или не найден — укажите путь в настройках | — | 2467–2469 (known job failure, not generic exception) |
| jobs.shazam.empty_file | File is empty or contains no recognized tracks | Файл пуст или не содержит распознанных треков | — | 2471 |
| jobs.shazam.file_unset | Shazam file is not set | Файл Shazam не задан | — | 2518 |
| jobs.recommend.name | Recommendations | Рекомендации | — | 2729 |
| jobs.recommend.scanning | Scanning library… | Сканирование библиотеки... | — | 2699 |
| jobs.recommend.radio | YouTube Music radio… | Радио YouTube Music... | — | 2705 |
| jobs.recommend.seed | Processed seed {index} of {total} | Обработан сид {index} из {total} | index,total | 2716; preserve `kind:recommendations`, `seed_index`, `seed_count`, `seed`, `items`, `seeds`, `library_count`, `total` |
| jobs.common.done | Done | Готово | — | 736,1975,2380,2404,2719, frontend `lib/jobs.ts` / downloads store |
| jobs.common.failed | Error | Ошибка | — | frontend fallback only |

`jobs.py:131` currently `job.fail(str(e))`: convert only recognized application failures; unknown exception stays string. Polling terminal `error`, SSE terminal `{type:"error",error}`, progress `message` (read old `msg`); done SSE has no `result`: `lib/jobs.ts` polls for it. `routes.py:1410–1414` uses the fixed `Скачивание` name (the frontend may supply a separate track/URL title), and `routes.py:1975` pushes done with no percent; preserve both. `_BatchProgress.complete(url, msg)` at 1473 and 2551 is an indirect push, not caught by a `job.push`-only inventory. Reconnect/history tests: `frontend/tests/jobs.test.ts`, `downloads.test.ts`, `downloadDock.test.tsx`; backend `tests/test_web_api.py`, job-related tests. Never turn `seed`, `url`, `filename`, `artist`, `title` into message keys; **`label` is data only when it originates from music/URL/file/provider.** Owned result labels are copy (see below).

**Result DTO decision (not silently excluded):** `/api/compress` returns `result: {done, skipped, label}` with `label = "Сжато аудио" | "Пережато обложек"`; `frontend/src/views/library/trackDetail.tsx:168–173` interpolates it into progress. Freeze `label: RenderableMessage` on *this* result only, using `jobs.compress.audio_result` / `jobs.compress.cover_result`, and accept old string result labels in frontend. Do not globally change fields called `label` (YT titles, picker options are separate). `/api/ytmusic/download` result `items[].error` and `/api/download/batch` result `items[].error` become `RenderableMessage` **for known owned fallback** `jobs.download.failed`; unknown `res.error` stays string. At `routes.py:1252`, post-processing failure stays the full legacy string; `jobs.download.postprocess_failed` is a historical proposal, not an assigned key. `SearchScreen.tsx:167` currently constructs `new Error(item.error)` and would stringify descriptors to `[object Object]`: resolve at UI boundary, preserving descriptor for locale switches where stored. Normal job `error` has `null` on success (legacy `""` accepted), job results retain their existing status/count/data fields. Apply `results[].error` is a different quality result field; see diagnostic decision below.

Diagnostic rows: owner `src/health.py`, `src/lint.py`, `src/quality.py`; transport `_issue_list_by_cat`, `_quality_issue_dict`, `_quality_plan_dict`, apply return in `src/web/routes.py:1584–1685,2232–2295`; consumer `QualityScreen.tsx` (other health/lint endpoints may be consumed externally). Expose `{code,params,message}` **inside each existing `message` field**. `normalize.py` produces changes with no `message`; its `field`, `old_value`, `new_value`, `cause` are data; `routes.py:_quality_change_dict` and `/normalize/plan` map these to `field,path,old,new,cause`, unchanged. Quality screen builds the display sentence separately under `diagnostics.quality.change`.

| Code | EN | RU | Params | Producer |
|---|---|---|---|---|
| diagnostics.health.unreadable | Could not read file | Не удалось прочитать файл | — | health.py:184 |
| diagnostics.health.missing_tag | Missing tag “{fieldLabel}” | Нет тега «{fieldLabel}» | wire: field (stable ID); formatter derives fieldLabel | health.py:198 |
| diagnostics.health.exact_duplicate | Exact duplicate (MD5 matches another file) | Точный дубликат (MD5 совпадает с другим файлом) | — | health.py:220 |
| diagnostics.health.semantic_duplicate | Semantic duplicate “{title}” | Семантический дубликат «{title}» | title | health.py:241 |
| diagnostics.health.filename_mismatch | Filename “{filename}” differs from title tag “{title}” | Имя файла «{filename}» ≠ тег «{title}» | filename,title | health.py:255 |
| diagnostics.health.loose_file | File is at library root, outside Artist/Album folders | Файл в корне библиотеки, вне структуры Artist/Album | — | health.py:266 |
| diagnostics.lint.whitespace | “{fieldLabel}”: extra spaces in “{value}” | «{fieldLabel}»: лишние пробелы в «{value}» | wire: field ID, value (trimmed first 40 chars, verbatim); formatter derives fieldLabel | lint.py:147 |
| diagnostics.lint.artist_case | Artist capitalization “{variant}” differs from “{canonical}” | Регистр исполнителя «{variant}» ≠ «{canonical}» | variant,canonical | lint.py:172 |
| diagnostics.lint.album_case | Album capitalization “{variant}” differs from “{canonical}” | Регистр альбома «{variant}» ≠ «{canonical}» | variant,canonical | lint.py:193 |
| diagnostics.lint.feat | Nonstandard featured artist in “{value}” (use “feat.”) | Фит в нестандартном виде: «{value}» (используйте «feat.») | value | lint.py:202 |
| diagnostics.lint.duplicate_track_number | “{value}”: duplicate album track number | «{value}»: повторяющийся номер трека в альбоме | value | lint.py:224 |
| diagnostics.lint.invalid_track_number | “{value}”: invalid track number | «{value}»: некорректный номер трека | value | lint.py:229 |
| diagnostics.lint.invalid_disc_number | “{value}”: invalid disc number | «{value}»: некорректный номер диска | value | lint.py:234 |
| diagnostics.lint.album_artist_conflict | Album Artist “{value}” conflicts with other tracks in the album | Album Artist «{value}» противоречит другим трекам альбома | value | lint.py:250 |
| diagnostics.lint.genre_conflict | Genre “{value}” differs from other album tracks ({others}) | Жанр «{value}» отличается от других треков альбома ({others}) | value,others (raw joined tag values; no translation) | lint.py:266 |
| diagnostics.lint.invalid_year | Invalid year “{value}” | Некорректный год «{value}» | value | lint.py:274 |
| diagnostics.quality.change | {fieldLabel}: “{old}” → “{new}” | {fieldLabel}: «{old}» → «{new}» | wire: field ID, old,new verbatim; formatter derives fieldLabel | quality.py:123; QualityScreen ChangeTable; normalize change DTO has **no** message |
| diagnostics.quality.duplicate_field | Field “{fieldLabel}” was selected for change more than once | Поле «{fieldLabel}» выбрано для изменения повторно | wire: field ID; formatter derives fieldLabel | quality.py:257 |
| diagnostics.quality.fix_move | “{filename}” → “{target}” | «{filename}» → «{target}» | filename,target (path verbatim) | quality.py:277 |
| diagnostics.quality.file_missing | File not found | Файл не найден | — | quality.py:292,299 |
| diagnostics.quality.target_exists | Target path occupied: {filename} | Целевой путь занят: {filename} | filename | quality.py:303 |
| diagnostics.quality.write_tags_failed | Could not write tags | Не удалось записать теги | — | quality.py:371 (`results[].error`, not `message`) |
| diagnostics.quality.target_occupied | Target path occupied | Целевой путь занят | — | quality.py:388 (`results[].conflicts[].message`) |

**Diagnostic field contract (single approach, no alternatives):** keep `HealthIssue`/`LintIssue`/`QualityIssue` JSON keys `category,path,message` (and quality severity/flags). For `diagnostics.health.missing_tag`, `diagnostics.lint.whitespace`, `diagnostics.quality.change`, `diagnostics.quality.duplicate_field`, backend sends `message.params.field` as stable raw ID, NEVER `fieldLabel`; whitespace also sends `value`, change also `old,new`. An optional top-level `field` discriminator may be added but must agree with params.field. Define frontend `resolveFieldLabel(field: JsonValue, locale: 'en'|'ru'): string`: for known string IDs in `FIELD_LABEL_KEYS` resolve `editor.fields.<id>` in active locale; for unknown ID report dev/test diagnostic and return `String(field)` (data, never use it as an i18n key). Define `resolveMessage(value: RenderableMessage): string`: for these four codes copy params, set local-only `fieldLabel = resolveFieldLabel(params.field, activeLocale)`, then call ICU `t(code, {...params, fieldLabel})`; do not mutate DTO. Do not pass raw `field` into a `{fieldLabel}` slot. `FIELD_LABEL_KEYS` exactly covers `artist,title,album,album_artist,genre,year,cover,track_number,disc_number,isrc,composer,publisher,comment`; labels in both catalogs, including `cover`. English backend fallbacks use the English-owned field label rather than Russian tuple values; unknown field fallback uses raw ID. Other codes have no implicit field conversion. `quality.py:126` normalization-change issue and `quality.py:259` conflict follow this rule. `src/web/routes.py:2281–2285` `/normalize/plan` change DTO remains `{field,path,old,new,cause}` with no `message`; `routes.py:_quality_change_dict` likewise stays data. For display of either DTO `renderNormalizationChange(change)` constructs a **view-only** descriptor `{code:'diagnostics.quality.change',params:{field:change.field,old:change.old??'',new:change.new??''}}` and calls `resolveMessage`; no change to tag values or cause. `QualityScreen.ChangeTable` currently shows field in a column and diff values separately; translate the field column with `resolveFieldLabel`, and if a summary sentence is needed use `renderNormalizationChange` (do not duplicate text). `cause` is a discriminator mapped via `quality.cause.*`, not sentence content. `/normalize/plan` has no current React consumer; future UI/external client must use the view descriptor, not infer a translated backend `message`. Test DTO preservation and view formatting independently. Fix message/conflict path params stay verbatim.

**Apply error contract:** `quality.py:371` is an owned string in `results[].error`, not a conflict message. Freeze `results[].error?: RenderableMessage` for this known `diagnostics.quality.write_tags_failed`; `quality.py:376,398` keep unknown `str(exc)` as legacy strings. `results[].conflicts[].message` from plan conflicts or `quality.py:388` is a separate `RenderableMessage`; counters `results[].errors` and top-level `errors` remain numbers. `apply_quality_plan` returns dict directly from `routes.py:1695`, so both plan and apply must preserve descriptor objects. `quality.py:195` and `health.py:310` use `Неизвестный исполнитель` as persisted path components, not translatable diagnostics. Sorting by prose (`quality.py:131`) must change to stable IDs/data before storing descriptors. `QualityScreen.tsx:474` Russian regex removes missing-tag prefix; use code/field-aware rendering, not translated prose regex. Python Rich CLI `render_health`/`render_lint` currently print `issue.message`: Task 8 must use readable fallback when these issue objects become descriptors, even if CLI language remains out of scope. Tests `tests/test_health.py`, `test_lint.py`, `test_normalize.py`, `test_quality.py`, `test_quality_plan.py`, `test_quality_api.py`, `frontend/tests/qualityScreen.test.tsx`, `diff.test.ts`.

## Frontend catalog ownership and key families

### CURRENT catalog/diagnostic validation state (OPEN)

The proposed Markdown entries are **not** a machine-verified EN/RU catalog: baseline/continuation tables include multiple keys per cell, prose placeholders such as “see baseline”, and conflicting source spellings. No recursive extraction/parity or ICU syntax/category check has been completed for every proposed row. In particular `quality.apply.summary` and `quality.lyrics.summary` still have conditional localized fragments rather than a single approved ICU message; `ytm.artist.subscribers` receives potentially nonnumeric provider text; `ytm.album.card_aria` uses a precomposed suffix; `lib/format.ts:638` still offers formatter alternatives. These are explicit unresolved contract defects, not reviewed translations. **Do not mark key/ICU parity as verified.** The catalogs do not exist yet.

For diagnostic field labels use the single mapping at the diagnostic field contract below: wire `params.field` is a stable ID, frontend supplies `fieldLabel` from `editor.fields.*` at render; for unknown IDs render raw ID, never an opaque translation key. For normalization changes, the wire remains raw `{field,path,old,new,cause}` and only the *view* builds `diagnostics.quality.change` from the raw values. `quality.py` English fallback must derive its own English field label; when an ID is unknown use raw ID, not a Russian hardcoded tuple. This rule is definitive, though the source-to-row/ICU audit remains open.

Concrete baseline keys below have EN/RU source and params. These are **representative, not an assertion that the frontend has only these strings**. For each listed file, implementation owner must add one key per distinct app-owned visible phrase (including conditional alternatives, aria/title/alt/placeholder, status/toast/dialog/progress/pipeline labels) and record the final key in both catalogs before closing Tasks 4/5/9. All frontend rows travel directly from TSX/TS through React or toast/ops/dialog state into DOM; non-component stores must store keys/descriptors until display, not rendered strings. Use `{count, plural, ...}` rather than `трек(ов)` or English singular/plural manually. If same semantic phrase occurs twice, reuse a shared `common.*` key; if context differs, use separate keys.

| Key | EN | RU | Params | Producer → consumer |
|---|---|---|---|---|
| nav.home | Home | Главная | — | nav.ts → Topbar, Tabbar, CommandPalette, KeymapDialog |
| common.errors.unavailable | Something went wrong | Что-то пошло не так | — | lib/i18n/messages.ts fallback → any UI boundary |
| nav.library | Library | Библиотека | — | same |
| nav.search | Search | Поиск | — | same |
| nav.recommendations | Recommendations | Рекомендации | — | same |
| nav.issues | Issues | Проблемы | — | same |
| nav.settings | Settings | Настройки | — | same |
| shell.more | More | Ещё | — | Tabbar / MoreMenu |
| shell.command.search | Search commands… | Поиск команды… | — | CommandPalette |
| shell.command.empty | No commands found | Ничего не найдено | — | CommandPalette |
| shell.theme.switch | Toggle theme | Переключить тему | — | Topbar / CommandPalette |
| dialogs.confirm.title | Confirmation | Подтверждение | — | DialogProvider |
| dialogs.prompt.title | Input | Ввод | — | DialogProvider |
| dialogs.yes | Yes | Да | — | DialogProvider and callers |
| dialogs.cancel | Cancel | Отмена | — | DialogProvider and callers |
| dialogs.close_aria | Close dialog | Закрыть диалог | — | DialogProvider |
| jobs.dock.launching | Starting… | Запуск... | — | downloads.ts → DownloadsDock |
| jobs.dock.empty | No active jobs | Нет активных задач | — | DownloadsDock |
| jobs.dock.active | Downloads · {count} · {percent}% | Загрузки · {count} · {percent}% | count,percent | DownloadsDock |
| jobs.dock.failed | Downloads · error ({count}) | Загрузки · ошибка ({count}) | count | DownloadsDock |
| jobs.dock.clear | Clear | Очистить | — | DownloadsDock |
| settings.language.label | Language | Язык | — | SettingsScreen (new selector) |
| settings.language.save_failed | Language changed, but could not be saved | Язык изменён, но сохранить выбор не удалось | — | SettingsScreen → toast |
| editor.fields.title | Title | Название | — | lib/tags.ts / editor / library / diagnostics field-label rendering |
| editor.fields.artist | Artist | Исполнитель | — | same |
| editor.fields.album | Album | Альбом | — | same |
| editor.fields.year | Year | Год | — | same |
| editor.fields.genre | Genre | Жанр | — | same |
| editor.fields.album_artist | Album artist | Исполнитель альбома | — | same |
| editor.fields.cover | Cover art | Обложка | — | diagnostics.health missing / editor |
| editor.fields.track_number | Track number | № трека | — | diagnostics.lint whitespace / editor |
| editor.fields.disc_number | Disc number | № диска | — | diagnostics.lint whitespace / editor |
| editor.fields.isrc | ISRC | ISRC | — | lib/tags.ts → editor / diagnostic field resolver |
| editor.fields.composer | Composer | Композитор | — | lib/tags.ts → editor / diagnostic field resolver |
| editor.fields.publisher | Publisher / Label | Издатель / Лейбл | — | lib/tags.ts → editor / diagnostic field resolver |
| editor.fields.comment | Comment | Комментарий | — | lib/tags.ts → editor / diagnostic field resolver |
| editor.validation.year_four_digits | Year: 4 digits, e.g. 2024 | Год: 4 цифры, например 2024 | — | lib/tags.ts → TrackEditor |
| editor.validation.integer | Integer | Целое число | — | lib/tags.ts → TrackEditor |
| quality.title | Library issues | Проблемы библиотеки | — | QualityScreen |
| quality.empty | No issues found | Проблем не найдено | — | QualityScreen |
| quality.category.missing | Missing tags | Незаполненные теги | — | QualityScreen CAT_LABELS_RU |
| quality.category.unreadable | Unreadable files | Нечитаемые файлы | — | QualityScreen CAT_LABELS_RU |
| quality.category.duplicates | Duplicates | Дубликаты | — | QualityScreen CAT_LABELS_RU |
| quality.category.whitespace | Extra spaces | Лишние пробелы | — | QualityScreen CAT_LABELS_RU |
| quality.category.case | Capitalization | Регистр | — | QualityScreen CAT_LABELS_RU |
| quality.category.feat | Featured artists | Feat-исполнители | — | QualityScreen CAT_LABELS_RU |
| quality.category.tracknum | Track numbers | Номера треков | — | QualityScreen CAT_LABELS_RU |
| quality.category.album_artist | Album artist | Исполнитель альбома | — | QualityScreen CAT_LABELS_RU |
| quality.category.genre | Genre | Жанр | — | QualityScreen CAT_LABELS_RU |
| quality.category.year | Year | Год | — | QualityScreen CAT_LABELS_RU |
| quality.category.mismatch | Filename ≠ tag | Имя файла ≠ тег | — | QualityScreen CAT_LABELS_RU |
| quality.category.loose | Files outside folders | Файлы вне папок | — | QualityScreen CAT_LABELS_RU |
| quality.cause.track_number | Track numbers | Номера треков | — | QualityScreen CAUSE_LABELS_RU |
| quality.cause.disc_number | Disc numbers | Номера дисков | — | QualityScreen CAUSE_LABELS_RU |
| quality.cause.global_genre | Common genres | Общие жанры | — | QualityScreen CAUSE_LABELS_RU |
| quality.plan.confirm | Apply changes? | Применить изменения? | — | QualityScreen.confirmPlanDialog |
| quality.plan.conflicts | Conflicts — {count} | Конфликты — {count} | count | QualityScreen.confirmPlanDialog |
| quality.plan.apply | Apply ({count}) | Применить ({count}) | count | QualityScreen.confirmPlanDialog |
| search.query.placeholder | YouTube query or URL (video / playlist / audio) | Запрос на YouTube или URL (видео / плейлист / аудио) | — | SearchScreen |
| library.empty | Library is empty | Библиотека пуста | — | TracksTab, ArtistsTab, AlbumsTab |
| shazam.unconfigured | Shazam file is not configured | Файл Shazam не настроен | — | MiscScreen |
| recommend.disconnected | YouTube Music is not connected | YouTube Music не подключён | — | RecommendScreen |

### Verified shell/shared frontend phrase ledger (partial)

Locations relative to `frontend/src/`. Transport: React DOM unless stated otherwise. EN/RU are proposed catalog values; code has not been migrated. Every conditional branch has its own row. Other batches below remain blocking.

| Producer location | Key | EN | RU | ICU params | Consumer |
|---|---|---|---|---|---|
| `App.tsx:58–60` | shell.skip | Skip to content | Перейти к содержимому | — | skip link |
| `nav.ts:11–24` | `nav.home/library/search/recommendations/issues/settings` | see baseline table | see baseline table | — | Topbar, Tabbar, MoreMenu, CommandPalette |
| `components/Topbar.tsx:54` | shell.stats.health_title | Library health (tracks without issues) | Здоровье библиотеки (треки без проблем) | — | health title |
| `components/Topbar.tsx:60` | shell.stats.tracks | {count, plural, one {# track} other {# tracks}} · {size} | {count, plural, one {# трек} few {# трека} many {# треков} other {# трека}} · {size} | count,size | sidebar statistics |
| `components/Topbar.tsx:74` | shell.nav.main_aria | Main navigation | Основная навигация | — | nav aria |
| `components/Topbar.tsx:94,96` | shell.theme.switch | Toggle theme | Переключить тему | — | title, aria |
| `components/Topbar.tsx:100` | shell.theme.light | light | светлая | — | theme state |
| `components/Topbar.tsx:100` | shell.theme.dark | dark | тёмная | — | theme state |
| `components/Tabbar.tsx:18` | shell.nav.mobile_aria | Mobile navigation | Мобильная навигация | — | nav aria |
| `components/Tabbar.tsx:39,50` | shell.more | More | Ещё | — | tab aria + text |
| `components/MoreMenu.tsx:23` | shell.nav.more_aria | Additional navigation | Дополнительная навигация | — | menu aria |
| `components/CommandPalette.tsx:25` | shell.command.label | Command palette | Палитра команд | — | dialog label |
| `components/CommandPalette.tsx:30–32` | shell.command.search / shell.command.empty | see baseline table | see baseline table | — | placeholder / empty |
| `components/CommandPalette.tsx:33` | shell.command.navigate | Navigate | Переход | — | group heading |
| `components/CommandPalette.tsx:47` | shell.command.actions | Actions | Действия | — | group heading |
| `components/CommandPalette.tsx:49` | shell.theme.switch | see baseline table | see baseline table | — | command item |
| `components/CommandPalette.tsx:59`, `components/dialogs/KeymapDialog.tsx:71–72` | dialogs.keymap.title | Keyboard shortcuts | Горячие клавиши | — | command item / dialog heading + aria |
| `components/dialogs/KeymapDialog.tsx:8` | dialogs.keymap.command | Command palette | Палитра команд | — | keyboard row |
| `components/dialogs/KeymapDialog.tsx:9` | dialogs.keymap.navigation | Home / Library / Search / Recommendations / Issues / Settings | Главная / Библиотека / Поиск / Рекомендации / Проблемы / Настройки | — | keyboard row |
| `components/dialogs/KeymapDialog.tsx:10` | dialogs.keymap.theme | Dark / light theme | Тёмная / светлая тема | — | keyboard row |
| `components/dialogs/KeymapDialog.tsx:11` | dialogs.keymap.this_list | This list | Этот список | — | keyboard row |
| `components/dialogs/KeymapDialog.tsx:12` | dialogs.keymap.dismiss | Close dialog / list | Закрыть диалог / список | — | keyboard row |
| `components/dialogs/KeymapDialog.tsx:13` | dialogs.keymap.enter | Search / select | Поиск / выбрать | — | keyboard row |
| `components/dialogs/KeymapDialog.tsx:14` | dialogs.keymap.next_track | Next / previous track in list | Следующий / предыдущий трек в списке | — | keyboard row |
| `components/dialogs/KeymapDialog.tsx:86–87` | dialogs.close | Close | Закрыть | — | button |
| `components/dialogs/DialogProvider.tsx:132–181` | dialogs.confirm.title / dialogs.prompt.title / dialogs.yes / dialogs.cancel | see baseline table | see baseline table | — | dialog defaults |
| `components/dialogs/DialogProvider.tsx:153,163,174` | dialogs.ok | OK | ОК | — | dialog default action |
| `components/dialogs/DialogProvider.tsx:230` | dialogs.close_aria | see baseline table | see baseline table | — | close aria |
| `components/ui/Spinner.tsx:2` | common.loading | Loading… | Загрузка… | — | spinner default |

`components/dialogs/DialogProvider.tsx:64,73` exceptions are technical invariant errors, not UI copy; caller-supplied `message`, `title`, `label`, `sub`, `hint`, `okTitle` are **not automatically data**: inventory each caller separately. `KeymapDialog` key glyphs are physical shortcut data. `Tabbar` SVG path attributes and `App` route/import IDs are technical. `frontend/index.html:6` title `music-lib` is a product name, not prose; `lang="ru"` is language metadata to be set from active locale; inline theme script has no visible copy.

### Mandatory frontend file/source inventory (remaining phrase enumeration)

`SOURCE_PHRASE_PENDING` here is a **blocking catalog task**, not a translation or a real catalog key. Use owner namespace, `en = translate precise Russian phrase at source into natural English`, `ru = original phrase reviewed for grammar`, ICU params = all runtime interpolations (data/numbers). Producer = named file; consumer = DOM/toast/dialog/job state as indicated. File coverage is organized by existing plan batches; match **every** visible occurrence, including English strings, ASCII-only `OK`, numbers with noun labels and fallback text, rather than scanning Cyrillic alone.

| Batch / owner key prefix | Source files; required phrase classes / consumer |
|---|---|
| `shell.*`, `nav.*`, `dialogs.*`, `common.*` | `App.tsx`, `nav.ts`, `components/{Topbar,Tabbar,MoreMenu,CommandPalette}.tsx`, `components/dialogs/{KeymapDialog,DialogProvider}.tsx`; nav and menu labels, counts/theme modes, command input and empty/group items, hotkey descriptions, modal defaults/buttons/aria; use key references in nav, resolve at render. `components/ui/{EmptyState,StatusLine,Pipeline,ProgressBar,QueueItem,TrackRow,CollapsibleGroup,SegControl,Table,Cover}.tsx`: default fallback copy if any, or caller-owned labels. `index.html` page title also inspect. |
| `jobs.dock.*`, `player.*` | `stores/downloads.ts`, `lib/jobs.ts`, `lib/ops.tsx`, `lib/toast.tsx`, `components/{DownloadsDock,PlayerBar,AudioPlayer,PreviewButton}.tsx`; endpoint `TITLES`, launch/done/error/history, dock status/aria, playback controls/title fallback, toasts/progress stages. Distinguish dynamic track title/artist from owned verbs. |
| `library.*` | `views/LibraryScreen.tsx`, `views/library/{AlbumsTab,ArtistsTab,TracksTab,PlaylistsTab,Inbox,Cards,albumDetail,trackDetail,LibrarySkeleton}.tsx`, `views/library/{libUtils,useYtData}.ts`; tabs, sort options, counts, selection and hover/aria, Inbox actions, playlist controls, plan/move/delete dialogs, empty/error/toasts, cover chooser, common field labels, album details, loading/skeleton text, compress result label; metadata, paths and provider titles are not keys. |
| `discover.*`, `search.*`, `shazam.*`, `recommend.*` | `views/{DiscoverScreen,SearchScreen,MiscScreen,RecommendScreen,MenuScreen,MenuSkeleton}.tsx`; tab headers, input placeholders, results and empty/error states, prompts/toasts, download stage names and counters, recommendation seed progress, card actions and aria; `lib/ops.tsx` stores descriptors. |
| `ytm.*` | `features/ytm/{badges,cards,detail,rows,download,settings}.tsx`; connected/liked/clip/status labels, playlist/artist/album UI, download prompts/alerts, rating/status, card button aria and title. Never translate provider-owned names (`YouTube Music`, `Discogs`, etc.) or songs. |
| `settings.*` | `views/{SettingsScreen,settings/parts,settings/YtmCard,settings/SettingsSkeleton}.tsx`; sections, hints, options, path browser fallback, OAuth flow/device/auth labels, cookies, validation and alerts. Native selector choices exactly `English` and `Русский`; these autonyms are not translated. |
| `editor.*` | `lib/tags.ts`, `features/editor/{TrackEditor,TrackEditorDialog,BatchEditorDialog,runMetaflow,useMetaSources}.tsx`; TAG_FIELDS group/field labels, validation messages, save/error/cover/status, source choice, batch counters and progress, field aria, batch done toast; provider records stay verbatim. |
| `quality.*` | `views/{QualityScreen,QualitySkeleton}.tsx`; all `CAT_LABELS_RU` + `CAUSE_LABELS_RU` variants, dialog headings/table headers/toolbar, issue count/chips, regex special case at :474, action/empty/error/toasts, diff counts, changes. `lib/diff.ts[x]` display labels only (diff tokens are data). |
| `common.format.*` | `lib/format.ts` and date/count/number calls in views; inspect hardcoded date locale and `localeCompare` in `views/library/libUtils.ts`; use `Intl` active locale (not catalog for numeric data). |

### Standalone missing-build page (`src/web/server.py:20–50,77–79`)

This is app-owned UI served at `/` with 503 when `dist` is absent. Task 6 owns negotiation: parse `Accept-Language` by descending q-values, support `ru`/`ru-*` and `en`/`en-*`, skip unsupported and `q=0`, choose English when no supported match; select matching standalone HTML with `<html lang>` and `Content-Language`, preserve 503. Do not load SPA settings/i18next. Keep commands and product names literal. An English browser must not receive only Russian copy. Translation data (backend-owned standalone template, **not** frontend catalog interpolation):

| Key | RU (`server.py` source) | EN | Params | Consumer |
|---|---|---|---|---|
| shell.build_hint.title | music-lib — фронтенд не собран | music-lib — frontend not built | — | HTML `<title>` |
| shell.build_hint.heading | Фронтенд не собран | Frontend not built | — | HTML `<h1>` |
| shell.build_hint.launcher | API работает, но интерфейс ещё не собран. Запустите лаунчер — он соберёт UI автоматически: | The API works, but the interface has not been built. Run the launcher to build it automatically: | — | HTML first paragraph |
| shell.build_hint.manual | Или вручную: … . Для разработки — … (Vite, обновление на лету). | Or build it manually: … . For development, run … (Vite, live reload). | — | HTML second paragraph; `cd frontend && npm install && npm run build` and `python scripts/dev.py` remain literal in `<code>` |

The `python scripts/run.py` command is literal data, not a key. `server.py:122–135` terminal prints are user-visible **CLI** and, by PM decision recorded in the active addendum, remain outside the approved web localization boundary. `tests/test_web_api.py` existing Russian 503 expectation must become explicit `Accept-Language: ru` and gain English/default assertions.

### Follow-up: line-level inventory for inspected nested modules (not full closure)

The rows below are additional migration specifications. Locations are relative to `frontend/src`; render owner includes intermediate state when applicable. `—` in params means no ICU parameter. An occurrence range only groups identical call-site branches; it is not a blanket exemption for other literals in the range. Existing baseline keys above take precedence. Preserve descriptors/data until render, especially across locale switches. This follow-up does **not** mark the remaining `P` files closed.

| Source occurrence | Stable key | EN source | RU | ICU params | Render owner |
|---|---|---|---|---|---|
| `views/QualityScreen.tsx:108` | quality.table.field | Field | Поле | — | ChangeTable header |
| `views/QualityScreen.tsx:108,141,158` | quality.table.file | File | Файл | — | plan tables |
| `views/QualityScreen.tsx:108` | quality.table.before | Before | Было | — | ChangeTable header |
| `views/QualityScreen.tsx:108` | quality.table.after | After | Станет | — | ChangeTable header |
| `views/QualityScreen.tsx:134` | quality.plan.tag_changes | Tag changes — {count} | Изменения тегов — {count} | count | confirmPlanDialog heading |
| `views/QualityScreen.tsx:140` | quality.plan.files | Files — {count} | Файлы — {count} | count | confirmPlanDialog heading |
| `views/QualityScreen.tsx:141` | quality.table.action | Action | Действие | — | file plan header |
| `views/QualityScreen.tsx:141` | quality.table.destination | Destination | Куда | — | file plan header |
| `views/QualityScreen.tsx:144` | quality.action.move | Move | Перенос | — | file plan cell |
| `views/QualityScreen.tsx:144` | quality.action.rename | Rename | Переименовать | — | file plan cell |
| `views/QualityScreen.tsx:156` | quality.plan.conflicts | Conflicts — {count} | Конфликты — {count} | count | confirmPlanDialog heading; baseline |
| `views/QualityScreen.tsx:157` | quality.plan.conflicts_skip | These items will be skipped; the remaining changes will be applied | Эти элементы будут пропущены, остальные изменения применятся | — | dialog note |
| `views/QualityScreen.tsx:158` | quality.table.obstacle | Obstacle | Препятствие | — | conflicts header |
| `views/QualityScreen.tsx:171` | quality.plan.apply | Apply ({count}) | Применить ({count}) | count | dialog action; baseline |
| `views/QualityScreen.tsx:172` | dialogs.cancel | Cancel | Отмена | — | dialog action; baseline |
| `views/QualityScreen.tsx:250` | editor.saved | Tags saved | Теги сохранены | — | toast |
| `views/QualityScreen.tsx:258` | quality.lyrics.updated | Lyrics updated | Текст обновлён | — | toast success |
| `views/QualityScreen.tsx:258` | quality.lyrics.not_found | Lyrics not found | Текст не найден | — | toast warning |
| `views/QualityScreen.tsx:269,307,326` | quality.selection.required | Select tracks using the checkboxes on the cards | Отметьте треки флажками на карточках | — | toast warning (three callers) |
| `views/QualityScreen.tsx:281` | quality.plan.no_changes | No automatic changes for the selected tracks | Для выбранных треков нет автоматических изменений | — | toast warning |
| `views/QualityScreen.tsx:292` | quality.apply.conflicts_suffix | , conflicts: {count} | , конфликтов: {count} | count | conditional toast suffix (prefer composing full optional count variants without locale-fixed comma order) |
| `views/QualityScreen.tsx:293` | quality.apply.errors_suffix | , errors: {count} | , ошибок: {count} | count | conditional toast suffix |
| `views/QualityScreen.tsx:295` | quality.apply.summary | Applied: {applied}, skipped: {skipped}{conflicts}{errors} | Применено: {applied}, пропущено: {skipped}{conflicts}{errors} | applied,skipped,conflicts,errors (suffixes are owned localized fragments; alternatively ICU select for presence) | toast |
| `views/QualityScreen.tsx:317` | quality.selection.saved | Saved {count, plural, one {# track} other {# tracks}} | Сохранено {count, plural, one {# трек} few {# трека} many {# треков} other {# трека}} | count | toast |
| `views/QualityScreen.tsx:329` | quality.lyrics.confirm | Update lyrics for {count, plural, one {# track} other {# tracks}}? | Обновить тексты для {count, plural, one {# трека} few {# треков} many {# треков} other {# трека}}? | count | confirm dialog |
| `views/QualityScreen.tsx:329` | quality.lyrics.update_action | Update | Обновить | — | lyrics confirmation action |
| `views/QualityScreen.tsx:382` | quality.refresh | Refresh | Обновить | — | report refresh button |
| `views/QualityScreen.tsx:349` | quality.lyrics.item_progress | [{index}/{total}] {filename} | [{index}/{total}] {filename} | index,total,filename (filename verbatim) | operation panel |
| `views/QualityScreen.tsx:354` | quality.lyrics.summary | Updated: {updated}, not found: {missed}{errors} | Обновлено: {updated}, не найдено: {missed}{errors} | updated,missed,errors (conditional localized suffix as above) | operation panel |
| `views/QualityScreen.tsx:355` | quality.refreshing | Refreshing list… | Обновление списка… | — | operation panel |
| `views/QualityScreen.tsx:368` | quality.title | Library issues | Проблемы библиотеки | — | heading; baseline |
| `views/QualityScreen.tsx:369` | quality.subtitle | Combined report: files, tags and suggested fixes | Единый отчёт: файлы, теги и предлагаемые исправления | — | subtitle |
| `views/QualityScreen.tsx:380` | quality.include_inbox | Include Inbox | Включая Inbox | — | checkbox label |
| `views/QualityScreen.tsx:385` | quality.selection.toolbar | Selected track actions | Действия с выбранными треками | — | toolbar aria |
| `views/QualityScreen.tsx:386` | quality.selection.count | Selected: {count} | Выбрано: {count} | count | toolbar count |
| `views/QualityScreen.tsx:387,484` | quality.editor | Editor | Редактор | — | buttons |
| `views/QualityScreen.tsx:388` | quality.normalize | Normalize | Нормализовать | — | button |
| `views/QualityScreen.tsx:389` | quality.lyrics | Lyrics | Тексты | — | button |
| `views/QualityScreen.tsx:390` | quality.selection.clear | Clear selection | Сбросить | — | button |
| `views/QualityScreen.tsx:402` | quality.summary.checked | Tracks checked: {count} | Проверено треков: {count} | count | report header |
| `views/QualityScreen.tsx:403` | quality.summary.issues | Issues: {count} | Проблем: {count} | count | report tag |
| `views/QualityScreen.tsx:404` | quality.summary.auto_fixes | Automatic fixes: {count} | Автоисправления: {count} | count | report tag |
| `views/QualityScreen.tsx:407` | quality.empty | No issues found | Проблем не найдено | — | empty panel; baseline |
| `views/QualityScreen.tsx:418` | quality.category.show_aria | Show category: {category} | Показать категорию: {category} | category (localized categoryLabel) | filter aria |
| `views/QualityScreen.tsx:418` | quality.category.hide_aria | Hide category: {category} | Скрыть категорию: {category} | category (localized categoryLabel) | filter aria |
| `views/QualityScreen.tsx:421` | quality.category.count | {category} ({count}) | {category} ({count}) | category,count | filter button |
| `views/QualityScreen.tsx:426` | quality.category.show_all | Show all | Показать все | — | button |
| `views/QualityScreen.tsx:445` | quality.selection.deselect_all | Deselect all ({count}) | Снять выделение ({count}) | count | button |
| `views/QualityScreen.tsx:445` | quality.selection.select_all | Select all ({count}) | Выбрать все ({count}) | count | button |
| `views/QualityScreen.tsx:458` | quality.selection.track_aria | Select: {name} | Выбрать: {name} | name (metadata/path verbatim) | checkbox aria |
| `views/QualityScreen.tsx:474` | editor.fields.* | field label (see baseline) | название поля (см. базовые ключи) | field ID lookup, not a string param | missing-tag chip only; replace Russian regex with code/field-aware branch; all other issue messages use resolveMessage |
| `views/QualityScreen.tsx:478` | quality.auto_fix.tooltip | Number of changes suggested by automatic fixes | Столько изменений предложит автоисправление | — | title |
| `views/QualityScreen.tsx:479` | quality.auto_fix.count | Automatic fixes: {count} | Автоисправления: {count} | count | chip (may reuse quality.summary.auto_fixes if same wording) |
| `views/QualityScreen.tsx:486` | quality.fix | Fix | Исправить | — | button |
| `views/QualityScreen.tsx:489` | quality.lyrics.singular | Lyrics | Текст | — | button (different source phrase from :389) |
| `views/QualityScreen.tsx:498` | quality.selection.no_matching | No tracks in the selected categories | Нет треков с выбранными категориями | — | empty panel |
| `views/QualityScreen.tsx:501` | quality.plan.title_count | Normalization plan — {count} | План нормализации — {count} | count | collapsible title |

Quality exclusions, with evidence: `:26–27` unknown category/cause key is a raw ID fallback, not catalog copy; `:84–87,110–116` quote/arrows and `old/new` are punctuation and tag data; `:91–103` `Inbox` is a folder token; `:111` `c.field` is a stable ID and MUST use `resolveFieldLabel`, not be treated as provider prose; `:162` conflict `message` is backend RenderableMessage, `kind` is a raw discriminator (use localized conflict message where known, do not catalog arbitrary kinds); `:197,261,277,300,398` error strings are legacy/API descriptors to resolve at render, not new literal keys; `:312,349,450,464–468` paths, filename, titles, artist and album are data; `:474` regex is Russian-specific control logic, not a phrase to translate. `:14–24` category/cause dictionaries already have baseline keys; `cause.album_artist` shares `quality.category.album_artist`. Conditional suffixes :292–295/:354 require translator-controlled composition rather than blindly concatenating English-ordered prose.

| Source occurrence | Stable key | EN source | RU | ICU params | Render owner |
|---|---|---|---|---|---|
| `features/ytm/detail.tsx:26` | ytm.back | ← Back | ← Назад | — | BackButton |
| `features/ytm/detail.tsx:82,155,333,391` | ytm.loading.album / ytm.loading.artist / ytm.loading.playlist / common.loading | Loading album… / Loading artist… / Loading playlist… / Loading… | Загрузка альбома… / Загрузка исполнителя… / Загрузка плейлиста… / Загрузка… | — | detail / radio panels; four distinct branches |
| `features/ytm/detail.tsx:83,157,337` | ytm.fallback.album / ytm.fallback.artist / ytm.fallback.playlist | Album / Artist / Playlist | Альбом / Исполнитель / Плейлист | — | missing metadata title fallback |
| `features/ytm/detail.tsx:91,339`, `features/ytm/cards.tsx:129` | ytm.tracks.count | {count, plural, one {# track} other {# tracks}} | {count, plural, one {# трек} few {# трека} many {# треков} other {# трека}} | count | metadata counts |
| `features/ytm/detail.tsx:99,101` | ytm.download.album_group | Album: {name} | Альбом: {name} | name (music title) | job/playlist name passed to download callbacks; retain descriptor until render if name displayed |
| `features/ytm/detail.tsx:162` | ytm.artist.subscribers | {count} {count, plural, one {subscriber} other {subscribers}} | {count} {count, plural, one {подписчик} few {подписчика} many {подписчиков} other {подписчика}} | count (provider string may be abbreviated; if not numeric use raw provider count and localized unit without ICU plural) | artist metadata |
| `features/ytm/detail.tsx:162`, `features/ytm/cards.tsx:86` | ytm.artist.local_count | {count} in library | {count} в библиотеке | count | artist metadata/badge |
| `features/ytm/detail.tsx:173`, `features/ytm/cards.tsx:80` | ytm.artist.photo_alt | Photo: {name} | Фото: {name} | name (provider metadata) | image alt |
| `features/ytm/detail.tsx:186` | ytm.download.popular | Download popular | Скачать популярные | — | downloadAllLabel prefix (do not pass localized prefix as fixed state) |
| `features/ytm/detail.tsx:195,220,305,308,309` | ytm.artist.albums / ytm.artist.popular_songs / ytm.artist.top_tracks / ytm.artist.searching_popular / ytm.artist.no_results | Albums / Popular songs / Top tracks / Searching for popular tracks… / Nothing found | Альбомы / Популярные песни / Топ треков / Ищем популярное… / Ничего не нашлось | — | section headings/loading/empty; distinct branches |
| `features/ytm/detail.tsx:246–247,279,287,399,403` | ytm.download.youtube_group / ytm.download.radio_group | YouTube: {artist} / Radio: {title} | YouTube: {artist} / Радио: {title} | artist,title (metadata verbatim) | download group names; :287 search query `музыка` is NOT UI copy: literal query-language suffix sent to API; do not localize without search semantics decision |
| `features/ytm/detail.tsx:380,383,393` | ytm.radio.similar / dialogs.close / ytm.radio.empty | Similar: / Close / No similar tracks found | Похожие: / Закрыть / Похожих треков не нашлось | — | radio heading / close aria / empty |
| `features/ytm/cards.tsx:33` | ytm.album.card_aria | Album: {title}{artistSuffix} | Альбом: {title}{artistSuffix} | title,artistSuffix (artist delimiter composition; prefer separate optional artist ICU select) | card aria |
| `features/ytm/cards.tsx:39` | ytm.album.cover_alt | Album cover: {title} | Обложка альбома: {title} | title | img alt |
| `features/ytm/cards.tsx:74` | ytm.artist.card_aria | Artist: {name} | Исполнитель: {name} | name | card aria |
| `features/ytm/cards.tsx:85,89` | ytm.artist.local_title / ytm.artist.subscription_title | Files in the local library / YouTube Music subscription | Файлы в локальной библиотеке / Подписка на YouTube Music | — | badge titles |
| `features/ytm/cards.tsx:86,89` | ytm.artist.subscribed | Subscribed | Подписан | — | badge / appended status (separate phrase from local count) |
| `features/ytm/cards.tsx:94` | ytm.artist.subscribers_short | {count} subscribers | {count} подписч. | count (provider-formatted string, do not infer plural from non-numeric string) | card sub |
| `features/ytm/cards.tsx:114` | ytm.cover_alt | Cover: {title} | Обложка: {title} | title | playlist image alt; reuse for rows:90 |
| `features/ytm/cards.tsx:120` | ytm.fallback.playlist | Playlist | Плейлист | — | missing title |
| `features/ytm/rows.tsx:18,19` | ytm.download.title / ytm.download.track_aria | Download / Download: {title} | Скачать / Скачать: {title} | — / title | button title/aria |
| `features/ytm/rows.tsx:32,33,36` | ytm.radio.title / ytm.radio.track_aria / ytm.radio.button | Similar (radio) / Similar: {title} / Radio | Похожие (радио) / Похожие: {title} / Радио | — / title / — | button title/aria/body |
| `features/ytm/rows.tsx:80` | ytm.empty | Empty | Пусто | — | empty track list |
| `features/ytm/rows.tsx:90,102,106` | ytm.cover_alt / editor.fields.track_number / ytm.track.source_title | Cover: {title} / Track number / Source | Обложка: {title} / Номер трека / Источник | title / — / — | image alt / tooltips; `YT` at :106 is provider abbreviation data |
| `features/ytm/badges.tsx:11,12` | ytm.badge.in_library_title / ytm.badge.in_library_aria | Track is already in the local library / In library | Трек уже в локальной библиотеке / В библиотеке | — | title / aria |
| `features/ytm/badges.tsx:20–22` | ytm.badge.clip_title / ytm.badge.clip | This is a video clip, not an audio version / Video clip | Это клип, а не аудиоверсия / Клип | — | title / badge |
| `features/ytm/badges.tsx:32,40,47,61–63` | ytm.badge.album_full / ytm.badge.album_partial / ytm.badge.album_absent / ytm.badge.none | Album is in the local library / Album is partially saved; some tracks are on YouTube Music / Not in the local library / None | Альбом в локальной библиотеке / Альбом сохранён частично — часть треков есть на YouTube Music / В локальной библиотеке нет / Нет | — | count-badge tooltip variants / empty badge; `● ◐ ○` and fraction are numeric/symbol data |
| `features/ytm/badges.tsx:52` | ytm.tracks.short_count | {count} tracks | {count} тр. | count | count badge without total |
| `features/ytm/download.ts:25` | ytm.download.archive / ytm.download.complete | Archive: {filename} / Downloaded: {count} | Архив: {filename} / Скачано: {count} | filename (path basename),count | toast alternatives |
| `features/ytm/download.ts:33–34` | ytm.download.missing_count / ytm.download.all_present | Download missing ({count}) / Everything is already in the library | Скачать отсутствующие ({count}) / Всё уже в библиотеке | count / — | downloadAllLabel button alternatives; caller :186 uses a distinct prefix `ytm.download.popular`, so use separate `ytm.download.popular_count` = `Download popular ({count})` / `Скачать популярные ({count})`, never interpolate a localized prefix |

**Clarification on multi-key cells:** slash-separated key/EN/RU alternatives above are editorial shorthand for *separate catalog messages*, not one key with slashes. For instance `ytm.loading.album`, `ytm.loading.artist`, `ytm.loading.playlist`, `common.loading` are four independent keys at :82, :155, :333 and :391 respectively. `ytm.download.popular_count` belongs to the `detail.tsx:186` → `downloadAllLabel` branch with `{count}`. `quality.selection.saved` and `quality.lyrics.confirm` must use ICU plural rather than `трек(ов)`.

YTM exclusions: `features/ytm/{types,index,settings}.ts` contain only DTO types/re-exports/config IDs/API path/default audio format; no user prose. `badges.tsx:4–5` SVG markup is visual data; `cards.tsx:46,93`, `detail.tsx:89,157,206,236–247,381,337,339`, `rows.tsx:54,63–65,84,86,96–103` music metadata, numeric track number, formatted duration, URI and fallback dash remain data. `detail.tsx:19,81,154,332,388` API/unknown error is rendered through descriptor resolver; not a new frontend literal key. `download.ts:28` likewise raw API/provider error. `detail.tsx:99,101,246–247,399,403` group names contain owned prefixes even though the interpolated album/artist/seed are data; if used as stored job titles, do not freeze the rendered prefix at request time. `cards.tsx:8` Enter and Space are keyboard key identifiers. `rows.tsx:9` MUSIC_VIDEO_TYPE_ATV is a wire discriminator. `download.ts:19–22` `m4a`, format/source defaults and booleans are settings data. These exclusions cover the stated locations, not every uninspected frontend file.

| Source occurrence | Stable key | EN source | RU | ICU params | Render owner |
|---|---|---|---|---|---|
| `views/settings/parts.tsx:66` | settings.browse.folder_title | Choose a folder | Выбор папки | — | fallback browse dialog |
| `views/settings/parts.tsx:68` | dialogs.close | Close | Закрыть | — | dialog action (shell ledger) |
| `views/settings/parts.tsx:93` | settings.browse.error | Error: {reason} | Ошибка: {reason} | reason (API/OS error verbatim) | browse error panel; resolve known API descriptor before composition |
| `views/settings/parts.tsx:94` | settings.browse.loading | Reading folders… | Читаю папки… | — | Spinner text |
| `views/settings/parts.tsx:98` | settings.browse.folder | Folder: | Папка: | — | path prefix (path itself raw) |
| `views/SettingsScreen.tsx:50` | settings.sources.drag_title | Drag to reorder | Перетащить | — | drag handle title |
| `views/SettingsScreen.tsx:135` | settings.shazam.migrated | Shazam: {count, plural, one {# line moved to the new file} other {# lines moved to the new file}} | Shazam: {count, plural, one {# строка перенесена в новый файл} few {# строки перенесены в новый файл} many {# строк перенесено в новый файл} other {# строки перенесены в новый файл}} | count | toast |
| `views/SettingsScreen.tsx:137` | settings.saved | Settings saved | Настройки сохранены | — | toast |
| `views/SettingsScreen.tsx:158` | settings.primuse.backfill_summary | Done: .lrc {lyrics}, covers {covers}, skipped {skipped} | Готово: .lrc {lyrics}, обложек {covers}, пропущено {skipped} | lyrics,covers,skipped | progress bar result |
| `views/SettingsScreen.tsx:160` | settings.primuse.backfill_done | Sidecar files created | Sidecar-файлы созданы | — | toast |
| `views/SettingsScreen.tsx:171` | settings.primuse.cleanup_confirm | Delete {lyrics} .lrc and {covers} -cover.jpg files (including Inbox)? Tags will not be changed. | Удалить {lyrics} .lrc и {covers} -cover.jpg (включая Inbox)? Теги не изменятся. | lyrics,covers | confirm dialog |
| `views/SettingsScreen.tsx:172` | settings.delete | Delete | Удалить | — | dialog action |
| `views/SettingsScreen.tsx:181` | settings.primuse.cleanup_summary | Deleted: .lrc {lyrics}, covers {covers} | Удалено: .lrc {lyrics}, обложек {covers} | lyrics,covers | progress bar |
| `views/SettingsScreen.tsx:182` | settings.primuse.cleanup_done | Library cleared of sidecar files | Библиотека очищена от sidecar-файлов | — | toast |
| `views/SettingsScreen.tsx:202,207` | nav.settings / settings.save | Settings / Save | Настройки / Сохранить | — | heading / button (two separate keys) |
| `views/SettingsScreen.tsx:203` | settings.subtitle | Library · formats · sources · YouTube Music · files · Primuse | Каталог · форматы · источники · YouTube Music · файлы · Primuse | — | subtitle |
| `views/SettingsScreen.tsx:213` | nav.library | Library | Библиотека | — | card title |
| `views/SettingsScreen.tsx:213` | settings.library.subtitle | Folder and audio formats | Папка и форматы аудио | — | card subtitle |
| `views/SettingsScreen.tsx:214,217,312` | settings.library.directory / settings.browse.action | Directory / Browse | Каталог / Обзор | — | Field label / two buttons (separate keys) |
| `views/SettingsScreen.tsx:221` | settings.format.source / settings.format.source_hint | Source format / Audio format received before conversion to the final format | Формат источника / Формат аудио, получаемый перед конвертацией в конечный формат | — | Field label / hint |
| `views/SettingsScreen.tsx:228` | settings.format.output / settings.format.output_hint | Output format / Format of audio files in the library | Конечный формат / Формат аудиофайла в библиотеке | — | Field label / hint |
| `views/SettingsScreen.tsx:235` | settings.format.quality | Quality, kbps | Качество, кбит/с | — | Field label |
| `views/SettingsScreen.tsx:245,248–250` | settings.names.language / settings.names.auto / settings.names.cyrillic / settings.names.latin | Filename script / Automatic / Cyrillic / Latin | Язык имён / Авто / Кириллица / Латиница | — | field + three selector options (four keys; IDs remain raw) |
| `views/SettingsScreen.tsx:257` | settings.names.hint | Transliteration for matched names in local Cyrillic and Latin YouTube Music metadata (for example, Валентин Стрыкало / Valentin Strykalo). Automatic keeps the original spelling. English-language names are unchanged. | Транслитерация для совпавших пар «локальная кириллица + латиница YT Music» (Валентин Стрыкало / Valentin Strykalo). Авто — как в оригинале. Англоязычные имена не меняются. | — | hint; example names are literal example data, not individual keys |
| `views/SettingsScreen.tsx:281,304` | settings.sources.title / settings.sources.subtitle / settings.sources.order_hint | Sources / Metadata search / Drag ⋮⋮ to set priority: earlier sources take precedence when tags are filled automatically | Источники / Поиск метаданных / Перетащите ⋮⋮, чтобы задать приоритет: первые источники выигрывают при автоподстановке тегов | — | card title / subtitle / hint (three keys) |
| `views/SettingsScreen.tsx:308–309` | settings.files.title / settings.files.shazam / settings.files.shazam_hint | Files / Shazam file / One “Title - Artist” entry per line | Файлы / Файл Shazam / «Название - Исполнитель» по строке | — | card / field / hint (three keys); `Shazam` :308 card subtitle is provider name |
| `views/SettingsScreen.tsx:317,319` | settings.primuse.subtitle / settings.primuse.save | .lrc and -cover.jpg next to each track / Save .lrc and -cover.jpg | .lrc и -cover.jpg рядом с треком / Сохранять .lrc и -cover.jpg | — | Primuse card subtitle / switch label (two keys); Primuse is provider/product name |
| `views/SettingsScreen.tsx:325,328` | settings.primuse.create_all / settings.primuse.delete_all | Create sidecars for the entire library / Delete .lrc and -cover.jpg | Создать sidecar всей библиотеке / Удалить .lrc и -cover.jpg | — | buttons (two keys) |

Settings exclusions: `SettingsScreen.tsx:53` metadata source ID shown raw (service/provider data); `:89–101,139,163,184,188` API errors require descriptor-aware rendering and unknown legacy strings stay verbatim; `:154,179` job progress `msg` from backend, not a new local literal; `:223–232` audio format choices come from server IDs, uppercase is presentation of data; `:216,311` user paths are data; `:206` decorative dirty-state dot is non-prose; `views/settings/parts.tsx:98,101–109` directory names/paths and `~` home shorthand are data/navigation symbols. `views/{settings/SettingsSkeleton,QualitySkeleton,library/LibrarySkeleton,MenuSkeleton}.tsx` are aria-hidden skeleton geometry with no visible or accessible words; string literals are CSS classes, dimensions, technical view IDs. `features/ytm/{types,index,settings}.ts` and `features/editor/index.ts` are DTOs, exports, or request defaults with zero user-facing copy. This does **not** clear `views/settings/YtmCard.tsx`; its many unclassified strings remain blocking.

**Coverage boundary of this follow-up:** 81 matching `frontend/src/**/*.{ts,tsx,html}` sources exist. Seventeen were directly read for this pass: `views/{QualityScreen,SettingsScreen,QualitySkeleton,MenuSkeleton}.tsx`, `views/settings/{parts,SettingsSkeleton,YtmCard}.tsx`, `views/library/LibrarySkeleton.tsx`, `features/ytm/{detail,cards,rows,badges,download,settings,types,index}.ts[x]`, `features/editor/index.ts`. The two non-skeleton screens, `parts`, and five YTM copy-bearing modules above have additional rows, but have **not** received independent literal-by-literal mechanical reconciliation: they remain partially reviewed, not audited/closed. Eight copy-free modules (four skeletons, three YTM technical files, editor index) have explicit exemption reasons above. `YtmCard` was read but has no phrase ledger. Of the 81 files, **65 have no follow-up inventory** (64 not directly read here plus `YtmCard`). Earlier shell rows are partial and do not convert these to audited. The exact 65-path list is appended to the Task 1 report. `frontend/index.html` is outside `frontend/src` and already has a partial classification above; it still requires closure under the brief's HTML scope. No claim of zero unclassified occurrences is made.

### File-level closure ledger (remaining work; not a claim of phrase coverage)

`R` = reviewed above with known entries (still verify English-only literals); `P` = `SOURCE_PHRASE_PENDING`, must enumerate exact branch, key, EN/RU, params, consumer before Task 1 can be signed off; `T` = technical/data-only per noted reason, subject to literal scan. These rows enumerate files, **not** each pending phrase. Do not use them as permission to close migration. Sources below are relative to `frontend/src/`.

| Files | State | Boundary / remaining work |
|---|---|---|
| `App.tsx`, `nav.ts`, `components/{Topbar,Tabbar,MoreMenu,CommandPalette}.tsx`, `components/dialogs/{KeymapDialog,DialogProvider}.tsx` | R | partial shell ledger above; check runtime caller labels |
| `components/{DownloadsDock,PlayerBar,AudioPlayer,PreviewButton}.tsx` | P | dock, audio controls, previews; include aria/title |
| `components/ui/{Spinner,EmptyState,Button,Table,Cover,Pipeline,SegControl,ProgressBar,CollapsibleGroup,TrackRow,QueueItem,StatusLine,SkeletonRows,Icon}.tsx` | P | Spinner default keyed above; verify other defaults/caller-supplied text; Icon/SkeletonRows likely technical only, require confirmation |
| `views/{MenuScreen,MenuSkeleton,DiscoverScreen,SearchScreen,RecommendScreen,MiscScreen,LibraryScreen,QualityScreen,QualitySkeleton,SettingsScreen}.tsx` | P | headings, status, confirmations, tooltips, options, toast, dynamic alternatives |
| `views/library/{TracksTab,ArtistsTab,AlbumsTab,PlaylistsTab,Inbox,Cards,albumDetail,trackDetail,LibrarySkeleton}.tsx` | P | titles, tables, playlist and selection labels, compress result display |
| `views/library/{useYtData,libUtils}.ts` | P | libUtils field labels and compression label are owned copy; useYtData likely fetch/data-only, verify |
| `views/settings/{parts,YtmCard,SettingsSkeleton}.tsx` | P | all settings widgets, help, authorization states |
| `features/editor/{TrackEditor,TrackEditorDialog,BatchEditorDialog}.tsx`, `features/editor/{runMetaflow,useMetaSources}.ts`, `lib/tags.ts` | P | field groups, UI errors and source/progress labels; preserve provider records |
| `features/ytm/{detail,badges,cards,rows}.tsx`, `features/ytm/{download,settings}.ts` | P | labels, counts, aria/title, jobs; check non-component copy |
| `features/ytm/{types,index}.ts`, `features/editor/index.ts` | T | types and re-exports, no UI literal expected; verify |
| `lib/{jobs,api,format,ops,diff,hotkeys,prefetch}.ts`, `lib/{toast,ops,diff}.tsx` | P | jobs/errors, units/dates, diff UI and toasts; hotkeys/prefetch likely technical, verify |
| `stores/{downloads,player,overlays}.ts`, `hooks/{useTheme,useHashRoute}.ts` | P | downloads owned titles; others state/IDs only if scan confirms |
| `main.tsx`, `routes.ts` | T | bootstrap and route IDs, no visible copy expected; verify |
| `frontend/index.html` | R | product title and locale metadata classified above |

**Open literal examples proving `P` is blocking:** `views/QualityScreen.tsx:134,140,156,171,292–295,317,329,349,354,402–405,418,445,458,474,478–479,501` contain distinct dynamic copy; `views/SettingsScreen.tsx:135–182,202–328` contains settings/toasts/dialogs; `features/ytm/detail.tsx:91,162,339` contains count morphology. No complete key/EN/RU mapping is supplied for these yet. Do not mark Task 1 done until these sites and all other P sites are reconciled.

### Reconciliation procedure / required evidence before migration tasks are closed

1. For **every file** in the table enumerate JSX text nodes and expressions containing text, JSX `aria-label`, `title`, `alt`, `placeholder`, `label`, `heading`, `sub`, `text` props, option text, constants/arrays of labels; then string arguments to `toast`, dialog `confirm/prompt/info/pick/open`, `Spinner`, `EmptyState`, `StatusLine`, `op.set`, `startJob`, downloads `titleFor`/`finish`. Inspect dynamic template strings and ternary branches individually. Add exact key and EN/RU ICU messages + params to both catalogs. Preserve source line references in review. For each file, use a closure ledger `path | occurrence/line | key | EN | RU | ICU params | render owner | exemption reason (if any)`; require one row per *distinct* visible branch, including repeated phrase sites mapped to a shared key. Mark each file `pending → reconciled`, not just each feature batch. In particular include `PlaylistsTab.tsx`, `index.html`, `lib/jobs.ts`, `lib/api.ts` fallback, `stores/downloads.ts`, `components/ui/Spinner.tsx` and `frontend/src/features/ytm/download.ts`; ensure `features/ytm/types.ts`, `lib/hotkeys.ts`, `routes.ts`, hooks/stores etc. are individually reviewed as UI source or explicitly excluded as technical/data-only. A file row with `SOURCE_PHRASE_PENDING` is unfinished until all occurrences are keyed or exempted with a reason.
2. Re-run `rg -n 'aria-label=|title=|alt=|placeholder=|toast\(|\.confirm\(|\.prompt\(|\.info\(|\.pick\(|\.open\(|\.set\(|<[^>]+>[^<{]*[[:alpha:]]' frontend/src --glob '*.{ts,tsx}'` plus literal scan for `label:`, `text:`, `sub:`, `heading=`, `message`, template strings and frontend index.html; do not rely solely on Cyrillic regex (English copy also exists). Review match against key, data exemption, technical/ID, comment, or test-only fixture. In code review require zero unclassified matches, not zero raw string matches.
3. Re-run `rg -n 'HTTPException|detail=|\.push\(|message=|msg=|jobs\.submit|errors\[|RuntimeError|\["label"\]|\["error"\]' src/web src/health.py src/lint.py src/quality.py src/normalize.py`. Review all lines, **including multiline `detail=`**, job result `label`, field `errors`, `_BatchProgress.complete`, and `str(exc)`. Compare to the backend rows above. `src/web/server.py:_HINT_HTML` is an app-owned user-visible `GET /` 503 page when `dist` is missing, **not** served through React; include in Task 6 (`server.py` is already in its file list). Freeze standalone bilingual EN/RU HTML variants selected by `Accept-Language` supported match, then English fallback; HTML `lang` and title/headline/paragraph instructions change together, command lines stay literal. Do not use `/api/settings`/localStorage here (SPA not built); no JS/i18next dependency. Retain status 503. Update `tests/test_web_api.py:2464` existing Russian text assertion to assert explicit ru header and add en/default tests. Terminal `run_server` prints at `server.py:122–135` are CLI output and out of web-UI scope per PM decision; do not treat them as a pending web localization task. Backend CLI-only rich table summaries/debug/log messages are not web UI but do not confuse them with serialized issue.message.
4. Assert en/ru key parity and ICU argument names/cases including ru `one/few/many/other`; capture mount-then-locale-change checks for any stored UI string, structured/legacy errors, SSE and polling restore, diagnostics issue/plan/apply and unchanged user data.

## Explicit data/technical exclusions

Never catalog track/album/artist/playlist titles, file and folder names/paths/URLs, lyrics, comments, tags (`old`, `new`, `value`), input query, Shazam file content, metadata records, provider service responses or unknown exception strings. Keep `field` ID raw in DTO and localize only its *display label*. `category`, `cause`, `kind`, `status`, `action`, browser/source/format IDs and API paths remain technical discriminators (map to UI labels). `Inbox`, `Shazam`, `Primuse`, `YouTube Music`, `iTunes`, `Deezer`, `Discogs`, `LRCLIB`, `ISRC`, `OAuth`, `JPEG`, `PNG`, `MD5`, `MB` are product/provider/technical names (may remain tokens **inside** translated sentences). `src/normalize.py:_GLOBAL_GENRE_MAP` values and `_normalize_feat` output are written to audio tags, not UI prose: do not translate; `_WHITESPACE_FIELDS` labels and `health.py:MISSING_FIELDS`/`lint.py:_TEXT_FIELDS` are owned display labels and should use stable field IDs/locale lookups if shown to user. `quality.py:_fix_target` fallback artist is stored as folder name; changing on locale switch would corrupt identity/idempotence. `frontend/src/views/library/libUtils.ts:CYR2LAT` is algorithmic data; `frontend/src/lib/diff.ts` diff parts are tag values. JSX symbols (`—`, `×`, arrows), numeric hotkeys and CSS class names are not translatable prose. Test fixtures and comments are not production copy, but tests asserting rendered Russian literals must be updated when behavior changes. Raw `item.error` in batch/YTM job result, OS/provider exceptions and HTTP status text stay readable strings unless a *known* app-owned branch is coded. `src/web/server.py:_HINT_HTML` is localized separately as specified above.

## Open concerns / handoff

- Frontend file-level inventory is **not** an exhaustive phrase-by-phrase bilingual catalog yet. The partial ledger and P rows are a blocker for Task 1 itself, not work silently deferred to Tasks 4/5/9. Do not freeze the full frontend key list or claim Task 1 complete based on this artifact. Check naming collisions during implementation.
- Diagnostic field labels resolve from raw IDs at render and English labels for fallbacks; **never** send Russian `_TEXT_FIELDS`/`MISSING_FIELDS` values as ICU params. If backend cannot emit field IDs on missing/whitespace issues, Task 8 is blocked until the producer is corrected.
- `QualityScreen.tsx:474` Russian regex is a contract coupling; `quality.py:131` sorts on message prose; both must be migrated with the DTO change. Job progress/history stored at start may outlive locale switch; resolve at render, not when pushing to store.
- `jobs.py` generic failure and API raw provider/OS detail are legacy strings intentionally, not omissions. Result `label/error` branches and fallback 503 page now have explicit scoped decisions above; tests must still verify legacy input and safe rendering.
- This artifact was assembled by source inspection, not by executing app/tests or a mechanically exhaustive literal extraction. Required independent scan and literal-by-literal closure remain for the implementing agents.

## Continuation audit: directly reconciled shared sources (2026-10-14)

This table adds occurrence-level decisions for **only the files named below**. Paths relative to `frontend/src/`; `—` means no ICU params. The earlier shell table supplies the exact EN/RU for its referenced keys; repeated occurrences are explicitly listed here rather than counted as new phrases. RenderableMessage from backend, caller-supplied labels, music metadata and URLs are not new local copy. Of the previously listed 65, **44 have received direct occurrence-level review or explicit no-copy exemptions; 21 remain without closure**, listed exactly in the task report. This is a documentation contract, not implemented code.

| Source occurrence | Key | EN | RU | ICU params | Producer → consumer |
|---|---|---|---|---|---|
| `App.tsx:58–60` | shell.skip | Skip to content | Перейти к содержимому | — | App → skip link |
| `nav.ts:11,21` | nav.home / nav.issues | Home / Issues | Главная / Проблемы | — | NAV_ITEMS/MORE_ITEMS → Topbar/Tabbar/MoreMenu/CommandPalette; each slash alternative is a separate key |
| `nav.ts:12–16,22–23` | nav.library / nav.search / nav.recommendations / nav.issues / nav.settings | Library / Search / Recommendations / Issues / Settings | Библиотека / Поиск / Рекомендации / Проблемы / Настройки | — | same; repeated issue/recommend/settings occurrences reuse keys |
| `components/Topbar.tsx:54` | shell.stats.health_title | Library health (tracks without issues) | Здоровье библиотеки (треки без проблем) | — | LibStats → title |
| `components/Topbar.tsx:60` | shell.stats.tracks | {count, plural, one {# track} other {# tracks}} · {size} | {count, plural, one {# трек} few {# трека} many {# треков} other {# трека}} · {size} | count,size | LibStats → topbar; size formatted in active locale |
| `components/Topbar.tsx:74` | shell.nav.main_aria | Main navigation | Основная навигация | — | Topbar → nav aria |
| `components/Topbar.tsx:85` | nav.* | see nav rows | см. nav rows | — | nav item label → topbar |
| `components/Topbar.tsx:94,96` | shell.theme.switch | Toggle theme | Переключить тему | — | Topbar → title, aria |
| `components/Topbar.tsx:100` | shell.theme.light / shell.theme.dark | light / dark | светлая / тёмная | — | Topbar → theme state (two alternatives) |
| `components/Tabbar.tsx:18,32,39,50` | shell.nav.mobile_aria / nav.* / shell.more | Mobile navigation / see nav rows / More | Мобильная навигация / см. nav rows / Ещё | — | Tabbar → nav aria, link, button aria/text; separate keys |
| `components/MoreMenu.tsx:23,35` | shell.nav.more_aria / nav.* | Additional navigation / see nav rows | Дополнительная навигация / см. nav rows | — | MoreMenu → menu aria / links |
| `components/CommandPalette.tsx:25,30,32,33,41,47,49,59` | shell.command.label / shell.command.search / shell.command.empty / shell.command.navigate / nav.* / shell.command.actions / shell.theme.switch / dialogs.keymap.title | Command palette / Search commands… / No commands found / Navigate / see nav rows / Actions / Toggle theme / Keyboard shortcuts | Палитра команд / Поиск команды… / Ничего не найдено / Переход / см. nav rows / Действия / Переключить тему / Горячие клавиши | — | CommandPalette → dialog label/input/empty/group/items; alternatives separate keys |
| `components/dialogs/KeymapDialog.tsx:8–14` | dialogs.keymap.command / dialogs.keymap.navigation / dialogs.keymap.theme / dialogs.keymap.this_list / dialogs.keymap.dismiss / dialogs.keymap.enter / dialogs.keymap.next_track | Command palette / Home / Library / Search / Recommendations / Issues / Settings / Dark / light theme / This list / Close dialog / list / Search / select / Next / previous track in list | Палитра команд / Главная / Библиотека / Поиск / Рекомендации / Проблемы / Настройки / Тёмная / светлая тема / Этот список / Закрыть диалог / список / Поиск / выбрать / Следующий / предыдущий трек в списке | — | ROWS → dialog table; seven separate keys; key glyphs are data |
| `components/dialogs/KeymapDialog.tsx:71–72,87` | dialogs.keymap.title / dialogs.close | Keyboard shortcuts / Close | Горячие клавиши / Закрыть | — | KeymapDialog → aria + heading / close button |
| `components/dialogs/DialogProvider.tsx:132,136–143` | dialogs.yes / dialogs.cancel / dialogs.confirm.title | Yes / Cancel / Confirmation | Да / Отмена / Подтверждение | — | confirm defaults → modal actions/title; both action order branches share keys |
| `components/dialogs/DialogProvider.tsx:150,153–154,163,174,181,230` | dialogs.prompt.title / dialogs.ok / dialogs.cancel / dialogs.close_aria | Input / OK / Cancel / Close dialog | Ввод / ОК / Отмена / Закрыть диалог | — | prompt/info/pick defaults and close aria; reused keys |
| `components/ui/Spinner.tsx:2` | common.loading | Loading… | Загрузка… | — | default text → Spinner, including App Suspense |
| `components/ui/Pipeline.tsx:13` | common.pipeline.pending | pending | ожидает | — | STATE_TEXT → node aria |
| `components/ui/Pipeline.tsx:14` | common.pipeline.active | in progress | выполняется | — | STATE_TEXT → node aria |
| `components/ui/Pipeline.tsx:15` | common.pipeline.done | done | готово | — | STATE_TEXT → node aria |
| `components/ui/Pipeline.tsx:16` | common.pipeline.error | error | ошибка | — | STATE_TEXT → node aria |
| `components/ui/Pipeline.tsx:17` | common.pipeline.skip | skipped | пропущен | — | STATE_TEXT → node aria |
| `components/ui/Pipeline.tsx:31` | common.pipeline.aria | Operation stages | Этапы операции | — | Pipeline → list aria |
| `components/ui/Pipeline.tsx:33` | common.pipeline.node_aria | {stage}: {state} | {stage}: {state} | stage,state (both localized by caller/state resolver) | Pipeline → listitem aria; stage label is caller-owned, not data by default |
| `components/ui/ProgressBar.tsx:10` | common.progress.aria | Operation progress | Прогресс операции | — | ProgressBar → progressbar aria |
| `components/ui/QueueItem.tsx:66,71` | jobs.common.done / jobs.common.failed | Done / Error | Готово / Ошибка | — | useQueue defaults → queue sub; retain keys for locale switch |
| `components/ui/QueueItem.tsx:82,84` | common.queue.removed / common.queue.undo | Removed from queue / Undo | Убрано из очереди / Вернуть | — | useQueue.dismiss → toastEx title/undo button |
| `components/ui/TrackRow.tsx:17` | common.cover_alt | Cover: {title} | Обложка: {title} | title (track metadata) | TrackRow → Cover img alt (only when title present) |
| `components/AudioPlayer.tsx:84–85` | player.pause / player.play | Pause / Play | Пауза / Воспроизвести | — | playing conditional → title + aria (two branches) |
| `components/AudioPlayer.tsx:100` | player.position_aria | Playback position | Позиция воспроизведения | — | slider aria |
| `components/PreviewButton.tsx:41` | player.preview.action | Preview | Прослушать | — | button title |
| `components/PreviewButton.tsx:42` | player.preview.aria | Preview: {title} | Прослушать: {title} | title (music title OR localized fallback below) | button aria |
| `components/PreviewButton.tsx:42` | player.preview.track_fallback | track | трек | — | empty title → player.preview.aria param |
| `components/PreviewButton.tsx:51`, `stores/player.ts:34`, `components/PlayerBar.tsx:26` | player.preview.title | Preview | Превью | — | player store fallback and MediaMetadata title; must not freeze rendered string on locale switch |
| `components/PlayerBar.tsx:66–67` | player.close | Close player | Закрыть плеер | — | title + aria |
| `components/DownloadsDock.tsx:43` | jobs.dock.heading | Downloads | Загрузки | — | dock collapsed label default |
| `components/DownloadsDock.tsx:49` | jobs.dock.active | Downloads · {count} · {percent}% | Загрузки · {count} · {percent}% | count,percent | active dock summary |
| `components/DownloadsDock.tsx:51` | jobs.dock.failed | Downloads · error ({count}) | Загрузки · ошибка ({count}) | count | error summary |
| `components/DownloadsDock.tsx:53` | jobs.dock.finished | Downloads · done | Загрузки · готово | — | done summary |
| `components/DownloadsDock.tsx:68` | jobs.dock.collapse_aria / jobs.dock.expand_aria | Downloads: collapse / Downloads: expand | Загрузки: свернуть / Загрузки: развернуть | — | expanded conditional → aria; separate branches |
| `components/DownloadsDock.tsx:80–85` | jobs.dock.clear_title / jobs.dock.clear_aria / jobs.dock.clear | Remove finished / Remove finished jobs / Clear | Убрать завершённые / Убрать завершённые задачи / Очистить | — | clear button title / aria / body; three distinct keys |
| `components/DownloadsDock.tsx:92` | jobs.dock.log_aria | Background jobs | Фоновые задачи | — | dock panel aria |
| `components/DownloadsDock.tsx:124–125` | jobs.dock.remove_title / jobs.dock.remove_aria | Remove / Remove: {title} | Убрать / Убрать: {title} | — / title (job title descriptor or user data resolved at render) | dismiss title / aria |
| `components/DownloadsDock.tsx:138` | jobs.dock.empty | No active jobs | Нет активных задач | — | empty panel |
| `stores/downloads.ts:48–60` | jobs.dock.title.ytm / jobs.dock.title.batch / jobs.dock.title.track / jobs.dock.title.shazam_scan / jobs.dock.title.recommend / jobs.dock.title.sort / jobs.dock.title.lyrics / jobs.dock.title.compress / jobs.dock.title.cookies / jobs.dock.title.accounts / jobs.dock.title.oauth / jobs.dock.title.primuse_backfill / jobs.dock.title.primuse_cleanup | YouTube Music — download / Batch download / Track download / Shazam — search / Recommendations / Sort library / Update lyrics / Compression / Browser cookies / Find accounts / YouTube Music sign-in / Primuse — lyrics / Primuse — cleanup | YouTube Music — скачивание / Пакетное скачивание / Скачивание трека / Shazam — поиск / Рекомендации / Сортировка библиотеки / Обновление текстов / Сжатие / Куки из браузера / Поиск аккаунтов / Вход YouTube Music / Primuse — тексты / Primuse — очистка | — | TITLES endpoint lookup → stored dock title; **13 separate keys**, resolve at render, not once at titleFor; distinguish backend job.name wording |
| `stores/downloads.ts:86` | jobs.dock.title.generic | Background job | Фоновая задача | — | unmatched endpoint → dock title |
| `stores/downloads.ts:93` | jobs.dock.launching | Starting… | Запуск... | — | track → dock sub |
| `stores/downloads.ts:125,178` | jobs.common.done / jobs.common.failed | Done / Error | Готово / Ошибка | — | finish/renderDone → dock sub |
| `stores/downloads.ts:167,169` | jobs.dock.title.restored / jobs.common.failed | Job / Error | Задача / Ошибка | — | restore fallback name/error → dock; do not replace existing server descriptors |
| `lib/jobs.ts:68,93,142` | jobs.common.failed | Error | Ошибка | — | polling/SSE/startJob unknown error fallback → dock/screen; preserve descriptor, do not `new Error(object)` |
| `lib/jobs.ts:139` | jobs.common.done | Done | Готово | — | startJob → dock |
| `features/editor/useMetaSources.ts:104,152` | editor.sources.unavailable_reason | Sources unavailable: {reason} | Источники недоступны: {reason} | reason (API/unknown error verbatim, resolve owned descriptor first) | batch/fallback request → warning toast |
| `features/editor/useMetaSources.ts:139` | editor.sources.unavailable | Sources unavailable | Источники недоступны | — | all sources failed → warning toast |
| `features/editor/runMetaflow.ts:15,19` | editor.metaflow.searching / editor.metaflow.lyrics | Searching metadata sources… / Updating lyrics (LRCLIB)… | Поиск метаданных в источниках... / Обновление текста (LRCLIB)... | — | runMetaflow onStep → caller progress; separate stages |

`components/DownloadsDock.tsx:97–110`: `item.name`, `item.title`, `item.msg` are **not automatically plain data**: backend name/progress/error and local title defaults must remain descriptor/key references until DOM. The middle dot separator between name and title is punctuation, not a key. `lib/jobs.ts:56–100` polling/SSE job error is backend-owned (legacy string or descriptor); recommendation payload `kind`, `seed`, `items`, `total` is data. `lib/api.ts:34–45` `{status} {statusText}` is a browser/HTTP fallback, not a catalog phrase; `detail`, `errors[field]` retain descriptors (previous freeze). `components/PreviewButton.tsx:53` API error is legacy/descriptor; do not catalog the raw exception. `components/ui/QueueItem.tsx:23–24,38,49` title/sub/text supplied by caller are not exempt caller copy. `components/ui/SegControl.tsx:23–39`, `EmptyState.tsx:20–22`, `Table.tsx:10–13`, `CollapsibleGroup.tsx:21`, `ProgressBar.tsx:18`, `lib/toast.tsx:28–44`, `lib/ops.tsx:29,49,61–62`, `DialogProvider.tsx:225,245,269,288,322–323` forward caller text and must receive localized messages at producer or resolve descriptors at display. In particular cached toasts and operation state must not render stale-language strings. `components/ui/TrackRow.tsx:19` em dash fallback is punctuation, not a key; its title/sub are music data *only for callers that pass metadata*.

### Explicit reviewed no-owned-copy exemptions (continuation)

Each file here was read in full; paths/lines establish the boundary. `components/ui/Button.tsx:6–27` only CSS variant names and caller-provided attributes; `Cover.tsx:8–23` default empty alt and aria-hidden music glyph (caller owns nonempty alt); `EmptyState.tsx:5–23` empty defaults and aria-hidden glyph, title/sub/action supplied by caller; `Icon.tsx:6–101` SVG geometry and aria-hidden span; `SegControl.tsx:16–39` caller options/aria label, value ID; `SkeletonRows.tsx:4–20` aria-hidden geometry; `StatusLine.tsx:6–18` aria-hidden symbolic markers and caller content; `Table.tsx:4–18` caller headers/rows; `CollapsibleGroup.tsx:19–23` caller title and caret glyph. `lib/diff.ts:14–57` only tag-value tokenization/diff flags; `lib/diff.tsx:4–13` only render of diff data; `lib/toast.tsx:24–60` caller-supplied title/body/undoLabel and Sonner position/role; `lib/ops.tsx:26–62` caller-owned stages/messages and technical status IDs; `lib/api.ts:26–71` transport/HTTP fallback (statusText is platform data, not owned prose), no owned UI phrase; `hooks/useHashRoute.ts:6–15`, `hooks/useTheme.ts:3–33`, `lib/hotkeys.ts:5–75`, `lib/prefetch.ts:9–39`, `main.tsx:8–12`, `routes.ts:3–18`, `stores/overlays.ts:15–28` only route/keyboard/theme/CSS/API IDs or bootstrap. `views/library/useYtData.ts:9–98` only API/cache/discriminator strings; no rendered copy. `components/ui/Spinner.tsx` and `ProgressBar.tsx` are **not** exempt (defaults/aria above); `stores/player.ts` is **not** exempt (preview fallback above); `components/AudioPlayer.tsx:8,130–132` clock digits and separator are data, not prose. `components/dialogs/DialogProvider.tsx:64,73` invariant exceptions are developer errors, not rendered copy; picker labels/subs and all caller options require separate caller audit.

### Separately checked HTML entry

`frontend/index.html:2,6,9–18,21–23`: `<title>music-lib</title>` is product-name data; `lang="ru"` is **not** a translation key and must track effective locale once known (do not leave permanently Russian); theme-color and inline theme script are tokens/state, no visible phrases, root/script paths technical. This is the built SPA entry, **not** the backend standalone 503 page; the latter remains governed by the EN/RU Accept-Language contract above. No HTML phrase row required for `frontend/index.html`.

**Still `SOURCE_PHRASE_PENDING` from the previous 65 (21 filenames):** `features/editor/BatchEditorDialog.tsx`, `features/editor/TrackEditor.tsx`, `features/editor/TrackEditorDialog.tsx`, `lib/format.ts`, `lib/tags.ts`, `views/DiscoverScreen.tsx`, `views/LibraryScreen.tsx`, `views/MenuScreen.tsx`, `views/MiscScreen.tsx`, `views/RecommendScreen.tsx`, `views/SearchScreen.tsx`, `views/library/AlbumsTab.tsx`, `views/library/ArtistsTab.tsx`, `views/library/Cards.tsx`, `views/library/Inbox.tsx`, `views/library/PlaylistsTab.tsx`, `views/library/TracksTab.tsx`, `views/library/albumDetail.tsx`, `views/library/libUtils.ts`, `views/library/trackDetail.tsx`, `views/settings/YtmCard.tsx`. `lib/format.ts` has been read but not occurrence-reconciled: `:6` GB/MB and `:30–33` fixed Russian date layout need locale-aware formatting; `:11–17` hardcodes Russian plural rules. `lib/tags.ts`, `views/library/libUtils.ts`, `views/settings/YtmCard.tsx` have since been directly read but are not yet occurrence-reconciled; the other 17 files have not been read in this continuation. Additional verification still required for the previously partially inventoried QualityScreen, SettingsScreen, parts, and YTM modules; no zero-unclassified-literals assertion is made.

Read-but-unmapped anchors to carry forward (not counted as catalog rows): `lib/tags.ts:9–20` group and field labels, `:42–43` validation; `views/library/libUtils.ts:145–155` shared album field labels, `:172–173` compression label alternatives, `:73–75,117–119` locale-implicit comparisons (sort semantics, not keys); `views/settings/YtmCard.tsx:102–111` account option variants, `:148–150` extract completion, `:162–211` auth dialogs and toasts, `:222–561` option labels, accessibility attributes, help text, cookie/check/OAuth results. Account names/handles, browser names, Page IDs, returned errors and tag values remain verbatim data. No exact occurrence count can be claimed for these files without ledger rows.

### Continuation: editor dialogs, field schema and formatting (five-file occurrence audit)

This section supersedes the **five named paths only** in the historical pending list at line 561 and the `lib/tags.ts` / `lib/format.ts` anchors at line 563. That list is a snapshot, **not** the current remaining-file count; the current count is 16 (enumerated in the audit report). Paths below are relative to `frontend/src/`; references are to the inspected pre-migration source. `—` = no ICU arguments. Each slash-separated key at a conditional denotes a **separate branch/key**; shared keys explicitly refer to the earlier canonical entries. EN/RU are catalog proposals, not source edits. For new editor keys use the `editor.*` namespace already reserved above. Source → consumer includes intermediary state where it affects language switching. Provider/OS/API strings must not be translated as arbitrary text.

| Source occurrence | Key (new unless marked reused) | EN | RU | ICU params | Producer → consumer |
|---|---|---|---|---|---|
| `features/editor/BatchEditorDialog.tsx:38` | editor.batch.title | Batch metadata editor | Массовое редактирование метаданных | — | trackBatchEditorDialog → DialogProvider title |
| `features/editor/BatchEditorDialog.tsx:42` | editor.batch.done | Done | Готово | — | dialog action → DialogProvider button; distinct from `jobs.common.done` job status |
| `features/editor/BatchEditorDialog.tsx:121` (one saved) | editor.tags.saved (shared with `TrackEditor.tsx:275`) | Tags saved | Теги сохранены | — | BatchBody.finish / TrackEditor.save → toast |
| `features/editor/BatchEditorDialog.tsx:121` (multiple saved) | editor.batch.saved_count | Tracks saved: {count} | Сохранено треков: {count} | count | BatchBody.finish → toast; branch only for count > 1 |
| `features/editor/BatchEditorDialog.tsx:140` | editor.batch.select_source_first | Select a source for the current track first | Сначала выберите источник для текущего трека | — | applyAlbumSource → warning toast |
| `features/editor/BatchEditorDialog.tsx:143,147` | editor.batch.applying (reused in both loop stages) | Applying {index}/{total}… | Применяю {index}/{total}… | index,total | applyAlbumSource → applyLabel state → disabled button; preserve descriptor/params until render |
| `features/editor/BatchEditorDialog.tsx:182,183–184` (no failure) | editor.batch.applied | Applied: {count} | Применено: {count} | count | applyAlbumSource → toast; success branch |
| `features/editor/BatchEditorDialog.tsx:182–184` (failure) | editor.batch.applied_with_errors | Applied: {count}, errors: {failed} | Применено: {count}, ошибок: {failed} | count,failed | applyAlbumSource → warning toast; avoid concatenating pretranslated fragments |
| `features/editor/BatchEditorDialog.tsx:190` | editor.batch.tracks_heading | Tracks ({count}) | Треки ({count}) | count | BatchBody → sidebar heading |
| `features/editor/BatchEditorDialog.tsx:194` | editor.batch.apply_title | Apply the selected source from the current track to all tracks | Разнести выбранный на текущем треке источник на все треки | — | BatchBody → apply button title |
| `features/editor/BatchEditorDialog.tsx:195` | editor.batch.apply_aria | Apply selected source to all tracks | Применить выбранный источник ко всем трекам | — | BatchBody → apply button aria-label |
| `features/editor/BatchEditorDialog.tsx:199` | editor.batch.apply_all | Apply to all tracks | Применить ко всем трекам | — | BatchBody → apply button idle label; applying branch uses `editor.batch.applying` |
| `features/editor/BatchEditorDialog.tsx:201` | editor.batch.list_aria | Tracks to edit | Треки для редактирования | — | BatchBody → listbox aria-label |
| `features/editor/BatchEditorDialog.tsx:216` (dirty branch) | editor.batch.unsaved_aria | {track} (unsaved changes) | {track} (есть несохранённые изменения) | track (title and optional artist, verbatim) | BatchBody rowState → option aria-label; clean branch is `track` verbatim, not a key |
| `features/editor/TrackEditor.tsx:261` | editor.validation.check_field | Check “{fieldLabel}”: {reason} | Проверьте поле «{fieldLabel}»: {reason} | fieldLabel (localized `editor.fields.*`), reason (localized validation key) | validateTagField → TrackEditor.save → error toast; retain field ID/error key until render |
| `features/editor/TrackEditor.tsx:275` | editor.tags.saved (reused) | Tags saved | Теги сохранены | — | TrackEditor.save → toast |
| `features/editor/TrackEditor.tsx:311` | editor.load_error | Error: {reason} | Ошибка: {reason} | reason (API descriptor or legacy text, resolved at UI boundary) | GET tags catch → state.loadError → panel; do not freeze `Error.message` for a known code |
| `features/editor/TrackEditor.tsx:314` | common.loading (reused; existing EN `Loading…`) | Loading… | Загрузка… | — | TrackEditor → Spinner text; current source uses `Загрузка...` |
| `features/editor/TrackEditor.tsx:320` | editor.cover.current_alt | Current track cover | Текущая обложка трека | — | TrackEditor → img alt |
| `features/editor/TrackEditor.tsx:329` | editor.fields.cover (reused) | Cover art | Обложка | — | TrackEditor → cover section heading |
| `features/editor/TrackEditor.tsx:333` | editor.cover.current_title | Current cover | Текущая обложка | — | TrackEditor → before-cover title |
| `features/editor/TrackEditor.tsx:335` | editor.cover.source_title | Source cover | Обложка источника | — | TrackEditor → after-cover title |
| `features/editor/TrackEditor.tsx:336` | editor.cover.source_alt | Selected source cover | Обложка выбранного источника | — | TrackEditor → after-cover img alt |
| `features/editor/TrackEditor.tsx:345` | editor.cover.apply | Apply cover | Применить обложку | — | TrackEditor → checkbox label |
| `features/editor/TrackEditor.tsx:351` | editor.cover.not_found | Cover not found | Обложка не найдена | — | TrackEditor → cover empty text |
| `features/editor/TrackEditor.tsx:355` | editor.sources.heading | Source | Источник | — | TrackEditor → source section heading |
| `features/editor/TrackEditor.tsx:367` | editor.groups.main / editor.groups.release / editor.groups.other (reused from `lib/tags.ts:9,13,17` below) | Main / Release / Other | Основное / Релиз / Прочее | — | TAG_FIELDS.group → TrackEditor field group heading; one key per group |
| `features/editor/TrackEditor.tsx:378,408` | editor.fields.title / artist / album / album_artist / year / genre / track_number / disc_number / isrc / composer / publisher / comment (reused from `lib/tags.ts:10–19`) | field names as in rows below | названия полей из строк ниже | — (fieldLabel is resolved value in restore aria) | TAG_FIELDS label → input label and restore aria argument; 12 separate keys, no raw Russian label cached across locale change |
| `features/editor/TrackEditor.tsx:400` | editor.validation.year_four_digits / editor.validation.integer / api.fields.year_four_digits / api.fields.integer_required (reused) | Year: 4 digits, e.g. 2024 / Integer / Year must be four digits, e.g. 2024 / Must be an integer | Год: 4 цифры, например 2024 / Целое число / Год должен состоять из 4 цифр, например 2024 / Должно быть целым числом | — | local validation or HTTP errors[field] → state.errors → aria-live field error; descriptor persists until render; each alternative is separate |
| `features/editor/TrackEditor.tsx:407` | editor.fields.restore_title | Restore original value from file | Вернуть исходное значение из файла | — | TrackEditor → chip title |
| `features/editor/TrackEditor.tsx:408` | editor.fields.restore_aria | Restore original value for {fieldLabel} | Вернуть исходное значение поля {fieldLabel} | fieldLabel (localized `editor.fields.*`) | TrackEditor → chip aria-label; chip body `orig` is original file tag data |
| `features/editor/TrackEditor.tsx:439` | editor.sources.searching | Searching sources… | Поиск в источниках… | — | SourceList → Spinner text |
| `features/editor/TrackEditor.tsx:459` | editor.sources.none | No sources found | Источники не найдены | — | SourceList → empty state |
| `features/editor/TrackEditor.tsx:468,493` | editor.sources.album_tags | Album tags | Теги альбома | — | SourceList album fallback → card label and title; `r.album` appended only by next row |
| `features/editor/TrackEditor.tsx:468` (album present) | editor.sources.album_tags_named | Album tags: {album} | Теги альбома: {album} | album (provider/track data) | SourceList album fallback → cardLabel → selection aria |
| `features/editor/TrackEditor.tsx:469` (no record metadata) | editor.sources.record_fallback | Source record | Запись источника | — | SourceList → cardLabel → selection aria |
| `features/editor/TrackEditor.tsx:478` | editor.sources.select_aria | Select source: {record} | Выбрать источник: {record} | record (localized album-tags label OR verbatim provider title/artist/album) | SourceList → source card aria-label; provider group name at :465 stays verbatim |
| `features/editor/TrackEditor.tsx:504` | editor.sources.searching_provider | Searching {source}… | Ищу в {source}… | source (provider name verbatim) | pending provider name → SourceList group status |
| `features/editor/TrackEditorDialog.tsx:36` (title present) | editor.dialog.title | Editor: {title} | Редактор: {title} | title (track metadata verbatim) | trackEditorDialog → DialogProvider title |
| `features/editor/TrackEditorDialog.tsx:36` (title absent) | editor.dialog.track_fallback | track | трек | — | trackEditorDialog → `editor.dialog.title` title param; do not translate provided `tags.title` |
| `features/editor/TrackEditorDialog.tsx:54` | editor.dialog.save | Save | Сохранить | — | trackEditorDialog → DialogProvider action button |
| `features/editor/TrackEditorDialog.tsx:55` | dialogs.cancel (reused) | Cancel | Отмена | — | trackEditorDialog → DialogProvider ghost action |
| `lib/tags.ts:9` | editor.groups.main | Main | Основное | — | TAG_FIELDS → TrackEditor group heading |
| `lib/tags.ts:13` | editor.groups.release | Release | Релиз | — | TAG_FIELDS → TrackEditor group heading |
| `lib/tags.ts:17` | editor.groups.other | Other | Прочее | — | TAG_FIELDS → TrackEditor group heading |
| `lib/tags.ts:10` (`title`) | editor.fields.title (reused) | Title | Название | — | TAG_FIELDS/TAG_FIELD_LIST → TrackEditor label, validation toast, restore aria; diagnostics field resolver |
| `lib/tags.ts:10` (`artist`) | editor.fields.artist (reused) | Artist | Исполнитель | — | same |
| `lib/tags.ts:11` (`album`) | editor.fields.album (reused) | Album | Альбом | — | same |
| `lib/tags.ts:11` (`album_artist`) | editor.fields.album_artist (reused) | Album artist | Альбом-исполнитель | — | same; canonical baseline had `Исполнитель альбома`; **normalize RU to baseline or approve change across all consumers** |
| `lib/tags.ts:14` (`year`) | editor.fields.year (reused) | Year | Год | — | same |
| `lib/tags.ts:14` (`genre`) | editor.fields.genre (reused) | Genre | Жанр | — | same |
| `lib/tags.ts:15` (`track_number`) | editor.fields.track_number (reused) | Track number | Трек № | — | same; baseline RU `№ трека`, harmonize with baseline |
| `lib/tags.ts:15` (`disc_number`) | editor.fields.disc_number (reused) | Disc number | Диск № | — | same; baseline RU `№ диска`, harmonize with baseline |
| `lib/tags.ts:18` (`isrc`) | editor.fields.isrc (reused) | ISRC | ISRC | — | same |
| `lib/tags.ts:18` (`composer`) | editor.fields.composer (reused) | Composer | Композитор | — | same |
| `lib/tags.ts:19` (`publisher`) | editor.fields.publisher (reused) | Publisher / Label | Издатель / Лейбл | — | same |
| `lib/tags.ts:19` (`comment`) | editor.fields.comment (reused) | Comment | Комментарий | — | same |
| `lib/tags.ts:42` | editor.validation.year_four_digits (reused) | Year: 4 digits, e.g. 2024 | Год: 4 цифры, например 2024 | — | validateTagField → TrackEditor state.errors → field error + `editor.validation.check_field` toast |
| `lib/tags.ts:43` | editor.validation.integer (reused for both track/disc) | Integer | Целое число | — | validateTagField → TrackEditor state.errors → field error + toast |

**Canonical field-label resolution:** the three `lib/tags.ts` source variants for `album_artist`, `track_number`, `disc_number` above are transcribed faithfully to show the occurrences; their reused catalog keys retain the baseline RU values `Исполнитель альбома`, `№ трека`, `№ диска` at lines 208–211. They must not become second keys solely because their current spelling differs. Group and field labels need to be resolved by stable field/group ID at display time, not stored as translated values in `TAG_FIELDS` consumed by the reducer; local validation returns key/descriptors, not a locale-frozen error string. `lib/tags.ts:42–43` is also called from `views/library/albumDetail.tsx:238` (its display/toast is outside this five-file audit); include that consumer when migrating validation. `TrackEditor.tsx:282–288` receives `err.fields` from HTTP and `err.message`; known structured descriptors need resolution at UI, unknown legacy strings remain unchanged. `TrackEditorDialog.tsx:27–30` likewise forwards an API error to toast without a new key. No new error key is assigned to external exception text.

**Formatting decisions (no catalog strings for numeric/time data):**

| Source occurrence | Key / formatter | EN | RU | ICU params | Producer → consumer |
|---|---|---|---|---|---|
| `lib/format.ts:4` | none (data placeholder) | — | — | — | fmtSize falsy bytes → callers; em dash has no language-dependent words; distinguish 0 from absent only if product behavior changes |
| `lib/format.ts:6` (`>=1024 MB` / `<1024 MB`) | `Intl.NumberFormat(activeLocale, {style:'unit',unit:'gigabyte'/'megabyte',unitDisplay:'short',maximumFractionDigits:1,minimumFractionDigits:1})` or equivalent locale-aware number plus localized unit via Intl | e.g. `1.0 GB` / `1.0 MB` | e.g. `1,0 ГБ` / `1,0 МБ` | numeric value (not ICU text) | fmtSize(bytes) → MenuScreen:98, trackDetail:45, libUtils:173, Topbar:60, Cards:91; retain existing binary 1024 thresholds and one decimal; assert desired binary-vs-SI unit policy before implementation |
| `lib/format.ts:11–17` (`one/few/many` branches) | ICU `{count, plural, one {...} few {...} many {...} other {...}}` at each **caller-owned noun phrase** or `Intl.PluralRules(activeLocale)` when caller truly needs a category | English one/other | Russian one/few/many/other | count at caller | plural() → TracksTab:109, ArtistsTab:88, PlaylistsTab:38, AlbumsTab:116,124, albumDetail:192,267,280,437; current helper assumes Russian even under English; caller phrases need their own keys (out of this batch) |
| `lib/format.ts:19–26` | none (elapsed-time numeric data) | `m:ss` / `h:mm:ss` | `m:ss` / `h:mm:ss` | — | fmtDuration → SearchScreen:350,371,490; MenuScreen:97; trackDetail:43; MiscScreen:236; ytm/detail:238, rows:54,107; Cards:90; zero/absent → empty by current contract; no human-readable units or copy |
| `lib/format.ts:30–33` | `Intl.DateTimeFormat(activeLocale, {day:'2-digit',month:'2-digit',year:'numeric'})` with explicit timezone policy | locale date order (e.g. `12/31/2024`) | locale date order (e.g. `31.12.2024`) | timestamp data (seconds → milliseconds) | fmtDate(ts) → MenuScreen:133; keep absent → empty; current `Date#getDate` uses local timezone, so specify local timezone unless deliberately changing behavior; no catalog key |

**Explicit exclusions / branch reconciliation:** `BatchEditorDialog.tsx:28–33,204,235–236` derives fallback filenames, track title and artist from caller/file and joins them with punctuation; clean option aria at :216 uses that data. :77,157 fetch URLs are technical; :170–175 provider record, cover URL and album-match logic are data/algorithm; :178 catch silently increments count, with owned toast at :182–184. :219–232 keyboard keys are technical. `TrackEditor.tsx:94–115,117–198,247–252,265–274,293–307` field IDs, values, selected provider source and API paths are technical/user data; `:234`, `:282–288` error content comes from API/exception and is not a new local literal; `:322,334,390–397,489–495` note glyph, arrow, diff tokens, placeholder em dash, source year and provider metadata are data/punctuation (only album-tags/fallback and aria wrappers above are copy). `:465` provider source name is verbatim. `TrackEditorDialog.tsx:18–27,29,58` path/thumbnail/tags and returned error are data or transport; title fallback and dialog actions are inventoried. `lib/tags.ts:23–37,39–41,44–74` tag IDs, empty validation sentinel, regex, provider field values, publisher fallback, normalized lookup key and album-match choice are algorithm/data; group and label literals plus both nonempty validation branches are inventoried. `lib/format.ts:3–34` math, thresholds, zero/empty result, date parts and separators are formatter behavior, not separately translated prose; locale-sensitive results and Russian-only inflection are accounted for above. No tests or application code were changed in this audit.

### Continuation: six top-level views (2026-10-14 occurrence audit)

This section supersedes **only** `views/{DiscoverScreen,LibraryScreen,MenuScreen,MiscScreen,RecommendScreen,SearchScreen}.tsx` in the pending snapshot at :561 and the 16-file report list. Paths below are relative to `frontend/src/`; `:line` always refers to the current, unmodified source. Each row represents a distinct phrase or branch; comma-separated lines mean repeated occurrences sharing one key. Slash-separated alternatives are individually keyed in separate rows. EN/RU are catalog proposals, not edits. `—` means no ICU arguments. `ref` means the key was already defined in the canonical map; use its existing translation where punctuation differs. Consumer specifies the render boundary, including intermediate job/operation/dialog state. For every stored string, preserve key + params until display so a locale switch can rerender it. Literal service/product names and data inside a translated sentence remain verbatim.

| Source occurrence | Key | EN | RU | ICU params | Producer → render owner/consumer |
|---|---|---|---|---|---|
| `views/DiscoverScreen.tsx:10,55` | nav.search (ref) | Search | Поиск | — | TABS → tab button |
| `views/DiscoverScreen.tsx:45` | discover.tabs_aria | Download sections | Загрузка: разделы | — | tablist aria-label |
| `views/LibraryScreen.tsx:208` | quality.selection.required (ref; harmonize existing RU) | Select tracks using the checkboxes on the cards | Отметьте треки флажками на карточках | — | selectedPaths → warning toast |
| `views/LibraryScreen.tsx:226` | library.selection.saved | Saved: {count, plural, one {# track} other {# tracks}} | Сохранено: {count, plural, one {# трек} few {# трека} many {# треков} other {# трека}} | count | batch editor result → toast; distinct punctuation from quality.selection.saved |
| `views/LibraryScreen.tsx:235` | library.compress.confirm | Compress {count, plural, one {# track} other {# tracks}} to the quality set in Settings? The files will be re-encoded; their original quality cannot be restored. | Сжать {count, plural, one {# трек} few {# трека} many {# треков} other {# трека}} до качества из настроек? Файлы будут перекодированы — исходное качество не восстановить. | count | selected paths → confirm dialog body |
| `views/LibraryScreen.tsx:236` | library.compress.action | Compress | Сжать | — | confirm okTitle (also toolbar :597 uses same verb) |
| `views/LibraryScreen.tsx:244` | library.lyrics.confirm_all | Update synchronized lyrics? Tracks that already have synchronized lyrics will be skipped. | Обновить синхронные тексты? Уже имеющие синхронный текст треки будут пропущены. | — | confirm body |
| `views/LibraryScreen.tsx:245` | quality.lyrics.update_action (ref) | Update | Обновить | — | confirm okTitle |
| `views/LibraryScreen.tsx:250` | library.lyrics.preparing | Preparing the lyrics list… | Подготавливаем список текстов… | — | op.set → OpPanels |
| `views/LibraryScreen.tsx:263` | library.lyrics.summary | Updated: {updated}, skipped: {skipped}, errors: {errors} | Обновлено: {updated}, пропущено: {skipped}, ошибок: {errors} | updated,skipped,errors | op.set → OpPanels |
| `views/LibraryScreen.tsx:264` | quality.refreshing (ref) | Refreshing list… | Обновление списка… | — | op.set → OpPanels |
| `views/LibraryScreen.tsx:281` | library.sort.already_sorted | Everything is already sorted into folders | Всё уже разложено по папкам | — | toast |
| `views/LibraryScreen.tsx:285,588` | library.sort.title | Sort into folders | Разложить по папкам | — | dialog title / toolbar title |
| `views/LibraryScreen.tsx:288` (not truncated) | library.sort.move_count | Files to move: {count} | Переместить файлов: {count} | count | dialog build → summary |
| `views/LibraryScreen.tsx:288` (truncated) | library.sort.move_count_truncated | Files to move: {count} (first {shown} shown) | Переместить файлов: {count} (показаны первые {shown}) | count,shown | dialog build → summary; no concatenated suffix |
| `views/LibraryScreen.tsx:290` | library.sort.explanation | Move into Artist/Album folders according to tags; empty folders will be removed | перенос в Artist/Album по тегам; пустые папки будут удалены | — | dialog explanatory note; Artist/Album are folder tokens |
| `views/LibraryScreen.tsx:307,338` | dialogs.cancel (ref) | Cancel | Отмена | — | sort/dedup dialog actions |
| `views/LibraryScreen.tsx:308` | library.sort.action | Sort | Сортировать | — | dialog action |
| `views/LibraryScreen.tsx:319` | library.sort.summary | Moved: {moved}, folders removed: {removed} | Перемещено: {moved}, удалено папок: {removed} | moved,removed | op.set → OpPanels |
| `views/LibraryScreen.tsx:329,331` | library.dedup.mode | Deduplication mode | Режим дедупликации | — | dialog title and select aria |
| `views/LibraryScreen.tsx:332` | library.dedup.exact | Exact (MD5) | Точная (MD5) | — | select option; md5 value is ID |
| `views/LibraryScreen.tsx:333` | library.dedup.semantic | Semantic (title + artist) | Семантическая (название + артист) | — | select option; semantic value is ID |
| `views/LibraryScreen.tsx:337` | library.dedup.find | Find | Найти | — | dialog action |
| `views/LibraryScreen.tsx:347` | library.dedup.none | No duplicates found | Дубликатов не найдено | — | toast |
| `views/LibraryScreen.tsx:355` | quality.category.duplicates (ref) | Duplicates | Дубликаты | — | dialog title |
| `views/LibraryScreen.tsx:359` | library.dedup.instructions | Groups found: {count}. Select the files to delete. | Найдено групп: {count}. Отметьте файлы для удаления. | count | dialog build → note |
| `views/LibraryScreen.tsx:363` | library.dedup.group | Group: | Группа: | — | dialog group label |
| `views/LibraryScreen.tsx:375` | library.dedup.best | best | лучший | — | file badge |
| `views/LibraryScreen.tsx:383` | library.dedup.delete_selected | Delete selected | Удалить выделенные | — | dialog action |
| `views/LibraryScreen.tsx:384,436` | dialogs.close (ref) | Close | Закрыть | — | dialog action |
| `views/LibraryScreen.tsx:389` | library.dedup.deleted | Deleted: {count} | Удалено: {count} | count | toast |
| `views/LibraryScreen.tsx:402` | library.merge.none | No albums with multiple tracks found | Альбомов с несколькими треками не найдено | — | warning toast |
| `views/LibraryScreen.tsx:407` | library.merge.title | Merge albums | Объединить альбомы | — | dialog title and overflow action :589 |
| `views/LibraryScreen.tsx:411` | library.merge.instructions | Albums found: {count}. Select the albums to merge. | Найдено альбомов: {count}. Отметьте альбомы для объединения. | count | dialog build → note |
| `views/LibraryScreen.tsx:426` | library.merge.mixed | different artists | разные исполнители | — | album badge |
| `views/LibraryScreen.tsx:428` | library.merge.album_meta | {count} {count, plural, one {track} other {tracks}} · {artists} | {count} тр. · {artists} | count,artists (joined provider/tag names or em dash, verbatim) | dialog album subline; short Russian abbreviation intentionally retained |
| `views/LibraryScreen.tsx:435` | library.merge.selected | Merge selected | Объединить выбранные | — | dialog action |
| `views/LibraryScreen.tsx:444` | library.merge.album_artist_prompt | Album artist for albums with different artists | Альбом-артист для альбомов с разными исполнителями | — | prompt body |
| `views/LibraryScreen.tsx:457` | library.merge.merged | Merged: {count} | Объединено: {count} | count | toast |
| `views/LibraryScreen.tsx:480` | library.tabs.albums | Albums | Альбомы | — | tabs array → tab button :585 |
| `views/LibraryScreen.tsx:481` | library.tabs.tracks | Tracks | Треки | — | tabs → tab button :585 |
| `views/LibraryScreen.tsx:482` | library.tabs.artists | Artists | Исполнители | — | tabs → tab button :585 |
| `views/LibraryScreen.tsx:483` | library.tabs.playlists | Playlists | Плейлисты | — | tabs → tab button :585 |
| `views/LibraryScreen.tsx:580` | nav.library (ref) | Library | Библиотека | — | h1 |
| `views/LibraryScreen.tsx:581` | library.subtitle | All files, tags, covers and lyrics | все файлы, теги, обложки и тексты | — | subtitle |
| `views/LibraryScreen.tsx:585` | library.views_aria | Library views | Представления библиотеки | — | tab group aria |
| `views/LibraryScreen.tsx:586` (full) | library.density.grid | Grid | Сетка | — | SegControl option |
| `views/LibraryScreen.tsx:586` (compact) | library.density.compact | Compact | Компакт | — | SegControl option |
| `views/LibraryScreen.tsx:586` (minimal) | library.density.list | List | Список | — | SegControl option |
| `views/LibraryScreen.tsx:586` (label) | library.density.aria | Grid density | Плотность сетки | — | SegControl aria |
| `views/LibraryScreen.tsx:587` (title) | library.sort.control_title | Sort | Сортировка | — | select title |
| `views/LibraryScreen.tsx:587` (aria) | library.sort.control_aria | Sort tracks | Сортировка треков | — | select aria |
| `views/LibraryScreen.tsx:587` (title option) | library.sort.by_title | By title | По названию | — | select option |
| `views/LibraryScreen.tsx:587` (artist option) | library.sort.by_artist | By artist | По исполнителю | — | select option |
| `views/LibraryScreen.tsx:587` (size option) | library.sort.by_size | By size | По размеру | — | select option |
| `views/LibraryScreen.tsx:588` (folder aria) | library.sort.folders_aria | Sort into Artist/Album folders | Разложить по папкам Artist/Album | — | folder button aria |
| `views/LibraryScreen.tsx:588` (lyrics title) | library.lyrics.update_title | Update lyrics | Обновить тексты | — | toolbar button title |
| `views/LibraryScreen.tsx:588` (lyrics aria) | library.lyrics.update_aria | Update song lyrics | Обновить тексты песен | — | toolbar button aria |
| `views/LibraryScreen.tsx:589` (tags) | library.selection.tags_action | Tags for selected tracks | Теги выбранных | — | OverflowMenu item |
| `views/LibraryScreen.tsx:589` (duplicates) | library.dedup.find_action | Find duplicates | Найти дубликаты | — | OverflowMenu item |
| `views/LibraryScreen.tsx:589` (merge) | library.merge.title (ref in this section) | Merge albums | Объединить альбомы | — | OverflowMenu item |
| `views/LibraryScreen.tsx:589` (compress) | library.compress.selected_action | Compress selected | Сжать выбранные | — | OverflowMenu item |
| `views/LibraryScreen.tsx:590` (badge) | library.selection.badge | selected {count} | выбрано {count} | count | selection badge |
| `views/LibraryScreen.tsx:590` (title) | quality.refresh (ref) | Refresh | Обновить | — | reload button title |
| `views/LibraryScreen.tsx:590` (aria) | library.refresh_aria | Refresh library | Обновить библиотеку | — | reload button aria |
| `views/LibraryScreen.tsx:594` | quality.selection.toolbar (ref) | Selected track actions | Действия с выбранными треками | — | selection toolbar aria; source shorter |
| `views/LibraryScreen.tsx:595` | library.selection.count | Selected {count} | Выбрано {count} | count | selection toolbar count; quality.selection.count has colon, distinct |
| `views/LibraryScreen.tsx:596` | library.selection.tags | Tags | Теги | — | toolbar button |
| `views/LibraryScreen.tsx:597` | library.compress.action (ref) | Compress | Сжать | — | toolbar button |
| `views/LibraryScreen.tsx:598` | quality.selection.clear (ref) | Clear selection | Сбросить | — | toolbar button; source says Снять выделение, normalize or use distinct copy if specificity required |
| `views/LibraryScreen.tsx:643,644` | library.more_actions | More actions | Ещё действия | — | OverflowMenu button title and aria |
| `views/LibraryScreen.tsx:728` | library.filters.search_placeholder | Find… | Найти… | — | FiltersBar input placeholder |
| `views/LibraryScreen.tsx:729` | library.filters.search_aria | Search by title, artist or album | Поиск по названию, исполнителю, альбому | — | input aria |
| `views/LibraryScreen.tsx:743,744` | library.filters.clear_search | Clear search | Очистить поиск | — | clear button title and aria |
| `views/LibraryScreen.tsx:755` | library.filters.label | Filter: | Фильтр: | — | filter bar text |
| `views/LibraryScreen.tsx:758` (all) | library.filters.all_artists | All artists | Все исполнители | — | select default option |
| `views/LibraryScreen.tsx:758` (aria) | library.filters.artist_aria | Filter by artist | Фильтр по исполнителю | — | select aria |
| `views/LibraryScreen.tsx:759` (all) | library.filters.all_albums | All albums | Все альбомы | — | select default option |
| `views/LibraryScreen.tsx:759` (aria) | library.filters.album_aria | Filter by album | Фильтр по альбому | — | select aria |
| `views/LibraryScreen.tsx:760` (all) | library.filters.all_genres | All genres | Все жанры | — | select default option |
| `views/LibraryScreen.tsx:760` (aria) | library.filters.genre_aria | Filter by genre | Фильтр по жанру | — | select aria |
| `views/LibraryScreen.tsx:767` | library.filters.missing_lyrics | no lyrics | нет текста | — | filter checkbox label |
| `views/LibraryScreen.tsx:775` | library.filters.needs_compression | needs compression | нужно сжать | — | filter checkbox label |
| `views/LibraryScreen.tsx:793` (all selected) | library.selection.deselect_all | Deselect all | Снять все | — | select-all button; distinct from quality.selection.deselect_all ({count}) |
| `views/LibraryScreen.tsx:793` (not all) | quality.selection.select_all (ref) | Select all ({count}) | Выбрать все ({count}) | count | select-all button |
| `views/LibraryScreen.tsx:804` | library.filters.reset | Reset | Сбросить | — | filter-reset button (not selection clearing) |
| `views/MenuScreen.tsx:63` | home.subtitle | Music library, tags, lyrics and reports | библиотека музыки, теги, тексты и отчёты | — | home subtitle |
| `views/MenuScreen.tsx:66,144` | home.find_music | Find music | Найти музыку | — | hero / empty-state action |
| `views/MenuScreen.tsx:69` | home.tidy | Tidy up | Навести порядок | — | hero action |
| `views/MenuScreen.tsx:75` | settings.browse.error (ref; generic prefix) | Error: {reason} | Ошибка: {reason} | reason (API error resolved at display; unknown verbatim) | error panel |
| `views/MenuScreen.tsx:94` | library.tabs.tracks (ref) | Tracks | Треки | — | stat chip label |
| `views/MenuScreen.tsx:95,158–159` | library.tabs.artists (ref) | Artists | Исполнители | — | chip + stats mode |
| `views/MenuScreen.tsx:96` | library.tabs.albums (ref) | Albums | Альбомы | — | stat chip label |
| `views/MenuScreen.tsx:97` | home.stats.duration | Duration | Длительность | — | stat chip label |
| `views/MenuScreen.tsx:98` | home.stats.size | Size | Размер | — | stat chip label |
| `views/MenuScreen.tsx:118` | home.recent.title | Recently added | Последние добавленные | — | section heading |
| `views/MenuScreen.tsx:140` | home.recent.empty | Nothing here yet | Пока пусто | — | EmptyState title |
| `views/MenuScreen.tsx:141` | home.recent.empty_hint | Find music on the “New” tab | Найдите музыку во вкладке «Новые» | — | EmptyState sub; stale “New” tab in current navigation: product decision, do not claim it exists |
| `views/MenuScreen.tsx:153` | home.stats.title | Statistics | Статистика | — | section heading |
| `views/MenuScreen.tsx:156` | home.stats.genres | Genres | Жанры | — | stats mode button |
| `views/MenuScreen.tsx:167,191` (configured + zero) | ytm.empty (ref) | Empty | Пусто | — | stats empty / Shazam status |
| `views/MenuScreen.tsx:178` | home.health.title | Health | Здоровье | — | health card heading |
| `views/MenuScreen.tsx:182` (issues) | quality.summary.issues (ref) | Issues: {count} | Проблем: {count} | count | health card body |
| `views/MenuScreen.tsx:182` (healthy) | home.health.ok | All good | Всё в порядке | — | health card body |
| `views/MenuScreen.tsx:191` (configured + nonzero) | home.shazam.queued | Queued: {count} | В очереди: {count} | count | Shazam card body |
| `views/MenuScreen.tsx:191` (unconfigured) | home.shazam.file_unconfigured | File not configured | Файл не настроен | — | Shazam card body |
| `views/MiscScreen.tsx:77` | jobs.download.name (ref) | Download | Скачивание | — | startOp Pipeline stage |
| `views/MiscScreen.tsx:78` | shazam.stage.metadata | Metadata | Метаданные | — | Pipeline stage |
| `views/MiscScreen.tsx:79` | shazam.stage.lyrics | Lyrics | Текст | — | Pipeline stage |
| `views/MiscScreen.tsx:80` | shazam.stage.library | To library | В библиотеку | — | Pipeline stage |
| `views/MiscScreen.tsx:93` | search.download.postprocessing | Downloaded; post-processing… | Скачано, постобработка... | — | op.set → OpPanels; shared with SearchScreen:209,229 |
| `views/MiscScreen.tsx:96` | search.metadata.fetching | Fetching metadata from sources… | Метаданные из источников... | — | op.set → OpPanels; shared SearchScreen:116 |
| `views/MiscScreen.tsx:97` | search.metadata.confirm | Fetch metadata from sources? | Загрузить метаданные из источников? | — | confirm dialog body; SearchScreen:117 |
| `views/MiscScreen.tsx:97` (okTitle) | dialogs.yes (ref) | Yes | Да | — | confirm action; SearchScreen:117 |
| `views/MiscScreen.tsx:97` (cancelTitle) | dialogs.skip | Skip | Пропустить | — | confirm action; SearchScreen:117; RecommendScreen:472 |
| `views/MiscScreen.tsx:109` | editor.metaflow.lyrics (ref) | Updating lyrics (LRCLIB)… | Обновление текста (LRCLIB)… | — | op.set → OpPanels; SearchScreen:129; preserve same key as runMetaflow stage |
| `views/MiscScreen.tsx:113` | shazam.stage.moving | Moving to library… | Перенос в библиотеку... | — | op.set → OpPanels; SearchScreen:187 |
| `views/MiscScreen.tsx:116` | shazam.stage.completed | Done: {display} | Готово: {display} | display (Shazam line verbatim) | op.set → OpPanels; SearchScreen:190 uses same pattern with destination path as param |
| `views/MiscScreen.tsx:122` | shazam.track_added | Track added to library | Трек добавлен в библиотеку | — | toast; SearchScreen:192 |
| `views/MiscScreen.tsx:132` | shazam.remove.confirm | Remove this track's line from the file? | Удалить строку с треком из файла? | — | confirm body |
| `views/MiscScreen.tsx:132` (okTitle) | settings.delete (ref) | Delete | Удалить | — | confirm action |
| `views/MiscScreen.tsx:136` | shazam.remove.count | Lines removed: {count} | Удалено строк: {count} | count | toast |
| `views/MiscScreen.tsx:146` | shazam.subtitle | Find music from a “Title — Artist” list. Matches are searched in YouTube Music and, if needed, YouTube. | Поиск музыки по списку «Название — Исполнитель». Совпадения ищутся в YouTube Music, при необходимости — на YouTube. | — | subtitle |
| `views/MiscScreen.tsx:148` | shazam.find_matches | Find matches | Найти совпадения | — | button |
| `views/MiscScreen.tsx:152` | shazam.searching_matches | Searching for matches… | Поиск совпадений… | — | Spinner text |
| `views/MiscScreen.tsx:156` | shazam.unconfigured (ref) | Shazam file is not configured | Файл Shazam не настроен | — | EmptyState title |
| `views/MiscScreen.tsx:157` | shazam.configure_hint | Specify the path to the “Title — Artist” list file in Settings | Укажите путь к файлу со списком «Название — Исполнитель» в настройках | — | EmptyState sub |
| `views/MiscScreen.tsx:160` | shazam.open_settings | Open settings | Открыть настройки | — | EmptyState button; RecommendScreen:267 |
| `views/MiscScreen.tsx:171` | shazam.file | File: {path} | Файл: {path} | path (configured file path verbatim) | scan summary |
| `views/MiscScreen.tsx:174` (title) | editor.fields.title (ref) | Title | Название | — | Table header |
| `views/MiscScreen.tsx:174` (artist) | editor.fields.artist (ref) | Artist | Исполнитель | — | Table header |
| `views/MiscScreen.tsx:174` (duration) | shazam.table.duration_short | Duration | Длит. | — | Table header; SearchScreen:459 |
| `views/MiscScreen.tsx:180` | shazam.download_hint | Downloads use the format set in Settings. You can then fetch metadata from iTunes/Deezer, add lyrics and move the track to the library. After downloading, the track's line is removed from the file. | Скачивание идёт в формате из настроек. Затем можно загрузить метаданные из iTunes/Deezer, текст и перенести трек в библиотеку. После скачивания строка трека удаляется из файла. | — | explanatory note |
| `views/MiscScreen.tsx:184` | ytm.empty (ref) | Empty | Пусто | — | no scan entries |
| `views/MiscScreen.tsx:212` | shazam.remove.title | Remove this track's line from the file | Удалить строку с треком из файла | — | row button title |
| `views/MiscScreen.tsx:213` | shazam.remove.aria | Remove line: {display} | Удалить строку: {display} | display (Shazam input verbatim) | row button aria |
| `views/MiscScreen.tsx:216` | shazam.remove.action | Remove line | Удалить строку | — | row button body |
| `views/MiscScreen.tsx:226` | ytm.download.title (ref) | Download | Скачать | — | row button; SearchScreen:360,389,479 |
| `views/MiscScreen.tsx:236` | shazam.match.score | {duration} · match {score}% | {duration} · совпадение {score}% | duration (formatted time),score (rounded provider match score) | result row |
| `views/MiscScreen.tsx:243` | shazam.match.none | No matches found on YouTube Music | Совпадений в YouTube Music не найдено | — | result row empty |
| `views/RecommendScreen.tsx:76` | recommend.apply.library | To library | В библиотеку | — | applyTexts → card button; distinct from Pipeline stage |
| `views/RecommendScreen.tsx:77` | recommend.apply.library_overlay | TO LIBRARY | В БИБЛИОТЕКУ | — | applyTexts → gesture overlay |
| `views/RecommendScreen.tsx:78` | recommend.apply.library_sent | Saved to YouTube Music library | Сохранено в библиотеку YouTube Music | — | applyTexts → toast :209 |
| `views/RecommendScreen.tsx:79` | recommend.hint.swipe_library | swipe ▶ — add to library | свайп ▶ — в библиотеку | — | applyTexts → hint :296–301 (touch) |
| `views/RecommendScreen.tsx:82` (label) | recommend.apply.like | Like | Лайк | — | applyTexts → card button |
| `views/RecommendScreen.tsx:82` (overlay) | recommend.apply.like_overlay | LIKE | ЛАЙК | — | applyTexts → gesture overlay |
| `views/RecommendScreen.tsx:82` (toastText) | recommend.apply.like_sent | Like sent to YouTube Music | Лайк отправлен в YouTube Music | — | applyTexts → toast :209 |
| `views/RecommendScreen.tsx:82` (hint) | recommend.hint.swipe_like | swipe ▶ — like | свайп ▶ — лайк | — | applyTexts → hint :296–301 (touch) |
| `views/RecommendScreen.tsx:140` | recommend.collecting_seeds | Collecting seeds… | Сбор сидов... | — | progress state → ProgressBar |
| `views/RecommendScreen.tsx:155,167` | recommend.info.summary | Library: {libraryCount, plural, one {# track} other {# tracks}} · recommendations: {total} | Библиотека: {libraryCount, plural, one {# трек} few {# трека} many {# треков} other {# трека}} · рекомендаций: {total} | libraryCount,total | SSE snapshot/final DTO → info state → DOM |
| `views/RecommendScreen.tsx:158` | jobs.recommend.seed (ref) | Processed seed {index} of {total} | Обработан сид {index} из {total} | index,total | missing backend msg fallback → progress state → ProgressBar |
| `views/RecommendScreen.tsx:212` | recommend.dislike.sent | Disliked — the radio will take this into account | Дизлайк отправлен — радио это учтёт | — | toast |
| `views/RecommendScreen.tsx:249` | recommend.title | Recommendations based on your library | Рекомендации по библиотеке | — | h1; distinct from shorter nav label |
| `views/RecommendScreen.tsx:250` | recommend.subtitle | Recommendations based on your library. Likes, dislikes and saved tracks are sent to YouTube Music | Рекомендации на основе вашей библиотеки. Лайки, дизлайки и сохранение отправляются в YouTube Music | — | subtitle |
| `views/RecommendScreen.tsx:263` | recommend.disconnected (ref) | YouTube Music is not connected | YouTube Music не подключён | — | EmptyState title |
| `views/RecommendScreen.tsx:267` | shazam.open_settings (ref) | Open settings | Открыть настройки | — | EmptyState action |
| `views/RecommendScreen.tsx:281` (streaming) | recommend.empty.streaming_title | Processing more seeds | Обрабатываем следующие сиды | — | rec-empty heading |
| `views/RecommendScreen.tsx:281` (ready) | recommend.empty.exhausted_title | No more recommendations | Рекомендаций больше нет | — | rec-empty heading |
| `views/RecommendScreen.tsx:283` (streaming) | recommend.empty.streaming_hint | Cards will appear as processing continues | карточки появятся по мере обработки | — | rec-empty sub |
| `views/RecommendScreen.tsx:283` (ready) | recommend.empty.exhausted_hint | YouTube Music radio will update later | радио YouTube Music обновится позже | — | rec-empty sub |
| `views/RecommendScreen.tsx:286` | recommend.refresh | Refresh recommendations | Обновить рекомендации | — | button |
| `views/RecommendScreen.tsx:294` | recommend.counter | {index} of {total} | {index} из {total} | index,total | rec counter |
| `views/RecommendScreen.tsx:296` (touch) | recommend.hint.swipe_dislike | ◀ swipe — dislike | ◀ свайп — дизлайк | — | touch hint first clause |
| `views/RecommendScreen.tsx:296` (pointer) | recommend.hint.arrow_dislike | ← dislike | ← дизлайк | — | mouse/keyboard hint first clause |
| `views/RecommendScreen.tsx:297–300` (pointer, library) | recommend.hint.arrow_library | → add to library | → в библиотеку | — | hint second clause; do not string-replace translated swipe phrase |
| `views/RecommendScreen.tsx:297–300` (pointer, like) | recommend.hint.arrow_like | → like | → лайк | — | hint second clause |
| `views/RecommendScreen.tsx:301` | recommend.hint.buttons | buttons below | кнопки ниже | — | hint suffix (dot separators are punctuation) |
| `views/RecommendScreen.tsx:408` | recommend.apply.library_overlay / recommend.apply.like_overlay (ref) | TO LIBRARY / LIKE | В БИБЛИОТЕКУ / ЛАЙК | — | card overlay (two independent mode branches) |
| `views/RecommendScreen.tsx:411` | recommend.dislike.overlay | DISLIKE | ДИЗЛАЙК | — | gesture overlay |
| `views/RecommendScreen.tsx:420` | recommend.cover_alt | Cover: {artist} — {title} | Обложка: {artist} — {title} | artist,title (provider metadata) | img alt; common.cover_alt only takes title; leave full data separate |
| `views/RecommendScreen.tsx:431` | recommend.seed_similar | similar to: {seed} | похоже на: {seed} | seed (backend seed, music metadata) | seed label |
| `views/RecommendScreen.tsx:439,460` | recommend.listen | Listen | Слушать | — | preview button title / body |
| `views/RecommendScreen.tsx:440` | recommend.listen_aria | Listen: {title} | Слушать: {title} | title (provider title) | preview button aria |
| `views/RecommendScreen.tsx:465` | recommend.dislike.action | Dislike | Дизлайк | — | button |
| `views/RecommendScreen.tsx:468` | recommend.apply.library / recommend.apply.like (ref) | To library / Like | В библиотеку / Лайк | — | apply button mode branches |
| `views/RecommendScreen.tsx:472` | dialogs.skip (ref) | Skip | Пропустить | — | card skip button |
| `views/SearchScreen.tsx:48,54` | jobs.download.name (ref) | Download | Скачивание | — | TRACK_STAGES/BATCH_STAGES → Pipeline |
| `views/SearchScreen.tsx:49` | shazam.stage.metadata (ref) | Metadata | Метаданные | — | TRACK_STAGES → Pipeline |
| `views/SearchScreen.tsx:50` | shazam.stage.lyrics (ref) | Lyrics | Текст | — | TRACK_STAGES → Pipeline |
| `views/SearchScreen.tsx:51,55` | shazam.stage.library (ref) | To library | В библиотеку | — | TRACK_STAGES/BATCH_STAGES → Pipeline |
| `views/SearchScreen.tsx:57` | search.note.youtube | Downloads use the format set in Settings; afterward you can fetch metadata from iTunes/Deezer. | Скачивание идёт в формате из настроек; после — предложение метаданных из iTunes/Deezer. | — | YT_NOTE → results.note :529 |
| `views/SearchScreen.tsx:58` | search.note.ytmusic | Tags come from YouTube Music (album, cover); the file uses the format set in Settings; afterward you can fetch metadata from iTunes/Deezer. | Теги — из YouTube Music (альбом, обложка), файл — в формате из настроек; после — предложение метаданных из iTunes/Deezer. | — | YTM_NOTE → results.note :529 |
| `views/SearchScreen.tsx:60` (title) | search.results.empty_title | Nothing found | Ничего не найдено | — | EMPTY_RESULTS → EmptyState |
| `views/SearchScreen.tsx:60` (sub) | search.results.empty_hint | Try another query or paste a direct link | Попробуйте другой запрос или вставьте прямую ссылку | — | EMPTY_RESULTS → EmptyState |
| `views/SearchScreen.tsx:116` | search.metadata.fetching (ref) | Fetching metadata from sources… | Метаданные из источников... | — | op.set → OpPanels |
| `views/SearchScreen.tsx:117` (body) | search.metadata.confirm (ref) | Fetch metadata from sources? | Загрузить метаданные из источников? | — | confirm dialog |
| `views/SearchScreen.tsx:117` (yes) | dialogs.yes (ref) | Yes | Да | — | confirm action |
| `views/SearchScreen.tsx:117` (skip) | dialogs.skip (ref) | Skip | Пропустить | — | confirm cancel action |
| `views/SearchScreen.tsx:129` | editor.metaflow.lyrics (ref) | Updating lyrics (LRCLIB)… | Обновление текста (LRCLIB)… | — | op.set → OpPanels |
| `views/SearchScreen.tsx:167` (fallback) | jobs.download.failed (ref) | Download error | Ошибка скачивания | — | result.items[0].error absent/!ok → error toast; preserve descriptor when item.error provided |
| `views/SearchScreen.tsx:170,171` (archive) | ytm.download.archive (ref) | Archive: {filename} | Архив: {filename} | filename (basename of server path) | op.set → OpPanels + toast |
| `views/SearchScreen.tsx:170,171` (no archive) | search.download.complete | Downloaded | Скачано | — | op.set → OpPanels + toast |
| `views/SearchScreen.tsx:187` | shazam.stage.moving (ref) | Moving to library… | Перенос в библиотеку... | — | op.set → OpPanels |
| `views/SearchScreen.tsx:190` | shazam.stage.completed (ref) | Done: {display} | Готово: {display} | display (destination path verbatim) | op.set → OpPanels |
| `views/SearchScreen.tsx:192` | shazam.track_added (ref) | Track added to library | Трек добавлен в библиотеку | — | toast |
| `views/SearchScreen.tsx:209,229` | search.download.postprocessing (ref) | Downloaded; post-processing… | Скачано, постобработка... | — | op.set → OpPanels |
| `views/SearchScreen.tsx:247` | search.batch.title | Batch: {count, plural, one {# track} other {# tracks}} | Пакет: {count, plural, one {# трек} few {# трека} many {# треков} other {# трека}} | count | startJob title → DownloadsDock; store descriptor |
| `views/SearchScreen.tsx:250,251` | search.batch.summary | Downloaded: {downloaded}, errors: {errors} | Скачано: {downloaded}, ошибок {errors} | downloaded,errors | op.set → OpPanels + toast |
| `views/SearchScreen.tsx:273` | search.results.ytm_heading | Results (YouTube Music): {query} | Результаты (YouTube Music): {query} | query (user input verbatim) | applyItems → results.heading → h2 :510 |
| `views/SearchScreen.tsx:277` | search.results.heading | Results: {query} | Результаты: {query} | query (user input verbatim) | applyItems → results.heading → h2 :510 |
| `views/SearchScreen.tsx:357,386` | ytm.download.track_aria (ref) | Download: {title} | Скачать: {title} | title (provider title or URL/video ID) | result button aria (YT + YTM) |
| `views/SearchScreen.tsx:360,389,479` | ytm.download.title (ref) | Download | Скачать | — | result and playlist buttons |
| `views/SearchScreen.tsx:381` | ytm.badge.in_library_aria (ref; capitalization differs) | In library | В библиотеке | — | YTM result badge |
| `views/SearchScreen.tsx:399` | search.title | Search and download | Поиск и скачивание | — | h1 |
| `views/SearchScreen.tsx:400` | search.subtitle | Search for music on YouTube or YouTube Music and download it in the selected format | Ищите музыку на YouTube или YouTube Music и скачивайте её в выбранном формате | — | subtitle |
| `views/SearchScreen.tsx:408` | search.engine_aria | Search source | Источник поиска | — | SegControl aria; provider option names :403–404 verbatim |
| `views/SearchScreen.tsx:410,417` | search.query.label | YouTube query or URL | Запрос на YouTube или URL | — | visually-hidden label and input aria |
| `views/SearchScreen.tsx:416` | search.query.placeholder (ref) | YouTube query or URL (video / playlist / audio) | Запрос на YouTube или URL (видео / плейлист / аудио) | — | input placeholder |
| `views/SearchScreen.tsx:426` (busy) | search.searching | Searching… | Поиск… | — | submit button busy branch |
| `views/SearchScreen.tsx:426` (idle) | nav.search (ref) | Search | Поиск | — | submit button idle branch |
| `views/SearchScreen.tsx:441` | search.processing | Processing… | Обработка... | — | URL-loading Spinner |
| `views/SearchScreen.tsx:449` | search.failed | Search failed: {reason} | Поиск не удался: {reason} | reason (known API descriptor resolved at UI boundary; unknown verbatim) | error panel |
| `views/SearchScreen.tsx:451` | search.retry | Try again | Попробовать снова | — | error retry button |
| `views/SearchScreen.tsx:458` | search.playlist.count | Playlist ({count, plural, one {# track} other {# tracks}}) | Плейлист ({count, plural, one {# трек} few {# трека} many {# треков} other {# трека}}) | count | playlist heading |
| `views/SearchScreen.tsx:459` (title) | editor.fields.title (ref) | Title | Название | — | playlist Table header |
| `views/SearchScreen.tsx:459` (channel) | search.table.channel | Channel | Канал | — | playlist Table header |
| `views/SearchScreen.tsx:459` (duration) | shazam.table.duration_short (ref) | Duration | Длит. | — | playlist Table header |
| `views/SearchScreen.tsx:465` | quality.selection.track_aria (ref) | Select: {name} | Выбрать: {name} | name (provider title or URL verbatim) | playlist checkbox aria |
| `views/SearchScreen.tsx:496` | search.selection.all | All | Все | — | playlist select button |
| `views/SearchScreen.tsx:499` | search.selection.none | None | Ничего | — | playlist deselect button |
| `views/SearchScreen.tsx:502` | search.selection.download | Download selected ({count}) | Скачать выбранные ({count}) | count | playlist batch button |
| `views/SearchScreen.tsx:526` | search.results.more | Show 10 more ({count} shown) | Показать ещё 10 (показано {count}) | count | load-more button; fixed page increment 10 |

**Six-view exclusions and hazards (each exclusion is bounded by these source locations):** `DiscoverScreen.tsx:11` “Shazam” is a service name rendered verbatim; `:16–19,40,49–53,60–62` hash/route IDs, CSS and tab discriminators are not prose. `LibraryScreen.tsx:42–101,108–114,133–139,169–181,205–224,273–277,342–345,393–396,450–454,479–484,700–719,733–735,833–876` view/filter/sort/density IDs, paths, tag values, artist/album/genre option values, provider titles and API paths are data; default prompt value `Various Artists` at :445 is **user-editable tag data**, not a UI label: retain it consistently across locales to avoid silently changing a written tag. `:288–300` from/to paths are displayed verbatim; only the count sentence and explanation are owned. `:374` file label comes from the dedup API, not a key. `:602,261,317` error/progress are API/job messages (structured or legacy); `:117,268,277,323,398,460` stringify API/OS errors today — do not translate unknown strings or freeze known descriptors in state/toast. `:267,322` empty operation string clears a panel, not visible copy. `:63–71,585–590,640–648` SVG/CSS/ID HTML are technical. `:751` × is a symbol. `MenuScreen.tsx:10–15,59–61` ASCII logo and product name are branding, not translatable; `:32–38,100–101,105–113,120–133,165,179,188` genre/artist/track/album metadata, file extension, scores, counts, percentage and icons are data; `fmtSize` and `fmtDate` require active-locale Intl formatting per :638–641, not new keys. `:51,75` API error is not an owned frontend reason. `MiscScreen.tsx:15–37,54,58–64,86–92,99–101,118,127,135,139,145,166,171,174,208,223–236` Shazam input/display, provider hit titles/uploader/URL, configured path, service names and backend errors/progress are data/transport; table empty headers and icons are structural, not prose. The Russian substring test at :59 against `укажите путь` is **branch control coupled to legacy prose**: replace with stable `jobs.shazam.file_missing`/`api` code when migration occurs, while still supporting legacy string errors; it is not a translatable UI phrase. The `msg === "Обновление текста (LRCLIB)..."` check at :101 and `SearchScreen.tsx:121` likewise couples pipeline state to localized text from runMetaflow: use a stage ID/event, not comparison with a translation. `RecommendScreen.tsx:32–69,96–125,192–241,330–379,386–405,414–429` transliteration/dedup regex, event names, CSS/geometry, input data, metadata, URLs and decorative glyphs are not catalog copy. `:149,158,172,216,245,455` backend job/error strings should be descriptors or legacy readable text; the Russian `error.includes("Подключите YouTube Music")` at :245 is control logic coupled to backend prose: use stable `api.errors.ytm_connection_required` code for classification; do not translate the match string. `:92,105` applyTexts output is currently stored in state, so switching locale must derive labels from mode ID instead of caching translations. `:296–301` avoid `.replace("свайп ▶", "→")` on localized strings: select mode and pointer-specific keys explicitly. `SearchScreen.tsx:25–46,71–86,90–97,99–110,137–164,191,207,224–227,258–305,308–340,343–395,403–405,460–490` provider labels, user query/URL, job result paths, video IDs, tags/metadata, format settings, protocol fields, empty header cells, route IDs and lookup flags remain data. `:75,273,277,291–305` results.heading and note are stored pretranslated; store keys + query and render on locale switch. `:77,282,449` search errors are API/OS strings or descriptors, not new reason translations; `:167` must not call `new Error(item.error)` on a structured result error (otherwise `[object Object]`), use descriptor-aware rendering; `:164,207,227,247` startJob title includes raw music title/URL or owned batch phrase, respectively. `:60` ∅, `:348,369` —, `:459` #, `:433` path arrow are symbols/data. Source comments, conditional statuses (`done`, `active`, `error`), CSS, key names and internal query words are not UI messages. `MenuScreen.tsx:141` references a “New” tab absent from `DiscoverScreen.tsx:9–12`; confirm desired destination/copy before implementation.

**Audit boundary:** This continuation closes occurrence classification for the six named views only, **not** nested library modules or Task 1 as a whole. Keep backend/UI error objects and job progress as descriptors until rendering; a literal captured into `op.set`, `setProgress`, `setInfo`, `setResults`, or `applyTexts` will not update on a language switch unless the store changes shape. Baseline and earlier audit keys remain authoritative where marked `ref`; exact-source differences (e.g. `quality.selection.required`, `quality.selection.clear`, `ytm.empty`) need a single agreed shared wording, not parallel keys. No tests or application code were modified.

### Continuation: ten nested library/settings files (2026-10-14 occurrence audit)

Only the ten paths named below are reconciled here; paths are relative to `frontend/src/`, line numbers refer to the inspected unmodified sources. Every table row is one distinct renderable message/conditional branch (multiple locations = identical reuse). `ref` points to an already mapped key with the canonical wording; spelling differences in current source are not grounds for duplicate keys. `—` means no ICU params. Runtime metadata and provider/OS/API error text included as parameters remain verbatim, not catalog entries. Counts of rows by file are in the Task 1 report; earlier pending snapshots remain historical. Store message IDs + params, not rendered strings, in `onCount`, operation/progress state, dialog and account-option state where locale switching must update them.

| Source occurrence | Stable key | EN | RU | ICU params | Producer → render consumer |
|---|---|---|---|---|---|
| `views/library/AlbumsTab.tsx:119` (filtered) | library.albums.shown | Showing {shown} of {total} albums | Показано {shown} из {total} альбомов | shown,total | base → onCount → LibraryScreen count |
| `views/library/AlbumsTab.tsx:120` (unfiltered) | library.albums.count | {count, plural, one {# album} other {# albums}} | {count, plural, one {# альбом} few {# альбома} many {# альбомов} other {# альбома}} | count | base → onCount |
| `views/library/AlbumsTab.tsx:124` | ytm.tracks.count (ref) | {count, plural, one {# track} other {# tracks}} | {count, plural, one {# трек} few {# трека} many {# треков} other {# трека}} | count | open album → onCount |
| `views/library/AlbumsTab.tsx:129`, `views/library/ArtistsTab.tsx:94`, `views/library/TracksTab.tsx:115` | library.cloud.more | · {count} more on YouTube Music | · ещё {count} на YT Music | count | local count + cloud span → onCount; prefix punctuation belongs to this key |
| `views/library/AlbumsTab.tsx:133`, `views/library/ArtistsTab.tsx:98`, `views/library/TracksTab.tsx:119` | library.cloud.only | {count} on YouTube Music | {count} на YT Music | count | cloud-only count → onCount; do not use suffix key |
| `views/library/AlbumsTab.tsx:156`, `views/library/ArtistsTab.tsx:107`, `views/library/TracksTab.tsx:202` | library.filters.no_results | Nothing matches the filters | Ничего не найдено по фильтру | — | filtered empty div |
| `views/library/AlbumsTab.tsx:159`, `views/library/ArtistsTab.tsx:110`, `views/library/TracksTab.tsx:205` | library.empty (ref) | Library is empty | Библиотека пуста | — | EmptyState title |
| `views/library/AlbumsTab.tsx:160`, `views/library/ArtistsTab.tsx:111`, `views/library/TracksTab.tsx:206` | library.empty_hint | Find and download music; files will appear here | Найдите музыку и скачайте — файлы появятся здесь | — | EmptyState sub |
| `views/library/AlbumsTab.tsx:163`, `views/library/ArtistsTab.tsx:114`, `views/library/TracksTab.tsx:209` | home.find_music (ref) | Find music | Найти музыку | — | EmptyState action |
| `views/library/ArtistsTab.tsx:93,100` | library.artists.count | {count, plural, one {# artist} other {# artists}} | {count, plural, one {# исполнитель} few {# исполнителя} many {# исполнителей} other {# исполнителя}} | count | shown → onCount; both local+cloud and local-only branches |
| `views/library/PlaylistsTab.tsx:38` | library.playlists.count | {count, plural, one {# playlist} other {# playlists}} | {count, plural, one {# плейлист} few {# плейлиста} many {# плейлистов} other {# плейлиста}} | count | shown → onCount |
| `views/library/PlaylistsTab.tsx:48` | library.playlists.disconnected | YouTube Music is not connected: connect it in Settings | YouTube Music не подключён: подключите в «Настройках» | — | disconnected empty state; distinct from `recommend.disconnected` (action included) |
| `views/library/PlaylistsTab.tsx:49` | library.playlists.none | No saved playlists | Плейлистов не сохранено | — | connected empty state |
| `views/library/TracksTab.tsx:108` (filtered) | library.tracks.shown | Showing {shown} of {total} | Показано {shown} из {total} | shown,total | baseCount → onCount; current phrase omits noun, preserve semantics |
| `views/library/TracksTab.tsx:109` (unfiltered) | ytm.tracks.count (ref) | {count, plural, one {# track} other {# tracks}} | {count, plural, one {# трек} few {# трека} many {# треков} other {# трека}} | count | baseCount → onCount |
| `views/library/TracksTab.tsx:259` | library.detail.heading | Information | Информация | — | detail pane h3 |
| `views/library/TracksTab.tsx:260` | library.detail.choose_track | Select a track | Выберите трек | — | detail pane empty prompt |
| `views/library/Cards.tsx:52` | library.card.open_track_aria | Open details: {name} | Открыть детали: {name} | name (metadata or filename) | TrackCard button aria |
| `views/library/Cards.tsx:60` | quality.selection.track_aria (ref) | Select: {name} | Выбрать: {name} | name (metadata or filename) | TrackCard checkbox aria |
| `views/library/Cards.tsx:70`, `views/library/Inbox.tsx:129`, `views/library/trackDetail.tsx:30` | common.cover_alt (ref) | Cover: {title} | Обложка: {title} | title (precomposed artist/title from tags or filename; retain data verbatim) | local image alt |
| `views/library/Cards.tsx:75,92` | library.compress.needed_short | compress | сжать | — | TrackCard cover badge + row badge |
| `views/library/Cards.tsx:76,93,118` | library.ytm.liked_title | Liked on YouTube Music | Лайк в YouTube Music | — | local/YT card badge title |
| `views/library/Cards.tsx:85` | editor.fields.track_number (ref) | Track number | № трека | — | num title; source has «Номер трека» |
| `views/library/Cards.tsx:88` | library.card.format_title | Format | Формат | — | format title |
| `views/library/Cards.tsx:89` | library.card.bitrate_title | Bitrate | Битрейт | — | bitrate title |
| `views/library/Cards.tsx:114` | library.card.ytm_aria | YouTube Music: {name} | YouTube Music: {name} | name (provider track name) | YtTrackCard aria |
| `views/library/Cards.tsx:115` | library.card.clip_title | Video clip on YouTube Music | Клип на YouTube Music | — | cover title if clip; `isClip` flag technical |
| `views/library/Cards.tsx:116` | ytm.cover_alt (ref) | Cover: {title} | Обложка: {title} | title (provider name) | YtTrackCard img alt |
| `views/library/Cards.tsx:127` (title) | ytm.radio.title (ref) | Similar (radio) | Похожие (радио) | — | radio button title |
| `views/library/Cards.tsx:127` (aria) | ytm.radio.track_aria (ref) | Similar: {title} | Похожие: {title} | title (provider title/video ID) | radio button aria |
| `views/library/Cards.tsx:128` | ytm.radio.button (ref) | Radio | Радио | — | radio button body |
| `views/library/Cards.tsx:130` (title) | ytm.download.title (ref) | Download | Скачать | — | download button title |
| `views/library/Cards.tsx:130` (aria) | ytm.download.track_aria (ref) | Download: {title} | Скачать: {title} | title (provider title/video ID) | download button aria |
| `views/library/Cards.tsx:147` (artist present) | library.card.open_album_artist_aria | Open album: {title} — {artist} ({have} of {total} tracks) | Открыть альбом: {title} — {artist} ({have} из {total} тр.) | title,artist,have,total | LocalAlbumCard aria |
| `views/library/Cards.tsx:147` (no artist) | library.card.open_album_aria | Open album: {title} ({have} of {total} tracks) | Открыть альбом: {title} ({have} из {total} тр.) | title,have,total | LocalAlbumCard aria |
| `views/library/Cards.tsx:153` | library.card.album_cover_alt | Album cover: {name} | Обложка альбома: {name} | name (artist/title tag composition) | LocalAlbumCard img alt; reuse `ytm.album.cover_alt` only if matching title-only semantics; here artist is included |
| `views/library/Cards.tsx:216` | library.card.artist_aria | Artist: {name} ({count} tracks) | Исполнитель: {name} ({count} тр.) | name (tag artist),count | LocalArtistCard aria; abbreviation from source, no plural helper needed if RU short form stays |
| `views/library/Cards.tsx:222` | ytm.cover_alt (ref) | Cover: {title} | Обложка: {title} | title (artist tag) | LocalArtistCard img alt |
| `views/library/Cards.tsx:226` | ytm.artist.local_count (ref) | {count} in library | {count} в библиотеке | count | LocalArtistCard badge |
| `views/library/Cards.tsx:230` | library.artist.files | {count, plural, one {# file} other {# files}} | {count, plural, one {# файл} few {# файла} many {# файлов} other {# файла}} | count | LocalArtistCard sub; replace файл(ов) |
| `views/library/Inbox.tsx:29` | library.inbox.moved_to | Moved to: {path} | Перенесено: {path} | path (API destination verbatim) | moveInbox → toast |
| `views/library/Inbox.tsx:39` | library.inbox.move_confirm | Move {count, plural, one {# file} other {# files}} from Inbox into Artist/Album folders using tags? | Перенести {count, plural, one {# файл} few {# файла} many {# файлов} other {# файла}} из Inbox в Artist/Album по тегам? | count | moveAllInbox → confirm body |
| `views/library/Inbox.tsx:40` | library.inbox.move_action | Move | Перенести | — | confirm okTitle |
| `views/library/Inbox.tsx:47` | library.inbox.item_progress | {index}/{total}: {title} | {index}/{total}: {title} | index,total,title (tag or filename) | moveAllInbox → op.set → OpPanels; numeric punctuation plus data, explicit progress template |
| `views/library/Inbox.tsx:55` (no failures) | library.inbox.move_summary | Moved: {count} | Перенесено: {count} | count | op.set → OpPanels |
| `views/library/Inbox.tsx:55` (failures) | library.inbox.move_summary_errors | Moved: {count}, errors: {failed} | Перенесено: {count}, ошибок: {failed} | count,failed | op.set → OpPanels; no locale-fixed suffix concatenation |
| `views/library/Inbox.tsx:62` | library.inbox.delete_all_title | Delete everything from Inbox | Удалить всё из Inbox | — | deleteAllInbox → DialogProvider title |
| `views/library/Inbox.tsx:65` | library.inbox.delete_confirm | Permanently delete {count, plural, one {# file} other {# files}}? | Удалить безвозвратно {count, plural, one {# файл} few {# файла} many {# файлов} other {# файла}}? | count | dialog body; current source count without noun |
| `views/library/Inbox.tsx:67` | library.inbox.delete_warning | Files will be erased from disk and cannot be restored | Файлы стираются с диска — восстановить нельзя | — | dialog warning |
| `views/library/Inbox.tsx:79` | dialogs.cancel (ref) | Cancel | Отмена | — | dialog action |
| `views/library/Inbox.tsx:80,117` | library.inbox.delete_all | Delete all | Удалить все | — | dialog destructive action + toolbar button |
| `views/library/Inbox.tsx:88` | library.inbox.delete_item_progress | {index}/{total} | {index}/{total} | index,total | deleteAllInbox → op.set → OpPanels; numbers only, no translatable prose but keep structured progress contract |
| `views/library/Inbox.tsx:96` (no failures) | library.inbox.delete_summary | Deleted: {count} | Удалено: {count} | count | op.set → OpPanels |
| `views/library/Inbox.tsx:96` (failures) | library.inbox.delete_summary_errors | Deleted: {count}, errors: {failed} | Удалено: {count}, ошибок: {failed} | count,failed | op.set → OpPanels |
| `views/library/Inbox.tsx:107` | library.inbox.move_all_aria | Move all Inbox files to the library ({count}) | Перенести все файлы Inbox в библиотеку ({count}) | count | toolbar aria |
| `views/library/Inbox.tsx:109` | library.inbox.move_all | Move all ({count}) | Перенести все ({count}) | count | toolbar button |
| `views/library/Inbox.tsx:115` | library.inbox.delete_all_aria | Delete all Inbox files ({count}) | Удалить все файлы Inbox ({count}) | count | toolbar aria |
| `views/library/Inbox.tsx:120` | library.inbox.heading | Inbox — files outside folders ({count}) | Inbox — файлы вне папок ({count}) | count | CollapsibleGroup title |
| `views/library/Inbox.tsx:138` | library.selection.tags (ref) | Tags | Теги | — | card action |
| `views/library/Inbox.tsx:148`, `views/library/trackDetail.tsx:65` | library.track.meta_action | Metadata | Мета | — | card/detail action |
| `views/library/Inbox.tsx:150`, `views/library/trackDetail.tsx:68` | quality.lyrics.singular (ref) | Lyrics | Текст | — | card/detail action |
| `views/library/Inbox.tsx:151`, `views/settings/YtmCard.tsx:342` | recommend.apply.library (ref) | To library | В библиотеку | — | Inbox card move / settings feedback option; different side effect, same action wording |
| `views/library/Inbox.tsx:152` | settings.delete (ref) | Delete | Удалить | — | Inbox card action |
| `views/library/albumDetail.tsx:84` | editor.fields.album (ref) | Album | Альбом | — | section aria |
| `views/library/albumDetail.tsx:85` | ytm.back (ref) | ← Back | ← Назад | — | back button |
| `views/library/albumDetail.tsx:87` | ytm.album.cover_alt (ref) | Album cover: {title} | Обложка альбома: {title} | title (tag album) | header img alt |
| `views/library/albumDetail.tsx:98` | library.album.fetch_tags_title | Fill all album tags from one source | Заполнить теги всего альбома из одного источника | — | button title |
| `views/library/albumDetail.tsx:101` | library.album.choose_tags | Choose tags for album | Выбрать теги для альбома | — | button |
| `views/library/albumDetail.tsx:106` | library.album.common_tags_title | Set shared tags (artist, album, year and others) for all tracks | Задать общие теги (исполнитель, альбом, год и другие) сразу для всех треков | — | button title |
| `views/library/albumDetail.tsx:109,201` | library.album.common_tags | Shared album tags | Общие теги альбома | — | button/dialog title |
| `views/library/albumDetail.tsx:114` | library.album.choose_cover_title | Choose a source cover for all album tracks | Выбрать обложку из источников для всех треков альбома | — | button title |
| `views/library/albumDetail.tsx:117,354` | library.album.cover_dialog | Album cover | Обложка для альбома | — | button/dialog title |
| `views/library/albumDetail.tsx:124` | home.stats.genres (ref) | Genres | Жанры | — | nfo styles aria |
| `views/library/albumDetail.tsx:135` | library.album.missing_count | Missing from local library ({count}) | Не хватает в локальной библиотеке ({count}) | count | missing section heading |
| `views/library/albumDetail.tsx:139` | library.album.download_missing_title | Download all missing tracks | Скачать все недостающие треки | — | button title |
| `views/library/albumDetail.tsx:141,149` | ytm.download.album_group (ref) | Album: {name} | Альбом: {name} | name (provider album title) | ytmDownload job title → dock; defer resolution |
| `views/library/albumDetail.tsx:144` | library.album.download_all | Download all ({count}) | Скачать все ({count}) | count | button |
| `views/library/albumDetail.tsx:153` | library.album.tracks_aria | Album tracks | Треки альбома | — | section aria |
| `views/library/albumDetail.tsx:155` | editor.batch.tracks_heading (ref) | Tracks ({count}) | Треки ({count}) | count | heading |
| `views/library/albumDetail.tsx:162` (selected) | library.selection.deselect_all (ref) | Deselect all | Снять все | — | button |
| `views/library/albumDetail.tsx:162` (not selected) | quality.selection.select_all (ref) | Select all ({count}) | Выбрать все ({count}) | count | button |
| `views/library/albumDetail.tsx:192` | library.selection.saved (ref) | Saved: {count, plural, one {# track} other {# tracks}} | Сохранено: {count, plural, one {# трек} few {# трека} many {# треков} other {# трека}} | count | toast; source has extra noun |
| `views/library/albumDetail.tsx:206,357` | library.album.apply | Apply | Применить | — | two dialog actions |
| `views/library/albumDetail.tsx:207,358` | dialogs.cancel (ref) | Cancel | Отмена | — | two dialog actions |
| `views/library/albumDetail.tsx:247` | editor.validation.check_field (ref) | Check “{fieldLabel}”: {reason} | Проверьте поле «{fieldLabel}»: {reason} | fieldLabel (resolved field ID),reason (validateTagField key) | toast; never store raw label as key |
| `views/library/albumDetail.tsx:252` | library.album.one_field_required | Fill in at least one field | Заполните хотя бы одно поле | — | warning toast |
| `views/library/albumDetail.tsx:258,421` | editor.batch.applying (ref) | Applying {index}/{total}… | Применяю {index}/{total}… | index,total | state progress → ProgressBar (two dialogs) |
| `views/library/albumDetail.tsx:267` (no failure) | library.album.tags_applied | Tags applied: {count, plural, one {# track} other {# tracks}} | Теги применены: {count, plural, one {# трек} few {# трека} many {# треков} other {# трека}} | count | toast |
| `views/library/albumDetail.tsx:267` (failure) | library.album.tags_applied_errors | Tags applied: {count, plural, one {# track} other {# tracks}}, errors: {failed} | Теги применены: {count, plural, one {# трек} few {# трека} many {# треков} other {# трека}}, ошибок: {failed} | count,failed | warning toast |
| `views/library/albumDetail.tsx:279–281` | library.album.common_tags_hint | Filled fields will be applied to all {count, plural, one {# track} other {# tracks}} in “{album}”. Empty fields are not changed; titles, track numbers and covers are unaffected. | Заполненные поля применятся ко всем {count, plural, one {# треку} few {# трекам} many {# трекам} other {# треку}} альбома «{album}». Пустые поля не изменяются; названия, номера треков и обложки не затрагиваются. | count,album (tag) | dialog hint; combine all three fragments into one translatable message |
| `views/library/albumDetail.tsx:286` (mixed) | library.album.values_mixed_placeholder | Different values in album | в альбоме: разные значения | — | input placeholder |
| `views/library/albumDetail.tsx:286` (present) | library.album.current_placeholder | Current: {value} | сейчас: {value} | value (tag) | input placeholder |
| `views/library/albumDetail.tsx:286` (empty) | library.album.unset_placeholder | Not set | не задано | — | input placeholder |
| `views/library/albumDetail.tsx:307` | library.album.values_mixed_title | Album tracks have different values in this field | У треков альбома в этом поле разные значения | — | disabled chip title |
| `views/library/albumDetail.tsx:308` | library.album.values_mixed_aria | Album tracks have different values for “{fieldLabel}” | У поля «{fieldLabel}» в альбоме разные значения | fieldLabel (localized field ID) | disabled chip aria |
| `views/library/albumDetail.tsx:310` | library.album.values_mixed | Different values | Разные значения | — | disabled chip body |
| `views/library/albumDetail.tsx:317` | library.album.use_current_title | Use the current album value | Подставить текущее значение альбома | — | chip title |
| `views/library/albumDetail.tsx:318` | library.album.use_current_aria | Use current value for “{fieldLabel}” | Подставить текущее значение поля «{fieldLabel}» | fieldLabel (localized field ID) | chip aria |
| `views/library/albumDetail.tsx:387` | library.album.track_file_source | Track file | Файл трека | — | cover candidate source state → source label/aria/alt at :479,492; provider sources verbatim |
| `views/library/albumDetail.tsx:415` | library.album.choose_cover_first | Select a cover first | Сначала выберите обложку | — | warning toast |
| `views/library/albumDetail.tsx:437` (no failure) | library.album.cover_applied | Cover applied: {count, plural, one {# track} other {# tracks}} | Обложка применена: {count, plural, one {# трек} few {# трека} many {# треков} other {# трека}} | count | toast |
| `views/library/albumDetail.tsx:437` (failure) | library.album.cover_applied_errors | Cover applied: {count, plural, one {# track} other {# tracks}}, errors: {failed} | Обложка применена: {count, plural, one {# трек} few {# трека} many {# треков} other {# трека}}, ошибок: {failed} | count,failed | warning toast |
| `views/library/albumDetail.tsx:447` | library.album.cover_type | Choose a JPEG or PNG file | Выберите файл JPEG или PNG | — | warning toast |
| `views/library/albumDetail.tsx:458` | library.album.cover_read_failed | Could not read the cover file | Не удалось прочитать файл обложки | — | error toast |
| `views/library/albumDetail.tsx:467` | library.album.cover_hint | Cover will be applied to all tracks of “{album}”. | Обложка применится ко всем трекам альбома «{album}». | album (tag) | dialog hint |
| `views/library/albumDetail.tsx:468` | editor.sources.unavailable (ref) | Sources unavailable | Источники недоступны | — | cover picker error |
| `views/library/albumDetail.tsx:469` | library.album.searching_covers | Searching sources for covers… | Ищу обложки в источниках… | — | cover picker loading |
| `views/library/albumDetail.tsx:479` | library.album.select_cover_aria | Select cover: {source} | Выбрать обложку: {source} | source (localized `library.album.track_file_source` or provider name) | candidate aria |
| `views/library/albumDetail.tsx:492` | library.album.cover_from_alt | Album cover from {source} | Обложка альбома из {source} | source (localized own label or provider name) | candidate img alt |
| `views/library/albumDetail.tsx:512` | library.album.upload_cover_aria | Upload a cover file | Загрузить файл обложки | — | file input aria |
| `views/library/albumDetail.tsx:518` | library.album.uploaded_cover_alt | Uploaded cover: {filename} | Загруженная обложка: {filename} | filename | uploaded img alt |
| `views/library/albumDetail.tsx:524` | library.album.upload_cover | Upload cover | Загрузить обложку | — | upload tile heading |
| `views/library/albumDetail.tsx:525` | library.album.drop_or_click | Drop a file or click | Перетащите файл или нажмите | — | upload tile hint |
| `views/library/libUtils.ts:146–154` | editor.fields.artist / album / album_artist / year / genre / isrc / composer / publisher / comment (ref, one per field) | Artist / Album / Album artist / Year / Genre / ISRC / Composer / Publisher / Label / Comment | Исполнитель / Альбом / Исполнитель альбома / Год / Жанр / ISRC / Композитор / Издатель / Лейбл / Комментарий | — | ALBUM_COMMON_TAG_FIELDS → albumDetail:235 validation, :289 labels and :308/:318 aria; resolve IDs at render, baseline spelling prevails |
| `views/library/libUtils.ts:173` (needs compression) | library.compress.needed | Needed ({before} → {after}) | нужно ({before} → {after}) | before,after (fmtSize in active locale) | compressLabel → trackDetail field value |
| `views/library/libUtils.ts:173` (no compression) | library.compress.ok | OK | ок | — | compressLabel → trackDetail field value |
| `views/library/trackDetail.tsx:30` | common.cover_alt (ref) | Cover: {title} | Обложка: {title} | title (tag/filename) | TrackDetailBody img alt |
| `views/library/trackDetail.tsx:36–40` | editor.fields.title / artist / album / year / genre (ref; one per field) | Title / Artist / Album / Year / Genre | Название / Исполнитель / Альбом / Год / Жанр | — | fields → TrackDetailBody labels |
| `views/library/trackDetail.tsx:41–42` | editor.fields.track_number / editor.fields.disc_number (ref; two fields) | Track number / Disc number | № трека / № диска | — | fields → detail labels; original order differs |
| `views/library/trackDetail.tsx:43` | home.stats.duration (ref) | Duration | Длительность | — | detail label |
| `views/library/trackDetail.tsx:44` (label) | library.card.bitrate_title (ref) | Bitrate | Битрейт | — | detail label |
| `views/library/trackDetail.tsx:44` (value) | library.track.bitrate_value | {rate} kbps | {rate} кбит/с | rate | detail value; numeric unit, may use locale-aware unit formatter rather than catalog |
| `views/library/trackDetail.tsx:45` | home.stats.size (ref) | Size | Размер | — | detail label; value via fmtSize Intl |
| `views/library/trackDetail.tsx:46` | library.track.compression_label | Compression | Сжатие | — | detail label; value `compressLabel` keyed above |
| `views/library/trackDetail.tsx:61` | library.track.edit_tags | Edit tags | Редактировать теги | — | detail action |
| `views/library/trackDetail.tsx:65,68` | library.track.meta_action / quality.lyrics.singular (ref; two messages) | Metadata / Lyrics | Мета / Текст | — | detail actions |
| `views/library/trackDetail.tsx:73` | library.compress.action (ref) | Compress | Сжать | — | action |
| `views/library/trackDetail.tsx:83` | library.track.delete_action | Delete track | Удалить трек | — | action |
| `views/library/trackDetail.tsx:104,117` | dialogs.close (ref) | Close | Закрыть | — | detail/lyrics dialog action |
| `views/library/trackDetail.tsx:114` (no lyrics) | library.track.no_lyrics | No lyrics | Нет текста | — | lyrics dialog pre fallback |
| `views/library/trackDetail.tsx:116` | library.track.update_lyrics_action | Update (LRCLIB) | Обновить (LRCLIB) | — | lyrics dialog action |
| `views/library/trackDetail.tsx:122,123` | quality.lyrics.updated / quality.lyrics.not_found (ref; two outcomes) | Lyrics updated / Lyrics not found | Текст обновлён / Текст не найден | — | lyrics update → success/warning toast |
| `views/library/trackDetail.tsx:148` | library.track.delete_confirm | Permanently delete this track? | Удалить трек безвозвратно? | — | confirm body |
| `views/library/trackDetail.tsx:148` (okTitle) | settings.delete (ref) | Delete | Удалить | — | confirm action |
| `views/library/trackDetail.tsx:152` | library.track.deleted | Track deleted | Трек удалён | — | toast |
| `views/library/trackDetail.tsx:173` (audio result) | library.compress.result | {label}: done {done}, skipped {skipped} | {label}: сделано {done}, пропущено {skipped} | label (resolved `jobs.compress.audio_result`),done,skipped | job result → op.set → OpPanels; retain descriptor through display |
| `views/library/trackDetail.tsx:173` (cover result, not reached with `mode: audio`) | library.compress.result (ref) | {label}: done {done}, skipped {skipped} | {label}: сделано {done}, пропущено {skipped} | label (resolved `jobs.compress.cover_result`),done,skipped | same template if mode extended; not another source phrase |
| `views/settings/YtmCard.tsx:102` (missing account name) | settings.ytm.account.unnamed | unnamed | без имени | — | account option label → select; keep candidate IDs raw |
| `views/settings/YtmCard.tsx:104` (page ID) | settings.ytm.account.page | (channel) | (страничный) | — | option label conditional; prefer composed select/ICU for whole option |
| `views/settings/YtmCard.tsx:105` | settings.ytm.account.option | {name}{handle}{page} — {likes} likes, authuser {authuser} | {name}{handle}{page} — {likes} лайков, authuser {authuser} | name (provider or fallback),handle (optional provider),page (localized marker),likes,authuser | candidate mapping → accounts state → option; do not pluralize preformatted strings; prefer ICU `{likes, plural, ...}` if integer |
| `views/settings/YtmCard.tsx:111` (candidates) | settings.ytm.account.found | Accounts found: {count} | Найдено аккаунтов: {count} | count | findAccounts → accountsOut → ProgressBar |
| `views/settings/YtmCard.tsx:111` (none) | settings.ytm.account.unrecognized | Accounts not recognized: refresh music.youtube.com using the desired account | Аккаунты не распознаны: обновите music.youtube.com под нужной учёткой | — | accountsOut → ProgressBar |
| `views/settings/YtmCard.tsx:113` | settings.ytm.account.not_found | No accounts found | Аккаунты не найдены | — | toast error |
| `views/settings/YtmCard.tsx:148` | settings.ytm.account.unknown | unknown account | неизвестный аккаунт | — | extract fallback name → progress/toast |
| `views/settings/YtmCard.tsx:149` | settings.ytm.extract.done | Done: {account} (+{authuser}) | Готово: {account} (+{authuser}) | account (provider name or localized fallback),authuser | extractOut → ProgressBar |
| `views/settings/YtmCard.tsx:150` | settings.ytm.extract.saved | Cookies saved: {account} | Куки сохранены: {account} | account (same source) | toast |
| `views/settings/YtmCard.tsx:162` | settings.ytm.auth.delete_confirm | Delete YouTube Music authorization? Account likes and albums will become unavailable again. | Удалить авторизацию YouTube Music? Лайки и альбомы аккаунта снова будут недоступны. | — | confirm dialog |
| `views/settings/YtmCard.tsx:163,235,388,455` | settings.delete (ref) | Delete | Удалить | — | confirm and buttons |
| `views/settings/YtmCard.tsx:168` | settings.ytm.auth.deleted | Authorization deleted | Авторизация удалена | — | toast |
| `views/settings/YtmCard.tsx:177` | settings.ytm.headers.required | Paste request headers from DevTools | Вставьте заголовки запроса из DevTools | — | toast error |
| `views/settings/YtmCard.tsx:183` | settings.ytm.auth.saved | Authorization saved | Авторизация сохранена | — | toast |
| `views/settings/YtmCard.tsx:195` | settings.ytm.oauth.credentials_required | Fill in client_id and client_secret | Заполните client_id и client_secret | — | toast error; separate from backend `api.errors.oauth_credentials_required` |
| `views/settings/YtmCard.tsx:210` | settings.ytm.oauth.done | Done: YouTube Music connected | Готово: YouTube Music подключён | — | authOut → ProgressBar |
| `views/settings/YtmCard.tsx:211` | settings.ytm.connected | YouTube Music connected | YouTube Music подключён | — | toast |
| `views/settings/YtmCard.tsx:222` (title) | settings.ytm.brand | YouTube Music | YouTube Music | — | Card title; proper brand token (not a translation key; documented occurrence) |
| `views/settings/YtmCard.tsx:222` (sub) | settings.ytm.subtitle | Personal session (likes/albums) and age-restricted videos | личная сессия (лайки/альбомы) + возрастные видео | — | Card subtitle |
| `views/settings/YtmCard.tsx:224` | settings.ytm.status.label | Status | Статус | — | Field label |
| `views/settings/YtmCard.tsx:225` | settings.ytm.status.hint | Authorization via browser cookies — extract them below | авторизация через cookie браузера — извлеките их ниже | — | Field hint |
| `views/settings/YtmCard.tsx:230` | settings.ytm.status.disconnected | Not connected — extract cookies from your browser | не подключено — извлеките куки из браузера | — | status line |
| `views/settings/YtmCard.tsx:231` (oauth) | settings.ytm.status.oauth | Connected (OAuth) | подключено (OAuth) | — | status line; account name appended as data via `settings.ytm.status.with_account` below |
| `views/settings/YtmCard.tsx:231` (headers) | settings.ytm.status.headers | Connected (browser headers) | подключено (заголовки браузера) | — | status line |
| `views/settings/YtmCard.tsx:232` | settings.ytm.status.with_account | {status} — {account} | {status} — {account} | status (localized branch above),account (provider name) | status line; compose only after resolving active locale |
| `views/settings/YtmCard.tsx:233` | settings.ytm.status.login_failed | Sign-in isn't working | вход не работает | — | status badge; account_error is presence signal, not copy |
| `views/settings/YtmCard.tsx:240` | settings.ytm.browser_cookies | Browser cookies | Куки из браузера | — | Field label |
| `views/settings/YtmCard.tsx:242–245` | settings.ytm.browser_cookies_hint | “Find accounts” shows personal profiles and YouTube channels (brand, such as …@pages.plusgoogle.com) with their Page IDs. Select the account you need. Use the manual Page ID field below if a channel is not recognized (value from DevTools → Request Headers → X-Goog-PageId). | «Найти аккаунты» покажет личные профили и страничные каналы YouTube (brand, например …@pages.plusgoogle.com) с их Page ID — выберите нужный в списке. Ручное поле Page ID ниже — на случай, если канал не распознался (значение из DevTools → Request Headers → X-Goog-PageId) | — | Field hint (all concatenated literals one message; protocol/header tokens remain literal) |
| `views/settings/YtmCard.tsx:251` | settings.ytm.browser_aria | Browser | Браузер | — | select aria |
| `views/settings/YtmCard.tsx:261` | settings.ytm.browser.none | Not found | не найдено | — | select option |
| `views/settings/YtmCard.tsx:267` | settings.ytm.profile_aria | Profile | Профиль | — | select aria |
| `views/settings/YtmCard.tsx:276` | settings.ytm.profile.none | No profile found | профиль не найден | — | select option |
| `views/settings/YtmCard.tsx:278` (Default) | settings.ytm.profile.default | Main (Default) | Основной (Default) | — | select option; Default is browser profile ID, other profile names verbatim |
| `views/settings/YtmCard.tsx:287` | settings.ytm.account.find | Find accounts | Найти аккаунты | — | button |
| `views/settings/YtmCard.tsx:295` | settings.ytm.extract.action | Extract from browser | Извлечь из браузера | — | button |
| `views/settings/YtmCard.tsx:300` | settings.ytm.account.aria | Account | Аккаунт | — | select aria |
| `views/settings/YtmCard.tsx:305` | settings.ytm.account.auto | Auto (by likes) | авто (по лайкам) | — | select option |
| `views/settings/YtmCard.tsx:313` | settings.ytm.page_id.placeholder | Page ID (brand/channel accounts, optional) | Page ID (бренд/страничные аккаунты, опционально) | — | input placeholder |
| `views/settings/YtmCard.tsx:322` | settings.ytm.no_clips | Avoid video clips: download Topic audio instead | Избегать клипов: качать аудиоверсии (Topic) вместо клипов | — | SwitchRow text |
| `views/settings/YtmCard.tsx:324` | search.engine_aria (ref) | Search source | Источник поиска | — | Field label |
| `views/settings/YtmCard.tsx:327–328` | none (provider names) | YouTube Music / YouTube | YouTube Music / YouTube | — | SegControl option display = provider brand; values youtube_music/youtube are technical IDs |
| `views/settings/YtmCard.tsx:335` | settings.ytm.search_hint | The main search source and source for an artist's top tracks. YouTube Music searches its catalog and supplies tags; yt-dlp still downloads the files. YouTube searches without authorization. | основной источник на экране поиска и топа треков исполнителя. YouTube Music — поиск по каталогу YT Music и теги из него; файлы всё равно качает yt-dlp. YouTube — обычный поиск без авторизации. | — | help text |
| `views/settings/YtmCard.tsx:338` | settings.ytm.feedback.label | Accept recommendations as | Принимать рекомендации как | — | Field label |
| `views/settings/YtmCard.tsx:341` | recommend.apply.like (ref) | Like | Лайк | — | SegControl option |
| `views/settings/YtmCard.tsx:349` | settings.ytm.feedback.hint | What to do with an accepted recommendation (button or swipe right). A like is a strong signal: radio adapts faster and the track appears in Liked. Saving to the library is quieter: it doesn't mark the track as liked. | что делать с принятым треком на экране рекомендаций (кнопка и свайп вправо). Лайк — сильный сигнал: радио подстраивается быстрее, трек виден в «Нравится». Библиотека — тише: без пометки «нравится» в аккаунте. | — | help text |
| `views/settings/YtmCard.tsx:352` | settings.ytm.checks.title | YouTube checks (18+ and sign-in) | Проверки YouTube (18+ и вход) | — | Details title |
| `views/settings/YtmCard.tsx:353` (label) | settings.ytm.download_browser | Browser for downloads | Браузер для скачивания | — | Field label |
| `views/settings/YtmCard.tsx:353` (hint) | settings.ytm.safari_hint | Safari also reads profiles | safari читает и профили | — | Field hint; product/browser name remains literal |
| `views/settings/YtmCard.tsx:360` | settings.ytm.cookies.status_label | Cookie status | Статус cookies | — | Field label |
| `views/settings/YtmCard.tsx:363` | settings.ytm.cookies.set | Set ({filename}) | заданы ({filename}) | filename (configured basename or literal cookies.txt) | status line |
| `views/settings/YtmCard.tsx:364` | settings.ytm.cookies.unset | Not set — 18+ videos cannot be downloaded | не заданы — видео 18+ качаться не будут | — | status line |
| `views/settings/YtmCard.tsx:367` (label) | settings.ytm.cookies.file_label | cookies.txt | cookies.txt | — | Field label: technical filename, no locale key required |
| `views/settings/YtmCard.tsx:367` (hint) | settings.ytm.cookies.export_hint | “Get cookies.txt LOCALLY”: open youtube.com while signed in → Export | «Get cookies.txt LOCALLY»: откройте youtube.com залогиненным → Export | — | Field hint; quoted extension UI and URL verbatim |
| `views/settings/YtmCard.tsx:380` | settings.ytm.cookies.saved | Cookies saved ({count, plural, one {# line} other {# lines}}) | Cookies сохранены ({count, plural, one {# строка} few {# строки} many {# строк} other {# строки}}) | count | upload → toast |
| `views/settings/YtmCard.tsx:396` | settings.ytm.methods.title | Other sign-in methods | Другие способы входа | — | Details title |
| `views/settings/YtmCard.tsx:398` | settings.ytm.methods.hint | If automatic browser extraction isn't available (for example, when accessing remotely) | если автоизвлечение из браузера недоступно (например, при удалённом доступе) | — | help text |
| `views/settings/YtmCard.tsx:401` (label) | settings.ytm.headers.label | Browser headers | Заголовки браузера | — | Field label |
| `views/settings/YtmCard.tsx:402` | settings.ytm.headers.hint | In DevTools at music.youtube.com: Network → GET /browse → Request Headers; copy and paste here | DevTools: открыт music.youtube.com → Network → GET /browse → Request Headers, скопируйте и вставьте сюда | — | Field hint; API/DevTools tokens literal |
| `views/settings/YtmCard.tsx:407` | none (protocol example) | Cookie: … / X-Goog-AuthUser: 0 / Authorization: … | same | — | textarea placeholder: wire header sample, preserve bytes/line breaks |
| `views/settings/YtmCard.tsx:414` | settings.ytm.headers.paste | Paste headers | Вставить заголовки | — | button |
| `views/settings/YtmCard.tsx:419` | settings.ytm.oauth.label | OAuth (YouTube Data API application) | OAuth (приложение YouTube Data API) | — | Field label |
| `views/settings/YtmCard.tsx:421,425` | none (credential identifiers) | client_id (YouTube Data API) / client_secret | same | — | input placeholders, protocol IDs and provider name, preserve literals; explicit technical exclusions |
| `views/settings/YtmCard.tsx:367` | none (technical filename) | cookies.txt | same | — | configured cookie-export filename; explicit technical exclusion |
| `views/settings/YtmCard.tsx:431` | settings.ytm.oauth.connect | Connect OAuth | Подключить OAuth | — | button |
| `views/settings/YtmCard.tsx:439` | settings.ytm.oauth.confirm_link | Confirm access at: | Подтвердите доступ по ссылке: | — | link prefix; authOut.url remains URL data |
| `views/settings/YtmCard.tsx:453` | settings.ytm.cookies.delete_confirm | Delete saved YouTube cookies? 18+ videos will no longer download. | Удалить сохранённые YouTube-cookies? Видео 18+ снова качаться не будут. | — | confirm dialog |
| `views/settings/YtmCard.tsx:461` | settings.ytm.cookies.deleted | Cookies deleted | Cookies удалены | — | toast |
| `views/settings/YtmCard.tsx:476` | settings.ytm.checks.reading | Reading… (macOS may request Keychain access — click Allow) | читаю… (macOS может спросить доступ к связке ключей — нажмите Allow) | — | checkLogin → login state → DOM |
| `views/settings/YtmCard.tsx:484` | settings.ytm.checks.error | error | ошибка | — | browser check status badge |
| `views/settings/YtmCard.tsx:485` | settings.ytm.checks.empty | empty | пусто | — | browser check status badge |
| `views/settings/YtmCard.tsx:486` (authenticated) | settings.ytm.checks.signed_in | signed in | вход | — | browser check status badge |
| `views/settings/YtmCard.tsx:486` (unauthenticated) | settings.ytm.checks.signed_out | not signed in | без входа | — | browser check status badge |
| `views/settings/YtmCard.tsx:487` (empty) | settings.ytm.checks.no_cookies | No YouTube cookies | cookies YouTube нет | — | browser check detail |
| `views/settings/YtmCard.tsx:487` (nonempty) | settings.ytm.checks.cookie_count | {count} cookies | {count} шт | count (may be absent in legacy response; preserve readable fallback) | browser check detail |
| `views/settings/YtmCard.tsx:502` (authenticated) | settings.ytm.checks.can_download | Signed in ({browsers}) — downloads available | вход есть ({browsers}) — можно качать | browsers (joined browser names verbatim) | checkLogin result → login state → DOM |
| `views/settings/YtmCard.tsx:502` (unauthenticated) | settings.ytm.checks.sign_in_hint | Not signed in: sign in to YouTube in “{browser}” and try again | входа нет: войдите в YouTube в «{browser}» и повторите | browser (server-selected name, possibly absent; handle missing separately) | checkLogin result → login state → DOM |
| `views/settings/YtmCard.tsx:516` | settings.ytm.checks.requesting | Checking YouTube… | запрашиваю YouTube… | — | checkAge → age state → DOM |
| `views/settings/YtmCard.tsx:523` | library.compress.ok (ref; review context) | OK | ок | — | age-check success badge; if compression status semantics differ, use `settings.ytm.checks.ok` with same text |
| `views/settings/YtmCard.tsx:524` | settings.ytm.checks.no_login | not signed in | входа нет | — | age-check gate badge; distinct case from `settings.ytm.checks.signed_out` |
| `views/settings/YtmCard.tsx:525` | settings.ytm.checks.not_18 | not 18+ | не 18+ | — | age-check blocked badge |
| `views/settings/YtmCard.tsx:526` | settings.ytm.checks.error (ref) | error | ошибка | — | age-check other badge |
| `views/settings/YtmCard.tsx:538` | settings.ytm.checks.age_label | 18+: | 18+: | — | age-check heading: technical age marker, punctuation only; no separate key required |
| `views/settings/YtmCard.tsx:539` (verified) | settings.ytm.checks.verified | verified | подтверждены | — | overall age badge |
| `views/settings/YtmCard.tsx:539` (unverified) | settings.ytm.checks.unverified | not verified | не подтверждены | — | overall age badge |
| `views/settings/YtmCard.tsx:554` | settings.ytm.checks.login_action | Check sign-in | Проверить вход | — | button |
| `views/settings/YtmCard.tsx:556` | settings.ytm.checks.login_hint | The server will read the selected browser's cookie store | сервер прочитает хранилище выбранного браузера | — | idle hint |
| `views/settings/YtmCard.tsx:559` | settings.ytm.checks.age_action | Check 18+ | Проверить 18+ | — | button |
| `views/settings/YtmCard.tsx:561` | settings.ytm.checks.age_hint | Each source will request an age-restricted video | запросит age-видео каждым источником | — | idle hint |

**Ten-file exclusions and migration notes (bounded, not a blanket exemption):** `AlbumsTab.tsx:1–2,66,89,101,170–202`, `ArtistsTab.tsx:1–2,36–85,123–155`, `TracksTab.tsx:1–2,16–32,64–104,125–198,216–256`, `PlaylistsTab.tsx:1,20–35,43,53–57` comments, matchMedia/CSS/sort and YTM query IDs, memo keys, count math and loading skeleton are technical. Their artist/album/track titles and YT records are provider/tag data; `TracksTab:236` `YouTube Music` is the brand passed as a job group title, `:264` playlist name is provider data. `onCount` presently receives rendered Russian JSX/string: when locale changes the effect dependencies and memoized count must update; don't cache translated nodes by a count-only dependency. `plural()` calls at AlbumsTab:116,124; ArtistsTab:88; PlaylistsTab:38; TracksTab:109 are **not** translatable helper outputs by themselves; each consuming whole phrase is mapped above.

`Cards.tsx:14,21–22,44–45,68–74,79–82,87–91,112,122–125,140–141,157,163,187–198,211–238` keyboard IDs, aria-hidden music glyph, cover paths, duration/size/bitrate/tag values, album/artist metadata and CountBadge numeric status are data/technical; `fmtSize` needs active locale Intl, `fmtDuration` is numeric clock; `♥ YT` badge glyph/provider abbreviation and `↓` are symbolic, not a sentence. `Inbox.tsx:28,32,49–53,71–72,90–94,123–136,143–146` API paths, error payloads, filenames, file titles/artists and cover URL are not local messages; API errors at :32 must preserve descriptors, not `String(error.message)`. `Inbox:88` numeric-only progress is listed for pipeline consistency, not a translatable noun; `:55,96` failure branches must be full messages, not Russian fragments. `albumDetail.tsx:48–80,86–93,122–125,166–175,184–190,223–244,260–264,284–285,289–305,312–325,336–346,384–406,422–434,444–446,450–455,461,473–475,484–508,516–520,535–551` review/styles, tracks, album names, field IDs and values, cover URLs/MIME, user filename, keyboard IDs and paths are data/technical. `:238` validateTagField returns an owned **validation message** (see editor ledger), `:235/:289` field labels must resolve `editor.fields.*`, not be stored as Russian values from libUtils. `:387` “Файл трека” is owned source-label copy, unlike provider `r.source` at :401. `:280` plural helper is subsumed by whole hint. `:192,267,437` plurals are in keyed toast branches above. `albumDetail:87` exact reusable key is `ytm.album.cover_alt` (title-only); the descriptive `library.album.cover_alt` label in that row is an alias, **not a new catalog key**.

`libUtils.ts:40–140,157–169` filename stem, Cyrillic transliteration table, normalization, grouping and sorting are algorithmic, not display copy. `localeCmp:73–75` uses implicit platform locale; `groupAlbums:117–119` uses default `localeCompare` too. Define whether sort should follow active UI locale without changing canonical identity/group keys (currently `normOne`, lowercase `album::` and path). `:145–155` array second values are owned labels (including invariant ISRC), not tag values; reusable `editor.fields.*` resolves by field ID; `:173` formatted sizes are data inside an owned status. `trackDetail.tsx:26–34,36–47,52–56,102–103,111–114,133–139,151,168–171` tag values, filenames, fetched lyrics and artist/title, API paths, clock, em dash and numeric formatting are data; labels/status/empty fallback are keyed. `:127,156,177` unknown error text is legacy verbatim; known descriptors must not be stringified before toast. `:171` job progress from backend belongs to `jobs.*`, not a new frontend phrase. `:168–173` compress result label is owned backend copy and may be a descriptor; resolve at display with full summary key, never concatenate `[object Object]`.

`YtmCard.tsx:13–24,51–65,69–80,83–95,99–101,103 (handle),106 (authuser number),114–120,125–147,151–159,164–173,180–189,198–209,213–219,228–229,263–264,277–279 (profile names),307 (account value),317–318,326–332,355–358,362–363 (filename),369–379,382,393,406–411,421–427,437–444,459–465,478–483,487 (raw error),489–496,508,518–522,528–534,545` state/IDs/API paths, browser/account/provider names, URL, profile IDs, CSS, file contents, credential keys and vendor feedback/error strings remain verbatim. `:95,146,206` backend job progress is `RenderableMessage` (legacy `msg`), not YtmCard-owned copy; preserve descriptors in state and resolve in ProgressBar. `:116,154,171,187,215,382,463,508,545` raw exception/HTTP errors are not translation keys; retain structured owned codes where available. `:531` provider video title or error is response data. `:483–487,523–526` checks branch on raw status/reason IDs (correct); **no Russian-prose matching is present in these ten files**. Other previously observed Russian-prose branching (`MiscScreen:59,101`, `SearchScreen:121`, `RecommendScreen:245`, `QualityScreen:474`) remains a stable-code/stage-ID migration concern, not catalog content. `YtmCard:102–106` stores composed option labels, `:476–545` stores React result trees, so both need deferred localization; `status.account_error` controls a badge but its raw contents are not rendered. `:407,421,425` placeholders are protocol/credential examples, not prose, and `:538` 18+ is a numeric category. All reused messages with slightly different original capitalization/punctuation must be harmonized with their canonical references.
