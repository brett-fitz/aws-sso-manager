"""awsssomanager.config module: config"""
import logging
from os import makedirs
from typing import Dict, List

import yaml

from awsssomanager import AWS_DIR, SSO_MANAGER_CONFIG_FILE
from awsssomanager.utils import is_valid_dir, is_valid_file


__all__ = [
    "AWSSSOManagerConfig"
]

logger = logging.getLogger(__name__)


class AWSSSOManagerConfig:
    """AWSSSOManagerConfig Class
    """

    def __init__(self, config: Dict):
        self.config: Dict = config

    @property
    def login_account(self) -> str:
        """Get the loginAccount

        Returns:
            loginAccount.
        """
        return self.config['default']['loginAccount']

    @property
    def region(self) -> str:
        """Get the default aws region

        Returns:
            AWS region.
        """
        return self.config['default']['region']

    @property
    def role_priority(self) -> List[str]:
        """Get the role priority list

        Returns:
            Role priority list.
        """
        return self.config['role_priority']

    @property
    def sso_domain(self) -> str:
        """Get the ssoDomain

        Returns:
            ssoDomain.
        """
        return self.config['default']['ssoDomain']

    @classmethod
    def from_config(cls, config_file: str):
        """Create a AWS SSO Manager config from a user config file.

        Args:
            config_file: AWS SSO Manager user config file.

        Returns:
            class instance.
        """
        with open(config_file, 'r') as file:
            config = yaml.safe_load(file)
        return cls(config=config)

    @staticmethod
    def check_aws_dir_exists() -> bool:
        """Checks if ~/.aws exists

        Returns:
            bool: True or False based on whether the directory exists or not.
        """
        try:
            is_valid_dir(AWS_DIR)
            logger.info('Found aws directory at ~/.aws/')
            return True
        except FileNotFoundError:
            logger.warning('Directory ~/.aws/ does not exist!')
            return False

    @staticmethod
    def create_aws_dir() -> None:
        """Creates the default ~/.aws directory if it does not already exist.
        """
        if not AWSSSOManagerConfig.check_aws_dir_exists():
            logger.info('Creating directory ~/.aws/')
            makedirs(AWS_DIR)

    @staticmethod
    def check_aws_sso_config_exists() -> bool:
        """Checks if the aws sso manager config file exists.

        Returns:
            bool: Boolean value indicating whether the file exists or not.
        """
        try:
            is_valid_file(filename=SSO_MANAGER_CONFIG_FILE)
            logger.info(f'Found aws-sso-manager config file: {SSO_MANAGER_CONFIG_FILE}')
            return True
        except FileNotFoundError:
            logger.warning(f'File {SSO_MANAGER_CONFIG_FILE} does not exist')
            return False

    def write_config(self) -> None:
        """Write aws-sso-manger config file
        """
        with open(SSO_MANAGER_CONFIG_FILE, 'w') as file:
            logger.info(f'writing config file {SSO_MANAGER_CONFIG_FILE}')
            yaml.safe_dump(self.config, file, default_flow_style=False)
