# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres
to [Semantic Versioning](https://semver.org/). Releases before this file existed are described in
the [GitHub releases](https://github.com/brett-fitz/aws-sso-manager/releases).

## [Unreleased]

### Changed

- Requires Python 3.11 or newer (previously 3.9).
- Built and managed with uv and hatchling instead of Poetry. Install with
  `pip install awsssomanager` or `uv tool install awsssomanager`.
- Linting and formatting moved from pylint to ruff, with ty for type checking.
- Supports Python 3.15.
- Raised minimum dependency versions to current releases (boto3 1.44, click 8.5, pyyaml 6.0.3,
  yamale 6.1).

### Fixed

- CI never ran for pull requests that only changed package code, because the path filter pointed
  at `aws-sso-manager/**` instead of `awsssomanager/**`.
- The docs build walked the whole repository, including `.venv`, when generating API reference
  pages. It now documents only the `awsssomanager` package.
