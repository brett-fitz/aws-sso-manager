"""aws-sso-manager sso module: roles"""
import logging
import time
from typing import Dict, List

import boto3

from awsssomanager.config.config import AWSSSOManagerConfig

__all__ = [
    "compare_roles",
    "get_roles_for_accounts",
    "get_role_credentials"
]

logger = logging.getLogger(__name__)


def compare_roles(
    config: AWSSSOManagerConfig,
    left_role_name: str,
    right_role_name: str
) -> int:
    """Compare two roles by name and return
        1 if the first is higher priority,
        -1 if the second is higher,
        or 0 if same.

    Args:
        config: _description_
        left_role_name: _description_
        right_role_name: _description_

    Returns:
        _description_
    """
    left_index = (
        config.role_priority.index(left_role_name)
        if left_role_name in config.role_priority else -1
    )
    right_index = (
        config.role_priority.index(right_role_name)
        if right_role_name in config.role_priority else -1
    )

    if left_index > right_index:
        return 1
    if left_index < right_index:
        return -1
    return 0


def get_roles_for_accounts(accounts: List[Dict], access_token: str) -> List[Dict]:
    """Retrieve roles for a list of accounts.

    Args:
        accounts (List[Dict]): List of accounts.
        access_token (str): The access token for authentication.

    Returns:
        List[Dict]: List of roles.
    """
    sso_client = boto3.client("sso", region_name="us-east-1")
    roles = []
    list_roles_paginator = sso_client.get_paginator("list_account_roles")

    for account in accounts:
        page = list_roles_paginator.paginate(
            accessToken=access_token, accountId=account["accountId"]
        ).build_full_result()
        roles.extend(page["roleList"])

    return roles


def get_role_credentials(
    role: Dict,
    access_token: str,
    accounts_info: Dict
) -> Dict:
    """Retrieve credentials for a role.

    Args:
        role (Dict): The role for which credentials are to be retrieved.
        access_token (str): The access token for authentication.
        accounts_info (Dict): Information about accounts.

    Returns:
        Dict: A dictionary containing role credentials.
    """
    sso_client = boto3.client("sso", region_name="us-east-1")
    account_id = role["accountId"]

    role_credentials = sso_client.get_role_credentials(
        accessToken=access_token, accountId=account_id, roleName=role['roleName']
    )["roleCredentials"]

    return {
        f"{account_id}_{role['roleName']}": {
            "aws_access_key_id": role_credentials["accessKeyId"],
            "aws_secret_access_key": role_credentials["secretAccessKey"],
            "aws_session_token": role_credentials["sessionToken"],
            "aws_sso_role_name": role["roleName"],
            "aws_sso_account_id": account_id,
            "aws_sso_account_name": accounts_info[account_id]["accountName"],
            "aws_sso_account_email": accounts_info[account_id]["emailAddress"],
            "aws_sso_updated_at": time.ctime(),
        }
    }
