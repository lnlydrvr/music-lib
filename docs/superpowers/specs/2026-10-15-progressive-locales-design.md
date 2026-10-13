# Progressive locale onboarding design

## Goal

Make it practical to add a language before its translation is complete. A
generated locale is immediately selectable in the UI. Translated strings appear
in that language, while keys still listed as untranslated use English. The
workflow must keep a normal JSON translation catalog and must not mistake an
English-identical translation for unfinished work.

## User workflow

Run a locale-generation command with a valid BCP-47 primary language code and
the locale's native display name, for example `python scripts/new_locale.py es
--name Español`. The command creates `frontend/src/locales/es.json` by copying
the nested English source catalog and creates `frontend/src/locales/es.todo.json`
containing every source leaf key. It registers the locale so the application
can offer it immediately. The translator edits `es.json` and removes each
translated key from `es.todo.json`; unfinished keys remain usable through the
English fallback. The final remaining TODO keys are an explicit completion
check.

The command must reject malformed/unsupported path-like locale codes, existing
catalogs, and duplicate registrations without overwriting user files. It should
validate the source catalog before generation and write output atomically or
clean up partial output on failure.

## Locale registry and loading

Add a small checked-in locale registry as the shared source of locale codes and
native display names. Frontend and backend read the same registry; generation
adds an entry. Existing `en` and `ru` entries retain their current behavior.
Only registered locales are accepted by settings APIs or displayed in the
language selector. Unknown, unregistered, or removed saved values resolve as
unset and fall back using the existing browser-language/English rules.

Frontend catalog loading discovers registered locale JSON resources at build
time (not arbitrary files) so a generated catalog is included in the Vite build
without hand-editing an import list. Locale codes become runtime strings while
translation message keys remain statically typed from `en.json`. Locale native
names are metadata, not translated UI prose.

For each non-English locale, its `.todo.json` is a list of dot-separated leaf
keys still awaiting translation. Before registering resources with i18next,
remove those keys from the locale's runtime translation object. i18next then
uses its existing English fallback for those keys, including ICU messages and
nested structured message codes. Do not mutate the imported JSON object shared
with tests or build tooling.

## Validation and completion

Extend `scripts/check_locales.py` to validate the registry, catalog set, and
TODO sets. Every registered locale must have a valid catalog and TODO file;
TODO keys must be unique source leaf keys, and catalog shape, ICU argument
names/kinds, and plural requirements must remain valid. Empty values are only
permitted for keys explicitly listed in TODO (generation itself copies English
values, so normal work starts nonempty). A locale is complete when its TODO set
is empty. The existing two-locale validation remains unchanged for `en` and
`ru`, with an empty TODO set for `ru`.

The TypeScript translation-key contract continues to derive exclusively from
English; adding an incomplete runtime locale does not weaken typed `t()` calls.
`check:i18n-keys` validates code keys, and locale validation reports each
remaining TODO key and completion count.

## Documentation and compatibility

Update English and Russian localization guides together, including the
generation command, translation loop, fallback behavior, TODO format,
completion checks, and native display-name convention. Update README language
claims from fixed English/Russian support to describe installed/registered
locales where appropriate.

Existing settings semantics remain: no explicit saved locale is represented as
`null`; a valid saved locale wins over browser preference; unsupported saved
values are treated as unset. Persisted locale codes remain stable identifiers.

## Verification

Add focused tests for generation (including refusal to overwrite), registry
discovery/validation, TODO key validation, fallback rendering for a pending key,
and selection/persistence of a generated locale through settings. Run the
locale and copy checks, i18n key check, frontend and Python tests, and production
build. Confirm English and Russian startup/browser fallback behavior remains
intact.

## Out of scope

- Automatically translating source strings.
- Accepting unregistered locale files as application languages.
- Translating music metadata, provider content, technical identifiers, or
  other user/provider data.
- Translation context/comments beyond the English source strings and existing
  keys.
