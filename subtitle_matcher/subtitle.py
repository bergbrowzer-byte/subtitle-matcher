"""Core subtitle data structures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True, slots=True)
class Subtitle:
    """A single subtitle cue.

    Attributes:
        index: One-based cue number from the source subtitle file.
        start: Cue start time.
        end: Cue end time.
        text: Cue text, preserving internal line breaks.
    """

    index: int
    start: timedelta
    end: timedelta
    text: str

    @property
    def duration(self) -> timedelta:
        """Return the cue duration."""
        return self.end - self.start
