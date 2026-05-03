"""Tests for tools.timeparse.parse_time_seconds."""

import pytest

from tools.timeparse import parse_time_seconds


@pytest.mark.parametrize(
    "text,expected",
    [
        ("0", 0.0),
        ("90", 90.0),
        ("3661.25", 3661.25),
        ("  45 ", 45.0),
        ("05:30", 330.0),
        ("0:05.5", 5.5),
        ("90:00", 5400.0),
        ("1:15:30", 4530.0),
        ("0:0:0", 0.0),
        ("2:59:59.5", 10799.5),
    ],
)
def test_parse_time_seconds_accepted(text: str, expected: float) -> None:
    assert parse_time_seconds(text) == pytest.approx(expected)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "-10",
        "5:-1",
        "5:-0.1",
        "1:60:00",
        "abc",
        "::",
        "1:2:3:4",
    ],
)
def test_parse_time_seconds_rejects(text: str) -> None:
    with pytest.raises(ValueError):
        parse_time_seconds(text)
