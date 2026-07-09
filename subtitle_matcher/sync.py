"""Automatic subtitle synchronization engine.

This module corrects the timing of one subtitle list by comparing its text with a
reference subtitle list. It detects anchors with fuzzy text matching, estimates
local timing corrections, splits the timeline into drift segments, interpolates
between anchor points and emits corrected subtitles while preserving the original
subtitle numbering and text.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from rapidfuzz import fuzz

from subtitle_matcher.encoding import read_text
from subtitle_matcher.srt import parse_srt, write_srt
from subtitle_matcher.subtitle import Subtitle


@dataclass(frozen=True, slots=True)
class SynchronizationOptions:
    """Configuration for automatic subtitle synchronization.

    Attributes:
        min_anchor_score: Minimum RapidFuzz WRatio score for text anchors.
        max_anchor_search_distance: Maximum cue-position distance considered when
            looking for anchor candidates. ``None`` compares against all cues.
        max_segment_gap: Largest original-timeline gap between anchors before a
            new drift segment is started.
        max_segment_drift_change: Largest correction change between consecutive
            anchors before a new drift segment is started.
    """

    min_anchor_score: float = 80.0
    max_anchor_search_distance: int | None = 25
    max_segment_gap: timedelta = timedelta(minutes=3)
    max_segment_drift_change: timedelta = timedelta(seconds=2)


@dataclass(frozen=True, slots=True)
class SyncAnchor:
    """A high-confidence text anchor between an original and reference cue."""

    original: Subtitle
    reference: Subtitle
    score: float

    @property
    def correction(self) -> timedelta:
        """Return the timing correction from original start to reference start."""
        return self.reference.start - self.original.start


@dataclass(frozen=True, slots=True)
class SyncSegment:
    """A contiguous timeline segment with locally estimated timing drift."""

    anchors: list[SyncAnchor]

    @property
    def start(self) -> timedelta:
        """Return the segment start time on the original timeline."""
        return self.anchors[0].original.start

    @property
    def end(self) -> timedelta:
        """Return the segment end time on the original timeline."""
        return self.anchors[-1].original.start

    @property
    def start_correction(self) -> timedelta:
        """Return the correction at the first anchor in the segment."""
        return self.anchors[0].correction

    @property
    def end_correction(self) -> timedelta:
        """Return the correction at the last anchor in the segment."""
        return self.anchors[-1].correction


@dataclass(frozen=True, slots=True)
class SynchronizationReport:
    """Result of synchronizing subtitle timing against a reference file."""

    corrected_subtitles: list[Subtitle]
    anchors: list[SyncAnchor]
    segments: list[SyncSegment]


def synchronize_subtitle_files(
    reference_path: str | Path,
    original_path: str | Path,
    output_path: str | Path,
    options: SynchronizationOptions | None = None,
) -> SynchronizationReport:
    """Synchronize an SRT file and write corrected subtitles to ``output_path``.

    The reference file supplies desired timing. The original file supplies the
    subtitle numbering and text that are preserved in the output SRT.
    """
    reference_text, _ = read_text(reference_path)
    original_text, _ = read_text(original_path)
    report = synchronize_subtitles(
        parse_srt(reference_text), parse_srt(original_text), options
    )
    Path(output_path).write_text(
        write_srt(report.corrected_subtitles), encoding="utf-8"
    )
    return report


def synchronize_subtitles(
    reference_subtitles: list[Subtitle],
    original_subtitles: list[Subtitle],
    options: SynchronizationOptions | None = None,
) -> SynchronizationReport:
    """Correct subtitle timing by interpolating between fuzzy text anchors."""
    resolved_options = options or SynchronizationOptions()
    anchors = find_sync_anchors(
        reference_subtitles, original_subtitles, resolved_options
    )
    if not anchors:
        return SynchronizationReport(original_subtitles.copy(), [], [])

    segments = split_anchors_into_segments(anchors, resolved_options)
    corrected = [
        Subtitle(
            index=subtitle.index,
            start=_correct_time(subtitle.start, anchors),
            end=_correct_time(subtitle.end, anchors),
            text=subtitle.text,
        )
        for subtitle in original_subtitles
    ]
    return SynchronizationReport(corrected, anchors, segments)


def find_sync_anchors(
    reference_subtitles: list[Subtitle],
    original_subtitles: list[Subtitle],
    options: SynchronizationOptions | None = None,
) -> list[SyncAnchor]:
    """Find monotonic text anchors between original and reference subtitles."""
    resolved_options = options or SynchronizationOptions()
    used_reference_positions: set[int] = set()
    anchors: list[SyncAnchor] = []
    last_reference_position = -1

    for original_position, original in enumerate(original_subtitles):
        candidate = _best_reference_anchor(
            original,
            original_position,
            reference_subtitles,
            used_reference_positions,
            last_reference_position,
            resolved_options,
        )
        if candidate is None:
            continue

        reference_position, reference, score = candidate
        used_reference_positions.add(reference_position)
        last_reference_position = reference_position
        anchors.append(SyncAnchor(original=original, reference=reference, score=score))

    return anchors


def split_anchors_into_segments(
    anchors: list[SyncAnchor],
    options: SynchronizationOptions | None = None,
) -> list[SyncSegment]:
    """Split anchors into local drift segments when timing behavior changes."""
    if not anchors:
        return []

    resolved_options = options or SynchronizationOptions()
    segments: list[SyncSegment] = []
    current_segment = [anchors[0]]

    for previous, current in zip(anchors, anchors[1:], strict=False):
        anchor_gap = current.original.start - previous.original.start
        drift_change = abs(current.correction - previous.correction)
        if (
            anchor_gap > resolved_options.max_segment_gap
            or drift_change > resolved_options.max_segment_drift_change
        ):
            segments.append(SyncSegment(current_segment))
            current_segment = []
        current_segment.append(current)

    segments.append(SyncSegment(current_segment))
    return segments


def interpolate_correction(time: timedelta, anchors: list[SyncAnchor]) -> timedelta:
    """Interpolate the timing correction for ``time`` from surrounding anchors."""
    if not anchors:
        return timedelta()
    if len(anchors) == 1 or time <= anchors[0].original.start:
        return anchors[0].correction
    if time >= anchors[-1].original.start:
        return anchors[-1].correction

    for left, right in zip(anchors, anchors[1:], strict=False):
        if left.original.start <= time <= right.original.start:
            return _interpolate_between(time, left, right)

    return anchors[-1].correction


def _best_reference_anchor(
    original: Subtitle,
    original_position: int,
    reference_subtitles: list[Subtitle],
    used_reference_positions: set[int],
    last_reference_position: int,
    options: SynchronizationOptions,
) -> tuple[int, Subtitle, float] | None:
    """Return the best unused monotonic reference cue for an original cue."""
    best: tuple[int, Subtitle, float] | None = None
    for reference_position, reference in enumerate(reference_subtitles):
        if reference_position in used_reference_positions:
            continue
        if reference_position <= last_reference_position:
            continue
        if not _within_anchor_search_window(
            original_position, reference_position, options.max_anchor_search_distance
        ):
            continue

        score = float(fuzz.WRatio(original.text, reference.text))
        if score < options.min_anchor_score:
            continue
        if best is None or score > best[2]:
            best = (reference_position, reference, score)

    return best


def _within_anchor_search_window(
    original_position: int,
    reference_position: int,
    max_distance: int | None,
) -> bool:
    """Return whether two cue positions are close enough to compare."""
    if max_distance is None:
        return True
    return abs(original_position - reference_position) <= max_distance


def _correct_time(time: timedelta, anchors: list[SyncAnchor]) -> timedelta:
    """Apply interpolated correction to a timestamp and clamp at zero."""
    corrected = max(timedelta(), time + interpolate_correction(time, anchors))

    milliseconds = round(corrected.total_seconds() * 1000)
    return timedelta(milliseconds=milliseconds)


def _interpolate_between(
    time: timedelta, left: SyncAnchor, right: SyncAnchor
) -> timedelta:
    """Linearly interpolate correction between two anchors."""
    total_seconds = (right.original.start - left.original.start).total_seconds()
    if total_seconds <= 0:
        return left.correction

    elapsed_seconds = (time - left.original.start).total_seconds()
    ratio = elapsed_seconds / total_seconds
    correction_delta = right.correction - left.correction
    return left.correction + (correction_delta * ratio)
