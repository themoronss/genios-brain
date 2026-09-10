"""L1-02 — three word lists decided whether a message raised a signal at all.

    pytest tests/capture/esqe/test_the_customers_own_words_can_reach_a_signal.py -q

Anisha's clinic writes *"three no-shows this week and the ultrasound room is down for
calibration"*. No token in `RISK_TOKENS` matches — `no-show` and `calibration` are not in it —
no Commitment, no ResolvedDate, no Money, so `_detect_all` returns `[]`. Then
`classify_signals` returns None, `normalized` is empty, `importance` is an empty tuple, and the
ESQE trace records `signal_type=None, signals=0`.

The message was read, extracted, judged business-relevant, and produced NO SIGNAL — because no
Python predicate recognised the customer's own vocabulary. Same shape as the
`thread.objective` zero-facts bite, one layer earlier.
"""

from __future__ import annotations

import textwrap

import pytest

from genios_engine.capture.esqe.detector import (
    RENEWAL_MATCH,
    RENEWAL_TOKENS,
    RISK_MATCH,
    RISK_TOKENS,
    load_token_predicates,
)

pytestmark = pytest.mark.unit


def table(tmp_path, body: str, name: str = "authored.yaml"):
    (tmp_path / name).write_text(textwrap.dedent(body))
    return tmp_path


# =============================================================================================
# Today is unchanged.
# =============================================================================================
def test_the_shipped_tables_are_byte_identical():
    """`tokens/shipped.yaml` is a transcription of the literals; a drift between the two would
    silently widen or narrow detection for every tenant."""
    assert RENEWAL_MATCH == RENEWAL_TOKENS
    assert RISK_MATCH == RISK_TOKENS


# =============================================================================================
# The clinic.
# =============================================================================================
def test_a_clinics_words_can_reach_an_existing_signal(tmp_path):
    root = table(tmp_path, """
        predicates:
          - signal_type: RISK_FLAGGED
            predicate_id: risk_topic
            tokens: [no-show, calibration, recall]
    """)

    got = load_token_predicates(root)

    assert {"no-show", "calibration", "recall"} <= got["risk_topic"]


def test_authored_tokens_add_and_never_replace(tmp_path):
    root = table(tmp_path, """
        predicates:
          - {signal_type: RISK_FLAGGED, predicate_id: risk_topic, tokens: [no-show]}
    """)
    # The shipped table sits in the real directory; here we assert the merge SHAPE, then that
    # the live constant still contains every original word.
    assert "no-show" in load_token_predicates(root)["risk_topic"]
    assert RISK_TOKENS <= RISK_MATCH


def test_two_files_both_contribute(tmp_path):
    table(tmp_path, "predicates:\n  - {signal_type: RISK_FLAGGED, predicate_id: risk_topic, "
                    "tokens: [alpha]}\n", "a.yaml")
    table(tmp_path, "predicates:\n  - {signal_type: RISK_FLAGGED, predicate_id: risk_topic, "
                    "tokens: [beta]}\n", "b.yaml")

    got = load_token_predicates(tmp_path)

    assert {"alpha", "beta"} <= got["risk_topic"]


def test_tokens_are_lowercased_the_way_topic_tokens_are(tmp_path):
    root = table(tmp_path, "predicates:\n  - {signal_type: RISK_FLAGGED, "
                           "predicate_id: risk_topic, tokens: ['No-Show', ' RECALL ']}\n")

    assert {"no-show", "recall"} <= load_token_predicates(root)["risk_topic"]


# =============================================================================================
# What a row may not do.
# =============================================================================================
def test_a_row_cannot_mint_a_signal_type(tmp_path):
    """`SignalType` is a REJECT boundary, the key of the precedence order and of the type
    weight, and its own docstring states the governance for adding one — a schema version bump
    plus corpus review. This lane widens the WORDS that reach an existing kind."""
    root = table(tmp_path, "predicates:\n  - {signal_type: CLINICAL_ALERT, "
                           "predicate_id: clinical, tokens: [sepsis]}\n")

    assert load_token_predicates(root) == {}


def test_a_row_with_no_predicate_id_is_skipped(tmp_path):
    """The predicate id is what lands in the receipt; a fire nobody can explain is not a fire
    worth having."""
    root = table(tmp_path, "predicates:\n  - {signal_type: RISK_FLAGGED, tokens: [x]}\n")

    assert load_token_predicates(root) == {}


def test_a_row_with_no_tokens_is_skipped(tmp_path):
    root = table(tmp_path, "predicates:\n  - {signal_type: RISK_FLAGGED, "
                           "predicate_id: risk_topic, tokens: []}\n")

    assert load_token_predicates(root) == {}


# =============================================================================================
# It fails soft.
# =============================================================================================
def test_one_unreadable_table_does_not_blind_the_others(tmp_path):
    table(tmp_path, "predicates: [unclosed\n", "broken.yaml")
    table(tmp_path, "predicates:\n  - {signal_type: RISK_FLAGGED, predicate_id: risk_topic, "
                    "tokens: [alpha]}\n", "good.yaml")

    assert "alpha" in load_token_predicates(tmp_path)["risk_topic"]


def test_a_missing_directory_leaves_the_literals_standing(tmp_path):
    assert load_token_predicates(tmp_path / "does-not-exist") == {}
    assert RISK_MATCH == RISK_TOKENS


def test_the_claim_shaped_predicates_did_not_move():
    """Commitment, ResolvedDate, Money and Conflict read typed contract objects and are
    genuinely universal — a promise is a promise in every business. They must not become
    authorable."""
    import inspect

    from genios_engine.capture.esqe import detector

    source = inspect.getsource(detector._detect_all)

    assert "ex.commitments" in source or "Commitment" in source
    assert "load_token_predicates" not in source
