"""aws-sso-manager sso module: device"""
import logging
import time

import boto3

from awsssomanager.config.config import AWSSSOManagerConfig
from awsssomanager.sso.token import test_create_token
from awsssomanager.utils.general import run_cmd


__all__ = [
    "authorize_device",
    "register_new_device",
    "start_device_authorization"
]

logger = logging.getLogger(__name__)


def authorize_device(config: AWSSSOManagerConfig) -> AWSSSOManagerConfig:
    """Authorize the device for sso

    Args:
        config: AWSSSOMangerConfig instance.

    Returns:
        AWSSSOMangerConfig instance.
    """
    # check if device is registered
    if not set(
        [
            "clientId",
            "clientSecret",
            "clientSecretExpiresAt",
            "deviceCode"
        ]
    ).issubset(set([*config.config["default"]])):
        config = register_new_device(config)
    elif time.localtime() >= time.localtime(
        float(config.config["default"]["clientSecretExpiresAt"])
    ):
        # Device registration has expired (3 months)
        config = register_new_device(config)
    return config


def register_new_device(config: AWSSSOManagerConfig) -> AWSSSOManagerConfig:
    """Register the aws-sso-helper cli as a new device.

    Args:
        config: AWSSSOMangerConfig instance.

    Returns:
        AWSSSOMangerConfig instance.
    """
    sso_client = boto3.client("sso-oidc", region_name="us-east-1")
    register_results = sso_client.register_client(
        clientName="awsssomanager", clientType="public"
    )
    for key in ["clientId", "clientSecret", "clientSecretExpiresAt"]:
        config.config["default"][key] = str(register_results[key])
    config = start_device_authorization(config)

    # Save the config when we return it
    return config


def start_device_authorization(
    config: AWSSSOManagerConfig,
) -> AWSSSOManagerConfig:
    """Start device authorization for client.

    Args:
        config (AWSSSOManagerConfig): _description_

    Raises:
        RuntimeError: _description_

    Returns:
        AWSSSOManagerConfig: _description_
    """
    # create sso client
    sso_client = boto3.client("sso-oidc", region_name=config.region)

    # start device authorization
    device_auth_results = sso_client.start_device_authorization(
        clientId=config.config["default"]["clientId"],
        clientSecret=config.config["default"]["clientSecret"],
        startUrl=f"https://{config.sso_domain}.awsapps.com/start",
    )
    device_auth_starttime = time.time()
    config.config["default"]["deviceCode"] = device_auth_results["deviceCode"]
    verification_uri = device_auth_results["verificationUriComplete"]

    # prompt user for verification
    logger.info(
        f'Registering device. A browser window or tab should open. '
        f'If not, please go to {verification_uri} )'
    )
    run_cmd(command=f'open {verification_uri}')
    logger.info('waiting on user...')

    while not test_create_token(config):
        time.sleep(1)
        if (time.time() - device_auth_starttime) >= device_auth_results["expiresIn"]:
            raise RuntimeError("Failed to authenticate in time")
    logger.info('Successfully registered user.')
    return config
