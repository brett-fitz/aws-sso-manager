"""IAM Identity Center login: token, role discovery, selection, and credentials file."""

from concurrent.futures import ThreadPoolExecutor
from functools import partial
import logging
import sys
import time

import boto3

from awsssomanager.config import AWSSSOManagerConfig
from awsssomanager.credentials_file import write_profiles
from awsssomanager.models import Role
from awsssomanager.profiles import build_profiles, plan_profiles, select_roles
from awsssomanager.sso.device import start_device_authorization
from awsssomanager.sso.roles import get_role_credentials, get_roles_for_accounts
from awsssomanager.sso.token import create_token


__all__ = [
    "discover_roles",
    "ensure_access_token",
    "get_accounts_info",
    "get_credentials",
]

logger = logging.getLogger(__name__)

_MAX_WORKERS = 10
_UNAUTHORIZED_RETRY_SECONDS = 30


def get_accounts_info(config: AWSSSOManagerConfig) -> dict:
    """Retrieve account information for all accounts that a user
    has access to.

    Args:
        config (AWSSSOManagerConfig): AWSSSOManagerConfig.

    Returns:
        Dict: A dictionary containing account information.
    """
    sso_client = boto3.client("sso", region_name=config.region)
    accounts_info = {}
    list_accounts_paginator = sso_client.get_paginator("list_accounts")

    def process_page(page):
        for account in page["accountList"]:
            logger.info(f"found account: {account['accountId']}")
            accounts_info[account["accountId"]] = {
                "accountId": account["accountId"],
                "accountName": account["accountName"],
                "emailAddress": account["emailAddress"],
            }

    for page in list_accounts_paginator.paginate(accessToken=config.access_token):
        process_page(page)

    return accounts_info


def ensure_access_token(config: AWSSSOManagerConfig) -> AWSSSOManagerConfig:
    """Create a new access token when the current one has expired.

    Args:
        config: Config with a registered device.

    Returns:
        The config, holding a current access token.
    """
    if time.time() <= config.access_token_expires_at:
        return config
    sso_oidc = boto3.client("sso-oidc", region_name=config.region)
    try:
        return create_token(config)
    except sso_oidc.exceptions.InvalidGrantException:
        # invalid grant, reauthorize device
        logger.warning("Unable to create token, reauthorizing...")
        return start_device_authorization(config)
    except Exception as error:  # preserve the historical hard exit on unknown failures
        logger.error(f"Unable to create token, unknown exception: {error}")
        sys.exit(1)


def discover_roles(config: AWSSSOManagerConfig) -> list[Role]:
    """List every account and role the access token can reach.

    Args:
        config: Config holding a current access token.

    Returns:
        Roles in account order.
    """
    accounts = get_accounts_info(config=config)
    return [
        Role(
            account_id=role["accountId"],
            role_name=role["roleName"],
            account_name=accounts[role["accountId"]]["accountName"],
        )
        for role in get_roles_for_accounts(accounts.values(), config)
    ]


def get_credentials(config: AWSSSOManagerConfig) -> None:
    """Fetch credentials for the selected roles and write their profiles.

    Only roles that pass the ``profiles`` include/exclude rules are fetched.

    Args:
        config: Config with a registered device.
    """
    sso_oidc = boto3.client("sso-oidc", region_name=config.region)
    selection = config.profile_selection

    logger.info("Retrieving credentials")
    while True:
        try:
            config = ensure_access_token(config)
            roles = discover_roles(config)
            selected = select_roles(roles, selection)
            logger.info(f"selected {len(selected)} of {len(roles)} role(s)")

            wanted = [item.role for item in selected]
            sso = boto3.client("sso", region_name=config.region)  # one client, shared by threads
            with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
                fetched = list(pool.map(partial(get_role_credentials, config, client=sso), wanted))

            plan = plan_profiles(
                selected,
                role_priority=config.role_priority,
                easy_profiles=selection.easy_profiles,
                login_account=config.login_account,
            )
            profiles = build_profiles(
                plan, dict(zip(wanted, fetched, strict=True)), source=config.credential_source
            )
            write_profiles(profiles, source=config.credential_source, adopt_legacy_sso=True)
            logger.info("Credentials successfully retrieved")
            break  # exit out of cred loop

        except sso_oidc.exceptions.UnauthorizedClientException:
            logger.info("Access token unauthorized, sleeping and refetching credentials...")
            time.sleep(_UNAUTHORIZED_RETRY_SECONDS)
