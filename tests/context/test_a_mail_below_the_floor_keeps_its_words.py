"""STEP-05 · a mail the qualification floor did not publish enters memory with its words.

    pytest tests/context/test_a_mail_below_the_floor_keeps_its_words.py -q

Tree `yc2_w27_s05 · M23.C3.L-logic.V2.U01`, decision `06` D20. A mail Layer 1 READ and the floor did not
publish has its extraction already — Neel Jain's question, Manik's traction ask. The adapter projects it
exactly as it projects a signal's, with no model call, at a confidence below the pipeline's ranking
floor, and says where it came from: an `l1.below_floor` observation beside the claims.
"""
from __future__ import annotations

from genios_engine.context.pipeline import RELEVANCE_FLOOR
from genios_engine.context.qes_adapter import BELOW_FLOOR_CONFIDENCE_BP, adapt_qes_extraction
from tests.context.test_qes_adapter import QUOTE, extraction


def test_below_the_floor_the_claims_are_the_same_claims():
    signal = adapt_qes_extraction(extraction(), confidence_bp=8000)
    below = adapt_qes_extraction(extraction(), confidence_bp=BELOW_FLOOR_CONFIDENCE_BP,
                                 below_floor=True)
    assert below.commitments == signal.commitments
    assert below.questions == signal.questions
    assert below.fact_candidates == signal.fact_candidates
    assert below.input_tokens == below.output_tokens == 0          # no model call


def test_it_ranks_below_the_floor_and_says_why():
    below = adapt_qes_extraction(extraction(), confidence_bp=BELOW_FLOOR_CONFIDENCE_BP,
                                 below_floor=True)
    assert below.relevance < RELEVANCE_FLOOR
    assert {"kind": "l1.below_floor", "evidence_text": QUOTE} in below.observations


def test_a_signal_carries_no_below_floor_mark():
    signal = adapt_qes_extraction(extraction(), confidence_bp=8000, signal_types=["contract_renewal"])
    assert all(o["kind"] != "l1.below_floor" for o in signal.observations)
