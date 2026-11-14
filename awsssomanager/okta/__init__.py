"""Okta SAML federation (the Okta "AWS Account Federation" app) into IAM roles.

Needs the ``okta`` extra: ``pip install 'awsssomanager[okta]'``.
"""

from awsssomanager.okta.browser import BrowserLoginError, capture_saml_response
from awsssomanager.okta.login import discover_roles, login
from awsssomanager.okta.saml import SamlAssertion, SamlError, parse_saml_response


__all__ = [
    "BrowserLoginError",
    "SamlAssertion",
    "SamlError",
    "capture_saml_response",
    "discover_roles",
    "login",
    "parse_saml_response",
]
