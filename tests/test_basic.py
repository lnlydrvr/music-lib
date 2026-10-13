"""Basic tests for music-lib."""
from pathlib import Path
import unicodedata

from src.downloader import AudioFormat, DownloadProgress, VideoInfo
from src.tagger import AudioTags, Tagger
from src.utils import sanitize_name, clean_artist_name
from src.fetcher import FetchedTags
from src.lyrics import LyricsResult
from src.utils import nfc_path


def test_audio_format():
    """Test AudioFormat enum."""
    assert AudioFormat.FLAC.value == "flac"
    assert AudioFormat.MP3.value == "mp3"
    assert AudioFormat.AAC.value == "m4a"
    assert AudioFormat.OPUS.value == "opus"
    assert len(AudioFormat.all()) == 4


def test_audio_format_opts():
    """Test ydl_opts method."""
    opts = AudioFormat.ydl_opts("mp3", quality=256)
    assert opts["format"] == "bestaudio/best"
    assert opts["postprocessors"][0]["preferredcodec"] == "mp3"
    assert opts["postprocessors"][0]["preferredquality"] == "256"


def test_audio_format_opts_flac_no_quality():
    """FLAC is lossless — no preferredquality even when quality passed."""
    opts = AudioFormat.ydl_opts("flac", quality=256)
    assert opts["postprocessors"][0]["preferredcodec"] == "flac"
    assert "preferredquality" not in opts["postprocessors"][0]


def test_audio_format_opts_default_quality():
    """No quality passed → no preferredquality key."""
    opts = AudioFormat.ydl_opts("m4a")
    assert opts["postprocessors"][0]["preferredcodec"] == "m4a"
    assert "preferredquality" not in opts["postprocessors"][0]


def test_video_info():
    """Test VideoInfo dataclass."""
    info = VideoInfo(
        id="test123",
        title="Test Song",
        duration=240,
        uploader="Test Artist",
    )
    assert info.id == "test123"
    assert info.title == "Test Song"
    assert info.duration == 240
    assert info.uploader == "Test Artist"


def test_video_info_from_ydl():
    """Test VideoInfo.from_ydl method."""
    data = {
        "id": "abc123",
        "title": "My Song",
        "duration": 180,
        "uploader": "Artist",
        "thumbnail": "http://example.com/thumb.jpg",
        "webpage_url": "http://example.com/watch?v=abc123",
    }
    info = VideoInfo.from_ydl(data)
    assert info.id == "abc123"
    assert info.title == "My Song"
    assert info.thumbnail == "http://example.com/thumb.jpg"


def test_download_progress():
    """Test DownloadProgress dataclass."""
    progress = DownloadProgress(
        filename="test.mp3",
        status="downloading",
        total_bytes=1000000,
        downloaded_bytes=500000,
        speed=1000,
        eta=500,
    )
    assert progress.total_bytes == 1000000
    assert progress.downloaded_bytes == 500000


def test_audio_tags():
    """Test AudioTags dataclass."""
    tags = AudioTags(
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        album_artist="Various Artists",
        year="2024",
        track_number="1",
        genre="Rock",
    )
    assert tags.title == "Test Song"
    assert tags.artist == "Test Artist"
    assert tags.album_artist == "Various Artists"


def test_album_artist_tag_roundtrip(tmp_path):
    """Write and read back the Album Artist (TPE2) tag on an MP3 stub."""
    # Minimal valid MPEG frames so EasyMP3 can parse the file.
    frame = b"\xff\xfb\x90\x44" + b"\x00" * 413
    path = tmp_path / "song.mp3"
    path.write_bytes(frame * 4)

    tags = AudioTags(
        title="Song",
        artist="Artist",
        album="Compilation",
        album_artist="Various Artists",
        track_number="2",
    )
    assert Tagger(path).write(tags) is True

    read = Tagger(path).read()
    assert read.title == "Song"
    assert read.artist == "Artist"
    assert read.album == "Compilation"
    assert read.album_artist == "Various Artists"
    assert read.track_number == "2"


def test_sanitize_name():
    """Test sanitize_name utility."""
    assert sanitize_name("Test Song") == "Test Song"
    assert sanitize_name('Test: Song') == "Test_ Song"
    assert sanitize_name("") == "Unknown"
    assert sanitize_name("  ") == "Unknown"
    assert sanitize_name('<>:"/\\|?*') == "_________"


def test_clean_artist_name():
    """Test clean_artist_name utility."""
    # Topic variants
    assert clean_artist_name("Pink Floyd - Topic") == "Pink Floyd"
    assert clean_artist_name("Pink Floyd Topic") == "Pink Floyd"
    assert clean_artist_name("Pink Floyd - Topic Audio") == "Pink Floyd"

    # VEVO
    assert clean_artist_name("Radiohead VEVO") == "Radiohead"
    assert clean_artist_name("Radiohead - VEVO") == "Radiohead"

    # Official
    assert clean_artist_name("Band - Official") == "Band"
    assert clean_artist_name("Band - Official Audio") == "Band"

    # Other suffixes
    assert clean_artist_name("Artist - Music") == "Artist"
    assert clean_artist_name("Artist - Records") == "Artist"
    assert clean_artist_name("Artist - Audio") == "Artist"

    # No suffix — unchanged
    assert clean_artist_name("Normal Artist") == "Normal Artist"
    assert clean_artist_name("The Band") == "The Band"

    # Edge cases
    assert clean_artist_name("  Pink Floyd - Topic  ") == "Pink Floyd"
    assert clean_artist_name("Topic") == "Topic"  # only suffix, return as-is
    assert clean_artist_name("") == ""


def test_fetched_tags():
    """Test FetchedTags dataclass."""
    tags = FetchedTags(
        title="Test",
        artist="Artist",
        album="Album",
        cover_url="http://example.com/cover.jpg",
    )
    assert tags.title == "Test"
    assert tags.cover_url == "http://example.com/cover.jpg"


def testnfc_path_normalization():
    """Test that nfc_path normalizes Unicode differences between macOS filesystem and tags."""
    # macOS stores ペ (PE) as NFD: ヘ (HE) + combining semi-voiced mark
    # Tags return ペ as NFC (single codepoint)
    nfc_pe = "\u30da"          # ペ (NFC, single codepoint)
    nfd_pe = "\u30d8\u309a"    # ヘ + combining semi-voiced mark (NFD, two codepoints)
    assert nfc_pe != nfd_pe  # different raw bytes

    p_nfc = Path(f"/music/{nfc_pe}ルソナ4/Heaven.mp3")
    p_nfd = Path(f"/music/{nfd_pe}ルソナ4/Heaven.mp3")

    # Raw comparison fails (macOS NFD vs tag NFC)
    assert str(p_nfc) != str(p_nfd)

    # nfc_path normalizes both to NFC, making them equal
    assert nfc_path(p_nfc) == nfc_path(p_nfd)

    # Same path → still equal
    p2 = Path(f"/music/{nfc_pe}ルソナ4/Heaven.mp3")
    assert nfc_path(p_nfc) == nfc_path(p2)


def test_lyrics_result():
    """Test LyricsResult dataclass."""
    lyrics = LyricsResult(
        track_name="Test Song",
        artist_name="Test Artist",
        album_name="Test Album",
        duration=240,
        plain_lyrics="Line 1\nLine 2",
        synced_lyrics="[00:01.00] Line 1\n[00:05.00] Line 2",
    )
    assert lyrics.track_name == "Test Song"
    assert lyrics.artist_name == "Test Artist"
    assert lyrics.plain_lyrics == "Line 1\nLine 2"
    assert lyrics.synced_lyrics == "[00:01.00] Line 1\n[00:05.00] Line 2"


def test_lyrics_result_defaults():
    """Test LyricsResult default values."""
    lyrics = LyricsResult()
    assert lyrics.track_name == ""
    assert lyrics.plain_lyrics == ""
    assert lyrics.synced_lyrics == ""
    assert lyrics.duration == 0


def test_audio_tags_lyrics_field():
    """Test AudioTags has lyrics field."""
    tags = AudioTags(
        title="Song",
        artist="Artist",
        lyrics="Hello world",
    )
    assert tags.lyrics == "Hello world"

    tags_empty = AudioTags()
    assert tags_empty.lyrics == ""


if __name__ == "__main__":
    test_audio_format()
    test_audio_format_opts()
    test_video_info()
    test_video_info_from_ydl()
    test_download_progress()
    test_audio_tags()
    test_sanitize_name()
    test_clean_artist_name()
    test_fetched_tags()
    test_lyrics_result()
    test_lyrics_result_defaults()
    test_audio_tags_lyrics_field()
    print("All tests passed!")
