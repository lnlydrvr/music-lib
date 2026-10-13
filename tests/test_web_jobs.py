import json
import asyncio

from src.web.jobs import Job


def test_job_serializes_descriptor_progress_and_null_success_error():
    job = Job("j1", {"code": "jobs.download.name", "params": {}, "message": "Download"})
    job.push({"code": "jobs.download.fetching_info", "params": {}, "message": "Fetching…"}, 12)
    job.done({"ok": True})

    data = job.to_dict()
    assert data["name"]["code"] == "jobs.download.name"
    assert data["error"] is None
    assert data["progress"] == [{
        "type": "progress",
        "message": {"code": "jobs.download.fetching_info", "params": {}, "message": "Fetching…"},
            "msg": "Fetching…",
        "percent": 12,
    }]


def test_job_accepts_legacy_strings_and_sse_has_terminal_error_then_end():
    job = Job("j2", "Download")
    job.push("Working")
    job.fail("Provider failed")

    data = job.to_dict()
    assert data["name"] == "Download"
    assert data["error"] == "Provider failed"
    async def collect():
        return [chunk async for chunk in job.stream().body_iterator]

    events = asyncio.run(collect())
    payloads = [json.loads(chunk.split("data: ", 1)[1]) for chunk in events]
    assert payloads == [
        {"type": "progress", "message": "Working", "msg": "Working"},
        {"type": "error", "error": "Provider failed"},
        {"type": "end"},
    ]
