"""Base exception for failures the CLI reports as a message rather than a traceback."""

__all__ = ["AWSSSOManagerError"]


class AWSSSOManagerError(Exception):
    """An expected, user-actionable failure (bad config, sign-in timeout, and so on)."""
