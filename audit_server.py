#!/usr/bin/env python3
"""audit_server.py — Orchestrates multi-tool accessibility audits.

Usage:
    python audit_server.py

Endpoint:
    POST /audit
    Body:  {"url": "https://example.com", "tools": ["axe", "lighthouse", "wave"]}
    Response: {"url": "...", "axe": {...}, "lighthouse": {...}, "wave": {...}}

    GET /health  →  {"status": "ok"}
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

from origins import origin_allowed  # noqa: E402

HOST = "127.0.0.1"
PORT = 5001


class AuditHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_cors(200)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        else:
            self._respond(404, {"error": "Use POST /audit"})

    def do_POST(self) -> None:  # noqa: N802
        if not origin_allowed(self.headers.get("Origin")):
            self._respond(403, {"error": "Requests from this website are not allowed."})
            return
        if self.path != "/audit":
            self._respond(404, {"error": "Not found. Use POST /audit"})
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            self._respond(400, {"error": "Invalid JSON body"})
            return

        url: str | None = payload.get("url")
        tools: list[str] = payload.get("tools", ["axe"])

        if not url:
            self._respond(400, {"error": "Missing required field: url"})
            return

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

        self._respond(200, results)

    def _send_cors(self, code: int) -> None:
        self.send_response(code)
        origin = self.headers.get("Origin")
        if origin and origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _respond(self, code: int, data: dict) -> None:
        body = json.dumps(data).encode()
        self._send_cors(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: ANN002
        print(f"[audit] {self.address_string()} - {fmt % args}", flush=True)


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), AuditHandler)
    print(f"Audit server listening on http://{HOST}:{PORT}")
    print('Endpoint: POST /audit  body: {"url": "https://...", "tools": ["axe", "lighthouse", "wave"]}')
    print("Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)
