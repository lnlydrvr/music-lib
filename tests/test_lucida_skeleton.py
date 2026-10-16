import importlib
import subprocess
import sys
from pathlib import Path

import src.lucida.paths as lucida_paths
from src.lucida.services import AMAZON_STOREFRONTS, default_country, normalize_service


def test_lucida_paths_follow_music_lib_config_convention(monkeypatch, tmp_path):
    home = tmp_path / "home"
    try:
        with monkeypatch.context() as scoped:
            scoped.setattr(Path, "home", staticmethod(lambda: home))
            paths = importlib.reload(lucida_paths)

            assert paths.CONFIG_DIR == home / ".config" / "music-lib"
            assert paths.CLEARANCE_PATH == paths.CONFIG_DIR / "lucida_clearance.json"
            assert paths.LOG_PATH == paths.CONFIG_DIR / "lucida.log"
            assert not paths.CONFIG_DIR.exists()
    finally:
        importlib.reload(lucida_paths)


def test_lucida_paths_are_restored_after_test_home_override():
    assert lucida_paths.CONFIG_DIR == Path.home() / ".config" / "music-lib"


def test_service_helpers_normalize_and_supply_defaults():
    assert normalize_service("  QOBUZ ") == "qobuz"
    assert default_country("qobuz") == "NL"
    assert default_country("amazon") == ""
    assert AMAZON_STOREFRONTS == ["", "US", "GB", "JP"]


def test_lucida_imports_do_not_load_optional_libraries():
    script = """
import importlib
import sys

import src.lucida
import src.lucida.paths
import src.lucida.services

for module in (src.lucida, src.lucida.paths, src.lucida.services):
    importlib.reload(module)

for root in ("httpx", "playwright", "pyjson5"):
    assert not any(name == root or name.startswith(root + ".") for name in sys.modules), root
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_available_detects_playwright_without_importing_optional_modules(monkeypatch):
    import src.lucida as lucida

    monkeypatch.setattr(lucida.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(
        lucida.importlib,
        "import_module",
        lambda name: (_ for _ in ()).throw(AssertionError(f"available() imported {name}")),
    )

    assert lucida.available() is True


def test_available_call_does_not_import_optional_modules_in_fresh_process():
    script = """
import sys
import src.lucida as lucida

lucida.available()

for root in ("httpx", "playwright", "pyjson5"):
    assert not any(name == root or name.startswith(root + ".") for name in sys.modules), root
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
