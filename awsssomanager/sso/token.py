"""aws-sso-manager sso module: token"""
import logging
import time

import boto3

from awsssomanager.config.config import AWSSSOManagerConfig

__all__ = [
    "create_token",
    "test_create_token"
]

logger = logging.getLogger(__name__)


def create_token(config: AWSSSOManagerConfig) -> AWSSSOManagerConfig:
    """
    Create an AWS SSO access token and update the configuration.

    Args:
        config (AWSSSOManagerConfig): The configuration parser containing SSO settings.

    Returns:
        AWSSSOManagerConfig: Updated configuration after creating the token.
    """
    sso_client = boto3.client("sso-oidc", region_name=config.region)
    token_result = sso_client.create_token(
        clientId=config.client_id,
        clientSecret=config.client_secret,
        grantType="urn:ietf:params:oauth:grant-type:device_code",
        refreshToken="abcdefg",  # Note: test refreshToken
        deviceCode=config.device_code,
        code=config.device_code,
    )

    # Update configuration with token information
    config.config["device"]["accessToken"] = token_result["accessToken"]
    config.config["device"]["accessTokenExpiresAt"] = str(
        time.time() + float(token_result["expiresIn"]) - 1
    )
    return config


def test_create_token(config: AWSSSOManagerConfig) -> bool:
    """Attempt to create a SSO token.

    Args:
        config (AWSSSOManagerConfig):

    Returns:
        bool: True if successful else False.
    """
    sso_client = boto3.client("sso-oidc", region_name=config.region)
    try:
        create_token(config)
    except (
        sso_client.exceptions.InvalidClientException,
        sso_client.exceptions.AuthorizationPendingException,
    ):
        return False
    return True
