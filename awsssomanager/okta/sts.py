"""Exchange one SAML assertion for credentials on many roles.

The assertion is short-lived (Okta typically allows about five minutes), so every selected role
is assumed in parallel straight after sign-in.
"""

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import Any

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from awsssomanager.models import Role, RoleCredentials
from awsssomanager.okta.saml import SamlAssertion


__all__ = ["DEFAULT_SESSION_DURATION", "assume_roles", "resolve_session_duration"]

logger = logging.getLogger(__name__)

#: STS's own default, and the fallback when a role rejects a longer duration.
DEFAULT_SESSION_DURATION = 3600
_MAX_WORKERS = 10


def resolve_session_duration(configured: int | None, assertion: SamlAssertion) -> int:
    """Pick the requested credential lifetime.

    Precedence: ``okta.sessionDuration`` in the config, then the assertion's ``SessionDuration``
    attribute, then one hour.

    Args:
        configured: ``okta.sessionDuration`` from the config, if set.
        assertion: The parsed SAMLResponse.

    Returns:
        Duration in seconds.
    """
    return configured or assertion.session_duration or DEFAULT_SESSION_DURATION


def _sts_client(region: str) -> Any:
    # AssumeRoleWithSAML is unauthenticated; UNSIGNED keeps boto3 from hunting for ambient
    # credentials (which may be the expired ones this run is replacing).
    return boto3.client("sts", region_name=region, config=Config(signature_version=UNSIGNED))


def _is_duration_rejection(error: ClientError) -> bool:
    details = error.response.get("Error", {})
    return details.get("Code") == "ValidationError" and "DurationSeconds" in details.get(
        "Message", ""
    )


def _assume(client: Any, assertion: SamlAssertion, role: Role, duration: int) -> RoleCredentials:
    request = {
        "RoleArn": role.role_arn,
        "PrincipalArn": role.principal_arn,
        "SAMLAssertion": assertion.raw,
    }
    try:
        response = client.assume_role_with_saml(**request, DurationSeconds=duration)
    except ClientError as error:
        if duration <= DEFAULT_SESSION_DURATION or not _is_duration_rejection(error):
            raise
        logger.warning(
            f"{role.role_arn} does not allow {duration}s sessions; "
            f"retrying with {DEFAULT_SESSION_DURATION}s"
        )
        response = client.assume_role_with_saml(**request, DurationSeconds=DEFAULT_SESSION_DURATION)

    creds = response["Credentials"]
    return RoleCredentials(
        access_key_id=creds["AccessKeyId"],
        secret_access_key=creds["SecretAccessKey"],
        session_token=creds["SessionToken"],
        expiration=creds["Expiration"],
        principal_arn=response.get("AssumedRoleUser", {}).get("Arn"),
    )


def assume_roles(
    assertion: SamlAssertion,
    roles: Sequence[Role],
    *,
    region: str,
    duration: int,
    client: Any | None = None,
    max_workers: int = _MAX_WORKERS,
) -> dict[Role, RoleCredentials | Exception]:
    """Assume every role with the same assertion.

    One role failing (for example, a role whose trust policy changed) does not stop the others.

    Args:
        assertion: The parsed SAMLResponse.
        roles: Roles to assume; each needs ``role_arn`` and ``principal_arn``.
        region: STS region.
        duration: Requested ``DurationSeconds``.
        client: Optional STS client (tests inject a stubbed one).
        max_workers: Parallel STS calls.

    Returns:
        Credentials, or the exception raised, per role.
    """
    sts = client or _sts_client(region)

    def attempt(role: Role) -> RoleCredentials | Exception:
        try:
            return _assume(sts, assertion, role, duration)
        except (ClientError, BotoCoreError) as error:
            return error

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return dict(zip(roles, pool.map(attempt, roles), strict=True))
