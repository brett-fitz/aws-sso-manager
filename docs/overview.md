# Overview

`aws-sso-manager` is a CLI that writes short-lived credentials into `~/.aws/credentials` for
every AWS account and role you choose, from one sign-in.

## Providers

| Provider | Use it when | How it signs in |
|---|---|---|
| `sso` (default) | Your org uses **AWS IAM Identity Center** (`<domain>.awsapps.com/start`) | Device authorization in your browser |
| `okta` | Your org uses Okta's **AWS Account Federation** app: SAML straight into IAM roles, the setup saml2aws targets | Okta sign-in in a browser, with any MFA factor |

!!! question "Which one do I have?"
    Look at the Okta link you use for AWS (or the `url` in `~/.saml2aws`). A path containing
    `/home/amazon_aws/` is the AWS Account Federation app, so use `okta`. A
    `*.awsapps.com/start` portal is IAM Identity Center, so use `sso`. Assumed-role ARNs tell you
    too: Identity Center roles are named `AWSReservedSSO_*`.

With `okta`, one sign-in returns a SAML assertion listing every role you are assigned.
aws-sso-manager exchanges that single assertion for credentials on every selected role (with
`sts:AssumeRoleWithSAML`) while it is still valid. You don't need a separate login per profile.

## Configure

If you haven't already, head over to the [setup page](setup.md) to install `aws-sso-manager`.
The Okta provider needs the extra: `pip install 'awsssomanager[okta]'`.

### IAM Identity Center config

```yaml
ssoDomain: 'myssodomain'       # Your aws sso domain (<sso domain>.awsapps.com)
region: 'us-east-1'            # The aws region where your aws sso is configured.

default:
  loginAccount: '1234567890'   # The default account you want mapped to the profile: default

role_priority:                 # Role priority from low to high
  - "ViewOnlyAccess"
  - "PowerUserAccess"
  - "PowerUserPlus"
  - "AdministratorAccess"
```

!!! warning "ssoDomain Region"
    The region here is not the region you want to access resources in. It is the **region
    where your ssoDomain is configured.** The wrong region produces an "Invalid Grant" error.

### Okta config

```yaml
provider: okta
okta:
  appUrl: 'https://example.okta.com/home/amazon_aws/0oaXXXXXXXXXXXXXXX/272'
  sessionDuration: 3600        # optional; seconds (900-43200), capped per role by AWS
  browser: chrome              # optional: chrome | chrome-beta | msedge | chromium
  timeout: 300                 # optional: seconds allowed to finish signing in
region: us-east-1              # optional: STS region

default:
  loginAccount: dev         # account id, account alias, or a profile name

profiles:
  easyProfiles: false
  include:
    - role: Okta-ReadOnly-dev
      name: dev
    - role: Okta-Developer-dev
      name: developer
    - account: logs   # every Okta-* role in this account,
      role: 'Okta-*'             # with generated names
  exclude:
    - role: '*BreakGlass*'
```

`sessionDuration` falls back to the assertion's `SessionDuration` attribute, then to one hour.
If a role's maximum session is shorter than requested, that role is retried at one hour.

!!! note "Browser"
    The default `chrome` uses your installed Google Chrome, with a dedicated profile under
    `~/.aws/aws-sso-manager/browser/` (user-only permissions). It keeps your Okta session, so
    repeat logins are usually zero-click. To use Playwright's bundled browser instead, set
    `browser: chromium` and run `playwright install chromium`.

### Choosing which roles get profiles

The `profiles` block is optional and works with both providers. Selection happens before any
credentials are requested, so excluded roles, such as break-glass roles, are never assumed.

- **`include`** selects roles. If you omit it, every role is selected (the original behaviour).
  An empty list selects nothing.
- **`exclude`** drops roles. Exclusion always wins over inclusion.
- **Rule fields:**
    - `account` is matched against the account id *or* its alias.
    - `role` is matched against the role name.
    - Both are case-insensitive globs (`*`, `?`, `[...]`). A rule needs at least one of them.
- **`name`** on an include rule gives that role an explicit profile name. If the rule matches
  more than one role, that is an error. If two roles claim the same name, that is also an error.
- **`easyProfiles`** (default `true`) also writes the [easy profiles](#easy-profiles) for every
  selected role. Set it to `false` to write only the named profiles (and `default`).

!!! tip
    Quote account ids (`'012345678901'`) so YAML keeps any leading zeros.

### Run configure

```shell
$ aws-sso-manager configure ~/workspace/aws-sso-manager.yml
```

The config is saved to `~/.aws/aws-sso-manager.yml`. Later runs read that copy, so edit it (or
re-run `configure -R`) to change your selection.

- **sso:** your browser opens the AWS device authorization page.
- **okta:** your browser opens Okta. Sign in as usual. The window closes on its own once the
  assertion is captured, and no AWS console session is opened.

## Easy Profiles

Profiles are generated in the following formats and can be used as soon as credentials are
acquired:

```
<account_id>_<role_name>
<account_id>
<account_name>
```

!!! note
    The highest-priority role (per `role_priority`) for each account backs `<account_id>` and
    `<account_name>`. To reach a lower role, use `<account_id>_<role_name>`. Okta account names
    come from the AWS sign-in page. If that lookup fails, only account-id profiles are written.

## Daily Operation

```shell
$ aws-sso-manager roles   # every role you can reach, whether it is selected, its profile names
$ aws-sso-manager login   # refresh credentials
```

`roles` signs in but writes no credentials, so you can tune `include`/`exclude` safely.

### What gets written

Every section aws-sso-manager writes carries `x_managed_by = aws-sso-manager` and an `x_source`.
It also carries `x_security_token_expires` and, for Okta, `x_principal_arn`, which are the same
keys saml2aws writes. On each login:

- sections for selected roles are replaced;
- sections this source wrote earlier, for roles no longer selected, are removed;
- sections written by anything else (saml2aws, hand-written profiles) are left alone.

If any role fails to assume, nothing is removed, so the previous credentials keep working.

## Usage

```shell
$ AWS_PROFILE=<profile_name> aws s3 ls
```

**Example**

```shell
1234567890 = dev

$ AWS_PROFILE=dev aws s3 ls
$ AWS_PROFILE=1234567890 aws s3 ls
$ AWS_PROFILE=1234567890_AdministratorAccess aws s3 ls
```

### Python

```python
AWS_AIOSESSION = AioSession(profile="dev")
AWS_SESSION = Session(profile_name="dev")
```
