# Task 6 review-fix report

## 2026-10-15 — review findings resolved

- `/api/playlist` now returns the exact descriptor
  `{code: "api.errors.empty_playlist", params: {}, message: "Playlist is empty"}`
  when extraction produces no entries and `last_error` is empty. If a provider
  error is present, the complete legacy string (`Плейлист пуст (<reason>)`) is
  preserved.
- `/api/recommend/generate` now returns the exact
  `api.errors.ytm_connection_required` descriptor when YouTube Music is not
  connected. Both new API message keys are present in EN and RU catalogs.
- The standalone missing-build 503 page negotiates `ru`/`ru-*` and `en`/`en-*`
  from `Accept-Language` by descending q-value, ignores unsupported and q=0
  candidates, and defaults to English. Its `<html lang>` and
  `Content-Language` agree with the selected page.
- Removed the dead `_validate_tag_fields` wrapper. Updated the API-client
  header comment to describe string and descriptor error payloads. The
  unreadable-response frontend test now verifies `ApiError.status` and
  `renderableMessage` as well as `message`.

## 2026-10-15 — follow-up regressions resolved

- Empty `/api/playlist` extraction is now covered in both result states: without
  a provider reason it returns the owned `api.errors.empty_playlist` descriptor;
  with one, it preserves the complete legacy `Плейлист пуст (<reason>)` string.
  This keeps arbitrary provider text out of catalog interpolation without losing
  actionable context.
- Missing-build language negotiation now has regression cases for regional
  language tags and an invalid `q=nan` weight. The parser accepts only finite
  quality values in the HTTP range `(0, 1]`, so invalid, zero, negative, and
  greater-than-one candidates cannot outrank a valid supported language.

## Verification — 2026-10-15

- `pytest tests/test_web_api.py -q` — 157 passed (two upstream
  TestClient/httpx deprecation warnings).
- `pytest` — 756 passed (the same two upstream TestClient/httpx deprecation
  warnings).
- `cd frontend && npm test` — 35 files, 240 tests passed.
- `cd frontend && npm run build` — passed (`tsc --noEmit` and Vite production
  build).
- Parsed both locale JSON catalogs with `python -m json.tool`; passed.
