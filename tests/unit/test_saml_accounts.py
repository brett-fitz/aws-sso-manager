"""Account alias lookup via the AWS SAML sign-in page."""

from urllib.parse import parse_qs

import httpx
import respx

from awsssomanager.saml.accounts import fetch_account_aliases, parse_account_aliases
from awsssomanager.saml.assertion import parse_saml_response
from tests.unit.factories import AWS_SAML_URL, FORENSICS, SECOPS, make_saml_response, role_arn


# Trimmed from the real role-chooser page structure.
ROLE_CHOOSER_HTML = f"""
<form id="saml_form" name="saml_form" action="/saml" method="post">
  <fieldset>
    <div class="saml-account">
      <div onClick="expandCollapse(0);">
        <div class="saml-account-name">Account: secops ({SECOPS})</div>
      </div>
      <div class="saml-account" id="0">
        <div class="saml-role">
          <label class="saml-role-description">Okta-ReadOnly-secops</label>
        </div>
      </div>
    </div>
    <div class="saml-account">
      <div class="saml-account-name">Account:
        <span>forensics</span> ({FORENSICS})</div>
    </div>
    <div class="saml-account">
      <div class="saml-account-name">Account: 111122223333</div>
    </div>
  </fieldset>
</form>
"""


def assertion(destination: str | None = AWS_SAML_URL):
    return parse_saml_response(
        make_saml_response([role_arn(SECOPS, "Okta-ReadOnly-secops")], destination=destination)
    )


def test_parse_account_aliases() -> None:
    assert parse_account_aliases(ROLE_CHOOSER_HTML) == {SECOPS: "secops", FORENSICS: "forensics"}


@respx.mock
def test_posts_assertion_to_aws_sign_in() -> None:
    route = respx.post(AWS_SAML_URL).mock(return_value=httpx.Response(200, text=ROLE_CHOOSER_HTML))
    parsed = assertion()

    assert fetch_account_aliases(parsed) == {SECOPS: "secops", FORENSICS: "forensics"}

    form = parse_qs(route.calls.last.request.content.decode())
    assert form["SAMLResponse"] == [parsed.raw]


@respx.mock
def test_uses_regional_destination() -> None:
    regional = "https://us-west-2.signin.aws.amazon.com/saml"
    route = respx.post(regional).mock(return_value=httpx.Response(200, text=ROLE_CHOOSER_HTML))
    assert fetch_account_aliases(assertion(destination=regional))
    assert route.called


@respx.mock
def test_never_posts_to_a_non_aws_destination() -> None:
    route = respx.post(AWS_SAML_URL).mock(return_value=httpx.Response(200, text=ROLE_CHOOSER_HTML))
    fetch_account_aliases(assertion(destination="https://evil.example.com/saml"))
    assert route.called


@respx.mock
def test_http_error_falls_back_to_empty() -> None:
    respx.post(AWS_SAML_URL).mock(side_effect=httpx.ConnectError("offline"))
    assert fetch_account_aliases(assertion()) == {}


@respx.mock
def test_non_200_falls_back_to_empty() -> None:
    respx.post(AWS_SAML_URL).mock(return_value=httpx.Response(302, headers={"Location": "/"}))
    assert fetch_account_aliases(assertion()) == {}
