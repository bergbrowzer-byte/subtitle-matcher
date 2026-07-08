"""Tests for SRT parsing and writing."""

from datetime import timedelta

import pytest

from subtitle_matcher.srt import format_timestamp, parse_srt, parse_timestamp, write_srt
from subtitle_matcher.subtitle import Subtitle


SRT_TEXT = """1
00:00:01,000 --> 00:00:03,500
Hello world.

2
00:00:04,000 --> 00:00:05,250
Second line
continues.
"""


def test_parse_srt() -> None:
    subtitles = parse_srt(SRT_TEXT)

    assert subtitles == [
        Subtitle(1, timedelta(seconds=1), timedelta(seconds=3, milliseconds=500), "Hello world."),
        Subtitle(
            2,
            timedelta(seconds=4),
            timedelta(seconds=5, milliseconds=250),
            "Second line\ncontinues.",
        ),
    ]


def test_write_srt() -> None:
    subtitles = parse_srt(SRT_TEXT)

    assert write_srt(subtitles) == SRT_TEXT


def test_parse_empty_srt() -> None:
    assert parse_srt("\n\n") == []


def test_parse_invalid_block_raises_value_error() -> None:
    with pytest.raises(ValueError, match="invalid timestamp"):
        parse_srt("1\nnot a timestamp\nText")


def test_timestamp_roundtrip() -> None:
    value = timedelta(hours=1, minutes=2, seconds=3, milliseconds=456)

    assert parse_timestamp(format_timestamp(value)) == value
