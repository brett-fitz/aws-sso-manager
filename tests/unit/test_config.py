"""AWSSSOManagerConfig loading and validation."""

from pathlib import Path
import stat

import pytest
from yamale import YamaleError

from awsssomanager.config import AWSSSOManagerConfig, ConfigError
from awsssomanager.profiles import ProfileRule


DATA = Path(__file__).parent / "data"


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yml"
    path.write_text(text)
    return path


def test_create_aws_dir(aws_dir: Path) -> None:
    AWSSSOManagerConfig.create_aws_dir()
    assert aws_dir.is_dir()
    assert AWSSSOManagerConfig.check_aws_dir_exists()


def test_legacy_sso_config_still_loads() -> None:
    config = AWSSSOManagerConfig.from_config(config_file=DATA / ".aws-sso-manager.yml")
    assert config.provider == "identity-center"
    assert config.sso_domain == "test"
    assert config.login_account == "1234567890"
    assert config.region == "us-east-1"
    assert config.credential_source == "identity-center:test"
    assert config.profile_selection.include is None


def test_saml_config_loads() -> None:
    config = AWSSSOManagerConfig.from_config(config_file=DATA / "saml.yml")
    assert config.provider == "saml"
    assert config.region == "us-east-1"  # STS default
    assert config.saml_browser == "chromium"
    assert config.saml_session_duration == 3600
    assert config.saml_timeout == 300
    assert config.login_account == "secops"
    assert config.role_priority == []
    assert config.credential_source == "saml:example.okta.com"
    selection = config.profile_selection
    assert selection.easy_profiles is False
    assert selection.include is not None
    assert selection.include[1] == ProfileRule(
        account="381492076076", role="Okta-SecretsValueEditor-*", name="forensics"
    )


def test_saml_requires_app_url(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"saml\.appUrl"):
        AWSSSOManagerConfig.from_config(write(tmp_path, "provider: saml\n"))


def test_saml_app_url_must_be_https(tmp_path: Path) -> None:
    path = write(tmp_path, "provider: saml\nsaml:\n  appUrl: http://example.okta.com/app\n")
    with pytest.raises(ConfigError, match="https"):
        AWSSSOManagerConfig.from_config(path)


def test_sso_requires_domain_and_region(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="ssoDomain, region"):
        AWSSSOManagerConfig.from_config(write(tmp_path, "role_priority: []\n"))


def test_unknown_keys_are_rejected(tmp_path: Path) -> None:
    path = write(tmp_path, "ssoDomain: x\nregion: us-east-1\nprofile:\n  include: []\n")
    with pytest.raises(YamaleError):
        AWSSSOManagerConfig.from_config(path)


def test_rule_without_account_or_role_is_rejected(tmp_path: Path) -> None:
    path = write(
        tmp_path, "ssoDomain: x\nregion: us-east-1\nprofiles:\n  include:\n    - name: all\n"
    )
    with pytest.raises(ConfigError, match="at least one"):
        AWSSSOManagerConfig.from_config(path)


def test_unquoted_login_account_is_coerced(tmp_path: Path) -> None:
    path = write(tmp_path, "ssoDomain: x\nregion: us-east-1\ndefault:\n  loginAccount: 1234\n")
    assert AWSSSOManagerConfig.from_config(path).login_account == "1234"


def test_write_config_is_user_only(saved_config_path: Path) -> None:
    config = AWSSSOManagerConfig.from_config(DATA / "saml.yml")
    config.write_config()
    assert stat.S_IMODE(saved_config_path.stat().st_mode) == 0o600
    assert AWSSSOManagerConfig.from_config(saved_config_path).saml_app_url == config.saml_app_url
