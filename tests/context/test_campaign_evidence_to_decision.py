"""Fixed-time compiler/decision probe; persistence is a separate assembly test."""
import json
from datetime import datetime, timedelta

from sqlalchemy import text

from .test_derived_provenance import provenance_db
from .test_support_derived_provenance import NOW
from .test_campaign_silence import campaign, rows, DECK
from genios_engine.context import outreach_situations as outreach
from genios_engine.context.situation_bso import build_business_situation, build_context_slice
from genios_engine.packs.compiler import DomainCompiler, InMemoryRuntimeBrains
from genios_engine.packs.compiler.authoring import ExpertBrainCatalog, default_authoring_root
from genios_engine.reason.adapters.expertise import expertise_capability_manifest
from genios_engine.reason.adapters.native import reason_native_capability
from genios_engine.reason.adapters.situation_projection import project_situation
from genios_engine.reason.engine import NodeContext
from genios_engine.contracts.reasoning import ExecutionMode
from genios_engine.reason.decision_maker import DEFAULT_CONFIDENCE_FLOOR_BP


def compile_campaign(c, *, persist=False):
    sent = NOW - timedelta(days=30)
    grouping = campaign([f"p{i}" for i in range(7)], sentence=DECK, at=sent)
    for event in grouping.event_ids:
        c.execute(text("insert into source_events values ('o',:e,'gmail',:e,:at)"),
                  {"e": event, "at": sent.isoformat()})
    [finding] = outreach.read_campaign_silence(rows(waiting={p: 30 for p in grouping.recipients},
        campaigns=(grouping,)), NOW, {})
    receipts = outreach._group_receipts(c, org_id="o", finding=finding, now=NOW)
    stats = outreach._refined_stats(c, org_id="o", node_id="anchor", finding=finding,
        now=NOW, fallback=None, group_receipts=receipts)
    evidence = outreach.evidence_score(event_count=stats.events, source_count=stats.sources)
    fresh, known = outreach.freshness_score(last_seen_at=stats.last_at, now=NOW)
    assert (evidence, fresh, known) == (65, 50, True)
    row = dict(situation_id="sit_campaign", situation_type="campaign_awaiting_reply", domain="admin",
        status="active", correlation_id=finding.correlation_id, anchor_node_id="anchor",
        anchor_type="campaign", anchor_name=finding.display_name, confidence_overall=50,
        confidence_evidence=evidence, confidence_freshness=fresh, confidence_consistency=100,
        confidence_identity=100, confidence_analytic=-1, coverage=50,
        first_seen_at=sent, last_seen_at=sent, missing=list(finding.missing), inputs=finding.inputs)
    facts = {field: {"value": value, "confidence": 9500, "authority_rank": 2,
        "occurred_at": sent.isoformat(), "source_ref_id": receipts[0].event_id,
        "independence_group": "gmail"} for field, value, _ in finding.facts}
    if persist:
        from .test_support_derived_provenance import _fact_schema
        from genios_engine.context.support_situations import _upsert, _write_fact
        _fact_schema(c)
        c.execute(text("""create table context_situations (
            situation_id text primary key, org_id text, correlation_id text, anchor_node_id text,
            situation_type text, domain text, status text, confidence_overall int,
            confidence_evidence int, confidence_freshness int, confidence_consistency int,
            confidence_identity int, confidence_analytic int default -1, coverage int,
            missing text, inputs text, first_seen_at timestamp, last_seen_at timestamp,
            computed_at timestamp, resolved_by text, resolved_at timestamp,
            unique(org_id,correlation_id))"""))
        # Real persistence, repeated to test receipt/upsert idempotency; neither statement
        # nor result is mocked. Qualified IDs remain fixture input, not admission proof.
        for _ in range(2):
            for field, value, kind in finding.facts:
                _write_fact(c, org_id="o", node_id="anchor", field_name=field,
                    value=value, value_type=kind, now=NOW, key=field, event_receipts=receipts)
            _upsert(c, org_id="o", corr=finding.correlation_id, node_id="anchor",
                stype="campaign_awaiting_reply", domain="admin", now=NOW, coverage=50,
                missing=list(finding.missing), inputs=finding.inputs, evidence=evidence,
                freshness=fresh, identity=100, first_seen=sent, last_seen=sent)
        row = dict(c.execute(text("select * from context_situations")).mappings().one())
        row.update(anchor_type="campaign", anchor_name=finding.display_name)
        for key in ("missing", "inputs"):
            row[key] = json.loads(row[key])
        assert row["inputs"] == finding.inputs
        for key in ("first_seen_at", "last_seen_at"):
            row[key] = datetime.fromisoformat(row[key])
        stored = c.execute(text("select field,value,confidence,authority_rank from graph_facts")).mappings().all()
        facts = {f["field"]: {**facts[f["field"]], "value":json.loads(f["value"]),
            "confidence":int(f["confidence"] * 10000), "authority_rank":f["authority_rank"]}
            for f in stored}
    bso = build_business_situation(org_id="o", situation=row,
        signal_ids=[f"qes_{r.event_id}" for r in receipts],
        evidence=[{"event_id": r.event_id, "source": r.source} for r in receipts], trace_id="fixture")
    context = build_context_slice(org_id="o", situation=row, facts=facts, observations=[],
        neighbor=(1, set(), {}), graph_version=1, eval_time=NOW, trace_id="fixture")
    package = DomainCompiler(catalog=ExpertBrainCatalog(default_authoring_root()),
        runtime_brains=InMemoryRuntimeBrains(), publisher=None, require_admission=False).compile(bso, context)
    projection = project_situation(situation=bso, context=context, root_entity_id="anchor")
    manifest = expertise_capability_manifest(package, root_entity_type="campaign", situation=bso,
        context=context, roster_v2=True, ranking_v2=True, projection=projection)
    execution = reason_native_capability(org_id="o", context=NodeContext(node_id="anchor",
        node_type="campaign", facts=facts, obs=[]), capability=manifest,
        evaluation_time=NOW, graph_version=1, config_snapshot_id=None,
        mode=ExecutionMode.SHADOW, projection=projection)
    return execution, package, facts


def test_seven_source_events_reach_the_real_compiler_and_reasoner_at_5000_bp(provenance_db):
    execution, package, facts = compile_campaign(provenance_db)
    assert DEFAULT_CONFIDENCE_FLOOR_BP == 4500
    assert execution.decision is not None
    assert execution.decision.confidence_bp == 5000, execution.decision
    assert execution.decision.selected_candidate_id is not None, execution.decision
