from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.packs.general_v1 import GENERAL_V1
from genios_engine.packs.merge import apply_guardrails, merge_config
from genios_engine.packs.sales_v1 import SALES_V1
from genios_engine.packs.snapshot import canonical, snapshot_id
from genios_engine.reason.engine import NodeContext, evaluate, score_rule
from genios_engine.reason.rules import rule_from_dict, rules_for_scope

# L4 pack logic — offline, deterministic. The DB path (registry.effective + runner stamping
# signals) is proven separately against real Supabase; here we lock the pure logic the pack
# system rests on: conformance, merge/guardrails/pins, snapshot, and pack-driven scoring.

NOW = datetime(2026, 7, 31, tzinfo=timezone.utc)
SC = SALES_V1["scoring_defaults"]


# ---- pack conformance ------------------------------------------------------

def test_sales_pack_is_wellformed():
    assert SALES_V1["id"] == "sales" and SALES_V1["version"] == "1.8.0"
    assert {"weights", "c_weights", "gate", "budget_per_user_day", "impact",
            "bands", "execution"} <= SC.keys()
    assert SC["weights"]["u"] + SC["weights"]["i"] + SC["weights"]["r"] == 100


def test_execution_block_is_readable_by_every_l5_unit():
    """The L5 tunables are pack data, so they merge, pin and guardrail like everything else in
    scoring_defaults. This proves the shipped block is one the engine actually consumes rather
    than a hopeful dict nobody reads."""
    from datetime import timedelta

    from genios_engine.executive.escalation import build_ladder
    from genios_engine.executive.execution import execution_config

    block = execution_config({"scoring": SC})
    assert set(block) == {"planning", "communication", "escalation", "reminder", "monitor"}
    ladder = build_ladder(eval_time=NOW, expires_at=NOW + timedelta(days=60), band="standard",
                          cfg=block["escalation"])
    assert [step.day_offset for step in ladder] == [1, 3, 7, 14]


def test_bands_are_ordered_and_in_manifest():
    assert SC["gate"]["s_min"] < SC["bands"]["high"] < SC["bands"]["critical"]


def test_every_reason_code_has_a_card_template():
    tpls = SALES_V1["templates"]
    for rc in SALES_V1["schema"]["signal_vocab"]:
        assert rc in tpls, f"{rc} has no card template"
        t = tpls[rc]
        assert "render_hint" in t and "fallback" in t and "artifact_kind" in t
        assert "headline" in t["fallback"] and "situation" in t["fallback"]


def test_every_rule_has_a_play_and_matching_vocab():
    plays, vocab = SALES_V1["plays"], set(SALES_V1["schema"]["signal_vocab"])
    for r in SALES_V1["rules"]:
        assert r["play"] in plays, f"{r['id']} references unknown play {r['play']}"
        assert r["reason_code"] in vocab, f"{r['id']} reason_code not in signal_vocab"


def test_rule_evidence_fields_are_declared_in_schema():
    fields = set(SALES_V1["schema"]["fields"])
    for r in SALES_V1["rules"]:
        for f in r["evidence_fields"]:
            assert f in fields, f"{r['id']} evidence {f} not in pack schema.fields"


# ---- merge / guardrails / pins ---------------------------------------------

def test_merge_layers_lvl1_lvl2_lvl3():
    eff = merge_config(SC, {"budget_per_user_day": 10}, {"gate": {"s_min": 60}}, [])
    assert eff["budget_per_user_day"] == 10          # LVL2 admin override wins over pack
    assert eff["gate"]["s_min"] == 60                # LVL3 learned nudge applied
    assert eff["gate"]["c_min"] == 60                # untouched pack value survives merge


def test_guardrails_clamp_hostile_overrides():
    eff = merge_config(SC, {"gate": {"c_min": 10}, "budget_per_user_day": 99,
                            "weights": {"u": 90, "i": 90, "r": 90}}, {}, [])
    assert eff["gate"]["c_min"] == 50                # absolute confidence floor
    assert eff["budget_per_user_day"] == 15          # absolute spam ceiling
    assert eff["weights"] == {"u": 45, "i": 35, "r": 20}   # sum≠100 → reset
    assert len(eff["_guardrail_rejections"]) == 3


def test_valid_lopsided_weights_are_admin_freedom():
    eff = merge_config(SC, {"weights": {"u": 90, "i": 5, "r": 5}}, {}, [])
    assert eff["weights"] == {"u": 90, "i": 5, "r": 5}     # normalized → kept
    assert eff["_guardrail_rejections"] == []


def test_pin_freezes_a_path_against_lvl3():
    eff = merge_config(SC, {}, {"gate": {"s_min": 80}}, pins=["gate.s_min"])
    assert eff["gate"]["s_min"] == 55                # pinned → LVL3 nudge rejected


# ---- snapshot hasher --------------------------------------------------------

def test_snapshot_is_canonical_and_deterministic():
    a = {"gate": {"c_min": 60, "s_min": 55}, "weights": {"u": 45, "i": 35, "r": 20}}
    b = {"weights": {"r": 20, "u": 45, "i": 35}, "gate": {"s_min": 55, "c_min": 60}}
    assert canonical(a) == canonical(b)              # key order irrelevant
    assert snapshot_id(a) == snapshot_id(b)


def test_snapshot_is_sensitive_to_any_value_change():
    base = merge_config(SC, {}, {}, [])
    moved = merge_config(SC, {"gate": {"s_min": 56}}, {}, [])
    assert snapshot_id(base) != snapshot_id(moved)


# ---- rule_from_dict / scope filtering --------------------------------------

def test_rule_from_dict_roundtrip_and_scope_filter():
    rules = [rule_from_dict(r) for r in SALES_V1["rules"]]
    assert {r.scope for r in rules} == {"deal", "person"}   # "meeting" moved to general_v1
    assert [r.id for r in rules_for_scope(rules, "deal")] == \
        ["stalled_deal", "single_threaded_deal", "competitor_in_live_deal"]


# ---- pack-driven scoring (the injection point) -----------------------------

def _stalled_deal_ctx():
    """deal open, last inbound 9d ago, value 200k — the live S=85 case, reconstructed."""
    return NodeContext(
        node_id="n1", node_type="deal",
        facts={
            "deal.status": {"value": "open", "confidence": 0.95, "authority_rank": 2},
            "deal.last_inbound": {"value": (NOW - timedelta(days=9)).isoformat(),
                                  "confidence": 0.9, "authority_rank": 2},
            "deal.value": {"value": 200000, "confidence": 0.8, "authority_rank": 2},
        })


def test_stalled_deal_fires_and_scores_from_pack():
    rule = rule_from_dict(SALES_V1["rules"][0])       # stalled_deal
    ctx = _stalled_deal_ctx()
    assert evaluate(ctx, rule, NOW) is True
    S, inputs = score_rule(ctx, rule, NOW, SC)
    # 9 days stale, 7-day flip → 48h past flip → R decays to 100·e^(-48/72)=51 (NOT a constant 100)
    assert (inputs["U"], inputs["I"], inputs["R"], inputs["C"]) == (95, 100, 51, 87)
    assert S == 77                                    # byte-identical to the live Supabase run


def test_recency_decays_with_staleness():
    # the R-decay fix: a fresh-crossing deal outranks a long-stale one on the R term
    rule = rule_from_dict(SALES_V1["rules"][0])
    fresh = _stalled_deal_ctx()                       # 9 days stale (just past the 7-day flip)
    stale = _stalled_deal_ctx()
    stale.facts["deal.last_inbound"]["value"] = (NOW - timedelta(days=45)).isoformat()
    _, fresh_in = score_rule(fresh, rule, NOW, SC)
    _, stale_in = score_rule(stale, rule, NOW, SC)
    assert stale_in["R"] < fresh_in["R"]              # 45-day-stale decays far below the 9-day one
    assert stale_in["R"] <= 5


def test_score_changes_when_pack_weights_change():
    rule = rule_from_dict(SALES_V1["rules"][0])
    ctx = _stalled_deal_ctx()
    all_impact = {**SC, "weights": {"u": 0, "i": 100, "r": 0}}
    S, _ = score_rule(ctx, rule, NOW, all_impact)
    assert S == 87                                    # C·I = 0.87·100 → pack truly drives L3


def test_impact_floor_protects_early_tenant_with_no_deal_value():
    rule = rule_from_dict(SALES_V1["rules"][0])
    ctx = _stalled_deal_ctx()
    ctx.facts.pop("deal.value")                       # pre-revenue: no P90 signal
    _, inputs = score_rule(ctx, rule, NOW, SC)
    assert inputs["I"] == SC["impact"]["i_floor"]     # floored at 40, not starved to 0


# ---- derived-metric + cross-entity rules (C1/C2) ---------------------------

def _rule(rid):
    return next(rule_from_dict(r) for r in SALES_V1["rules"] if r["id"] == rid)


def test_cooling_deal_fires_on_derived_engagement_and_neighbour_deal():
    """derived.engagement injected as a fact + a neighbour with an open deal → cooling_deal fires;
    raise engagement above the floor and it stops firing (proves the threshold is real)."""
    rule = _rule("cooling_deal")
    ctx = NodeContext(node_id="p1", node_type="person",
                      facts={"derived.engagement": {"value": 0.4, "confidence": 0.85, "authority_rank": 2}},
                      neighbor_facts={"deal.status": "open"})
    assert evaluate(ctx, rule, NOW) is True
    ctx.facts["derived.engagement"]["value"] = 0.9     # interaction healthy again
    assert evaluate(ctx, rule, NOW) is False
    ctx.facts["derived.engagement"]["value"] = 0.4
    ctx.neighbor_facts = {}                            # no live deal in the neighbourhood
    assert evaluate(ctx, rule, NOW) is False


def test_single_threaded_deal_fires_on_edge_count():
    rule = _rule("single_threaded_deal")
    ctx = NodeContext(node_id="d1", node_type="deal",
                      facts={"deal.status": {"value": "open", "confidence": 0.9, "authority_rank": 2}},
                      edge_count=1)
    assert evaluate(ctx, rule, NOW) is True
    ctx.edge_count = 4                                 # well-threaded deal
    assert evaluate(ctx, rule, NOW) is False


def test_competitor_in_live_deal_fires_on_neighbour_obs():
    rule = _rule("competitor_in_live_deal")
    ctx = NodeContext(node_id="d1", node_type="deal",
                      facts={"deal.status": {"value": "open", "confidence": 0.9, "authority_rank": 2}},
                      neighbor_obs={"competitor"})
    assert evaluate(ctx, rule, NOW) is True
    ctx.neighbor_obs = {"pricing_discussed"}          # rival no longer named
    assert evaluate(ctx, rule, NOW) is False


def test_deal_sentiment_negative_fires_on_derived_sentiment():
    rule = _rule("deal_sentiment_negative")
    ctx = NodeContext(node_id="p1", node_type="person",
                      facts={"derived.sentiment": {"value": -0.5, "confidence": 0.85, "authority_rank": 2}},
                      neighbor_facts={"deal.status": "open"})
    assert evaluate(ctx, rule, NOW) is True
    ctx.facts["derived.sentiment"]["value"] = 0.2      # net-positive again
    assert evaluate(ctx, rule, NOW) is False


# ---- C3 composite deal-health planner --------------------------------------

def test_plan_composites_clusters_neighbour_signals_into_one_verdict():
    """Two DISTINCT concerns — one on the deal, one on a neighbouring contact — compose into a
    single deal_health plan whose evidence lists both member reason_codes and whose score is the
    strongest driver's."""
    from genios_engine.reason.composer import plan_composites
    deal, contact = "d1", "p1"
    adj = {deal: {contact}, contact: {deal}}
    sigs = [
        {"subject_node_id": deal, "reason_code": "stalled_deal", "score": 72, "score_inputs": {"C": 87}},
        {"subject_node_id": contact, "reason_code": "objection_open", "score": 80, "score_inputs": {"C": 90}},
    ]
    plans = plan_composites([deal], sigs, adj)
    assert len(plans) == 1
    p = plans[0]
    assert p["deal_id"] == deal and p["score"] == 80        # strongest driver
    assert p["codes"] == ["objection_open", "stalled_deal"]  # score-desc: 80 then 72
    assert {e["value"] for e in p["evidence"]} == {"stalled_deal", "objection_open"}
    assert p["inputs"]["composite_of"] == ["objection_open", "stalled_deal"]


def test_plan_composites_needs_two_distinct_concerns():
    from genios_engine.reason.composer import plan_composites
    deal, contact = "d1", "p1"
    adj = {deal: {contact}, contact: {deal}}
    # two signals but the SAME reason_code → not a compound story, no composite
    same = [{"subject_node_id": deal, "reason_code": "stalled_deal", "score": 70, "score_inputs": {}},
            {"subject_node_id": contact, "reason_code": "stalled_deal", "score": 60, "score_inputs": {}}]
    assert plan_composites([deal], same, adj) == []
    # a single concern → no composite
    lone = [{"subject_node_id": deal, "reason_code": "stalled_deal", "score": 70, "score_inputs": {}}]
    assert plan_composites([deal], lone, adj) == []


# ---- general pack (relationship hygiene, any contact — not deal-linked) ---------------------
# same conformance bar as sales_v1: this pack ships to production too, evaluated alongside sales
# by reason/runner.run_all on every org.

GC = GENERAL_V1["scoring_defaults"]


def test_general_pack_is_wellformed():
    assert GENERAL_V1["id"] == "general" and GENERAL_V1["version"] == "1.1.1"
    assert {"weights", "c_weights", "gate", "budget_per_user_day", "impact",
            "bands"} <= GC.keys()
    assert GC["weights"]["u"] + GC["weights"]["i"] + GC["weights"]["r"] == 100
    assert GC["gate"]["s_min"] < GC["bands"]["high"] < GC["bands"]["critical"]
    # shared org-wide daily budget across packs (runner._budget_used counts every org signal
    # regardless of pack) — must match sales' value or the combined cap silently changes.
    assert GC["budget_per_user_day"] == SC["budget_per_user_day"]


def test_general_every_reason_code_has_a_card_template():
    tpls = GENERAL_V1["templates"]
    for rc in GENERAL_V1["schema"]["signal_vocab"]:
        assert rc in tpls, f"{rc} has no card template"
        t = tpls[rc]
        assert "render_hint" in t and "fallback" in t and "artifact_kind" in t
        assert "headline" in t["fallback"] and "situation" in t["fallback"]


def test_general_every_rule_has_a_play_and_matching_vocab():
    plays, vocab = GENERAL_V1["plays"], set(GENERAL_V1["schema"]["signal_vocab"])
    for r in GENERAL_V1["rules"]:
        assert r["play"] in plays, f"{r['id']} references unknown play {r['play']}"
        assert r["reason_code"] in vocab, f"{r['id']} reason_code not in signal_vocab"


def test_general_rule_evidence_fields_are_declared_in_schema():
    fields = set(GENERAL_V1["schema"]["fields"])
    for r in GENERAL_V1["rules"]:
        for f in r["evidence_fields"]:
            assert f in fields, f"{r['id']} evidence {f} not in pack schema.fields"


def test_sales_and_general_rule_ids_never_collide():
    """run_all evaluates both packs against the same node set — a shared rule id would collide
    on the (org_id, rule_id, subject_node_id) open-signal key and on the dedup/cooldown lookup."""
    sales_ids = {r["id"] for r in SALES_V1["rules"]}
    general_ids = {r["id"] for r in GENERAL_V1["rules"]}
    assert sales_ids & general_ids == set()


def test_unanswered_email_fires_and_scores_from_general_pack():
    rule = next(rule_from_dict(r) for r in GENERAL_V1["rules"] if r["id"] == "unanswered_email")
    ctx = NodeContext(
        node_id="p1", node_type="person",
        facts={
            "thread.ball_in_court": {"value": "us", "confidence": 0.9, "authority_rank": 2},
            "thread.last_inbound": {"value": (NOW - timedelta(days=3)).isoformat(),
                                    "confidence": 0.9, "authority_rank": 2},
        })
    assert evaluate(ctx, rule, NOW) is True
    S, inputs = score_rule(ctx, rule, NOW, GC)
    assert inputs["I"] == GC["impact"]["i_floor"]     # no deal.value on a plain contact → floored
    assert S >= GC["gate"]["s_min"]                   # clears the gate — a real, deliverable card
