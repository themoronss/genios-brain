"""D10 · thread context reaches S4 — whose turn it is, and which thread this is about.

    pytest tests/capture/esqe/test_thread_context.py -q

`capture/structural/threads.py` reconstructs direction, turn index and `ball_in_court`, and
`capture/validate/claim_group.py` rung 4 groups a claim by its THREAD. Neither reached the ESQE
stage: `run_esqe_stage` called `normalize_signals` with no `thread_key` at all, so every signal
on an ordinary email thread fell to ALG-22's last rung — `event:{event_id}` — and two messages
of ONE conversation produced two subjects that nothing downstream could ever join. And a signal
was classified without knowing whose turn it was, which is exactly the difference between "they
are waiting on us" and "we are waiting on them".

Every test here goes through `pipeline.run_esqe_stage` or `pipeline.capture_event` — the
production entry points — because a thread context supplied by a test proves the unit and not
the wiring.
"""

from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture import pipeline as P
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.esqe.normalize import ThreadContext
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import Commitment, ExtractionResult

OWNER = "founder@genios.ai"
COUNTERPARTY = "buyer@acme.com"
NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
BODY = ("Confirming the annual contract renewal — we still need Finance to approve the budget "
        "before the deal can move forward.")


class RaisingLLM:
    model = "must-not-be-called"

    def call(self, prompt: str, *, max_tokens: int = 4096):
        raise AssertionError("LLM-5 must not be called on a rules path")


def _raw(**over) -> RawObject:
    kwargs = dict(source="gmail", object_type="email_message", source_object_id="m_1",
                  occurred_at=NOW, actor_email=COUNTERPARTY, recipients=(OWNER,),
                  parent_object_id="t_renewal",
                  raw={"subject": "Renewal", "body": BODY})
    raw = dict(kwargs["raw"])
    raw.update(over.pop("raw", {}))
    kwargs.update(over)
    kwargs["raw"] = raw
    return RawObject(**kwargs)


def _event_for(raw: RawObject):
    return P.land_raw_object(raw, org_id="org_thread", connection_id="con_thread",
                             repo=InMemorySourceEventRepository(),
                             mailbox_owner=OWNER).event


def _span(quote: str) -> EvidenceSpan:
    start = BODY.index(quote)
    return EvidenceSpan(source_ref="prepared_content:evt_thread", quote=quote,
                        start_offset=start, end_offset=start + len(quote))


def _extraction() -> ExtractionResult:
    commitment = Commitment(actor=COUNTERPARTY, action="approve the renewal",
                            is_conditional=False, confidence_bp=9000,
                            evidence=[_span("Confirming the annual contract renewal")])
    return ExtractionResult(intent="commit", stance="positive", commitments=[commitment],
                            model_snapshot="test-model", prompt_version="v1",
                            schema_version="1", extraction_profile="general",
                            input_tokens=10, output_tokens=10)


def _stage(**over) -> P.EsqeStage:
    kwargs = dict(eval_time=NOW, relevance_llm=RaisingLLM())
    kwargs.update(over)
    return P.EsqeStage(**kwargs)


def _run(raw: RawObject, **over):
    kwargs = dict(stage=_stage(), extraction=_extraction(), conflicts=None,
                  sender_known=True, is_structured=False, mailbox_owner=OWNER)
    kwargs.update(over)
    return P.run_esqe_stage(_event_for(raw), None, raw.raw, **kwargs)


# =============================================================================================
# ALG-22 rung 4 — the thread is the subject when nothing more specific is.
# =============================================================================================
def test_two_messages_of_one_thread_derive_one_subject():
    """The grouping this defect destroyed. Two events, one conversation: without a thread key
    every signal anchors on its own `event_id` and the two can never be compared."""
    first = _run(_raw(source_object_id="m_1"))
    second = _run(_raw(source_object_id="m_2", raw={"body": BODY}))

    assert first.normalized and second.normalized
    assert first.normalized[0].subject_key.startswith("thread:t_renewal")
    assert first.normalized[0].subject_key == second.normalized[0].subject_key


def test_a_message_with_no_thread_still_anchors_on_its_own_event():
    """No parent, no thread rung — ALG-22's last rung, not a crash and not a fabricated key."""
    outcome = _run(_raw(parent_object_id=None))

    assert outcome.thread.thread_key is None
    assert outcome.normalized[0].subject_key.startswith("event:")


def test_an_attachments_parent_is_its_message_and_never_a_thread():
    """`claim_group.thread_group_key` refuses this case in as many words: an attachment's
    unresolved parent is a MESSAGE, and answering `thread:<message id>` mints a private thread
    for a file and quietly orphans it."""
    outcome = _run(_raw(object_type="email_attachment", source_object_id="f_1",
                        parent_object_id="m_1"))

    assert outcome.thread.thread_key is None
    assert not outcome.normalized[0].subject_key.startswith("thread:m_1")


# =============================================================================================
# Whose turn it is.
# =============================================================================================
def test_a_signal_states_whose_turn_it_is():
    """They spoke last, so we owe the reply — `structural/threads.py`'s own rule, applied to the
    newest message of the thread, which at capture time is this event."""
    inbound = _run(_raw(actor_email=COUNTERPARTY))
    outbound = _run(_raw(actor_email=OWNER, recipients=(COUNTERPARTY,)))

    assert inbound.thread.ball_in_court == "us"
    assert inbound.thread.direction == "inbound"
    assert outbound.thread.ball_in_court == "them"
    assert outbound.thread.direction == "outbound"
    assert inbound.normalized[0].thread is inbound.thread, (
        "a normalized signal that does not carry its thread cannot say whose turn it is")


def test_no_mailbox_identity_refuses_to_guess_whose_turn_it_is():
    """With no identity for "us" every message looks inbound — the bug that modelled a
    product's own onboarding mail as a prospect asking for a demo. Unknown is the answer."""
    outcome = _run(_raw(), mailbox_owner=None)

    assert outcome.thread.direction is None
    assert outcome.thread.ball_in_court == "unknown"


def test_the_turn_index_is_the_connectors_position_not_a_guess():
    outcome = _run(_raw(raw={"thread_position": 3, "thread_depth": 5}))

    assert outcome.thread.turn_index == 2 and outcome.thread.thread_depth == 5


# =============================================================================================
# Through the real door, with nothing wired.
# =============================================================================================
def test_thread_context_reaches_the_trace_through_capture_event():
    """The trace row is where an operator asks "why was this signal about that?" — a thread
    context that never lands in it is unauditable."""
    res = P.capture_event(_raw(), org_id="org_thread", connection_id="con_thread",
                          repo=InMemorySourceEventRepository(), mailbox_owner=OWNER,
                          sender_known=True, esqe=_stage())

    row = next(r for r in res.trace.records if r.stage == P.ESQE_STAGE)
    assert row.detail["thread_key"] == "thread:t_renewal"
    assert row.detail["ball_in_court"] == "us"
    assert res.esqe.thread == ThreadContext(thread_key="thread:t_renewal", direction="inbound",
                                            turn_index=0, thread_depth=1, ball_in_court="us")
