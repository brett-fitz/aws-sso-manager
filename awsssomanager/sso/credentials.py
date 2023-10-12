"""aws-sso-manager sso module: roles"""
from concurrent.futures import ThreadPoolExecutor
import configparser
import logging
import time
from typing import Dict

import boto3
import botocore

from awsssomanager import CREDENTIALS_FILE
from awsssomanager.config import AWSSSOManagerConfig
from awsssomanager.sso.roles import compare_roles, get_role_credentials, get_roles_for_accounts
from awsssomanager.sso.device import start_device_authorization
from awsssomanager.sso.token import create_token


__all__ = [
    "get_accounts_info",
    "get_credentials",
    "get_roles_for_accounts",
    "get_role_credentials",
    "update_credentials_for_role",
    "load_credentials",
    "save_credentials"
]

logger = logging.getLogger(__name__)


def get_aws_sso_client() -> boto3.client:
    """Get an AWS SSO client.

    Returns:
        boto3.client
    """
    return boto3.client("sso", region_name="us-east-1")


def get_accounts_info(access_token: str) -> Dict:
    """Retrieve account information for all accounts that a user
    has access to.

    Args:
        access_token (str): The access token for authentication.

    Returns:
        Dict: A dictionary containing account information.
    """
    sso_client = get_aws_sso_client()
    accounts_info = {}
    list_accounts_paginator = sso_client.get_paginator("list_accounts")

    def process_page(page):
        for account in page["accountList"]:
            logger.info(f'found account: {account["accountId"]}')
            accounts_info[account["accountId"]] = {
                "accountId": account["accountId"],
                "accountName": account["accountName"],
                "emailAddress": account["emailAddress"],
            }

    for page in list_accounts_paginator.paginate(accessToken=access_token):
        process_page(page)

    return accounts_info


def get_credentials(config: AWSSSOManagerConfig) -> None:
    """Retrieve fresh AWS credentials in a loop.

    Args:
        config (AWSSSOManagerConfig): AWSSSOManagerConfig.

    Returns:
        None
    """
    credentials = load_credentials()
    sso_client = boto3.client("sso-oidc", region_name="us-east-1")
    token_expires_at = float(config.config["default"].get("accessTokenExpiresAt", "0"))
    access_token = config.config["default"].get("accessToken", "")

    logger.info('Retrieving credentials')
    while True:
        try:
            if time.time() > token_expires_at:
                # token expired, create a new one
                try:
                    config = create_token(config)
                except sso_client.exceptions.InvalidGrantException:
                    # invalid grant, reauthorize device
                    logger.warning("Unable to create token, reauthorizing...")
                    config = start_device_authorization(config)
                access_token = config.config["default"]["accessToken"]
                token_expires_at = float(config.config["default"]["accessTokenExpiresAt"])

            # Get list of accounts user has access to
            accounts = get_accounts_info(access_token)
            logger.debug(accounts)

            # Get list of roles (for each account) the user has access to
            roles = get_roles_for_accounts(accounts.values(), access_token)
            logger.debug(roles)

            # Get credentials for all roles
            new_credentials = {}
            with ThreadPoolExecutor(max_workers=10) as pool:
                results = list(pool.map(
                    lambda role: get_role_credentials(
                        role, access_token, accounts
                    ),
                    roles,
                ))

            # Merge the dictionaries returned by the function into new_credentials
            for result in results:
                new_credentials.update(result)

            logger.debug(new_credentials)
            # Iterate over roles for account default permissions
            with ThreadPoolExecutor(max_workers=10) as pool:
                pool.map(
                    lambda role: update_credentials_for_role(
                        config, new_credentials, accounts, role
                    ),
                    roles,
                )

            # get default credentials
            if config.login_account in new_credentials:
                new_credentials["default"] = new_credentials[config.login_account].copy()
            else:
                logger.warning(f'{config.login_account} not found in credentials')

            credentials.update(new_credentials)
            credentials = save_credentials(credentials)
            logger.info("Credentials successfully retrieved")
            break  # exit out of cred loop

        except sso_client.exceptions.UnauthorizedException:
            logger.info("Access token unauthorized, sleeping and refetching credentials...")
            time.sleep(30)


def update_credentials_for_role(
    config: AWSSSOManagerConfig,
    new_credentials: Dict,
    accounts_info: Dict,
    role: Dict
) -> None:
    """Update credentials for a role.

    Args:
        new_credentials (Dict): The new credentials to be updated.
        accounts_info (Dict): Information about accounts.
        role (Dict): The role for which credentials are to be updated.

    Returns:
        None
    """
    account_id = role["accountId"]
    role_name = role["roleName"]
    profile_name = f"{account_id}_{role_name}"
    account_name = accounts_info[account_id]["accountName"]

    # If the account id alias is already in credentials, check to see if we should override for higher priority
    if account_id in new_credentials:
        if compare_roles(config, role_name, new_credentials[account_id]["aws_sso_role_name"]) > 0:
            new_credentials[account_id] = new_credentials[profile_name].copy()
            new_credentials[account_name] = new_credentials[profile_name].copy()
    else:
        try:
            new_credentials[account_id] = new_credentials[profile_name].copy()
            new_credentials[account_name] = new_credentials[profile_name].copy()
        except KeyError:
            logger.error(f'Could not update credentials for profile: {profile_name}')


def load_credentials() -> configparser.ConfigParser:
    """Load AWS credentials from an INI file.

    Returns:
        configparser.ConfigParser: ConfigParser object containing the credentials.
    """
    credentials = configparser.ConfigParser()
    credentials.optionxform = str  # type: ignore
    credentials.read(CREDENTIALS_FILE)
    return credentials


def save_credentials(credentials: configparser.ConfigParser) -> configparser.ConfigParser:
    """Save AWS SSO Helper config to an INI file.

    Args:
        credentials (configparser.ConfigParser): ConfigParser object containing the credentials.

    Returns:
        configparser.ConfigParser: ConfigParser object after saving.
    """
    with open(CREDENTIALS_FILE, "w") as credentialsfile:
        credentials.write(credentialsfile)
    return load_credentials()
