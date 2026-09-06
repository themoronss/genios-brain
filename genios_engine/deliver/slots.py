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


def _either(facts: dict, *fields):
    """The first of these fact paths the subject actually holds.

    Two node shapes reach this function and they name the same quantity differently: the
    `outreach` anchor a compiled card is built on holds `outreach.days_waiting`, while the person
    a legacy card is built on holds `thread.days_waiting`. Ordering is anchor-first because the
    anchor's copy belongs to the situation that produced the card.
    """
    for field in fields:
        value = _fval(facts, field)
        if value is not None and value != "":
            return value
    return None


def _int(v):
    """A numeric fact as a whole number, or None when it is not one.

    `graph_facts` stores numbers as JSON, so a count arrives as `2`, `2.0` or `"2"` depending on
    which writer produced it. A slot that renders "2.0 follow-ups" is worse than one that renders
    nothing, and a float that is really a count has no business reaching a sentence.
    """
    if isinstance(v, bool) or v is None:
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


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
    # THE THREE STATE READINGS. Their reason_code IS their situation type (the compiled lane has
    # no rule, so `clock_path` arrives None and this map is the only clock they will ever get),
    # and each names the timestamp its own finding is measured from: when we last wrote, when the
    # promise was due, when the meeting was. Without an entry `_fval(facts, "")` returns None and
    # `{days}` collapses to the sentinel — the exact fault that shipped "Raised severald ago".
    "awaiting_response": "thread.last_outbound",
    "commitment_overdue": "commitment.due_at",
    "meeting_follow_through": "meeting.start_at",
    # The two Sales situations promoted out of draft. Their reason_code is their L2 situation
    # type, and each names the timestamp its own finding is measured from — when THEY wrote, and
    # when the deal last moved. Without an entry `{days}` renders the sentinel word.
    "inbound_lead": "thread.last_inbound",
    "enterprise_deal": "deal.last_inbound",
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
    # THE WAITING SLOTS. Everything above describes a thing that happened; a card whose whole
    # subject is that nothing happened could state none of it, so the authored render hints that
    # ask for "since when, how many times, and is that unusual for them" had no way to be
    # answered and fell through to their template stubs on every row.
    #
    # `follow_ups` is the one where zero is the most important value in the range — "we asked
    # once and never chased" is a different instruction from "we have chased three times" — so
    # its sentinel is deliberately a word no count can equal.
    "waited_days": "several",
    "follow_ups": "an unknown number of",
    "last_heard_days": "some time",
    "their_cadence": "an unknown time",
    "role": "this contact",
    "ball": "unclear",
    # Its own sentinel rather than a neutral word, because "we do not know why we wrote" has to
    # stay visibly different from any real objective. A card that guesses this sends the wrong
    # message with full confidence.
    "objective": "an unstated purpose",
    # THE CAMPAIGN SLOTS. A cohort card's whole content is its split — how many, how many quiet,
    # how many never chased — and without slots for them the fallback would be one sentence
    # repeated over every campaign in the org. That is the "eleven identical cards" failure this
    # codebase already fought once, and a group-shaped card is the easiest place to repeat it.
    "contacted": "several",
    "awaiting": "several",
    "never_chased": "an unknown number of",
    "past_normal": "several",
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
    # The waiting facts (`context/waiting.py`) read straight through — no clock arithmetic here,
    # because they were computed against the SAME `eval_time` the sweep used and recomputing a
    # duration from a duration is how a card comes to disagree with the decision that produced it.
    # ANCHOR FIRST, THEN THE PERSON. A compiled card's subject is the `outreach` node
    # `context/outreach_situations.py` mints, which carries `outreach.*`; a legacy card's subject
    # is the person, who carries `thread.*`. Reading only the person's names meant every compiled
    # card fell back to sentinels for the exact numbers the situation was built to state — the
    # card came out as "about fundraising" with the wait, the chase count and the cadence all cut.
    waited = _int(_either(facts, "outreach.days_waiting", "thread.days_waiting"))
    follow_ups = _int(_either(facts, "outreach.follow_up_count", "thread.follow_up_count"))
    last_heard = _int(_either(facts, "outreach.days_since_last_heard", "thread.last_heard_days"))
    cadence = _int(_either(facts, "outreach.their_normal_reply_days", "party.reply_cadence_days"))
    # `party.role` is what they did in one exchange; `relationship.nature` is what they ARE to us.
    # The nature is what changes the advice — an investor and a prospect who both went quiet need
    # opposite messages — so it wins, and role is the fallback when nobody has typed the
    # relationship yet.
    role = _either(facts, "outreach.counterparty_role",
                   "relationship.nature", "party.role")
    ball = _fval(facts, "thread.ball_in_court")
    # WHY WE WROTE — read from the anchor's own field first, then the person's. A card built on an
    # `outreach` node holds the projected copy; a legacy card built on the person holds the
    # original, and both should be able to say it.
    objective = _either(facts, "outreach.objective", "thread.objective",
                        "cohort.objective")
    contacted = _int(_fval(facts, "cohort.contacted"))
    awaiting = _int(_fval(facts, "cohort.awaiting"))
    never_chased = _int(_fval(facts, "cohort.never_chased"))
    past_normal = _int(_fval(facts, "cohort.awaiting_beyond_normal"))
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
        "waited_days": waited if waited is not None else SENTINELS["waited_days"],
        "follow_ups": follow_ups if follow_ups is not None else SENTINELS["follow_ups"],
        "last_heard_days": last_heard if last_heard is not None else SENTINELS["last_heard_days"],
        "their_cadence": cadence if cadence is not None else SENTINELS["their_cadence"],
        "role": role or SENTINELS["role"],
        "ball": ball or SENTINELS["ball"],
        "objective": objective or SENTINELS["objective"],
        "contacted": contacted if contacted is not None else SENTINELS["contacted"],
        "awaiting": awaiting if awaiting is not None else SENTINELS["awaiting"],
        "never_chased": (never_chased if never_chased is not None
                         else SENTINELS["never_chased"]),
        "past_normal": past_normal if past_normal is not None else SENTINELS["past_normal"],
    }
