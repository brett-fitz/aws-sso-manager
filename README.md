# aws-sso-manager

[![License](https://img.shields.io/github/license/brett-fitz/aws-sso-manager?style=flat-square)](https://github.com/brett-fitz/aws-sso-manager/blob/main/LICENSE)
[![Issues](https://img.shields.io/github/issues/brett-fitz/aws-sso-manager?style=flat-square)](https://github.com/brett-fitz/aws-sso-manager/issues)

Simple AWS SSO Manager that makes authenticating between multiple profiles and roles a breeze. 

## Overview

`aws-sso-manager` is a simple cli to manage auth for aws sso accounts and roles. 

## Setup

```shell
pip3 install awsssomanager
or
poetry add awsssomanager
```

### Config file

Create a config file. You can create a config file for each `ssoDomain`.

```yaml
default:
    loginAccount: '1234567890'
    ssoDomain: 'myssodomain'
    region: 'us-east-1'

role_priority:
  - "ViewOnlyAccess"
  - "PowerUserAccess"
  - "PowerUserPlus"
  - "AdministratorAccess"
```

### Configure ssoDomain

```shell
$ aws-sso-manager configure /path/to/config/file
```

All done!

## Daily Operation

Whenever your tokens expire, you will need to run the command:

```shell
$ aws-sso-manager login
```

## Easy Profiles

Profiles are automatically generated in the following formats and can be used directly after credentials are acquired:

```
<account_id>_<role_name>
<account_id>
<account_name>
```

### Usage

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

## Help :construction_worker:

#### Join us in discussions
I use GitHub Discussions to talk about all sorts of topics related to this repo.

#### Open an issue
First, check out the [existing issues](https://github.com/brett-fitz/aws-sso-manager/issues). If you spot
something new, open an issue. We'll use the issue to have a conversation about the problem you want
to fix, and I'll try to get to it as soon as I can.

