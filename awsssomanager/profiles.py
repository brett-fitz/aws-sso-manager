"""Choose which roles get profiles, and what those profiles are called.

Selection runs *before* any credentials are requested, so roles a user never wants (break-glass
roles, for example) are never assumed at all, not merely hidden from the credentials file.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC
from fnmatch import fnmatchcase
import logging
from typing import Any

from awsssomanager.errors import AWSSSOManagerError
from awsssomanager.models import Role, RoleCredentials


__all__ = [
    "DEFAULT_PROFILE",
    "MANAGED_BY",
    "ProfileRule",
    "ProfileSelection",
    "ProfileSelectionError",
    "SelectedRole",
    "build_profiles",
    "plan_profiles",
    "select_roles",
]

logger = logging.getLogger(__name__)

DEFAULT_PROFILE = "default"
MANAGED_BY = "aws-sso-manager"
_UNRANKED = -1


class ProfileSelectionError(AWSSSOManagerError, ValueError):
    """The ``profiles`` config is invalid or ambiguous for the roles that were discovered."""


def _glob(value: str, pattern: str) -> bool:
    return fnmatchcase(value.lower(), pattern.lower())


@dataclass(frozen=True)
class ProfileRule:
    """One ``profiles.include`` / ``profiles.exclude`` entry.

    Attributes:
        account: Glob matched against the account id *or* the account name/alias.
        role: Glob matched against the role name.
        name: Explicit profile name. Only meaningful on include rules, and only when the rule
            resolves to exactly one role.
    """

    account: str = "*"
    role: str = "*"
    name: str | None = None

    @classmethod
    def from_config(cls, data: Mapping[str, Any]) -> "ProfileRule":
        """Build a rule from its YAML mapping.

        Account ids are coerced to strings so an unquoted ``account: 123456789012`` still works.

        Args:
            data: The rule mapping (``account``, ``role``, ``name``; all optional).

        Returns:
            The rule.

        Raises:
            ProfileSelectionError: If the rule sets neither ``account`` nor ``role``, which would
                match every role and is almost certainly a mistake.
        """
        account = data.get("account")
        role = data.get("role")
        if account is None and role is None:
            raise ProfileSelectionError(
                f"profile rule {dict(data)} must set at least one of 'account' or 'role'"
            )
        name = data.get("name")
        return cls(
            account="*" if account is None else str(account),
            role="*" if role is None else str(role),
            name=None if name is None else str(name),
        )

    def matches(self, role: Role) -> bool:
        """Whether this rule selects ``role`` (case-insensitive globs).

        Args:
            role: Candidate role.

        Returns:
            True if both the account and role patterns match.
        """
        account_ok = _glob(role.account_id, self.account) or (
            role.account_name is not None and _glob(role.account_name, self.account)
        )
        return account_ok and _glob(role.role_name, self.role)

    def describe(self) -> str:
        """Human-readable form for log and error messages."""
        parts = [f"account={self.account}", f"role={self.role}"]
        if self.name:
            parts.append(f"name={self.name}")
        return "{" + ", ".join(parts) + "}"


@dataclass(frozen=True)
class ProfileSelection:
    """The parsed ``profiles`` config block.

    Attributes:
        include: Rules that select roles. ``None`` selects every role (the behaviour before
            this block existed); an empty tuple selects nothing.
        exclude: Rules that drop roles. Exclusion always wins over inclusion.
        easy_profiles: Also write ``<account_id>_<role>``, ``<account_id>`` and
            ``<account_name>`` profiles for every selected role.
    """

    include: tuple[ProfileRule, ...] | None = None
    exclude: tuple[ProfileRule, ...] = ()
    easy_profiles: bool = True

    @classmethod
    def from_config(cls, data: Mapping[str, Any] | None) -> "ProfileSelection":
        """Build the selection from the ``profiles`` mapping (or its absence).

        Args:
            data: The ``profiles`` mapping, or None when the block is omitted.

        Returns:
            The selection.
        """
        if not data:
            return cls()
        include = data.get("include")
        return cls(
            include=None
            if include is None
            else tuple(ProfileRule.from_config(rule) for rule in include),
            exclude=tuple(ProfileRule.from_config(rule) for rule in data.get("exclude") or ()),
            easy_profiles=bool(data.get("easyProfiles", True)),
        )


@dataclass(frozen=True)
class SelectedRole:
    """A role that passed selection, plus any explicit profile names given to it."""

    role: Role
    names: tuple[str, ...] = ()


def select_roles(roles: Iterable[Role], selection: ProfileSelection) -> list[SelectedRole]:
    """Apply include/exclude rules to the discovered roles.

    Args:
        roles: Every role the provider discovered, in discovery order.
        selection: The parsed ``profiles`` block.

    Returns:
        Selected roles in discovery order.

    Raises:
        ProfileSelectionError: If a named rule matches more than one role, or two roles claim the
            same explicit profile name.
    """
    candidates = [
        role for role in roles if not any(rule.matches(role) for rule in selection.exclude)
    ]
    if selection.include is None:
        return [SelectedRole(role) for role in candidates]

    names: dict[Role, list[str]] = {}
    for rule in selection.include:
        matched = [role for role in candidates if rule.matches(role)]
        if rule.name and len(matched) > 1:
            found = ", ".join(f"{r.account_id}/{r.role_name}" for r in matched)
            raise ProfileSelectionError(
                f"profile rule {rule.describe()} names a single profile but matches "
                f"{len(matched)} roles: {found}"
            )
        if rule.name and not matched:
            logger.warning(
                f"profile '{rule.name}': rule {rule.describe()} matches no selectable role "
                "(excluded, or not assigned to you)"
            )
        for role in matched:
            role_names = names.setdefault(role, [])
            if rule.name and rule.name not in role_names:
                role_names.append(rule.name)

    owners: dict[str, Role] = {}
    for role, role_names in names.items():
        for name in role_names:
            other = owners.setdefault(name, role)
            if other != role:
                raise ProfileSelectionError(
                    f"profile name '{name}' is claimed by both {other.account_id}/"
                    f"{other.role_name} and {role.account_id}/{role.role_name}"
                )

    return [SelectedRole(role, tuple(names[role])) for role in candidates if role in names]


def _priority(role_priority: Sequence[str], role_name: str) -> int:
    return role_priority.index(role_name) if role_name in role_priority else _UNRANKED


def plan_profiles(
    selected: Sequence[SelectedRole],
    *,
    role_priority: Sequence[str] = (),
    easy_profiles: bool = True,
    login_account: str | None = None,
) -> dict[str, Role]:
    """Decide every profile name to write and which role each one holds.

    Precedence, lowest to highest: easy profiles, then ``default``, then explicit names.

    Args:
        selected: Output of :func:`select_roles`.
        role_priority: Role names from lowest to highest priority. Per account, the highest
            ranked role backs the ``<account_id>`` / ``<account_name>`` profiles; unranked
            roles lose to ranked ones and ties keep the first role discovered.
        easy_profiles: Write the ``<account_id>_<role>``, ``<account_id>`` and
            ``<account_name>`` profiles.
        login_account: Account id, account name, or explicit profile name to copy into the
            ``default`` profile.

    Returns:
        Profile name to role.
    """
    best: dict[str, Role] = {}
    for item in selected:
        current = best.get(item.role.account_id)
        if current is None or _priority(role_priority, item.role.role_name) > _priority(
            role_priority, current.role_name
        ):
            best[item.role.account_id] = item.role

    explicit = {name: item.role for item in selected for name in item.names}

    plan: dict[str, Role] = {}
    if easy_profiles:
        for item in selected:
            plan[f"{item.role.account_id}_{item.role.role_name}"] = item.role
        for account_id, role in best.items():
            plan[account_id] = role
            if role.account_name and role.account_name != account_id:
                plan[role.account_name] = role

    if login_account:
        target = (
            best.get(login_account)
            or next((r for r in best.values() if r.account_name == login_account), None)
            or explicit.get(login_account)
        )
        if target is None:
            logger.warning(f"loginAccount '{login_account}' matches no selected role")
        else:
            plan[DEFAULT_PROFILE] = target

    for name, role in explicit.items():
        previous = plan.get(name)
        if previous is not None and previous != role:
            logger.warning(
                f"profile '{name}' is set explicitly and replaces the generated profile for "
                f"{previous.account_id}/{previous.role_name}"
            )
        plan[name] = role

    return plan


def build_profiles(
    plan: Mapping[str, Role],
    credentials: Mapping[Role, RoleCredentials],
    *,
    source: str,
) -> dict[str, dict[str, str]]:
    """Render planned profiles into credentials-file sections.

    Profiles whose role has no credentials (because fetching them failed) are left out.

    Args:
        plan: Output of :func:`plan_profiles`.
        credentials: Credentials per role.
        source: Identifies the provider instance (``identity-center:<domain>`` or
            ``saml:<host>``), so a later run only prunes sections it wrote itself.

    Returns:
        Section name to key/value pairs.
    """
    sections: dict[str, dict[str, str]] = {}
    for name, role in plan.items():
        creds = credentials.get(role)
        if creds is None:
            continue
        section = {
            "aws_access_key_id": creds.access_key_id,
            "aws_secret_access_key": creds.secret_access_key,
            "aws_session_token": creds.session_token,
            "x_security_token_expires": creds.expiration.astimezone(UTC).isoformat(),
        }
        if creds.principal_arn:
            section["x_principal_arn"] = creds.principal_arn
        section["x_account_id"] = role.account_id
        if role.account_name:
            section["x_account_name"] = role.account_name
        section["x_role_name"] = role.role_name
        section["x_managed_by"] = MANAGED_BY
        section["x_source"] = source
        sections[name] = section
    return sections
