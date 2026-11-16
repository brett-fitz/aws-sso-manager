"""SAML login: one browser sign-in, then every selected role from the same assertion."""

from dataclasses import replace
import logging

from awsssomanager.config import AWSSSOManagerConfig
from awsssomanager.credentials_file import write_profiles
from awsssomanager.models import Role, RoleCredentials
from awsssomanager.profiles import build_profiles, plan_profiles, select_roles
from awsssomanager.saml.accounts import fetch_account_aliases
from awsssomanager.saml.assertion import SamlAssertion, parse_saml_response
from awsssomanager.saml.browser import capture_saml_response
from awsssomanager.saml.sts import assume_roles, resolve_session_duration


__all__ = ["discover_roles", "login"]

logger = logging.getLogger(__name__)


def discover_roles(config: AWSSSOManagerConfig) -> tuple[SamlAssertion, list[Role]]:
    """Sign in to the IdP and list every role the assertion grants, with account aliases.

    Args:
        config: A saml-provider config.

    Returns:
        The assertion (still valid for a few minutes) and its roles.
    """
    saml_response = capture_saml_response(
        config.saml_app_url, browser=config.saml_browser, timeout=config.saml_timeout
    )
    assertion = parse_saml_response(saml_response)
    aliases = fetch_account_aliases(assertion)
    roles = [replace(role, account_name=aliases.get(role.account_id)) for role in assertion.roles]
    accounts = {role.account_id for role in roles}
    logger.info(f"SAML assertion grants {len(roles)} role(s) across {len(accounts)} account(s)")
    return assertion, roles


def login(config: AWSSSOManagerConfig) -> dict[Role, Exception]:
    """Assume every selected role and write its profiles.

    If any role fails, stale profiles are not pruned, so credentials that are still valid from
    the previous run survive.

    Args:
        config: A saml-provider config.

    Returns:
        Roles that could not be assumed, with the error for each (empty on full success).
    """
    selection = config.profile_selection
    assertion, roles = discover_roles(config)
    selected = select_roles(roles, selection)
    logger.info(f"selected {len(selected)} of {len(roles)} role(s)")
    if not selected:
        logger.warning("no roles selected; check the profiles include/exclude rules")
        return {}

    results = assume_roles(
        assertion,
        [item.role for item in selected],
        region=config.region,
        duration=resolve_session_duration(config.saml_session_duration, assertion),
    )
    credentials = {role: r for role, r in results.items() if isinstance(r, RoleCredentials)}
    failures = {role: r for role, r in results.items() if isinstance(r, Exception)}
    for role, error in failures.items():
        logger.error(f"could not assume {role.role_arn}: {error}")

    plan = plan_profiles(
        selected,
        role_priority=config.role_priority,
        easy_profiles=selection.easy_profiles,
        login_account=config.login_account,
    )
    profiles = build_profiles(plan, credentials, source=config.credential_source)
    write_profiles(profiles, source=config.credential_source, prune=not failures)
    if failures:
        logger.warning("some roles failed, so existing profiles were not pruned")
    return failures
