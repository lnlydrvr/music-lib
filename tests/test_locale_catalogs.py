"""Behavioral tests for the locale-catalog validation command."""

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("check_locales", ROOT / "scripts" / "check_locales.py")
assert SPEC and SPEC.loader
check_locales = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_locales)


def write_catalogs(tmp_path: Path, en: dict, ru: dict) -> Path:
    """Write the smallest complete catalog pair used by one assertion."""
    locale_dir = tmp_path / "locales"
    locale_dir.mkdir()
    (locale_dir / "en.json").write_text(json.dumps(en))
    (locale_dir / "ru.json").write_text(json.dumps(ru))
    (locale_dir / "ru.todo.json").write_text("[]")
    write_registry(locale_dir, [{"code": "en", "name": "English"}, {"code": "ru", "name": "Русский"}])
    return locale_dir


def write_registry(locale_dir: Path, entries: list[dict[str, str]]) -> None:
    (locale_dir / "registry.json").write_text(json.dumps(entries), encoding="utf-8")


def test_valid_catalogs_allow_locale_specific_plural_categories(tmp_path):
    locale_dir = write_catalogs(
        tmp_path,
        {"greeting": "Hi, {name}", "tracks": "{count, plural, one {# track} other {# tracks}}"},
        {"greeting": "Привет, {name}", "tracks": "{count, plural, one {# трек} few {# трека} many {# треков} other {# трека}}"},
    )

    assert check_locales.validate_catalogs(locale_dir) == []


def test_todo_keys_are_reported_as_incomplete_without_failing_validation(tmp_path):
    locale_dir = write_catalogs(tmp_path, {"greeting": "Hello"}, {"greeting": "Hola"})
    (locale_dir / "es.json").write_text(json.dumps({"greeting": "Hola"}), encoding="utf-8")
    write_registry(locale_dir, [{"code": "en", "name": "English"}, {"code": "ru", "name": "Русский"}, {"code": "es", "name": "Español"}])
    (locale_dir / "es.todo.json").write_text(json.dumps(["greeting"]), encoding="utf-8")

    assert check_locales.validate_catalogs(locale_dir) == []
    assert check_locales.locale_status(locale_dir)["es"] == ["greeting"]


def test_registered_non_english_locale_requires_todo_file(tmp_path):
    locale_dir = write_catalogs(tmp_path, {"greeting": "Hello"}, {"greeting": "Привет"})
    write_registry(locale_dir, [{"code": "en", "name": "English"}, {"code": "ru", "name": "Русский"}])
    (locale_dir / "ru.todo.json").unlink()

    assert "ru: TODO file not found" in check_locales.validate_catalogs(locale_dir)


def test_ru_todo_file_must_be_empty(tmp_path):
    locale_dir = write_catalogs(tmp_path, {"greeting": "Hello"}, {"greeting": "Привет"})
    write_registry(locale_dir, [{"code": "en", "name": "English"}, {"code": "ru", "name": "Русский"}])
    (locale_dir / "ru.todo.json").write_text(json.dumps(["greeting"]), encoding="utf-8")

    assert "ru: TODO file must be empty" in check_locales.validate_catalogs(locale_dir)


@pytest.mark.parametrize("todo", [["missing"], ["greeting", "greeting"], [1]])
def test_invalid_todo_keys_are_reported(tmp_path, todo):
    locale_dir = write_catalogs(tmp_path, {"greeting": "Hello"}, {"greeting": "Привет"})
    write_registry(locale_dir, [{"code": "en", "name": "English"}, {"code": "ru", "name": "Русский"}])
    (locale_dir / "ru.todo.json").write_text(json.dumps(todo), encoding="utf-8")

    assert any(error.startswith("ru: invalid TODO") for error in check_locales.validate_catalogs(locale_dir))


def test_source_catalog_requires_its_own_plural_categories(tmp_path):
    locale_dir = write_catalogs(
        tmp_path,
        {"tracks": "{count, plural, other {# tracks}}"},
        {"tracks": "{count, plural, one {# трек} few {# трека} many {# треков} other {# трека}}"},
    )

    assert "en: plural categories for tracks.count must include one" in check_locales.validate_catalogs(locale_dir)


@pytest.mark.parametrize("message", [
    "{count, plural, one {# track} other {# tracks}",
    "{count, unknown, one {# track} other {# tracks}}",
    "{count, plural, one # track other {# tracks}}",
])
def test_catalogs_reject_malformed_icu(tmp_path, message):
    locale_dir = write_catalogs(tmp_path, {"tracks": message}, {"tracks": message})

    assert any(error.startswith("en: invalid ICU for tracks") for error in check_locales.validate_catalogs(locale_dir))


def test_catalogs_accept_icu_quoted_braces_and_nested_messages(tmp_path):
    source = "It's '{literal}' {count, plural, one {{status, select, ok {OK} other {not ok}}} other {many}}"
    translated = "It's '{literal}' {count, plural, one {{status, select, ok {OK} other {not ok}}} few {few} many {many} other {other}}"
    locale_dir = write_catalogs(tmp_path, {"message": source}, {"message": translated})

    assert check_locales.validate_catalogs(locale_dir) == []


def test_catalogs_reject_icu_option_selector_commas(tmp_path):
    message = "{count, plural, one, {one} other {many}}"
    locale_dir = write_catalogs(tmp_path, {"message": message}, {"message": message})

    assert any(error.startswith("en: invalid ICU for message") for error in check_locales.validate_catalogs(locale_dir))


@pytest.mark.parametrize("message", ["{count, plural, =x {one} other {many}}", "{count, plural, = {one} other {many}}"])
def test_catalogs_reject_invalid_icu_exact_selectors(tmp_path, message):
    locale_dir = write_catalogs(tmp_path, {"message": message}, {"message": message})

    assert any(error.startswith("en: invalid ICU for message") for error in check_locales.validate_catalogs(locale_dir))


@pytest.mark.parametrize(
    ("en_message", "ru_message", "expected"),
    [
        (
            "{count, plural, one {# track} other {# tracks}}",
            "{count, select, one {один} other {много}}",
            "ru: ICU argument kind differs for tracks.count (expected plural, got select)",
        ),
        (
            "{status, select, ready {Ready} other {Unknown}}",
            "{status}",
            "ru: ICU argument kind differs for status.status (expected select, got simple)",
        ),
        (
            "{count, plural, one {# track} other {# tracks}}",
            "{count}",
            "ru: ICU argument kind differs for tracks.count (expected plural, got simple)",
        ),
    ],
)
def test_catalogs_reject_icu_argument_kind_mismatches(tmp_path, en_message, ru_message, expected):
    locale_dir = write_catalogs(tmp_path, {"tracks": en_message} if "count" in en_message else {"status": en_message}, {"tracks": ru_message} if "count" in ru_message else {"status": ru_message})

    assert expected in check_locales.validate_catalogs(locale_dir)


@pytest.mark.parametrize(
    ("en", "ru", "expected"),
    [
        ({"group": {"name": "Name"}}, {"group": {}}, "ru: missing key group.name"),
        ({"group": {}}, {"group": {"name": "Имя"}}, "ru: extra key group.name"),
        ({"name": "Name"}, {"name": "   "}, "ru: empty value name"),
        ({"greeting": "Hi, {name}"}, {"greeting": "Привет, {user}"}, "ru: ICU arguments differ for greeting"),
        (
            {"tracks": "{count, plural, one {# track} other {# tracks}}"},
            {"tracks": "{count, plural, one {# трек} other {# трека}}"},
            "ru: plural categories for tracks.count must include few, many",
        ),
    ],
)
def test_invalid_catalogs_report_locale_key_and_contract_problem(tmp_path, en, ru, expected):
    locale_dir = write_catalogs(tmp_path, en, ru)

    errors = check_locales.validate_catalogs(locale_dir)

    assert any(error.startswith(expected) for error in errors)
