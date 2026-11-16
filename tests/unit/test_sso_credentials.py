"""IAM Identity Center flow with profile selection."""

from pathlib import Path
from typing import Any

import boto3
from botocore.stub import Stubber
from pytest_mock import MockerFixture

from awsssomanager.config import AWSSSOManagerConfig
from awsssomanager.credentials_file import load_credentials
from awsssomanager.models import Role
from awsssomanager.sso.credentials import get_credentials
from awsssomanager.sso.roles import get_role_credentials
from tests.unit.factories import make_creds


ACCOUNTS = {
    "111111111111": {"accountId": "111111111111", "accountName": "dev", "emailAddress": "d@x"},
    "222222222222": {"accountId": "222222222222", "accountName": "prod", "emailAddress": "p@x"},
}
ROLE_LIST = [
    {"accountId": "111111111111", "roleName": "ViewOnlyAccess"},
    {"accountId": "111111111111", "roleName": "AdministratorAccess"},
    {"accountId": "222222222222", "roleName": "ViewOnlyAccess"},
    {"accountId": "222222222222", "roleName": "BreakGlassAdmin"},
]


def sso_config(**extra: Any) -> AWSSSOManagerConfig:
    config = AWSSSOManagerConfig(
        {
            "ssoDomain": "corp",
            "region": "us-east-1",
            "default": {"loginAccount": "111111111111"},
            "role_priority": ["ViewOnlyAccess", "AdministratorAccess"],
            **extra,
        }
    )
    config.validate()
    return config


def patch_sso(mocker: MockerFixture) -> Any:
    mocker.patch("awsssomanager.sso.credentials.ensure_access_token", side_effect=lambda c: c)
    mocker.patch("awsssomanager.sso.credentials.get_accounts_info", return_value=ACCOUNTS)
    mocker.patch("awsssomanager.sso.credentials.get_roles_for_accounts", return_value=ROLE_LIST)
    return mocker.patch(
        "awsssomanager.sso.credentials.get_role_credentials",
        side_effect=lambda config, role, **_: make_creds(str(len(role.role_name) % 9)),
    )


def test_fetches_only_selected_roles(credentials_path: Path, mocker: MockerFixture) -> None:
    fetch = patch_sso(mocker)

    get_credentials(sso_config(profiles={"exclude": [{"role": "BreakGlass*"}]}))

    fetched = [call.args[1] for call in fetch.call_args_list]
    assert Role("222222222222", "BreakGlassAdmin", "prod") not in fetched
    assert len(fetched) == 3
    sections = load_credentials(credentials_path).sections()
    assert "222222222222_BreakGlassAdmin" not in sections


def test_easy_profiles_priority_and_default(credentials_path: Path, mocker: MockerFixture) -> None:
    patch_sso(mocker)

    get_credentials(sso_config())

    credentials = load_credentials(credentials_path)
    assert sorted(credentials.sections()) == [
        "111111111111",
        "111111111111_AdministratorAccess",
        "111111111111_ViewOnlyAccess",
        "222222222222",
        "222222222222_BreakGlassAdmin",
        "222222222222_ViewOnlyAccess",
        "default",
        "dev",
        "prod",
    ]
    assert credentials["dev"]["x_role_name"] == "AdministratorAccess"
    assert credentials["default"]["x_role_name"] == "AdministratorAccess"
    assert credentials["prod"]["x_source"] == "identity-center:corp"


def test_prunes_legacy_sections_no_longer_selected(
    credentials_path: Path, mocker: MockerFixture
) -> None:
    credentials_path.parent.mkdir(parents=True)
    credentials_path.write_text(
        "[222222222222_BreakGlassAdmin]\naws_access_key_id = OLD\n"
        "aws_sso_updated_at = Mon Jan  1 00:00:00 2024\n"
        "[mine]\naws_access_key_id = KEEP\n"
    )
    patch_sso(mocker)

    get_credentials(sso_config(profiles={"exclude": [{"role": "BreakGlass*"}]}))

    sections = load_credentials(credentials_path).sections()
    assert "222222222222_BreakGlassAdmin" not in sections
    assert "mine" in sections


def test_get_role_credentials_converts_expiration(mocker: MockerFixture) -> None:
    client = boto3.client("sso", region_name="us-east-1")
    stubber = Stubber(client)
    stubber.add_response(
        "get_role_credentials",
        {
            "roleCredentials": {
                "accessKeyId": "ASIAEXAMPLE00000001",
                "secretAccessKey": "s",
                "sessionToken": "t",
                "expiration": 1_794_700_800_000,
            }
        },
        {"accessToken": "tok", "accountId": "111111111111", "roleName": "ViewOnlyAccess"},
    )
    mocker.patch("awsssomanager.sso.roles.boto3.client", return_value=client)
    config = sso_config(device={"accessToken": "tok"})

    with stubber:
        creds = get_role_credentials(config, Role("111111111111", "ViewOnlyAccess"))

    assert creds.expiration.timestamp() == 1_794_700_800
    assert creds.expiration.tzinfo is not None
