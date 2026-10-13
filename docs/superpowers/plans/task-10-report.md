# Task 10 — localization guardrails report

## Completed scope

- **Typed i18next keys:** `frontend/src/i18n/i18next.typecheck.d.ts` imports the
  English catalog and registers it as `CustomTypeOptions.resources.translation`.
  Production `tsconfig.json` now includes all of `src`, including that
  augmentation, and enables JSON module resolution.
- **Production API regression:** `frontend/src/i18n/production.typecheck.ts` is
  compiled by `npm run build`. It uses the actual `useTranslation()` hook and
  singleton `i18n.t`, with necessary `@ts-expect-error` directives for an
  unknown key. Removing the augmentation makes those directives unused; allowing
  an invalid literal makes the production build fail.
- **Explicit dynamic-key boundary (superseded below):** the initial runtime
  boundary was `translateDynamic()` for API/configuration-derived keys. The
  follow-up replaced it with narrow key-family and API descriptor resolvers;
  statically authored calls remain direct typed `t()`/`i18n.t()` calls and
  production source is not excluded from key checking.
- **ICU contract validation:** `scripts/check_locales.py` compares argument
  presentation kinds as well as argument names, plural categories, catalog
  tree shape, and non-empty values. It rejects changes such as `plural` to
  `select` and `select` to a simple interpolation; nested select/plural option
  labels are not incorrectly treated as interpolation arguments.
- **Copy checker binding and scope resolution:** notification detection is now
  performed by `scripts/check_copy_frontend.mjs` using the TypeScript AST and
  lexical bindings, not a call-shaped regex. It reports only `toast` imported
  from `../lib/toast` (including aliases) and unshadowed browser
  `alert`/`confirm`/`prompt` calls. The existing Python AST checker continues
  to restrict backend descriptor checks to supported `message` imports.
- **Fixtures:** Python regression fixtures retain plural-to-simple ICU mismatch
  coverage and cover imported toast aliases, unshadowed browser notifications,
  unrelated same-named functions, function parameters/local shadows, comments,
  and strings. Existing fixtures cover aliased/shadowed backend message
  constructors. The mounted frontend i18n suite verifies the App skip link and
  structured toast descriptors change from Russian to English without a remount.
- **App skip link catalog:** added `shell.skip_to_content` in both catalogs and
  rendered it through `useTranslation()` in `App`.
- **Guidance:** `AGENTS.md` now requires statically typed frontend `t()` keys
  and documents that the copy guardrail is binding/scope aware.

## Verification — 2026-10-15

- `pytest tests/test_copy_guardrails.py tests/test_locale_catalogs.py -q` —
  **14 passed**.
- `cd frontend && npm run check:i18n-keys` — passed.
- `cd frontend && npm run build` — passed (`tsc --noEmit` and Vite production
  build).
- `python scripts/check_locales.py` — passed.
- `python scripts/check_copy.py` — passed.

## Explicit boundary

The typed API intentionally covers statically known frontend keys. Structured
backend descriptors use dynamic codes received over HTTP, so `resolveMessage`
checks `i18n.exists(code)` at runtime and falls back to the readable message
or the localized generic error for unknown codes. This keeps provider and
legacy payloads renderable without weakening literal `t("…")` call checking.

## 2026-10-15 — resolver and AST scope hardening follow-up

- Removed the arbitrary `translateDynamic()` export. Dynamic UI domains now use
  narrow key-family resolvers: quality category/cause labels, editor group and
  field labels, recommendation actions, and YouTube Music download labels.
  Production typecheck fixtures prove a download resolver rejects `nav.*` and a
  recommendation resolver rejects `api.*` keys.
- Added `resolveApiDescriptor()` as the explicit API descriptor boundary. It
  accepts only runtime codes with the `api.` prefix and an existing catalog
  entry; unknown API/provider codes retain the descriptor fallback or the
  generic localized error. Non-API structured descriptors still resolve through
  the separately named catalog-descriptor adapter.
- The copy-checker AST walker now collects identifiers from object/array
  destructuring in variables and parameters, plus catch clauses. This prevents
  destructured callback names from being treated as browser dialog globals.
- The checker now reports `window.alert/confirm/prompt` and
  `globalThis.alert/confirm/prompt` only when `window`/`globalThis` are not
  lexically shadowed. Arbitrary object properties and shadowed globals remain
  excluded.
- Added regression fixtures for parameter/local/catch destructuring and for
  unshadowed versus shadowed `window`/`globalThis` dialogs.

## 2026-10-15 — loop-header binding hardening follow-up

- The copy-checker now creates a lexical scope for `for`, `for…of`, and
  `for…in` statements and registers their variable declaration binding
  patterns before walking the initializer, condition/iteration expression, and
  loop body. Object and array destructuring therefore correctly shadows
  browser dialog globals inside the loop.
- Added a fixture covering object and array destructuring in `for`, `for…of`,
  and `for…in` headers; an unshadowed global `alert` remains reported.
- Corrected the stray indentation in `childScope`.

## Verification — 2026-10-15 (loop-header scope hardening)

- `pytest tests/test_copy_guardrails.py -q` — **7 passed**.
- `python scripts/check_copy.py` — passed.
- `python scripts/check_locales.py` — passed.
- `cd frontend && npm run check:i18n-keys` — passed.
- `cd frontend && npm run build` — passed (`tsc --noEmit` and Vite production
  build).

## 2026-10-15 — `var` function/module-scope hardening follow-up

- The TypeScript AST walker now distinguishes `var` from `let`/`const` bindings:
  `var` declarations are registered in the enclosing function scope, or in the
  module scope when no function encloses them. The collector hoists nested
  `var` declarations before walking earlier statements, matching JavaScript's
  scope semantics.
- `let` and `const` remain lexical: a binding declared in a nested block does
  not shadow an unqualified browser dialog call after that block.
- Added a regression fixture for nested function- and module-scoped `var`,
  including calls preceding the declaration and companion `let`/`const`
  controls.

## Verification — 2026-10-15 (`var` scope hardening)

- `pytest tests/test_copy_guardrails.py -q` — **8 passed**.

## Verification — 2026-10-15 (resolver and AST scope hardening)

- `pytest tests/test_copy_guardrails.py -q` — **6 passed**.
- `cd frontend && npm run check:i18n-keys` — passed.
- `cd frontend && npm test -- ytmDownload.test.ts qualityScreen.test.tsx i18n.test.tsx` — **42 passed**.
- `cd frontend && npm run build` — passed (`tsc --noEmit` and Vite production build).
- `python scripts/check_copy.py` — passed.
- `python scripts/check_locales.py` — passed.
