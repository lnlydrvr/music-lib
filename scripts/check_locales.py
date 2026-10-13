#!/usr/bin/env python3
"""Validate JSON locale catalogs without requiring frontend dependencies."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any


REQUIRED_PLURAL_CATEGORIES = {
    "en": {"one", "other"},
    "ru": {"one", "few", "many", "other"},
}
ARGUMENT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
LOCALE_CODE = re.compile(r"^[a-z]{2,3}$")


def _leaves(value: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for key in sorted(value):
            child_key = f"{prefix}.{key}" if prefix else key
            yield from _leaves(value[key], child_key)
    else:
        yield prefix, value


def _matching_brace(text: str, opening: int) -> int | None:
    depth = 0
    quoted = False
    index = opening
    while index < len(text):
        char = text[index]
        if char == "'":
            if index + 1 < len(text) and text[index + 1] == "'":
                index += 2
                continue
            if quoted or (index + 1 < len(text) and text[index + 1] in "{}'"):
                quoted = not quoted
        elif not quoted and char == "{":
            depth += 1
        elif not quoted and char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _split_top_level(value: str, limit: int = 2) -> list[str]:
    parts: list[str] = []
    depth = 0
    quoted = False
    start = 0
    for index, char in enumerate(value):
        if char == "'":
            if quoted or (index + 1 < len(value) and value[index + 1] in "{}'"):
                quoted = not quoted
        elif not quoted and char == "{":
            depth += 1
        elif not quoted and char == "}":
            depth -= 1
        elif not quoted and char == "," and depth == 0 and len(parts) < limit:
            parts.append(value[start:index].strip())
            start = index + 1
    parts.append(value[start:].strip())
    return parts


def _plural_categories(body: str) -> set[str]:
    categories: set[str] = set()
    index = 0
    while index < len(body):
        match = re.search(r"(?:^|\s)(=?-?\d+|[A-Za-z][A-Za-z0-9]*)\s*\{", body[index:])
        if match is None:
            break
        category = match.group(1)
        opening = index + match.end() - 1
        closing = _matching_brace(body, opening)
        if closing is None:
            break
        categories.add(category)
        index = closing + 1
    return categories


def _option_messages(body: str) -> Iterator[str]:
    """Yield ICU option bodies, excluding their selector labels."""
    index = 0
    while index < len(body):
        match = re.search(r"(?:^|\s)(=?[A-Za-z0-9]+)\s*\{", body[index:])
        if match is None:
            return
        opening = index + match.end() - 1
        closing = _matching_brace(body, opening)
        if closing is None:
            return
        yield body[opening + 1:closing]
        index = closing + 1


def icu_argument_kinds(message: str) -> dict[str, str]:
    """Return each ICU argument's presentation kind (simple/select/plural)."""
    kinds: dict[str, str] = {}
    index = 0
    quoted = False
    while index < len(message):
        if message[index] == "'":
            if index + 1 < len(message) and message[index + 1] == "'":
                index += 2
                continue
            if quoted or (index + 1 < len(message) and message[index + 1] in "{}'"):
                quoted = not quoted
            index += 1
            continue
        if quoted:
            index += 1
            continue
        if message[index] != "{":
            index += 1
            continue
        closing = _matching_brace(message, index)
        if closing is None:
            index += 1
            continue
        parts = _split_top_level(message[index + 1:closing])
        name = parts[0] if parts else ""
        if ARGUMENT_NAME.fullmatch(name):
            kind = parts[1] if len(parts) >= 2 else "simple"
            kinds[name] = kind
            if len(parts) >= 3 and kind in {"plural", "select", "selectordinal"}:
                for option in _option_messages(parts[2]):
                    kinds.update(icu_argument_kinds(option))
        index = closing + 1
    return kinds


def icu_contract(message: str) -> tuple[set[str], dict[str, set[str]]]:
    """Return interpolation arguments and plural categories for an ICU message."""
    arguments: set[str] = set()
    plurals: dict[str, set[str]] = {}
    index = 0
    quoted = False
    while index < len(message):
        if message[index] == "'":
            if index + 1 < len(message) and message[index + 1] == "'":
                index += 2
                continue
            if quoted or (index + 1 < len(message) and message[index + 1] in "{}'"):
                quoted = not quoted
            index += 1
            continue
        if quoted:
            index += 1
            continue
        if message[index] != "{":
            index += 1
            continue
        closing = _matching_brace(message, index)
        if closing is None:
            index += 1
            continue
        parts = _split_top_level(message[index + 1:closing])
        name = parts[0] if parts else ""
        if ARGUMENT_NAME.fullmatch(name):
            arguments.add(name)
            if len(parts) >= 3 and parts[1] in {"plural", "selectordinal"}:
                plurals[name] = _plural_categories(parts[2])
        if len(parts) >= 3 and parts[1] in {"plural", "select", "selectordinal"}:
            for option in _option_messages(parts[2]):
                nested_arguments, nested_plurals = icu_contract(option)
                arguments.update(nested_arguments)
                plurals.update(nested_plurals)
        index = closing + 1
    return arguments, plurals


def validate_icu(message: str) -> str | None:
    """Return a syntax error for malformed ICU messages."""
    def parse_message(index: int, stop_at_closing: bool = False) -> int:
        quoted = False
        while index < len(message):
            char = message[index]
            if char == "'":
                if index + 1 < len(message) and message[index + 1] == "'":
                    index += 2
                    continue
                if quoted or (index + 1 < len(message) and message[index + 1] in "{}'"):
                    quoted = not quoted
                index += 1
                continue
            if quoted:
                index += 1
                continue
            if char == "}":
                if stop_at_closing:
                    return index + 1
                raise ValueError("unexpected closing brace")
            if char != "{":
                index += 1
                continue
            index = parse_argument(index + 1)
        if stop_at_closing:
            raise ValueError("missing closing brace")
        if quoted:
            raise ValueError("unterminated quoted text")
        return index

    def parse_argument(index: int) -> int:
        start = index
        depth = 0
        while index < len(message):
            char = message[index]
            if char == "{" :
                depth += 1
            elif char == "}":
                if depth:
                    depth -= 1
                else:
                    break
            elif char == "," and depth == 0:
                break
            index += 1
        name = message[start:index].strip()
        if not ARGUMENT_NAME.fullmatch(name):
            raise ValueError("invalid argument name")
        if index >= len(message):
            raise ValueError("missing closing brace")
        if message[index] == "}":
            return index + 1
        index += 1
        kind_start = index
        while index < len(message) and message[index] not in ",}":
            index += 1
        kind = message[kind_start:index].strip()
        if kind not in {"plural", "select", "selectordinal"}:
            raise ValueError(f"unknown argument type: {kind}")
        if index >= len(message) or message[index] == "}":
            raise ValueError("missing ICU options")
        index += 1
        option_count = 0
        while index < len(message) and message[index] != "}":
            while index < len(message) and message[index].isspace():
                index += 1
            label_start = index
            while index < len(message) and not message[index].isspace() and message[index] != "{":
                index += 1
            label = message[label_start:index]
            while index < len(message) and message[index].isspace():
                index += 1
            valid_label = bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", label))
            if kind in {"plural", "selectordinal"}:
                valid_label = bool(re.fullmatch(r"(?:[A-Za-z][A-Za-z0-9]*|=-?\d+)", label))
            if not valid_label or index >= len(message) or message[index] != "{":
                raise ValueError("invalid ICU option")
            option_count += 1
            index = parse_message(index + 1, stop_at_closing=True)
        if option_count == 0 or index >= len(message) or message[index] != "}":
            raise ValueError("missing ICU option or closing brace")
        return index + 1

    try:
        parse_message(0)
    except ValueError as error:
        return str(error)
    return None


def _load_catalog(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        catalog = json.load(handle)
    if not isinstance(catalog, dict):
        raise ValueError("catalog root must be a JSON object")
    return catalog


def _load_registry(locale_dir: Path) -> tuple[list[dict[str, str]], list[str]]:
    path = locale_dir / "registry.json"
    if not path.is_file():
        return [], [f"registry: file not found: {path}"]
    errors: list[str] = []
    try:
        with path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [], [f"registry: invalid registry: {error}"]
    if not isinstance(raw, list):
        return [], ["registry: registry root must be an array"]
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict) or not isinstance(entry.get("code"), str) or not isinstance(entry.get("name"), str):
            errors.append(f"registry: invalid entry {index}")
            continue
        code, name = entry["code"], entry["name"]
        if not LOCALE_CODE.fullmatch(code) or not name.strip() or code in seen:
            errors.append(f"registry: invalid or duplicate locale {code}")
            continue
        seen.add(code)
        entries.append({"code": code, "name": name})
    if "en" not in seen:
        errors.append("registry: en locale is required")
    return entries, errors


def _load_todo(path: Path, source_keys: set[str], locale: str) -> tuple[list[str], list[str]]:
    if locale == "en" and path.exists():
        return [], ["en: TODO file is not allowed"]
    if not path.exists():
        if locale != "en":
            return [], [f"{locale}: TODO file not found"]
        return [], []
    try:
        with path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return [], [f"{locale}: invalid TODO: {error}"]
    if not isinstance(raw, list) or any(not isinstance(key, str) for key in raw):
        return [], [f"{locale}: invalid TODO: expected a list of strings"]
    if len(raw) != len(set(raw)):
        return [], [f"{locale}: invalid TODO: duplicate keys"]
    invalid = sorted(key for key in raw if key not in source_keys)
    if invalid:
        return [], [f"{locale}: invalid TODO: unknown keys {', '.join(invalid)}"]
    if locale == "ru" and raw:
        return sorted(raw), ["ru: TODO file must be empty"]
    return sorted(raw), []


def locale_status(locale_dir: Path) -> dict[str, list[str]]:
    """Return untranslated keys by registered locale."""
    registry, _ = _load_registry(locale_dir)
    source = dict(_leaves(_load_catalog(locale_dir / "en.json")))
    status: dict[str, list[str]] = {}
    for entry in registry:
        code = entry["code"]
        todo, _ = _load_todo(locale_dir / f"{code}.todo.json", set(source), code)
        status[code] = todo
    return status


def validate_catalogs(locale_dir: Path, source_locale: str = "en") -> list[str]:
    """Return deterministic catalog contract violations for every locale JSON file."""
    registry, errors = _load_registry(locale_dir)
    source_path = locale_dir / f"{source_locale}.json"
    if not source_path.is_file():
        return errors + [f"{source_locale}: source catalog not found: {source_path}"]
    source = dict(_leaves(_load_catalog(source_path)))
    registered = {entry["code"] for entry in registry}
    for entry in registry:
        code = entry["code"]
        if not (locale_dir / f"{code}.json").is_file():
            errors.append(f"{code}: catalog not found")
    for path in locale_dir.glob("*.json"):
        code = path.stem
        if code.endswith(".todo"):
            continue
        if code not in registered and code != "registry":
            errors.append(f"{code}: catalog is not registered")
    todo_by_locale: dict[str, set[str]] = {}
    for entry in registry:
        code = entry["code"]
        todo, todo_errors = _load_todo(locale_dir / f"{code}.todo.json", set(source), code)
        errors.extend(todo_errors)
        todo_by_locale[code] = set(todo)
    for path in locale_dir.glob("*.todo.json"):
        if path.stem.removesuffix(".todo") not in registered:
            errors.append(f"{path.stem}: TODO locale is not registered")
    errors.extend(_source_errors(source, source_locale))
    for path in sorted(locale_dir.rglob("*.json")):
        locale = path.relative_to(locale_dir).with_suffix("").as_posix()
        if locale == source_locale or locale == "registry" or locale.endswith(".todo") or locale not in registered:
            continue
        try:
            translated = dict(_leaves(_load_catalog(path)))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            errors.append(f"{locale}: invalid JSON catalog: {error}")
            continue
        for key in sorted(source.keys() - translated.keys()):
            errors.append(f"{locale}: missing key {key}")
        for key in sorted(translated.keys() - source.keys()):
            errors.append(f"{locale}: extra key {key}")
        for key in sorted(source.keys() & translated.keys()):
            value = translated[key]
            if not isinstance(value, str) or (not value.strip() and key not in todo_by_locale.get(locale, set())):
                errors.append(f"{locale}: empty value {key}")
                continue
            source_value = source[key]
            if not isinstance(source_value, str):
                errors.append(f"{source_locale}: value must be a string {key}")
                continue
            for message_locale, message_value in ((source_locale, source_value), (locale, value)):
                if (icu_error := validate_icu(message_value)) is not None:
                    errors.append(f"{message_locale}: invalid ICU for {key}: {icu_error}")
            source_args, _ = icu_contract(source_value)
            translated_args, translated_plurals = icu_contract(value)
            if source_args != translated_args:
                errors.append(f"{locale}: ICU arguments differ for {key} (expected {sorted(source_args)}, got {sorted(translated_args)})")
            source_kinds = icu_argument_kinds(source_value)
            translated_kinds = icu_argument_kinds(value)
            for argument in sorted(source_kinds.keys() & translated_kinds.keys()):
                if source_kinds[argument] != translated_kinds[argument]:
                    errors.append(
                        f"{locale}: ICU argument kind differs for {key}.{argument} "
                        f"(expected {source_kinds[argument]}, got {translated_kinds[argument]})"
                    )
            for argument, categories in sorted(translated_plurals.items()):
                required = REQUIRED_PLURAL_CATEGORIES.get(locale)
                if required:
                    missing = sorted(required - categories)
                    unsupported = sorted(category for category in categories if not category.startswith("=") and category not in required)
                    if missing:
                        errors.append(f"{locale}: plural categories for {key}.{argument} must include {', '.join(missing)}")
                    if unsupported:
                        errors.append(f"{locale}: plural categories for {key}.{argument} are invalid: {', '.join(unsupported)}")
    return errors


def _source_errors(source: dict[str, Any], source_locale: str) -> list[str]:
    errors: list[str] = []
    for key, value in sorted(source.items()):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{source_locale}: empty value {key}")
            continue
        if (icu_error := validate_icu(value)) is not None:
            errors.append(f"{source_locale}: invalid ICU for {key}: {icu_error}")
        _, plurals = icu_contract(value)
        for argument, categories in sorted(plurals.items()):
            required = REQUIRED_PLURAL_CATEGORIES.get(source_locale)
            if required:
                missing = sorted(required - categories)
                unsupported = sorted(category for category in categories if not category.startswith("=") and category not in required)
                if missing:
                    errors.append(f"{source_locale}: plural categories for {key}.{argument} must include {', '.join(missing)}")
                if unsupported:
                    errors.append(f"{source_locale}: plural categories for {key}.{argument} are invalid: {', '.join(unsupported)}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locales", type=Path, default=Path("frontend/src/locales"))
    args = parser.parse_args(argv)
    errors = validate_catalogs(args.locales)
    if errors:
        print("Locale catalog validation failed:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"Locale catalogs validated: {args.locales}")
    for locale, keys in sorted(locale_status(args.locales).items()):
        print(f"{locale}: {len(keys)} untranslated key(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
