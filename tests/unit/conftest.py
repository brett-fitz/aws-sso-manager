"""Shared fixtures: keep every test away from the real ~/.aws."""

from pathlib import Path

import pytest


@pytest.fixture
def aws_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point every ~/.aws path at a temp directory."""
    directory = tmp_path / ".aws"
    monkeypatch.setattr("awsssomanager.config.config.AWS_DIR", f"{directory}/")
    monkeypatch.setattr(
        "awsssomanager.config.config.SSO_MANAGER_CONFIG_FILE",
        str(directory / "aws-sso-manager.yml"),
    )
    monkeypatch.setattr(
        "awsssomanager.cli.cli.SSO_MANAGER_CONFIG_FILE", str(directory / "aws-sso-manager.yml")
    )
    monkeypatch.setattr(
        "awsssomanager.credentials_file.CREDENTIALS_FILE", str(directory / "credentials")
    )
    return directory


@pytest.fixture
def credentials_path(aws_dir: Path) -> Path:
    return aws_dir / "credentials"


@pytest.fixture
def saved_config_path(aws_dir: Path) -> Path:
    aws_dir.mkdir(parents=True, exist_ok=True)
    return aws_dir / "aws-sso-manager.yml"
