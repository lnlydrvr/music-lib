"""Tests for src/downloader.py (audio download, format options, progress)."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.downloader import (
    AudioFormat,
    DownloadResult,
    Downloader,
    DownloadProgress,
    VideoInfo,
    append_m3u8,
    archive_dir,
    archive_path,
)

from conftest import MP3_FRAME


class FakeYDL:
    """A YoutubeDL stand-in: records options and serves canned info/files."""

    instances: list["FakeYDL"] = []
    info: dict = {}
    extra: dict = {}
    raise_on_extract: Exception | None = None
    raise_on_download: Exception | None = None
    write_file: bool = True
    download_hook = None

    def __init__(self, opts=None):
        self.opts = opts or {}
        self.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=False):
        if self.raise_on_extract is not None:
            raise self.raise_on_extract
        return dict(self.info)

    def download(self, urls):
        if FakeYDL.download_hook is not None:
            FakeYDL.download_hook(self, urls)
            return
        if self.raise_on_download is not None:
            raise self.raise_on_download
        if not self.write_file:
            return
        outtmpl = self.opts["outtmpl"].replace("%(ext)s", "m4a")
        out = Path(outtmpl)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(MP3_FRAME * 4)


@pytest.fixture
def fake_ydl(monkeypatch):
    FakeYDL.info = {
        "id": "test123",
        "title": "Test Song",
        "duration": 240,
        "uploader": "Pink Floyd - Topic",
        "thumbnail": "http://example.com/thumb.jpg",
        "webpage_url": "http://example.com/watch?v=test123",
        "description": "desc",
        "upload_date": "20240101",
        "view_count": 10,
    }
    FakeYDL.extra = {}
    FakeYDL.raise_on_extract = None
    FakeYDL.raise_on_download = None
    FakeYDL.write_file = True
    FakeYDL.download_hook = None
    FakeYDL.instances = []
    monkeypatch.setattr("src.downloader.YoutubeDL", FakeYDL)
    return FakeYDL


# --- AudioFormat -----------------------------------------------------


class TestAudioFormat:
    def test_all_values(self):
        assert set(AudioFormat.all()) == {"flac", "mp3", "m4a", "opus"}

    def test_opts_opus_no_quality(self):
        opts = AudioFormat.ydl_opts("opus")
        assert opts["format"] == "bestaudio/best"
        assert opts["postprocessors"][0]["preferredcodec"] == "opus"
        assert "preferredquality" not in opts["postprocessors"][0]

    def test_opts_quality_zero_is_ignored(self):
        opts = AudioFormat.ydl_opts("mp3", quality=0)
        assert "preferredquality" not in opts["postprocessors"][0]

    def test_opts_flac_ignores_quality(self):
        opts = AudioFormat.ydl_opts("flac", quality=320)
        assert opts["postprocessors"][0]["preferredcodec"] == "flac"
        assert "preferredquality" not in opts["postprocessors"][0]

    def test_opts_mp3_with_quality(self):
        opts = AudioFormat.ydl_opts("mp3", quality=192)
        assert opts["postprocessors"][0]["preferredquality"] == "192"

    def test_source_selector_none_is_bestaudio(self):
        assert AudioFormat.source_selector(None) == "bestaudio/best"
        assert AudioFormat.ydl_opts("m4a")["format"] == "bestaudio/best"

    def test_source_selector_opus_prefers_opus_then_m4a(self):
        selector = AudioFormat.source_selector("opus")
        assert selector == "bestaudio[acodec=opus]/bestaudio[ext=m4a]/bestaudio/best"
        assert AudioFormat.ydl_opts("opus", source="opus")["format"] == selector

    def test_source_selector_m4a_prefers_m4a(self):
        selector = AudioFormat.source_selector("m4a")
        assert selector == "bestaudio[ext=m4a]/bestaudio/best"
        assert AudioFormat.ydl_opts("m4a", source="m4a")["format"] == selector


# --- VideoInfo / DownloadResult / DownloadProgress ------------------


class TestVideoInfo:
    def test_defaults(self):
        info = VideoInfo.from_ydl({})
        assert info.title == "Unknown"
        assert info.uploader == "Unknown"
        assert info.duration == 0
        assert info.thumbnail is None
        assert info.view_count == 0

    def test_from_ydl_full(self):
        info = VideoInfo.from_ydl({
            "id": "1", "title": "T", "duration": 99, "uploader": "A",
            "thumbnail": "u", "webpage_url": "w", "description": "d",
            "upload_date": "20010101", "view_count": 7,
        })
        assert info.id == "1"
        assert info.description == "d"
        assert info.upload_date == "20010101"
        assert info.view_count == 7

    def test_duration_falsy_coerced(self):
        info = VideoInfo.from_ydl({"duration": None})
        assert info.duration == 0


class TestDownloadResult:
    def test_defaults(self):
        res = DownloadResult(success=False)
        assert res.filepath is None
        assert res.error is None
        assert res.info is None


# --- Downloader internals -------------------------------------------


class TestDownloader:
    def test_init_creates_output_dir(self, tmp_path):
        out = tmp_path / "nested" / "dir"
        dl = Downloader(out)
        assert out.exists()
        assert dl.output_dir == out

    def test_base_opts(self):
        opts = Downloader._base_opts()
        assert opts["quiet"] is True
        assert opts["cookiesfrombrowser"] == ("safari",)

    def test_progress_hook_no_callback(self, tmp_path):
        dl = Downloader(tmp_path)
        dl._progress_hook({"status": "downloading"}, None)  # no crash

    def test_progress_hook_total_bytes(self, tmp_path):
        dl = Downloader(tmp_path)
        got: list[DownloadProgress] = []
        dl._progress_hook({
            "filename": "/x/a.mp3",
            "status": "downloading",
            "total_bytes": 1000,
            "downloaded_bytes": 400,
            "speed": 3.5,
            "eta": 9,
        }, got.append)
        assert got[0].filename == "/x/a.mp3"
        assert got[0].status == "downloading"
        assert got[0].total_bytes == 1000
        assert got[0].downloaded_bytes == 400
        assert got[0].speed == 3.5
        assert got[0].eta == 9

    def test_progress_hook_uses_estimate(self, tmp_path):
        dl = Downloader(tmp_path)
        got: list[DownloadProgress] = []
        dl._progress_hook({
            "status": "downloading",
            "total_bytes": 0,
            "total_bytes_estimate": 5000,
            "speed": None,
            "eta": None,
        }, got.append)
        assert got[0].total_bytes == 5000
        assert got[0].speed == 0
        assert got[0].eta == 0

    def test_build_output_template_cleans_parts(self, tmp_path):
        dl = Downloader(tmp_path)
        info = VideoInfo(id="1", title="Test: Song", duration=1, uploader="Radiohead - Topic")
        tmpl = dl._build_output_template(info, "m4a")
        assert tmpl == str(tmp_path / "Inbox" / "Test_ Song.%(ext)s")

    def test_build_output_template_unknown_uploader(self, tmp_path):
        dl = Downloader(tmp_path)
        info = VideoInfo(id="1", title="  ", duration=1, uploader="")
        tmpl = dl._build_output_template(info, "m4a")
        assert tmpl.startswith(str(tmp_path / "Inbox" / "Unknown"))

    def test_get_info(self, fake_ydl, tmp_path):
        dl = Downloader(tmp_path)
        info = dl._get_info("http://example.com/v")
        assert info is not None
        assert info.id == "test123"
        assert info.uploader == "Pink Floyd - Topic"

    def test_get_info_returns_none_on_error(self, fake_ydl, tmp_path):
        FakeYDL.raise_on_extract = RuntimeError("boom")
        dl = Downloader(tmp_path)
        assert dl._get_info("http://example.com/v") is None


# --- download() ------------------------------------------------------


class TestDownload:
    def test_download_success(self, fake_ydl, tmp_path):
        dl = Downloader(tmp_path)
        res = dl.download("http://example.com/v", fmt="m4a")
        assert res.success is True
        assert res.filepath == tmp_path / "Inbox" / "Test Song.m4a"
        assert res.info is not None
        last_opts = FakeYDL.instances[-1].opts
        assert last_opts["format"] == "bestaudio/best"
        assert "outtmpl" in last_opts
        assert "progress_hooks" in last_opts

    def test_download_progress_callback(self, fake_ydl, tmp_path):
        dl = Downloader(tmp_path)
        calls: list[DownloadProgress] = []

        def hooked(ydl, urls):
            outtmpl = ydl.opts["outtmpl"].replace("%(ext)s", "m4a")
            out = Path(outtmpl)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"x")
            ydl.opts["progress_hooks"][0]({
                "status": "downloading", "total_bytes": 10, "downloaded_bytes": 5,
            })

        FakeYDL.download_hook = hooked
        res = dl.download("http://e/v", fmt="m4a", progress_callback=calls.append)
        assert res.success is True
        assert calls and calls[0].downloaded_bytes == 5

    def test_download_unable_to_fetch_info(self, fake_ydl, tmp_path, monkeypatch):
        monkeypatch.setattr("src.downloader.time.sleep", lambda s: None)
        FakeYDL.raise_on_extract = RuntimeError("no")
        dl = Downloader(tmp_path)
        res = dl.download("http://e/v")
        assert res.success is False
        assert res.error.startswith("Не удалось получить информацию о видео")
        assert "no" in res.error

    def test_download_file_not_found(self, fake_ydl, tmp_path):
        FakeYDL.write_file = False
        dl = Downloader(tmp_path)
        res = dl.download("http://e/v", fmt="m4a")
        assert res.success is False
        assert res.error == "Файл не найден после скачивания"
        assert res.info is not None  # info was fetched

    def test_download_exception_returns_error(self, fake_ydl, tmp_path):
        FakeYDL.raise_on_download = OSError("disk full")
        dl = Downloader(tmp_path)
        res = dl.download("http://e/v")
        assert res.success is False
        assert res.error == "disk full"


# --- download_many() --------------------------------------------------


class TestDownloadMany:
    def test_empty_urls(self, tmp_path):
        assert Downloader(tmp_path).download_many([]) == []

    def test_results_in_order_and_progress(self, tmp_path, monkeypatch):
        dl = Downloader(tmp_path)
        seen: list[tuple[str, bool]] = []

        def fake_download(url, fmt, quality, cb, source=None):
            if cb:
                cb(DownloadProgress(filename=url, status="downloading", downloaded_bytes=1))
            seen.append((url, True))
            return DownloadResult(success=True, filepath=Path("/x") / url, info=None)

        monkeypatch.setattr(dl, "download", fake_download)
        urls = ["u1", "u2", "u3"]
        results = dl.download_many(urls, max_workers=2)
        assert [r.filepath.name for r in results] == urls
        assert sorted(u for u, _ in seen) == sorted(urls)

    def test_failure_keeps_position(self, tmp_path, monkeypatch):
        dl = Downloader(tmp_path)

        def fake_download(url, fmt, quality, cb, source=None):
            if url == "bad":
                return DownloadResult(success=False, error="nope")
            return DownloadResult(success=True, filepath=Path("/x") / url)

        monkeypatch.setattr(dl, "download", fake_download)
        results = dl.download_many(["bad", "ok"], max_workers=2)
        assert results[0].success is False
        assert results[1].success is True


# --- .m3u8-архив -------------------------------------------------------


class TestArchive:
    def test_archive_dir_and_path(self, tmp_path):
        assert archive_dir(tmp_path) == tmp_path / "Плейлисты"
        p = archive_path(tmp_path, "Лайки 2024")
        assert p == tmp_path / "Плейлисты" / "Лайки 2024.m3u8"
        assert archive_path(tmp_path, "Play.m3u8").name == "Play.m3u8"
        assert archive_path(tmp_path, "  ").name.endswith(".m3u8")

    def test_append_m3u8_creates_file(self, tmp_path):
        target = tmp_path / "A.mp3"
        target.write_bytes(b"x")
        path = archive_path(tmp_path, "Likes")
        assert append_m3u8(path, target, title="Песня", duration=65) is True
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        assert lines[0] == "#EXTM3U"
        assert "#EXTINF:65,Песня" in lines
        assert str(target.resolve()) in lines

    def test_append_m3u8_no_duplicates(self, tmp_path):
        target = tmp_path / "B.flac"
        target.write_bytes(b"x")
        path = archive_path(tmp_path, "Likes")
        append_m3u8(path, target, title="T", duration=100)
        assert append_m3u8(path, target, title="T", duration=100) is False
        text = path.read_text(encoding="utf-8")
        assert text.count("#EXTINF") == 1

    def test_append_m3u8_keeps_existing_entries(self, tmp_path):
        first = tmp_path / "1.mp3"
        second = tmp_path / "2.mp3"
        first.write_bytes(b"a")
        second.write_bytes(b"b")
        path = archive_path(tmp_path, "Mix")
        append_m3u8(path, first, title="First")
        append_m3u8(path, second, title="Second")
        text = path.read_text(encoding="utf-8")
        assert text.count("#EXTM3U") == 1
        assert text.count("#EXTINF") == 2

    def test_append_m3u8_sanitizes_name(self, tmp_path):
        target = tmp_path / "C.mp3"
        target.write_bytes(b"c")
        assert archive_path(tmp_path, "Вы  &* /ц").parent == archive_dir(tmp_path)