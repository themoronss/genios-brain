from __future__ import annotations

from datetime import datetime, timezone

# Fact-derived slots — the ONLY values a card may state. Both the deterministic fallback
# template and the invention validator (§5.10) draw from here: E1's LLM output may contain a
# name/number/date only if it appears in this slot set (or the raw facts). Everything computed
# from typed facts + the passed eval_time — no wall clock, no invention.


def _parse_ts(v):
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _days_since(v, eval_time) -> int | None:
    ts = _parse_ts(v)
    if ts is None:
        return None
    return max(0, int((eval_time - ts).total_seconds() // 86400))


def _money(v) -> str | None:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    if n >= 1000:
        return f"${n/1000:.0f}k" if n < 1_000_000 else f"${n/1_000_000:.1f}M"
    return f"${n:.0f}"


def _fval(facts: dict, field: str):
    f = facts.get(field)
    return f.get("value") if isinstance(f, dict) else None


# which fact carries the "elapsed" clock per reason_code (mirrors the pack rule urgency.path)
_CLOCK = {
    "stalled_deal": "deal.last_inbound",
    "commitment_overdue": "commitment.due_at",
    "unanswered_email": "thread.last_inbound",
    "champion_quiet": "thread.last_inbound",
    "meeting_no_followup": "meeting.start_at",
    "deal_health": "deal.last_inbound",       # composite verdict clocks off the deal's last touch
}


def compute_slots(reason_code: str, node_name: str, facts: dict, eval_time: datetime) -> dict:
    """Named slots for template interpolation + the invention whitelist. Missing facts collapse
    to safe generic words (never a fabricated specific), so a card is always renderable + honest."""
    days = _days_since(_fval(facts, _CLOCK.get(reason_code, "")), eval_time)
    stage = _fval(facts, "deal.status") or _fval(facts, "deal.stage")
    money = _money(_fval(facts, "deal.value"))
    action = _fval(facts, "commitment.action")
    return {
        "entity": node_name or "this account",
        "days": days if days is not None else "several",
        "stage": stage or "open",
        "money": money or "no value set",
        "action": action or "the commitment",
        "who": node_name or "them",
        "concerns": "several open items",     # composite override in card_builder; default is safe
    }
