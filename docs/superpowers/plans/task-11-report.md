# Task 11 — documentation review follow-up

## Task11 review finding

- Updated `docs/en/I18N.md` and `docs/ru/I18N.md` to state the same locale
  selection behavior: a saved server language takes precedence after settings
  load; with no saved choice, use a supported `navigator.language` value and
  otherwise English; if the settings request fails or times out, preserve the
  provisional locale derived from `localStorage` or the browser.
- No implementation changes.

## Verification

- Link check — passed.
- `python scripts/check_locales.py` — passed.
