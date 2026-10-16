"""Лаунчеры scripts/run.py и scripts/dev.py: решения о сборке и запуск."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import dev as dev_mod  # noqa: E402
import launcher_lib as lib  # noqa: E402
import run as run_mod  # noqa: E402


def _touch(path: Path, delta: float = 0) -> None:
    """Создать файл с контролируемым mtime (сдвиг в секундах)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    st = path.stat()
    os.utime(path, (st.st_atime, st.st_mtime + delta))


class TestProjectRoot:
    def test_root_contains_pyproject(self):
        assert (lib.project_root() / "pyproject.toml").is_file()

    def test_root_contains_app(self):
        assert (lib.project_root() / "app.py").is_file()


class TestFindNpm:
    def test_none_when_missing(self, monkeypatch):
        monkeypatch.setattr(lib.shutil, "which", lambda _name: None)
        assert lib.find_npm() is None

    def test_finds_npm(self, monkeypatch):
        monkeypatch.setattr(
            lib.shutil, "which",
            lambda name: "/usr/bin/npm" if name == "npm" else None,
        )
        assert lib.find_npm() == "/usr/bin/npm"

    def test_ensure_npm_prints_hint(self, monkeypatch, capsys):
        monkeypatch.setattr(lib, "find_npm", lambda: None)
        assert lib.ensure_npm() is None
        assert "Node.js" in capsys.readouterr().err

    def test_ensure_npm_returns_path(self, monkeypatch):
        monkeypatch.setattr(lib, "find_npm", lambda: "/usr/bin/npm")
        assert lib.ensure_npm() == "/usr/bin/npm"


class TestNeedNpmInstall:
    def test_true_without_node_modules(self, tmp_path):
        assert lib.need_npm_install(tmp_path) is True

    def test_true_without_marker(self, tmp_path):
        (tmp_path / "node_modules").mkdir()
        assert lib.need_npm_install(tmp_path) is True

    def test_true_when_lock_newer(self, tmp_path):
        _touch(tmp_path / "node_modules" / ".package-lock.json", delta=0)
        _touch(tmp_path / "package-lock.json", delta=10)
        assert lib.need_npm_install(tmp_path) is True

    def test_false_when_install_fresh(self, tmp_path):
        _touch(tmp_path / "package-lock.json", delta=0)
        _touch(tmp_path / "node_modules" / ".package-lock.json", delta=10)
        assert lib.need_npm_install(tmp_path) is False


class TestNeedBuild:
    def _fresh_tree(self, root: Path) -> None:
        _touch(root / "src" / "web" / "dist" / "index.html", delta=100)
        _touch(root / "frontend" / "index.html", delta=0)
        _touch(root / "frontend" / "package.json", delta=0)
        _touch(root / "frontend" / "package-lock.json", delta=0)
        _touch(root / "frontend" / "vite.config.ts", delta=0)
        _touch(root / "frontend" / "tsconfig.json", delta=0)
        _touch(root / "frontend" / "src" / "App.tsx", delta=0)
        _touch(root / "frontend" / "src" / "views" / "X.tsx", delta=0)

    def test_true_when_dist_missing(self, tmp_path):
        assert lib.need_build(tmp_path) is True

    def test_false_when_dist_fresh(self, tmp_path):
        self._fresh_tree(tmp_path)
        assert lib.need_build(tmp_path) is False

    def test_true_when_source_newer(self, tmp_path):
        self._fresh_tree(tmp_path)
        _touch(tmp_path / "frontend" / "src" / "views" / "New.tsx", delta=200)
        assert lib.need_build(tmp_path) is True

    def test_true_when_lock_newer(self, tmp_path):
        self._fresh_tree(tmp_path)
        _touch(tmp_path / "frontend" / "package-lock.json", delta=200)
        assert lib.need_build(tmp_path) is True


class TestLogo:
    def test_logo_is_ascii(self):
        lib.LOGO.encode("ascii")

    def test_print_logo_outputs_art(self, capsys):
        lib.print_logo()
        out = capsys.readouterr().out
        assert out.strip() == lib.LOGO.strip()

    def test_run_prints_logo(self, monkeypatch, capsys):
        TestRunMain()._patch(monkeypatch)
        run_mod.main([])
        assert lib.LOGO.strip().splitlines()[0] in capsys.readouterr().out

    def test_dev_prints_logo(self, monkeypatch, capsys):
        procs = [_FakeProc(exit_code=0), _FakeProc()]
        TestDevMain()._patch(monkeypatch, procs)
        dev_mod.main([])
        assert lib.LOGO.strip().splitlines()[0] in capsys.readouterr().out


class TestRunMain:
    def _patch(self, monkeypatch, npm="/usr/bin/npm", install=False, build=False,
               cmd_code=0):
        cmds = []
        monkeypatch.setattr(run_mod, "ensure_npm", lambda: npm)
        monkeypatch.setattr(run_mod, "need_npm_install", lambda _fe: install)
        monkeypatch.setattr(run_mod, "need_build", lambda _root: build)
        monkeypatch.setattr(run_mod, "run_cmd",
                            lambda cmd, cwd: cmds.append(cmd) or cmd_code)
        launched = {}

        def fake_call(cmd, cwd=None):
            launched["cmd"] = cmd
            return 7

        monkeypatch.setattr(run_mod.subprocess, "call", fake_call)
        return cmds, launched

    def test_installs_playwright_chromium_when_missing(self, monkeypatch):
        cmds, launched = self._patch(monkeypatch)
        monkeypatch.setattr(run_mod, "chromium_installed", lambda: False)
        monkeypatch.setattr(run_mod, "playwright_installed", lambda: True)
        assert run_mod.main([]) == 7
        assert cmds == [[sys.executable, "-m", "playwright", "install", "chromium"]]
        assert launched

    def test_skips_playwright_install_when_chromium_exists(self, monkeypatch):
        cmds, _launched = self._patch(monkeypatch)
        monkeypatch.setattr(run_mod, "chromium_installed", lambda: True)
        monkeypatch.setattr(run_mod, "playwright_installed", lambda: True)
        run_mod.main([])
        assert cmds == []

    def test_continues_startup_when_playwright_install_fails(self, monkeypatch, capsys):
        cmds, launched = self._patch(monkeypatch, cmd_code=1)
        monkeypatch.setattr(run_mod, "chromium_installed", lambda: False)
        monkeypatch.setattr(run_mod, "playwright_installed", lambda: True)
        assert run_mod.main([]) == 7
        assert cmds == [[sys.executable, "-m", "playwright", "install", "chromium"]]
        assert launched
        assert "Не удалось установить Chromium; продолжаю запуск приложения." in capsys.readouterr().out

    def test_skips_chromium_install_when_playwright_missing(self, monkeypatch):
        cmds, launched = self._patch(monkeypatch)
        monkeypatch.setattr(run_mod, "chromium_installed", lambda: False)
        monkeypatch.setattr(run_mod, "playwright_installed", lambda: False)
        assert run_mod.main([]) == 7
        assert cmds == []
        assert launched

    def test_no_npm_returns_1(self, monkeypatch):
        cmds, launched = self._patch(monkeypatch, npm=None)
        monkeypatch.setattr(run_mod, "chromium_installed", lambda: True)
        assert run_mod.main(["--port", "9000"]) == 1
        assert cmds == []
        assert launched == {}

    def test_fresh_dist_skips_install_and_build(self, monkeypatch):
        cmds, launched = self._patch(monkeypatch)
        monkeypatch.setattr(run_mod, "chromium_installed", lambda: True)
        assert run_mod.main(["--port", "9000"]) == 7
        assert cmds == []
        assert launched["cmd"][2:] == ["--port", "9000"]

    def test_launches_app_with_sys_python(self, monkeypatch):
        _cmds, launched = self._patch(monkeypatch)
        monkeypatch.setattr(run_mod, "chromium_installed", lambda: True)
        run_mod.main([])
        assert launched["cmd"][0] == sys.executable
        assert launched["cmd"][1].endswith("app.py")

    def test_stale_runs_ci_build_then_app(self, monkeypatch):
        cmds, launched = self._patch(monkeypatch, install=True, build=True)
        monkeypatch.setattr(run_mod, "chromium_installed", lambda: True)
        assert run_mod.main([]) == 7
        assert cmds == [["/usr/bin/npm", "ci"], ["/usr/bin/npm", "run", "build"]]
        assert launched["cmd"][2:] == []

    def test_ci_failure_stops(self, monkeypatch):
        cmds, launched = self._patch(monkeypatch, install=True, cmd_code=3)
        monkeypatch.setattr(run_mod, "chromium_installed", lambda: True)
        assert run_mod.main([]) == 3
        assert cmds == [["/usr/bin/npm", "ci"]]
        assert launched == {}

    def test_build_failure_stops(self, monkeypatch):
        cmds, launched = self._patch(monkeypatch, build=True, cmd_code=4)
        monkeypatch.setattr(run_mod, "chromium_installed", lambda: True)
        assert run_mod.main([]) == 4
        assert launched == {}


def _raise_ki(_t):
    raise KeyboardInterrupt


class _FakeProc:
    def __init__(self, exit_code=None):
        self.exit_code = exit_code
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.exit_code

    def terminate(self):
        self.terminated = True
        self.exit_code = 0

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return self.exit_code


class TestDevMain:
    def _patch(self, monkeypatch, procs, sleep=None):
        started = []
        monkeypatch.setattr(dev_mod, "ensure_npm", lambda: "/usr/bin/npm")
        monkeypatch.setattr(dev_mod, "need_npm_install", lambda _fe: False)

        def fake_popen(cmd, cwd=None, env=None):
            started.append({"cmd": cmd, "cwd": cwd, "env": env})
            return procs[len(started) - 1]

        monkeypatch.setattr(dev_mod.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(dev_mod.time, "sleep", sleep or (lambda _t: None))
        return started

    def test_starts_backend_and_vite(self, monkeypatch):
        procs = [_FakeProc(), _FakeProc()]
        started = self._patch(monkeypatch, procs, sleep=_raise_ki)
        assert dev_mod.main([]) == 0
        backend, vite = started
        assert backend["cmd"][1].endswith("app.py")
        assert "--no-browser" in backend["cmd"]
        assert Path(backend["cwd"]).name != "frontend"
        assert vite["cmd"][1:] == ["run", "dev"]
        assert Path(vite["cwd"]).name == "frontend"
        assert vite["env"]["MUSIC_LIB_DEV_PORT"] == "8765"

    def test_ctrl_c_stops_both(self, monkeypatch):
        procs = [_FakeProc(), _FakeProc()]
        self._patch(monkeypatch, procs, sleep=_raise_ki)
        dev_mod.main([])
        assert all(p.terminated for p in procs)

    def test_backend_exit_stops_vite(self, monkeypatch):
        procs = [_FakeProc(exit_code=5), _FakeProc()]
        self._patch(monkeypatch, procs)
        assert dev_mod.main([]) == 5
        assert procs[1].terminated

    def test_vite_exit_stops_backend(self, monkeypatch):
        procs = [_FakeProc(), _FakeProc(exit_code=1)]
        self._patch(monkeypatch, procs)
        assert dev_mod.main([]) == 1
        assert procs[0].terminated

    def test_custom_port_and_rest_args(self, monkeypatch):
        procs = [_FakeProc(), _FakeProc()]
        started = self._patch(monkeypatch, procs, sleep=_raise_ki)
        dev_mod.main(["--port", "9000", "--host", "0.0.0.0"])
        backend, vite = started
        assert "--port" in backend["cmd"] and "9000" in backend["cmd"]
        assert "--host" in backend["cmd"] and "0.0.0.0" in backend["cmd"]
        assert vite["env"]["MUSIC_LIB_DEV_PORT"] == "9000"

    def test_no_npm_returns_1(self, monkeypatch):
        monkeypatch.setattr(dev_mod, "ensure_npm", lambda: None)
        started = []
        monkeypatch.setattr(dev_mod.subprocess, "Popen",
                            lambda *a, **k: started.append(1))
        assert dev_mod.main([]) == 1
        assert started == []

    def test_installs_deps_when_needed(self, monkeypatch):
        cmds = []
        monkeypatch.setattr(dev_mod, "ensure_npm", lambda: "/usr/bin/npm")
        monkeypatch.setattr(dev_mod, "need_npm_install", lambda _fe: True)
        monkeypatch.setattr(dev_mod, "run_cmd",
                            lambda cmd, cwd: cmds.append(cmd) or 0)
        backend_proc, vite_proc = _FakeProc(exit_code=0), _FakeProc()
        calls = []

        def fake_popen(cmd, cwd=None, env=None):
            calls.append(cmd)
            return backend_proc if len(calls) == 1 else vite_proc

        monkeypatch.setattr(dev_mod.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(dev_mod.time, "sleep", lambda _t: None)
        assert dev_mod.main([]) == 0
        assert cmds == [["/usr/bin/npm", "ci"]]
        assert vite_proc.terminated
