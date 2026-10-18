"""STEP-05 · a mail the qualification floor did not publish enters memory with its words.

    pytest tests/context/test_a_mail_below_the_floor_keeps_its_words.py -q

Tree `yc2_w27_s05 · M23.C3.L-logic.V2.U01` and `U06`, decision `06` D20. A mail Layer 1 READ and the floor
did not publish has its extraction already — Neel Jain's question, Manik's traction ask. The adapter
projects it exactly as it projects a signal's, with no model call, at a confidence below the pipeline's
ranking floor — and that relevance, on every claim, is the whole mark (`03` F69: no confidence of its
own exists for a floor refusal).

RESTATED (U06). U01 also wrote an `l1.below_floor` observation whose evidence was the extraction's first
span; on five golden cases that span was a bare name, and the card narrator was handed it as something
the counterparty wrote. An observation's evidence is read as a quote by every reader of quotes, so the
mark is not one: the projection carries only what the mail said.
"""
from __future__ import annotations

from genios_engine.context.pipeline import RELEVANCE_FLOOR
from genios_engine.context.qes_adapter import BELOW_FLOOR_CONFIDENCE_BP, adapt_qes_extraction
from tests.context.test_qes_adapter import extraction


def test_below_the_floor_the_claims_are_the_same_claims():
    signal = adapt_qes_extraction(extraction(), confidence_bp=8000)
    below = adapt_qes_extraction(extraction(), confidence_bp=BELOW_FLOOR_CONFIDENCE_BP)
    assert below.commitments == signal.commitments
    assert below.questions == signal.questions
    assert below.fact_candidates == signal.fact_candidates
    assert below.input_tokens == below.output_tokens == 0          # no model call


def test_it_ranks_below_the_floor_and_carries_nothing_the_mail_did_not_say():
    below = adapt_qes_extraction(extraction(), confidence_bp=BELOW_FLOOR_CONFIDENCE_BP)
    assert below.relevance < RELEVANCE_FLOOR
    assert below.observations == adapt_qes_extraction(extraction(), confidence_bp=8000).observations
    assert all(not o["kind"].startswith("l1.") for o in below.observations)


def test_the_adapter_takes_no_below_floor_flag():
    """The mark is the confidence the caller passes; there is no second way to say it."""
    import inspect

    assert "below_floor" not in inspect.signature(adapt_qes_extraction).parameters
