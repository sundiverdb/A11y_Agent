#!/usr/bin/env python3
"""Throttled, resumable multi-page audits with CSV reports for spreadsheets."""

from __future__ import annotations

import csv
import json
import os
import re
import ssl
import threading
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    import certifi

    _SSL_CTX: ssl.SSLContext | None = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CTX = None

VALID_TOOLS = ("axe", "wave", "lighthouse")
SAMPLED_TOOLS = ("wave", "lighthouse")  # paid or slow, so run per template by default
MIN_DELAY_SECONDS = 0.5
MAX_URLS = 5000
MAX_CHILD_SITEMAPS = 50
MAX_SITEMAP_BYTES = 20_000_000
RETRY_WAIT_SECONDS = 60.0
MAX_CONSECUTIVE_BLOCKS = 5
BLOCK_STATUSES = {403, 429, 503}
_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9.-]{0,120}$")

PAGE_COLUMNS = [
    "url", "template", "status", "final_url", "title", "lang", "h1_count",
    "images_missing_alt", "noindex", "links_to_accessibility_statement",
    "axe_violations", "axe_critical", "axe_serious", "axe_moderate", "axe_minor",
    "axe_needs_review", "axe_rules", "wave_errors", "wave_contrast", "wave_alerts",
    "lighthouse_accessibility", "tools_run", "error",
]
ISSUE_COLUMNS = [
    "tool", "rule", "severity", "wcag", "pages_affected", "templates", "instances",
    "description", "help_url", "sample_urls",
]


def runs_root() -> Path:
    """Return the directory that stores batch runs."""
    return Path(os.environ.get("A11Y_AGENT_RUNS", Path.home() / ".a11y_agent" / "runs"))


def default_runners() -> dict[str, Callable[[str], dict[str, Any]]]:
    """Import the auditors lazily so unused tools add no startup cost."""
    from auditors.axe_runner import run_axe
    from auditors.lighthouse_runner import run_lighthouse
    from auditors.wave_runner import run_wave

    return {"axe": run_axe, "wave": run_wave, "lighthouse": run_lighthouse}


def validate_url(url: str) -> str:
    """Return a stripped http(s) URL, or raise ValueError with a fix."""
    url = url.strip()
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(f"Not a full http(s) URL: {url!r}. Include https://.")
    return url


def validate_tools(tools: list[str]) -> list[str]:
    """Return tools with duplicates removed, or raise ValueError for unknown names."""
    unknown = [t for t in tools if t not in VALID_TOOLS]
    if unknown or not tools:
        raise ValueError(f"Choose tools from {list(VALID_TOOLS)}. Received: {tools}.")
    return list(dict.fromkeys(tools))


def template_for(url: str) -> str:
    """Guess a page's template from its path, such as products or blogs/article."""
    parts = [p for p in urllib.parse.urlsplit(url).path.split("/") if p]
    if not parts:
        return "home"
    if len(parts) >= 3 and parts[0] == "collections" and parts[2] == "products":
        return "products"
    if parts[0] == "blogs":
        return "blogs/article" if len(parts) >= 3 else "blogs/landing"
    return parts[0] if len(parts) > 1 else "root-page"


def _fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "A11y-Agent/1.0"})
    with urllib.request.urlopen(request, timeout=30, context=_SSL_CTX) as response:
        return response.read(MAX_SITEMAP_BYTES).decode("utf-8", "replace")


def _unescape(text: str) -> str:
    return (
        text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        .replace("&apos;", "'").replace("&quot;", '"')
    )


def expand_sitemap(url: str, fetch: Callable[[str], str] = _fetch_text) -> list[str]:
    """Return page URLs from a sitemap or index, following same-host child sitemaps.

    Locations are matched as text rather than parsed as XML, so a hostile sitemap
    can't trigger entity expansion.
    """
    host = urllib.parse.urlsplit(validate_url(url)).netloc
    pages: list[str] = []
    queue, seen = [url], set()
    while queue and len(seen) < MAX_CHILD_SITEMAPS and len(pages) < MAX_URLS:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        body = fetch(current)
        for block, kind in ((body, "sitemap"), (body, "url")):
            pattern = rf"<{kind}\b[^>]*>(.*?)</{kind}>"
            for entry in re.findall(pattern, block, re.S | re.I):
                found = re.search(r"<loc>\s*(.*?)\s*</loc>", entry, re.S | re.I)
                if not found:
                    continue
                loc = _unescape(found[1])
                if urllib.parse.urlsplit(loc).netloc != host:
                    continue
                (queue if kind == "sitemap" else pages).append(loc)
    return list(dict.fromkeys(pages))[:MAX_URLS]


def plan_tools(
    urls: list[str], tools: list[str], per_template: int
) -> dict[str, list[str]]:
    """Assign tools per URL. Sampled tools run on the first N per template; 0 means all."""
    used: dict[str, int] = defaultdict(int)
    plan: dict[str, list[str]] = {}
    for url in urls:
        template = template_for(url)
        chosen = [t for t in tools if t not in SAMPLED_TOOLS]
        if per_template == 0 or used[template] < per_template:
            chosen += [t for t in tools if t in SAMPLED_TOOLS]
            used[template] += 1
        plan[url] = chosen
    return plan


def _safe_cell(value: Any) -> Any:
    """Stop page-supplied text from running as a formula when opened in a spreadsheet."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _impact_counts(violations: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for violation in violations:
        counts[violation.get("impact") or "unknown"] += 1
    return counts


def _wave_count(wave: dict[str, Any], category: str) -> Any:
    return wave.get("categories", {}).get(category, {}).get("count", "")


def page_row(record: dict[str, Any]) -> dict[str, Any]:
    """Flatten one stored page result into a pages.csv row."""
    axe = record.get("axe") or {}
    wave = record.get("wave") or {}
    lighthouse = record.get("lighthouse") or {}
    page = axe.get("page") or {}
    violations = axe.get("violations") or []
    impact = _impact_counts(violations)
    errors = [f"{t}: {record[t]['error']}" for t in VALID_TOOLS
              if isinstance(record.get(t), dict) and record[t].get("error")]
    return {
        "url": record["url"],
        "template": template_for(record["url"]),
        "status": page.get("status", ""),
        "final_url": page.get("final_url", ""),
        "title": page.get("title", ""),
        "lang": page.get("lang", ""),
        "h1_count": page.get("h1_count", ""),
        "images_missing_alt": page.get("images_missing_alt", ""),
        "noindex": page.get("noindex", ""),
        "links_to_accessibility_statement": page.get("has_accessibility_link", ""),
        "axe_violations": axe.get("violation_count", ""),
        "axe_critical": impact.get("critical", 0) if violations else "",
        "axe_serious": impact.get("serious", 0) if violations else "",
        "axe_moderate": impact.get("moderate", 0) if violations else "",
        "axe_minor": impact.get("minor", 0) if violations else "",
        "axe_needs_review": axe.get("incomplete", ""),
        "axe_rules": "; ".join(v["id"] for v in violations),
        "wave_errors": _wave_count(wave, "error"),
        "wave_contrast": _wave_count(wave, "contrast"),
        "wave_alerts": _wave_count(wave, "alert"),
        "lighthouse_accessibility": (lighthouse.get("scores") or {}).get("accessibility", ""),
        "tools_run": "; ".join(t for t in VALID_TOOLS if t in record),
        "error": " | ".join(errors),
    }


def aggregate_issues(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group findings by rule so a template bug is one row, worst and widest first."""
    issues: dict[tuple[str, str], dict[str, Any]] = {}

    def add(tool: str, rule: str, severity: str, wcag: str, nodes: int, text: str,
            help_url: str, url: str) -> None:
        item = issues.setdefault((tool, rule), {
            "tool": tool, "rule": rule, "severity": severity, "wcag": wcag, "urls": [],
            "templates": set(), "instances": 0, "description": text, "help_url": help_url,
        })
        item["urls"].append(url)
        item["templates"].add(template_for(url))
        item["instances"] += nodes

    for record in records:
        url = record["url"]
        for v in (record.get("axe") or {}).get("violations") or []:
            add("axe", v["id"], v.get("impact") or "unknown", "; ".join(v.get("wcag") or []),
                v.get("nodes", 0), v.get("description", ""), v.get("help_url", ""), url)
        categories = (record.get("wave") or {}).get("categories") or {}
        for category in ("error", "contrast"):
            for rule, item in (categories.get(category, {}).get("items") or {}).items():
                add("wave", rule, category, "", item.get("count", 0),
                    item.get("description", ""), "", url)
        lighthouse = (record.get("lighthouse") or {}).get("accessibility_failures") or []
        for failure in lighthouse:
            add("lighthouse", failure["id"], "failed", "", 1, failure.get("title", ""), "", url)

    order = {"critical": 0, "serious": 1, "error": 1, "contrast": 2, "failed": 2, "moderate": 3,
             "minor": 4}
    rows = [{
        **{k: v[k] for k in ("tool", "rule", "severity", "wcag", "instances", "description",
                             "help_url")},
        "pages_affected": len(v["urls"]),
        "templates": "; ".join(sorted(v["templates"])),
        "sample_urls": "; ".join(v["urls"][:5]),
    } for v in issues.values()]
    rows.sort(key=lambda r: (order.get(r["severity"], 5), -r["pages_affected"], r["rule"]))
    return rows


class BatchRun:
    """One audit run stored on disk, so it can be stopped and resumed."""

    def __init__(self, run_id: str) -> None:
        """Bind to a run directory after checking the ID can't escape the runs folder."""
        if not _RUN_ID.match(run_id):
            raise ValueError(f"Invalid run ID: {run_id!r}.")
        self.run_id = run_id
        self.dir = runs_root() / run_id
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.state = "idle"
        self.detail = ""

    @property
    def results_path(self) -> Path:
        """Path of the append-only results log."""
        return self.dir / "results.jsonl"

    def config(self) -> dict[str, Any]:
        """Read the saved run settings."""
        return json.loads((self.dir / "config.json").read_text(encoding="utf-8"))

    def records(self) -> list[dict[str, Any]]:
        """Read saved page results, skipping a partial last line after a crash."""
        if not self.results_path.exists():
            return []
        out = []
        for line in self.results_path.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out

    def export(self) -> dict[str, str]:
        """Write pages.csv and issues.csv and return their paths."""
        records = self.records()
        files = {"pages": self.dir / "pages.csv", "issues": self.dir / "issues.csv"}
        rows = {"pages": [page_row(r) for r in records], "issues": aggregate_issues(records)}
        columns = {"pages": PAGE_COLUMNS, "issues": ISSUE_COLUMNS}
        for key, path in files.items():
            with open(path, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns[key])
                writer.writeheader()
                for row in rows[key]:
                    writer.writerow({k: _safe_cell(v) for k, v in row.items()})
        return {k: str(v) for k, v in files.items()}

    def _audit(self, url: str, tools: list[str],
               runners: dict[str, Callable[[str], dict[str, Any]]]) -> dict[str, Any]:
        record: dict[str, Any] = {"url": url}
        for tool in tools:
            try:
                record[tool] = runners[tool](url)
            except Exception as exc:  # noqa: BLE001 - one bad page must not end the run
                record[tool] = {"error": f"{type(exc).__name__}: {exc}"}
        return record

    @staticmethod
    def _blocked(record: dict[str, Any]) -> bool:
        return ((record.get("axe") or {}).get("page") or {}).get("status") in BLOCK_STATUSES

    def _work(self, runners: dict[str, Callable[[str], dict[str, Any]]],
              retry_wait: float) -> None:
        cfg = self.config()
        done = {r["url"] for r in self.records()}
        plan = plan_tools(cfg["urls"], cfg["tools"], cfg["sampled_per_template"])
        blocks = 0
        self.state = "running"
        try:
            for url in cfg["urls"]:
                if self.stop_event.is_set():
                    self.state, self.detail = "stopped", "Stopped on request."
                    return
                if url in done:
                    continue
                record = self._audit(url, plan[url], runners)
                if self._blocked(record) and not self.stop_event.wait(retry_wait):
                    record = self._audit(url, plan[url], runners)
                if self._blocked(record):
                    blocks += 1
                    if blocks >= MAX_CONSECUTIVE_BLOCKS:
                        self.state = "paused"
                        self.detail = (f"Paused after {blocks} blocked pages in a row. "
                                       "The site may be rate limiting. Resume later, with a "
                                       "longer delay.")
                        return
                    continue  # left unsaved so a resume tries this page again
                blocks = 0
                with open(self.results_path, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record) + "\n")
                self.stop_event.wait(cfg["delay_seconds"])
            self.state, self.detail = "finished", ""
        except Exception as exc:  # noqa: BLE001 - surfaced through status
            self.state, self.detail = "failed", f"{type(exc).__name__}: {exc}"
        finally:
            self.export()

    def start(self, runners: dict[str, Callable[[str], dict[str, Any]]] | None = None,
              retry_wait: float = RETRY_WAIT_SECONDS) -> None:
        """Run or resume the audit on a background thread."""
        self.stop_event.clear()
        self.state, self.detail = "running", ""
        self.thread = threading.Thread(
            target=self._work, args=(runners or default_runners(), retry_wait), daemon=True
        )
        self.thread.start()

    def status(self) -> dict[str, Any]:
        """Summarize progress. A run with no live thread is reported as interrupted."""
        cfg = self.config()
        alive = bool(self.thread and self.thread.is_alive())
        done = len({r["url"] for r in self.records()})
        state = self.state
        if state in ("idle", "running") and not alive:
            state = "finished" if done >= len(cfg["urls"]) else "interrupted"
        return {
            "run_id": self.run_id, "state": state, "detail": self.detail,
            "pages_done": done, "pages_total": len(cfg["urls"]), "tools": cfg["tools"],
            "output_folder": str(self.dir),
        }

    def report(self, top: int = 20) -> dict[str, Any]:
        """Export the CSVs and return a summary with the leading issues."""
        files = self.export()
        records = self.records()
        issues = aggregate_issues(records)
        by_template: dict[str, dict[str, int]] = defaultdict(
            lambda: {"pages": 0, "pages_with_axe_violations": 0, "pages_with_errors": 0})
        for row in map(page_row, records):
            item = by_template[row["template"]]
            item["pages"] += 1
            item["pages_with_axe_violations"] += 1 if row["axe_violations"] else 0
            item["pages_with_errors"] += 1 if row["error"] else 0
        return {
            **self.status(), "files": files, "templates": dict(by_template),
            "unique_issues": len(issues), "top_issues": issues[:max(0, top)],
            "note": ("Automated tools catch only part of WCAG. Clean results do not show "
                     "conformance, and interactive states were not exercised."),
        }


class BatchManager:
    """Create and track runs. Only one runs at a time, to stay gentle on sites."""

    def __init__(self, runners: dict[str, Callable[[str], dict[str, Any]]] | None = None,
                 retry_wait: float = RETRY_WAIT_SECONDS) -> None:
        """Store optional runner overrides for tests."""
        self.runners = runners
        self.retry_wait = retry_wait
        self.runs: dict[str, BatchRun] = {}
        self.lock = threading.Lock()

    def get(self, run_id: str) -> BatchRun:
        """Return a known run, loading it from disk if this process didn't start it."""
        run = self.runs.get(run_id) or BatchRun(run_id)
        if not (run.dir / "config.json").exists():
            raise ValueError(f"No audit run named {run_id!r}. Use list_batch_audits to see runs.")
        self.runs[run_id] = run
        return run

    def _assert_idle(self) -> None:
        for run in self.runs.values():
            if run.thread and run.thread.is_alive():
                raise RuntimeError(f"Run {run.run_id} is still going. Stop it or wait.")

    def create(self, urls: list[str], tools: list[str], delay_seconds: float,
               sampled_per_template: int) -> dict[str, Any]:
        """Validate the request, save its settings and start the run."""
        tools = validate_tools(tools)
        clean = list(dict.fromkeys(validate_url(u) for u in urls))
        if not clean or len(clean) > MAX_URLS:
            raise ValueError(f"Provide between 1 and {MAX_URLS} URLs. Received {len(clean)}.")
        if sampled_per_template < 0:
            raise ValueError("sampled_tools_per_template must be 0 (all pages) or more.")
        with self.lock:
            self._assert_idle()
            host = urllib.parse.urlsplit(clean[0]).hostname or "site"
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            run = BatchRun(f"{host.lower()}-{stamp}")
            run.dir.mkdir(parents=True, exist_ok=False)
            config = {"urls": clean, "tools": tools, "sampled_per_template": sampled_per_template,
                      "delay_seconds": max(MIN_DELAY_SECONDS, delay_seconds)}
            (run.dir / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
            self.runs[run.run_id] = run
            run.start(self.runners, self.retry_wait)
        plan = plan_tools(clean, tools, sampled_per_template)
        return {**run.status(), "planned_requests": {
            t: sum(t in chosen for chosen in plan.values()) for t in tools}}

    def resume(self, run_id: str, delay_seconds: float | None = None) -> dict[str, Any]:
        """Continue a stopped, paused or interrupted run, skipping saved pages."""
        with self.lock:
            self._assert_idle()
            run = self.get(run_id)
            if delay_seconds is not None:
                config = run.config()
                config["delay_seconds"] = max(MIN_DELAY_SECONDS, delay_seconds)
                (run.dir / "config.json").write_text(json.dumps(config, indent=2),
                                                     encoding="utf-8")
            run.start(self.runners, self.retry_wait)
        return run.status()

    def stop(self, run_id: str) -> dict[str, Any]:
        """Ask a run to stop after its current page."""
        run = self.get(run_id)
        run.stop_event.set()
        if run.thread:
            run.thread.join(timeout=1)
        return run.status()

    def list(self) -> list[dict[str, Any]]:
        """Return the status of every saved run, newest last."""
        root = runs_root()
        if not root.exists():
            return []
        return [self.get(p.name).status() for p in sorted(root.iterdir())
                if (p / "config.json").exists()]
