"""Provider-neutral role and credential types.

Both credential providers (IAM Identity Center and SAML federation) reduce what they
discover to :class:`Role` and what they fetch to :class:`RoleCredentials`, so profile selection,
naming, and the credentials-file writer never need to know which provider ran.
"""

from dataclasses import dataclass, field
from datetime import datetime


__all__ = ["Role", "RoleCredentials"]


@dataclass(frozen=True)
class Role:
    """A role the signed-in user can obtain credentials for.

    Attributes:
        account_id: 12-digit AWS account id.
        role_name: Role name (the permission set name for IAM Identity Center).
        account_name: Account name or alias, when the provider can supply one.
        role_arn: Full IAM role ARN. Only known for SAML federation.
        principal_arn: SAML identity provider ARN paired with ``role_arn``. Only set for SAML
            federation, where ``AssumeRoleWithSAML`` needs it.
    """

    account_id: str
    role_name: str
    account_name: str | None = None
    role_arn: str | None = None
    principal_arn: str | None = None


@dataclass(frozen=True)
class RoleCredentials:
    """Temporary credentials for one role.

    Secrets are excluded from ``repr`` so an accidental log line never leaks them.

    Attributes:
        access_key_id: ``aws_access_key_id``.
        secret_access_key: ``aws_secret_access_key``.
        session_token: ``aws_session_token``.
        expiration: When the credentials stop working (timezone-aware).
        principal_arn: The assumed-role ARN, when the provider returns one.
    """

    access_key_id: str
    secret_access_key: str = field(repr=False)
    session_token: str = field(repr=False)
    expiration: datetime
    principal_arn: str | None = None
