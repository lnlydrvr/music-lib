"""Tests for sticky YouTube-cookie source (src/ytcookies.py + config)."""
from __future__ import annotations

from pathlib import Path

import pytest

import src.config as config
from src import ytcookies as ytc


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Перенаправить конфиг в временную папку (как в test_config.py)."""
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    cfg_dir = home / ".config" / "music-lib"
    monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config, "CONFIG_PATH", cfg_dir / "config.json")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    return cfg_dir


class TestPreferredFirst:
    def test_empty_prefer_keeps_order(self):
        cands = [{"a": 1}, {"b": 2}]
        assert ytc.preferred_first(cands, "") == cands
        assert ytc.preferred_first(cands, None) == cands

    def test_unknown_prefer_keeps_order(self):
        cands = [{"cookiesfrombrowser": ("safari",)}, {}]
        assert ytc.preferred_first(cands, "chrome") == cands

    def test_known_prefer_moves_first(self):
        anon: dict = {}
        safari = {"cookiesfrombrowser": ("safari",)}
        cands = [safari, anon]
        assert ytc.preferred_first(cands, "без cookies") == [anon, safari]

    def test_profile_label_roundtrip(self):
        opt = {"cookiesfrombrowser": ("safari", "/x/WebsiteDataStore/d7b4ace1-zzz/Cookies/Cookies.binarycookies")}
        assert ytc.describe_source(opt) == "safari:профиль D7B4ACE1"
        cands = [opt, {}]
        assert ytc.preferred_first(cands, "safari:профиль D7B4ACE1")[0] == opt


class TestStickyPersistence:
    def test_remember_and_get(self, isolated_home):
        assert ytc.get_preferred_source() == ""
        ytc.remember_working_source({"cookiesfrombrowser": ("safari",)})
        assert ytc.get_preferred_source() == "safari"
        assert config.load_config()["youtube_cookie_source"] == "safari"

    def test_reorder_uses_stored(self, isolated_home, monkeypatch):
        ytc.remember_working_source({})
        monkeypatch.setattr(
            ytc, "cookie_opt_candidates",
            lambda **kw: [{"cookiesfrombrowser": ("safari",)}, {}],
        )
        from src.downloader import Downloader

        # метод не трогает self — вызываем как функцию
        ordered = Downloader._cookie_candidates(None)
        assert ordered[0] == {}
