"""CLI commands."""

from pathlib import Path
import shutil
import sys

from botocore.exceptions import ClientError
from click.testing import CliRunner
import pytest
from pytest_mock import MockerFixture

import awsssomanager
from awsssomanager.cli.cli import cli
from tests.unit.factories import FORENSICS, SECOPS, okta_role


DATA = Path(__file__).parent / "data"
READONLY = okta_role(SECOPS, "Okta-ReadOnly-secops", "secops")
BREAKGLASS = okta_role(SECOPS, "Okta-BreakGlass-secops", "secops")
EDITOR = okta_role(FORENSICS, "Okta-SecretsValueEditor-forensics", "forensics")


@pytest.fixture
def okta_saved(saved_config_path: Path) -> Path:
    shutil.copy(DATA / "okta.yml", saved_config_path)
    return saved_config_path


@pytest.mark.usefixtures("okta_saved")
def test_roles_lists_selection_and_profile_names(mocker: MockerFixture) -> None:
    mocker.patch(
        "awsssomanager.okta.discover_roles",
        return_value=(object(), [READONLY, BREAKGLASS, EDITOR]),
    )

    result = CliRunner().invoke(cli, ["roles"])

    assert result.exit_code == 0, result.output
    table = result.stdout.splitlines()
    assert table[0].split()[0] == "SELECTED"
    lines = {line.split()[3]: line.split() for line in table[1:4]}
    assert lines["Okta-ReadOnly-secops"][0] == "yes"
    assert "default," in lines["Okta-ReadOnly-secops"]  # loginAccount: secops
    assert lines["Okta-BreakGlass-secops"][0] == "no"
    assert lines["Okta-SecretsValueEditor-forensics"][-1] == "forensics"
    assert "2 of 3 role(s) selected" in result.output


@pytest.mark.usefixtures("okta_saved")
def test_login_exits_non_zero_when_roles_fail(mocker: MockerFixture) -> None:
    denied = ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "AssumeRoleWithSAML")
    mocker.patch("awsssomanager.okta.login", return_value={READONLY: denied})

    result = CliRunner().invoke(cli, ["login"])

    assert result.exit_code == 1
    assert "1 role(s) could not be assumed" in result.output


@pytest.mark.usefixtures("aws_dir")
def test_login_without_config_explains() -> None:
    result = CliRunner().invoke(cli, ["login"])
    assert result.exit_code == 1
    assert "aws-sso-manager configure" in result.output


def test_configure_reports_config_errors_without_traceback(tmp_path: Path, aws_dir: Path) -> None:
    bad = tmp_path / "bad.yml"
    bad.write_text("provider: okta\n")
    result = CliRunner().invoke(cli, ["configure", str(bad)])
    assert result.exit_code == 1
    assert "okta.appUrl" in result.output
    assert "Traceback" not in result.output


def test_configure_okta_saves_config_then_logs_in(
    saved_config_path: Path, mocker: MockerFixture
) -> None:
    login = mocker.patch("awsssomanager.okta.login", return_value={})
    result = CliRunner().invoke(cli, ["configure", str(DATA / "okta.yml")])
    assert result.exit_code == 0, result.output
    assert saved_config_path.exists()
    login.assert_called_once()


@pytest.mark.usefixtures("okta_saved")
def test_missing_okta_extra_is_explained(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(awsssomanager, "okta", raising=False)
    monkeypatch.setitem(sys.modules, "awsssomanager.okta", None)

    result = CliRunner().invoke(cli, ["login"])

    assert result.exit_code == 1
    assert "awsssomanager[okta]" in result.output
