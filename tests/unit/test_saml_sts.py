"""AssumeRoleWithSAML for many roles from one assertion."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError
from botocore.stub import Stubber
import pytest

from awsssomanager.models import RoleCredentials
from awsssomanager.saml.assertion import SamlAssertion, parse_saml_response
from awsssomanager.saml.sts import DEFAULT_SESSION_DURATION, assume_roles, resolve_session_duration
from tests.unit.factories import DEV, PROD, make_saml_response, role_arn


READONLY_ARN = role_arn(DEV, "Okta-ReadOnly-dev")
EDITOR_ARN = role_arn(PROD, "Okta-SecretsEditor-prod")
EXPIRATION = datetime(2026, 11, 14, 19, 0, tzinfo=UTC)


@pytest.fixture
def assertion() -> SamlAssertion:
    return parse_saml_response(make_saml_response([READONLY_ARN, EDITOR_ARN]))


@pytest.fixture
def sts() -> Iterator[tuple[Any, Stubber]]:
    client = boto3.client("sts", region_name="us-east-1", config=Config(signature_version=UNSIGNED))
    with Stubber(client) as stubber:
        yield client, stubber
        stubber.assert_no_pending_responses()


def sts_response(role_name: str, key: str = "ASIAEXAMPLE00000001") -> dict:
    return {
        "Credentials": {
            "AccessKeyId": key,
            "SecretAccessKey": "secret",
            "SessionToken": "token",
            "Expiration": EXPIRATION,
        },
        "AssumedRoleUser": {
            "AssumedRoleId": "AROAEXAMPLE:user@example.com",
            "Arn": f"arn:aws:sts::{DEV}:assumed-role/{role_name}/user@example.com",
        },
    }


def expected(assertion: SamlAssertion, index: int, duration: int) -> dict:
    role = assertion.roles[index]
    return {
        "RoleArn": role.role_arn,
        "PrincipalArn": role.principal_arn,
        "SAMLAssertion": assertion.raw,
        "DurationSeconds": duration,
    }


def test_assumes_every_role(assertion: SamlAssertion, sts: tuple[Any, Stubber]) -> None:
    client, stubber = sts
    stubber.add_response(
        "assume_role_with_saml", sts_response("Okta-ReadOnly-dev"), expected(assertion, 0, 3600)
    )
    stubber.add_response(
        "assume_role_with_saml",
        sts_response("Okta-SecretsEditor-prod", "ASIAEXAMPLE00000002"),
        expected(assertion, 1, 3600),
    )

    results = assume_roles(
        assertion, assertion.roles, region="us-east-1", duration=3600, client=client, max_workers=1
    )

    first = results[assertion.roles[0]]
    assert isinstance(first, RoleCredentials)
    assert first.expiration == EXPIRATION
    assert first.principal_arn and first.principal_arn.endswith(
        "assumed-role/Okta-ReadOnly-dev/user@example.com"
    )
    second = results[assertion.roles[1]]
    assert isinstance(second, RoleCredentials)
    assert second.access_key_id == "ASIAEXAMPLE00000002"


def test_retries_rejected_duration_at_default(
    assertion: SamlAssertion, sts: tuple[Any, Stubber]
) -> None:
    client, stubber = sts
    stubber.add_client_error(
        "assume_role_with_saml",
        service_error_code="ValidationError",
        service_message=(
            "The requested DurationSeconds exceeds the MaxSessionDuration set for this role."
        ),
        expected_params=expected(assertion, 0, 43200),
    )
    stubber.add_response(
        "assume_role_with_saml",
        sts_response("Okta-ReadOnly-dev"),
        expected(assertion, 0, DEFAULT_SESSION_DURATION),
    )

    results = assume_roles(
        assertion, assertion.roles[:1], region="us-east-1", duration=43200, client=client
    )
    assert isinstance(results[assertion.roles[0]], RoleCredentials)


def test_one_failure_does_not_stop_the_rest(
    assertion: SamlAssertion, sts: tuple[Any, Stubber]
) -> None:
    client, stubber = sts
    stubber.add_client_error(
        "assume_role_with_saml",
        service_error_code="AccessDenied",
        service_message="Not authorized to perform sts:AssumeRoleWithSAML",
    )
    stubber.add_response("assume_role_with_saml", sts_response("Okta-SecretsEditor-prod"))

    results = assume_roles(
        assertion, assertion.roles, region="us-east-1", duration=3600, client=client, max_workers=1
    )

    assert isinstance(results[assertion.roles[0]], ClientError)
    assert isinstance(results[assertion.roles[1]], RoleCredentials)


def test_non_duration_validation_error_is_not_retried(
    assertion: SamlAssertion, sts: tuple[Any, Stubber]
) -> None:
    client, stubber = sts
    stubber.add_client_error(
        "assume_role_with_saml", service_error_code="ValidationError", service_message="bad ARN"
    )
    results = assume_roles(
        assertion, assertion.roles[:1], region="us-east-1", duration=43200, client=client
    )
    assert isinstance(results[assertion.roles[0]], ClientError)


def test_session_duration_precedence() -> None:
    with_attr = parse_saml_response(make_saml_response([READONLY_ARN], session_duration=7200))
    without = parse_saml_response(make_saml_response([READONLY_ARN]))
    assert resolve_session_duration(1800, with_attr) == 1800
    assert resolve_session_duration(None, with_attr) == 7200
    assert resolve_session_duration(None, without) == DEFAULT_SESSION_DURATION
