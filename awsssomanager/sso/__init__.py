"""AWS IAM Identity Center (SSO) device authorization and role credentials."""

from awsssomanager.sso.credentials import (
    get_accounts_info,
    get_credentials,
    load_credentials,
    save_credentials,
    update_credentials_for_role,
)
from awsssomanager.sso.device import (
    authorize_device,
    register_new_device,
    start_device_authorization,
)
from awsssomanager.sso.roles import compare_roles, get_role_credentials, get_roles_for_accounts
from awsssomanager.sso.token import create_token, test_create_token


__all__ = [
    "authorize_device",
    "compare_roles",
    "create_token",
    "get_accounts_info",
    "get_credentials",
    "get_role_credentials",
    "get_roles_for_accounts",
    "load_credentials",
    "register_new_device",
    "save_credentials",
    "start_device_authorization",
    "test_create_token",
    "update_credentials_for_role",
]
