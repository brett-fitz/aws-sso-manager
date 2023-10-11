"""awsssomanager.utils module: validators"""
import logging
from pathlib import Path

import yamale


__all__ = [
    "is_valid_dir",
    "is_valid_file",
    "validate_yaml"
]

logger = logging.getLogger(__name__)


def is_valid_dir(directory: str) -> bool:
    """
    Check if a directory exists.

    Args:
        directory (str): The directory path to check.

    Returns:
        bool: True if the directory exists, False otherwise.
    """
    path = Path(directory)
    if path.is_dir():
        return True
    raise FileNotFoundError(f"Directory not found: {directory}")


def is_valid_file(filename: str) -> bool:
    """
    Check if a file exists.

    Args:
        filename (str): The name of the file to check.

    Returns:
        bool: True if the file exists, False otherwise.
    """
    path = Path(filename)
    if path.is_file():
        return True
    raise FileNotFoundError(f"File not found: {filename}")


def validate_yaml(input_file: str, schema_file: str) -> None:
    """
    Validate whether the input YAML file conforms to the specified schema.

    Args:
        input_file (str): Path to the input YAML file.
        schema_file (str): Path to the YAML schema file.

    Raises:
        yamale.yamale_error.YamaleError: If validation fails.

    Returns:
        None
    """
    # Load schema
    schema = yamale.make_schema(schema_file)

    # Load data
    data = yamale.make_data(input_file)

    # Validate
    yamale.validate(schema, data)
