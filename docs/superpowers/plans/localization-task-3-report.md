# Task 3 re-review response — 2026-10-14

## Scoped finding fixed

`main.tsx` intentionally waits for `bootstrapLanguage()` before mounting React.
Previously, `bootstrapLanguage()` awaited `GET /api/settings` with no cancellation
path. A request that never settled therefore kept the page blank indefinitely.

`frontend/src/i18n/index.ts` now creates an `AbortController` for that bootstrap
request and aborts it after 5 seconds. The request receives the controller's
signal. Abort, network failure, non-OK responses, and JSON failures all follow
the existing recovery path, which retains the provisional locale and lets
`main.tsx` render. The timer is cleared in `finally`, both for successful and
failed requests.

## Regression coverage

`frontend/tests/i18n.test.ts` uses Vitest fake timers and an unresolved fetch
promise. It advances virtual time by 5 seconds, verifies that the request is
aborted, and verifies that the provisional Russian locale remains active. No
real-time wait is used. A companion test verifies that a successful settings
load leaves no pending bootstrap timer.

## Verification

All commands were run from `frontend` after the change:

| Command | Result |
| --- | --- |
| `npm test -- i18n.test.ts` | 1 file, 9 tests passed |
| `npm test` | 32 files, 220 tests passed |
| `npm run build` | passed (`tsc --noEmit` and Vite production build) |

## Scope

Only the i18n bootstrap timeout, its regression tests, and this Task 3 report
were changed for this re-review finding. Existing unrelated working-tree changes
were left untouched.
