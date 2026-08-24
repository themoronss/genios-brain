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
#: Fallback only. Every rule DECLARES its own clock in `urgency.path`, and the caller passes it —
#: this map is what the renderer used instead, and it covered 6 of the 25 rules. For the other 19
#: `_CLOCK.get(reason_code, "")` looked up the fact named `""`, got None, and substituted the
#: sentinel word into a `{days}d` slot: "Raised severald ago — still unanswered" shipped to a
#: real user. A duration the system cannot compute must be omitted, never worded.
_CLOCK = {
    "deal_health": "deal.last_inbound",       # composite verdict clocks off the deal's last touch
}


def compute_slots(reason_code: str, node_name: str, facts: dict, eval_time: datetime,
                  clock_path: str | None = None) -> dict:
    """Named slots for template interpolation + the invention whitelist.

    `clock_path` is the rule's own `urgency.path` — the field the reasoner actually timed the
    decision from. Passing it makes the day count correct for every rule instead of the six that
    happened to be in a hand-written map.
    """
    days = _days_since(_fval(facts, clock_path or _CLOCK.get(reason_code, "")), eval_time)
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
