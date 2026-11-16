"""Shared fixtures: keep every test away from the real ~/.aws."""

from pathlib import Path

import pytest


# Every module-level copy of a path constant. `from x import NAME` binds a copy, so each
# importing module has to be patched; test_isolation.py fails if a new copy is missed.
_STR_PATHS = {
    "AWS_DIR": lambda d: f"{d}/",
    "CREDENTIALS_FILE": lambda d: str(d / "credentials"),
    "SSO_MANAGER_CONFIG_FILE": lambda d: str(d / "aws-sso-manager.yml"),
}
_PATCH_TARGETS = {
    "awsssomanager.constants": ("AWS_DIR", "CREDENTIALS_FILE", "SSO_MANAGER_CONFIG_FILE"),
    "awsssomanager": ("AWS_DIR", "CREDENTIALS_FILE", "SSO_MANAGER_CONFIG_FILE"),
    "awsssomanager.config.config": ("AWS_DIR", "SSO_MANAGER_CONFIG_FILE"),
    "awsssomanager.cli.cli": ("SSO_MANAGER_CONFIG_FILE",),
    "awsssomanager.credentials_file": ("CREDENTIALS_FILE",),
}
_BROWSER_PROFILE_MODULES = ("awsssomanager.constants", "awsssomanager.saml.browser")


@pytest.fixture(autouse=True)
def aws_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every ~/.aws path at a temp directory, for every test (autouse).

    Opt-in isolation let a test write fixture credentials into the developer's real
    ~/.aws/credentials, so this is deliberately not optional.
    """
    directory = tmp_path / ".aws"
    for module, names in _PATCH_TARGETS.items():
        for name in names:
            monkeypatch.setattr(f"{module}.{name}", _STR_PATHS[name](directory))
    for module in _BROWSER_PROFILE_MODULES:
        monkeypatch.setattr(
            f"{module}.BROWSER_PROFILE_DIR", directory / "aws-sso-manager" / "browser"
        )
    return directory


@pytest.fixture
def credentials_path(aws_dir: Path) -> Path:
    return aws_dir / "credentials"


@pytest.fixture
def saved_config_path(aws_dir: Path) -> Path:
    aws_dir.mkdir(parents=True, exist_ok=True)
    return aws_dir / "aws-sso-manager.yml"
