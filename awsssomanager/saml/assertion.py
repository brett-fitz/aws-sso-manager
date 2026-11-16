"""Parse the AWS roles out of a SAMLResponse.

An identity provider's AWS app (Okta's AWS Account Federation, Entra ID, Google Workspace, ...)
puts every role the user may assume into one assertion, as
``https://aws.amazon.com/SAML/Attributes/Role`` values of the form
``<saml-provider ARN>,<role ARN>`` (in either order). That single assertion can be exchanged
with ``sts:AssumeRoleWithSAML`` once per role while it is valid, which is what lets one browser
sign-in authorize every selected role.
"""

import base64
import binascii
from dataclasses import dataclass, field
import logging
import re
from xml.etree.ElementTree import ParseError

from defusedxml import DefusedXmlException
from defusedxml.ElementTree import fromstring

from awsssomanager.errors import AWSSSOManagerError
from awsssomanager.models import Role


__all__ = [
    "AWS_SAML_ENDPOINT",
    "AWS_SAML_ENDPOINT_RE",
    "SamlAssertion",
    "SamlError",
    "parse_saml_response",
]

logger = logging.getLogger(__name__)

#: Global AWS sign-in SAML endpoint (the ACS URL that every IdP's AWS app posts to).
AWS_SAML_ENDPOINT = "https://signin.aws.amazon.com/saml"

#: Matches the global endpoint and the regional ones (``https://<region>.signin.aws...``).
AWS_SAML_ENDPOINT_RE = re.compile(
    r"^https://(?:[a-z0-9-]+\.)?signin\.aws\.amazon\.com/saml(?:[/?#].*)?$"
)

_ROLE_ATTRIBUTE = "https://aws.amazon.com/SAML/Attributes/Role"
_SESSION_DURATION_ATTRIBUTE = "https://aws.amazon.com/SAML/Attributes/SessionDuration"
_ASSERTION_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
_ATTRIBUTE_TAG = f"{{{_ASSERTION_NS}}}Attribute"
_ATTRIBUTE_VALUE_TAG = f"{{{_ASSERTION_NS}}}AttributeValue"
_ENCRYPTED_ASSERTION_TAG = f"{{{_ASSERTION_NS}}}EncryptedAssertion"
_ARN_ACCOUNT_FIELD = 4


class SamlError(AWSSSOManagerError, ValueError):
    """The SAMLResponse could not be decoded, or carries no AWS roles."""


@dataclass(frozen=True)
class SamlAssertion:
    """What aws-sso-manager needs from one SAMLResponse.

    Attributes:
        raw: The base64 SAMLResponse exactly as the IdP posted it (passed to STS unchanged).
        roles: Every role the assertion grants, in assertion order, de-duplicated.
        session_duration: The ``SessionDuration`` attribute, if the IdP sends one.
        destination: The ``Destination`` the response was addressed to, if present.
    """

    raw: str = field(repr=False)
    roles: tuple[Role, ...]
    session_duration: int | None = None
    destination: str | None = None


def _role_from_pair(value: str) -> Role | None:
    parts = [part.strip() for part in value.split(",")]
    role_arn = next((part for part in parts if ":role/" in part), None)
    principal_arn = next((part for part in parts if ":saml-provider/" in part), None)
    if role_arn is None or principal_arn is None:
        logger.warning(f"ignoring malformed SAML role attribute value: {value!r}")
        return None
    return Role(
        account_id=role_arn.split(":")[_ARN_ACCOUNT_FIELD],
        role_name=role_arn.rsplit("/", 1)[-1],
        role_arn=role_arn,
        principal_arn=principal_arn,
    )


def parse_saml_response(saml_response: str) -> SamlAssertion:
    """Decode a base64 SAMLResponse and extract its AWS roles.

    Args:
        saml_response: The ``SAMLResponse`` form value.

    Returns:
        The parsed assertion.

    Raises:
        SamlError: If the value is not base64 XML, the assertion is encrypted, or it grants no
            AWS roles.
    """
    try:
        # Tolerate line-wrapped base64; STS still receives the original value.
        document = base64.b64decode("".join(saml_response.split()), validate=True)
        root = fromstring(document)
    except (binascii.Error, ValueError, ParseError, DefusedXmlException) as error:
        raise SamlError(f"could not decode SAMLResponse: {error}") from error

    if root.find(f".//{_ENCRYPTED_ASSERTION_TAG}") is not None:
        raise SamlError(
            "the SAML assertion is encrypted; aws-sso-manager can only read unencrypted assertions"
        )

    roles: list[Role] = []
    session_duration: int | None = None
    for attribute in root.iter(_ATTRIBUTE_TAG):
        values = [
            (value.text or "").strip()
            for value in attribute.iter(_ATTRIBUTE_VALUE_TAG)
            if (value.text or "").strip()
        ]
        name = attribute.get("Name")
        if name == _ROLE_ATTRIBUTE:
            roles.extend(role for role in map(_role_from_pair, values) if role is not None)
        elif name == _SESSION_DURATION_ATTRIBUTE and values:
            try:
                session_duration = int(values[0])
            except ValueError:
                logger.warning(f"ignoring non-integer SessionDuration: {values[0]!r}")

    if not roles:
        raise SamlError(
            "the SAML assertion grants no AWS roles; check that saml.appUrl points at your "
            "identity provider's AWS app and that you are assigned roles in it"
        )

    return SamlAssertion(
        raw=saml_response,
        roles=tuple(dict.fromkeys(roles)),
        session_duration=session_duration,
        destination=root.get("Destination"),
    )
