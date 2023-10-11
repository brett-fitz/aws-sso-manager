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


def find_repo_root(path: str) -> Path:
    """Find repository root from the path's parents"""

    for parent in Path(path).parents:
        # Check whether "path/.git" exists and is a directory
        git_dir = parent.joinpath(".git")
        if git_dir.is_dir():
            return parent

    raise ValueError("Could not find .git folder")

SCHEMA_PATH: Final = Path("config/schema.yml")
