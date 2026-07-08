"""Encoding detection for subtitle files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DetectedEncoding:
    """Detected text encoding metadata."""

    name: str
    codec: str


_UTF8_BOM = b"\xef\xbb\xbf"
_UTF16_LE_BOM = b"\xff\xfe"
_UTF16_BE_BOM = b"\xfe\xff"


def detect_encoding(data: bytes) -> DetectedEncoding:
    """Detect a supported subtitle file encoding.

    The detector supports UTF-8, UTF-8 BOM, UTF-16 LE, UTF-16 BE and
    Windows-1252. It prefers explicit byte-order marks, then strict UTF-8, then
    UTF-16 heuristics, and finally falls back to Windows-1252.
    """
    if data.startswith(_UTF8_BOM):
        return DetectedEncoding("UTF-8 BOM", "utf-8-sig")
    if data.startswith(_UTF16_LE_BOM):
        return DetectedEncoding("UTF-16 LE", "utf-16-le")
    if data.startswith(_UTF16_BE_BOM):
        return DetectedEncoding("UTF-16 BE", "utf-16-be")

    if _looks_like_utf16_le(data):
        return DetectedEncoding("UTF-16 LE", "utf-16-le")
    if _looks_like_utf16_be(data):
        return DetectedEncoding("UTF-16 BE", "utf-16-be")

    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    else:
        return DetectedEncoding("UTF-8", "utf-8")

    return DetectedEncoding("Windows-1252", "cp1252")


def read_text(path: str | Path) -> tuple[str, DetectedEncoding]:
    """Read a file using the detected supported encoding."""
    data = Path(path).read_bytes()
    encoding = detect_encoding(data)
    text = data.decode(encoding.codec)
    return text.lstrip("\ufeff"), encoding


def _looks_like_utf16_le(data: bytes) -> bool:
    """Return whether bytes resemble UTF-16 little-endian text without a BOM."""
    return _null_ratio(data[1::2]) > 0.35 and _null_ratio(data[0::2]) < 0.10


def _looks_like_utf16_be(data: bytes) -> bool:
    """Return whether bytes resemble UTF-16 big-endian text without a BOM."""
    return _null_ratio(data[0::2]) > 0.35 and _null_ratio(data[1::2]) < 0.10


def _null_ratio(data: bytes) -> float:
    """Return the fraction of NUL bytes in data."""
    if not data:
        return 0.0
    return data.count(0) / len(data)
