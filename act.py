"""Load Microsoft's Accessibility Considerations Toolkit (ACT) from the pinned copy in vendor/ms-act.

The toolkit is reference guidance for the LLM side of an audit: what to check beyond what
axe, WAVE and Lighthouse can detect, organized by EN 301 549 functional performance
statements. See vendor/ms-act/VENDORED.md for the pinned commit and how to update it.

Merging and safeguard rules follow the toolkit README ("How to use"):
- elaborated topics get shared strategies, interaction contexts and learning entries appended,
  tagged from_shared: true, unless their id is in the topic's shared_excludes;
- stubs get nothing appended;
- licensing, responsible use and interpretation guidance always travel with a topic, plus any
  third-party notice the topic's provenance names.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ACT_DIR = Path(__file__).resolve().parent / "vendor" / "ms-act"
SCHEMAS_DIR = ACT_DIR / "schemas"

REQUIRED_SAFEGUARDS = ("licensing", "responsible-consideration-use", "consideration-interpretation")
GUIDE_FOLDERS = ("methodology", "heuristics")
WCAG_NOTICE = ("Supporting reference only, under the W3C Document License "
               "(see vendor/ms-act/standards/wcag-requirements.LICENSE.md). "
               "Use https://www.w3.org/TR/WCAG22/ for conformance decisions.")


class UnknownTopicError(ValueError):
    pass


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def _topics() -> dict[str, dict[str, Any]]:
    """Map each topic alias to its parsed YAML."""
    topics: dict[str, dict[str, Any]] = {}
    for path in sorted(SCHEMAS_DIR.glob("*.consideration.yaml")):
        data = yaml.safe_load(_read(path))
        topics[data["alias"]] = data
    return topics


@lru_cache(maxsize=None)
def _shared() -> dict[str, Any]:
    return yaml.safe_load(_read(SCHEMAS_DIR / "_shared-considerations.yaml"))


def list_topics() -> list[dict[str, str]]:
    """Return alias, EN 301 549 clause, title and status for every topic."""
    return [
        {"alias": a, "clause": t["clause"], "title": t["title"], "status": t["status"]}
        for a, t in sorted(_topics().items(), key=lambda item: _clause_key(item[1]["clause"]))
    ]


def _clause_key(clause: str) -> tuple[int, ...]:
    return tuple(int(part) for part in clause.split("."))


def merged_topic(alias: str) -> dict[str, Any]:
    """Return a topic with applicable shared guidance merged in."""
    topics = _topics()
    if alias not in topics:
        raise UnknownTopicError(f"Unknown topic {alias!r}. Known topics: {', '.join(sorted(topics))}")
    topic = dict(topics[alias])
    if topic["status"] == "stub":
        return topic
    if topic["status"] != "elaborated":
        raise ValueError(f"Unsupported topic status: {topic['status']!r}")
    excludes = set(topic.get("shared_excludes", []))
    for field in ("strategies", "interaction_contexts", "learning"):
        extra = [{**entry, "from_shared": True}
                 for entry in _shared().get(field, []) if entry["id"] not in excludes]
        topic[field] = list(topic.get(field, [])) + extra
    return topic


def safeguards() -> str:
    """Methodology that must accompany every topic given to a model."""
    return "\n\n".join(
        f"# Required methodology: methodology/{name}.md\n\n{_read(ACT_DIR / 'methodology' / f'{name}.md')}"
        for name in REQUIRED_SAFEGUARDS
    )


def topic_context(alias: str) -> str:
    """Return the safeguards, the merged topic as YAML, and any required third-party notice."""
    topic = merged_topic(alias)
    parts = [safeguards(), f"# Accessibility consideration: {alias} (EN 301 549 FPS {topic['clause']})\n\n"
             + yaml.safe_dump(topic, allow_unicode=True, sort_keys=False, width=120)]
    notice = (topic.get("provenance") or {}).get("required_notice")
    if notice:
        parts.append(f"# Required notice: {notice}\n\n{_read(ACT_DIR / notice)}")
    return "\n\n".join(parts)


def list_guides() -> list[str]:
    """Names accepted by guide(), e.g. 'methodology/confidence-gate' or 'heuristics/severity'."""
    return [f"{folder}/{path.stem}"
            for folder in GUIDE_FOLDERS for path in sorted((ACT_DIR / folder).glob("*.md"))]


def guide(name: str) -> str:
    """Return one methodology or heuristics document."""
    if name not in list_guides():
        raise UnknownTopicError(f"Unknown guide {name!r}. Known guides: {', '.join(list_guides())}")
    return _read(ACT_DIR / f"{name}.md")


def wcag_criterion(number: str) -> str:
    """Return one WCAG 2.2 success criterion, e.g. '2.4.11', from the toolkit's reference."""
    text = _read(ACT_DIR / "standards" / "wcag-requirements.md")
    match = re.search(rf"^### {re.escape(number.strip())} — .*?(?=^### |^## |\Z)", text, re.M | re.S)
    if not match:
        raise UnknownTopicError(f"No WCAG 2.2 success criterion {number!r} in the reference.")
    return f"{match.group(0).rstrip()}\n\n_{WCAG_NOTICE}_"
