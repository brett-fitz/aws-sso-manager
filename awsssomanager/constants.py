"""awsssomanager: constants."""

from pathlib import Path
from typing import Final


__all__ = [
    "AWS_DIR",
    "BROWSER_PROFILE_DIR",
    "CREDENTIALS_FILE",
    "DEFAULT_STS_REGION",
    "SCHEMA_PATH",
    "SSO_MANAGER_CONFIG_FILE",
]

AWS_DIR: Final = f"{Path.home()}/.aws/"
CREDENTIALS_FILE: Final = f"{AWS_DIR}credentials"
SSO_MANAGER_CONFIG_FILE: Final = f"{AWS_DIR}aws-sso-manager.yml"

#: Dedicated browser profile for Okta sign-in; holds the Okta session cookie between logins.
BROWSER_PROFILE_DIR: Final = Path(AWS_DIR) / "aws-sso-manager" / "browser"

#: STS region used for SAML federation when the config sets none.
DEFAULT_STS_REGION: Final = "us-east-1"

SCHEMA_PATH: Final = Path(__file__).resolve().parent / "config" / "schema.yml"
