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
from tests.unit.factories import FORENSICS, SECLOG, SECOPS, make_creds, okta_role


READONLY = okta_role(SECOPS, "Okta-ReadOnly-secops", "secops")
TIAGENT = okta_role(SECOPS, "Okta-TIAgentDeveloper-secops", "secops")
SECOPS_BREAKGLASS = okta_role(SECOPS, "Okta-BreakGlass-secops", "secops")
FORENSICS_EDITOR = okta_role(FORENSICS, "Okta-SecretsValueEditor-forensics", "forensics")
FORENSICS_BREAKGLASS = okta_role(FORENSICS, "Okta-BreakGlass-forensics", "forensics")
SECLOG_READONLY = okta_role(SECLOG, "Okta-ReadOnly-seclog-pipeline", "seclog-pipeline")
SECLOG_MANAGER = okta_role(
    SECLOG, "Okta-SecurityDatalakeManager-seclog-pipeline", "seclog-pipeline"
)

ALL_ROLES = [
    READONLY,
    TIAGENT,
    SECOPS_BREAKGLASS,
    FORENSICS_EDITOR,
    FORENSICS_BREAKGLASS,
    SECLOG_READONLY,
    SECLOG_MANAGER,
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
        assert SECOPS_BREAKGLASS not in selected_roles(result)
        assert FORENSICS_BREAKGLASS not in selected_roles(result)
        assert len(result) == len(ALL_ROLES) - 2

    def test_exclude_wins_over_include(self) -> None:
        result = select_roles(
            ALL_ROLES,
            selection(include=[{"account": "secops"}], exclude=[{"role": "*breakglass*"}]),
        )
        assert selected_roles(result) == [READONLY, TIAGENT]

    def test_include_keeps_discovery_order(self) -> None:
        result = select_roles(
            ALL_ROLES,
            selection(include=[{"role": "Okta-ReadOnly-*"}, {"role": "Okta-TIAgent*"}]),
        )
        assert selected_roles(result) == [READONLY, TIAGENT, SECLOG_READONLY]

    def test_account_matches_id_or_alias(self) -> None:
        by_id = select_roles(ALL_ROLES, selection(include=[{"account": FORENSICS}]))
        by_alias = select_roles(ALL_ROLES, selection(include=[{"account": "forens*"}]))
        assert selected_roles(by_id) == selected_roles(by_alias)
        assert selected_roles(by_id) == [FORENSICS_EDITOR, FORENSICS_BREAKGLASS]

    def test_unquoted_account_id_is_coerced(self) -> None:
        result = select_roles(ALL_ROLES, selection(include=[{"account": int(SECLOG)}]))
        assert selected_roles(result) == [SECLOG_READONLY, SECLOG_MANAGER]

    def test_globs_are_case_insensitive(self) -> None:
        result = select_roles(ALL_ROLES, selection(include=[{"role": "okta-readonly-SECOPS"}]))
        assert selected_roles(result) == [READONLY]

    def test_named_rules_attach_names(self) -> None:
        result = select_roles(
            ALL_ROLES,
            selection(
                include=[
                    {"role": "Okta-ReadOnly-secops", "name": "secops"},
                    {"role": "Okta-ReadOnly-secops", "name": "ro"},
                    {"role": "Okta-TIAgentDeveloper-secops", "name": "tiagent"},
                ]
            ),
        )
        assert result == [
            SelectedRole(READONLY, ("secops", "ro")),
            SelectedRole(TIAGENT, ("tiagent",)),
        ]

    def test_named_rule_matching_many_roles_raises(self) -> None:
        with pytest.raises(ProfileSelectionError, match="matches 2 roles"):
            select_roles(ALL_ROLES, selection(include=[{"account": SECLOG, "name": "seclog"}]))

    def test_named_rule_ambiguity_ignores_excluded_roles(self) -> None:
        result = select_roles(
            ALL_ROLES,
            selection(
                include=[{"account": FORENSICS, "name": "forensics"}],
                exclude=[{"role": "*BreakGlass*"}],
            ),
        )
        assert result == [SelectedRole(FORENSICS_EDITOR, ("forensics",))]

    def test_same_name_on_two_roles_raises(self) -> None:
        with pytest.raises(ProfileSelectionError, match="claimed by both"):
            select_roles(
                ALL_ROLES,
                selection(
                    include=[
                        {"role": "Okta-ReadOnly-secops", "name": "dup"},
                        {"role": "Okta-TIAgentDeveloper-secops", "name": "dup"},
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
        plan = plan_profiles([SelectedRole(READONLY), SelectedRole(FORENSICS_EDITOR)])
        assert plan == {
            f"{SECOPS}_Okta-ReadOnly-secops": READONLY,
            f"{FORENSICS}_Okta-SecretsValueEditor-forensics": FORENSICS_EDITOR,
            SECOPS: READONLY,
            "secops": READONLY,
            FORENSICS: FORENSICS_EDITOR,
            "forensics": FORENSICS_EDITOR,
        }

    def test_role_priority_picks_account_profile(self) -> None:
        plan = plan_profiles(
            [SelectedRole(READONLY), SelectedRole(TIAGENT)],
            role_priority=["Okta-ReadOnly-secops", "Okta-TIAgentDeveloper-secops"],
        )
        assert plan[SECOPS] == TIAGENT
        assert plan["secops"] == TIAGENT

    def test_unranked_roles_lose_and_ties_keep_first(self) -> None:
        ranked = plan_profiles(
            [SelectedRole(TIAGENT), SelectedRole(READONLY)],
            role_priority=["Okta-ReadOnly-secops"],
        )
        assert ranked[SECOPS] == READONLY
        unranked = plan_profiles([SelectedRole(TIAGENT), SelectedRole(READONLY)])
        assert unranked[SECOPS] == TIAGENT

    def test_no_alias_profile_without_account_name(self) -> None:
        bare = okta_role(SECOPS, "Okta-ReadOnly-secops")
        assert set(plan_profiles([SelectedRole(bare)])) == {
            f"{SECOPS}_Okta-ReadOnly-secops",
            SECOPS,
        }

    def test_easy_profiles_off_writes_only_named(self) -> None:
        plan = plan_profiles(
            [SelectedRole(READONLY, ("secops",)), SelectedRole(SECLOG_MANAGER)],
            easy_profiles=False,
        )
        assert plan == {"secops": READONLY}

    @pytest.mark.parametrize("login_account", [SECOPS, "secops", "ro"])
    def test_default_resolves_id_alias_or_explicit_name(self, login_account: str) -> None:
        plan = plan_profiles(
            [SelectedRole(READONLY, ("ro",)), SelectedRole(FORENSICS_EDITOR)],
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
            plan = plan_profiles(
                [SelectedRole(READONLY), SelectedRole(FORENSICS_EDITOR, ("secops",))]
            )
        assert plan["secops"] == FORENSICS_EDITOR
        assert "replaces the generated profile" in caplog.text


class TestBuildProfiles:
    def test_renders_sections_with_metadata(self) -> None:
        creds = make_creds("2", principal_arn="arn:aws:sts::1:assumed-role/x/y")
        sections = build_profiles({"secops": READONLY}, {READONLY: creds}, source="okta:example")
        assert sections == {
            "secops": {
                "aws_access_key_id": creds.access_key_id,
                "aws_secret_access_key": "secret-2",
                "aws_session_token": "token-2",
                "x_security_token_expires": "2026-11-14T20:00:00+00:00",
                "x_principal_arn": "arn:aws:sts::1:assumed-role/x/y",
                "x_account_id": SECOPS,
                "x_account_name": "secops",
                "x_role_name": "Okta-ReadOnly-secops",
                "x_managed_by": MANAGED_BY,
                "x_source": "okta:example",
            }
        }

    def test_skips_roles_without_credentials(self) -> None:
        sections = build_profiles(
            {"secops": READONLY, "tiagent": TIAGENT}, {READONLY: make_creds()}, source="s"
        )
        assert set(sections) == {"secops"}


def test_role_credentials_repr_hides_secrets() -> None:
    text = repr(make_creds("7"))
    assert "secret-7" not in text
    assert "token-7" not in text
