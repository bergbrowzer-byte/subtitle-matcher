"""Command line interface for Subtitle Matcher."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

from subtitle_matcher.encoding import read_text
from subtitle_matcher.srt import parse_srt
from subtitle_matcher.subtitle import Subtitle


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Subtitle Matcher command line interface."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(prog="subtitle-matcher")
    parser.add_argument("--version", action="version", version="subtitle-matcher 0.0.1")
    subparsers = parser.add_subparsers(dest="command", required=True)

    info_parser = subparsers.add_parser("info", help="Show summary information for an SRT file")
    info_parser.add_argument("file", type=Path, help="SRT file to inspect")
    info_parser.set_defaults(func=_info_command)

    return parser


def _info_command(args: argparse.Namespace) -> int:
    """Print information about a subtitle file."""
    text, encoding = read_text(args.file)
    subtitles = parse_srt(text)
    total_duration = sum((subtitle.duration for subtitle in subtitles), timedelta())
    average_duration = total_duration / len(subtitles) if subtitles else timedelta()
    average_characters = _average_characters(subtitles)

    print(f"encoding: {encoding.name}")
    print(f"subtitle count: {len(subtitles)}")
    print(f"total duration: {_format_duration(total_duration)}")
    print(f"average subtitle duration: {_format_duration(average_duration)}")
    print(f"average characters per subtitle: {average_characters:.2f}")
    return 0


def _average_characters(subtitles: list[Subtitle]) -> float:
    """Return the average number of characters per subtitle cue."""
    if not subtitles:
        return 0.0
    return sum(len(subtitle.text) for subtitle in subtitles) / len(subtitles)


def _format_duration(value: timedelta) -> str:
    """Format a duration as seconds with millisecond precision."""
    return f"{value.total_seconds():.3f}s"


if __name__ == "__main__":
    raise SystemExit(main())
