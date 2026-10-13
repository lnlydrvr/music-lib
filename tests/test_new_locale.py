import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("new_locale", ROOT / "scripts" / "new_locale.py")
assert SPEC and SPEC.loader
new_locale = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(new_locale)


def setup_locale_dir(tmp_path: Path) -> Path:
    locale_dir = tmp_path / "locales"
    locale_dir.mkdir()
    (locale_dir / "en.json").write_text(json.dumps({"nav": {"home": "Home"}, "count": "{count}"}), encoding="utf-8")
    (locale_dir / "registry.json").write_text(json.dumps([
        {"code": "en", "name": "English"}, {"code": "ru", "name": "Русский"}
    ]), encoding="utf-8")
    return locale_dir


def test_generate_locale_copies_source_and_marks_every_leaf_pending(tmp_path):
    locale_dir = setup_locale_dir(tmp_path)

    catalog_path, todo_path = new_locale.generate_locale("es", "Español", locale_dir)

    assert json.loads(catalog_path.read_text()) == {"nav": {"home": "Home"}, "count": "{count}"}
    assert json.loads(todo_path.read_text()) == ["count", "nav.home"]
    assert {entry["code"] for entry in json.loads((locale_dir / "registry.json").read_text())} == {"en", "ru", "es"}


@pytest.mark.parametrize("code", ["../es", "es_MX", "ES", "", "a"])
def test_generate_locale_rejects_invalid_codes_without_writing(tmp_path, code):
    locale_dir = setup_locale_dir(tmp_path)

    with pytest.raises(ValueError):
        new_locale.generate_locale(code, "Español", locale_dir)

    assert sorted(path.name for path in locale_dir.iterdir()) == ["en.json", "registry.json"]


def test_generate_locale_refuses_existing_output(tmp_path):
    locale_dir = setup_locale_dir(tmp_path)
    (locale_dir / "es.json").write_text("existing", encoding="utf-8")

    with pytest.raises(ValueError, match="already exists"):
        new_locale.generate_locale("es", "Español", locale_dir)

    assert (locale_dir / "es.json").read_text() == "existing"


def test_generate_locale_rejects_invalid_source_catalog(tmp_path):
    locale_dir = setup_locale_dir(tmp_path)
    (locale_dir / "en.json").write_text(json.dumps({"greeting": ""}), encoding="utf-8")

    with pytest.raises(ValueError, match="source catalog"):
        new_locale.generate_locale("es", "Español", locale_dir)


def test_generate_locale_does_not_accept_malformed_source_icu(tmp_path):
    locale_dir = setup_locale_dir(tmp_path)
    (locale_dir / "en.json").write_text(json.dumps({"count": "{count, plural, one {# item}"}), encoding="utf-8")

    with pytest.raises(ValueError, match="source catalog"):
        new_locale.generate_locale("es", "Español", locale_dir)


def test_generate_locale_updates_package_registry_when_using_repository_locales(tmp_path, monkeypatch):
    locale_dir = setup_locale_dir(tmp_path)
    package_registry = locale_dir.parents[2] / "src" / "locale_registry.json"
    package_registry.parent.mkdir(parents=True, exist_ok=True)
    package_registry.write_text("[]", encoding="utf-8")

    new_locale.generate_locale("es", "Español", locale_dir)

    assert json.loads(package_registry.read_text())[-1] == {"code": "es", "name": "Español"}


def test_generate_locale_rolls_back_when_package_registry_write_fails(tmp_path, monkeypatch):
    locale_dir = setup_locale_dir(tmp_path)
    package_registry = locale_dir.parents[2] / "src" / "locale_registry.json"
    package_registry.parent.mkdir(parents=True, exist_ok=True)
    package_registry.write_text("[]", encoding="utf-8")
    original_replace = new_locale._write_replace

    def fail_package_registry(path: Path, text: str) -> None:
        if path == package_registry:
            raise OSError("package registry unavailable")
        original_replace(path, text)

    monkeypatch.setattr(new_locale, "_write_replace", fail_package_registry)

    with pytest.raises(OSError, match="package registry unavailable"):
        new_locale.generate_locale("es", "Español", locale_dir)

    assert json.loads((locale_dir / "registry.json").read_text()) == [
        {"code": "en", "name": "English"}, {"code": "ru", "name": "Русский"}
    ]
    assert json.loads(package_registry.read_text()) == []
    assert not (locale_dir / "es.json").exists()
    assert not (locale_dir / "es.todo.json").exists()
