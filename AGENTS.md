# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project Overview

`aws-sso-manager` (package `awsssomanager`) is a CLI that writes short-lived AWS credentials
into `~/.aws/credentials` for every account and role a user can reach, with easy profile names
(`<account_id>_<role>`, `<account_id>`, `<account_name>`).

**Technology Stack:**
- Python 3.11+ with UV for dependency management
- [Taskfile](https://taskfile.dev/) (go-task) for task running (`Taskfile.yml`)
- Ruff for linting and formatting
- ty for type checking
- pytest for testing with pytest-cov for coverage
- boto3 for AWS APIs, click for the CLI, yamale for config validation
- mkdocs-material for docs (`docs/`, `mkdocs.yml`)

## Common Development Commands

### Setup and Installation
```bash
task setup # uv sync --all-groups --all-extras
uv run aws-sso-manager --help
```

### Testing
```bash
task test # uv run pytest tests/unit
task test:cov # uv run pytest --cov=awsssomanager tests/unit
uv run pytest tests/unit/test_config.py # single file
task test:integration # requires live AWS / IdP access
```

### Code Quality
```bash
task format # uv run ruff format .
task lint # uv run ruff check .
task lint:fix # uv run ruff check . --fix
task typecheck # uv run ty check awsssomanager
task check # lint + format check + typecheck + tests
task lock:check # verify lockfile is up-to-date
```

### Building
```bash
task build # uv build
task docs:build # uv run mkdocs build --no-directory-urls
```

## Architecture and Code Organization

```
awsssomanager/
├── __init__.py          # Re-exports path constants
├── constants.py         # ~/.aws paths, schema path
├── cli/cli.py           # click group: `configure`, `login`
├── config/
│   ├── config.py        # AWSSSOManagerConfig: user config + generated device state
│   └── schema.yml       # yamale schema for the user config
├── sso/                 # AWS IAM Identity Center
│   ├── device.py        # sso-oidc client registration + device authorization
│   ├── token.py         # sso-oidc CreateToken
│   ├── roles.py         # ListAccountRoles, GetRoleCredentials, role priority
│   └── credentials.py   # orchestration + ~/.aws/credentials read/write
└── utils/               # shell + file/schema validation helpers

tests/unit/              # pytest default (data/ holds fixture configs)
```

### Runtime files

- `~/.aws/aws-sso-manager.yml` — copy of the user's config plus generated device secrets.
  Written by `configure` / `login`.
- `~/.aws/credentials` — credentials sections written by this tool. Sections written by other
  tools (for example saml2aws) must be preserved.

## Code Style and Standards

### Python Style

**Imports:**
- Use absolute imports over relative imports
- Order imports alphabetically (isort via ruff)

**Type Hints:**
- Use type hints for all function parameters and returns
- Prefer built-in generics (`list[str]`, `dict[str, int]`) over `typing` equivalents
- Use union syntax (`str | None`) instead of `Optional[str]`

**Naming Conventions:**
- snake_case for functions and variables
- PascalCase for classes
- UPPER_CASE for constants
- Maximum line length: 100 characters

**Docstrings:**
- Use Google-style docstrings (configured in ruff)
- Document all public APIs
- Focus on why, not what
- Every module must have a module-level docstring

**Other Rules:**
- `__init__.py` files must define `__all__` to declare the public API (no star imports)
- Always specify exception types — never use bare `except:`
- Constants over magic numbers
- Single responsibility per function

### Testing Requirements

- Write tests before fixing bugs
- Test edge cases and error scenarios
- Never touch the real `~/.aws` from unit tests — monkeypatch the path constants onto `tmp_path`
- Stub AWS calls (botocore `Stubber` or pytest-mock); never call live AWS from unit tests
- Mark integration tests with `@pytest.mark.integration`
- **MUST run `task format && task lint` before completion**

### Security

- Never commit credentials or sensitive information
- Never log access keys, secret keys, session tokens, or SAML assertions
- Files containing credentials or session state must be user-only (0600 / 0700)

### Version Control

- Feature branches: `feature/<description>`; bugfix branches: `fix/<description>`;
  tooling: `chore/<description>`
- Small, focused commits with clear messages
- Follow semantic versioning (MAJOR.MINOR.PATCH)

### Changelog

- **MUST update `CHANGELOG.md`** when making user-facing changes
- Append to the `[Unreleased]` section at the top, under `Added`, `Changed`, `Fixed`, `Removed`
- Follow [Keep a Changelog](https://keepachangelog.com/) format
- Do not modify entries for already-released versions

### Development Workflow

1. Create feature branch
2. Make changes following coding standards
3. Run quality checks: `task format && task lint && task typecheck`
4. Run tests: `task test:cov`
5. Verify lockfile: `task lock:check`
6. Update `CHANGELOG.md`
7. Submit PR using the PR template
