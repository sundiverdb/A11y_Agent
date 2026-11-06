#!/usr/bin/env python3
"""MCP server exposing the accessibility auditors to Claude and other MCP clients.

Run over stdio by an MCP client:  python /path/to/A11y_Agent/mcp_server.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from batch import (  # noqa: E402
    BatchManager, default_runners, expand_sitemap, validate_tools, validate_url,
)

server = MCPServer(
    "a11y-agent",
    instructions=(
        "Automated accessibility audits with axe-core, WAVE and Lighthouse. Use audit_url for "
        "one page. For many pages use start_batch_audit, then poll get_batch_status and read "
        "get_batch_report. WAVE uses paid credits, so keep its per-template sampling unless "
        "the user asks otherwise. Automated results cover only part of WCAG: never present a "
        "clean result as conformance."
    ),
)
manager = BatchManager()


def _audit_one(url: str, tools: list[str]) -> dict[str, Any]:
    runners = default_runners()
    return {"url": url, **{tool: runners[tool](url) for tool in tools}}


@server.tool()
async def audit_url(url: str, tools: list[str] | None = None) -> dict[str, Any]:
    """Audit one page. Tools: axe (default), wave (uses paid credits), lighthouse."""
    clean = validate_url(url)
    chosen = validate_tools(tools or ["axe"])
    return await asyncio.to_thread(_audit_one, clean, chosen)


@server.tool()
async def start_batch_audit(
    urls: list[str] | None = None,
    sitemap_url: str | None = None,
    tools: list[str] | None = None,
    delay_seconds: float = 2.0,
    sampled_tools_per_template: int = 1,
) -> dict[str, Any]:
    """Start a background audit of a URL list or a sitemap, and return its run ID.

    Axe runs on every page. WAVE and Lighthouse run on the first
    sampled_tools_per_template pages of each template; use 0 to run them on all pages.
    The result's planned_requests shows how many requests each tool will make.
    """
    page_urls = list(urls or [])
    if sitemap_url:
        page_urls += await asyncio.to_thread(expand_sitemap, sitemap_url)
    return manager.create(page_urls, tools or ["axe"], delay_seconds, sampled_tools_per_template)


@server.tool()
def get_batch_status(run_id: str) -> dict[str, Any]:
    """Show a batch run's state and progress."""
    return manager.get(run_id).status()


@server.tool()
def get_batch_report(run_id: str, top_issues: int = 20) -> dict[str, Any]:
    """Summarize results by template and issue, and write pages.csv and issues.csv."""
    return manager.get(run_id).report(top_issues)


@server.tool()
def stop_batch_audit(run_id: str) -> dict[str, Any]:
    """Stop a batch run after its current page. Saved results are kept."""
    return manager.stop(run_id)


@server.tool()
def resume_batch_audit(run_id: str, delay_seconds: float | None = None) -> dict[str, Any]:
    """Continue a stopped, paused or interrupted run, skipping pages already saved."""
    return manager.resume(run_id, delay_seconds)


@server.tool()
def list_batch_audits() -> list[dict[str, Any]]:
    """List saved batch runs and their progress."""
    return manager.list()


if __name__ == "__main__":
    server.run()
