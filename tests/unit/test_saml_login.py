"""SAML login orchestration: sign-in -> select -> assume -> write."""

from pathlib import Path
from typing import Any

from botocore.exceptions import ClientError
import httpx
import pytest
from pytest_mock import MockerFixture
import respx

from awsssomanager.config import AWSSSOManagerConfig
from awsssomanager.credentials_file import load_credentials
from awsssomanager.models import Role
from awsssomanager.saml.login import login
from tests.unit.factories import (
    AWS_SAML_URL,
    DEV,
    PROD,
    make_creds,
    make_saml_response,
    role_arn,
)


ROLE_ARNS = [
    role_arn(DEV, "Okta-ReadOnly-dev"),
    role_arn(DEV, "Okta-Developer-dev"),
    role_arn(DEV, "Okta-BreakGlass-dev"),
    role_arn(PROD, "Okta-SecretsEditor-prod"),
]
ALIASES_HTML = (
    f'<div class="saml-account-name">Account: dev ({DEV})</div>'
    f'<div class="saml-account-name">Account: prod ({PROD})</div>'
)


def saml_config(**profiles: Any) -> AWSSSOManagerConfig:
    config = AWSSSOManagerConfig(
        {
            "provider": "saml",
            "saml": {"appUrl": "https://example.okta.com/home/amazon_aws/0oa1/272"},
            "profiles": profiles or None,
        }
    )
    config.validate()
    return config


@pytest.fixture
def signed_in(mocker: MockerFixture) -> Any:
    mocker.patch(
        "awsssomanager.saml.login.capture_saml_response",
        return_value=make_saml_response(ROLE_ARNS),
    )
    with respx.mock:
        respx.post(AWS_SAML_URL).mock(return_value=httpx.Response(200, text=ALIASES_HTML))
        yield


@pytest.fixture
def assume(mocker: MockerFixture) -> Any:
    def fake(assertion: Any, roles: list[Role], **_: Any) -> dict:
        return {role: make_creds(str(i + 1)) for i, role in enumerate(roles)}

    return mocker.patch("awsssomanager.saml.login.assume_roles", side_effect=fake)


@pytest.mark.usefixtures("signed_in")
def test_assumes_only_selected_roles(credentials_path: Path, assume: Any) -> None:
    config = saml_config(
        easyProfiles=False,
        include=[
            {"role": "Okta-ReadOnly-dev", "name": "dev"},
            {"role": "Okta-Developer-dev", "name": "developer"},
            {"account": "prod", "name": "prod"},
        ],
        exclude=[{"role": "*BreakGlass*"}],
    )

    assert login(config) == {}

    assumed = [role.role_name for role in assume.call_args.args[1]]
    assert assumed == [
        "Okta-ReadOnly-dev",
        "Okta-Developer-dev",
        "Okta-SecretsEditor-prod",
    ]
    credentials = load_credentials(credentials_path)
    assert sorted(credentials.sections()) == ["dev", "developer", "prod"]
    assert credentials["prod"]["x_account_name"] == "prod"
    assert credentials["dev"]["x_source"] == "saml:example.okta.com"


@pytest.mark.usefixtures("signed_in")
def test_session_duration_from_config(assume: Any) -> None:
    config = saml_config(include=[{"role": "Okta-ReadOnly-dev"}])
    config.config["saml"]["sessionDuration"] = 7200
    login(config)
    assert assume.call_args.kwargs["duration"] == 7200
    assert assume.call_args.kwargs["region"] == "us-east-1"


@pytest.mark.usefixtures("signed_in")
def test_failure_keeps_previous_profiles(
    credentials_path: Path, assume: Any, mocker: MockerFixture
) -> None:
    config = saml_config(
        easyProfiles=False,
        include=[
            {"role": "Okta-ReadOnly-dev", "name": "dev"},
            {"role": "Okta-Developer-dev", "name": "developer"},
        ],
    )
    login(config)

    denied = ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "AssumeRoleWithSAML")

    def partial_failure(assertion: Any, roles: list[Role], **_: Any) -> dict:
        return {roles[0]: make_creds("9"), roles[1]: denied}

    assume.side_effect = partial_failure
    failures = login(config)

    assert [role.role_name for role in failures] == ["Okta-Developer-dev"]
    credentials = load_credentials(credentials_path)
    assert sorted(credentials.sections()) == ["dev", "developer"]
    assert credentials["dev"]["aws_secret_access_key"] == "secret-9"


@pytest.mark.usefixtures("signed_in")
def test_nothing_selected_writes_nothing(credentials_path: Path, assume: Any) -> None:
    assert login(saml_config(include=[])) == {}
    assume.assert_not_called()
    assert not credentials_path.exists()
