"""L2 · the dormant-condition review queue, surfaced.

**A REVIEW QUEUE IS A SURFACE, NOT A SILENCE.** That sentence is `correlation_timeline`'s own, and
until this module existed it was not true. The correlator does everything it promises: it finds a
conditional statement, names its actor, extracts what that actor will do, keeps the counterparty's
verbatim sentence, and — when `parse_condition` cannot turn the condition into a checkable
predicate — files it under `derived.timeline.condition_review` rather than guessing. That refusal
is correct and deliberate: doc 03's first failure mode is a rhetorical condition matched, and the
stated mitigation is that only a PARSEABLE predicate may auto-fire.

What nobody built was the other half. On the pilot tenant that queue holds **24 conditions**, every
one with an actor, an action, a date and the sentence somebody actually wrote, and not one of them
reaches a card. Among them:

    Theresa Hoffmann, Antler, 7 Aug
      "If there's any changes in the business or updates you can share with us, please feel
       free to do so - always happy to take a look and reconsider."

    Hub71, 25 Aug
      "We'd encourage you to stay engaged so we can continue to track your progress."

    Boardy, 13 Aug
      'Reply with "I want to apply to HF0" and I'll call you to kick off your application'

    Sehan Sanjula, 28 Aug
      'If this isn't relevant, just reply "no" and I'll close the loop'

The first of those is the one that proves the point. Asked what to do about Antler, this system's
own feed reasoned from `follow_up_count = 5` and `days_waiting = 13` and concluded *stop chasing
them* — the exact opposite of what Theresa wrote, sitting unread in this queue since the day she
wrote it. **The intelligence was not missing. It was never surfaced.**

WHAT THIS MODULE DOES NOT DO, and the restraint is the design:

  * It does not parse. A condition whose predicate is `None` stays unparsed here too; this reading
    reports the condition, it does not evaluate it. `condition_now_satisfied` remains the pattern
    for conditions the world can actually check, and this is the queue of the ones it cannot.
  * It does not decide whose move it is. "If I love the company" (theirs) and "if that works for
    you, Rohit" (ours) are both in the queue, and the only deterministic fact available is whether
    the ACTOR is the mailbox owner. That fact is emitted; the inference is not.
  * It does not rank by importance. Age and the counterparty are emitted and the layers above
    decide, because a two-day-old condition from an investor and a two-month-old one from a
    newsletter are not ordered by either field alone.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone

from sqlalchemy import text

#: Where `correlation_timeline` files a condition it could not turn into a predicate. One row per
#: SUBJECT NODE, whose value is `{"review": [ …conditions… ]}` — so a person with four unparsed
#: conditions is one fact carrying four entries, not four facts.
REVIEW_FIELD = "derived.timeline.condition_review"

_REVIEW_ROWS = (
    "select f.subject_node_id as node_id, f.value as value "
    "from graph_facts f "
    "where f.org_id = :o and f.field = :field and f.status = 'active' "
    "and f.valid_to is null "
    "order by f.subject_node_id"
)

#: How many of one node's conditions become findings. A counterparty with a long history can
#: accumulate them, and the newest are the ones still live; the bound stops one busy thread
#: filling a feed. Ordered by `stated_at` descending before the cut, so it is the newest that
#: survive rather than whichever the correlator happened to serialise first.
MAX_PER_NODE = 6

#: A condition older than this is reported without urgency. It is not dropped — an invitation to
#: come back does not expire because the system was slow to show it — but the age travels so a
#: reader can tell a fortnight from a season.
STALE_AFTER_DAYS = 120


def _entries(value) -> tuple[Mapping, ...]:
    """The conditions inside one stored review row, defensively.

    The column is `jsonb` and arrives as a mapping from Postgres and as a string from a driver
    that has not decoded it; both are accepted because this reading must not be the reason a
    tenant's queue is invisible. Anything else yields nothing rather than raising: a malformed
    row is one silent condition, an exception is every condition on the tenant.
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return ()
    if not isinstance(value, Mapping):
        return ()
    review = value.get("review")
    if not isinstance(review, (list, tuple)):
        return ()
    return tuple(item for item in review if isinstance(item, Mapping))


def _stated_at(entry: Mapping) -> datetime | None:
    raw = entry.get("stated_at")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _quote(entry: Mapping) -> str | None:
    """The counterparty's own sentence, which is the whole value of the row.

    `statement` is a list of span mappings exactly as `EvidenceSpan` serialises them. Only the
    quote is taken: the offsets address a `prepared_content` frame this layer does not hold, and
    carrying them here would invite a reader to resolve them against the wrong text.
    """
    statement = entry.get("statement")
    if not isinstance(statement, (list, tuple)):
        return None
    for span in statement:
        if isinstance(span, Mapping):
            quote = str(span.get("quote") or "").strip()
            if quote:
                return quote
    return None


def _normalise_identity(value: str) -> str:
    """Lowercased alphanumerics only, so `"Rohit Swerashi"` and `"mrrohitswerashi@gmail.com"`
    become comparable without a name parser."""
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


#: How many name tokens an actor must carry before a substring match may claim identity. One is
#: not enough: a first name matches any address containing it, and on this tenant that is two
#: different people.
_MIN_IDENTITY_TOKENS = 2


def _is_owner(actor: str, owner: str) -> bool | None:
    """Whether `actor` is the mailbox owner — `None` when the question cannot be answered safely.

    A two-token name that normalises into the owner's address is a match: `"Rohit Swerashi"`
    becomes `rohitswerashi`, which is inside `mrrohitswerashigmailcom`. A single token is refused
    whatever it is, because it cannot distinguish two people who share a first name and this
    mailbox contains exactly that case.
    """
    if not owner or not actor:
        return None
    tokens = [t for t in actor.replace(".", " ").replace("_", " ").split() if t]
    normal_actor, normal_owner = _normalise_identity(actor), _normalise_identity(owner)
    if not normal_actor or not normal_owner:
        return None
    if len(tokens) < _MIN_IDENTITY_TOKENS and "@" not in actor:
        # Ambiguous by construction. Only say so when it might plausibly BE the owner; an actor
        # who shares nothing with the address is confidently not them.
        return None if normal_actor in normal_owner else False
    return normal_actor in normal_owner or normal_owner in normal_actor


def read_conditions_in_review(rows: Mapping[str, object], now: datetime,
                              mailbox_owner: str | None = None) -> list:
    """One finding per unparsed condition. `rows` maps subject node id to the stored review value.

    A condition with no actor, no action and no quote yields nothing — there would be nothing for
    a card to say. Everything else is reported, including the ones whose actor is us: "you told
    them you would reply once it was booked" is as much an open loop as anything they said.
    """
    from genios_engine.context.outreach_situations import _Finding

    owner = (mailbox_owner or "").strip().lower()
    findings: list = []
    for node_id, value in rows.items():
        entries = _entries(value)
        if not entries:
            continue
        ordered = sorted(
            entries,
            key=lambda e: (_stated_at(e) or datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True)[:MAX_PER_NODE]
        for entry in ordered:
            actor = str(entry.get("actor") or "").strip()
            action = str(entry.get("action") or "").strip()
            quote = _quote(entry)
            if not (actor or action or quote):
                continue
            condition_id = str(entry.get("condition_id") or "").strip()
            if not condition_id:
                continue

            facts: list[tuple[str, object, str]] = []
            if actor:
                facts.append(("condition.actor", actor, "string"))
            if action:
                facts.append(("condition.action", action, "string"))
            text_value = str(entry.get("condition_text") or "").strip()
            if text_value:
                facts.append(("condition.text", text_value, "string"))
            if quote:
                facts.append(("condition.quote", quote, "string"))

            stated = _stated_at(entry)
            if stated is not None:
                age = max(0, (now - stated).days)
                facts.append(("condition.stated_at", stated.isoformat(), "string"))
                facts.append(("condition.age_days", age, "number"))
                # Reported, never used to drop. See STALE_AFTER_DAYS.
                facts.append(("condition.stale", age > STALE_AFTER_DAYS, "bool"))

            # THE ONE INFERENCE THIS MODULE IS WILLING TO MAKE, and only when it is safe.
            # Whether the ACTOR is the mailbox owner is a fact; whether the resulting MOVE is ours
            # is a reading of the condition text and is left to the layers that can quote it back.
            #
            # A FIRST NAME IS NOT AN IDENTITY. This tenant carries two Rohits — Rohit Swerashi,
            # the mailbox owner, and Rohit Nallapeta of Crescere Labs — so `"Rohit"` alone matches
            # the owner's address by accident and would mark a counterparty's promise as ours.
            # `_is_owner` returns None for anything that ambiguous, and an absent flag is the
            # honest answer: the queue still surfaces the condition, it just does not claim whose
            # it is.
            owned = _is_owner(actor, owner)
            if owned is not None:
                facts.append(("condition.actor_is_us", owned, "bool"))

            display = f"{actor} — condition awaiting review" if actor else "condition awaiting review"
            findings.append(_Finding(
                anchor=ANCHOR_CONDITION,
                canonical_key=f"condition:{condition_id}",
                display_name=display,
                facts=facts,
                concerns_node=node_id,
                correlation_id=f"condition:{condition_id}",
                # `condition.predicate` is the field that would let this be evaluated rather than
                # reported, and it is absent BY DESIGN for everything in this queue — that absence
                # is why the row is here. Declared so the coverage score says "not evaluable"
                # rather than quietly scoring the reading as complete.
                missing=["condition.predicate"],
                inputs={"reading": ANCHOR_CONDITION,
                        "derived_from": "correlation_timeline review queue; predicate unparsed"},
            ))
    return findings


#: One conditional statement nobody could turn into a predicate. Its own anchor rather than the
#: person's: a counterparty can leave several conditions across months and they are separate open
#: loops, closed separately, and `type_for` maps an anchor to exactly one name per domain.
ANCHOR_CONDITION = "condition"


def gather_conditions_in_review(conn, org_id: str) -> dict[str, object]:
    """The stored review rows for one org, keyed by subject node."""
    rows = conn.execute(text(_REVIEW_ROWS), {"o": org_id, "field": REVIEW_FIELD}).mappings().all()
    return {str(row["node_id"]): row["value"] for row in rows}


__all__ = [
    "ANCHOR_CONDITION",
    "MAX_PER_NODE",
    "REVIEW_FIELD",
    "STALE_AFTER_DAYS",
    "gather_conditions_in_review",
    "read_conditions_in_review",
]
