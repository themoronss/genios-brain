"""L2.7.7-U1 step 5a · THE LEDGER — many claims about one situation, reduced to one word.

`decide_lifecycle` takes a single `stated_resolution`. This module is what produces it, and it
produces it by RE-READING every stored claim on every pass rather than by remembering what it
decided last time. That is the whole of why a statement-resolution is reversible: nothing here
is a latch. A contradiction that lands tomorrow does not "undo" anything — it changes what this
function computes, and the situation follows.

TWO RULES, AND THEY ARE THE TWO THE PLAN NAMES:

**LATEST STATEMENT WINS** (doc 07 failure mode 5). Claims are walked oldest to newest and a
`CONTRADICTED` claim CLEARS everything before it. *"done"* … *"actually not yet"* therefore ends
open, and the reverse order ends closed, which is the same rule read forwards.

**SCOPE ACCUMULATES, AND COVERAGE IS COMPARED TO WHAT IS STILL OPEN** (doc 12 case 2). Three of
five discharged on Monday and the other two on Thursday is a resolution on Thursday, without
anyone re-stating the first three. And a SIXTH obligation appearing on Friday drops the same
situation back to `partial` by itself — the comparison is against today's open set, not against
the set the claims were made about, so a situation cannot stay closed because it was closed
before the rest of the work arrived.

ORDERING IS `(stated_at, event_id)` AND NOT `created_at`. What matters is when the sentence was
WRITTEN, not when we got round to reading it: a backfill that ingests last week's thread out of
order must reach the same answer as a live drain, or a re-sync would silently re-close a
situation somebody's later message had already reopened.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from genios_engine.context.lifecycle.contract import (
    DECISION_APPLY,
    VERDICT_CONTRADICTED,
    VERDICT_PARTIALLY_RESOLVED,
    VERDICT_RESOLVED,
    ResolutionClaim,
)
from genios_engine.context.lifecycle.judge import SITUATION_SCOPE
from genios_engine.context.situations import (
    STATEMENT_NONE,
    STATEMENT_PARTIAL,
    STATEMENT_RESOLVED,
)

__all__ = ["StatementState", "derive_statement_state"]


@dataclass(frozen=True, slots=True)
class StatementState:
    """What the ledger says right now, and the evidence for saying it."""

    #: One of `situations.STATEMENT_*` — the word `decide_lifecycle` reads.
    state: str
    #: Which obligation ids are covered by live claims (after the last contradiction).
    covered: tuple[str, ...] = ()
    #: Which are not. Empty for a full resolution; the remainder of the work for a partial.
    outstanding: tuple[str, ...] = ()
    #: True when the newest applied claim is a contradiction — the reopen, for the ledger.
    contradicted: bool = False
    #: WHEN the newest live claim was written. This becomes the situation's `resolved_at`: a
    #: situation resolved by a sentence written on Tuesday was resolved on Tuesday, and the
    #: existing reopen rule compares `last_seen_at` against exactly that instant. Reading the
    #: clock here instead would make every re-derivation move the resolution forward in time and
    #: no later message could ever post-date it.
    resolved_at: datetime | None = None


def _key(claim: ResolutionClaim):
    return (claim.stated_at, claim.event_id)


def derive_statement_state(claims: Sequence[ResolutionClaim],
                           open_obligation_ids: Iterable[str] = ()) -> StatementState:
    """Reduce a situation's claims to one of the three words, with its scope.

    Only `decision == "apply"` claims are read. A claim in the review queue has NOT been
    accepted by anyone — it is a question waiting for a human — and a queue entry that quietly
    moved the lifecycle would make the floor decorative.
    """
    applied = sorted((c for c in claims if c.decision == DECISION_APPLY), key=_key)
    covered: set[str] = set()
    contradicted = False
    stated_at: datetime | None = None
    for claim in applied:
        if claim.verdict == VERDICT_CONTRADICTED:
            covered.clear()
            stated_at = None
            contradicted = True
            continue
        if claim.verdict in (VERDICT_RESOLVED, VERDICT_PARTIALLY_RESOLVED):
            covered.update(claim.scope)
            stated_at = claim.stated_at
            contradicted = False

    open_ids = [str(o) for o in open_obligation_ids]
    if not covered:
        return StatementState(STATEMENT_NONE, contradicted=contradicted)

    if not open_ids:
        # No per-obligation breakdown: the claim is about the situation itself, and the sentinel
        # is the only thing it can have covered.
        if SITUATION_SCOPE in covered:
            return StatementState(STATEMENT_RESOLVED, covered=tuple(sorted(covered)),
                                  contradicted=contradicted, resolved_at=stated_at)
        return StatementState(STATEMENT_PARTIAL, covered=tuple(sorted(covered)),
                              contradicted=contradicted, resolved_at=stated_at)

    outstanding = tuple(sorted(set(open_ids) - covered))
    if not outstanding:
        return StatementState(STATEMENT_RESOLVED, covered=tuple(sorted(covered)),
                              contradicted=contradicted, resolved_at=stated_at)
    return StatementState(STATEMENT_PARTIAL, covered=tuple(sorted(covered)),
                          outstanding=outstanding, contradicted=contradicted,
                          resolved_at=stated_at)
