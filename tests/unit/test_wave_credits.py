"""Unit tests for the WAVE credit tracker."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import wave_credits  # noqa: E402


@pytest.fixture(autouse=True)
def credits_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "wave_credits.json"
    monkeypatch.setenv("A11Y_AGENT_WAVE_CREDITS", str(path))
    return path


def response(credits: object) -> dict:
    return {"status": {"success": True}, "statistics": {"creditsremaining": credits}}


def test_nothing_saved_yet() -> None:
    assert wave_credits.load() is None
    assert wave_credits.budget_warning(10) is None


def test_records_balance_and_estimates_cost() -> None:
    first = wave_credits.record(response(100), "https://a.test/")
    assert first["credits_remaining"] == 100 and first["credits_per_request"] is None
    second = wave_credits.record(response(98), "https://a.test/b")
    assert second["credits_remaining"] == 98
    assert second["credits_per_request"] == 2
    assert wave_credits.load()["checked_url"] == "https://a.test/b"


def test_top_up_keeps_previous_estimate() -> None:
    wave_credits.record(response(10))
    wave_credits.record(response(8))
    state = wave_credits.record(response(500))
    assert state["credits_remaining"] == 500 and state["credits_per_request"] == 2


@pytest.mark.parametrize("bad", [None, "12", True, {}])
def test_ignores_responses_without_a_number(bad: object, credits_file: Path) -> None:
    assert wave_credits.record(response(bad)) is None
    assert wave_credits.record({"error": "boom"}) is None
    assert not credits_file.exists()


def test_budget_warning_uses_cost_per_request() -> None:
    wave_credits.record(response(40))
    wave_credits.record(response(38))  # 2 credits per request
    assert wave_credits.budget_warning(19) is None  # 38 needed
    warning = wave_credits.budget_warning(20)  # 40 needed
    assert warning and "20 WAVE requests" in warning and "38" in warning
    assert wave_credits.budget_warning(0) is None


def test_other_report_types_keep_the_estimate() -> None:
    wave_credits.record(response(50))
    wave_credits.record(response(48))
    state = wave_credits.record(response(47), "https://example.com", update_cost=False)
    assert state["credits_remaining"] == 47 and state["credits_per_request"] == 2
