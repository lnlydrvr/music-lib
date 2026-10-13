# Task 1 re-review response — 2026-10-14

## Status

**Re-review requested against a frozen contract, but Task 1 remains OPEN.** The original exhaustive acceptance is not met. The 778 frontend and 164 backend figures are candidate matching-line counts; they have not been reconciled line by line, so no complete unmatched count or full-coverage claim is valid.

## Previous blocking findings and disposition

| Previous finding | Evidence / affected area | Disposition in this handoff |
|---|---|---|
| Frontend inventory was not exhaustive | 81 frontend source files plus `frontend/index.html`; wide scan returned 778 matching lines | **Unresolved.** The map preserves the count and explicitly requires a final 778-line reconciliation. Existing occurrence tables are evidence, not closure. |
| Backend producer/transport inventory was not exhaustive | HTTP/jobs/diagnostics/normalize scan returned 164 matching lines; multiline calls and indirect `_BatchProgress` pushes included | **Unresolved.** Required final scan remains a Task 1 acceptance blocker. `_BatchProgress`, nested quality responses, result labels/errors and CLI renderers remain named risks. |
| 503 page had an unresolved language boundary | `src/web/server.py:20–50,77–79`; SPA is unavailable when page is served | **Resolved at contract level; implementation unverified.** Freeze standalone web-only EN/RU negotiation, q ordering, unsupported/q=0 handling, English fallback, `lang` and `Content-Language`, and 503 preservation. Tests still required. |
| CLI versus web scope was ambiguous | `server.py:122–135` terminal output; Rich CLI renderers in health/lint/normalize | **Resolved by PM decision:** CLI is out of web localization scope; Rich formatters print English descriptor `message` fallbacks or legacy strings unchanged. No locale catalog entries are required for CLI-only text. |
| Owned prefixes were mixed with raw provider/OS reasons | Historical HTTP alternatives for routes and external exception branches | **Resolved at contract level.** Code only when an independently valid English fallback exists; otherwise preserve the full legacy string. Historical alternatives remain marked as evidence, not instructions. Branch-by-branch confirmation is unresolved. |
| DTO field names and legacy compatibility were inconsistent | `detail/errors`, job `name/error/message/msg`, diagnostics and apply results | **Resolved at contract level.** Canonical names and legacy compatibility are frozen in the map addendum. Runtime implementation and transport tests are not done. |
| Diagnostic field label representation was ambiguous | Missing-tag/whitespace/change/duplicate-field paths; `fieldLabel` versus raw `field` | **Resolved at contract level.** Wire `params.field` is a stable raw ID; `resolveFieldLabel` supplies the locale label; unknown IDs render raw data with a dev/test diagnostic. Runtime verification is open. |
| Normalize change DTO risked becoming localized wire data | `/normalize/plan` and quality change rendering | **Resolved at contract level.** Normalize remains view-only `{field,path,old,new,cause}`; UI constructs a temporary change descriptor at render time. Implementation/test verification is open. |
| Defaults/data could be translated accidentally | `Various Artists` in `LibraryScreen`; provider names, tags, paths and metadata | **Resolved for the identified default.** `Various Artists` is explicitly editable tag data and must remain verbatim. Full data-vs-copy scan remains open. |
| Unknown structured codes could expose opaque codes or unsafe params | `resolveMessage` fallback and descriptor handling | **Resolved at contract level.** Prefer nonblank `value.message`; otherwise localized `common.errors.unavailable`; never display the code or interpolate unknown params. Runtime tests are open. |
| Catalog parity and ICU validity were not verified | No catalogs yet; editorial alternatives, slash rows and conditional fragments remain | **Unresolved.** Machine extraction, EN/RU key parity, ICU argument/category validation and plural checks remain required. |
| Required tests/checks were not run | No product tests or build; 503 and descriptor compatibility tests pending | **Unresolved.** This handoff intentionally does not claim test completion. |

## What changed in the documentation

- `localization-key-map.md` now has a compact canonical contract addendum that supersedes contradictory active instructions while preserving historical evidence.
- `localization-task-1-report.md` now records the final freeze/handoff state, PM decisions, open evidence and explicit failure to meet exhaustive acceptance.
- No product source, tests, catalogs or approved product/design documentation were edited.

## Required next review gate

1. Run the final frontend and backend scans against the frozen addendum.
2. Reconcile every candidate line to an occurrence row, bounded exclusion or justified legacy string.
3. Validate exact DTO names, JSON params, English fallback text and polling/SSE parity.
4. Implement and test standalone 503 negotiation, descriptor fallback, diagnostic field resolution and normalize view-only rendering.
5. Extract and validate EN/RU catalogs and ICU parity.
6. Run the required test/build suite, then request re-review with evidence.

Until those gates produce evidence, Task 1 is a **handoff with frozen decisions**, not a completed exhaustive inventory.

## Task reviewer follow-up

- Unset language representation: fixed to `GET /api/settings: {"language": null}` when no valid saved choice exists; saved selection returns exactly `"en"` or `"ru"`. See canonical map addendum and plan Task 2.
- Rich CLI: fixed as English-only CLI scope; issue formatters print structured descriptor's English `message`, or the legacy string unchanged. No translation keys are required solely for CLI output.
- The 778 frontend / 164 backend line-by-line reconciliation remains explicitly uncompleted and is not represented as exhaustive inventory. It remains a final implementation scan/guardrail, not a blocker for starting Task 2.
