"""A selected run must survive the persistence boundary — receipts and all.

The Unit Selector schedules a SUB-plan: a situation with no money fact does not pay for
`core.cost`. Until the roster woke, selection was enabled by no manifest anywhere, so the audit
store could demand that the executed plan equal the capability's whole DAG and never be wrong. The
first live compiled run with the roster awake hit that check and persisted NOTHING —
`reasoner plan differs from capability DAG` — which is a woken roster reasoning perfectly in
memory and leaving no trace an auditor or a replay could read.

The invariant is not relaxed here, it is moved: the executed plan must be a sub-plan of the DAG,
in the DAG's own order, and EVERY declared unit still owes a row — the ones that ran, then the
ones the selector dropped, each carrying the planner's receipt. A unit that is missing from a
bundle, or present without a reason, is refused by both the writer and the replay verifier.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from genios_engine.contracts.reasoning import (
    FailurePolicy,
    ReasonerSpec,
    ReasoningRequest,
)
from genios_engine.packs.capabilities.deal_cooling import DEAL_COOLING_V1
from genios_engine.reason.audit import _result_rows
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.plan import CONTEXT_AWARE_SELECTION_KEY
from genios_engine.reason.reasoners import default_registry
from genios_engine.reason.store import (
    ReasoningStore,
    ReasoningStoreError,
    ReplayIntegrityError,
    _audited_order,
)

from ..test_reasoning_audit_replay import CONFIG_SNAPSHOT_ID, NOW, _context, _persisted_bundle

#: One optional unit this situation cannot feed — the whole of what selection does, in one spec.
DROPPED = ReasonerSpec("core.timeline", "1.0.0", dependencies=("core.temporal",),
                       required_fields=("deal.close_date",),
                       failure_policy=FailurePolicy.OPTIONAL)


def _selected_execution():
    capability = replace(
        DEAL_COOLING_V1,
        reasoners=DEAL_COOLING_V1.reasoners + (DROPPED,),
        metadata={**dict(DEAL_COOLING_V1.metadata), CONTEXT_AWARE_SELECTION_KEY: True})
    request = ReasoningRequest(
        org_id="org_1", capability=capability, context=_context(), evaluation_time=NOW,
        trigger_kind="email.received", trigger_ref="event_1",
        config_snapshot_id=CONFIG_SNAPSHOT_ID)
    return ReasoningOrchestrator(default_registry()).execute(request)


def test_the_dropped_unit_is_persisted_as_a_skipped_row_carrying_its_receipt():
    execution = _selected_execution()

    assert "core.timeline" not in execution.plan.reasoner_plan
    rows = _result_rows(execution)
    receipt = next(row for row in rows if row["reasoner_id"] == "core.timeline")

    assert [row["ordinal"] for row in rows] == list(range(len(rows)))
    assert len(rows) == len(execution.request.capability.reasoners)
    assert receipt["status"].value == "skipped"
    assert receipt["skip_reason_code"] == "no_declared_input_available"
    assert receipt["missing_fields"] == ("deal.close_date",)


def test_a_selected_bundle_still_verifies_every_persisted_hash():
    bundle = _persisted_bundle(_selected_execution())

    ReasoningStore.__new__(ReasoningStore).verify_replay_bundle(bundle, org_id="org_1")


def test_a_bundle_whose_unscheduled_unit_lost_its_receipt_is_refused():
    """The one thing this change may not buy: a unit that quietly did not run."""
    bundle = _persisted_bundle(_selected_execution())
    for row in bundle["reasoner_results"]:
        if row["reasoner_id"] == "core.timeline":
            row["skip_reason_code"] = None

    with pytest.raises(ReplayIntegrityError, match="carries no skip receipt"):
        ReasoningStore.__new__(ReasoningStore).verify_replay_bundle(bundle, org_id="org_1")


def test_a_bundle_that_dropped_the_unscheduled_units_row_entirely_is_refused():
    bundle = _persisted_bundle(_selected_execution())
    bundle["reasoner_results"] = [row for row in bundle["reasoner_results"]
                                  if row["reasoner_id"] != "core.timeline"]

    with pytest.raises(ReplayIntegrityError, match="reasoner result count"):
        ReasoningStore.__new__(ReasoningStore).verify_replay_bundle(bundle, org_id="org_1")


# ── the ordering rule the store now enforces ─────────────────────────────────────────────────

def test_a_full_plan_orders_exactly_as_it_always_did():
    assert _audited_order(["a", "b", "c"], ["a", "b", "c"]) == ["a", "b", "c"]


def test_a_sub_plan_is_followed_by_the_units_it_left_out_in_dag_order():
    assert _audited_order(["a", "c"], ["a", "b", "c", "d"]) == ["a", "c", "b", "d"]


def test_a_plan_naming_a_unit_the_dag_never_declared_is_refused():
    with pytest.raises(ReasoningStoreError, match="differs from capability DAG"):
        _audited_order(["a", "z"], ["a", "b"])


def test_a_plan_that_reorders_the_dag_is_refused():
    with pytest.raises(ReasoningStoreError, match="reorders"):
        _audited_order(["b", "a"], ["a", "b"])


def test_a_plan_that_repeats_a_unit_is_refused():
    with pytest.raises(ReasoningStoreError, match="repeats"):
        _audited_order(["a", "a"], ["a", "b"])
