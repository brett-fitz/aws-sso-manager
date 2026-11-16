"""SAML 2.0 federation into IAM roles, with any identity provider.

Works with any IdP whose AWS app posts a SAMLResponse to the AWS sign-in endpoint: Okta's
"AWS Account Federation" app, Microsoft Entra ID, Google Workspace, OneLogin, JumpCloud, Ping,
ADFS, Keycloak, and so on.

Needs the ``saml`` extra: ``pip install 'awsssomanager[saml]'``.
"""

from awsssomanager.saml.assertion import SamlAssertion, SamlError, parse_saml_response
from awsssomanager.saml.browser import BrowserLoginError, capture_saml_response
from awsssomanager.saml.login import discover_roles, login


__all__ = [
    "BrowserLoginError",
    "SamlAssertion",
    "SamlError",
    "capture_saml_response",
    "discover_roles",
    "login",
    "parse_saml_response",
]
