"""Read and write ``~/.aws/credentials`` without disturbing other tools' sections.

The file is shared with the AWS CLI and with tools like saml2aws, so writes only replace or
prune sections this tool owns, identified by ``x_managed_by`` and ``x_source``.
"""

from collections.abc import Mapping
import configparser
import logging
import os
from pathlib import Path
import tempfile

from awsssomanager.constants import CREDENTIALS_FILE
from awsssomanager.profiles import MANAGED_BY


__all__ = [
    "LEGACY_SSO_MARKER",
    "load_credentials",
    "save_credentials",
    "write_profiles",
]

logger = logging.getLogger(__name__)

#: Key written by aws-sso-manager releases before ``x_managed_by`` existed (SSO only).
LEGACY_SSO_MARKER = "aws_sso_updated_at"
_CREDENTIALS_MODE = 0o600
_AWS_DIR_MODE = 0o700


class _CredentialsParser(configparser.ConfigParser):
    """ConfigParser that keeps key case (the default lower-cases every key)."""

    def optionxform(self, optionstr: str) -> str:
        return optionstr


def _path(path: str | Path | None) -> Path:
    # Resolved at call time so tests can monkeypatch CREDENTIALS_FILE.
    return Path(path if path is not None else CREDENTIALS_FILE)


def load_credentials(path: str | Path | None = None) -> configparser.ConfigParser:
    """Load the credentials file (an empty parser if it does not exist yet).

    Interpolation is disabled so a ``%`` in another tool's section can never break a write.

    Args:
        path: Credentials file. Defaults to ``~/.aws/credentials``.

    Returns:
        The parsed file.
    """
    credentials = _CredentialsParser(interpolation=None)
    credentials.read(_path(path), encoding="utf-8")
    return credentials


def save_credentials(
    credentials: configparser.ConfigParser, path: str | Path | None = None
) -> None:
    """Atomically write the credentials file with user-only permissions.

    Args:
        credentials: Parser holding every section to keep.
        path: Credentials file. Defaults to ``~/.aws/credentials``.
    """
    target = _path(path)
    if target.is_symlink():
        # Write through the link (dotfile setups) instead of replacing it with a regular file.
        target = target.resolve()
    target.parent.mkdir(mode=_AWS_DIR_MODE, parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".credentials.", text=True)
    try:
        os.chmod(tmp_name, _CREDENTIALS_MODE)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            credentials.write(file)
        os.replace(tmp_name, target)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def _owned(section: Mapping[str, str], source: str, *, adopt_legacy_sso: bool) -> bool:
    if section.get("x_managed_by") == MANAGED_BY:
        return section.get("x_source") == source
    return adopt_legacy_sso and LEGACY_SSO_MARKER in section


def write_profiles(
    profiles: Mapping[str, Mapping[str, str]],
    *,
    source: str,
    prune: bool = True,
    adopt_legacy_sso: bool = False,
    path: str | Path | None = None,
) -> list[str]:
    """Write profiles and prune the ones this source wrote earlier but no longer selects.

    Sections not owned by ``source`` (other tools, or another aws-sso-manager provider) are never
    removed. A section that this run writes is replaced, whoever wrote it before.

    Args:
        profiles: Section name to key/value pairs, from ``build_profiles``.
        source: Provider identity, matching ``x_source`` in the sections.
        prune: Remove stale owned sections. Callers turn this off when some roles failed, so
            still-valid credentials from the previous run are not deleted.
        adopt_legacy_sso: Treat pre-``x_managed_by`` aws-sso-manager sections as owned by this
            source (the SSO provider sets this).
        path: Credentials file. Defaults to ``~/.aws/credentials``.

    Returns:
        Names of pruned sections.
    """
    credentials = load_credentials(path)

    pruned: list[str] = []
    if prune:
        for name in credentials.sections():
            if name not in profiles and _owned(
                credentials[name], source, adopt_legacy_sso=adopt_legacy_sso
            ):
                credentials.remove_section(name)
                pruned.append(name)

    for name, values in profiles.items():
        if credentials.has_section(name):
            credentials.remove_section(name)
        credentials[name] = dict(values)

    save_credentials(credentials, path)
    for name in pruned:
        logger.info(f"removed stale profile: {name}")
    logger.info(f"wrote {len(profiles)} profile(s) to {_path(path)}")
    return pruned
