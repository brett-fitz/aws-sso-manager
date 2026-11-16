# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres
to [Semantic Versioning](https://semver.org/). Releases before this file existed are described in
the [GitHub releases](https://github.com/brett-fitz/aws-sso-manager/releases).

## [Unreleased]

### Added

- `provider` setting: `identity-center` (the default, and the existing behaviour) or `saml`.
- SAML provider (`provider: saml`) for any identity provider that federates into IAM roles
  over SAML 2.0: Okta's AWS Account Federation app, Microsoft Entra ID, Google Workspace, ADFS,
  Keycloak, and so on (the setup saml2aws targets). One browser sign-in works with any MFA
  factor and gets credentials for every selected role from a single SAML assertion. Install with
  `pip install 'awsssomanager[saml]'`.
- `profiles` config block, for both providers. `include` and `exclude` rules use globs on the
  account (id or alias) and the role name. An include rule can set an explicit profile `name`.
  `easyProfiles: false` writes only the named profiles. Excluded roles are never requested.
- `aws-sso-manager roles` lists every role you can reach, whether it is selected, and the
  profile names it would get, without writing any credentials.
- `default.loginAccount` also accepts an account alias or an explicit profile name.

### Changed

- Credentials sections now carry `x_managed_by`, `x_source`, `x_account_id`,
  `x_account_name`, `x_role_name` and `x_security_token_expires` (plus `x_principal_arn` for
  SAML). These replace the `aws_sso_*` keys.
- Profiles that aws-sso-manager wrote earlier but no longer selects are removed on the next
  login. Sections written by other tools are never touched. Nothing is removed if any role fails.
- `~/.aws/credentials` is written atomically with `0600` permissions, and through a symlink
  if it is one. `~/.aws/aws-sso-manager.yml`, which holds device secrets, is now written `0600`.
- The config schema is validated strictly: unknown keys are reported instead of ignored.
  `ssoDomain`, `default` and `role_priority` are now optional where the provider doesn't need
  them.
- Requires Python 3.11 or newer (previously 3.9).
- Built and managed with uv and hatchling instead of Poetry. Install with
  `pip install awsssomanager` or `uv tool install awsssomanager`.
- Linting and formatting moved from pylint to ruff, with ty for type checking.
- Supports Python 3.15.
- Raised minimum dependency versions to current releases (boto3 1.44, click 8.5, pyyaml 6.0.3,
  yamale 6.1).

### Fixed

- One unit test wrote fixture credentials into the real `~/.aws/credentials`. Every test now
  runs against a temporary `~/.aws`, and a guard test fails if any module still points at the
  real one. If you ran the tests, delete any sections tagged
  `x_source = okta:example.okta.com`.
- CI never ran for pull requests that only changed package code, because the path filter pointed
  at `aws-sso-manager/**` instead of `awsssomanager/**`.
- The docs build walked the whole repository, including `.venv`, when generating API reference
  pages. It now documents only the `awsssomanager` package.
- The `<account_id>` and `<account_name>` profiles could pick the wrong role. Role-priority
  resolution ran in threads that shared a dict, and its errors were silently discarded.
- Identity Center role credentials were fetched with a new boto3 client per thread, and creating
  boto3 clients concurrently isn't thread-safe. One shared client is now used.

### Removed

- Internal helpers `compare_roles`, `update_credentials_for_role`, and
  `awsssomanager.sso.load_credentials` / `save_credentials`. Their replacements are in
  `awsssomanager.profiles` and `awsssomanager.credentials_file`.
