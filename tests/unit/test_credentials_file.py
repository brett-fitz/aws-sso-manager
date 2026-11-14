"""Writing ~/.aws/credentials without disturbing other tools."""

from pathlib import Path
import stat

from awsssomanager.credentials_file import load_credentials, write_profiles
from awsssomanager.profiles import MANAGED_BY


SOURCE = "okta:example.okta.com"

SAML2AWS_SECTION = """[saml2aws-profile]
aws_access_key_id = ASIAOTHERTOOL0000
aws_secret_access_key = other
aws_session_token = other-token
x_principal_arn = arn:aws:sts::1:assumed-role/Okta-ReadOnly/user
x_security_token_expires = 2026-11-14T13:10:32-05:00
"""


def owned(source: str = SOURCE, key: str = "AKIA") -> dict[str, str]:
    return {
        "aws_access_key_id": key,
        "aws_secret_access_key": "s",
        "aws_session_token": "t",
        "x_managed_by": MANAGED_BY,
        "x_source": source,
    }


def test_creates_file_user_only(credentials_path: Path) -> None:
    write_profiles({"secops": owned()}, source=SOURCE)
    assert stat.S_IMODE(credentials_path.stat().st_mode) == 0o600
    assert load_credentials(credentials_path)["secops"]["aws_access_key_id"] == "AKIA"


def test_preserves_unmanaged_sections_and_key_case(credentials_path: Path) -> None:
    credentials_path.parent.mkdir(parents=True)
    credentials_path.write_text(SAML2AWS_SECTION + "\n[weird]\nNote = 100% literal\n")

    pruned = write_profiles({"secops": owned()}, source=SOURCE)

    assert pruned == []
    text = credentials_path.read_text()
    assert "[saml2aws-profile]" in text
    assert "x_principal_arn = arn:aws:sts::1:assumed-role/Okta-ReadOnly/user" in text
    assert "Note = 100% literal" in text


def test_prunes_stale_sections_from_same_source(credentials_path: Path) -> None:
    write_profiles({"secops": owned(), "breakglass": owned()}, source=SOURCE)
    pruned = write_profiles({"secops": owned()}, source=SOURCE)
    assert pruned == ["breakglass"]
    assert load_credentials(credentials_path).sections() == ["secops"]


def test_never_prunes_another_source(credentials_path: Path) -> None:
    write_profiles({"sso-profile": owned(source="sso:corp")}, source="sso:corp")
    write_profiles({"secops": owned()}, source=SOURCE)
    assert sorted(load_credentials(credentials_path).sections()) == ["secops", "sso-profile"]


def test_prune_disabled_keeps_stale(credentials_path: Path) -> None:
    write_profiles({"secops": owned(), "tiagent": owned()}, source=SOURCE)
    write_profiles({"secops": owned(key="NEW")}, source=SOURCE, prune=False)
    credentials = load_credentials(credentials_path)
    assert sorted(credentials.sections()) == ["secops", "tiagent"]
    assert credentials["secops"]["aws_access_key_id"] == "NEW"


def test_rewritten_section_drops_old_keys(credentials_path: Path) -> None:
    credentials_path.parent.mkdir(parents=True)
    credentials_path.write_text(SAML2AWS_SECTION.replace("[saml2aws-profile]", "[secops]"))
    write_profiles({"secops": owned()}, source=SOURCE)
    assert "x_principal_arn" not in load_credentials(credentials_path)["secops"]


def test_legacy_sso_sections_adopted_only_when_asked(credentials_path: Path) -> None:
    credentials_path.parent.mkdir(parents=True)
    legacy = "[old]\naws_access_key_id = A\naws_sso_updated_at = Mon Jan  1 00:00:00 2024\n"
    credentials_path.write_text(legacy)

    write_profiles({"secops": owned()}, source=SOURCE)
    assert "old" in load_credentials(credentials_path).sections()

    pruned = write_profiles({"secops": owned()}, source="sso:corp", adopt_legacy_sso=True)
    assert pruned == ["old"]


def test_writes_through_symlink(tmp_path: Path, credentials_path: Path) -> None:
    real = tmp_path / "dotfiles" / "credentials"
    real.parent.mkdir()
    real.write_text(SAML2AWS_SECTION)
    credentials_path.parent.mkdir(parents=True)
    credentials_path.symlink_to(real)

    write_profiles({"secops": owned()}, source=SOURCE)

    assert credentials_path.is_symlink()
    assert "[secops]" in real.read_text()
