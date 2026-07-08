# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Core subtitle matching engine with offset detection, RapidFuzz scoring, missing cue
  handling and inserted cue reporting.
- Automatic subtitle synchronization engine with variable drift correction, segment
  estimation, interpolation and corrected SRT output.

## [0.0.1] - 2026-07-06

### Added

- Initial Python 3.12 project foundation.
- SRT subtitle dataclass, parser and writer.
- Encoding detection for UTF-8, UTF-8 BOM, UTF-16 LE, UTF-16 BE and Windows-1252.
- `subtitle-matcher info <file>` CLI command.
- Unit tests and GitHub Actions workflow.
