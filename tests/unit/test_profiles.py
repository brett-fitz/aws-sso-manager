"""Profile selection, naming, and section rendering."""

import logging

import pytest

from awsssomanager.models import Role
from awsssomanager.profiles import (
    MANAGED_BY,
    ProfileRule,
    ProfileSelection,
    ProfileSelectionError,
    SelectedRole,
    build_profiles,
    plan_profiles,
    select_roles,
)
from tests.unit.factories import DEV, LOGS, PROD, make_creds, okta_role


READONLY = okta_role(DEV, "Okta-ReadOnly-dev", "dev")
DEVELOPER = okta_role(DEV, "Okta-Developer-dev", "dev")
DEV_BREAKGLASS = okta_role(DEV, "Okta-BreakGlass-dev", "dev")
PROD_EDITOR = okta_role(PROD, "Okta-SecretsEditor-prod", "prod")
PROD_BREAKGLASS = okta_role(PROD, "Okta-BreakGlass-prod", "prod")
LOGS_READONLY = okta_role(LOGS, "Okta-ReadOnly-logs", "logs")
LOGS_MANAGER = okta_role(
    LOGS, "Okta-DataManager-logs", "logs"
)

ALL_ROLES = [
    READONLY,
    DEVELOPER,
    DEV_BREAKGLASS,
    PROD_EDITOR,
    PROD_BREAKGLASS,
    LOGS_READONLY,
    LOGS_MANAGER,
]


def selection(**data: object) -> ProfileSelection:
    return ProfileSelection.from_config(data)


def selected_roles(result: list[SelectedRole]) -> list[Role]:
    return [item.role for item in result]


class TestSelectRoles:
    def test_no_profiles_block_selects_every_role(self) -> None:
        result = select_roles(ALL_ROLES, ProfileSelection.from_config(None))
        assert selected_roles(result) == ALL_ROLES
        assert all(item.names == () for item in result)

    def test_exclude_only_drops_matches(self) -> None:
        result = select_roles(ALL_ROLES, selection(exclude=[{"role": "*BreakGlass*"}]))
        assert DEV_BREAKGLASS not in selected_roles(result)
        assert PROD_BREAKGLASS not in selected_roles(result)
        assert len(result) == len(ALL_ROLES) - 2

    def test_exclude_wins_over_include(self) -> None:
        result = select_roles(
            ALL_ROLES,
            selection(include=[{"account": "dev"}], exclude=[{"role": "*breakglass*"}]),
        )
        assert selected_roles(result) == [READONLY, DEVELOPER]

    def test_include_keeps_discovery_order(self) -> None:
        result = select_roles(
            ALL_ROLES,
            selection(include=[{"role": "Okta-ReadOnly-*"}, {"role": "Okta-Developer*"}]),
        )
        assert selected_roles(result) == [READONLY, DEVELOPER, LOGS_READONLY]

    def test_account_matches_id_or_alias(self) -> None:
        by_id = select_roles(ALL_ROLES, selection(include=[{"account": PROD}]))
        by_alias = select_roles(ALL_ROLES, selection(include=[{"account": "pro*"}]))
        assert selected_roles(by_id) == selected_roles(by_alias)
        assert selected_roles(by_id) == [PROD_EDITOR, PROD_BREAKGLASS]

    def test_unquoted_account_id_is_coerced(self) -> None:
        result = select_roles(ALL_ROLES, selection(include=[{"account": int(LOGS)}]))
        assert selected_roles(result) == [LOGS_READONLY, LOGS_MANAGER]

    def test_globs_are_case_insensitive(self) -> None:
        result = select_roles(ALL_ROLES, selection(include=[{"role": "okta-readonly-DEV"}]))
        assert selected_roles(result) == [READONLY]

    def test_named_rules_attach_names(self) -> None:
        result = select_roles(
            ALL_ROLES,
            selection(
                include=[
                    {"role": "Okta-ReadOnly-dev", "name": "dev"},
                    {"role": "Okta-ReadOnly-dev", "name": "ro"},
                    {"role": "Okta-Developer-dev", "name": "developer"},
                ]
            ),
        )
        assert result == [
            SelectedRole(READONLY, ("dev", "ro")),
            SelectedRole(DEVELOPER, ("developer",)),
        ]

    def test_named_rule_matching_many_roles_raises(self) -> None:
        with pytest.raises(ProfileSelectionError, match="matches 2 roles"):
            select_roles(ALL_ROLES, selection(include=[{"account": LOGS, "name": "logs"}]))

    def test_named_rule_ambiguity_ignores_excluded_roles(self) -> None:
        result = select_roles(
            ALL_ROLES,
            selection(
                include=[{"account": PROD, "name": "prod"}],
                exclude=[{"role": "*BreakGlass*"}],
            ),
        )
        assert result == [SelectedRole(PROD_EDITOR, ("prod",))]

    def test_same_name_on_two_roles_raises(self) -> None:
        with pytest.raises(ProfileSelectionError, match="claimed by both"):
            select_roles(
                ALL_ROLES,
                selection(
                    include=[
                        {"role": "Okta-ReadOnly-dev", "name": "dup"},
                        {"role": "Okta-Developer-dev", "name": "dup"},
                    ]
                ),
            )

    def test_named_rule_matching_nothing_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            result = select_roles(
                ALL_ROLES, selection(include=[{"role": "Okta-Gone", "name": "gone"}])
            )
        assert result == []
        assert "profile 'gone'" in caplog.text

    def test_empty_include_selects_nothing(self) -> None:
        assert select_roles(ALL_ROLES, selection(include=[])) == []

    def test_rule_needs_account_or_role(self) -> None:
        with pytest.raises(ProfileSelectionError, match="at least one"):
            ProfileRule.from_config({"name": "everything"})


class TestPlanProfiles:
    def test_easy_profiles_cover_every_selected_role(self) -> None:
        plan = plan_profiles([SelectedRole(READONLY), SelectedRole(PROD_EDITOR)])
        assert plan == {
            f"{DEV}_Okta-ReadOnly-dev": READONLY,
            f"{PROD}_Okta-SecretsEditor-prod": PROD_EDITOR,
            DEV: READONLY,
            "dev": READONLY,
            PROD: PROD_EDITOR,
            "prod": PROD_EDITOR,
        }

    def test_role_priority_picks_account_profile(self) -> None:
        plan = plan_profiles(
            [SelectedRole(READONLY), SelectedRole(DEVELOPER)],
            role_priority=["Okta-ReadOnly-dev", "Okta-Developer-dev"],
        )
        assert plan[DEV] == DEVELOPER
        assert plan["dev"] == DEVELOPER

    def test_unranked_roles_lose_and_ties_keep_first(self) -> None:
        ranked = plan_profiles(
            [SelectedRole(DEVELOPER), SelectedRole(READONLY)],
            role_priority=["Okta-ReadOnly-dev"],
        )
        assert ranked[DEV] == READONLY
        unranked = plan_profiles([SelectedRole(DEVELOPER), SelectedRole(READONLY)])
        assert unranked[DEV] == DEVELOPER

    def test_no_alias_profile_without_account_name(self) -> None:
        bare = okta_role(DEV, "Okta-ReadOnly-dev")
        assert set(plan_profiles([SelectedRole(bare)])) == {
            f"{DEV}_Okta-ReadOnly-dev",
            DEV,
        }

    def test_easy_profiles_off_writes_only_named(self) -> None:
        plan = plan_profiles(
            [SelectedRole(READONLY, ("dev",)), SelectedRole(LOGS_MANAGER)],
            easy_profiles=False,
        )
        assert plan == {"dev": READONLY}

    @pytest.mark.parametrize("login_account", [DEV, "dev", "ro"])
    def test_default_resolves_id_alias_or_explicit_name(self, login_account: str) -> None:
        plan = plan_profiles(
            [SelectedRole(READONLY, ("ro",)), SelectedRole(PROD_EDITOR)],
            easy_profiles=False,
            login_account=login_account,
        )
        assert plan["default"] == READONLY

    def test_unknown_login_account_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            plan = plan_profiles([SelectedRole(READONLY)], login_account="999999999999")
        assert "default" not in plan
        assert "999999999999" in caplog.text

    def test_explicit_name_overrides_generated(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING):
            plan = plan_profiles([SelectedRole(READONLY), SelectedRole(PROD_EDITOR, ("dev",))])
        assert plan["dev"] == PROD_EDITOR
        assert "replaces the generated profile" in caplog.text


class TestBuildProfiles:
    def test_renders_sections_with_metadata(self) -> None:
        creds = make_creds("2", principal_arn="arn:aws:sts::1:assumed-role/x/y")
        sections = build_profiles({"dev": READONLY}, {READONLY: creds}, source="okta:example")
        assert sections == {
            "dev": {
                "aws_access_key_id": creds.access_key_id,
                "aws_secret_access_key": "secret-2",
                "aws_session_token": "token-2",
                "x_security_token_expires": "2026-11-14T20:00:00+00:00",
                "x_principal_arn": "arn:aws:sts::1:assumed-role/x/y",
                "x_account_id": DEV,
                "x_account_name": "dev",
                "x_role_name": "Okta-ReadOnly-dev",
                "x_managed_by": MANAGED_BY,
                "x_source": "okta:example",
            }
        }

    def test_skips_roles_without_credentials(self) -> None:
        sections = build_profiles(
            {"dev": READONLY, "developer": DEVELOPER}, {READONLY: make_creds()}, source="s"
        )
        assert set(sections) == {"dev"}


def test_role_credentials_repr_hides_secrets() -> None:
    text = repr(make_creds("7"))
    assert "secret-7" not in text
    assert "token-7" not in text
