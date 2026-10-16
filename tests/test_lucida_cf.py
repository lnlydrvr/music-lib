import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

import src.lucida.cf as cf


def test_load_and_save_clearance_round_trip(tmp_path, monkeypatch):
    path = tmp_path / "clearance.json"
    monkeypatch.setattr(cf, "CLEARANCE_PATH", path)

    assert cf.load_clearance() == (None, None)
    cf.save_clearance("clearance-token", "Browser UA")

    payload = json.loads(path.read_text())
    assert payload["cf_clearance"] == "clearance-token"
    assert payload["ua"] == "Browser UA"
    assert isinstance(payload["ts"], (float, int))
    assert math.isfinite(payload["ts"])
    assert cf.load_clearance() == ("clearance-token", "Browser UA")


def test_expired_clearance_is_not_ready(tmp_path, monkeypatch):
    path = tmp_path / "clearance.json"
    path.write_text(json.dumps({"cf_clearance": "token", "ua": "UA", "ts": cf.time.time() - 24 * 3600 - 1}))
    monkeypatch.setattr(cf, "CLEARANCE_PATH", path)

    assert cf.load_clearance() == (None, None)


@pytest.mark.skipif(__import__("os").name != "posix", reason="file modes are POSIX-specific")
def test_load_clearance_rejects_group_or_world_readable_file_without_reading_it(tmp_path, monkeypatch):
    path = tmp_path / "clearance.json"
    path.write_text(json.dumps({"cf_clearance": "token", "ua": "UA", "ts": cf.time.time()}))
    path.chmod(0o644)
    monkeypatch.setattr(cf, "CLEARANCE_PATH", path)
    monkeypatch.setattr(Path, "read_text", lambda *_args, **_kwargs: pytest.fail("unsafe token file must not be read"))

    assert cf.load_clearance() == (None, None)


@pytest.mark.skipif(__import__("os").name != "posix", reason="file modes are POSIX-specific")
def test_load_clearance_accepts_owner_only_file(tmp_path, monkeypatch):
    path = tmp_path / "clearance.json"
    path.write_text(json.dumps({"cf_clearance": "token", "ua": "UA", "ts": cf.time.time()}))
    path.chmod(0o600)
    monkeypatch.setattr(cf, "CLEARANCE_PATH", path)

    assert cf.load_clearance() == ("token", "UA")


@pytest.mark.skipif(__import__("os").name != "posix", reason="file modes are POSIX-specific")
def test_save_clearance_uses_private_atomic_file_and_directories(tmp_path, monkeypatch):
    path = tmp_path / "config" / "lucida_clearance.json"
    monkeypatch.setattr(cf, "CLEARANCE_PATH", path)

    cf.save_clearance("token", "UA")

    assert path.stat().st_mode & 0o777 == 0o600
    assert path.parent.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize("contents", [
    "{bad json",
    "{}",
    '{"cf_clearance":"x"}',
    '{"cf_clearance":"x","ua":"ua"}',
    '{"cf_clearance":"x","ua":"ua","ts":"1"}',
    '{"cf_clearance":"x","ua":"ua","ts":"not-a-number"}',
    '{"cf_clearance":"x","ua":"ua","ts":Infinity}',
    '{"cf_clearance":"x","ua":"ua","ts":-Infinity}',
    '{"cf_clearance":"x","ua":"ua","ts":NaN}',
])
def test_load_clearance_returns_empty_for_invalid_file(tmp_path, monkeypatch, contents):
    path = tmp_path / "clearance.json"
    path.write_text(contents)
    monkeypatch.setattr(cf, "CLEARANCE_PATH", path)

    assert cf.load_clearance() == (None, None)


def test_cf_module_import_does_not_load_playwright():
    result = subprocess.run(
        [sys.executable, "-c", "import sys; import src.lucida.cf; assert 'playwright' not in sys.modules"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_chromium_installed_checks_executable_without_launching(monkeypatch, tmp_path):
    class Chromium:
        executable_path = str(tmp_path / "chromium")

    class Playwright:
        chromium = Chromium()

    class Manager:
        def __enter__(self):
            return Playwright()

        def __exit__(self, *args):
            pass

    import types

    playwright = types.ModuleType("playwright")
    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: Manager()
    monkeypatch.setitem(sys.modules, "playwright", playwright)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)
    Path(Chromium.executable_path).touch()
    assert cf.chromium_installed()

    assert not hasattr(Chromium, "launch")


def test_chromium_installed_returns_false_if_executable_lookup_fails(monkeypatch):
    class Chromium:
        @property
        def executable_path(self):
            raise OSError("unavailable")

    class Manager:
        def __enter__(self):
            return type("Playwright", (), {"chromium": Chromium()})()

        def __exit__(self, *args):
            pass

    import types

    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: Manager()
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)

    assert not cf.chromium_installed()


def test_chromium_installed_returns_false_when_playwright_sync_api_is_missing(monkeypatch):
    def missing_module(_name):
        raise ModuleNotFoundError("No module named 'playwright.sync_api'")

    monkeypatch.setattr(cf.importlib, "import_module", missing_module)

    assert not cf.chromium_installed()


def test_load_clearance_missing_file_does_not_create_config_dir(tmp_path, monkeypatch):
    path = tmp_path / "not-created" / "clearance.json"
    monkeypatch.setattr(cf, "CLEARANCE_PATH", path)
    assert cf.load_clearance() == (None, None)
    assert not path.parent.exists()


def test_acquire_visible_challenge_harvests_and_closes_context(tmp_path, monkeypatch):
    path = tmp_path / "config" / "clearance.json"
    monkeypatch.setattr(cf, "CLEARANCE_PATH", path)
    events = []

    class Page:
        def goto(self, url, **kwargs):
            events.append(("goto", url, kwargs))

        def evaluate(self, script):
            return "Browser UA"

        def wait_for_timeout(self, milliseconds):
            events.append(("wait", milliseconds))

    class Context:
        pages = [Page()]

        def cookies(self, url):
            return [{"name": "cf_clearance", "value": "token"}]

        def close(self):
            events.append(("close",))

    class Chromium:
        def launch_persistent_context(self, **kwargs):
            events.append(("launch", kwargs))
            return Context()

    class Manager:
        def __enter__(self):
            return type("Playwright", (), {"chromium": Chromium()})()

        def __exit__(self, *args):
            pass

    import types

    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: Manager()
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)

    assert cf.acquire(visible=True) == ("token", "Browser UA")
    launch = next(event[1] for event in events if event[0] == "launch")
    assert launch["headless"] is False
    assert next(event[1] for event in events if event[0] == "goto") == "https://lucida.to"
    assert events.count(("close",)) == 1
    assert cf.load_clearance() == ("token", "Browser UA")


def test_acquire_refuses_hidden_browser(tmp_path, monkeypatch):
    monkeypatch.setattr(cf, "CLEARANCE_PATH", tmp_path / "clearance.json")
    with pytest.raises(cf.ClearanceAccessError):
        cf.acquire(visible=False)


@pytest.mark.parametrize("failure_point", ["goto", "cookies", "evaluate", "timeout"])
def test_acquire_wraps_browser_failures_and_closes_once(tmp_path, monkeypatch, failure_point):
    monkeypatch.setattr(cf, "CLEARANCE_PATH", tmp_path / "clearance.json")
    closed = []

    class Page:
        def goto(self, url, **kwargs):
            if failure_point == "goto":
                raise RuntimeError("navigation failed")

        def evaluate(self, script):
            if failure_point == "evaluate":
                raise RuntimeError("UA failed")
            return "UA"

        def wait_for_timeout(self, milliseconds):
            raise RuntimeError("wait limit")

    class Context:
        pages = [Page()]

        def cookies(self, url):
            if failure_point == "cookies":
                raise RuntimeError("cookie read failed")
            if failure_point == "evaluate":
                return [{"name": "cf_clearance", "value": "token"}]
            return []

        def close(self):
            closed.append(True)

    class Chromium:
        def launch_persistent_context(self, **kwargs):
            return Context()

    class Manager:
        def __enter__(self):
            return type("Playwright", (), {"chromium": Chromium()})()

        def __exit__(self, *args):
            pass

    import types

    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: Manager()
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)
    if failure_point == "timeout":
        monkeypatch.setattr(cf.time, "monotonic", lambda: 1000)
        monkeypatch.setattr(cf.time, "sleep", lambda _: None)

    with pytest.raises(cf.ClearanceAccessError):
        cf.acquire()
    assert len(closed) == 1


def test_acquire_bounds_navigation_by_remaining_deadline(tmp_path, monkeypatch):
    monkeypatch.setattr(cf, "CLEARANCE_PATH", tmp_path / "clearance.json")
    goto_kwargs = []

    class Page:
        def goto(self, url, **kwargs):
            goto_kwargs.append(kwargs)
            raise RuntimeError("navigation stopped")

    class Context:
        pages = [Page()]

        def close(self):
            pass

    class Chromium:
        def launch_persistent_context(self, **kwargs):
            return Context()

    class Manager:
        def __enter__(self):
            return type("Playwright", (), {"chromium": Chromium()})()

        def __exit__(self, *args):
            pass

    import types

    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: Manager()
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)
    with pytest.raises(cf.ClearanceAccessError):
        cf.acquire()
    assert 0 < goto_kwargs[0]["timeout"] <= 180_000


def test_acquire_bounds_context_launch_by_total_deadline(tmp_path, monkeypatch):
    monkeypatch.setattr(cf, "CLEARANCE_PATH", tmp_path / "clearance.json")
    launch_kwargs = []

    class Chromium:
        def launch_persistent_context(self, **kwargs):
            launch_kwargs.append(kwargs)
            raise RuntimeError("launch stopped")

    class Manager:
        def __enter__(self):
            return type("Playwright", (), {"chromium": Chromium()})()

        def __exit__(self, *args):
            pass

    import types

    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: Manager()
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)
    with pytest.raises(cf.ClearanceAccessError):
        cf.acquire()
    assert 0 < launch_kwargs[0]["timeout"] <= 180_000
