"""Checks for the vendored Accessibility Considerations Toolkit loader."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import act  # noqa: E402


def test_lists_all_topics_in_clause_order():
    topics = act.list_topics()
    assert len(topics) == 13
    assert topics[0]["alias"] == "nonvisual-access"
    assert topics[-1]["clause"] == "4.2.10"


def test_shared_guidance_respects_excludes():
    topic = act.merged_topic("keyboard-interaction")
    shared_ids = {s["id"] for s in topic["strategies"] if s.get("from_shared")}
    assert "form-interaction" in shared_ids
    assert not shared_ids & set(topic["shared_excludes"])


def test_stub_gets_no_shared_guidance():
    topic = act.merged_topic("photosensitive-seizure-prevention")
    assert "strategies" not in topic


def test_context_always_carries_safeguards():
    text = act.topic_context("visual-adaptation")
    for name in act.REQUIRED_SAFEGUARDS:
        assert f"methodology/{name}.md" in text


def test_cognitive_topic_carries_w3c_notice():
    text = act.topic_context("language-and-communication")
    assert "Required notice: considerations/cognitive-accessibility-sources.LICENSE.md" in text


def test_guides_and_wcag_lookup():
    assert "heuristics/severity" in act.list_guides()
    assert "Severity" in act.guide("heuristics/severity")
    criterion = act.wcag_criterion("2.4.11")
    assert criterion.startswith("### 2.4.11 — Focus Not Obscured (Minimum)")
    assert "### 2.4.12" not in criterion


def test_unknown_names_raise():
    with pytest.raises(act.UnknownTopicError):
        act.topic_context("not-a-topic")
    with pytest.raises(act.UnknownTopicError):
        act.guide("../../etc/passwd")
    with pytest.raises(act.UnknownTopicError):
        act.wcag_criterion("9.9.9")
