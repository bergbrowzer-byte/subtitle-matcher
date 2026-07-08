"""Subtitle Matcher package."""

from subtitle_matcher.encoding import DetectedEncoding, detect_encoding, read_text
from subtitle_matcher.srt import parse_srt, write_srt
from subtitle_matcher.subtitle import Subtitle

__all__ = [
    "DetectedEncoding",
    "Subtitle",
    "detect_encoding",
    "parse_srt",
    "read_text",
    "write_srt",
]
