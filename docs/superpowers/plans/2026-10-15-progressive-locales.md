# Progressive Locale Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let translators generate a new locale from English, make it immediately selectable, and fall back to English for keys still listed as untranslated.

**Architecture:** Use a checked-in JSON locale registry as the shared source for frontend and backend locale availability, language codes, and native display names. A generator copies `en.json`, writes a TODO key list, and registers the locale. Frontend filters TODO keys from the locale resources so i18next falls back to English; validation checks registry, catalogs, TODOs, and ICU contracts.

**Tech Stack:** Python 3.10+, JSON, React/TypeScript, Vite, i18next, pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-15-progressive-locales-design.md`

## Global Constraints

- English remains the source catalog and fallback.
- Only registered locales are accepted by settings APIs or displayed in the language selector.
- Translation message keys remain statically typed from `en.json`.
- A locale's `.todo.json` is a list of untranslated dot-separated leaf keys; pending keys resolve from English.
- Preserve existing settings semantics: absent language is `null`, valid saved locale wins over browser preference, unsupported saved values are unset.
- Update English and Russian localization documentation together.
- Do not add dependencies.

## Review Focus

- Malformed locale codes and path traversal: generator rejects codes that could escape the locale directory; test invalid values.
- Existing files/duplicate registry entries: generator refuses and leaves user files byte-for-byte unchanged; test both collisions.
- Missing/extra/duplicate/non-leaf TODO keys: validator rejects each with locale/key-specific errors; test all forms.
- Pending ICU translation: runtime removes pending key and renders English with interpolation/plural formatting; test a parameterized ICU key.
- Unsupported persisted locale: backend reports unset and frontend falls back via browser/English behavior; keep regression coverage for unknown language.

---

### Task 1: Shared locale registry and validation contract

**Files:**
- Create: `frontend/src/locales/registry.json`
- Modify: `src/config.py`
- Modify: `scripts/check_locales.py`
- Modify: `tests/test_locale_catalogs.py`
- Modify: `tests/test_config.py`

**Interfaces:**
- Registry JSON entries have `code` (lowercase primary BCP-47 language subtag) and `name` (native-language display name); initial entries are `en` / `English` and `ru` / `Русский`.
- Backend exposes registered codes through `SUPPORTED_LANGUAGES`, loaded from the shared registry with a safe fallback only if required by module initialization; settings validation must use that source.
- Validator accepts a locale directory containing registered locale catalogs and `.todo.json` files, reports remaining TODO keys, and returns errors for invalid registry/catalog/TODO contracts.

- [ ] **Step 1: Write registry and TODO validation tests**

Add tests that create a temporary registry and catalogs, then assert:

```python
def test_todo_keys_are_reported_as_incomplete(tmp_path):
    locale_dir = write_catalogs(tmp_path, {"greeting": "Hello"}, {"greeting": "Hola"})
    (locale_dir / "registry.json").write_text(json.dumps([
        {"code": "en", "name": "English"}, {"code": "es", "name": "Español"}
    ]))
    (locale_dir / "es.todo.json").write_text(json.dumps(["greeting"]))

    result = check_locales.validate_catalogs(locale_dir)

    assert any("es: 1 untranslated key" in item for item in result)
```

Also assert errors for malformed/duplicate locale codes, duplicate TODO entries, unknown TODO keys, missing registered catalog, unregistered catalog, and `.todo.json` files for `en`.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `pytest tests/test_locale_catalogs.py tests/test_config.py -q`
Expected: failures because registry loading and TODO validation are not implemented.

- [ ] **Step 3: Implement registry loading and validation**

Create the initial registry JSON. Update `src/config.py` to load its registered codes and use those for validation of persisted values. Extend `check_locales.py` to:

1. Parse/validate the registry (unique valid codes and non-empty native names; require `en`).
2. Require a catalog for each registered code and reject catalogs not in the registry.
3. Read `<code>.todo.json` as a list of unique dot-separated source leaf keys; reject malformed JSON, duplicates, non-string entries, unknown keys, and an English TODO file.
4. Keep validating ICU arguments/kinds for all actual catalog values. Require nonempty values except for keys explicitly listed in that locale's TODO file.
5. Report pending count and keys as incomplete status, not as validation failures, so the running translator branch remains checkable.

Preserve current behavior for `en` and `ru` by adding an empty `ru.todo.json` and no English TODO file.

- [ ] **Step 4: Run and pass focused validation tests**

Run: `pytest tests/test_locale_catalogs.py tests/test_config.py -q`
Expected: PASS, including the existing locale contract tests.

- [ ] **Step 5: Commit the registry and validation contract**

```bash
git add frontend/src/locales/registry.json frontend/src/locales/ru.todo.json src/config.py scripts/check_locales.py tests/test_locale_catalogs.py tests/test_config.py
git commit -m "feat: add locale registry and draft validation"
```

### Task 2: Locale generator

**Files:**
- Create: `scripts/new_locale.py`
- Create: `tests/test_new_locale.py`
- Modify: `scripts/check_locales.py` only if a shared registry helper is needed

**Interfaces:**
- CLI: `python scripts/new_locale.py <code> --name <native-name> [--locales frontend/src/locales]`.
- `generate_locale(code: str, name: str, locale_dir: Path) -> tuple[Path, Path]` creates `<code>.json`, `<code>.todo.json`, and appends the registry entry; it raises a clear `ValueError` on invalid input or collisions and never overwrites existing files.

- [ ] **Step 1: Write generator tests**

Test generation from a nested temporary English catalog, exact copied values, all leaf keys in TODO, registry update, invalid codes (`../es`, `es_MX`, empty, uppercase), missing name, catalog collision, TODO collision, and duplicate registry entry. Verify failure does not modify any existing file.

- [ ] **Step 2: Run the tests and verify failure**

Run: `pytest tests/test_new_locale.py -q`
Expected: FAIL because the generator module does not exist.

- [ ] **Step 3: Implement safe generation**

Validate a conservative lowercase BCP-47 primary-subtag format (`[a-z]{2,3}` or registered/private-use forms only if explicitly supported); reject path separators and codes not handled by the runtime. Validate English JSON first. Build all three output contents before writing. Refuse collisions. Write temporary files in the locale directory and replace into place; on any error, remove only files created by this invocation and do not modify existing files.

- [ ] **Step 4: Verify the CLI and tests**

Run: `pytest tests/test_new_locale.py -q`
Expected: PASS.

Run: `python scripts/new_locale.py --help`
Expected: usage documents code, required `--name`, and optional locale directory.

- [ ] **Step 5: Commit the generator**

```bash
git add scripts/new_locale.py tests/test_new_locale.py
git commit -m "feat: generate locale draft catalogs"
```

### Task 3: Runtime discovery, fallback, and language selection

**Files:**
- Modify: `frontend/src/i18n/index.ts`
- Modify: `frontend/src/i18n/i18next.typecheck.d.ts` only if registry typing needs adjustment
- Modify: `frontend/src/views/SettingsScreen.tsx`
- Modify: `frontend/tests/i18n.test.tsx`
- Modify: `frontend/tests/settingsScreen.test.tsx`
- Modify: `frontend/vite.config.ts` or `frontend/src/i18n/index.ts` for build-time registry/catalog discovery, depending on Vite glob support at these JSON paths
- Modify: `tests/test_web_api.py`

**Interfaces:**
- Frontend exports `SUPPORTED_LOCALES: readonly LocaleInfo[]` (or equivalent registry-derived list) and a `Locale` type based on registered codes while `TranslationKey` continues to derive from English.
- Frontend imports all registered catalog and TODO JSON resources at build time; unregistered files are ignored.
- Settings language selector renders each registered locale using its native display name.

- [ ] **Step 1: Add runtime tests for pending-key fallback and discovered selection**

Extend i18n tests with a test registry containing a temporary `es` fixture catalog and TODO list. Assert that a translated key resolves in Spanish, a pending key resolves to English (including ICU interpolation), `es-MX` resolves to `es`, and the selector exposes `Español`. Add backend API test asserting `language: "es"` can be saved and read when registered, and an unregistered code is rejected/unset according to existing API contract.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `cd frontend && npm test -- i18n.test.tsx settingsScreen.test.tsx`
Expected: FAIL because locale runtime remains hard-coded to `en`/`ru`.

Run: `pytest tests/test_web_api.py -k settings_language -q`
Expected: the generated locale is currently rejected.

- [ ] **Step 3: Implement registry-driven loading**

Use a Vite `import.meta.glob` with eager JSON imports constrained to registered locale catalog paths. Read registry metadata and matching TODO arrays. Deep-clone each catalog, delete all leaf keys listed in TODO (prune empty nested objects), then pass resources to i18next. Keep English as `fallbackLng`; keep `TranslationKey` sourced from `en.json`. Resolve locale code from browser tags using primary subtag and registry membership. Update Settings to build options from registry metadata. Ensure no arbitrary JSON or TODO file becomes a runtime locale.

- [ ] **Step 4: Align backend language validation and tests**

Use registry-derived codes in the settings API validation (through config's `SUPPORTED_LANGUAGES`). Keep `get_saved_language()` returning `None` for unknown or removed codes. Do not change language persistence format.

- [ ] **Step 5: Run focused checks**

Run: `cd frontend && npm test -- i18n.test.tsx settingsScreen.test.tsx`
Expected: PASS.

Run: `pytest tests/test_web_api.py -k settings_language -q`
Expected: PASS.

Run: `cd frontend && npm run build`
Expected: TypeScript and Vite build pass with registry-driven resources.

- [ ] **Step 6: Commit runtime onboarding**

```bash
git add frontend/src/i18n/index.ts frontend/src/views/SettingsScreen.tsx frontend/tests/i18n.test.tsx frontend/tests/settingsScreen.test.tsx frontend/vite.config.ts src/config.py tests/test_web_api.py
git commit -m "feat: load registered locales with English fallback"
```

### Task 4: Documentation and end-to-end verification

**Files:**
- Modify: `docs/en/I18N.md`
- Modify: `docs/ru/I18N.md`
- Modify: `README.md`
- Modify: `docs/en/README.md` and `docs/ru/README.md` if they repeat a fixed-language claim
- Modify: `tests/test_new_locale.py` or locale check test only if documentation command examples expose an uncovered behavior

**Interfaces:**
- Docs describe `python scripts/new_locale.py <code> --name <native-name>`, catalog/TODO workflow, immediate UI availability, English fallback, and how to check completion.
- README language claims describe registered languages rather than only English and Russian.

- [ ] **Step 1: Update English and Russian localization guides**

Document the registry fields and rule, generator example (`es` / `Español`), what files are created, how to remove translated keys from the TODO list, that TODO keys render in English, and that empty TODO means complete. Describe validation output as progress information.

- [ ] **Step 2: Update README language claims**

Replace fixed “English and Russian” claims with registered/available interface languages without promising that every registered language is fully translated.

- [ ] **Step 3: Run all required checks**

Run from repository root:

```bash
pytest
python scripts/check_locales.py
python scripts/check_copy.py
```

Run from `frontend`:

```bash
npm test
npm run check:i18n-keys
npm run build
```

Expected: all checks pass; locale check reports `en` and `ru` complete, and fixture/generated incomplete locale status is covered in tests without leaving a draft in the product registry.

- [ ] **Step 4: Commit documentation and final verification**

```bash
git add docs/en/I18N.md docs/ru/I18N.md README.md docs/en/README.md docs/ru/README.md
git commit -m "docs: explain progressive locale workflow"
```

Record exact test/check outcomes in the implementation report; do not claim an exhaustive localization audit as part of this feature.
