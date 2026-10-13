"""Tests for src/compress.py — re-encode/estimate/cover compression."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src import compress as c
from src.compress import (
    FORMAT_PROFILES,
    LOSSLESS_RATIO,
    LOSSLESS_SUFFIXES,
    compress_covers,
    compress_file,
    estimate_size,
    read_bitrate,
    should_compress,
)
from src.tagger import AudioTags, get_tags, set_tags


def _fake_ffmpeg(monkeypatch, write_bytes: bytes = b"encoded"):
    """Patch subprocess.run so it writes mock output to the last CLI arg."""

    def fake_run(cmd, **kw):
        Path(cmd[-1]).write_bytes(write_bytes)
        return None

    monkeypatch.setattr(c.subprocess, "run", fake_run)


def _record_ffmpeg(monkeypatch, write_bytes: bytes = b"encoded"):
    """Fake ffmpeg, запоминающий каждую команду."""
    cmds: list[list[str]] = []

    def fake_run(cmd, **kw):
        cmds.append(list(cmd))
        Path(cmd[-1]).write_bytes(write_bytes)
        return None

    monkeypatch.setattr(c.subprocess, "run", fake_run)
    return cmds


def _make_mp3(tmp_path: Path, bitrate: str = "320k") -> Path:
    """Настоящий короткий MP3 через ffmpeg (для тегов/битрейта)."""
    out = tmp_path / f"src_{bitrate}.mp3"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=0.4",
         "-codec:a", "libmp3lame", "-b:a", bitrate, str(out)],
        check=True, capture_output=True,
    )
    return out


class TestHelpers:
    def test_lossless_suffixes(self):
        assert LOSSLESS_SUFFIXES == {".flac", ".wav"}
        assert c._is_lossless(Path("a.flac"))
        assert c._is_lossless(Path("a.wav"))
        assert not c._is_lossless(Path("a.mp3"))
        assert c._is_lossless(Path("B.FLAC"))

    def test_lossless_ratio(self):
        assert LOSSLESS_RATIO > 1


class TestFormatProfiles:
    def test_codecs_and_suffixes(self):
        assert FORMAT_PROFILES["mp3"] == ("libmp3lame", ".mp3")
        assert FORMAT_PROFILES["m4a"] == ("aac", ".m4a")
        assert FORMAT_PROFILES["opus"] == ("libopus", ".opus")
        assert FORMAT_PROFILES["flac"] == ("flac", ".flac")

    def test_legacy_target_from_source(self):
        assert c._target_from_source(Path("a.flac")) == "mp3"
        assert c._target_from_source(Path("a.wav")) == "mp3"
        assert c._target_from_source(Path("a.mp3")) == "mp3"
        assert c._target_from_source(Path("a.m4a")) == "m4a"
        assert c._target_from_source(Path("a.aac")) == "m4a"
        assert c._target_from_source(Path("a.mp4")) == "m4a"
        assert c._target_from_source(Path("a.ogg")) == "mp3"

    def test_normalize_format(self):
        assert c._normalize_format("FLAC") == "flac"
        assert c._normalize_format(" m4a ") == "m4a"
        assert c._normalize_format(None) is None
        assert c._normalize_format("") is None
        assert c._normalize_format("wav") is None


class TestReadBitrate:
    def test_mp3_bitrate(self, mp3_stub):
        bitrate = read_bitrate(mp3_stub)
        assert bitrate == 128_000

    def test_flac_bitrate(self, audio_files):
        # mutagen may report a FLAC stream bitrate; only existence matters here.
        assert read_bitrate(audio_files["flac"]) >= 0

    def test_missing_file(self, tmp_path):
        assert read_bitrate(tmp_path / "nope.mp3") == 0

    def test_not_audio(self, tmp_path):
        p = tmp_path / "x.bin"
        p.write_bytes(b"\x00" * 100)
        assert read_bitrate(p) == 0


class TestShouldCompress:
    # --- legacy-вызов без target_format ---------------------------------

    def test_lossless_always(self, audio_files):
        assert should_compress(audio_files["flac"], 128) is True

    def test_lossy_above_threshold(self, mp3_stub):
        assert should_compress(mp3_stub, 64) is True  # 128k > 64*1.2

    def test_lossy_below_threshold(self, mp3_stub):
        assert should_compress(mp3_stub, 128) is False  # 128k ~ target

    def test_lossy_at_edge(self, mp3_stub):
        # 128000 > 100*1000*1.2 = 120000 → True
        assert should_compress(mp3_stub, 100) is True

    def test_unreadable_false(self, tmp_path):
        p = tmp_path / "x.mp3"
        p.write_bytes(b"junk")
        assert should_compress(p, 128) is False

    # --- lossy-таргет ----------------------------------------------------

    def test_lossy_target_lossless_source_is_candidate(self, audio_files):
        assert should_compress(audio_files["flac"], 192, target_format="mp3") is True

    def test_lossy_target_lossy_below_threshold(self, mp3_stub):
        assert should_compress(mp3_stub, 128, target_format="m4a") is False

    def test_lossy_target_lossy_above_threshold(self, mp3_stub):
        assert should_compress(mp3_stub, 64, target_format="opus") is True

    # --- lossless-таргет -------------------------------------------------

    def test_lossless_target_skips_flac(self, audio_files):
        assert should_compress(audio_files["flac"], 256, target_format="flac") is False

    def test_lossless_target_skips_wav(self, tmp_path):
        wav = tmp_path / "a.wav"
        wav.write_bytes(b"RIFF")
        assert should_compress(wav, 256, target_format="flac") is False

    def test_lossless_target_lossy_is_candidate(self, mp3_stub):
        # Настройка авторитетна: lossy → FLAC разрешён (битрейт известен).
        assert should_compress(mp3_stub, 256, target_format="flac") is True

    def test_lossless_target_unreadable_false(self, tmp_path):
        p = tmp_path / "x.mp3"
        p.write_bytes(b"junk")
        assert should_compress(p, 256, target_format="flac") is False


class TestEstimateSize:
    def test_estimates_mp3(self, mp3_stub):
        est = estimate_size(mp3_stub, 128)
        assert est > 0
        # duration ~ 4 * (417/128000*8...) → just sanity: 128kbps duration-based
        assert est < 1_000_000

    def test_lossless_target_no_estimate(self, mp3_stub):
        assert estimate_size(mp3_stub, 256, target_format="flac") == 0

    def test_missing_file(self, tmp_path):
        with pytest.raises(Exception):
            estimate_size(tmp_path / "nope.mp3", 128)

    def test_unknown_format(self, tmp_path):
        p = tmp_path / "x.xyz"
        p.write_bytes(b"data")
        assert estimate_size(p, 128) == 0


class TestCompressFile:
    def test_skip_when_already_small(self, mp3_stub):
        assert compress_file(mp3_stub, 320) is None

    def test_mp3_reencoded_in_place(self, mp3_stub, monkeypatch, tmp_path):
        _fake_ffmpeg(monkeypatch, write_bytes=b"smaller")
        new_path = compress_file(mp3_stub, 64)
        assert new_path is not None
        assert new_path == Path(str(mp3_stub))
        assert new_path.read_bytes() == b"smaller"

    def test_flac_converted_to_mp3(self, audio_files, tmp_path, monkeypatch):
        # В отдельной папке: рядом лежащий sample.mp3 из fixture занял бы
        # целевое имя (конфликт пути — корректный skip).
        path = tmp_path / "solo" / "track.flac"
        path.parent.mkdir()
        path.write_bytes(audio_files["flac"].read_bytes())
        set_tags(path, AudioTags(title="T", artist="A"))
        _fake_ffmpeg(monkeypatch, write_bytes=b"mp3data")
        new_path = compress_file(path, 192)
        assert new_path == path.with_suffix(".mp3")
        assert new_path.exists()
        assert not path.exists()

    def test_ffmpeg_error_returns_none(self, mp3_stub, monkeypatch):
        def boom(cmd, **kw):
            import subprocess as sp
            raise sp.CalledProcessError(1, cmd)

        monkeypatch.setattr(c.subprocess, "run", boom)
        assert compress_file(mp3_stub, 64) is None

    def test_unknown_target_format_skips(self, mp3_stub, monkeypatch):
        cmds = _record_ffmpeg(monkeypatch)
        assert compress_file(mp3_stub, 192, target_format="wav") is None
        assert cmds == []
        assert mp3_stub.exists()

    # --- ffmpeg-команды по форматам ---------------------------------------

    def test_target_mp3_command(self, mp3_stub, monkeypatch):
        cmds = _record_ffmpeg(monkeypatch)
        new_path = compress_file(mp3_stub, 64, target_format="mp3")
        assert new_path == mp3_stub
        cmd = cmds[0]
        assert cmd[cmd.index("-vn") + 1] == "-codec:a"  # без видеопотока-обложки
        assert cmd[cmd.index("-codec:a") + 1] == "libmp3lame"
        assert cmd[cmd.index("-b:a") + 1] == "64k"
        assert cmd[-1].endswith(".mp3")

    def test_target_m4a_command(self, mp3_stub, monkeypatch):
        cmds = _record_ffmpeg(monkeypatch)
        new_path = compress_file(mp3_stub, 64, target_format="m4a")
        assert new_path == mp3_stub.with_suffix(".m4a")
        assert not mp3_stub.exists()
        cmd = cmds[0]
        assert cmd[cmd.index("-codec:a") + 1] == "aac"
        assert cmd[cmd.index("-b:a") + 1] == "64k"
        assert cmd[-1].endswith(".m4a")

    def test_target_opus_command(self, mp3_stub, monkeypatch):
        cmds = _record_ffmpeg(monkeypatch)
        new_path = compress_file(mp3_stub, 64, target_format="opus")
        assert new_path == mp3_stub.with_suffix(".opus")
        assert not mp3_stub.exists()
        cmd = cmds[0]
        assert cmd[cmd.index("-codec:a") + 1] == "libopus"
        assert cmd[cmd.index("-b:a") + 1] == "64k"
        assert cmd[-1].endswith(".opus")

    def test_target_flac_no_bitrate(self, mp3_stub, monkeypatch):
        cmds = _record_ffmpeg(monkeypatch)
        new_path = compress_file(mp3_stub, 256, target_format="flac")
        assert new_path == mp3_stub.with_suffix(".flac")
        assert not mp3_stub.exists()
        cmd = cmds[0]
        assert cmd[cmd.index("-codec:a") + 1] == "flac"
        assert "-b:a" not in cmd
        assert cmd[-1].endswith(".flac")

    def test_flac_target_skips_lossless_sources(self, audio_files, tmp_path, monkeypatch):
        wav = tmp_path / "a.wav"
        wav.write_bytes(b"RIFF")
        cmds = _record_ffmpeg(monkeypatch)
        assert compress_file(audio_files["flac"], 256, target_format="flac") is None
        assert compress_file(wav, 256, target_format="flac") is None
        assert cmds == []
        assert audio_files["flac"].exists()
        assert wav.exists()

    # --- конфликт целевого пути -------------------------------------------

    def test_target_conflict_keeps_both_files(self, mp3_stub, monkeypatch):
        existing = mp3_stub.with_suffix(".m4a")
        existing.write_bytes(b"existing m4a")
        original = mp3_stub.read_bytes()
        _fake_ffmpeg(monkeypatch, write_bytes=b"encoded")

        assert compress_file(mp3_stub, 64, target_format="m4a") is None
        assert mp3_stub.read_bytes() == original  # исходник не тронут
        assert existing.read_bytes() == b"existing m4a"  # целевой не затёрт

    # --- теги на настоящем ffmpeg -----------------------------------------

    def test_tags_cover_and_lyrics_preserved_mp3(self, tmp_path, ffmpeg):
        src = _make_mp3(tmp_path, "320k")
        set_tags(src, AudioTags(
            title="T", artist="A", album="Al", year="2020",
            lyrics="la la",
            cover_data=b"\xff\xd8\xff\xe0cover", cover_mime="image/jpeg",
        ))
        new_path = compress_file(src, 64, target_format="mp3")
        assert new_path is not None and new_path.suffix == ".mp3"
        tags = get_tags(new_path)
        assert tags.title == "T"
        assert tags.artist == "A"
        assert tags.album == "Al"
        assert tags.year == "2020"
        assert tags.lyrics == "la la"
        assert tags.cover_data == b"\xff\xd8\xff\xe0cover"

    def test_tags_preserved_on_format_change_to_m4a(self, tmp_path, ffmpeg):
        src = _make_mp3(tmp_path, "320k")
        set_tags(src, AudioTags(
            title="T", artist="A",
            cover_data=b"\xff\xd8\xff\xe0cover", cover_mime="image/jpeg",
        ))
        new_path = compress_file(src, 128, target_format="m4a")
        assert new_path is not None and new_path.suffix == ".m4a"
        assert not src.exists()
        tags = get_tags(new_path)
        assert tags.title == "T"
        assert tags.artist == "A"
        assert tags.cover_data == b"\xff\xd8\xff\xe0cover"


class TestCompressCovers:
    def test_no_cover_false(self, mp3_stub):
        assert compress_covers(mp3_stub) is False

    def test_unchanged_cover_false(self, mp3_stub, monkeypatch):
        set_tags(mp3_stub, AudioTags(title="T", cover_data=b"small", cover_mime="image/jpeg"))

        def fake_prepare(data, *_a, **_k):
            return data  # nothing to shrink

        monkeypatch.setattr("src.fetcher._prepare_cover", fake_prepare)
        assert compress_covers(mp3_stub) is False

    def test_recompresses_cover(self, mp3_stub, monkeypatch):
        set_tags(mp3_stub, AudioTags(title="T", cover_data=b"large", cover_mime="image/jpeg"))

        def fake_prepare(data, *_a, **_k):
            return b"tiny"

        monkeypatch.setattr("src.fetcher._prepare_cover", fake_prepare)
        assert compress_covers(mp3_stub) is True
        assert get_tags(mp3_stub).cover_data == b"tiny"

    def test_exception_propagates(self, mp3_stub, monkeypatch):
        set_tags(mp3_stub, AudioTags(title="T", cover_data=b"large", cover_mime="image/jpeg"))

        def boom(data, *_a, **_k):
            raise RuntimeError

        monkeypatch.setattr("src.fetcher._prepare_cover", boom)
        with pytest.raises(RuntimeError):
            compress_covers(mp3_stub)
