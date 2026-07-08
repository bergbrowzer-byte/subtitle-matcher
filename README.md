# Subtitle Matcher

Subtitle Matcher is an open source Python tool for working with subtitle files.

The long-term goal is to combine timing from one subtitle file with text from
another subtitle file. Version 0.0.1 intentionally focuses on a reliable project
foundation and SRT inspection utilities; subtitle matching is not implemented yet.

## Features in v0.0.1

- Python 3.12 package
- SRT parser and writer
- Subtitle dataclass
- Encoding detection for:
  - UTF-8
  - UTF-8 BOM
  - UTF-16 LE
  - UTF-16 BE
  - Windows-1252
- Command line interface for inspecting SRT files
- Unit tests and GitHub Actions CI
- MIT License

## Matching engine

The matching engine compares source and target subtitle cues, estimates a
constant timing offset, scores text similarity with RapidFuzz and reports both
paired and unmatched cues. It is available as a Python API; GUI support is not
implemented yet.

```python
from subtitle_matcher.matching import match_subtitle_files

report = match_subtitle_files("source.srt", "target.srt")
print(report.detected_offset)
print(report.paired_matches)
```

## Installation

```bash
python -m pip install .
```

For development, install the package in editable mode with pytest:

```bash
python -m pip install -e . pytest
```

## Usage

Show information about an SRT file:

```bash
subtitle-matcher info path/to/subtitles.srt
```

Example output:

```text
encoding: UTF-8
subtitle count: 2
total duration: 5.000s
average subtitle duration: 2.500s
average characters per subtitle: 5.50
```

## Development

Run the test suite:

```bash
pytest
```

## Roadmap

Future versions will focus on matching subtitle timing from file A with subtitle
text from file B, including split and merge support, confidence scoring and
conflict reporting.
