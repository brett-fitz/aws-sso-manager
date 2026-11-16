"""Look up account aliases for the roles in a SAML assertion.

The assertion carries only role ARNs. AWS's SAML sign-in page, which a browser would show as the
role chooser, renders each account as ``Account: <alias> (<id>)``. Posting the same assertion
there is how saml2aws names accounts, and needs no IAM permissions. This lookup is best effort:
on any failure, profiles simply fall back to account ids.
"""

from html.parser import HTMLParser
from importlib.metadata import PackageNotFoundError, version
import logging
import re

import httpx

from awsssomanager.saml.assertion import AWS_SAML_ENDPOINT, AWS_SAML_ENDPOINT_RE, SamlAssertion


__all__ = ["fetch_account_aliases", "parse_account_aliases"]

logger = logging.getLogger(__name__)

_ACCOUNT_NAME_CLASS = "saml-account-name"
_ACCOUNT_LABEL_RE = re.compile(r"Account:\s*(?P<alias>.+?)\s*\((?P<id>\d{12})\)")
_TIMEOUT_SECONDS = 15.0


def _user_agent() -> str:
    try:
        return f"aws-sso-manager/{version('awsssomanager')}"
    except PackageNotFoundError:
        return "aws-sso-manager"


class _AccountNameParser(HTMLParser):
    """Collect the text of every ``<div class="saml-account-name">``."""

    def __init__(self) -> None:
        super().__init__()
        self.labels: list[str] = []
        self._depth = 0
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._depth:
            self._depth += 1
            return
        classes = (dict(attrs).get("class") or "").split()
        if _ACCOUNT_NAME_CLASS in classes:
            self._depth = 1
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        if not self._depth:
            return
        self._depth -= 1
        if not self._depth:
            self.labels.append(" ".join("".join(self._buffer).split()))

    def handle_data(self, data: str) -> None:
        if self._depth:
            self._buffer.append(data)


def parse_account_aliases(html: str) -> dict[str, str]:
    """Extract ``{account_id: alias}`` from the AWS SAML role-chooser page.

    Accounts without an alias render as ``Account: <id>`` and are omitted.

    Args:
        html: The sign-in page body.

    Returns:
        Account id to alias.
    """
    parser = _AccountNameParser()
    parser.feed(html)
    parser.close()
    aliases: dict[str, str] = {}
    for label in parser.labels:
        match = _ACCOUNT_LABEL_RE.search(label)
        if match:
            aliases[match["id"]] = match["alias"]
    return aliases


def fetch_account_aliases(
    assertion: SamlAssertion, *, client: httpx.Client | None = None
) -> dict[str, str]:
    """Fetch account aliases by posting the assertion to the AWS SAML sign-in page.

    The assertion is only ever sent to an AWS sign-in endpoint: its own ``Destination`` when
    that is one, otherwise the global endpoint.

    Args:
        assertion: The parsed SAMLResponse.
        client: Optional HTTP client (tests inject one).

    Returns:
        Account id to alias; empty when the lookup fails.
    """
    destination = assertion.destination
    url = (
        destination
        if destination and AWS_SAML_ENDPOINT_RE.match(destination)
        else AWS_SAML_ENDPOINT
    )
    try:
        if client is None:
            with httpx.Client(timeout=_TIMEOUT_SECONDS) as owned:
                response = _post(owned, url, assertion)
        else:
            response = _post(client, url, assertion)
    except httpx.HTTPError as error:
        logger.warning(f"could not look up account aliases ({error}); using account ids")
        return {}

    if response.status_code != httpx.codes.OK:
        logger.warning(f"AWS sign-in page returned HTTP {response.status_code}; using account ids")
        return {}
    aliases = parse_account_aliases(response.text)
    logger.debug(f"resolved {len(aliases)} account alias(es)")
    return aliases


def _post(client: httpx.Client, url: str, assertion: SamlAssertion) -> httpx.Response:
    return client.post(
        url,
        data={"SAMLResponse": assertion.raw, "RelayState": ""},
        headers={"User-Agent": _user_agent()},
        follow_redirects=False,
    )
