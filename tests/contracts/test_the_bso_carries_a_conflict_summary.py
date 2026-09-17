"""Fixing the lane and not the field turned 23 recoverable holds into hard rejects.

    pytest tests/contracts/test_the_bso_carries_a_conflict_summary.py -q

THE ORIGINAL DEFECT. `situation_publisher._TYPED_LANES` validated the conflict projection against
ALG-12's frozen `Conflict` RECORD. The record embeds both claim bodies and a detection clock; the
reader projects `signal_conflicts` into counted claims with no clock. So the validation required
two fields the projection must not carry and forbade five that it does, and every row was DROPPED
— silently, because `_typed_lanes` drops what does not validate. `carried["conflicts"]` was
always empty and `conflict_open` held all 52 situations that had a disagreement at all.

THE HALF FIX, WHICH WAS WORSE. Changing only the lane's declared type let the rows through to
`BusinessSituationObject.conflicts`, which was still `tuple[Conflict, ...]`. Pydantic then
rejected the whole object: `contract_invalid: 1 validation error ... Input should be a valid
dictionary or instance of Conflict`. Measured on the pilot 2026-09-16, that is 23 situations
moved from HOLD to REJECT — and a hold retries on the next sweep while a reject does not. The
lane and the field have to agree; a type declared in one place and not the other just moves where
the failure happens.

WHAT THE SUMMARY STILL GUARANTEES. "C-10 keeps no winner" survives as `claim_count` and
`event_ids`: a reader can tell that more than one claim existed and which events they came from,
which is what stops the situation reaching Layer 3 looking settled. The losing claim's verbatim
text lives in `signal_conflicts` and is reached through `conflict_ids`.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts.conflict import ConflictSummary
from genios_engine.contracts.situation import BusinessSituationObject

pytestmark = pytest.mark.unit

SUMMARY = ConflictSummary(
    conflict_id="cf_1", signal_id="sig_1", field="deal.stage", subject_key="acct_1",
    resolution="highest_authority", resolved_value="negotiation",
    event_ids=("evt_a", "evt_b"), claim_count=2)


def test_the_field_accepts_what_the_reader_actually_produces() -> None:
    """The lane hands a summary. If the field cannot hold one, the whole object is rejected."""
    field = BusinessSituationObject.model_fields["conflicts"]
    assert field.annotation == tuple[ConflictSummary, ...], (
        "the lane declares ConflictSummary; a field declaring anything else rejects every "
        "situation that has a disagreement at all")


def test_the_summary_still_says_nobody_won() -> None:
    """The property the record was carrying. Without these two the projection would be a claim
    that the disagreement was settled, which is the thing the field exists to prevent."""
    assert SUMMARY.claim_count == 2
    assert SUMMARY.event_ids == ("evt_a", "evt_b")


def test_a_summary_cannot_be_mistaken_for_a_record() -> None:
    """They are different types on purpose, and the summary forbids the record's extra fields —
    so a future edit cannot quietly widen one into the other."""
    with pytest.raises(Exception):
        ConflictSummary(
            conflict_id="cf_1", signal_id="sig_1", field="deal.stage", subject_key="acct_1",
            resolution="highest_authority", resolved_value="negotiation",
            event_ids=("evt_a",), claim_count=2,
            claims=({"value": "closed"},))          # the record's field, refused here


def test_the_lane_and_the_field_declare_the_same_type() -> None:
    """The invariant that was broken. Read from both sides so neither can drift alone."""
    from genios_engine.context.situation_publisher import _TYPED_LANES
    declared = {field: contract for _meta, field, contract in _TYPED_LANES}
    assert declared["conflicts"] is ConflictSummary
    assert BusinessSituationObject.model_fields["conflicts"].annotation == \
        tuple[declared["conflicts"], ...]
