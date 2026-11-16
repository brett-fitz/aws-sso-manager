"""Builders for SAML responses, roles and credentials used across the unit tests."""

import base64
from datetime import UTC, datetime, timedelta

from awsssomanager.models import Role, RoleCredentials


AWS_SAML_URL = "https://signin.aws.amazon.com/saml"
SECOPS = "496537994330"
FORENSICS = "381492076076"
SECLOG = "888577029845"


def role_arn(account_id: str, name: str) -> str:
    return f"arn:aws:iam::{account_id}:role/{name}"


def provider_arn(account_id: str) -> str:
    return f"arn:aws:iam::{account_id}:saml-provider/Okta"


def saml_role(account_id: str, name: str, account_name: str | None = None) -> Role:
    return Role(
        account_id=account_id,
        role_name=name,
        account_name=account_name,
        role_arn=role_arn(account_id, name),
        principal_arn=provider_arn(account_id),
    )


def make_saml_response(
    role_arns: list[str],
    *,
    session_duration: int | None = None,
    destination: str | None = AWS_SAML_URL,
    role_first: bool = False,
    extra_values: tuple[str, ...] = (),
) -> str:
    """Base64 SAMLResponse shaped like Okta's AWS Account Federation app output."""
    values = []
    for arn in role_arns:
        account_id = arn.split(":")[4]
        pair = [provider_arn(account_id), arn]
        if role_first:
            pair.reverse()
        values.append(",".join(pair))
    values.extend(extra_values)
    role_values = "".join(f"<saml2:AttributeValue>{v}</saml2:AttributeValue>" for v in values)
    duration = (
        '<saml2:Attribute Name="https://aws.amazon.com/SAML/Attributes/SessionDuration">'
        f"<saml2:AttributeValue>{session_duration}</saml2:AttributeValue></saml2:Attribute>"
        if session_duration is not None
        else ""
    )
    destination_attr = f' Destination="{destination}"' if destination else ""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<saml2p:Response xmlns:saml2p="urn:oasis:names:tc:SAML:2.0:protocol"'
        f'{destination_attr} ID="id1" Version="2.0">'
        '<saml2:Assertion xmlns:saml2="urn:oasis:names:tc:SAML:2.0:assertion"'
        ' ID="id2" Version="2.0">'
        "<saml2:AttributeStatement>"
        '<saml2:Attribute Name="https://aws.amazon.com/SAML/Attributes/RoleSessionName">'
        "<saml2:AttributeValue>user@example.com</saml2:AttributeValue></saml2:Attribute>"
        f'<saml2:Attribute Name="https://aws.amazon.com/SAML/Attributes/Role">{role_values}'
        "</saml2:Attribute>"
        f"{duration}"
        "</saml2:AttributeStatement></saml2:Assertion></saml2p:Response>"
    )
    return base64.b64encode(xml.encode()).decode()


def make_creds(tag: str = "1", *, principal_arn: str | None = None) -> RoleCredentials:
    return RoleCredentials(
        access_key_id=f"ASIAEXAMPLE{tag:0>8}",
        secret_access_key=f"secret-{tag}",
        session_token=f"token-{tag}",
        expiration=datetime(2026, 11, 14, 18, 0, tzinfo=UTC) + timedelta(hours=int(tag)),
        principal_arn=principal_arn,
    )
