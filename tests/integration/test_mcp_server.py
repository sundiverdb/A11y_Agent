"""End-to-end test: real MCP client, real browser, local fixture page.

Set AXE_SCRIPT_PATH to a local axe.min.js when the CDN copy can't be reached.
"""

from __future__ import annotations

import asyncio
import functools
import http.server
import os
import sys
import threading
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def site() -> str:
    """Serve the fixtures folder on a local port."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(ROOT / "tests" / "fixtures"))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_tools_over_stdio(site: str, tmp_path: Path) -> None:
    """List tools, audit one page, then finish a batch and read its report."""
    async def scenario() -> None:
        params = StdioServerParameters(
            command=sys.executable, args=[str(ROOT / "mcp_server.py")],
            env={**os.environ, "A11Y_AGENT_RUNS": str(tmp_path)})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {t.name for t in (await session.list_tools()).tools}
                assert {"audit_url", "start_batch_audit", "get_batch_report"} <= names

                one = await session.call_tool("audit_url", {"url": f"{site}/bad_page.html"})
                data = one.structured_content
                assert data["axe"]["page"]["h1_count"] == 2
                assert data["axe"]["page"]["images_missing_alt"] == 1
                assert data["axe"]["page"]["noindex"] is True
                assert data["axe"]["page"]["has_accessibility_link"] is True
                rules = {v["id"] for v in data["axe"]["violations"]}
                assert "image-alt" in rules

                missing = await session.call_tool("audit_url", {"url": f"{site}/nope.html"})
                assert missing.structured_content["axe"]["page"]["status"] == 404

                run = (await session.call_tool("start_batch_audit", {
                    "urls": [f"{site}/bad_page.html"], "delay_seconds": 0.5,
                })).structured_content
                for _ in range(120):
                    status = (await session.call_tool(
                        "get_batch_status", {"run_id": run["run_id"]})).structured_content
                    if status["state"] != "running":
                        break
                    await asyncio.sleep(0.5)
                assert status["state"] == "finished"
                report = (await session.call_tool(
                    "get_batch_report", {"run_id": run["run_id"]})).structured_content
                assert report["unique_issues"] >= 1
                assert Path(report["files"]["issues"]).exists()

    asyncio.run(scenario())
