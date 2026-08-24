"""The stable identity of ONE unresolved request — the unit completion closes.

Root cause #2 of the shallowness report (RC-2 / B-02): nothing in the system named a REQUEST.
Completion authority was the person-wide `thread.ball_in_court` — one bit per human — so
answering any of somebody's three questions read as answering all of them, a card expiring
read as the request resolving, and the same signal re-surfaced for eleven subjects because
"the card is gone" and "the loop is closed" were indistinguishable.

An open loop is identified by WHO asked, WHAT KIND of thing they asked for, and WHERE the ask
lives (its thread). Deliberately NOT by the event id — a follow-up email repeating the same
ask is the same loop, not a second one — and NOT by the ask's text, which rephrases freely
between reminders. Content-addressed and deterministic: the same ask re-extracted tomorrow, by
a different model version, lands on the same id, which is what lets a completion matcher close
exactly one request and a regeneration gate ask "is THIS loop still open" instead of "does a
card exist".
"""
from __future__ import annotations

import hashlib

#: Observation kinds that constitute a REQUEST — something a counterparty is waiting on.
#: Mirrors the ask-signal vocabulary the actionability gate and the unanswered_email rule
#: already use; a kind outside this set is information, not an open loop.
ASK_KINDS: frozenset[str] = frozenset({
    "question", "meeting_request", "proposal_sent", "demo_requested",
    "contract_requested", "next_step_agreed", "objection", "pricing_objection",
    "introduction",
})


def open_loop_id(*, org_id: str, subject_node_id: str, kind: str,
                 thread_id: str | None = None) -> str:
    """The deterministic identity of one unresolved ask.

    ``thread_id`` scopes two same-kind asks from the same person to their conversations — two
    questions on two threads are two loops. When no thread is known the loop is person-wide for
    that kind, which is the honest floor: coarser than ideal, still infinitely finer than one
    ball_in_court bit per person.
    """
    basis = f"{org_id}:{subject_node_id}:{kind}:{thread_id or 'no_thread'}"
    return "loop_" + hashlib.sha256(basis.encode()).hexdigest()[:24]


def is_ask(kind: str | None) -> bool:
    return (kind or "") in ASK_KINDS


__all__ = ["ASK_KINDS", "is_ask", "open_loop_id"]
