"""Tests for automatic subtitle synchronization."""

from datetime import timedelta

import pytest

pytest.importorskip("rapidfuzz")

from subtitle_matcher.srt import parse_srt  # noqa: E402
from subtitle_matcher.subtitle import Subtitle  # noqa: E402
from subtitle_matcher.sync import (  # noqa: E402
    SynchronizationOptions,
    find_sync_anchors,
    interpolate_correction,
    split_anchors_into_segments,
    synchronize_subtitle_files,
    synchronize_subtitles,
)


def cue(index: int, start_seconds: float, end_seconds: float, text: str) -> Subtitle:
    """Create a subtitle cue for synchronization tests."""
    return Subtitle(
        index=index,
        start=timedelta(seconds=start_seconds),
        end=timedelta(seconds=end_seconds),
        text=text,
    )


def test_synchronizes_variable_timing_drift() -> None:
    reference = [
        cue(1, 10, 12, "First line"),
        cue(2, 20, 22, "Second line"),
        cue(3, 30, 32, "Third line"),
    ]
    original = [
        cue(101, 9, 11, "First line"),
        cue(102, 18, 20, "Second line"),
        cue(103, 27, 29, "Third line"),
    ]

    report = synchronize_subtitles(reference, original)

    assert [subtitle.index for subtitle in report.corrected_subtitles] == [
        101,
        102,
        103,
    ]
    assert [subtitle.text for subtitle in report.corrected_subtitles] == [
        "First line",
        "Second line",
        "Third line",
    ]
    assert [subtitle.start for subtitle in report.corrected_subtitles] == [
        timedelta(seconds=10),
        timedelta(seconds=20),
        timedelta(seconds=30),
    ]
    assert [anchor.correction for anchor in report.anchors] == [
        timedelta(seconds=1),
        timedelta(seconds=2),
        timedelta(seconds=3),
    ]


def test_interpolates_between_anchor_points_for_non_anchor_cues() -> None:
    reference = [cue(1, 10, 12, "Alpha"), cue(3, 30, 32, "Omega")]
    original = [
        cue(1, 9, 11, "Alpha"),
        cue(2, 18, 20, "Middle text without matching anchor"),
        cue(3, 27, 29, "Omega"),
    ]

    report = synchronize_subtitles(reference, original)

    assert report.corrected_subtitles[1].start == timedelta(seconds=20)
    assert report.corrected_subtitles[1].end == timedelta(seconds=22, milliseconds=222)


def test_splits_anchors_into_segments_when_drift_changes_abruptly() -> None:
    reference = [
        cue(1, 10, 11, "One"),
        cue(2, 20, 21, "Two"),
        cue(3, 80, 81, "Three"),
    ]
    original = [
        cue(1, 9, 10, "One"),
        cue(2, 19, 20, "Two"),
        cue(3, 70, 71, "Three"),
    ]
    anchors = find_sync_anchors(reference, original)
    options = SynchronizationOptions(max_segment_drift_change=timedelta(seconds=2))

    segments = split_anchors_into_segments(anchors, options)

    assert [len(segment.anchors) for segment in segments] == [2, 1]
    assert segments[0].start_correction == timedelta(seconds=1)
    assert segments[1].start_correction == timedelta(seconds=10)


def test_returns_original_subtitles_when_no_anchors_are_found() -> None:
    reference = [cue(1, 10, 12, "Completely different")]
    original = [cue(1, 1, 3, "No shared text")]

    report = synchronize_subtitles(reference, original)

    assert report.corrected_subtitles == original
    assert report.anchors == []
    assert report.segments == []


def test_single_anchor_applies_constant_correction() -> None:
    reference = [cue(1, 10, 12, "Same text")]
    original = [cue(1, 5, 7, "Same text"), cue(2, 20, 22, "Unanchored")]

    report = synchronize_subtitles(reference, original)

    assert report.corrected_subtitles[0].start == timedelta(seconds=10)
    assert report.corrected_subtitles[1].start == timedelta(seconds=25)


def test_interpolate_correction_before_and_after_anchor_range() -> None:
    reference = [cue(1, 10, 11, "One"), cue(2, 20, 21, "Two")]
    original = [cue(1, 9, 10, "One"), cue(2, 18, 19, "Two")]
    anchors = find_sync_anchors(reference, original)

    assert interpolate_correction(timedelta(seconds=1), anchors) == timedelta(seconds=1)
    assert interpolate_correction(timedelta(seconds=50), anchors) == timedelta(
        seconds=2
    )


def test_synchronize_subtitle_files_writes_corrected_srt(tmp_path) -> None:
    reference_path = tmp_path / "reference.srt"
    original_path = tmp_path / "original.srt"
    output_path = tmp_path / "corrected.srt"
    reference_path.write_text(
        "1\n00:00:10,000 --> 00:00:12,000\nHello\n\n"
        "2\n00:00:20,000 --> 00:00:22,000\nWorld\n",
        encoding="utf-8",
    )
    original_path.write_text(
        "7\n00:00:09,000 --> 00:00:11,000\nHello\n\n"
        "8\n00:00:18,000 --> 00:00:20,000\nWorld\n",
        encoding="utf-8",
    )

    report = synchronize_subtitle_files(reference_path, original_path, output_path)
    written_subtitles = parse_srt(output_path.read_text(encoding="utf-8"))

    assert written_subtitles == report.corrected_subtitles
    assert [(subtitle.index, subtitle.text) for subtitle in written_subtitles] == [
        (7, "Hello"),
        (8, "World"),
    ]
    assert [subtitle.start for subtitle in written_subtitles] == [
        timedelta(seconds=10),
        timedelta(seconds=20),
    ]


def test_sync_command_writes_output_file(tmp_path, capsys) -> None:
    from subtitle_matcher.cli import main

    reference_path = tmp_path / "reference.srt"
    original_path = tmp_path / "original.srt"
    output_path = tmp_path / "corrected.srt"
    reference_path.write_text(
        "1\n00:00:10,000 --> 00:00:12,000\nHello\n", encoding="utf-8"
    )
    original_path.write_text(
        "9\n00:00:09,000 --> 00:00:11,000\nHello\n", encoding="utf-8"
    )

    exit_code = main(
        ["sync", str(reference_path), str(original_path), str(output_path)]
    )

    assert exit_code == 0
    assert output_path.exists()
    assert "anchors: 1" in capsys.readouterr().out
    assert parse_srt(output_path.read_text(encoding="utf-8"))[0].index == 9
