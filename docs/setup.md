# Setup

## Install

```shell
uv tool install awsssomanager          # IAM Identity Center
uv tool install 'awsssomanager[okta]'  # adds the Okta SAML provider
# or: pip install awsssomanager / pip install 'awsssomanager[okta]'
```

## Development

Clone the repo

```shell
git clone git@github.com:brett-fitz/aws-sso-manager.git
cd aws-sso-manager
```

Install dependencies with [uv](https://docs.astral.sh/uv/) and [Task](https://taskfile.dev/)

```shell
task setup        # uv sync --all-groups --all-extras
task check        # lint + format check + typecheck + tests
```

Run `aws-sso-manager`

```shell
❯ uv run aws-sso-manager
Usage: aws-sso-manager [OPTIONS] COMMAND [ARGS]...

  Manage AWS credentials for every account and role you can reach.

Options:
  -v, --verbose  Verbose logging
  -h, --help     Show this message and exit.

Commands:
  configure  Configure aws-sso-manager from CONFIG_FILE and log in.
  login      Refresh credentials using the saved configuration.
  roles      List every available role and the profiles it would get.
```
