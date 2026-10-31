#!/usr/bin/env python3
"""Run Lighthouse against a URL via the lighthouse CLI (Node.js required)."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any


def run_lighthouse(url: str) -> dict[str, Any]:
    """Run lighthouse CLI and return category scores + failed a11y audits."""
    if not shutil.which("lighthouse"):
        return {
            "error": (
                "Lighthouse CLI not found.\n"
                "Install Node.js 18+, then run:\n"
                "  npm install -g lighthouse"
            )
        }

    try:
        result = subprocess.run(
            [
                "lighthouse",
                url,
                "--output=json",
                "--output-path=stdout",
                "--quiet",
                "--chrome-flags=--headless --no-sandbox --disable-dev-shm-usage",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return {"error": "Lighthouse timed out (>120 s)"}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}

    if result.returncode != 0:
        return {"error": result.stderr.strip() or "Lighthouse exited with a non-zero status"}

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": "Could not parse Lighthouse JSON output"}

    categories = data.get("categories", {})
    audits = data.get("audits", {})

    # Build scores dict (0-100 integers)
    scores: dict[str, int | None] = {
        k: (round(v["score"] * 100) if v.get("score") is not None else None)
        for k, v in categories.items()
    }

    # Collect failed audits that belong to the accessibility category
    a11y_audit_ids = {
        ref["id"]
        for ref in categories.get("accessibility", {}).get("auditRefs", [])
    }
    a11y_failures = [
        {
            "id": aid,
            "title": audits[aid].get("title", ""),
            "description": audits[aid].get("description", ""),
            "score": audits[aid].get("score"),
        }
        for aid in a11y_audit_ids
        if aid in audits
        and audits[aid].get("score") is not None
        and audits[aid].get("score") < 1
        and audits[aid].get("scoreDisplayMode") not in ("informative", "notApplicable", "manual")
    ]

    return {"scores": scores, "accessibility_failures": a11y_failures}
