"""Unit tests for the batch audit engine."""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import batch  # noqa: E402
from origins import origin_allowed  # noqa: E402


def wait(run: batch.BatchRun) -> None:
    """Wait for a run's thread to finish."""
    deadline = time.time() + 10
    while run.thread and run.thread.is_alive() and time.time() < deadline:
        time.sleep(0.01)


@pytest.fixture(autouse=True)
def runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep each test's runs in a temporary folder."""
    monkeypatch.setenv("A11Y_AGENT_RUNS", str(tmp_path))
    monkeypatch.setattr(batch, "MIN_DELAY_SECONDS", 0)


def axe_ok(url: str) -> dict[str, Any]:
    """Return one shared violation for any URL."""
    return {"page": {"status": 200, "title": "=cmd()"}, "violation_count": 1, "incomplete": 0,
            "violations": [{"id": "image-alt", "impact": "critical", "nodes": 2,
                            "wcag": ["1.1.1"], "description": "d", "help_url": "h"}]}


@pytest.mark.parametrize("url,expected", [
    ("https://x.com/", "home"), ("https://x.com/products/a", "products"),
    ("https://x.com/collections/a/products/b", "products"),
    ("https://x.com/blogs/news", "blogs/landing"), ("https://x.com/blogs/news/a", "blogs/article"),
    ("https://x.com/about", "root-page"),
])
def test_template_for(url: str, expected: str) -> None:
    """Templates come from the URL path."""
    assert batch.template_for(url) == expected


def test_expand_sitemap_follows_same_host_only() -> None:
    """Child sitemaps on other hosts are ignored, and entities are decoded."""
    pages = {
        "https://x.com/sitemap.xml": "<sitemapindex><sitemap><loc>https://x.com/a.xml?f=1&amp;t=2"
        "</loc></sitemap><sitemap><loc>https://evil.com/b.xml</loc></sitemap></sitemapindex>",
        "https://x.com/a.xml?f=1&t=2": "<urlset><url><loc>https://x.com/p</loc><image:image>"
        "<image:loc>https://cdn.com/i.png</image:loc></image:image></url></urlset>",
    }
    assert batch.expand_sitemap("https://x.com/sitemap.xml", pages.__getitem__) == [
        "https://x.com/p"]


def test_plan_samples_wave_per_template() -> None:
    """WAVE runs once per template by default and everywhere when set to 0."""
    urls = ["https://x.com/products/a", "https://x.com/products/b", "https://x.com/"]
    plan = batch.plan_tools(urls, ["axe", "wave"], 1)
    assert plan[urls[0]] == ["axe", "wave"] and plan[urls[1]] == ["axe"]
    assert plan[urls[2]] == ["axe", "wave"]
    assert "wave" in batch.plan_tools(urls, ["axe", "wave"], 0)[urls[1]]


def test_rejects_bad_input() -> None:
    """File URLs, unknown tools and unsafe run IDs are refused."""
    with pytest.raises(ValueError):
        batch.validate_url("file:///etc/passwd")
    with pytest.raises(ValueError):
        batch.validate_tools(["nope"])
    with pytest.raises(ValueError):
        batch.BatchRun("../../etc")


def test_run_exports_escaped_csv_and_groups_issues() -> None:
    """A run groups one rule across pages and neutralizes formula-like titles."""
    manager = batch.BatchManager(runners={"axe": axe_ok})
    urls = ["https://x.com/products/a", "https://x.com/pages/b"]
    started = manager.create(urls, ["axe"], 0, 1)
    run = manager.get(started["run_id"])
    wait(run)
    report = run.report()
    assert report["state"] == "finished" and report["pages_done"] == 2
    assert report["unique_issues"] == 1 and report["top_issues"][0]["pages_affected"] == 2
    with open(report["files"]["pages"], encoding="utf-8-sig") as handle:
        assert next(csv.DictReader(handle))["title"] == "'=cmd()"


def test_resume_skips_saved_pages() -> None:
    """A resumed run audits only pages without saved results."""
    calls: list[str] = []

    def runner(url: str) -> dict[str, Any]:
        calls.append(url)
        return axe_ok(url)

    manager = batch.BatchManager(runners={"axe": runner})
    urls = ["https://x.com/a", "https://x.com/b"]
    run_id = manager.create(urls[:2], ["axe"], 0, 1)["run_id"]
    run = manager.get(run_id)
    wait(run)
    lines = run.results_path.read_text().splitlines()
    run.results_path.write_text(lines[0] + "\n")
    calls.clear()
    manager.resume(run_id)
    wait(run)
    assert len(calls) == 1 and run.status()["pages_done"] == 2


def test_pauses_when_site_blocks() -> None:
    """Repeated blocks pause the run without saving those pages."""
    def blocked(url: str) -> dict[str, Any]:
        return {"error": "HTTP 429", "page": {"status": 429}}

    manager = batch.BatchManager(runners={"axe": blocked}, retry_wait=0)
    urls = [f"https://x.com/p{i}" for i in range(8)]
    run = manager.get(manager.create(urls, ["axe"], 0, 1)["run_id"])
    wait(run)
    status = run.status()
    assert status["state"] == "paused" and status["pages_done"] == 0


def test_one_tool_crash_does_not_end_run() -> None:
    """An exception is recorded against the page and the run continues."""
    def boom(url: str) -> dict[str, Any]:
        raise RuntimeError("bad page")

    manager = batch.BatchManager(runners={"axe": boom})
    run = manager.get(manager.create(["https://x.com/a", "https://x.com/b"], ["axe"], 0, 1)[
        "run_id"])
    wait(run)
    assert run.status()["pages_done"] == 2
    assert "bad page" in batch.page_row(run.records()[0])["error"]


@pytest.mark.parametrize("origin,allowed", [
    (None, True), ("null", True), ("http://localhost:3000", True),
    ("https://evil.com", False), ("http://localhost.evil.com", False),
])
def test_origin_allowed(origin: str | None, allowed: bool) -> None:
    """Only local origins may call the HTTP servers."""
    assert origin_allowed(origin) is allowed
