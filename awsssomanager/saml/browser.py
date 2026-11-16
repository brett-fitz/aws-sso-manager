"""Capture a SAMLResponse by driving a real browser through the identity provider's sign-in.

A browser handles every IdP and MFA factor (Okta FastPass, push, WebAuthn, ...) without this tool
knowing about any of them. When the IdP posts the assertion to AWS, the request is intercepted
and aborted, so the assertion is captured but no AWS console session is opened. The browser
profile is persistent and dedicated to this tool, so a live IdP session makes repeat logins
zero-click.
"""

from contextlib import suppress
import logging
from pathlib import Path
import time
from urllib.parse import parse_qs

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Request, Route, sync_playwright

from awsssomanager.constants import BROWSER_PROFILE_DIR
from awsssomanager.errors import AWSSSOManagerError
from awsssomanager.saml.assertion import AWS_SAML_ENDPOINT_RE


__all__ = [
    "DEFAULT_BROWSER",
    "BrowserLoginError",
    "capture_saml_response",
    "extract_saml_response",
]

logger = logging.getLogger(__name__)

DEFAULT_BROWSER = "chrome"
_BUNDLED_CHROMIUM = "chromium"
_POLL_MS = 250
_PROFILE_DIR_MODE = 0o700


class BrowserLoginError(AWSSSOManagerError, RuntimeError):
    """Sign-in did not produce a SAMLResponse (timeout, closed window, no browser)."""


def extract_saml_response(post_data: str | None) -> str | None:
    """Pull ``SAMLResponse`` out of a form-encoded POST body.

    Args:
        post_data: The raw ``application/x-www-form-urlencoded`` body.

    Returns:
        The base64 SAMLResponse, or None if the body has none.
    """
    if not post_data:
        return None
    values = parse_qs(post_data).get("SAMLResponse")
    return values[0] if values else None


def _prepare_profile_dir(path: Path) -> None:
    # Holds the IdP's session cookies: user-only.
    path.mkdir(mode=_PROFILE_DIR_MODE, parents=True, exist_ok=True)
    path.chmod(_PROFILE_DIR_MODE)


def _launch_hint(browser: str, error: Exception) -> str:
    hint = f"could not launch the '{browser}' browser ({error})."
    if browser != _BUNDLED_CHROMIUM:
        hint += (
            " Install it, or set `saml.browser: chromium` and run `playwright install chromium`."
        )
    else:
        hint += " Run `playwright install chromium`."
    return hint


def capture_saml_response(
    app_url: str,
    *,
    browser: str = DEFAULT_BROWSER,
    timeout: int = 300,
    user_data_dir: Path | None = None,
) -> str:  # pragma: no cover - drives a real browser; verified manually
    """Open the identity provider's AWS app and return the SAMLResponse it posts to AWS.

    Args:
        app_url: IdP-initiated sign-in link for the AWS app (for example, Okta's embed link).
        browser: Playwright channel (``chrome``, ``msedge``, ...) or ``chromium`` for the
            Playwright-bundled build.
        timeout: Seconds to wait for the user to finish signing in.
        user_data_dir: Persistent browser profile directory. Defaults to
            ``~/.aws/aws-sso-manager/browser`` (resolved at call time).

    Returns:
        The base64 SAMLResponse.

    Raises:
        BrowserLoginError: If the browser cannot start, is closed, or sign-in times out.
    """
    user_data_dir = user_data_dir or BROWSER_PROFILE_DIR
    _prepare_profile_dir(user_data_dir)
    captured: list[str] = []

    def intercept(route: Route, request: Request) -> None:
        if request.method == "POST":
            saml_response = extract_saml_response(request.post_data)
            if saml_response:
                captured.append(saml_response)
        route.abort()

    logger.info(f"Opening {browser} to sign in (waiting up to {timeout}s)...")
    with sync_playwright() as playwright:
        try:
            context = playwright.chromium.launch_persistent_context(
                str(user_data_dir),
                channel=None if browser == _BUNDLED_CHROMIUM else browser,
                headless=False,
                no_viewport=True,
            )
        except PlaywrightError as error:
            raise BrowserLoginError(_launch_hint(browser, error)) from error

        try:
            context.route(AWS_SAML_ENDPOINT_RE, intercept)
            page = context.pages[0] if context.pages else context.new_page()
            try:
                page.goto(app_url, wait_until="commit")
            except PlaywrightError as error:
                # IdP redirects (and our abort of the final POST) can interrupt the initial
                # navigation; the wait below decides success.
                logger.debug(f"initial navigation interrupted: {error}")

            deadline = time.monotonic() + timeout
            while not captured:
                if time.monotonic() >= deadline:
                    raise BrowserLoginError(f"timed out after {timeout}s waiting for sign-in")
                try:
                    pages = context.pages
                    if not pages:
                        raise BrowserLoginError("the browser was closed before sign-in finished")
                    pages[0].wait_for_timeout(_POLL_MS)
                except PlaywrightError as error:
                    if captured:
                        break
                    raise BrowserLoginError(
                        "the browser was closed before sign-in finished"
                    ) from error
        finally:
            with suppress(PlaywrightError):
                context.close()

    logger.info("Captured SAML assertion")
    return captured[0]
