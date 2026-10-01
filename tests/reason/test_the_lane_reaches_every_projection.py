"""S3.F3.3 · the lane reaches the rows that render — and stops where it would duplicate itself.

    pytest tests/reason/test_the_lane_reaches_every_projection.py -q

⛔ THIS FILE IS THE ANTI-`not_carried` GUARD FOR S3. A lane computed in the decision maker and absent
from the card is the seventh instance of the shape this programme keeps finding: a value computed
correctly and dropped at a boundary.

`contracts/reasoning.DECISION_PROJECTIONS` documents the five places a decision is projected to and the
single writer each has. The lane reaches the two that matter and deliberately not the rest — see
`test_the_audited_row_is_not_given_duplicate_columns`.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from genios_engine.contracts.reasoning import OUTPUT_LANES, ReasoningDecision

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_MIGRATION = _ROOT / "migrations" / "0189_output_lane.sql"


# =================================================================================================
# 1 · ⛔ something actually routes
# =================================================================================================
def test_the_decision_maker_routes_every_decision_it_builds():
    """⛔ WITHOUT THIS THE WHOLE SECTION IS DEAD CODE. A lane vocabulary, a router and five projections
    with nothing calling `route()` is the "built, tested, green, called by nothing" shape — which this
    programme has now found seven times."""
    from genios_engine.reason import decision_maker

    source = inspect.getsource(decision_maker)
    assert "output_lane import route" in source
    assert "output_lane=_lane.lane" in source
    assert "lane_reason=_lane.reason" in source


def test_it_routes_where_the_outcome_and_the_confidence_first_exist_together():
    """Routing later would mean re-deriving both from a projection, and a re-derived route can disagree
    with the decision it describes."""
    from genios_engine.reason import decision_maker

    source = inspect.getsource(decision_maker)
    at = source.index("_route_lane(")
    window = source[at:at + 400]
    assert "outcome=outcome" in window
    assert "confidence_bp=confidence_bp" in window


def test_the_conflict_flag_is_read_from_markers_the_situation_layer_already_publishes():
    """⛔ A second conflict detector could disagree with the hold that raised it, and then two places
    decide whether a conflict is open."""
    from genios_engine.reason import decision_maker

    source = inspect.getsource(decision_maker)
    at = source.index("_route_lane(")
    window = source[at:at + 600]
    assert "conflict_open" in window
    assert "uncertainty" in window


def test_the_actionable_block_flag_is_conservatively_false_and_says_why():
    """⛔ Claiming a block is reader-actionable when it is not puts our own plumbing in front of a
    founder as a business question. This seam does not know, so it says nothing rather than guessing."""
    from genios_engine.reason import decision_maker

    source = inspect.getsource(decision_maker)
    at = source.index("_route_lane(")
    assert "reader_actionable_block=False" in source[at:at + 900]
    assert "Conservatively False" in source[at - 200:at + 900]


# =================================================================================================
# 2 · the in-memory object
# =================================================================================================
def test_the_decision_object_carries_the_lane_and_its_reason():
    fields = ReasoningDecision.__dataclass_fields__
    assert "output_lane" in fields and "lane_reason" in fields


def test_the_lane_is_NOT_part_of_the_decision_identity():
    """⛔ It is DERIVED from `outcome`, `confidence_bp` and `uncertainty`, all of which are already in
    the hash — so it adds no information and changing the hash for it would invalidate replay for every
    decision already written. See the long note in `test_every_decision_reaches_exactly_one_lane.py`."""
    source = inspect.getsource(ReasoningDecision.to_semantic_dict)
    assert 'body["output_lane"]' not in source


def test_neither_the_audit_envelope_nor_the_replay_rebuild_carries_the_lane():
    """⛔ THE THREE PLACES THAT MUST AGREE. `contracts` keeps the lane out of the hash, so `audit._output`
    must not persist it into `decision_core` and `store`'s rebuild must not restore it — any one of the
    three disagreeing produces `contract decision hash integrity mismatch`, which is precisely what
    happened when I first added it."""
    from genios_engine.reason import audit, store

    audit_src = inspect.getsource(audit)
    assert '("output_lane", decision.output_lane)' not in audit_src
    assert "NOT here" in audit_src

    store_src = inspect.getsource(store)
    assert '"output_lane", "lane_reason"):' not in store_src
    assert "must not become one" in store_src


# =================================================================================================
# 3 · ⛔ the flat projection the card reads
# =================================================================================================
def test_the_signals_projection_writes_both_columns():
    """`signals` is flat on purpose — `DECISION_PROJECTIONS`: *"the card layer must not re-derive a
    recommendation."* A lane the card has to re-derive is a lane the card will get wrong."""
    from genios_engine.reason import domain_shadow

    source = inspect.getsource(domain_shadow)
    assert '"output_lane, lane_reason, "' in source
    assert ':lane,:lreason,' in source
    assert '"lane":' in source and '"lreason":' in source


def test_the_projection_carries_the_lane_rather_than_re_routing():
    """⛔ Re-routing from the projected columns could disagree with the audited decision — the same
    failure `score` and `reason_code` in that insert are already commented against."""
    from genios_engine.reason import domain_shadow

    source = inspect.getsource(domain_shadow)
    at = source.index('"lane": (decision.output_lane')
    assert "decision.output_lane.value" in source[at:at + 200]
    assert "route(" not in source[at - 400:at + 400]


def test_an_unrouted_decision_projects_null_not_a_default_lane():
    """⛔ NULL is an answer. A default lane would claim a routing decision nobody made — the rule
    migration 0182 states for `situation_id`: *"fewer cards must come from merging, never from
    dropping."*"""
    from genios_engine.reason import domain_shadow

    source = inspect.getsource(domain_shadow)
    at = source.index('"lane": (decision.output_lane')
    assert "is not None else None" in source[at:at + 200]


# =================================================================================================
# 4 · the migration matches the code
# =================================================================================================
def test_the_migration_exists_and_allows_every_lane():
    sql = _MIGRATION.read_text()
    for lane in OUTPUT_LANES:
        assert f"'{lane.value}'" in sql


def test_the_columns_are_nullable_so_old_rows_stay_honest():
    sql = _MIGRATION.read_text()
    assert "add column if not exists output_lane text;" in sql
    assert "not null" not in sql.split("add column if not exists output_lane")[1][:80]


def test_a_lane_without_a_reason_cannot_be_written_at_all():
    """⛔ Both or neither, enforced by the database and not only by the writer. A card in the wrong lane
    with no recorded reason is undiagnosable."""
    sql = _MIGRATION.read_text()
    assert "signals_lane_has_a_reason" in sql
    assert "length(trim(lane_reason)) > 0" in sql


def test_a_reason_without_a_lane_is_refused_too():
    """It would describe a routing that did not happen."""
    sql = _MIGRATION.read_text()
    assert "(output_lane is null and lane_reason is null)" in sql


# =================================================================================================
# 5 · ⛔ where the lane deliberately does NOT go
# =================================================================================================
def test_the_audited_row_is_not_given_duplicate_columns():
    """⛔ `reasoning_run_outputs` already carries the lane — it is inside `decision_hash` via
    `to_semantic_dict`, and `decision_core` is the caller's mapping of that dict. A pair of columns
    there would duplicate a value already in the same row, and a duplicated value can disagree with its
    original.

    Adding them with no writer would be worse: the eighth "built, green, called by nothing"."""
    sql = _MIGRATION.read_text()
    assert "alter table reasoning_run_outputs" not in sql
    assert "DELIBERATELY DOES NOT ADD" in sql


def test_the_omission_names_what_carries_it_instead():
    """An undocumented omission reads as an oversight, and the next person 'fixes' it."""
    sql = _MIGRATION.read_text()
    assert "decision_hash" in sql
    assert "separate unit" in sql
