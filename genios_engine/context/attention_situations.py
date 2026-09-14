"""L2.7 · the subjects nothing on the board mentions — the coverage miss, recovered.

`residue.py` measures what this layer looked at and could not explain. `reply_owed_triage` asks a
model which of those matter. Until now both stopped there: the measurement had no reader and the
verdict had no destination, so the one thing the whole chain was built to surface — *"they replied,
we went quiet, and nothing said so"* — was recorded, judged, and shown to nobody.

THIS IS A CARD OF LAST RESORT AND SAYS SO. `read_unanswered_replies` is the deterministic reading
for the same shape and it is strictly better evidence: it compares two recorded instants,
`thread.last_inbound` against `thread.last_outbound`, and states the number of days owed. This one
fires only where that reading did NOT — residue exists exactly where no live situation covers the
subject — so the two can never both speak about one counterparty, by construction rather than by a
filter. What is left here is the population that reading missed: a node whose `thread.ball_in_court`
says the turn is ours while the timestamps it needs are absent, contradictory, or attached to a
thread that resolved elsewhere.

WHAT IT CANNOT SAY, AND DOES NOT. It has no `days_owed`, because the facts that would produce one
are the facts whose absence put the subject here. It cannot say why no reading covered the subject
— that is the question, not the answer. Both are declared in `missing` rather than guessed, so the
coverage score reads this as the partial reading it is instead of scoring it complete.

IT EXISTS ONLY WHERE A MODEL SAID SO, and that is the one place in this layer where that is true.
The standing rule is that no gate may refuse on ABSENCE, and this does not: without a verdict there
is no card, which is precisely the state the tenant is in today. Nothing is withheld, suppressed or
downgraded when the angle is unavailable — the layer simply returns to producing what it produced
before. That is the agreed law's other half: *a model may propose a situation; it may never rank
one, and never produces a number a card asserts.* Every number on this card is measured; the
model's contribution is whether the card exists at all.

ONLY `important` MINTS. `reply_owed_triage` answers `important` / `developing` / `ambient` /
`noise`, and the last three deliberately produce nothing. A card is an interruption, the enum
already separates "act" from "aware", and surfacing the other three would refill the queue this
was meant to triage.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from genios_engine.context.angles.queues import TRIAGE_ANGLE_BY_KIND, TRIAGE_KEY, triaged_residue
from genios_engine.context.residue import RESIDUE_BALL_IN_COURT, SELF_REPORTED_TYPE

#: The one verdict that becomes a card. See the module docstring: the other three are answers, not
#: interruptions.
ACTIONABLE = "important"

#: Its own anchor, and NOT the counterparty's. A person can be the subject of a real reading and of
#: this one at different times, and the two must close separately — the rule `condition_situations`
#: keeps for the same reason. `anchor_node_type` leaves this as its own node type, so it cannot
#: collide with a person, a commitment or a meeting.
ANCHOR_UNREPORTED = "unreported"

#: WHAT THIS CARD IS TYPED AS, imported by `residue.py` and spelled once. The coverage predicate
#: excludes exactly this type, because a card reporting that nothing explains a subject does not
#: itself explain it — without that exclusion the card appears on one sweep, covers the subject,
#: deletes its own residue row and vanishes on the next, for ever.
SITUATION_TYPE = SELF_REPORTED_TYPE

#: How many of these one sweep may produce. A ceiling rather than a sample: a tenant whose coverage
#: is poor could otherwise turn a recovery path into a second feed, and a queue of last-resort
#: cards is the thing this was built to shrink.
MAX_PER_SWEEP = 25


def _days(now: datetime, seen: Any) -> int | None:
    """How long this has gone unexplained. `first_seen_at` is never updated by the detector —
    "how long a thing has gone unexplained is the number that makes this a work queue rather than
    a gauge" — so it is the one honest duration available here."""
    if isinstance(seen, str):
        try:
            seen = datetime.fromisoformat(seen.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(seen, datetime):
        return None
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    return max(0, (now - seen).days)


def gather_unreported_attention(conn, org_id: str) -> tuple[Mapping[str, Any], ...]:
    """The triaged ball-in-court residue, newest-verdict-first is NOT applied — see below.

    Read through `angles/queues.triaged_residue` rather than by a query of its own, so the
    verdict-joining rule lives in one place: that module reads both tables and writes neither,
    which is what keeps `context_residue` out of a derivation cycle with the verdicts.
    """
    if RESIDUE_BALL_IN_COURT not in TRIAGE_ANGLE_BY_KIND:
        return ()
    rows = triaged_residue(conn, org_id, kind=RESIDUE_BALL_IN_COURT, limit=MAX_PER_SWEEP * 4)
    return tuple(row for row in rows if row.get(TRIAGE_KEY) == ACTIONABLE)


_NAMES = ("select node_id, display_name from graph_nodes "
          "where org_id = :o and valid_to is null")


def gather_display_names(conn, org_id: str) -> dict[str, str]:
    """Node ids to names, for the headline. Guarded by the caller, like every gather here."""
    return {str(r[0]): str(r[1] or "") for r in conn.execute(text(_NAMES), {"o": org_id})}


def read_unreported_attention(rows, now: datetime, names: Mapping[str, str] | None = None,
                              facts: Mapping[str, Mapping[str, Any]] | None = None) -> list:
    """One finding per subject the layer could not explain and a model called material.

    `rows` are already filtered to the actionable verdict by `gather_unreported_attention`; the
    check is repeated here because this function is also the one a test drives directly, and a
    reading that trusts its caller for the rule that decides whether a card exists is a reading
    whose rule lives in two places.
    """
    from genios_engine.context.outreach_situations import _Finding

    findings: list = []
    for row in list(rows)[:MAX_PER_SWEEP]:
        if row.get(TRIAGE_KEY) != ACTIONABLE:
            continue
        node_id = str(row.get("subject_ref") or "").strip()
        if not node_id:
            continue
        held = dict((facts or {}).get(node_id) or {})
        name = str((names or {}).get(node_id) or "").strip() or "this contact"

        card: list[tuple[str, object, str]] = [("attention.counterparty", name, "string")]
        days = _days(now, row.get("first_seen_at"))
        if days is not None:
            card.append(("attention.days_unexplained", days, "number"))
        # THE MODEL'S ANSWER, CARRIED AS WHAT IT IS. Recorded so a reader can see that this card
        # exists on a judgement rather than a measurement — and named `reading`, never `score`,
        # because the angle returns a word and no number here is the model's.
        card.append(("attention.reading", ACTIONABLE, "enum"))
        ball = held.get("thread.ball_in_court")
        if ball:
            card.append(("attention.ball_in_court", str(ball), "string"))
        role = held.get("relationship.nature") or held.get("party.role")
        if role:
            card.append(("attention.counterparty_role", str(role), "enum"))

        headline = (f"{name} — waiting on us, and nothing has said so"
                    if days is None else
                    f"{name} — waiting on us, unreported for {days}d")
        findings.append(_Finding(
            anchor=ANCHOR_UNREPORTED,
            canonical_key=f"unreported:{node_id}",
            display_name=headline,
            facts=card,
            concerns_node=node_id,
            correlation_id=f"unreported:{node_id}",
            # DECLARED, NOT DISCOVERED, and both of these are the point of the card rather than
            # gaps in it. `outreach.days_owed` is the number the deterministic reading would
            # carry; the facts that produce it are the facts whose absence put this subject here.
            # `attention.reason_uncovered` is the question this card asks, not one it answers.
            missing=["outreach.days_owed", "attention.reason_uncovered"],
            inputs={"reading": ANCHOR_UNREPORTED,
                    "derived_from": "context_residue ball_in_court_unreported, triaged "
                                    "`important` by reply_owed_triage; no live situation covers "
                                    "this subject"},
        ))
    return findings


__all__ = ["ACTIONABLE", "ANCHOR_UNREPORTED", "MAX_PER_SWEEP", "SITUATION_TYPE",
           "gather_display_names", "gather_unreported_attention", "read_unreported_attention"]
