"""Decide which browser origins may call the local HTTP servers."""

from __future__ import annotations

from urllib.parse import urlsplit


def origin_allowed(origin: str | None) -> bool:
    """Allow non-browser clients, a11yagent.html opened from a file, and localhost pages."""
    if origin is None or origin == "null":
        return True
    parts = urlsplit(origin)
    return parts.scheme in ("http", "https") and parts.hostname in ("localhost", "127.0.0.1")
