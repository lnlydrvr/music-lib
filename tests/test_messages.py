"""Contracts for backend-localized message descriptors."""

from pathlib import Path

import pytest

from src.messages import format_message
from src.web.messages import message


def test_message_uses_empty_params_and_english_fallback():
    assert message("api.errors.example", fallback="Example error") == {
        "code": "api.errors.example",
        "params": {},
        "message": "Example error",
    }


def test_message_keeps_nested_json_params():
    params = {"track": {"title": "Song", "artists": ["One", "Two"]}}

    assert message("jobs.example", params, fallback="Working") == {
        "code": "jobs.example",
        "params": params,
        "message": "Working",
    }


def test_message_rejects_non_json_params():
    with pytest.raises(TypeError, match="JSON"):
        message("api.errors.example", {"path": Path("/tmp/song.mp3")}, fallback="Example error")


@pytest.mark.parametrize(
    "params",
    [
        {"tracks": ("One", "Two")},
        {1: "non-string key"},
    ],
)
def test_message_rejects_python_values_that_do_not_match_json_wire_types(params):
    with pytest.raises(TypeError, match="JSON"):
        message("api.errors.example", params, fallback="Example error")


def test_message_requires_nonblank_fallback():
    with pytest.raises(ValueError, match="fallback"):
        message("api.errors.example", fallback="  ")


def test_format_message_prints_descriptor_english_fallback():
    assert format_message({
        "code": "diagnostics.example",
        "params": {"field": "title"},
        "message": "Missing title tag",
    }) == "Missing title tag"
