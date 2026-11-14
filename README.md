# aws-sso-manager

[![License](https://img.shields.io/github/license/brett-fitz/aws-sso-manager?style=flat-square)](https://github.com/brett-fitz/aws-sso-manager/blob/main/LICENSE)
[![Issues](https://img.shields.io/github/issues/brett-fitz/aws-sso-manager?style=flat-square)](https://github.com/brett-fitz/aws-sso-manager/issues)

A CLI that writes short-lived AWS credentials into `~/.aws/credentials` for every account and
role you choose, from one sign-in. It works with two kinds of single sign-on:

| Provider | Use it when | How it signs in |
|---|---|---|
| `sso` (default) | Your org uses **AWS IAM Identity Center** (`<domain>.awsapps.com/start`) | Device authorization in your browser |
| `okta` | Your org uses Okta's **AWS Account Federation** app (SAML straight into IAM roles, the setup saml2aws targets) | Okta sign-in in a browser, with any MFA |

With the `okta` provider, one Okta sign-in returns a SAML assertion listing every role you are
assigned. aws-sso-manager exchanges that one assertion for credentials on each role you
selected, so you no longer run a separate login per profile.

## Setup

```shell
uv tool install awsssomanager          # IAM Identity Center only
uv tool install 'awsssomanager[okta]'  # adds the Okta provider
# or: pip install awsssomanager / pip install 'awsssomanager[okta]'
```

The Okta provider drives Google Chrome by default. To use Playwright's bundled Chromium
instead, set `okta.browser: chromium` and run `playwright install chromium`.

### Config file: IAM Identity Center

```yaml
ssoDomain: 'myssodomain'       # <ssoDomain>.awsapps.com
region: 'us-east-1'            # region your Identity Center lives in (not where your resources are)

default:
  loginAccount: '1234567890'   # account copied into the `default` profile

role_priority:                 # lowest to highest; picks the role behind <account_id>/<account_name>
  - "ViewOnlyAccess"
  - "PowerUserAccess"
  - "AdministratorAccess"
```

### Config file: Okta

```yaml
provider: okta
okta:
  # The AWS Account Federation app's embed link (the `url` in ~/.saml2aws).
  appUrl: 'https://example.okta.com/home/amazon_aws/0oaXXXXXXXXXXXXXXX/272'
  sessionDuration: 3600        # optional; capped by each role's max session duration
  browser: chrome              # optional: chrome | chrome-beta | msedge | chromium
  timeout: 300                 # optional: seconds allowed to finish signing in
region: us-east-1              # optional STS region

default:
  loginAccount: secops         # an account id, account alias, or profile name below

profiles:
  easyProfiles: false          # write only the profiles named here
  include:
    - role: Okta-ReadOnly-secops
      name: secops
    - role: Okta-TIAgentDeveloper-secops
      name: tiagent
  exclude:
    - role: '*BreakGlass*'
```

### Choosing which roles get profiles

The optional `profiles` block works with both providers. Roles it leaves out are never
requested, not just hidden.

- **`include`**: rules that select roles. If you omit `include`, every role is selected.
- **`exclude`**: rules that drop roles. Exclusion always wins.
- **Rule fields**: each rule has `account` (matched against the account id *or* alias) and/or
  `role` (matched against the role name). Both are case-insensitive globs (`*`, `?`, `[...]`).
- **`name`**: on an include rule, names the profile. It must match exactly one role.
- **`easyProfiles`** (default `true`): also writes the generated names below for every selected
  role.

Quote account ids (`'012345678901'`) so YAML keeps leading zeros.

### Configure

```shell
$ aws-sso-manager configure /path/to/config.yml
```

Your config is saved to `~/.aws/aws-sso-manager.yml`. Edit that file, or re-run `configure -R`,
to change it later.

## Daily Operation

```shell
$ aws-sso-manager roles   # see every role you can reach and the profiles it would get
$ aws-sso-manager login   # refresh credentials
```

`roles` signs in but writes no credentials. Use it to check your include/exclude rules before
logging in.

aws-sso-manager only rewrites the sections it owns in `~/.aws/credentials`, which are marked
`x_managed_by = aws-sso-manager`. When a role stops being selected, its profile is removed on
the next login. Sections written by other tools, such as saml2aws, are never touched.

With Okta, the browser keeps a dedicated profile under `~/.aws/aws-sso-manager/browser/`. While
your Okta session is alive, `login` usually completes without a prompt.

## Easy Profiles

With `easyProfiles` on, these profiles are generated for selected roles:

```
<account_id>_<role_name>
<account_id>
<account_name>
```

### Usage

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

## Help :construction_worker:

#### Join us in discussions
I use GitHub Discussions to talk about all sorts of topics related to this repo.

#### Open an issue
First, check out the [existing issues](https://github.com/brett-fitz/aws-sso-manager/issues). If you spot
something new, open an issue. We'll use the issue to have a conversation about the problem you want
to fix, and I'll try to get to it as soon as I can.

