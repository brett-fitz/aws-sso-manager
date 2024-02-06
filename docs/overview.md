# Overview

`aws-sso-manager` is a simple CLI that makes authenticating between multiple profiles, roles, and SSO domains a breeze.

## Configure

If you haven't already, please head over to the [setup page](setup.md) to install `aws-sso-manager`.

After installation, you will need to configure your SSO Domains with a config file for each one. 

### Config File

The config file is important for registering and authorizing your device as well as defining
the custom role priority you prefer to be applied to each profile.

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

In this example, the ssoDomain is `myssodomain`, it is configured in the region `us-east-1`
and the default profile will be mapped to the account `1234567890`.

!!! warning "ssoDomain Region"
    It is important to note that the region you put here is not the region you would like
    to access resources in but the **region where your ssoDomain is configured.** Failure
    to provide the correct region will produce an "Invalid Grant" error.

After writing your config file, you can now execute `aws-sso-manager configure [file]`.

```shell
$ aws-sso-manager configure ~/workspace/1234567890-aws-sso-manager.yml
```

After a few moments your default browswer should open a window/tab with the AWS device authorization user consent page for you to authenticate your device with your desired AWS SSO account.

Following this, `aws-sso-manager` will authorize your device, get credentials and generate
**easy profiles** for you to use. 

## Easy Profiles

Profiles are automatically generated in the following formats and can be used directly after credentials are acquired:

```
<account_id>_<role_name>
<account_id>
<account_name>
```

!!! note
    Based on the role priority set in your config, the highest priority role found will be
    set to the profiles: `<account_id>` and `<account_name>`. However, if you need to access
    a lower role for an account, you can do so by directly specifying `<account_id>_<role_name>`. You can view all the generated profiles at `~/.aws/credentials` for reference.

## Daily Operation

Every time your credentials expire, depending on your Admin's policy its typically < 24hrs,
you will need to re-authorize your device to get credentials. Simply run the command:

```shell
$ aws-sso-manager login
```


## Usage

```shell
$ AWS_PROFILE=<proile_name> aws s3 ls
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
AWS_AIOSESSION = AioSession(profile='dev')
AWS_SESSION = Session(profile_name='dev')
```
