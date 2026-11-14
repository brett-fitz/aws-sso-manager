"""AWS IAM Identity Center (SSO) device authorization and role credentials."""

from awsssomanager.sso.credentials import (
    discover_roles,
    ensure_access_token,
    get_accounts_info,
    get_credentials,
)
from awsssomanager.sso.device import (
    authorize_device,
    register_new_device,
    start_device_authorization,
)
from awsssomanager.sso.roles import get_role_credentials, get_roles_for_accounts
from awsssomanager.sso.token import create_token, test_create_token


__all__ = [
    "authorize_device",
    "create_token",
    "discover_roles",
    "ensure_access_token",
    "get_accounts_info",
    "get_credentials",
    "get_role_credentials",
    "get_roles_for_accounts",
    "register_new_device",
    "start_device_authorization",
    "test_create_token",
]
