#!/usr/bin/env python3
"""audit_server.py — Local server behind a11yagent.html.

Usage:
    python audit_server.py

Endpoints:
    POST /audit                 {"url": "...", "tools": ["axe", "lighthouse", "wave"]}
                                Audit one page and return each tool's results.
    POST /batch                 {"sitemap_url": "..."} or {"urls": [...]},
                                plus optional "tools" and "sampled_per_template"
                                (1 = WAVE and Lighthouse on one page per page type, 0 = all pages).
                                Starts a background site audit and returns its run ID.
    GET  /batch/<run_id>        Progress of a site audit.
    GET  /batch/<run_id>/report Summary of a site audit; also writes pages.csv and issues.csv.
    POST /batch/<run_id>/stop   Stop a site audit after its current page.
    GET  /credits               Last known WAVE credit balance (free; no WAVE request).
    GET  /health                {"status": "ok"}
"""

from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import wave_credits
from batch import BatchManager, expand_sitemap, validate_tools, validate_url
from origins import origin_allowed

HOST = "127.0.0.1"
PORT = 5001
MAX_BODY_BYTES = 1_000_000
_RUN_PATH = re.compile(r"^/batch/([^/]+)(/report|/stop)?$")

manager = BatchManager()


def _audit_one(url: str, tools: list[str]) -> dict:
    results: dict = {"url": url}
    if "axe" in tools:
        try:
            from auditors.axe_runner import run_axe
            results["axe"] = run_axe(url)
        except ImportError:
            results["axe"] = {
                "error": "playwright not installed — run: pip install playwright && playwright install chromium"
            }
    if "lighthouse" in tools:
        from auditors.lighthouse_runner import run_lighthouse
        results["lighthouse"] = run_lighthouse(url)
    if "wave" in tools:
        from auditors.wave_runner import run_wave
        results["wave"] = run_wave(url)
    return results


def start_batch(payload: dict) -> dict:
    """Start a site audit from a sitemap or a URL list."""
    urls = list(payload.get("urls") or [])
    if payload.get("sitemap_url"):
        urls += expand_sitemap(payload["sitemap_url"])
        if not urls:
            raise ValueError("No pages were found in that sitemap. Check the address.")
    tools = validate_tools(payload.get("tools") or ["axe"])
    sampled = int(payload.get("sampled_per_template", 1))
    delay = float(payload.get("delay_seconds", 2.0))
    result = manager.create(urls, tools, delay, sampled)
    warning = wave_credits.budget_warning(result.get("planned_requests", {}).get("wave", 0))
    if warning:
        result["wave_credit_warning"] = warning
    return result


class AuditHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_cors(200)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if not self._origin_ok():
            return
        path = urlsplit(self.path)
        if path.path == "/health":
            self._respond(200, {"status": "ok"})
            return
        if path.path == "/credits":
            self._respond(200, wave_credits.load() or {"credits_remaining": None})
            return
        match = _RUN_PATH.match(path.path)
        if match and match[2] != "/stop":
            top = parse_qs(path.query).get("top", ["20"])[0]
            self._run_action(lambda: (manager.get(match[1]).report(int(top)) if match[2]
                                      else manager.get(match[1]).status()))
            return
        self._respond(404, {"error": "Not found."})

    def do_POST(self) -> None:  # noqa: N802
        if not self._origin_ok():
            return
        path = urlsplit(self.path).path
        match = _RUN_PATH.match(path)
        if match and match[2] == "/stop":
            self._run_action(lambda: manager.stop(match[1]))
            return
        if path not in ("/audit", "/batch"):
            self._respond(404, {"error": "Not found. Use POST /audit or POST /batch"})
            return
        payload = self._read_json()
        if payload is None:
            return
        if path == "/batch":
            self._run_action(lambda: start_batch(payload))
            return
        url = payload.get("url")
        if not url:
            self._respond(400, {"error": "Missing required field: url"})
            return
        self._run_action(lambda: _audit_one(validate_url(url),
                                            validate_tools(payload.get("tools") or ["axe"])))

    def _origin_ok(self) -> bool:
        if origin_allowed(self.headers.get("Origin")):
            return True
        self._respond(403, {"error": "Requests from this website are not allowed."})
        return False

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length > MAX_BODY_BYTES:
            self._respond(413, {"error": "Request is too large."})
            return None
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (json.JSONDecodeError, ValueError):
            self._respond(400, {"error": "Invalid JSON body"})
            return None
        if not isinstance(payload, dict):
            self._respond(400, {"error": "Send a JSON object."})
            return None
        return payload

    def _run_action(self, action) -> None:  # noqa: ANN001
        try:
            self._respond(200, action())
        except RuntimeError as exc:  # another run is still going
            self._respond(409, {"error": str(exc)})
        except (ValueError, TypeError) as exc:
            self._respond(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._respond(500, {"error": f"{type(exc).__name__}: {exc}"})

    def _send_cors(self, code: int) -> None:
        self.send_response(code)
        origin = self.headers.get("Origin")
        if origin and origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _respond(self, code: int, data: dict | list) -> None:
        body = json.dumps(data).encode()
        self._send_cors(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: ANN002
        print(f"[audit] {self.address_string()} - {fmt % args}", flush=True)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), AuditHandler)
    print(f"Audit server listening on http://{HOST}:{PORT}")
    print("Open a11yagent.html in your browser. Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)
