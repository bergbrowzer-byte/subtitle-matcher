"""Tests for encoding detection."""

from subtitle_matcher.encoding import detect_encoding


def test_detects_utf8() -> None:
    assert detect_encoding("hello".encode()).name == "UTF-8"


def test_detects_utf8_bom() -> None:
    assert detect_encoding("\ufeffhello".encode("utf-8-sig")).name == "UTF-8 BOM"


def test_detects_utf16_le_with_bom() -> None:
    assert detect_encoding(b"\xff\xfe" + "hello".encode("utf-16-le")).name == "UTF-16 LE"


def test_detects_utf16_be_with_bom() -> None:
    assert detect_encoding(b"\xfe\xff" + "hello".encode("utf-16-be")).name == "UTF-16 BE"


def test_detects_utf16_le_without_bom() -> None:
    assert detect_encoding("hello".encode("utf-16-le")).name == "UTF-16 LE"


def test_detects_utf16_be_without_bom() -> None:
    assert detect_encoding("hello".encode("utf-16-be")).name == "UTF-16 BE"


def test_falls_back_to_windows_1252() -> None:
    assert detect_encoding("café €".encode("cp1252")).name == "Windows-1252"
