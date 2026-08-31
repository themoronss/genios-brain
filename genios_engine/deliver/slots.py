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
    # THE COMPILED LANE HAS NO RULE AT ALL, so `clock_path` arrives None and this map is the only
    # clock it will ever get. `first_response_overdue` writes `response.opened_at` on every row it
    # mints (`context/support_situations.read_first_response`), and its fallback body says how
    # long somebody has been waiting — the single most row-specific thing on the card. Without
    # this entry `_fval(facts, "")` returned None, `days` collapsed to the sentinel, and all
    # eleven of the design partner's live cards read "several days ago" on 2026-08-30. Identical
    # words for waits of 4, 24 and 43 days.
    "first_response_overdue": "response.opened_at",
}


#: slot -> the value that means "we could not compute this".
#:
#: A sentinel is legitimate in the DETERMINISTIC fallback template, where it keeps a sentence
#: grammatical, and illegitimate in the LLM prompt, where it is read as a fact and written into
#: the copy as one. The compiled lane made that visible at scale: with no authored template the
#: prompt's "Key slots" line was five sentinels, and all eighteen live cards came back reading
#: "several open items blocking commitment ... in open stage for several days ... No value set"
#: about accounts with no deal in play. The model was not hallucinating — it was told those were
#: the facts.
#:
#: A grounded value that happens to EQUAL its sentinel (a deal genuinely in stage "open") is
#: treated as ungrounded here. That costs one content-free word in the prompt and is the only
#: reading available: `compute_slots` returns a string, not a provenance.
SENTINELS: dict[str, str] = {
    "entity": "this account",
    "days": "several",
    "stage": "open",
    "money": "no value set",
    "action": "the commitment",
    "who": "them",
    "concerns": "several open items",
}


def is_grounded(name: str, value) -> bool:
    """False when this slot holds its own "we do not know" sentinel."""
    return SENTINELS.get(name) != value


def grounded_slots(slots: dict) -> dict:
    """Only the slots that came from a fact — what the model is allowed to be told."""
    return {k: v for k, v in slots.items() if is_grounded(k, v)}


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
        "entity": node_name or SENTINELS["entity"],
        "days": days if days is not None else SENTINELS["days"],
        "stage": stage or SENTINELS["stage"],
        "money": money or SENTINELS["money"],
        "action": action or SENTINELS["action"],
        "who": node_name or SENTINELS["who"],
        # composite override in card_builder; the default is a sentinel, so it reaches the
        # fallback template and never the prompt.
        "concerns": SENTINELS["concerns"],
    }
