"""A conditional promise has no due date — "once legal confirms, by Friday" is not owed until legal confirms.

    pytest tests/context/test_a_conditional_promise_has_no_due_date.py -q

L3 audit, 21 Oct 2026. `qes_adapter` carries `is_conditional` beside the date and the pipeline's commitment
loop read the date and ignored the flag, so a promise waiting on someone else's yes minted
`commitment.due_at` and, once the date passed, a "promise past due" card about work nobody owed yet. The
contract (`contracts.extraction.Commitment`) and the detector (`capture/esqe/detector`) already say a
conditional promise is never dated. Prod, read-only, 21 Oct: 9 of 28 conditional promises carried a date.
The half that must not move: the same promise, unconditional, is still dated.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import create_engine

from genios_engine.context import pipeline
from genios_engine.context.extract.extractor import Extraction

from .test_outbound_is_evidence import THEM, _send, _store
from .test_support_derived_provenance import NOW

BODY = "I will send the signed contract once legal confirms, by Friday."
FRIDAY = (NOW + timedelta(days=3)).isoformat()


def _fields(monkeypatch, conditional: bool | None) -> list[str]:
    engine = create_engine("sqlite://")
    store = _store(monkeypatch, engine)
    written: list[str] = []
    monkeypatch.setattr(store, "write_fact", lambda *a, **kw: written.append(kw.get("field")))
    cm = {"actor": None, "action": "send the signed contract", "due_text": FRIDAY, "evidence_text": BODY}
    if conditional is not None:
        cm["is_conditional"] = conditional
    ex = Extraction(ok=True, relevance=0.9, noise_type="none", domains=[], entity_mentions=[],
                    fact_candidates=[], commitments=[cm], questions=[], observations=[])
    pipeline.process_event(**_send(store, ex, BODY, recipients=(THEM,)))
    engine.dispose()
    return written


def test_a_conditional_promise_mints_no_due_date(monkeypatch):
    fields = _fields(monkeypatch, conditional=True)
    assert "commitment.due_at" not in fields, (
        "a promise waiting on someone else's yes was given a deadline — it goes overdue and becomes a card")
    assert "commitment.last_due_at" not in fields, "the person's pointer to their soonest promise is a deadline too"


def test_the_same_promise_unconditional_is_still_dated(monkeypatch):
    """The half that must not move: a real dated promise still reaches the ledger."""
    fields = _fields(monkeypatch, conditional=False)
    assert "commitment.due_at" in fields
    assert "commitment.last_due_at" in fields


def test_a_promise_that_says_nothing_about_a_condition_is_dated(monkeypatch):
    """An extraction from before the flag existed carries none: only an explicit True withholds the date."""
    assert "commitment.due_at" in _fields(monkeypatch, conditional=None)
