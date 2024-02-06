# Setup

Clone the repo

```shell
git clone git@github.com:brett-fitz/aws-sso-manager.git
```

Install the aws-sso-manager package and CLI

=== "General"

    Install aws-sso-manager

    ```shell
    poetry install
    ```

=== "Select env python version"

    Set python environment

    ```shell
    poetry env use 3.11
    ```

    Install aws-sso-manager

    ```shell
    poetry install
    ```

Run `aws-sso-manager`

```shell
❯ poetry run aws-sso-manager 
Usage: aws-sso-manager [OPTIONS] COMMAND [ARGS]...

  Python CLI Core

Options:
  -v, --verbose  Verbose logging
  -h, --help     Show this message and exit.

Commands:
  configure  Configure AWS SSO Manager
  login      aws sso login
```
