"""awsssomanager.config.Config tests."""

from awsssomanager.config import AWSSSOManagerConfig


def test_create_aws_dir():
    """Test create_aws_dir."""
    AWSSSOManagerConfig.create_aws_dir()
    assert AWSSSOManagerConfig.check_aws_dir_exists()


def test_from_config(tmp_path):
    """Test from_config."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "default:\n  accessToken: test\n  loginAccount: test\n  region: us-east-1"
    )
    config = AWSSSOManagerConfig.from_config(config_file=config_file)
    assert config.access_token == "test"
    assert config.login_account == "test"
    assert config.region == "us-east-1"
