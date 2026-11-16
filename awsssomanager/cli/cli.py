"""aws-sso-manager command line interface."""

from collections import defaultdict
from collections.abc import Callable
import functools
import logging
from types import ModuleType
from typing import ParamSpec, TypeVar

import click
import coloredlogs
from yamale import YamaleError

from awsssomanager.config import PROVIDER_SAML, AWSSSOManagerConfig
from awsssomanager.constants import SSO_MANAGER_CONFIG_FILE
from awsssomanager.errors import AWSSSOManagerError
from awsssomanager.models import Role
from awsssomanager.profiles import plan_profiles, select_roles
from awsssomanager.sso.credentials import discover_roles as discover_sso_roles
from awsssomanager.sso.credentials import ensure_access_token, get_credentials
from awsssomanager.sso.device import authorize_device


__all__ = ["cli"]

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

_SAML_EXTRA_HINT = "provider saml needs the saml extra: pip install 'awsssomanager[saml]'"


def _friendly_errors(command: Callable[P, R]) -> Callable[P, R]:
    """Report expected failures as one-line errors instead of tracebacks."""

    @functools.wraps(command)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return command(*args, **kwargs)
        except (AWSSSOManagerError, YamaleError) as error:
            raise click.ClickException(str(error)) from error

    return wrapper


def _saml() -> ModuleType:
    # Imported lazily so Identity Center-only installs work without the saml extra.
    try:
        from awsssomanager import saml
    except ImportError as error:
        raise click.ClickException(_SAML_EXTRA_HINT) from error
    return saml


def _load_saved_config() -> AWSSSOManagerConfig:
    if not AWSSSOManagerConfig.check_aws_sso_config_exists():
        raise click.ClickException(
            "aws-sso-manager does not appear to be configured. "
            "Try running `aws-sso-manager configure`."
        )
    return AWSSSOManagerConfig.from_config(config_file=SSO_MANAGER_CONFIG_FILE)


@click.group()
@click.option("-v", "--verbose", is_flag=True, default=False, help="Verbose logging")
@click.help_option("-h", "--help")
def cli(verbose: bool) -> None:
    """Manage AWS credentials for every account and role you can reach."""
    log_level = logging.DEBUG if verbose else logging.INFO
    coloredlogs.install(level=log_level)  # root logger


@cli.command()
@click.argument("config_file", type=click.Path(exists=True, dir_okay=False))
@click.option("-R", "--reset", is_flag=True, default=False, help="Reset config and initiate setup")
@_friendly_errors
def configure(config_file: str, reset: bool) -> None:
    """Configure aws-sso-manager from CONFIG_FILE and log in."""
    # first check if config file is already present and we have permission to override
    if AWSSSOManagerConfig.check_aws_sso_config_exists() and not reset:
        raise click.ClickException(
            "config exists and reset flag was not set! (hint: -R, --reset to reconfigure)"
        )

    # create directory if needed
    AWSSSOManagerConfig.create_aws_dir()

    # validate, then save the config before signing in so a failed login can be retried
    config = AWSSSOManagerConfig.from_config(config_file=config_file)
    if config.provider == PROVIDER_SAML:
        config.write_config()
    _login(config)


@cli.command()
@_friendly_errors
def login() -> None:
    """Refresh credentials using the saved configuration."""
    _login(_load_saved_config())


@cli.command()
@_friendly_errors
def roles() -> None:
    """List every available role and the profiles it would get. Writes no credentials."""
    config = _load_saved_config()
    if config.provider == PROVIDER_SAML:
        _, discovered = _saml().discover_roles(config)
    else:
        config = authorize_device(config)
        config.write_config()
        discovered = discover_sso_roles(ensure_access_token(config))

    selection = config.profile_selection
    selected = select_roles(discovered, selection)
    plan = plan_profiles(
        selected,
        role_priority=config.role_priority,
        easy_profiles=selection.easy_profiles,
        login_account=config.login_account,
    )
    click.echo(_format_roles(discovered, {item.role for item in selected}, plan))


def _login(config: AWSSSOManagerConfig) -> None:
    if config.provider == PROVIDER_SAML:
        failures = _saml().login(config)
        if failures:
            raise click.ClickException(f"{len(failures)} role(s) could not be assumed")
        return

    # authorize device and get credentials
    config = authorize_device(config=config)
    config.write_config()
    get_credentials(config=config)


def _format_roles(roles: list[Role], selected: set[Role], plan: dict[str, Role]) -> str:
    profiles: dict[Role, list[str]] = defaultdict(list)
    for name, role in plan.items():
        profiles[role].append(name)

    header = ("SELECTED", "ACCOUNT ID", "ACCOUNT", "ROLE", "PROFILES")
    rows = [
        (
            "yes" if role in selected else "no",
            role.account_id,
            role.account_name or "-",
            role.role_name,
            ", ".join(sorted(profiles[role])) or "-",
        )
        for role in sorted(roles, key=lambda r: (r.account_name or r.account_id, r.role_name))
    ]
    widths = [max(len(row[i]) for row in [header, *rows]) for i in range(len(header) - 1)]

    def line(row: tuple[str, ...]) -> str:
        cells = [cell.ljust(width) for cell, width in zip(row, widths, strict=False)]
        return "  ".join([*cells, row[-1]])

    summary = f"\n\n{len(selected)} of {len(roles)} role(s) selected"
    return "\n".join(line(row) for row in [header, *rows]) + summary
