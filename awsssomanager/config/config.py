"""awsssomanager.config module: config."""

import logging
import os
from os import makedirs
from pathlib import Path
from urllib.parse import urlparse

import yaml

from awsssomanager.constants import (
    AWS_DIR,
    DEFAULT_STS_REGION,
    SCHEMA_PATH,
    SSO_MANAGER_CONFIG_FILE,
)
from awsssomanager.errors import AWSSSOManagerError
from awsssomanager.profiles import ProfileSelection, ProfileSelectionError
from awsssomanager.utils import is_valid_dir, is_valid_file
from awsssomanager.utils.validators import validate_yaml


__all__ = ["PROVIDER_SAML", "PROVIDER_IDENTITY_CENTER", "AWSSSOManagerConfig", "ConfigError"]

logger = logging.getLogger(__name__)

PROVIDER_IDENTITY_CENTER = "identity-center"
PROVIDER_SAML = "saml"
DEFAULT_SAML_BROWSER = "chrome"
DEFAULT_SAML_TIMEOUT = 300


class ConfigError(AWSSSOManagerError, ValueError):
    """The config passed schema validation but is inconsistent for its provider."""


class AWSSSOManagerConfig:
    """The aws-sso-manager config file plus the device registration state written back to it."""

    def __init__(self, config: dict):
        """Wrap a parsed config dict, ensuring the generated ``device`` block exists.

        Args:
            config: Parsed aws-sso-manager YAML config.
        """
        self.config: dict = config
        if not self.config.get("device"):
            self.config["device"] = {}

    @property
    def access_token(self) -> str:
        """Get the device accessToken.

        Returns:
            accessToken.
        """
        return self.config["device"]["accessToken"]

    @property
    def access_token_expires_at(self) -> float:
        """Get the device accessTokenExpiresAt.

        Returns:
            accessTokenExpiresAt.
        """
        return float(self.config["device"].get("accessTokenExpiresAt", "0"))

    @property
    def client_id(self) -> str:
        """Get the device clientId.

        Returns:
            clientId.
        """
        return self.config["device"]["clientId"]

    @property
    def client_secret(self) -> str:
        """Get the device clientSecret.

        Returns:
            clientSecret.
        """
        return self.config["device"]["clientSecret"]

    @property
    def client_secret_expires_at(self) -> float:
        """Get the device clientSecretExpiresAt.

        Returns:
            clientSecretExpiresAt.
        """
        return float(self.config["device"]["clientSecretExpiresAt"])

    @property
    def device_code(self) -> str:
        """Get the device deviceCode.

        Returns:
            deviceCode.
        """
        return self.config["device"]["deviceCode"]

    @property
    def login_account(self) -> str | None:
        """Account id, account name, or profile name to copy into ``default``, if configured."""
        value = (self.config.get("default") or {}).get("loginAccount")
        return None if value is None else str(value)

    @property
    def provider(self) -> str:
        """``identity-center`` (AWS IAM Identity Center, the default) or ``saml`` (federation)."""
        return self.config.get("provider") or PROVIDER_IDENTITY_CENTER

    @property
    def region(self) -> str:
        """Identity Center region (identity-center) or STS region (saml, default us-east-1)."""
        region = self.config.get("region")
        if region:
            return region
        if self.provider == PROVIDER_SAML:
            return DEFAULT_STS_REGION
        raise ConfigError("'region' is required when provider is identity-center")

    @property
    def role_priority(self) -> list[str]:
        """Role names from lowest to highest priority (empty when not configured)."""
        return list(self.config.get("role_priority") or [])

    @property
    def _saml(self) -> dict:
        return self.config.get("saml") or {}

    @property
    def saml_app_url(self) -> str:
        """IdP-initiated sign-in link for the IdP's AWS app (for example, Okta's embed link)."""
        return self._saml["appUrl"]

    @property
    def saml_session_duration(self) -> int | None:
        """Requested credential lifetime in seconds, if configured."""
        return self._saml.get("sessionDuration")

    @property
    def saml_browser(self) -> str:
        """Playwright browser channel used for the SAML sign-in."""
        return self._saml.get("browser") or DEFAULT_SAML_BROWSER

    @property
    def saml_timeout(self) -> int:
        """Seconds allowed to finish signing in to the identity provider."""
        return self._saml.get("timeout") or DEFAULT_SAML_TIMEOUT

    @property
    def profile_selection(self) -> ProfileSelection:
        """The parsed ``profiles`` block."""
        return ProfileSelection.from_config(self.config.get("profiles"))

    @property
    def credential_source(self) -> str:
        """Identity recorded in ``x_source`` on every credentials section this config writes."""
        if self.provider == PROVIDER_SAML:
            return f"saml:{urlparse(self.saml_app_url).hostname}"
        return f"identity-center:{self.sso_domain}"

    def validate(self) -> None:
        """Check the provider-specific rules the yamale schema cannot express.

        Raises:
            ConfigError: If a field the provider needs is missing or invalid.
        """
        if self.provider == PROVIDER_IDENTITY_CENTER:
            missing = [key for key in ("ssoDomain", "region") if not self.config.get(key)]
            if missing:
                raise ConfigError(f"provider identity-center requires: {', '.join(missing)}")
        else:
            if not self._saml.get("appUrl"):
                raise ConfigError("provider saml requires saml.appUrl")
            parsed = urlparse(self.saml_app_url)
            if parsed.scheme != "https" or not parsed.hostname:
                raise ConfigError(f"saml.appUrl must be an https URL, got: {self.saml_app_url}")
        try:
            self.profile_selection  # noqa: B018  # parse to surface rule errors early
        except ProfileSelectionError as error:
            raise ConfigError(str(error)) from error

    @property
    def sso_domain(self) -> str:
        """Get the ssoDomain.

        Returns:
            ssoDomain.
        """
        return self.config["ssoDomain"]

    @classmethod
    def from_config(cls, config_file: str | Path) -> "AWSSSOManagerConfig":
        """Create a AWS SSO Manager config from a user config file.

        Args:
            config_file: AWS SSO Manager user config file.

        Returns:
            class instance.

        Raises:
            yamale.YamaleError: If the file does not match the schema.
            ConfigError: If the file is inconsistent for its provider.
        """
        # validate config file
        validate_yaml(config_file, SCHEMA_PATH)

        # load config file
        with open(config_file, encoding="utf-8") as file:
            config = yaml.safe_load(file)
        instance = cls(config=config)
        instance.validate()
        return instance

    @staticmethod
    def check_aws_dir_exists() -> bool:
        """Checks if ~/.aws exists.

        Returns:
            bool: True or False based on whether the directory exists or not.
        """
        try:
            is_valid_dir(AWS_DIR)
            logger.info("Found aws directory at ~/.aws/")
            return True
        except FileNotFoundError:
            logger.warning("Directory ~/.aws/ does not exist!")
            return False

    @staticmethod
    def create_aws_dir() -> None:
        """Creates the default ~/.aws directory if it does not already exist."""
        if not AWSSSOManagerConfig.check_aws_dir_exists():
            logger.info("Creating directory ~/.aws/")
            makedirs(AWS_DIR)

    @staticmethod
    def check_aws_sso_config_exists() -> bool:
        """Checks if the aws sso manager config file exists.

        Returns:
            bool: Boolean value indicating whether the file exists or not.
        """
        try:
            is_valid_file(filename=SSO_MANAGER_CONFIG_FILE)
            logger.info(f"Found aws-sso-manager config file: {SSO_MANAGER_CONFIG_FILE}")
            return True
        except FileNotFoundError:
            logger.warning(f"File {SSO_MANAGER_CONFIG_FILE} does not exist")
            return False

    def write_config(self) -> None:
        """Write the aws-sso-manager config file (user-only: it holds device secrets)."""
        fd = os.open(SSO_MANAGER_CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.chmod(SSO_MANAGER_CONFIG_FILE, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            logger.info(f"writing config file {SSO_MANAGER_CONFIG_FILE}")
            yaml.safe_dump(self.config, file, default_flow_style=False)
