"""awsssomanager.utils module: general"""
import logging
import subprocess


__all__ = [
    "run_cmd",
]

logger = logging.getLogger(__name__)


def run_cmd(command):
    """
    Run a shell command safely.

    Args:
        command (str): The command to execute.

    Returns:
        tuple: A tuple containing (stdout, stderr).
    """
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        shell=True
    ) as process:
        stdout, stderr = process.communicate()
        return stdout, stderr
