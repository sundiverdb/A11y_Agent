#!/usr/bin/env python3
"""Run axe-core accessibility analysis on a URL via headless Playwright."""

from __future__ import annotations

import os
import re
from typing import Any

AXE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.0/axe.min.js"

PAGE_FACTS_JS = """() => {
  const robots = [...document.querySelectorAll('meta[name="robots" i]')]
    .map(m => m.content).join(' ');
  const links = [...document.querySelectorAll('a[href]')];
  return {
    title: document.title,
    lang: document.documentElement.getAttribute('lang') || '',
    h1_count: document.querySelectorAll('h1').length,
    images_missing_alt: document.querySelectorAll('img:not([alt])').length,
    noindex: /noindex/i.test(robots),
    has_accessibility_link: links.some(a =>
      /accessib/i.test(a.getAttribute('href')) || /accessib/i.test(a.textContent)),
  };
}"""


def _wcag_criteria(tags: list[str]) -> list[str]:
    """Convert axe tags such as wcag143 into success criteria such as 1.4.3."""
    found = []
    for tag in tags:
        match = re.fullmatch(r"wcag(\d)(\d)(\d+)", tag)
        if match:
            found.append(".".join(match.groups()))
    return found


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
                # bypass_csp: a site's Content-Security-Policy would otherwise block axe.
                page = browser.new_context(bypass_csp=True).new_page()
                response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                page.wait_for_timeout(2000)  # let JS render after DOM load
                facts = page.evaluate(PAGE_FACTS_JS)
                status = response.status if response else None
                headers = response.headers if response else {}
                facts.update(
                    status=status,
                    final_url=page.url,
                    noindex=facts["noindex"]
                    or "noindex" in headers.get("x-robots-tag", "").lower(),
                )
                if status is not None and status >= 400:
                    return {"error": f"Page returned HTTP {status}", "page": facts}
                axe_path = os.environ.get("AXE_SCRIPT_PATH")
                if axe_path:
                    page.add_script_tag(path=axe_path)
                else:
                    page.add_script_tag(url=AXE_CDN)
                page.wait_for_function("typeof axe !== 'undefined'", timeout=10_000)
                raw = page.evaluate("() => axe.run()")
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}

    violations = raw.get("violations", [])
    return {
        "page": facts,
        "violation_count": len(violations),
        "violations": [
            {
                "id": v["id"],
                "impact": v.get("impact"),
                "description": v.get("description", ""),
                "help_url": v.get("helpUrl", ""),
                "tags": v.get("tags", []),
                "wcag": _wcag_criteria(v.get("tags", [])),
                "nodes": len(v.get("nodes", [])),
            }
            for v in violations
        ],
        "passes": len(raw.get("passes", [])),
        "incomplete": len(raw.get("incomplete", [])),
        "inapplicable": len(raw.get("inapplicable", [])),
    }
