"""Track the WAVE API credit balance.

WAVE has no free balance endpoint: every response reports the balance in
statistics.creditsremaining, and a request to check it costs credits too. So the
balance is saved from every WAVE call the agent already makes, and a live check
is an explicit, paid choice.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def state_path() -> Path:
    """Return the file that stores the last known balance."""
    default = Path.home() / ".a11y_agent" / "wave_credits.json"
    return Path(os.environ.get("A11Y_AGENT_WAVE_CREDITS", default))


def load() -> dict[str, Any] | None:
    """Return the last saved balance, or None if WAVE has not been called yet."""
    try:
        return json.loads(state_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def record(response: dict[str, Any], url: str = "",
           update_cost: bool = True) -> dict[str, Any] | None:
    """Save the balance from a WAVE response. Returns the saved state, or None if absent.

    update_cost=False keeps the per-request estimate, for requests of a different report type.
    """
    remaining = (response.get("statistics") or {}).get("creditsremaining")
    if not isinstance(remaining, (int, float)) or isinstance(remaining, bool):
        return None
    previous = load()
    state: dict[str, Any] = {
        "credits_remaining": int(remaining),
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checked_url": url,
        "credits_per_request": (previous or {}).get("credits_per_request"),
    }
    if previous is not None and update_cost:
        used = previous["credits_remaining"] - int(remaining)
        if used > 0:  # a top-up makes this negative; keep the old estimate then
            state["credits_per_request"] = used
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(path)
    return state


def budget_warning(planned_requests: int) -> str | None:
    """Return a warning if the planned WAVE requests may exceed the known balance."""
    state = load()
    if not planned_requests or state is None:
        return None
    per = state.get("credits_per_request") or 1
    needed = planned_requests * per
    if needed <= state["credits_remaining"]:
        return None
    return (f"This run plans {planned_requests} WAVE requests (about {needed} credits), but the "
            f"last known balance was {state['credits_remaining']} on {state['checked_at']}. "
            "Pages past the balance will fail for WAVE. Stop the run or lower the WAVE sampling.")
