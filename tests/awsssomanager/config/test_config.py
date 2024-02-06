"""awsssomanager.config.Config tests."""
from pathlib import Path

from awsssomanager.config import AWSSSOManagerConfig


def test_create_aws_dir():
    """Test create_aws_dir."""
    AWSSSOManagerConfig.create_aws_dir()
    assert AWSSSOManagerConfig.check_aws_dir_exists()


def test_from_config():
    """Test from_config."""
    config = AWSSSOManagerConfig.from_config(
        config_file=Path(__file__).parent.parent.parent / "data" / ".aws-sso-manager.yml")
    assert config.sso_domain == "test"
    assert config.login_account == "1234567890"
    assert config.region == "us-east-1"
