import asyncio

import httpx
import pytest

from src.lucida import download
from src.lucida import cf
from src.lucida import http as lucida_http


class FakeResponse:
    def __init__(self, payload=None, *, body=b"audio", headers=None):
        self._payload = payload
        self.headers = headers or {}
        self.body = body

    def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def aiter_bytes(self):
        yield self.body


class FakeClient:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    async def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return next(self.replies)

    async def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return next(self.replies)

    async def stream(self, url, **kwargs):
        self.calls.append(("STREAM", url, kwargs))
        return _AsyncResponse(next(self.replies))


class _AsyncResponse:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, *_):
        return None


def test_start_download_sends_protocol_body_and_returns_handoff_server():
    client = FakeClient([FakeResponse({"handoff": "h-1", "server": "s-1"})])
    result = asyncio.run(download.start_download(
            {"url": "https://www.qobuz.com/track", "csrf": "csrf"},
        expiry=1234,
        country="NL",
        client=client,
    ))
    assert result == ("h-1", "s-1")
    method, url, kwargs = client.calls[0]
    assert method == "POST"
    assert url == "https://lucida.to/api/load?url=/api/fetch/stream/v2"
    assert kwargs["json"] == {
        "account": {"id": "NL", "type": "country"}, "compat": False,
        "downscale": "original", "handoff": True, "metadata": True,
        "private": False, "token": {"expiry": 1234, "primary": "csrf", "secondary": ""},
            "upload": {"enabled": False}, "url": "https://www.qobuz.com/track",
    }


def test_start_download_posts_trimmed_track_url():
    client = FakeClient([FakeResponse({"handoff": "h-1", "server": "s-1"})])

    asyncio.run(download.start_download(
        {"url": "  https://www.qobuz.com/track  ", "csrf": "csrf"},
        expiry=1234,
        country="NL",
        client=client,
    ))

    assert client.calls[0][2]["json"]["url"] == "https://www.qobuz.com/track"


def test_run_job_polls_streams_and_atomically_renames_in_inbox(tmp_path):
    client = FakeClient([
        FakeResponse({"status": "processing", "message": "queued"}),
        FakeResponse({"status": "completed"}),
        FakeResponse(body=b"audio-data", headers={"content-type": "audio/flac"}),
    ])
    statuses, byte_counts = [], []
    result = asyncio.run(download.run_job(
        "h-1", "s-1", tmp_path, "Track", statuses.append, byte_counts.append,
        client=client, poll_interval=0,
    ))
    assert result == tmp_path / "Track.flac"
    assert result.read_bytes() == b"audio-data"
    assert not list(tmp_path.glob("*.part"))
    assert statuses == ["queued", "completed"]
    assert byte_counts == [10]
    assert client.calls[0][1] == "https://s-1.lucida.to/api/fetch/request/h-1"
    assert client.calls[1][1] == "https://s-1.lucida.to/api/fetch/request/h-1"
    assert client.calls[2][1] == "https://s-1.lucida.to/api/fetch/request/h-1/download"


def test_run_job_removes_only_partial_on_stream_failure(tmp_path):
    complete = tmp_path / "already.m4a"
    complete.write_bytes(b"keep")
    foreign_partial = tmp_path / ".Track.other-job.part"
    foreign_partial.write_bytes(b"other job")

    class FailedStreamClient(FakeClient):
        async def stream(self, url, **kwargs):
            raise httpx.ReadError("interrupted")

    client = FailedStreamClient([FakeResponse({"status": "completed"})])
    with pytest.raises(httpx.ReadError):
        asyncio.run(download.run_job(
            "h", "s", tmp_path, "Track", None, None, client=client,
            poll_interval=0, max_stream_retries=0,
    ))
    assert complete.read_bytes() == b"keep"
    assert foreign_partial.read_bytes() == b"other job"


def test_run_job_aborts_when_polling_stalls(tmp_path):
    client = FakeClient([FakeResponse({"status": "processing"})] * 2)
    with pytest.raises(TimeoutError, match="stalled"):
        asyncio.run(download.run_job("h", "s", tmp_path, "Track", None, None, client=client,
                                     poll_interval=0, max_polls=2))


def test_run_job_with_real_client_and_mock_transport_downloads(tmp_path, monkeypatch):
    monkeypatch.setattr(cf, "load_clearance", lambda: ("cookie-value", "test-agent"))
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original_client(**{**kwargs, "http2": False})
    )

    async def handler(request):
        if request.url.path.endswith("/download"):
            return httpx.Response(200, headers={"content-type": "audio/mpeg"}, content=b"audio")
        return httpx.Response(200, json={"status": "completed"})

    async def run():
        async with lucida_http.LucidaClient(transport=httpx.MockTransport(handler)) as client:
            return await download.run_job("handoff", "server", tmp_path, "Track", client=client)

    result = asyncio.run(run())
    assert result == tmp_path / "Track.mp3"
    assert result.read_bytes() == b"audio"


def test_run_job_uses_unique_partial_and_preserves_colliding_completed_file(tmp_path):
    existing = tmp_path / "Track.flac"
    existing.write_bytes(b"keep")
    client = FakeClient([
        FakeResponse({"status": "completed"}),
        FakeResponse(body=b"new", headers={"content-type": "audio/flac"}),
    ])

    result = asyncio.run(download.run_job("h", "s", tmp_path, "Track", client=client, poll_interval=0))

    assert existing.read_bytes() == b"keep"
    assert result == tmp_path / "Track (1).flac"
    assert result.read_bytes() == b"new"
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize("name", ["../escape", "/tmp/escape", ".."])
def test_run_job_rejects_unsafe_filename(name, tmp_path):
    with pytest.raises(ValueError, match="filename"):
        asyncio.run(download.run_job("h", "s", tmp_path, name, client=FakeClient([])))


def test_run_job_retries_transient_stream_body_error_and_removes_its_partial(tmp_path):
    class BodyFailsOnce:
        headers = {"content-type": "audio/flac"}

        async def aiter_bytes(self):
            yield b"incomplete"
            raise httpx.ReadError("connection reset")

    client = FakeClient([
        FakeResponse({"status": "completed"}),
        BodyFailsOnce(),
        FakeResponse(body=b"complete", headers={"content-type": "audio/flac"}),
    ])

    result = asyncio.run(download.run_job(
        "h", "s", tmp_path, "Track", client=client, poll_interval=0, max_stream_retries=1
    ))

    assert result.read_bytes() == b"complete"
    assert len([call for call in client.calls if call[0] == "STREAM"]) == 2
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize("track", [{"csrf": "token"}, {"url": "https://example.test/track"}])
def test_start_download_requires_track_url_and_token_before_post(track):
    client = FakeClient([])
    with pytest.raises(ValueError):
        asyncio.run(download.start_download(track, expiry=123, country="NL", client=client))
    assert client.calls == []


@pytest.mark.parametrize("track_url", ["", "not-a-url", "ftp://example.test/track", "https://"])
def test_start_download_rejects_invalid_track_url_before_post(track_url):
    client = FakeClient([])

    with pytest.raises(ValueError, match="URL"):
        asyncio.run(download.start_download(
            {"url": track_url, "csrf": "csrf"}, expiry=123, country="NL", client=client
        ))

    assert client.calls == []


def test_start_download_uses_first_nonempty_csrf_or_token_value():
    client = FakeClient([FakeResponse({"handoff": "h-1", "server": "s-1"})])

    asyncio.run(download.start_download(
        {"url": "https://www.qobuz.com/track", "csrf": "", "token": "fallback-token"},
        expiry=123,
        country="NL",
        client=client,
    ))

    assert client.calls[0][2]["json"]["token"]["primary"] == "fallback-token"


@pytest.mark.parametrize("server", ["server.evil", "server/../../evil", "server@evil"])
def test_run_job_rejects_invalid_server_before_network_request(server, tmp_path):
    client = FakeClient([])

    with pytest.raises(ValueError, match="server"):
        asyncio.run(download.run_job("handoff", server, tmp_path, "Track", client=client))

    assert client.calls == []


def test_download_module_import_does_not_import_optional_clients():
    import subprocess, sys
    result = subprocess.run([sys.executable, "-c", "import sys; import src.lucida; import src.lucida.download; assert 'httpx' not in sys.modules; assert 'playwright' not in sys.modules; assert 'pyjson5' not in sys.modules"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_run_job_encodes_handoff_as_single_url_path_segment(tmp_path):
    client = FakeClient([
        FakeResponse({"status": "completed"}),
        FakeResponse(body=b"audio", headers={"content-type": "audio/mpeg"}),
    ])

    asyncio.run(download.run_job(
        "handoff/../../other?token=bad#fragment", "server", tmp_path, "Track", client=client
    ))

    assert client.calls[0][1] == (
        "https://server.lucida.to/api/fetch/request/"
        "handoff%2F..%2F..%2Fother%3Ftoken%3Dbad%23fragment"
    )


@pytest.mark.parametrize("max_stream_retries", [-1, 1.5, "1", True])
def test_run_job_rejects_invalid_stream_retry_count_before_network_request(max_stream_retries, tmp_path):
    client = FakeClient([])

    with pytest.raises(ValueError, match="max_stream_retries"):
        asyncio.run(download.run_job(
            "handoff", "server", tmp_path, "Track", client=client,
            max_stream_retries=max_stream_retries,
        ))

    assert client.calls == []
