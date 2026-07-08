"""Core subtitle matching engine.

The matcher aligns a source subtitle list with a target subtitle list by combining
fuzzy text similarity with timing proximity. It first estimates a constant offset
between both files, then performs a greedy one-to-one assignment that tolerates
missing source cues and inserted target cues.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from rapidfuzz import fuzz

from subtitle_matcher.encoding import read_text
from subtitle_matcher.srt import parse_srt
from subtitle_matcher.subtitle import Subtitle


@dataclass(frozen=True, slots=True)
class MatchOptions:
    """Configuration for subtitle matching.

    Attributes:
        min_confidence: Minimum combined score required to pair two cues.
        offset_text_threshold: Minimum text score used while estimating offsets.
        max_offset_candidates: Maximum high-text-similarity pairs to inspect for
            offset estimation.
        max_time_distance: Largest accepted distance from expected target time
            after offset compensation.
        offset_bucket_size: Bucket size used to group similar offset candidates.
        text_weight: Weight assigned to fuzzy text similarity in final scoring.
    """

    min_confidence: float = 60.0
    offset_text_threshold: float = 75.0
    max_offset_candidates: int = 250
    max_time_distance: timedelta = timedelta(seconds=4)
    offset_bucket_size: timedelta = timedelta(milliseconds=100)
    text_weight: float = 0.70

    @property
    def time_weight(self) -> float:
        """Return the timing contribution to a combined confidence score."""
        return 1.0 - self.text_weight


@dataclass(frozen=True, slots=True)
class SubtitleMatch:
    """A mapping from one source cue to an optional target cue.

    ``target`` is ``None`` when no reliable counterpart is found, allowing the
    caller to preserve missing cue information instead of dropping it.
    """

    source: Subtitle
    target: Subtitle | None
    confidence: float
    text_score: float
    time_score: float
    time_delta: timedelta | None


@dataclass(frozen=True, slots=True)
class MatchReport:
    """Complete matching result for two subtitle lists."""

    matches: list[SubtitleMatch]
    unmatched_targets: list[Subtitle]
    detected_offset: timedelta

    @property
    def paired_matches(self) -> list[SubtitleMatch]:
        """Return only source cues that were paired with target cues."""
        return [match for match in self.matches if match.target is not None]


@dataclass(frozen=True, slots=True)
class _Candidate:
    """Internal candidate pair with component scores."""

    target_position: int
    target: Subtitle
    confidence: float
    text_score: float
    time_score: float
    time_delta: timedelta


def match_subtitle_files(
    source_path: str | Path,
    target_path: str | Path,
    options: MatchOptions | None = None,
) -> MatchReport:
    """Read, parse and match two SRT subtitle files."""
    source_text, _ = read_text(source_path)
    target_text, _ = read_text(target_path)
    return match_subtitles(parse_srt(source_text), parse_srt(target_text), options)


def match_subtitles(
    source_subtitles: list[Subtitle],
    target_subtitles: list[Subtitle],
    options: MatchOptions | None = None,
) -> MatchReport:
    """Match source subtitles to target subtitles with confidence scores."""
    resolved_options = options or MatchOptions()
    detected_offset = detect_constant_offset(
        source_subtitles, target_subtitles, resolved_options
    )
    used_target_positions: set[int] = set()
    matches: list[SubtitleMatch] = []

    for source in source_subtitles:
        candidate = _best_candidate(
            source,
            target_subtitles,
            used_target_positions,
            detected_offset,
            resolved_options,
        )
        if candidate is None:
            matches.append(
                SubtitleMatch(
                    source=source,
                    target=None,
                    confidence=0.0,
                    text_score=0.0,
                    time_score=0.0,
                    time_delta=None,
                )
            )
            continue

        used_target_positions.add(candidate.target_position)
        matches.append(
            SubtitleMatch(
                source=source,
                target=candidate.target,
                confidence=candidate.confidence,
                text_score=candidate.text_score,
                time_score=candidate.time_score,
                time_delta=candidate.time_delta,
            )
        )

    unmatched_targets = [
        target
        for position, target in enumerate(target_subtitles)
        if position not in used_target_positions
    ]
    return MatchReport(matches, unmatched_targets, detected_offset)


def detect_constant_offset(
    source_subtitles: list[Subtitle],
    target_subtitles: list[Subtitle],
    options: MatchOptions | None = None,
) -> timedelta:
    """Estimate the constant time offset between source and target subtitles.

    The returned value should be added to source cue times to predict target cue
    times. If no reliable text anchors exist, the function returns zero.
    """
    resolved_options = options or MatchOptions()
    offset_scores: dict[int, float] = {}
    inspected = 0

    for source in source_subtitles:
        for target in target_subtitles:
            text_score = _text_similarity(source.text, target.text)
            if text_score < resolved_options.offset_text_threshold:
                continue
            offset = target.start - source.start
            bucket = _bucket_offset(offset, resolved_options.offset_bucket_size)
            offset_scores[bucket] = offset_scores.get(bucket, 0.0) + text_score
            inspected += 1
            if inspected >= resolved_options.max_offset_candidates:
                break
        if inspected >= resolved_options.max_offset_candidates:
            break

    if not offset_scores:
        return timedelta()

    best_bucket = max(offset_scores, key=offset_scores.get)
    return timedelta(milliseconds=best_bucket)


def _best_candidate(
    source: Subtitle,
    targets: list[Subtitle],
    used_target_positions: set[int],
    detected_offset: timedelta,
    options: MatchOptions,
) -> _Candidate | None:
    """Return the best unused target candidate for a source cue."""
    best: _Candidate | None = None
    for target_position, target in enumerate(targets):
        if target_position in used_target_positions:
            continue

        time_delta = target.start - (source.start + detected_offset)
        time_score = _time_score(abs(time_delta), options.max_time_distance)
        if time_score <= 0:
            continue

        text_score = _text_similarity(source.text, target.text)
        confidence = _combined_score(text_score, time_score, options)
        if confidence < options.min_confidence:
            continue

        candidate = _Candidate(
            target_position, target, confidence, text_score, time_score, time_delta
        )
        if best is None or candidate.confidence > best.confidence:
            best = candidate

    return best


def _text_similarity(source_text: str, target_text: str) -> float:
    """Return RapidFuzz WRatio text similarity as a percentage score."""
    return float(fuzz.WRatio(source_text, target_text))


def _time_score(delta: timedelta, max_delta: timedelta) -> float:
    """Return a 0-100 score based on distance from the expected start time."""
    max_seconds = max_delta.total_seconds()
    if max_seconds <= 0:
        return 0.0
    ratio = delta.total_seconds() / max_seconds
    return max(0.0, 100.0 * (1.0 - ratio))


def _combined_score(
    text_score: float, time_score: float, options: MatchOptions
) -> float:
    """Combine text and timing scores into one confidence value."""
    return (text_score * options.text_weight) + (time_score * options.time_weight)


def _bucket_offset(offset: timedelta, bucket_size: timedelta) -> int:
    """Round an offset to a bucket and return it as milliseconds."""
    bucket_ms = max(1, int(bucket_size.total_seconds() * 1000))
    offset_ms = int(offset.total_seconds() * 1000)
    return round(offset_ms / bucket_ms) * bucket_ms
