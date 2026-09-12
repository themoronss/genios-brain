"""TEST MODE — R-1 read by a model (`reason/llm_interpretation.py`).

What these pin:

* **The model decides WHAT is ambiguous** — no hedge list, no length band — and reads messages.
* **R-1's safety properties survive**: closed enum, 2,000-8,000 band, three readings at most,
  one hop, and evidence in the unattributed pool so a reading can never raise confidence.
* **Wired where it is paid for**: the orchestrator reads only a run about to reach the decision
  maker, and the decision is made on the augmented snapshot.
* **Failure is silence** — a bad answer twice leaves the request exactly as it was.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.context.llm.client import LLMResult
from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ContextSnapshot,
    DecisionOutcome,
    EvidenceRef,
    ExecutionMode,
    Goal,
    PlayDefinition,
    ReasonerSpec,
    ReasoningRequest,
)
from genios_engine.packs.capabilities import DEAL_COOLING_V1
from genios_engine.reason import llm_decision_maker as llm_dm
from genios_engine.reason import llm_interpretation as r1
from genios_engine.reason.interpretation import (
    AMBIGUITY_LLM,
    MAX_FLAGS_PER_SITUATION,
    UNATTRIBUTED_GROUP,
)
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.reasoners import default_registry

NOW = datetime(2026, 9, 12, 12, tzinfo=timezone.utc)
HEDGED = "We might revisit a pilot next quarter, not sure yet."
SETTLED = "We signed the order form today."


def _request(facts=None) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling", version="1.0.0", domain="sales",
        root_entity_type="deal", goal=Goal("g", "Restore healthy deal momentum"),
        reasoners=(ReasonerSpec("core.confidence", "1"),),
        plays=(PlayDefinition(play_id="nudge", version="1", label="Nudge",
                              steps=("Prepare a grounded draft",)),),
        policies=(), metadata={})
    context = ContextSnapshot(
        org_id="org_1", graph_version=1, root_entity_id="deal_1", root_entity_type="deal",
        evaluation_time=NOW, selector_version="s.v1",
        facts=facts or {"deal.status": "open", "thread.last_note": HEDGED,
                        "thread.decision_note": SETTLED})
    return ReasoningRequest(org_id="org_1", capability=capability, context=context,
                            evaluation_time=NOW, trigger_kind="email.received",
                            config_snapshot_id="cfg_1")


class FakeLLM:
    """Answers R-1 prompts from `r1_readings`, and decision prompts by scoring every play."""
    model = "fake-model"

    def __init__(self, r1_readings=None, r1_raw=None):
        self.r1_readings = r1_readings
        self.r1_raw = list(r1_raw or [])
        self.r1_prompts: list[str] = []
        self.dm_prompts: list[str] = []

    def call(self, prompt, *, max_tokens=4096):
        if prompt.startswith("You are R1"):
            self.r1_prompts.append(prompt)
            answer = self.r1_raw.pop(0) if self.r1_raw else {"readings": self.r1_readings}
        else:
            self.dm_prompts.append(prompt)
            template = json.loads(prompt.rsplit("\n", 1)[-1])
            answer = {"outcome": "decision",
                      "scores": {pid: 6_000 for pid in template["scores"]},
                      "confidence_bp": 6_000, "rationale": "ok", "missing": []}
        return LLMResult(parsed=answer, raw=json.dumps(answer), input_tokens=5,
                         output_tokens=5, model=self.model)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    llm_dm._reset_for_tests()
    r1._reset_for_tests()
    monkeypatch.setattr(llm_dm, "_record_cost", lambda **_kw: None)
    monkeypatch.setattr(llm_dm, "business_context", lambda _req: [])
    yield


def _item_number(items, field):
    return next(n for n, item in enumerate(items, 1) if item["field"] == field)


def test_the_model_sees_every_worded_fact_not_only_hedged_ones():
    items = r1.candidate_items(_request(), [])
    fields = [item["field"] for item in items]
    # The settled sentence reaches the model too — the model, not a word list, judges it.
    assert "thread.last_note" in fields and "thread.decision_note" in fields
    assert "deal.status" in fields


def test_messages_from_the_mailbox_are_read_too():
    items = r1.candidate_items(_request(), ["- this is a person: Maria",
                                            "- message 2026-08-11 from Maria: intent=request"])
    assert items[-1]["field"] == "mailbox.message_1"


def test_only_what_the_model_calls_ambiguous_becomes_a_reading():
    request = _request()
    items = r1.candidate_items(request, [])
    readings = [{"item": n, "ambiguous": item["field"] == "thread.last_note",
                 "classification": "EVALUATING_ALTERNATIVES", "confidence_bp": 6_000}
                for n, item in enumerate(items, 1)]
    out = r1.interpret_request(request, FakeLLM(readings))

    assert out is not request
    fact = out.context.facts["interpretation.thread.last_note"]["value"]
    assert fact["classification"] == "EVALUATING_ALTERNATIVES" and fact["kind"] == AMBIGUITY_LLM
    assert "interpretation.thread.decision_note" not in out.context.facts
    ref = next(r for r in out.context.evidence if r.field == "interpretation.thread.last_note")
    assert ref.independence_group == UNATTRIBUTED_GROUP        # can never raise a confidence


def test_one_hop_and_the_cap_of_three_hold():
    facts = {f"thread.note_{i}": f"Maybe we could look at option {i} later on." for i in range(6)}
    request = _request(facts)
    items = r1.candidate_items(request, [])
    readings = [{"item": n, "ambiguous": True, "classification": "SPECULATION_ONLY",
                 "confidence_bp": 5_000} for n in range(1, len(items) + 1)]
    fake = FakeLLM(readings)

    out = r1.interpret_request(request, fake)
    added = [n for n in out.context.facts if n.startswith("interpretation.")]

    assert len(added) == MAX_FLAGS_PER_SITUATION
    assert r1.interpret_request(out, fake) is out             # never read twice
    assert len(fake.r1_prompts) == 1


def test_a_bad_answer_twice_leaves_the_request_untouched():
    request = _request()
    fake = FakeLLM(r1_raw=[{"readings": "nope"}, {"readings": [{"item": 99}]}])

    assert r1.interpret_request(request, fake) is request
    assert len(fake.r1_prompts) == 2 and "CORRECTION" in fake.r1_prompts[1]


def test_out_of_band_confidence_is_refused_not_clamped():
    with pytest.raises(r1._Refused):
        r1.parse_readings({"readings": [{"item": 1, "ambiguous": True,
                                         "classification": "INTENT_STATED",
                                         "confidence_bp": 9_500}]}, 1)


def _deal_request() -> ReasoningRequest:
    """A real registered capability that reaches the decision maker, plus one hedged note."""
    inbound = (NOW - timedelta(days=10)).isoformat()
    context = ContextSnapshot(
        org_id="org_1", graph_version=21, root_entity_id="deal_1", root_entity_type="deal",
        evaluation_time=NOW, selector_version="deal_cooling.selector.v1",
        facts={
            "deal.status": {"value": "open", "confidence_bp": 9_500, "src_count": 2},
            "deal.value": {"value": 500_000, "confidence_bp": 9_500, "src_count": 2},
            "derived.engagement": {"value_bp": 4_000, "confidence_bp": 8_500, "src_count": 2},
            "thread.last_inbound": {"value": inbound, "confidence_bp": 9_000, "src_count": 2},
            "relationship.verified_stakeholder_count": {"value": 2},
            "thread.last_note": {"value": HEDGED},
        },
        neighbor_facts={"deal.status": "open", "contact.verified_recipient": True,
                        "account.alternate_stakeholder_verified": True},
        neighbor_observations=("pricing_discussed", "buying_intent"), edge_count=2,
        evidence=(
            EvidenceRef("ev_status", "deal.status", "open", source_ref_id="email_1",
                        fact_version_id="factv_status_1", occurred_at=NOW - timedelta(hours=1),
                        confidence_bp=9_500, authority_rank=3, independence_group="crm"),
            EvidenceRef("ev_engagement", "derived.engagement", 4_000,
                        confidence_bp=8_500, authority_rank=2),
            EvidenceRef("ev_inbound", "thread.last_inbound", inbound,
                        confidence_bp=9_000, authority_rank=2)),
        metadata={"tenant_timezone": "Asia/Kolkata"})
    return ReasoningRequest(org_id="org_1", capability=DEAL_COOLING_V1, context=context,
                            evaluation_time=NOW, trigger_kind="email.received",
                            trigger_ref="event_1", mode=ExecutionMode.LIVE,
                            config_snapshot_id=None)


def test_the_orchestrator_reads_before_deciding_and_decides_on_the_reading(monkeypatch):
    request = _deal_request()
    items = r1.candidate_items(request, [])
    number = _item_number(items, "thread.last_note")
    fake = FakeLLM([{"item": number, "ambiguous": True,
                     "classification": "EVALUATING_ALTERNATIVES", "confidence_bp": 6_000}])
    monkeypatch.setattr(llm_dm, "enabled_for", lambda _org, _mode=None: True)
    monkeypatch.setattr(llm_dm, "client", lambda: fake)

    execution = ReasoningOrchestrator(default_registry()).execute(request)

    assert len(fake.r1_prompts) == 1 and len(fake.dm_prompts) == 1
    assert "interpretation.thread.last_note" in execution.request.context.facts
    assert "R1 — HOW THE WORDING READS" in fake.dm_prompts[0]
    assert "evaluating alternatives" in fake.dm_prompts[0]
    assert execution.decision.outcome == DecisionOutcome.DECISION


def test_switch_off_means_r1_is_never_called(monkeypatch):
    fake = FakeLLM([])
    monkeypatch.setattr(llm_dm, "enabled_for", lambda _org, _mode=None: False)
    monkeypatch.setattr(llm_dm, "client", lambda: fake)

    ReasoningOrchestrator(default_registry()).execute(_deal_request())

    assert fake.r1_prompts == [] and fake.dm_prompts == []
