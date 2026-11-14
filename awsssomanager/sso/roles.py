"""IAM Identity Center role discovery and per-role credentials."""

from collections.abc import Iterable
from datetime import UTC, datetime
import logging
from typing import Any

import boto3

from awsssomanager.config.config import AWSSSOManagerConfig
from awsssomanager.models import Role, RoleCredentials


__all__ = ["get_role_credentials", "get_roles_for_accounts"]

logger = logging.getLogger(__name__)

_MS_PER_SECOND = 1000


def get_roles_for_accounts(accounts: Iterable[dict], config: AWSSSOManagerConfig) -> list[dict]:
    """Retrieve roles for a list of accounts.

    Args:
        accounts (List[Dict]): List of accounts.
        config (AWSSSOManagerConfig): AWSSSOManagerConfig.

    Returns:
        List[Dict]: List of roles.
    """
    sso_client = boto3.client("sso", region_name=config.region)
    roles = []
    list_roles_paginator = sso_client.get_paginator("list_account_roles")

    for account in accounts:
        page = list_roles_paginator.paginate(
            accessToken=config.access_token, accountId=account["accountId"]
        ).build_full_result()
        roles.extend(page["roleList"])

    return roles


def get_role_credentials(
    config: AWSSSOManagerConfig, role: Role, *, client: Any | None = None
) -> RoleCredentials:
    """Retrieve credentials for one Identity Center role.

    Args:
        config: Config holding a valid access token.
        role: The role to fetch credentials for.
        client: Shared ``sso`` client. Pass one when calling from threads: creating clients
            concurrently from boto3's default session is not thread-safe.

    Returns:
        The role's temporary credentials.
    """
    sso_client = client or boto3.client("sso", region_name=config.region)
    role_credentials = sso_client.get_role_credentials(
        accessToken=config.access_token, accountId=role.account_id, roleName=role.role_name
    )["roleCredentials"]

    return RoleCredentials(
        access_key_id=role_credentials["accessKeyId"],
        secret_access_key=role_credentials["secretAccessKey"],
        session_token=role_credentials["sessionToken"],
        expiration=datetime.fromtimestamp(role_credentials["expiration"] / _MS_PER_SECOND, UTC),
    )
