# Overview

`aws-sso-manager` is a CLI that writes short-lived credentials into `~/.aws/credentials` for
every AWS account and role you choose, from one sign-in.

## Providers

Both providers are single sign-on. They differ in **how AWS accepts the sign-in**:

| `provider` | Use it when | How it signs in |
|---|---|---|
| `identity-center` (default) | Your org uses **AWS IAM Identity Center** (`<domain>.awsapps.com/start`). Roles are permission sets. | Device authorization in your browser |
| `saml` | Your identity provider (IdP) federates into **IAM roles over SAML 2.0**: Okta's AWS Account Federation app, Microsoft Entra ID, Google Workspace, OneLogin, JumpCloud, Ping, ADFS, Keycloak, and so on. This is the setup saml2aws targets. | IdP sign-in in a browser, with any MFA factor |

!!! question "Which one do I have?"
    A `*.awsapps.com/start` portal is IAM Identity Center, so use `identity-center`. This is true
    even when the portal itself signs you in through Okta or Entra ID. If your IdP's AWS tile
    takes you to AWS's "Select a role" page, or straight into the console, use `saml`.
    Assumed-role ARNs tell you too: Identity Center roles are named `AWSReservedSSO_*`.

With `saml`, one sign-in returns a SAML assertion listing every role you are assigned.
aws-sso-manager exchanges that single assertion for credentials on every selected role (with
`sts:AssumeRoleWithSAML`) while it is still valid. You don't need a separate login per profile.

## Configure

If you haven't already, head over to the [setup page](setup.md) to install `aws-sso-manager`.
The SAML provider needs the extra: `pip install 'awsssomanager[saml]'`.

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

### SAML config

```yaml
provider: saml
saml:
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

#### Finding `appUrl`

`appUrl` is the IdP-initiated sign-in link for your IdP's AWS app: the link its AWS tile opens.
It's needed because it is the only thing that says which IdP and which app to sign in to. Check
it by opening it in a browser. If you land on AWS's "Select a role" page or the console, it will
work.

| IdP | `appUrl` |
|---|---|
| Okta (AWS Account Federation) | `https://<org>.okta.com/home/amazon_aws/<app id>/272` (the `url` in `~/.saml2aws`) |
| Microsoft Entra ID | The enterprise app's *User access URL*: `https://launcher.myapps.microsoft.com/api/signin/<app id>?tenantId=<tenant id>` |
| Google Workspace | `https://accounts.google.com/o/saml2/initsso?idpid=<idp id>&spid=<sp id>&forceauthn=false` |
| ADFS | `https://<adfs host>/adfs/ls/IdpInitiatedSignOn.aspx?loginToRp=urn:amazon:webservices` |
| Keycloak | `https://<host>/realms/<realm>/protocol/saml/clients/<client url name>` |

!!! warning "Limits"
    - **Encrypted assertions** are not supported. The roles have to be readable from the assertion.
    - **Commercial AWS partition only.** `signin.aws.amazon.com` and its regional endpoints
      (`<region>.signin.aws.amazon.com`) work. GovCloud and China sign-in endpoints are not yet
      supported.

!!! note "Browser"
    The default `chrome` uses your installed Google Chrome, with a dedicated profile under
    `~/.aws/aws-sso-manager/browser/` (user-only permissions). It keeps your IdP session, so
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

- **identity-center:** your browser opens the AWS device authorization page.
- **saml:** your browser opens your IdP. Sign in as usual. The window closes on its own once the
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
    `<account_name>`. To reach a lower role, use `<account_id>_<role_name>`. With `saml`, account
    names come from the AWS sign-in page. If that lookup fails, only account-id profiles are written.

## Daily Operation

```shell
$ aws-sso-manager roles   # every role you can reach, whether it is selected, its profile names
$ aws-sso-manager login   # refresh credentials
```

`roles` signs in but writes no credentials, so you can tune `include`/`exclude` safely.

### What gets written

Every section aws-sso-manager writes carries `x_managed_by = aws-sso-manager` and an `x_source`.
It also carries `x_security_token_expires` and, for SAML, `x_principal_arn`, which are the same
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
