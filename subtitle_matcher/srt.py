"""SRT parsing and writing."""

from __future__ import annotations

import re
from datetime import timedelta

from subtitle_matcher.subtitle import Subtitle

_TIMESTAMP_RE = re.compile(
    r"^(?P<start>\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*"
    r"(?P<end>\d{2}:\d{2}:\d{2},\d{3})$"
)


def parse_srt(text: str) -> list[Subtitle]:
    """Parse SRT text into subtitle cues."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    subtitles: list[Subtitle] = []
    for block_number, block in enumerate(re.split(r"\n{2,}", normalized), start=1):
        lines = block.split("\n")
        if len(lines) < 3:
            raise ValueError(f"Invalid SRT block {block_number}: expected index, time and text")

        try:
            index = int(lines[0].strip())
        except ValueError as exc:
            raise ValueError(f"Invalid SRT block {block_number}: invalid index") from exc

        match = _TIMESTAMP_RE.match(lines[1].strip())
        if match is None:
            raise ValueError(f"Invalid SRT block {block_number}: invalid timestamp line")

        start = parse_timestamp(match.group("start"))
        end = parse_timestamp(match.group("end"))
        if end < start:
            raise ValueError(f"Invalid SRT block {block_number}: end time precedes start time")

        subtitles.append(Subtitle(index=index, start=start, end=end, text="\n".join(lines[2:])))

    return subtitles


def write_srt(subtitles: list[Subtitle]) -> str:
    """Serialize subtitle cues to SRT text."""
    blocks = []
    for subtitle in subtitles:
        blocks.append(
            "\n".join(
                [
                    str(subtitle.index),
                    f"{format_timestamp(subtitle.start)} --> {format_timestamp(subtitle.end)}",
                    subtitle.text,
                ]
            )
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def parse_timestamp(value: str) -> timedelta:
    """Parse an SRT timestamp into a ``timedelta``."""
    hours_text, minutes_text, seconds_text = value.split(":")
    seconds_text, milliseconds_text = seconds_text.split(",")
    return timedelta(
        hours=int(hours_text),
        minutes=int(minutes_text),
        seconds=int(seconds_text),
        milliseconds=int(milliseconds_text),
    )


def format_timestamp(value: timedelta) -> str:
    """Format a ``timedelta`` as an SRT timestamp."""
    total_milliseconds = int(value.total_seconds() * 1000)
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"
