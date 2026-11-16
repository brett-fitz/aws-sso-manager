"""Guard: no test may touch the developer's real ~/.aws."""

import importlib
from pathlib import Path
import pkgutil
import sys

import awsssomanager
from awsssomanager.credentials_file import write_profiles


REAL_AWS_DIR = Path.home() / ".aws"


def _all_modules() -> list[str]:
    names = [awsssomanager.__name__]
    for info in pkgutil.walk_packages(awsssomanager.__path__, prefix="awsssomanager."):
        importlib.import_module(info.name)
        names.append(info.name)
    return names


def test_no_module_points_at_real_aws_dir(aws_dir: Path) -> None:
    leaks = []
    for name in _all_modules():
        for attr, value in vars(sys.modules[name]).items():
            if isinstance(value, str | Path) and Path(value).is_relative_to(REAL_AWS_DIR):
                leaks.append(f"{name}.{attr} = {value}")
    assert not leaks, f"unpatched ~/.aws paths (add them to conftest._PATCH_TARGETS): {leaks}"


def test_default_writes_land_in_tmp(aws_dir: Path, tmp_path: Path) -> None:
    write_profiles({"probe": {"aws_access_key_id": "x"}}, source="test")
    assert (aws_dir / "credentials").is_file()
    assert aws_dir.is_relative_to(tmp_path)
