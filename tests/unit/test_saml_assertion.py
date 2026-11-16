"""SAMLResponse parsing."""

import base64
import logging
import textwrap

import pytest

from awsssomanager.saml.assertion import SamlError, parse_saml_response
from tests.unit.factories import (
    DEV,
    PROD,
    make_saml_response,
    provider_arn,
    role_arn,
    saml_role,
)


READONLY_ARN = role_arn(DEV, "Okta-ReadOnly-dev")
EDITOR_ARN = role_arn(PROD, "Okta-SecretsEditor-prod")


@pytest.mark.parametrize("role_first", [False, True])
def test_parses_roles_in_either_pair_order(role_first: bool) -> None:
    assertion = parse_saml_response(
        make_saml_response([READONLY_ARN, EDITOR_ARN], role_first=role_first)
    )
    assert assertion.roles == (
        saml_role(DEV, "Okta-ReadOnly-dev"),
        saml_role(PROD, "Okta-SecretsEditor-prod"),
    )
    assert assertion.roles[0].principal_arn == provider_arn(DEV)


def test_role_name_drops_iam_path() -> None:
    arn = f"arn:aws:iam::{DEV}:role/teams/dev/Okta-Analyst"
    (role,) = parse_saml_response(make_saml_response([arn])).roles
    assert role.role_name == "Okta-Analyst"
    assert role.role_arn == arn


def test_reads_session_duration_and_destination() -> None:
    destination = "https://us-east-1.signin.aws.amazon.com/saml"
    assertion = parse_saml_response(
        make_saml_response([READONLY_ARN], session_duration=43200, destination=destination)
    )
    assert assertion.session_duration == 43200
    assert assertion.destination == destination


def test_keeps_raw_value_for_sts_and_hides_it_from_repr() -> None:
    raw = make_saml_response([READONLY_ARN])
    assertion = parse_saml_response(raw)
    assert assertion.raw == raw
    assert raw not in repr(assertion)


def test_accepts_line_wrapped_base64() -> None:
    wrapped = "\n".join(textwrap.wrap(make_saml_response([READONLY_ARN]), 76))
    assert len(parse_saml_response(wrapped).roles) == 1


def test_deduplicates_roles() -> None:
    assertion = parse_saml_response(make_saml_response([READONLY_ARN, READONLY_ARN]))
    assert len(assertion.roles) == 1


def test_ignores_malformed_values(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        assertion = parse_saml_response(
            make_saml_response([READONLY_ARN], extra_values=("not-an-arn-pair",))
        )
    assert len(assertion.roles) == 1
    assert "malformed" in caplog.text


def test_no_roles_is_an_error() -> None:
    with pytest.raises(SamlError, match="grants no AWS roles"):
        parse_saml_response(make_saml_response([]))


def test_not_base64_is_an_error() -> None:
    with pytest.raises(SamlError, match="could not decode"):
        parse_saml_response("%%% not base64 %%%")


def test_encrypted_assertion_is_an_error() -> None:
    xml = (
        '<saml2p:Response xmlns:saml2p="urn:oasis:names:tc:SAML:2.0:protocol">'
        '<saml2:EncryptedAssertion xmlns:saml2="urn:oasis:names:tc:SAML:2.0:assertion"/>'
        "</saml2p:Response>"
    )
    with pytest.raises(SamlError, match="encrypted"):
        parse_saml_response(base64.b64encode(xml.encode()).decode())


def test_rejects_entity_expansion() -> None:
    bomb = '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]><r>&b;</r>'
    with pytest.raises(SamlError):
        parse_saml_response(base64.b64encode(bomb.encode()).decode())
