"""Tests for the command line interface."""

from subtitle_matcher.cli import main


def test_info_command_prints_subtitle_statistics(tmp_path, capsys) -> None:
    subtitle_file = tmp_path / "sample.srt"
    subtitle_file.write_text(
        "1\n00:00:01,000 --> 00:00:03,000\nHello\n\n"
        "2\n00:00:04,000 --> 00:00:07,000\nWorld!\n",
        encoding="utf-8",
    )

    exit_code = main(["info", str(subtitle_file)])

    assert exit_code == 0
    assert capsys.readouterr().out == (
        "encoding: UTF-8\n"
        "subtitle count: 2\n"
        "total duration: 5.000s\n"
        "average subtitle duration: 2.500s\n"
        "average characters per subtitle: 5.50\n"
    )
