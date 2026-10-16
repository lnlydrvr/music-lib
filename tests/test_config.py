"""Tests for src/config.py — priоритеты каталога вывода. All IO mocked."""
import json
import threading
from pathlib import Path

import pytest

import src.config as config


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Перенаправить конфиг и home в временную папку."""
    home = tmp_path / "home"
    home.mkdir()
    cfg_dir = home / ".config" / "music-lib"
    monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config, "CONFIG_PATH", cfg_dir / "config.json")
    monkeypatch.setattr(config, "_ICLOUD_DIR", home / "iCloud")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    return home


@pytest.fixture
def no_cloud(monkeypatch):
    monkeypatch.setattr(config, "cloud_dir_available", lambda: False)


@pytest.fixture
def with_cloud(monkeypatch):
    monkeypatch.setattr(config, "cloud_dir_available", lambda: True)


@pytest.fixture
def no_env(monkeypatch):
    monkeypatch.delenv("MUSIC_LIB_DIR", raising=False)
    monkeypatch.delenv("MUSIC_DL_DIR", raising=False)


class TestDefaultOutputDir:
    def test_falls_back_to_music_when_no_cloud(self, isolated_home, no_cloud):
        assert config.default_output_dir() == isolated_home / "Music"

    def test_uses_icloud_when_available(self, isolated_home, with_cloud):
        assert config.default_output_dir() == isolated_home / "iCloud"

    def test_non_darwin_never_uses_icloud(self, isolated_home, monkeypatch):
        monkeypatch.setattr(config, "sys", type("S", (), {"platform": "linux"})())
        assert config.default_output_dir() == isolated_home / "Music"


class TestConfigIO:
    def test_load_missing_file(self, isolated_home):
        assert config.load_config() == {}

    def test_load_corrupt_file(self, isolated_home):
        config.CONFIG_PATH.parent.mkdir(parents=True)
        config.CONFIG_PATH.write_text("{not json", encoding="utf-8")
        assert config.load_config() == {}

    def test_save_load_roundtrip(self, isolated_home):
        config.save_config({"output_dir": "/x", "default_quality": 320})
        assert config.load_config() == {"output_dir": "/x", "default_quality": 320}


class TestLanguage:
    def test_defaults_to_english_when_language_is_unset(self, isolated_home):
        assert config.get_language() == "en"

    def test_reads_russian_language(self, isolated_home):
        config.save_config({config.LANGUAGE_KEY: "ru"})
        assert config.get_language() == "ru"

    def test_reads_explicit_english_language(self, isolated_home):
        config.save_config({config.LANGUAGE_KEY: "en"})
        assert config.get_saved_language() == "en"
        assert config.get_language() == "en"

    def test_invalid_persisted_language_is_unset_but_effective_default_is_english(self, isolated_home):
        config.save_config({config.LANGUAGE_KEY: "de"})

        assert config.get_saved_language() is None
        assert config.get_language() == "en"

    def test_saving_language_preserves_unrelated_keys(self, isolated_home):
        config.save_config({"default_quality": 320, config.LANGUAGE_KEY: "ru"})

        assert config.load_config() == {"default_quality": 320, config.LANGUAGE_KEY: "ru"}


class TestResolveOutputDir:
    def test_override_has_priority(self, isolated_home, no_cloud, no_env, tmp_path):
        target = tmp_path / "out"
        target.mkdir()
        assert config.resolve_output_dir(target) == target.resolve()

    def test_env_beats_config(self, isolated_home, no_cloud, tmp_path, monkeypatch):
        env_dir = tmp_path / "env"
        env_dir.mkdir()
        cfg_dir = tmp_path / "cfg"
        cfg_dir.mkdir()
        config.save_config({"output_dir": str(cfg_dir)})
        monkeypatch.setenv("MUSIC_LIB_DIR", str(env_dir))
        assert config.resolve_output_dir() == env_dir.resolve()

    def test_config_beats_default(self, isolated_home, no_cloud, no_env, tmp_path):
        cfg_dir = tmp_path / "cfg"
        cfg_dir.mkdir()
        config.save_config({"output_dir": str(cfg_dir)})
        assert config.resolve_output_dir() == cfg_dir.resolve()

    def test_missing_override_returned_as_is(self, isolated_home, no_cloud, no_env):
        missing = isolated_home / "does-not-exist"
        assert config.resolve_output_dir(missing) == missing.resolve()

    def test_missing_env_returned_as_is(self, isolated_home, no_cloud, monkeypatch):
        missing = isolated_home / "nope"
        monkeypatch.setenv("MUSIC_LIB_DIR", str(missing))
        assert config.resolve_output_dir() == missing.resolve()

    def test_missing_config_dir_returned_as_is(self, isolated_home, no_cloud, no_env):
        missing = isolated_home / "nope"
        config.save_config({"output_dir": str(missing)})
        assert config.resolve_output_dir() == missing.resolve()

    def test_config_icloud_path_with_space(self, isolated_home, no_cloud, no_env):
        icloud = isolated_home / "Library/Mobile Documents/com~apple~CloudDocs/Музыка"
        config.save_config({"output_dir": str(icloud)})
        assert config.resolve_output_dir() == icloud.resolve()

    def test_plain_default(self, isolated_home, no_cloud, no_env):
        assert config.resolve_output_dir() == default_dir(isolated_home)

    def test_env_dir_with_spaces(self, isolated_home, no_cloud, tmp_path, monkeypatch):
        env_dir = tmp_path / "env dir"
        env_dir.mkdir()
        monkeypatch.setenv("MUSIC_LIB_DIR", str(env_dir))
        assert config.resolve_output_dir() == env_dir.resolve()


def default_dir(home: Path) -> Path:
    return home / "Music"


class TestNormalizePathInput:
    def test_strips_shell_escaped_space(self):
        raw = "/Users/u/Library/Mobile\\ Documents/com~apple~CloudDocs/Музыка"
        assert config.normalize_path_input(raw) == (
            "/Users/u/Library/Mobile Documents/com~apple~CloudDocs/Музыка"
        )

    def test_strips_shell_escaped_tilde_in_name(self):
        raw = "/x/com\\~apple~CloudDocs"
        assert config.normalize_path_input(raw) == "/x/com~apple~CloudDocs"

    def test_strips_surrounding_quotes(self):
        assert config.normalize_path_input("'/x/y'") == "/x/y"
        assert config.normalize_path_input('"/x/y"') == "/x/y"

    def test_plain_path_unchanged(self):
        raw = "/Users/u/Music"
        assert config.normalize_path_input(raw) == raw

    def test_strips_whitespace(self):
        assert config.normalize_path_input("  ~/Music  ") == "~/Music"


class TestInboxDir:
    def test_returns_inbox_subfolder(self, tmp_path):
        assert config.inbox_dir(tmp_path) == tmp_path / "Inbox"

    def test_inbox_name_constant(self):
        assert config.INBOX_DIR_NAME == "Inbox"


class TestYtmusicGetters:
    def test_auth_file_default(self, isolated_home):
        assert config.get_ytmusic_auth_file() == (
            isolated_home / ".config" / "music-lib" / "ytmusic_auth.json")

    def test_auth_file_from_config(self, isolated_home):
        path = isolated_home / "auth" / "ytm.json"
        config.save_config({config.YTMUSIC_AUTH_FILE_KEY: str(path)})
        assert config.get_ytmusic_auth_file() == path


class TestMetadataSources:
    def test_defaults(self, isolated_home):
        assert config.get_metadata_sources() == config.DEFAULT_METADATA_SOURCES
    def test_reads_configured(self, isolated_home):
        config.save_config({config.METADATA_SOURCES_KEY: ["Deezer", "Discogs"]})
        assert config.get_metadata_sources() == ["Deezer", "Discogs"]

    def test_dedupes_and_strips(self, isolated_home):
        config.save_config({config.METADATA_SOURCES_KEY: [" iTunes ", "iTunes", ""]})
        assert config.get_metadata_sources() == ["iTunes"]

    def test_empty_list_means_all_off(self, isolated_home):
        config.save_config({config.METADATA_SOURCES_KEY: []})
        assert config.get_metadata_sources() == []

    def test_bad_type_falls_back_to_default(self, isolated_home):
        config.save_config({config.METADATA_SOURCES_KEY: "iTunes"})
        assert config.get_metadata_sources() == config.DEFAULT_METADATA_SOURCES


class TestMetadataSourcesOrder:
    def test_defaults_to_registry(self, isolated_home):
        assert config.get_metadata_sources_order() == config.DEFAULT_METADATA_SOURCES

    def test_saved_order_first_missing_appended(self, isolated_home):
        config.save_config({config.METADATA_SOURCES_ORDER_KEY: ["Deezer", "iTunes"]})
        assert config.get_metadata_sources_order() == ["Deezer", "iTunes", "Discogs"]

    def test_stale_names_dropped(self, isolated_home):
        config.save_config({config.METADATA_SOURCES_ORDER_KEY:
                            ["Nope", "Discogs", "iTunes", "Deezer"]})
        assert config.get_metadata_sources_order() == ["Discogs", "iTunes", "Deezer"]

    def test_dedupes_and_strips(self, isolated_home):
        config.save_config({config.METADATA_SOURCES_ORDER_KEY:
                            [" iTunes ", "iTunes", "Deezer"]})
        assert config.get_metadata_sources_order() == ["iTunes", "Deezer", "Discogs"]

    def test_bad_type_falls_back_to_registry(self, isolated_home):
        config.save_config({config.METADATA_SOURCES_ORDER_KEY: "iTunes"})
        assert config.get_metadata_sources_order() == config.DEFAULT_METADATA_SOURCES


class TestSourceFormat:
    def test_defaults_to_m4a(self, isolated_home):
        assert config.get_source_format() == "m4a"

    def test_reads_configured_opus(self, isolated_home):
        config.save_config({config.SOURCE_FORMAT_KEY: "opus"})
        assert config.get_source_format() == "opus"

    def test_invalid_falls_back_to_default(self, isolated_home):
        config.save_config({config.SOURCE_FORMAT_KEY: "flac"})
        assert config.get_source_format() == config.DEFAULT_SOURCE_FORMAT


class TestNameTranslit:
    def test_defaults_to_auto(self, isolated_home):
        assert config.get_name_translit() == "auto"

    def test_reads_configured_latin(self, isolated_home):
        config.save_config({config.NAME_TRANSLIT_KEY: "latin"})
        assert config.get_name_translit() == "latin"

    def test_invalid_falls_back_to_default(self, isolated_home):
        config.save_config({config.NAME_TRANSLIT_KEY: "emoji"})
        assert config.get_name_translit() == config.DEFAULT_NAME_TRANSLIT


class TestSearchSource:
    def test_defaults_to_youtube_music(self, isolated_home):
        assert config.get_search_source() == config.DEFAULT_SEARCH_SOURCE

    def test_reads_configured_youtube(self, isolated_home):
        config.save_config({config.SEARCH_SOURCE_KEY: "youtube"})
        assert config.get_search_source() == "youtube"

    def test_strips_and_lowercases(self, isolated_home):
        config.save_config({config.SEARCH_SOURCE_KEY: "  YouTube_Music "})
        assert config.get_search_source() == "youtube_music"

    def test_invalid_falls_back_to_default(self, isolated_home):
        config.save_config({config.SEARCH_SOURCE_KEY: "rutube"})
        assert config.get_search_source() == config.DEFAULT_SEARCH_SOURCE


class TestLucidaSettings:
    def test_defaults_are_safe_for_lucida_downloads(self, isolated_home):
        assert config.get_lucida_service() == "qobuz"
        assert config.get_lucida_country() is None
        assert config.get_lucida_jobs() == 3

    def test_normalizes_valid_service_and_country(self, isolated_home):
        config.save_config({
            config.LUCIDA_SERVICE_KEY: "  AMAZON ",
            config.LUCIDA_COUNTRY_KEY: " us ",
            config.LUCIDA_JOBS_KEY: "4",
        })

        assert config.get_lucida_service() == "amazon"
        assert config.get_lucida_country() == "US"
        assert config.get_lucida_jobs() == 4

    @pytest.mark.parametrize("value", ["tidal", "", None, 7])
    def test_invalid_service_falls_back_to_qobuz(self, isolated_home, value):
        config.save_config({config.LUCIDA_SERVICE_KEY: value})

        assert config.get_lucida_service() == "qobuz"

    @pytest.mark.parametrize("value", ["", "   ", None, 4, []])
    def test_empty_or_non_string_country_is_unset(self, isolated_home, value):
        config.save_config({config.LUCIDA_COUNTRY_KEY: value})

        assert config.get_lucida_country() is None

    @pytest.mark.parametrize(("value", "expected"), [
        ("USA", None),
        ("1!", None),
        ("ЖП", None),
        ("ſs", None),
        (" us ", "US"),
        ("GB", "GB"),
    ])
    def test_lucida_country_accepts_only_normalized_ascii_iso_codes(self, isolated_home, value, expected):
        config.save_config({config.LUCIDA_COUNTRY_KEY: value})

        assert config.get_lucida_country() == expected

    @pytest.mark.parametrize("value", [0, -1, 9, 3.0, "many", True])
    def test_invalid_jobs_fall_back_to_default(self, isolated_home, value):
        config.save_config({config.LUCIDA_JOBS_KEY: value})

        assert config.get_lucida_jobs() == 3


class TestYoutubeCookies:
    def test_browser_default_safari(self, isolated_home, monkeypatch):
        monkeypatch.delenv("MUSIC_LIB_BROWSER", raising=False)
        monkeypatch.delenv("MUSIC_DL_BROWSER", raising=False)
        assert config.get_youtube_browser() == "safari"

    def test_browser_from_config_and_env(self, isolated_home, monkeypatch):
        config.save_config({config.YOUTUBE_BROWSER_KEY: "firefox"})
        assert config.get_youtube_browser() == "firefox"
        monkeypatch.setenv("MUSIC_LIB_BROWSER", "chrome")
        assert config.get_youtube_browser() == "chrome"

    def test_cookies_file_default_none(self, isolated_home, monkeypatch):
        monkeypatch.delenv("MUSIC_LIB_COOKIES_FILE", raising=False)
        monkeypatch.delenv("MUSIC_DL_COOKIES_FILE", raising=False)
        assert config.get_youtube_cookies_file() is None


class TestLegacyCompat:
    """Совместимость с music-dl: старые env и конфиг продолжают работать."""

    def test_legacy_dir_env_honored(self, isolated_home, no_cloud, tmp_path,
                                    monkeypatch):
        env_dir = tmp_path / "legacy"
        env_dir.mkdir()
        monkeypatch.setenv("MUSIC_DL_DIR", str(env_dir))
        assert config.resolve_output_dir() == env_dir.resolve()

    def test_new_dir_env_beats_legacy(self, isolated_home, no_cloud, tmp_path,
                                      monkeypatch):
        new_dir = tmp_path / "new"
        new_dir.mkdir()
        old_dir = tmp_path / "old"
        old_dir.mkdir()
        monkeypatch.setenv("MUSIC_LIB_DIR", str(new_dir))
        monkeypatch.setenv("MUSIC_DL_DIR", str(old_dir))
        assert config.resolve_output_dir() == new_dir.resolve()

    def test_legacy_browser_env_honored(self, isolated_home, monkeypatch):
        monkeypatch.setenv("MUSIC_DL_BROWSER", "chrome")
        assert config.get_youtube_browser() == "chrome"

    def test_legacy_config_migrated_on_load(self, isolated_home):
        legacy = isolated_home / ".config" / "music-dl" / "config.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_text('{"default_quality": 320}', encoding="utf-8")
        assert config.load_config() == {"default_quality": 320}
        assert config.CONFIG_PATH.is_file()

    def test_first_save_keeps_legacy_settings(self, isolated_home):
        legacy = isolated_home / ".config" / "music-dl" / "config.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_text('{"output_dir": "/x"}', encoding="utf-8")
        config.save_config({config.YOUTUBE_COOKIE_SOURCE_KEY: "safari"})
        assert config.load_config() == {
            "output_dir": "/x",
            config.YOUTUBE_COOKIE_SOURCE_KEY: "safari",
        }

    def test_new_config_beats_legacy(self, isolated_home):
        legacy = isolated_home / ".config" / "music-dl" / "config.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_text('{"default_quality": 320}', encoding="utf-8")
        config.save_config({"default_quality": 128})
        assert config.load_config() == {"default_quality": 128}

    def test_update_during_legacy_migration_preserves_legacy_and_new_values(
        self, isolated_home, monkeypatch,
    ):
        legacy = isolated_home / ".config" / "music-dl" / "config.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_text('{"default_quality": 320}', encoding="utf-8")

        copied = threading.Event()
        update_contending_for_lock = threading.Event()
        allow_replace = threading.Event()
        migration_errors: list[BaseException] = []
        update_errors: list[BaseException] = []
        real_replace = config.os.replace
        real_lock = config._config_lock
        updater: threading.Thread | None = None

        class SignalingLock:
            """Signal immediately before the updater blocks on the real lock."""

            def __enter__(self):
                if threading.current_thread() is updater:
                    update_contending_for_lock.set()
                real_lock.acquire()
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                real_lock.release()

        monkeypatch.setattr(config, "_config_lock", SignalingLock())

        def pause_migration_replace(source, destination):
            if Path(destination) == config.CONFIG_PATH:
                copied.set()
                assert allow_replace.wait(timeout=2)
            return real_replace(source, destination)

        monkeypatch.setattr(config.os, "replace", pause_migration_replace)
        def migrate():
            try:
                config.load_config()
            except BaseException as error:
                migration_errors.append(error)

        def update_language():
            try:
                config.update_config(
                    lambda cfg: cfg.__setitem__(config.LANGUAGE_KEY, "ru"),
                )
            except BaseException as error:
                update_errors.append(error)

        migration = threading.Thread(target=migrate)
        migration.start()
        updater = threading.Thread(target=update_language)
        try:
            assert copied.wait(timeout=2)
            updater.start()
            # Migration remains inside its lock. The wrapper emits this signal
            # directly before the updater attempts that same lock acquisition.
            assert update_contending_for_lock.wait(timeout=2)
            allow_replace.set()
        finally:
            # Never leave either worker blocked if a timing assertion fails.
            allow_replace.set()
            migration.join(timeout=2)
            updater.join(timeout=2)

        assert not migration.is_alive()
        assert not updater.is_alive()
        assert migration_errors == []
        assert update_errors == []
        assert config.load_config() == {"default_quality": 320, config.LANGUAGE_KEY: "ru"}

    def test_legacy_migration_replaces_config_atomically(self, isolated_home, monkeypatch):
        legacy = isolated_home / ".config" / "music-dl" / "config.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_text('{"default_quality": 320}', encoding="utf-8")
        replacements: list[tuple[Path, Path]] = []
        real_replace = config.os.replace

        def record_replace(source, destination):
            replacements.append((Path(source), Path(destination)))
            return real_replace(source, destination)

        monkeypatch.setattr(config.os, "replace", record_replace)
        assert config.load_config() == {"default_quality": 320}
        assert replacements
        source, destination = replacements[0]
        assert source.parent == config.CONFIG_DIR
        assert source.name.startswith(".config.json.")
        assert destination == config.CONFIG_PATH
