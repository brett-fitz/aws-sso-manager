"""Browser capture helpers (the Playwright flow itself is verified manually)."""

from urllib.parse import urlencode

import pytest

from awsssomanager.okta.browser import _launch_hint, extract_saml_response
from awsssomanager.okta.saml import AWS_SAML_ENDPOINT_RE


def test_extracts_saml_response_from_form_body() -> None:
    value = "PHNhbWw+abc+/def=="  # '+' and '/' must survive form decoding
    body = urlencode({"SAMLResponse": value, "RelayState": ""})
    assert extract_saml_response(body) == value


@pytest.mark.parametrize("body", [None, "", "RelayState=x", "SAMLResponse="])
def test_missing_saml_response(body: str | None) -> None:
    assert extract_saml_response(body) is None


@pytest.mark.parametrize(
    "url",
    [
        "https://signin.aws.amazon.com/saml",
        "https://us-east-1.signin.aws.amazon.com/saml",
        "https://signin.aws.amazon.com/saml?SAMLRequest=x",
    ],
)
def test_acs_pattern_matches_aws_sign_in(url: str) -> None:
    assert AWS_SAML_ENDPOINT_RE.match(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://signin.aws.amazon.com/saml",
        "https://signin.aws.amazon.com.evil.example/saml",
        "https://evil.example/signin.aws.amazon.com/saml",
        "https://evilsignin.aws.amazon.com/saml",
        "https://signin.aws.amazon.com/samlx",
    ],
)
def test_acs_pattern_rejects_lookalikes(url: str) -> None:
    assert not AWS_SAML_ENDPOINT_RE.match(url)


def test_launch_hint_suggests_bundled_chromium() -> None:
    assert "okta.browser: chromium" in _launch_hint("chrome", RuntimeError("not found"))
    assert "okta.browser" not in _launch_hint("chromium", RuntimeError("not found"))
