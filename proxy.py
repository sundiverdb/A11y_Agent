#!/usr/bin/env python3
"""proxy.py — Local proxy server that calls the WAVE API.

Usage:
    python proxy.py

Reads WAVE_API_KEY from a11y_agent.env (same directory as this script),
then serves GET /check?url=<url> by forwarding the request to the WAVE API
and returning the JSON response. CORS headers are set so dialog.html can
call this server from a file:// or localhost origin.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


WAVE_API_ENDPOINT = "https://wave.webaim.org/api/request"
HOST = "127.0.0.1"
PORT = 5000


def load_env_file(path: Path) -> dict:
    """Parse a simple KEY=VALUE env file; ignores blank lines and comments."""
    env = {}
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


_env = load_env_file(Path(__file__).parent / "a11y_agent.env")
WAVE_API_KEY: str = _env.get("WAVE_API_KEY") or os.environ.get("WAVE_API_KEY", "")


class ProxyHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler that proxies WAVE API requests."""

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_cors(200)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path != "/check":
            self._respond(404, {"error": "Not found. Use GET /check?url=<url>"})
            return

        params = urllib.parse.parse_qs(parsed.query)
        target_url = params.get("url", [None])[0]

        if not target_url:
            self._respond(400, {"error": "Missing required query parameter: url"})
            return

        if not WAVE_API_KEY:
            self._respond(
                500,
                {"error": "WAVE_API_KEY is not configured. Add it to a11y_agent.env."},
            )
            return

        wave_query = urllib.parse.urlencode(
            {"key": WAVE_API_KEY, "url": target_url, "reporttype": "2"}
        )
        wave_url = f"{WAVE_API_ENDPOINT}?{wave_query}"

        try:
            with urllib.request.urlopen(wave_url, timeout=30) as resp:
                body = resp.read()
            data = json.loads(body)
            self._respond(200, data)
        except urllib.error.HTTPError as exc:
            self._respond(exc.code, {"error": f"WAVE API HTTP error: {exc.reason}"})
        except urllib.error.URLError as exc:
            self._respond(502, {"error": f"Could not reach WAVE API: {exc.reason}"})
        except Exception as exc:  # noqa: BLE001
            self._respond(500, {"error": str(exc)})

    def _send_cors(self, code: int) -> None:
        self.send_response(code)
        # Allow both file:// (origin "null") and localhost origins
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _respond(self, code: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self._send_cors(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: ANN002
        print(f"[proxy] {self.address_string()} - {fmt % args}")


if __name__ == "__main__":
    if not WAVE_API_KEY:
        print(
            "WARNING: WAVE_API_KEY not found in a11y_agent.env or environment.\n"
            "         Add WAVE_API_KEY=<your-key> to a11y_agent.env and restart."
        )

    server = HTTPServer((HOST, PORT), ProxyHandler)
    print(f"Proxy listening on http://{HOST}:{PORT}  —  Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nProxy stopped.")
