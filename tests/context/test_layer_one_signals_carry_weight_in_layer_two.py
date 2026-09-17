"""Every signal Layer 1 publishes has to MEAN something here, or it is recorded and ignored.

`observations/kinds.yaml` opens by naming the failure it was built to end: a kind could be
authored at the extraction end and hardcoded at the meaning end, so *"a new kind reached the graph
and then scored ZERO everywhere: neutral sentiment, not an ask, not progress. Not refused, not
flagged — silently weightless."*

That was still happening, to Layer 1's own vocabulary. `capture/esqe/classifier.PRECEDENCE`
publishes fifteen signal types and `context/qes_adapter` turns each one straight into an
observation `kind` — no filter, no gate. Thirteen of the fifteen had no row here, so every
`risk_flagged`, `escalation`, `decision_pending`, `contract_renewal` and `commitment_made` the
system recorded contributed nothing to `derived.sentiment`, nothing to `derived.momentum` and
nothing to whether anybody was waiting on an answer.

THE FIRST TEST IS THE ONE THAT MATTERS. It does not check the thirteen rows this unit added — it
checks that L1's census and L2's vocabulary AGREE, so the sixteenth signal type somebody adds
upstream fails here instead of being quietly ignored for a year.
"""
import pytest

from genios_engine.capture.esqe.classifier import PRECEDENCE
from genios_engine.context.vocabulary import OBSERVATION_MEANINGS, kinds_where


def observation_meaning(kind: str):
    """The row for one kind, or None. A helper rather than an import: `OBSERVATION_MEANINGS` is
    the mapping the engine reads, and going through it keeps this test honest about what the
    engine would actually find."""
    return OBSERVATION_MEANINGS.get(kind)

L1_TYPES = frozenset(str(signal.value) for signal in PRECEDENCE)


def test_every_layer_one_signal_type_has_a_meaning_here() -> None:
    """THE GUARD, not the fix. `qes_adapter` passes L1's signal type through as a `kind` with no
    translation and no gate, so a type with no row here is recorded and weightless — the exact
    failure this file's own header describes, pointed at our own upstream."""
    missing = sorted(L1_TYPES - set(OBSERVATION_MEANINGS))
    assert missing == [], (
        f"Layer 1 publishes {missing} and Layer 2 gives them no meaning. `qes_adapter` writes "
        f"them to the graph regardless, where they score neutral, not-an-ask and not-progress "
        f"in silence. Add a row to observations/kinds.yaml.")


def test_the_five_that_were_being_thrown_away_now_land_somewhere() -> None:
    """Named individually because these are the ones a founder would expect to change a card."""
    for kind in ("risk_flagged", "escalation", "decision_pending", "contract_renewal",
                 "commitment_made"):
        assert observation_meaning(kind) is not None, kind


def test_the_unambiguous_ones_carry_their_direction() -> None:
    assert observation_meaning("risk_flagged").polarity == "negative"
    assert observation_meaning("escalation").polarity == "negative"
    assert observation_meaning("opportunity_signal").polarity == "positive"


def test_a_decision_and_a_commitment_count_as_movement() -> None:
    """`derived.momentum` is the observation balance for "did this relationship move". A promise
    made and a decision reached both did; `decision_deferred` next door is the negative twin."""
    progress = kinds_where(is_progress=True)
    assert {"commitment_made", "decision_made"} <= progress


@pytest.mark.parametrize("kind", sorted(L1_TYPES - {"approval_requested"}))
def test_no_direction_agnostic_signal_is_marked_as_an_ask(kind: str) -> None:
    """THE DECISION THIS UNIT REFUSED TO MAKE, pinned so nobody makes it later by accident.

    `is_ask` means WE put a question to them and are owed an answer. L1's types do not carry
    direction — `commitment_made` is a promise by somebody, `decision_pending` is a decision
    somewhere. `waiting.py` records exactly what marking a direction-agnostic kind as an ask
    costs, measured on this tenant: outbound mail produced 425 observations across two subject
    nodes, "so when Rohit pitched eleven VCs, the ask landed on Rohit's own node and never on
    theirs", and every one of them read as `response_expected = false`.

    `approval_requested` is excluded because it names its own direction and was already here.
    """
    meaning = observation_meaning(kind)
    assert meaning is not None and meaning.is_ask is False, kind


def test_neutral_is_used_where_the_type_carries_no_direction() -> None:
    """Guessing a polarity does not add signal, it adds a bias to `derived.sentiment` nobody can
    trace back. An anomaly can be a surprise order or a churn signal; a `relationship_change` can
    be a champion arriving or leaving."""
    for kind in ("anomaly", "availability_change", "relationship_change", "decision_made",
                 "decision_pending", "commitment_due", "commitment_made", "contract_renewal",
                 "financial_obligation", "information_conflict"):
        assert observation_meaning(kind).polarity == "neutral", kind


def test_the_vocabulary_still_loads_as_one_file() -> None:
    """`kinds_where` reads this file at import and both `waiting.py` and `derived.py` fall back to
    a hardcoded literal when it returns empty — a malformed row would silently restore the
    three-Python-literals world this file was written to end."""
    assert len(OBSERVATION_MEANINGS) >= 64
    assert kinds_where(is_ask=True) and kinds_where(is_progress=True)
