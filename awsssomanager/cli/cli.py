"""aws-sso-manager.cli module: cli"""
import logging

import click
import coloredlogs

from awsssomanager import SCHEMA_PATH, SSO_MANAGER_CONFIG_FILE
from awsssomanager.config import AWSSSOManagerConfig
from awsssomanager.sso.credentials import get_credentials
from awsssomanager.sso.device import authorize_device
from awsssomanager.utils.validators import validate_yaml


__all__ = [
    "cli"
]

logger = logging.getLogger(__name__)


@click.group()
@click.option("-v", "--verbose", is_flag=True, default=False, help="Verbose logging")
@click.help_option('-h', '--help')
def cli(verbose: bool):
    """Python CLI Core"""
    log_level = logging.DEBUG if verbose else logging.INFO
    coloredlogs.install(level=log_level)  # root logger


@cli.command()
@click.argument('config_file', type=click.STRING)
@click.option("-R", "--reset", is_flag=True, default=False, help="Reset config and initiate setup")
def configure(config_file: str, reset: bool) -> None:
    """Configure AWS SSO Manager"""
    # first check if config file is already present and we have permission to override
    if AWSSSOManagerConfig.check_aws_sso_config_exists() and not reset:
        logger.error(
            'config exists and reset flag was not set! '
            '(hint: -R, --reset to reconfigure)'
        )
        click.get_current_context().exit()

    # validate config file
    validate_yaml(config_file, SCHEMA_PATH)

    # create directory if needed
    AWSSSOManagerConfig.create_aws_dir()

    # create aws-sso-manager config file
    config = AWSSSOManagerConfig.from_config(config_file=config_file)

    # authorize device and get credentials
    _authorize_device_and_get_credentials(config=config)


@cli.command()
def login() -> None:
    """aws sso login"""
    if not AWSSSOManagerConfig.check_aws_sso_config_exists():
        logger.error(
            'aws-sso-manager does not appear to be configured. '
            'Try running `aws-sso-manager configure`.'
        )
        click.get_current_context().exit()
    config = AWSSSOManagerConfig.from_config(config_file=SSO_MANAGER_CONFIG_FILE)

    # authorize device and get credentials
    _authorize_device_and_get_credentials(config=config)


def _authorize_device_and_get_credentials(config: AWSSSOManagerConfig) -> None:
    # authorize device and get credentials
    config = authorize_device(config=config)

    # write device credentials
    config.write_config()

    # get account credentials
    get_credentials(config=config)
