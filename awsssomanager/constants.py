"""awsssomanager: constants"""
from pathlib import Path
from typing import Final

__all__ = [
    "AWS_DIR",
    "CREDENTIALS_FILE",
    "SSO_MANAGER_CONFIG_FILE",
    "SCHEMA_PATH"
]

AWS_DIR: Final = f"{Path.home()}/.aws/"
CREDENTIALS_FILE: Final = f"{AWS_DIR}credentials"
SSO_MANAGER_CONFIG_FILE: Final = f"{AWS_DIR}aws-sso-manager.yml"

SCHEMA_PATH: Final = Path(__file__).resolve().parent / "config" / "schema.yml"
