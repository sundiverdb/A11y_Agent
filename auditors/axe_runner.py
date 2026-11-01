#!/usr/bin/env python3
"""Run axe-core accessibility analysis on a URL via headless Playwright."""

from __future__ import annotations

from typing import Any

AXE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.0/axe.min.js"


def run_axe(url: str) -> dict[str, Any]:
    """Navigate to url with headless Chromium, inject axe-core, return results."""
    try:
        from playwright.sync_api import sync_playwright
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
    except ImportError:
        return {
            "error": (
                "playwright is not installed. Run:\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            )
        }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                page.wait_for_timeout(2000)  # let JS render after DOM load
                page.add_script_tag(url=AXE_CDN)
                page.wait_for_function("typeof axe !== 'undefined'", timeout=10_000)
                raw = page.evaluate("() => axe.run()")
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}

    violations = raw.get("violations", [])
    return {
        "violation_count": len(violations),
        "violations": [
            {
                "id": v["id"],
                "impact": v.get("impact"),
                "description": v.get("description", ""),
                "help_url": v.get("helpUrl", ""),
                "tags": v.get("tags", []),
                "nodes": len(v.get("nodes", [])),
            }
            for v in violations
        ],
        "passes": len(raw.get("passes", [])),
        "incomplete": len(raw.get("incomplete", [])),
        "inapplicable": len(raw.get("inapplicable", [])),
    }
