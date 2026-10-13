#!/usr/bin/env python3
"""Generate a locale catalog and its untranslated-key list."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any


LOCALE_CODE = re.compile(r"^[a-z]{2,3}$")


def _leaves(value: Any, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        return [leaf for key in sorted(value) for leaf in _leaves(value[key], f"{prefix}.{key}" if prefix else key)]
    return [prefix]


def _write_new(path: Path, text: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o644)
    created: list[Path] = []
    replaced: list[tuple[Path, str]] = []
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _write_replace(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        _write_new(temporary, text)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _acquire_generation_lock(locale_dir: Path) -> Path:
    lock_path = locale_dir / ".new_locale.lock"
    try:
        descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        os.close(descriptor)
    except FileExistsError as error:
        raise ValueError("another locale generation is already in progress") from error
    return lock_path


def _validate_source(source: Any) -> None:
    if not isinstance(source, dict):
        raise ValueError("source catalog must be a JSON object")
    leaves = _leaves(source)
    if any(not leaf for leaf in leaves):
        raise ValueError("source catalog must contain named leaf values")
    values = _values(source)
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("source catalog must contain nonempty string values")
    validate_icu = _icu_validator()
    for value in values:
        if (error := validate_icu(value)) is not None:
            raise ValueError(f"source catalog contains invalid ICU: {error}")


def _values(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return [child for nested in value.values() for child in _values(nested)]
    return [value]


def _icu_validator():
    checker_path = Path(__file__).with_name("check_locales.py")
    spec = importlib.util.spec_from_file_location("music_lib_locale_checker", checker_path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load locale validator")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker.validate_icu


def generate_locale(code: str, name: str, locale_dir: Path) -> tuple[Path, Path]:
    """Create a copied catalog, TODO list, and registry entry without overwriting files."""
    if not LOCALE_CODE.fullmatch(code) or not name.strip():
        raise ValueError("locale code must be a lowercase 2-3 letter language code and name must be nonempty")
    source_path = locale_dir / "en.json"
    registry_path = locale_dir / "registry.json"
    catalog_path = locale_dir / f"{code}.json"
    todo_path = locale_dir / f"{code}.todo.json"
    package_registry_path = locale_dir.parents[2] / "src" / "locale_registry.json"
    if not locale_dir.is_dir():
        raise ValueError(f"locale directory does not exist: {locale_dir}")
    lock_path = _acquire_generation_lock(locale_dir)
    try:
        source = json.loads(source_path.read_text(encoding="utf-8"))
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        lock_path.unlink(missing_ok=True)
        raise ValueError(f"cannot read locale source or registry: {error}") from error
    created: list[Path] = []
    replaced: list[tuple[Path, str]] = []
    try:
        if not isinstance(source, dict) or not isinstance(registry, list):
            raise ValueError("English catalog must be an object and registry must be an array")
        _validate_source(source)
        if any(isinstance(entry, dict) and entry.get("code") == code for entry in registry):
            raise ValueError(f"locale is already registered: {code}")
        updated_registry = [*registry, {"code": code, "name": name.strip()}]
        registry_text = json.dumps(updated_registry, ensure_ascii=False, indent=2) + "\n"
        outputs = {
            catalog_path: json.dumps(source, ensure_ascii=False, indent=2) + "\n",
            todo_path: json.dumps(_leaves(source), ensure_ascii=False, indent=2) + "\n",
            registry_path: registry_text,
        }
        if catalog_path.exists() or todo_path.exists():
            raise ValueError(f"locale output already exists: {code}")
        _write_new(catalog_path, outputs[catalog_path])
        created.append(catalog_path)
        _write_new(todo_path, outputs[todo_path])
        created.append(todo_path)
        replaced.append((registry_path, registry_path.read_text(encoding="utf-8")))
        _write_replace(registry_path, outputs[registry_path])
        if package_registry_path.is_file():
            replaced.append((package_registry_path, package_registry_path.read_text(encoding="utf-8")))
            _write_replace(package_registry_path, registry_text)
    except BaseException:
        rollback_errors: list[Exception] = []
        for path, previous in reversed(replaced):
            try:
                _write_replace(path, previous)
            except Exception as rollback_error:
                rollback_errors.append(rollback_error)
        for path in created:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    finally:
        lock_path.unlink(missing_ok=True)
    return catalog_path, todo_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("code")
    parser.add_argument("--name", required=True)
    parser.add_argument("--locales", type=Path, default=Path("frontend/src/locales"))
    args = parser.parse_args(argv)
    try:
        generate_locale(args.code, args.name, args.locales)
    except ValueError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
