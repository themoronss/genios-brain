"""L1.3.9-U5 · the structured lane, end to end — W2·D4.

The defect this file closes: **the structured mapper could not pass S3 against any doc-04
vocabulary, and the only thing checking it was a vocabulary the test had invented.** `mapper.py`
said so itself —

    GAP FLAG (cross-doc): doc 04's closed profile set is `email | chat | transcript | document |
    crm_note` and contains no `structured` member, so an extraction from this lane fails S-3
    against a vocabulary built strictly from that list.

— and `test_mapper.py` worked around it by hand-writing all six closed sets beside the real ones.
A lane asserted against a copy of its vocabulary passes forever: the copy is what gets updated.

So every assertion here goes through `structured_vocabulary()`, which is
`ExtractionVocabulary(**vocabulary_sets())` and reads `capture/semantic/vocabulary.py` — the one
closed set — and the lane has a production caller in `capture/pipeline.py`, driven below through
a model client that RAISES on contact.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.pipeline import (STRUCTURED_STAGE, EsqeStage, SemanticLane,
                                            StructuredLane, capture_event)
from genios_engine.capture.semantic.open_lane import InMemoryOpenLaneStore
from genios_engine.capture.semantic.vocabulary import EXTRACTION_PROFILE, vocabulary_sets
from genios_engine.capture.structured.lane import run_structured_lane, structured_vocabulary
from genios_engine.capture.structured.mapper import (STRUCTURED_PROFILE,
                                                     structured_validation_stage)
from genios_engine.capture.structured.registry import (all_mappings, get_mapping,
                                                       mapping_from_dict, register)
from genios_engine.capture.structured.registry import _REGISTRY
from genios_engine.capture.validate.schema import ExtractionVocabulary, validate_extraction_schema

WAVE = "W2"
GATE = "G2"

NOW = datetime(2026, 9, 5, 9, 0, tzinfo=timezone.utc)
ORG = "org_w2_lane"
EVENT = "evt_w2_lane"

#: A complete HubSpot deal: every declared column present, including the currency column the
#: money field names. Incomplete payloads are their own test below.
HUBSPOT_DEAL: dict[str, Any] = {
    "id": "deal_9912",
    "dealname": "Chat360 Pilot",
    "dealstage": "contractsent",
    "amount": "84000",
    "deal_currency_code": "USD",
    "closedate": 1795046400000,
    "contact_email": ["Priya@Chat360.io", "ops@chat360.io"],
}

GCAL_EVENT: dict[str, Any] = {
    "id": "evt_1", "summary": "Pricing review", "status": "confirmed",
    "start": {"dateTime": "2026-09-10T10:00:00+05:30"},
    "end": {"dateTime": "2026-09-10T11:00:00+05:30"},
    "attendees": [{"email": "priya@chat360.io", "displayName": "Priya"}],
}

#: The object a registered mapping is applied to, per mapping id — so the S-1..S-9 sweep below
#: runs over real payloads rather than over an empty dict that would conform vacuously.
PAYLOADS: dict[str, dict[str, Any]] = {
    "hubspot.deal.v1": HUBSPOT_DEAL,
    "gcal.event.v1": GCAL_EVENT,
    "stripe.subscription.v1": {"id": "sub_1", "status": "active",
                               "current_period_end": 1795046400},
    "postgres.public.customer_accounts.v1": {"account_id": "a1", "plan": "growth",
                                             "status": "active", "seats_used": 42},
    "postgres.customer_accounts.v1": {"account_id": "a1", "plan": "growth",
                                      "status": "active", "seats_used": 42},
    "postgres.product_usage_events.v1": {"id": "u1", "event_name": "report_run",
                                         "account_id": "acct_7", "quantity": 3,
                                         "occurred_at": "2026-09-04T11:00:00+00:00",
                                         "user_email": "priya@chat360.io"},
}


def _run(mapping, raw, **over):
    kwargs = dict(org_id=ORG, event_id=EVENT, eval_time=NOW)
    kwargs.update(over)
    return run_structured_lane(mapping, raw, **kwargs)


class _RaisingLLM:
    """A model that RAISES on contact. Stricter than a fake with no canned answers: there is no
    count to be off by, and no way for a swallowed exception to look like a zero."""

    model = "must-never-be-called"

    def call(self, prompt: str, *, max_tokens: int = 4096):      # noqa: ARG002
        raise AssertionError("the structured lane called a model; the bypass is not a bypass")


# ── D4 · the vocabulary is the real one ───────────────────────────────────────────────────────

def test_the_lane_validates_against_the_shipping_vocabulary_and_no_copy_of_it():
    """`structured_vocabulary()` IS `capture/semantic/vocabulary.py`, field for field.

    Asserted against `vocabulary_sets()` rather than against a list retyped here, because a
    retyped list is exactly what D4 is about.
    """
    built = structured_vocabulary()
    assert isinstance(built, ExtractionVocabulary)
    for name, members in vocabulary_sets().items():
        assert getattr(built, name) == members, f"{name} is not the shipping set"


def test_the_profile_this_lane_stamps_is_a_member_of_the_closed_profile_set():
    """The gap the mapper flagged and could not close from inside itself: doc 03 mandates the
    literal `structured`, doc 04's list predates the bypass. Filing a HubSpot deal under
    `crm_note` would be a lie about a typed column, and filing a calendar event under it is not
    even a plausible one — so the word is in the set, and this is what says so."""
    assert STRUCTURED_PROFILE in EXTRACTION_PROFILE


@pytest.mark.gate
@pytest.mark.parametrize("mapping", all_mappings(), ids=lambda m: m.mapping_id)
def test_every_registered_mapping_produces_an_extraction_that_passes_s1_to_s9(mapping):
    """G2, for real. Every shipping mapping, a real payload, the real vocabulary, the stage this
    lane is genuinely at.

    `POST_VERIFICATION` is not a way around S-9: every span the lane carries was set by
    `verify_span` — ALG-08 itself, on a literal slice of a real rendering — which is exactly the
    condition that stage names. The other eight rules all run.
    """
    payload = PAYLOADS.get(mapping.mapping_id)
    assert payload is not None, (
        f"{mapping.mapping_id} has no payload in this file — a mapping added without one would "
        "be silently skipped by the sweep that exists to cover every mapping")

    outcome = _run(mapping, payload)

    assert outcome.failure is None, outcome.failure
    assert outcome.result is not None
    assert outcome.schema.conforms, outcome.schema.violations
    report = validate_extraction_schema(outcome.result, vocabulary=structured_vocabulary(),
                                        stage=structured_validation_stage())
    assert report.conforms and report.violations == (), report.violations


def test_the_extraction_carries_the_typed_claims_the_columns_stated():
    outcome = _run(get_mapping("hubspot", "deal"), HUBSPOT_DEAL)

    assert outcome.result is not None
    assert outcome.result.extraction_profile == STRUCTURED_PROFILE
    assert outcome.result.input_tokens == 0 and outcome.result.output_tokens == 0
    assert [money.currency for money in outcome.result.amounts] == ["USD"]
    assert outcome.result.amounts[0].minor_units == 8_400_000
    assert {m.canonical_hint for m in outcome.result.entity_mentions} == {
        "priya@chat360.io", "ops@chat360.io"}
    assert dict(outcome.fields)["deal.stage"] == "contractsent"


# ── D4 · zero LLM, proven by a client that raises ─────────────────────────────────────────────

def test_the_lane_has_no_model_client_to_call():
    """The strongest available form of the guarantee: there is no parameter to pass one through.

    A lane that accepted a client and promised not to use it could break the promise in a later
    edit with nothing failing.
    """
    import inspect

    assert "llm" not in inspect.signature(run_structured_lane).parameters
    assert "client" not in inspect.signature(run_structured_lane).parameters


@pytest.mark.gate
def test_the_pipeline_runs_this_lane_on_a_crm_object_with_a_model_that_raises():
    """The wiring, and the zero-LLM guarantee, in one assertion.

    Before this, `map_to_extraction` had no production caller at all: the pipeline called
    `apply_mapping` for the values and nothing ever built the extraction beside them. A unit
    with no caller cannot regress and cannot help, which is why the assertion is made through
    `capture_event` rather than against the lane directly.
    """
    raw = RawObject(source="hubspot", object_type="deal", source_object_id="deal_9912",
                    occurred_at=NOW, actor_email="owner@genios.ai", content_version="v1",
                    raw=HUBSPOT_DEAL)
    lane = SemanticLane(llm=_RaisingLLM(), eval_time=NOW, open_lane=InMemoryOpenLaneStore())

    result = capture_event(raw, org_id=ORG, connection_id="con_w2",
                           repo=InMemorySourceEventRepository(), semantic=lane,
                           mailbox_owner="owner@genios.ai")

    assert result.outcome == "emitted"
    assert result.gated is not None and result.gated.route == "structured"
    assert result.gated.structured_fields["deal.stage"] == "contractsent"
    assert result.extraction is not None, "the structured lane still has no production caller"
    assert result.extraction.extraction_profile == STRUCTURED_PROFILE
    assert validate_extraction_schema(result.extraction, vocabulary=structured_vocabulary(),
                                      stage=structured_validation_stage()).conforms
    assert STRUCTURED_STAGE in [record.stage for record in result.trace.records], \
        "a lane that leaves no trace record is unauditable"


def test_a_typed_record_takes_the_bypass_with_no_semantic_lane_configured_at_all():
    """THE DECOUPLING. A HubSpot deal is a typed record: it needs no model, no extraction call
    and no activation row — that is the entire point of the bypass. It used to be gated behind
    `semantic is not None`, so a tenant with no model wiring got no structured signals either,
    and an activation flag guarded a path that never reaches a model.

    Driven with NO semantic lane and with LLM-5's client set to one that RAISES, so the only
    way this test can pass is if nothing on the structured route touches a model.
    """
    raw = RawObject(source="hubspot", object_type="deal", source_object_id="deal_9912",
                    occurred_at=NOW, actor_email="owner@genios.ai", content_version="v1",
                    raw=HUBSPOT_DEAL)
    store = InMemoryOpenLaneStore()

    result = capture_event(raw, org_id=ORG, connection_id="con_w2",
                           repo=InMemorySourceEventRepository(), semantic=None,
                           structured=StructuredLane(open_lane=store, timezone="Asia/Kolkata"),
                           esqe=EsqeStage(relevance_llm=_RaisingLLM()),
                           mailbox_owner="owner@genios.ai")

    assert result.outcome == "emitted"
    assert result.gated is not None and result.gated.route == "structured"
    assert result.gated.structured_fields["deal.stage"] == "contractsent"
    assert result.extraction is not None, \
        "the structured lane is still coupled to the semantic lane being configured"
    assert result.extraction.extraction_profile == STRUCTURED_PROFILE
    assert validate_extraction_schema(result.extraction, vocabulary=structured_vocabulary(),
                                      stage=structured_validation_stage()).conforms
    assert STRUCTURED_STAGE in [record.stage for record in result.trace.records]
    # and it QUALIFIES: a signal came out of a typed record with no model anywhere in the run.
    assert result.qualification is not None, "a typed record produced no qualified signal"
    assert result.extraction_ref == f"struct:{result.event.event_id}"


def test_the_bypass_resolves_typed_dates_against_the_events_own_world_time():
    """No lane means no frozen instant, and a wall-clock read inside the pipeline would make a
    replay of a March object a different extraction. The event's own `occurred_at` is the stored
    moment every other unactivated path already judges against (`EsqeStage.eval_time`), so it is
    what the structured lane is handed too."""
    raw = RawObject(source="hubspot", object_type="deal", source_object_id="deal_9912",
                    occurred_at=NOW, actor_email="owner@genios.ai", content_version="v1",
                    raw=HUBSPOT_DEAL)

    result = capture_event(raw, org_id=ORG, connection_id="con_w2",
                           repo=InMemorySourceEventRepository())

    assert result.extraction is not None
    direct = _run(get_mapping("hubspot", "deal"), HUBSPOT_DEAL, eval_time=NOW)   # NOW == occurred_at
    assert direct.result is not None
    assert (result.extraction.dates_mentioned == direct.result.dates_mentioned
            and result.extraction.amounts == direct.result.amounts), \
        "the bypass resolved its typed dates against something other than the event's own time"


@pytest.fixture()
def drifted_mapping():
    """The drifted tenant mapping, registered for one test and removed again — a registry left
    dirty would change what `all_mappings()` sweeps assert over, in whatever order they run."""
    mapping = mapping_from_dict(DRIFTED_CONFIG)
    register(mapping)
    try:
        yield mapping
    finally:
        _REGISTRY.pop((mapping.source, mapping.object_type), None)


def test_the_structured_bundle_persists_its_discoveries_with_no_model_wired(drifted_mapping):
    """`StructuredLane` is what carries the org's zone and the discovery store on the branch that
    has no `SemanticLane` to carry them. Without it the open lane would be reachable only by
    activated tenants — a discovery lane that only collects from the tenants that need it least.
    """
    store = InMemoryOpenLaneStore()
    raw = RawObject(source="postgres", object_type="public.deals", source_object_id="d1",
                    occurred_at=NOW, actor_email="owner@genios.ai", content_version="v1",
                    raw={"id": "d1", "name": "Chat360 Pilot", "stage_name": "negotiation"})

    result = capture_event(raw, org_id=ORG, connection_id="con_w2",
                           repo=InMemorySourceEventRepository(),
                           structured=StructuredLane(open_lane=store))

    assert result.gated is not None
    rows = store.observations_for(org_id=ORG, event_id=result.event.event_id)
    assert [row.proposed_kind_raw for row in rows] == ["crm.deal_stage"]


# ── #6 · a refused name lands in the open lane and nowhere else, through the real lane ────────

#: A tenant config declaring one addressable target and one that is not: `crm.deal_stage` is the
#: shape a mapping drifts into when somebody pastes a field in from another integration.
DRIFTED_CONFIG: dict[str, Any] = {
    "mapping_id": "client.deal.v1", "source": "postgres", "object_type": "public.deals",
    "identity_field": "id", "node_type": "deal", "intent": "pipeline_update",
    "name_field": "deal.title",
    "fields": [{"source_field": "name", "target": "deal.title", "value_type": "string"},
               {"source_field": "stage_name", "target": "crm.deal_stage", "value_type": "enum"}],
}


def test_a_drifted_target_lands_in_the_open_lane_and_in_no_other_place():
    """W2·#6 through the whole lane, not just the sift.

    The name appears in exactly one row of one table. It is not in the fields L2 commits, not in
    the extraction's typed claims, and the extraction it rides on still passes S-1..S-9 — a
    discovery that broke the schema would be a discovery nobody could store.
    """
    store = InMemoryOpenLaneStore()
    raw = {"id": "d1", "name": "Chat360 Pilot", "stage_name": "negotiation"}

    outcome = _run(mapping_from_dict(DRIFTED_CONFIG), raw, open_lane=store)

    assert dict(outcome.fields) == {"deal.title": "Chat360 Pilot"}
    assert [record.target for record in outcome.refused] == ["crm.deal_stage"]
    assert outcome.result is not None and outcome.schema.conforms, outcome.schema.violations

    rows = store.observations_for(org_id=ORG, event_id=EVENT)
    assert [row.proposed_kind_raw for row in rows] == ["crm.deal_stage"]
    assert outcome.capture.stored == 1

    # Every field of the extraction EXCEPT the open lane, serialized: the name must appear in
    # none of them. Asserted over the whole object rather than over the three fields somebody
    # thought to check, so a field added to the contract next year is covered too.
    dumped = outcome.result.model_dump(mode="json")
    dumped.pop("unclassified_observations")
    assert "crm.deal_stage" not in json.dumps(dumped), (
        "the refused name appears somewhere other than the open lane: "
        f"{[name for name, value in dumped.items() if 'crm.deal_stage' in json.dumps(value)]}")
    assert [o.proposed_kind for o in outcome.result.unclassified_observations] == \
        ["crm.deal_stage"]
    assert "crm.deal_stage" not in dict(outcome.fields)


def test_the_open_lane_regrades_the_lanes_own_probe_rather_than_trusting_it():
    """The probe is minted at offsets 0..len with `verified=False`; ALG-08 relocates it into the
    object's own rendering and the row stores the CORRECTED offsets with the verdict the grader
    gave. A lane that stored its own flag would be asserting its salvage was checked."""
    store = InMemoryOpenLaneStore()
    raw = {"id": "d1", "name": "Chat360 Pilot", "stage_name": "negotiation"}

    _run(mapping_from_dict(DRIFTED_CONFIG), raw, open_lane=store)

    row = store.observations_for(org_id=ORG, event_id=EVENT)[0]
    assert row.verified is True, "the receipt did not resolve against the object it came from"
    assert row.quote == "negotiation"
    assert row.start_offset > 0, "the probe's placeholder offsets were stored as though real"


def test_without_a_store_the_name_is_still_refused_and_simply_not_kept():
    """`open_lane=None` is the pre-wiring behaviour and must stay exactly that: the closure is
    about what may be STORED, and a lane store is not required to enforce it."""
    outcome = _run(mapping_from_dict(DRIFTED_CONFIG),
                   {"id": "d1", "name": "Chat360 Pilot", "stage_name": "negotiation"})

    assert dict(outcome.fields) == {"deal.title": "Chat360 Pilot"}
    assert outcome.capture.rows == () and outcome.capture.stored == 0
    assert outcome.result is not None
    assert [o.proposed_kind for o in outcome.result.unclassified_observations] == \
        ["crm.deal_stage"]


# ── park-never-drop: a drifted mapping loses the extraction, never the object ─────────────────

def test_a_mapping_that_cannot_normalise_a_column_returns_the_failure_and_keeps_the_fields():
    """`map_to_extraction` raises on schema drift and doc 03 is right that it should. On the
    ingestion path that raise must not cost the object: `fields` is produced by the sift and is
    unaffected by whether an extraction could be built beside it."""
    outcome = _run(get_mapping("hubspot", "deal"),
                   dict(HUBSPOT_DEAL, deal_currency_code=None))     # amount with no currency

    assert outcome.result is None and outcome.extracted is False
    assert outcome.failure is not None and "currency" in outcome.failure
    assert dict(outcome.fields)["deal.stage"] == "contractsent", \
        "a drifted column cost the customer their whole deal record"


def test_a_pipeline_capture_survives_a_mapping_that_cannot_map():
    """The same thing at the seam: L1's rule is park-never-drop, and the structured route may not
    become the one place an object disappears."""
    raw = RawObject(source="hubspot", object_type="deal", source_object_id="deal_9912",
                    occurred_at=NOW, actor_email="owner@genios.ai", content_version="v1",
                    raw=dict(HUBSPOT_DEAL, closedate="not-a-timestamp"))
    lane = SemanticLane(llm=_RaisingLLM(), eval_time=NOW)

    result = capture_event(raw, org_id=ORG, connection_id="con_w2",
                           repo=InMemorySourceEventRepository(), semantic=lane,
                           mailbox_owner="owner@genios.ai")

    assert result.outcome == "emitted"
    assert result.gated is not None
    assert result.gated.structured_fields["deal.stage"] == "contractsent"
    assert result.extraction is None
    record = [r for r in result.trace.records if r.stage == STRUCTURED_STAGE][0]
    assert record.reason_code is not None, "the failure left no reason anybody can read"


# ── the SWEEP door, with no model configured anywhere ─────────────────────────────────────────

class _CrmConnector:
    """One HubSpot deal, delivered the way a real connector delivers it."""

    def initial_snapshot(self, cursor=None, limit=50):
        return SourceBatch(objects=self._objects(), next_cursor=None)

    def incremental_changes(self, cursor=None, limit=50, since=None):
        return SourceBatch(objects=self._objects(), next_cursor=None)

    @staticmethod
    def _objects():
        return [RawObject(source="hubspot", object_type="deal", source_object_id="deal_9912",
                          occurred_at=NOW, actor_email="owner@genios.ai", content_version="v1",
                          raw=HUBSPOT_DEAL)]


@pytest.mark.gate
def test_the_sweep_extracts_a_crm_object_for_a_tenant_with_no_semantic_lane():
    """THE WIRING, at the largest capture entry in the system.

    `run_sync` is what every production door funnels into, and it passes `semantic=None` for
    every tenant that is not in `l1_semantic_activation` — which is nearly all of them. Asserting
    through `capture_event` alone would leave that untested: the sweep is the caller, and this is
    the assertion that the typed route survives the trip through it with no model configured.
    """
    summary = run_sync(_CrmConnector(), org_id=ORG, connection_id="con_w2",
                       repo=InMemorySourceEventRepository(), mode="backfill",
                       source="hubspot", mailbox_owner="owner@genios.ai",
                       semantic=None,
                       structured=StructuredLane(timezone="Asia/Kolkata"),
                       esqe=EsqeStage(relevance_llm=_RaisingLLM()))

    assert summary.scanned == 1 and summary.emitted == 1
    result, = summary.results
    assert result.extraction is not None, \
        "the sweep still cannot extract a typed record without a semantic lane"
    assert result.extraction.extraction_profile == STRUCTURED_PROFILE
    assert result.qualification is not None
