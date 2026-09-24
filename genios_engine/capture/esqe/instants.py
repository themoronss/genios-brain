"""L1.6.x · THE TEMPORAL FIELD SET AND REPLY PAIRING — a timestamp is not temporal meaning.

`QualifiedEnterpriseSignal` carried three `_at` fields and one of them is a processing fact:

    occurred_at · expires_at · ingested_at(processing)

**So a signal cannot say "8 days overdue."** The deadline lives inside `Commitment.due`, a claim
nested in the extraction, and nothing can sort or sweep by a value that deep. P2 asks exactly that
question and the object L2 receives cannot answer it.

**REPLY PAIRING BELONGS IN L1 AND WAS NOT HERE.** `structural/threads.py` already computes
`last_inbound_at`, `last_outbound_at`, `turn_index` and `ball_in_court`. The LATENCY is computed in
`context/waiting.py` — Layer 2 — but the pairing itself (this inbound, that outbound, Δt) is
**mechanical**: no judgement, no context, no model.

The JUDGEMENT is not: Claude's *"binary responder: 9 of 14 under 30 minutes"* is a pattern over many
pairs, one pair cannot support it, and §9 keeps it in L2. This module offers no median, no
percentile and no label — a function called `is_fast_responder()` would invite a caller to ask it of
a single exchange.

⛔ **§5's 14-U5: the two rules are MOVED, NOT REWRITTEN.** `context/waiting.py` was read first, as
§8 requires, and its logic is reproduced here exactly:

    pending = None
    for direction, at in timeline:
        if direction == "out":
            if pending is None:        # consecutive outbounds: only the FIRST is pending
                pending = at
        elif pending is not None:      # only the FIRST reply after an outbound counts
            gaps.append(...); pending = None

Its docstring states both in words: *"a thread where they answered once and then sent four more
messages describes one reply latency, not five. Consecutive outbounds with no reply between them
contribute nothing — an unanswered message has no latency yet, and **scoring it as zero would make a
silent counterparty look fast**."*

**ONE DELIBERATE DIFFERENCE.** `waiting.py` returns float days (`total_seconds() / 86400.0`). That
is fine inside L2 and not fine crossing a seam — V-7, and a float reaches jsonb as a number nobody
can trace back to two timestamps. This emits **integer seconds**: same pairing, same rules, a unit
that survives storage.

PURE: no clock, no I/O, no model. Every instant is a parameter, so a replay of last week produces
last week's answer.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

#: The direction values this module reads, matching `structural/threads.Direction`.
OUTBOUND = "out"
INBOUND = "in"


@dataclass(frozen=True, slots=True)
class ReplyTurn:
    """One message in a thread, as the pairing sees it.

    `is_auto_reply` is SUPPLIED rather than detected here. E7's rule already exists —
    `gate/rules.availability_marker` returns `AUTO_REPLY` — and 14-U5 forbids a second version: two
    regexes for one rule is how the gate and this module come to disagree about what an
    out-of-office is.
    """

    message_id: str
    direction: str
    at: datetime
    is_auto_reply: bool = False


@dataclass(frozen=True, slots=True)
class ReplyPair:
    """One outbound answered by one inbound, with the gap between them.

    BOTH IDS, because E6: *"the pair is by message id, not by content."* A reply that quotes the
    whole thread is still one message answering one message, and a content-based pairing would
    match the quotation instead of the reply.
    """

    outbound_message_id: str
    inbound_message_id: str
    #: INTEGER SECONDS. See the module docstring on why this is not float days.
    latency_seconds: int


def due_at_of(commitments: Iterable[object]) -> datetime | None:
    """The soonest deadline any of these commitments carries, or None.

    **LIFTED, NEVER RE-DERIVED** (§9). `Commitment.due` is a `ResolvedDate` ALG-09 already produced,
    with a certainty and a window. A second derivation here would be a second answer to a question
    the extraction has already answered, and the two drift the first time the cascade changes.

    THE FAR END OF A RANGE, and that is the same argument step 12 makes. *"Next Friday"* is a range,
    and a promise is overdue when the range the speaker actually committed to has passed. Taking the
    near end invents a deadline — the failure `Commitment`'s own contract names: *"an invented
    deadline must not be able to produce a false overdue."* The range is not destroyed; it stays on
    the claim where ALG-09 put it.

    THE SOONEST WINS when a signal rests on several. A sweep asking *"what is overdue"* must not
    miss the earlier of two because the later one happened to be stored.
    """
    deadlines: list[datetime] = []
    for commitment in commitments:
        due = getattr(commitment, "due", None)
        if due is None:
            continue
        latest = getattr(due, "latest", None)
        if isinstance(latest, datetime):
            deadlines.append(latest)
    return min(deadlines) if deadlines else None


def pair_replies(turns: Sequence[ReplyTurn]) -> tuple[ReplyPair, ...]:
    """Pair each outbound with the counterparty's next real reply. 14-U4.

    **The two rules are `context/waiting.py`'s, moved rather than reinvented** — see the module
    docstring for its code and its own words. In this loop they are:

    * ``if pending is None`` — consecutive outbounds contribute ONE latency, measured from the
      first. An unanswered message has no latency yet, and scoring it as zero would make a silent
      counterparty look fast;
    * ``pending = None`` after a pair — only the FIRST reply after an outbound counts. They
      answered once and then sent four more messages: that is one reply latency, not five.

    **An auto-reply is skipped entirely** (E7). An out-of-office arriving four minutes after a pitch
    is not a four-minute response time, and letting it pair would make every unreachable
    counterparty the fastest in the graph. The `pending` outbound is deliberately LEFT pending, so
    the real reply — whenever it comes — still pairs with it.

    Sorted by time first: a page can arrive newest-first, and pairing an out-of-order timeline would
    produce negative latencies, which reads as "they replied before we wrote".
    """
    ordered = sorted(turns, key=lambda t: (t.at, t.message_id))
    pairs: list[ReplyPair] = []
    pending: ReplyTurn | None = None

    for turn in ordered:
        if turn.direction == OUTBOUND:
            if pending is None:
                pending = turn
        elif turn.direction == INBOUND:
            if turn.is_auto_reply:
                continue                       # E7 — never the counterparty answering
            if pending is not None:
                pairs.append(ReplyPair(
                    outbound_message_id=pending.message_id,
                    inbound_message_id=turn.message_id,
                    latency_seconds=int((turn.at - pending.at).total_seconds())))
                pending = None
    return tuple(pairs)


__all__ = ["INBOUND", "OUTBOUND", "ReplyPair", "ReplyTurn", "due_at_of", "pair_replies"]
