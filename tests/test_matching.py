"""Tests for the subtitle matching engine."""

from datetime import timedelta

import pytest

rapidfuzz = pytest.importorskip("rapidfuzz")

from subtitle_matcher.matching import (  # noqa: E402
    MatchOptions,
    detect_constant_offset,
    match_subtitle_files,
    match_subtitles,
)
from subtitle_matcher.subtitle import Subtitle  # noqa: E402


def cue(index: int, start_seconds: float, end_seconds: float, text: str) -> Subtitle:
    """Create a subtitle cue for tests."""
    return Subtitle(
        index=index,
        start=timedelta(seconds=start_seconds),
        end=timedelta(seconds=end_seconds),
        text=text,
    )


def test_matches_subtitles_with_detected_constant_offset() -> None:
    source = [
        cue(1, 1, 2, "Hello there"),
        cue(2, 4, 5, "How are you?"),
        cue(3, 8, 9, "Goodbye"),
    ]
    target = [
        cue(1, 3, 4, "Hello there!"),
        cue(2, 6, 7, "How are you"),
        cue(3, 10, 11, "Good bye"),
    ]

    report = match_subtitles(source, target)

    assert report.detected_offset == timedelta(seconds=2)
    assert [match.target.index if match.target else None for match in report.matches] == [
        1,
        2,
        3,
    ]
    assert all(match.confidence >= 80 for match in report.paired_matches)
    assert report.unmatched_targets == []


def test_handles_inserted_target_cues() -> None:
    source = [cue(1, 1, 2, "First"), cue(2, 4, 5, "Second")]
    target = [
        cue(1, 1, 2, "First"),
        cue(2, 2.5, 3, "Inserted target cue"),
        cue(3, 4, 5, "Second"),
    ]

    report = match_subtitles(source, target)

    assert [match.target.index if match.target else None for match in report.matches] == [1, 3]
    assert [subtitle.index for subtitle in report.unmatched_targets] == [2]


def test_handles_missing_target_cues() -> None:
    source = [
        cue(1, 1, 2, "First"),
        cue(2, 4, 5, "Missing in target"),
        cue(3, 8, 9, "Third"),
    ]
    target = [cue(1, 1, 2, "First"), cue(2, 8, 9, "Third")]

    report = match_subtitles(source, target)

    assert [match.target.index if match.target else None for match in report.matches] == [1, None, 2]
    assert report.matches[1].confidence == 0
    assert report.matches[1].time_delta is None


def test_rejects_low_confidence_text_match_even_when_timing_is_close() -> None:
    source = [cue(1, 1, 2, "The original subtitle text")]
    target = [cue(1, 1, 2, "Completely unrelated dialogue")]
    options = MatchOptions(min_confidence=80)

    report = match_subtitles(source, target, options)

    assert report.matches[0].target is None
    assert report.unmatched_targets == target


def test_offset_detection_returns_zero_without_text_anchors() -> None:
    source = [cue(1, 1, 2, "Alpha")]
    target = [cue(1, 10, 11, "Omega")]

    assert detect_constant_offset(source, target) == timedelta()


def test_match_subtitle_files_reads_and_matches_srt_files(tmp_path) -> None:
    source_path = tmp_path / "source.srt"
    target_path = tmp_path / "target.srt"
    source_path.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8"
    )
    target_path.write_text(
        "1\n00:00:02,500 --> 00:00:03,500\nHello!\n", encoding="utf-8"
    )

    report = match_subtitle_files(source_path, target_path)

    assert report.detected_offset == timedelta(milliseconds=1500)
    assert report.matches[0].target is not None
    assert report.matches[0].target.text == "Hello!"
