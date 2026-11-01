#!/usr/bin/env python3
"""Query the WebAIM WAVE API directly (server-side — no CORS proxy needed)."""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# Mac Python (from python.org) ships without system SSL certs.
# Use certifi's bundle if available, otherwise fall back to default context.
try:
    import certifi
    _SSL_CTX: ssl.SSLContext | None = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = None

WAVE_ENDPOINT = "https://wave.webaim.org/api/request"


def _load_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
    return env


_env = _load_env_file(Path(__file__).parent.parent / "a11y_agent.env")
WAVE_API_KEY: str = _env.get("WAVE_API_KEY") or os.environ.get("WAVE_API_KEY", "")


def run_wave(url: str) -> dict[str, Any]:
    """Call the WAVE API with reporttype=2 and return the JSON response."""
    if not WAVE_API_KEY:
        return {
            "error": (
                "WAVE_API_KEY is not configured.\n"
                "Add it to a11y_agent.env or set the WAVE_API_KEY environment variable."
            )
        }

    query = urllib.parse.urlencode({"key": WAVE_API_KEY, "url": url, "reporttype": "2"})
    wave_url = f"{WAVE_ENDPOINT}?{query}"

    try:
        with urllib.request.urlopen(wave_url, timeout=30, context=_SSL_CTX) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return {"error": f"WAVE API HTTP {exc.code}: {exc.reason}"}
    except urllib.error.URLError as exc:
        return {"error": f"Could not reach WAVE API: {exc.reason}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
