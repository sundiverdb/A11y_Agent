"""Integration tests for the site-audit endpoints in audit_server.py (fake auditors, no network)."""

from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import audit_server  # noqa: E402
import batch  # noqa: E402

PAGES = [f"https://shop.test/products/p{i}" for i in range(4)] + ["https://shop.test/pages/about"]


def fake_runner(name: str):
    def run(url: str) -> dict[str, Any]:
        if name == "axe":
            return {"violation_count": 1, "passes": 3, "violations": [
                {"id": "color-contrast", "impact": "serious", "description": "Low contrast",
                 "tags": ["wcag143"], "nodes": 2, "help_url": ""}]}
        return {}
    return run


@pytest.fixture()
def server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("A11Y_AGENT_RUNS", str(tmp_path / "runs"))
    monkeypatch.setenv("A11Y_AGENT_WAVE_CREDITS", str(tmp_path / "credits.json"))
    monkeypatch.setattr(batch, "MIN_DELAY_SECONDS", 0)
    monkeypatch.setattr(audit_server, "expand_sitemap", lambda url: list(PAGES))
    monkeypatch.setattr(audit_server, "manager", batch.BatchManager(
        runners={t: fake_runner(t) for t in ("axe", "wave", "lighthouse")}, retry_wait=0))
    httpd = audit_server.ThreadingHTTPServer(("127.0.0.1", 0), audit_server.AuditHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def call(base: str, path: str, body: dict | None = None, origin: str | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, method="POST" if body is not None else "GET")
    req.add_header("Content-Type", "application/json")
    if origin:
        req.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_site_audit_from_sitemap(server: str) -> None:
    code, started = call(server, "/batch", {"sitemap_url": "https://shop.test/sitemap.xml",
                                            "tools": ["axe", "wave"], "sampled_per_template": 1,
                                            "delay_seconds": 0})
    assert code == 200, started
    assert started["pages_total"] == 5
    assert started["planned_requests"] == {"axe": 5, "wave": 2}  # one per page type
    run_id = started["run_id"]
    deadline = time.time() + 10
    while time.time() < deadline:
        code, st = call(server, f"/batch/{run_id}")
        if st["state"] != "running":
            break
        time.sleep(0.05)
    assert st["state"] == "finished" and st["pages_done"] == 5
    code, rep = call(server, f"/batch/{run_id}/report?top=5")
    assert code == 200 and rep["unique_issues"] >= 1
    assert rep["top_issues"][0]["rule"] == "color-contrast"
    assert Path(rep["files"]["issues"]).exists()


def test_errors_are_reported_plainly(server: str) -> None:
    assert call(server, "/batch", {"sitemap_url": "not a url"})[0] in (200, 400)
    code, body = call(server, "/batch", {"urls": [], "tools": ["axe"]})
    assert code == 400 and "URL" in body["error"]
    code, body = call(server, "/batch", {"urls": PAGES, "tools": ["nope"]})
    assert code == 400
    code, body = call(server, "/batch/../../etc")
    assert code in (400, 404)
    code, body = call(server, "/batch/unknown-run-20260101-000000")
    assert code == 400 and "No audit run" in body["error"]


def test_blocks_other_websites(server: str) -> None:
    code, body = call(server, "/batch", {"urls": PAGES}, origin="https://evil.example")
    assert code == 403
    code, _ = call(server, "/health", origin="https://evil.example")
    assert code == 403
    code, body = call(server, "/credits")
    assert code == 200 and body == {"credits_remaining": None}


def test_stop_endpoint(server: str) -> None:
    code, started = call(server, "/batch", {"urls": PAGES, "tools": ["axe"], "delay_seconds": 5})
    code, st = call(server, f"/batch/{started['run_id']}/stop", {})
    assert code == 200 and st["state"] in ("stopped", "running", "finished")
