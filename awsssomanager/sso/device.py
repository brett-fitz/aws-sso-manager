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
    """Authorizes the device for AWS SSO access.

    Args:
        config (AWSSSOManagerConfig): The configuration object containing device and AWS SSO
                                      client information.

    Returns:
        AWSSSOManagerConfig: The updated configuration object with device authorization.

    Notes:
        This function checks if the device is already registered for AWS SSO access. If the
        necessary device information (client ID, client secret, client secret expiration, and
        device code) is not present in the configuration object, it registers the device by
        calling the register_new_device function. If the client secret has expired, it also
        triggers device registration to obtain new credentials. Once the device is registered or
        updated, the function returns the updated configuration object.
    """
    # check if device is registered
    if not set(
        [
            "clientId",
            "clientSecret",
            "clientSecretExpiresAt",
            "deviceCode"
        ]
    ).issubset(set([*config.config["device"]])):
        config = register_new_device(config)
    elif time.localtime() >= time.localtime(
        config.client_secret_expires_at
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
    sso_client = boto3.client("sso-oidc", region_name=config.region)
    register_results = sso_client.register_client(
        clientName="aws-sso-manager", clientType="public"
    )
    for key in ["clientId", "clientSecret", "clientSecretExpiresAt"]:
        config.config["device"][key] = str(register_results[key])
    config = start_device_authorization(config)

    # Save the config when we return it
    return config


def start_device_authorization(
    config: AWSSSOManagerConfig,
) -> AWSSSOManagerConfig:
    """Starts the device authorization flow for the AWS SSO client.

    Args:
        config (AWSSSOManagerConfig): The configuration object containing necessary parameters
                                      for the AWS SSO client.

    Raises:
        RuntimeError: Raised if the device authorization process fails to authenticate within the
                      specified time limit.

    Returns:
        AWSSSOManagerConfig: The updated configuration object with the device code and verification
                             URI information.

    Notes:
        This function initiates the device authorization flow for the AWS SSO client. It obtains the
        necessary information from the provided configuration object, including the client ID, client
        secret, and SSO domain. The device authorization process is started using the provided AWS SSO
        client and parameters. Once started, the function prompts the user to verify the device by
        opening a browser window or tab with the verification URI. It then waits for the user to
        complete the verification process. If the process fails to authenticate within the specified
        time limit, a RuntimeError is raised.
    """
    # create sso client
    sso_client = boto3.client("sso-oidc", region_name=config.region)

    # start device authorization
    device_auth_results = sso_client.start_device_authorization(
        clientId=config.client_id,
        clientSecret=config.client_secret,
        startUrl=f"https://{config.sso_domain}.awsapps.com/start",
    )

    device_auth_starttime = time.time()
    config.config["device"]["deviceCode"] = device_auth_results["deviceCode"]
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
