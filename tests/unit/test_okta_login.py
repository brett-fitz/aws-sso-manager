"""Okta login orchestration: sign-in -> select -> assume -> write."""

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
from awsssomanager.okta.login import login
from tests.unit.factories import (
    AWS_SAML_URL,
    FORENSICS,
    SECOPS,
    make_creds,
    make_saml_response,
    role_arn,
)


ROLE_ARNS = [
    role_arn(SECOPS, "Okta-ReadOnly-secops"),
    role_arn(SECOPS, "Okta-TIAgentDeveloper-secops"),
    role_arn(SECOPS, "Okta-BreakGlass-secops"),
    role_arn(FORENSICS, "Okta-SecretsValueEditor-forensics"),
]
ALIASES_HTML = (
    f'<div class="saml-account-name">Account: secops ({SECOPS})</div>'
    f'<div class="saml-account-name">Account: forensics ({FORENSICS})</div>'
)


def okta_config(**profiles: Any) -> AWSSSOManagerConfig:
    config = AWSSSOManagerConfig(
        {
            "provider": "okta",
            "okta": {"appUrl": "https://example.okta.com/home/amazon_aws/0oa1/272"},
            "profiles": profiles or None,
        }
    )
    config.validate()
    return config


@pytest.fixture
def signed_in(mocker: MockerFixture) -> Any:
    mocker.patch(
        "awsssomanager.okta.login.capture_saml_response",
        return_value=make_saml_response(ROLE_ARNS),
    )
    with respx.mock:
        respx.post(AWS_SAML_URL).mock(return_value=httpx.Response(200, text=ALIASES_HTML))
        yield


@pytest.fixture
def assume(mocker: MockerFixture) -> Any:
    def fake(assertion: Any, roles: list[Role], **_: Any) -> dict:
        return {role: make_creds(str(i + 1)) for i, role in enumerate(roles)}

    return mocker.patch("awsssomanager.okta.login.assume_roles", side_effect=fake)


@pytest.mark.usefixtures("signed_in")
def test_assumes_only_selected_roles(credentials_path: Path, assume: Any) -> None:
    config = okta_config(
        easyProfiles=False,
        include=[
            {"role": "Okta-ReadOnly-secops", "name": "secops"},
            {"role": "Okta-TIAgentDeveloper-secops", "name": "tiagent"},
            {"account": "forensics", "name": "forensics"},
        ],
        exclude=[{"role": "*BreakGlass*"}],
    )

    assert login(config) == {}

    assumed = [role.role_name for role in assume.call_args.args[1]]
    assert assumed == [
        "Okta-ReadOnly-secops",
        "Okta-TIAgentDeveloper-secops",
        "Okta-SecretsValueEditor-forensics",
    ]
    credentials = load_credentials(credentials_path)
    assert sorted(credentials.sections()) == ["forensics", "secops", "tiagent"]
    assert credentials["forensics"]["x_account_name"] == "forensics"
    assert credentials["secops"]["x_source"] == "okta:example.okta.com"


@pytest.mark.usefixtures("signed_in")
def test_session_duration_from_config(assume: Any) -> None:
    config = okta_config(include=[{"role": "Okta-ReadOnly-secops"}])
    config.config["okta"]["sessionDuration"] = 7200
    login(config)
    assert assume.call_args.kwargs["duration"] == 7200
    assert assume.call_args.kwargs["region"] == "us-east-1"


@pytest.mark.usefixtures("signed_in")
def test_failure_keeps_previous_profiles(
    credentials_path: Path, assume: Any, mocker: MockerFixture
) -> None:
    config = okta_config(
        easyProfiles=False,
        include=[
            {"role": "Okta-ReadOnly-secops", "name": "secops"},
            {"role": "Okta-TIAgentDeveloper-secops", "name": "tiagent"},
        ],
    )
    login(config)

    denied = ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "AssumeRoleWithSAML")

    def partial_failure(assertion: Any, roles: list[Role], **_: Any) -> dict:
        return {roles[0]: make_creds("9"), roles[1]: denied}

    assume.side_effect = partial_failure
    failures = login(config)

    assert [role.role_name for role in failures] == ["Okta-TIAgentDeveloper-secops"]
    credentials = load_credentials(credentials_path)
    assert sorted(credentials.sections()) == ["secops", "tiagent"]
    assert credentials["secops"]["aws_secret_access_key"] == "secret-9"


@pytest.mark.usefixtures("signed_in")
def test_nothing_selected_writes_nothing(credentials_path: Path, assume: Any) -> None:
    assert login(okta_config(include=[])) == {}
    assume.assert_not_called()
    assert not credentials_path.exists()
