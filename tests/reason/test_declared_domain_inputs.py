"""U3, behavioural half — the readings a core unit used to make for itself, made in the manifest.

The grep in `test_units_domain_free.py` proves the words are gone. This file proves the *reading*
moved rather than being deleted: the same situations still produce the same observations once the
capability says which fact carries an inbound, a state, an assignee — and produce silence with a
receipt when it does not, instead of a zero that reads as "no opportunity here".
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from genios_engine.contracts.reasoning import ResultStatus
from genios_engine.packs.capabilities.deal_cooling_v2 import DEAL_COOLING_FULL_V2
from genios_engine.reason.reasoners.opportunity import UNDECLARED_REASON, OpportunityUnit
from genios_engine.reason.reasoners.resource_unit import ResourceUnit

from .conftest import NOW, completed, run

BOUND = {"inbound_field": "deal.last_inbound", "outbound_field": "deal.last_outbound",
         "status_field": "deal.status",
         "active_statuses": ("open", "active", "in_progress", "negotiation"),
         "owner_field": "deal.owner"}
QUIET = {"core.temporal": completed("core.temporal", drop_bp=6_000)}


def _ago(hours: int) -> str:
    return (NOW - timedelta(hours=hours)).isoformat()


# ── core.opportunity ──────────────────────────────────────────────────────────────────────────

def test_an_undeclared_capability_gets_silence_with_a_receipt():
    """`matched=None`, not False. A capability that declared no inputs has not been told this
    situation is uninteresting; it has been told nothing, and the Decision Maker must be able to
    tell those apart."""
    result = run(OpportunityUnit(), facts={"deal.status": {"value": "open"}}, prior=QUIET)

    assert result.status is ResultStatus.COMPLETED
    assert result.matched is None
    assert result.metrics["opportunity_bp"] == 0
    assert UNDECLARED_REASON in result.reason_codes


def test_the_same_situation_reads_the_same_once_the_manifest_binds_the_fields():
    """The reading moved to Layer 3; it did not evaporate."""
    result = run(OpportunityUnit(), config=BOUND, facts={"deal.status": {"value": "open"}},
                 prior=QUIET)

    assert result.metrics["opportunity_bp"] == 6_000
    assert "active_without_momentum" in result.reason_codes
    assert result.matched is True


def test_which_state_words_mean_live_is_the_manifests_call():
    """Whether `negotiation` means the work is still winnable is domain knowledge that differs by
    industry and by customer. A unit that hardcoded it would ship one vertical to every tenant."""
    facts = {"deal.status": {"value": "negotiation"}}
    narrow = dict(BOUND, active_statuses=("open",))

    assert run(OpportunityUnit(), config=BOUND, facts=facts,
               prior=QUIET).metrics["opportunity_bp"] == 6_000
    assert run(OpportunityUnit(), config=narrow, facts=facts,
               prior=QUIET).metrics["opportunity_bp"] == 0


def test_a_state_field_with_no_live_vocabulary_is_an_authoring_fault():
    """A half-made declaration must fail loudly. Guessing the missing half is how a unit ends up
    deciding what "open" means for a business it has never seen."""
    with pytest.raises(ValueError):
        run(OpportunityUnit(), config={"status_field": "deal.status"},
            facts={"deal.status": {"value": "open"}}, prior=QUIET)


def test_an_assignee_field_nobody_captured_is_not_an_unowned_relationship():
    """The fabrication this wave closes: reading an absent fact as "no owner" invented an
    opportunity on every situation in any org that never synced its assignees."""
    uncaptured = run(OpportunityUnit(), config=BOUND, facts={}, prior={})
    captured_empty = run(OpportunityUnit(), config=BOUND, facts={"deal.owner": {"value": ""}},
                         prior={})

    assert uncaptured.metrics["opportunity_count"] == 0
    assert captured_empty.metrics["opportunity_bp"] == 4_000
    assert "no_owner_assigned" in captured_empty.reason_codes


def test_an_inbound_with_no_declared_outbound_makes_no_claim():
    """Without knowing when we last wrote back, the unit cannot tell an unanswered message from
    an answered one, and "they are waiting on us" is the strongest claim it makes."""
    facts = {"deal.last_inbound": {"value": _ago(20)}}
    half = {"inbound_field": "deal.last_inbound"}

    assert run(OpportunityUnit(), config=half, facts=facts).metrics["opportunity_count"] == 0
    assert run(OpportunityUnit(), config=BOUND, facts=facts).metrics["opportunity_bp"] > 0


def test_an_answered_inbound_closes_the_gap():
    facts = {"deal.last_inbound": {"value": _ago(20)},
             "deal.last_outbound": {"value": _ago(2)}}

    assert run(OpportunityUnit(), config=BOUND, facts=facts).metrics["opportunity_count"] == 0


# ── core.resource ─────────────────────────────────────────────────────────────────────────────

def test_resource_reads_the_assignee_field_the_manifest_names():
    declared = run(ResourceUnit(), config={"owner_field": "deal.owner"},
                   facts={"deal.owner": {"value": ""}})
    undeclared = run(ResourceUnit(), facts={"deal.owner": {"value": ""}})

    assert declared.metrics["capacity_bp"] == 0
    assert "no_owner_to_execute" in declared.reason_codes
    assert "capacity_bp" not in undeclared.metrics
    assert "resource_capacity_unknown" in undeclared.reason_codes


def test_resource_still_refuses_to_invent_an_availability():
    """An owner field that was never captured, or never declared, is silence — and silence about
    capacity is a WARN that reaches the human, not a shortfall the unit made up."""
    result = run(ResourceUnit(), config={"owner_field": "deal.owner"}, facts={})

    assert result.matched is None
    assert "resource_capacity_unknown" in result.reason_codes


# ── the seam is actually bound ────────────────────────────────────────────────────────────────

def test_the_shipped_capability_declares_the_vocabulary_the_units_gave_up():
    """A purge that left no capability declaring the fields would be a silent feature removal
    dressed as a principle. `sales.deal_cooling_full` names them, in the manifest, where the rest
    of its expertise already lives."""
    specs = {item.reasoner_id: item.config for item in DEAL_COOLING_FULL_V2.reasoners}

    assert specs["core.opportunity"]["status_field"] == "deal.status"
    assert "open" in specs["core.opportunity"]["active_statuses"]
    assert specs["core.opportunity"]["inbound_field"] == "deal.last_inbound"
    assert specs["core.resource"]["owner_field"] == "deal.owner"
