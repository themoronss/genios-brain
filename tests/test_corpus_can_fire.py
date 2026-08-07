"""CALIBRATION RATCHET — can the shipped rules actually produce a signal?

A rule that cannot clear the gate under ANY reachable state is not a quiet rule; it is
dead code that looks like product. The dossier already found this class once ("six
single-source rules were mathematically unable to fire") and fixed it with an impact
floor of 40 — the number was too small, and nothing tested the property, so the corpus
silently regressed to ZERO fireable rules once L2 confidence became deterministic.

What this locks:
  * the fixture is the REALISTIC common case — an email-derived, evidence-guarded
    rank-2 fact from ONE source (a tenant with no CRM is exactly this)
  * a rule "can fire" if some elapsed time exists where S >= s_min and C >= c_min
  * rules that cannot are listed in KNOWN_UNFIREABLE, and that list may only SHRINK

Changing FACT_CONF_BY_RANK, i_floor, s_min, c_weights or the weights re-runs this
arithmetic. If a change kills rules, the test names them.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.context.pipeline import FACT_CONF_BY_RANK
from genios_engine.packs.general_v1 import GENERAL_V1
from genios_engine.packs.sales_v1 import SALES_V1
from genios_engine.reason.engine import NodeContext, score_rule
from genios_engine.reason.rules import rule_from_dict

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
SEARCH_DAYS = 45

# Rules whose urgency curve (h) is too slow relative to their own trigger threshold, or
# which carry no deal linkage (impact floor does not apply → I = 0). These are PACK
# DESIGN issues, not confidence issues: they stay dead at conf = 1.0 and full
# corroboration. Fixing one means retuning its h (or giving it deal linkage) — and
# deleting its entry here.
KNOWN_UNFIREABLE = {
    "objection_open", "security_review_pending", "budget_freeze", "legal_in_review",
    "timeline_slip", "champion_quiet", "meeting_no_followup", "intro_followup",
}


def _context(rule_d: dict, days: float, conf: float) -> NodeContext:
    """A node whose facts satisfy the rule, with the urgency clock at `days`."""
    path = rule_d["urgency"]["path"]
    facts = {path: {"value": (NOW - timedelta(days=days)).isoformat(), "confidence": conf,
                    "authority_rank": 2, "occurred_at": NOW - timedelta(days=days),
                    "src_count": 1}}
    for c in rule_d.get("when", []):
        if c.get("fn") is None and "path" in c and c["path"] not in facts:
            facts[c["path"]] = {"value": c.get("value"), "confidence": conf,
                                "authority_rank": 2, "occurred_at": NOW, "src_count": 1}
    obs = [{"kind": c["has_obs"], "occurred_at": NOW}
           for c in rule_d.get("when", []) if "has_obs" in c]
    return NodeContext(node_id="n1", node_type=rule_d.get("scope", "person"),
                       facts=facts, obs=obs)


def _peak(rule_d: dict, scoring_cfg: dict, conf: float) -> tuple[int, int]:
    """(best S, its C) over every reachable elapsed time. Quarter-day resolution."""
    rule = rule_from_dict(rule_d)
    best = (0, 0)
    for i in range(1, SEARCH_DAYS * 4):
        S, inputs = score_rule(_context(rule_d, i / 4, conf), rule, NOW, scoring_cfg)
        if S > best[0]:
            best = (S, int(inputs["C"]))
    return best


def _all_rules():
    for pack in (SALES_V1, GENERAL_V1):
        for rule_d in pack["rules"]:
            yield pack["id"], rule_d


def test_shipped_rules_can_produce_a_signal():
    cfg = SALES_V1["scoring_defaults"]
    s_min, c_min = cfg["gate"]["s_min"], cfg["gate"]["c_min"]
    conf = FACT_CONF_BY_RANK[2]                 # the real L2 value for extracted facts
    dead = []
    for pack_id, rule_d in _all_rules():
        if rule_d["id"] in KNOWN_UNFIREABLE:
            continue
        S, C = _peak(rule_d, cfg, conf)
        if S < s_min or C < c_min:
            dead.append(f"{pack_id}/{rule_d['id']}: peak S={S} C={C} "
                        f"(needs S>={s_min}, C>={c_min})")
    assert not dead, (
        f"rules that can NEVER fire at FACT_CONF_BY_RANK[2]={conf} — the corpus is "
        f"mis-calibrated, not quiet:\n" + "\n".join(dead))


def test_known_unfireable_list_only_shrinks():
    """Every name in KNOWN_UNFIREABLE must still be genuinely unfireable. When a pack
    fix revives one, this fails and forces the entry to be deleted — the list can never
    silently grow into an excuse."""
    cfg = SALES_V1["scoring_defaults"]
    s_min = cfg["gate"]["s_min"]
    conf = FACT_CONF_BY_RANK[2]
    revived = []
    for pack_id, rule_d in _all_rules():
        if rule_d["id"] not in KNOWN_UNFIREABLE:
            continue
        S, _C = _peak(rule_d, cfg, conf)
        if S >= s_min:
            revived.append(f"{pack_id}/{rule_d['id']} (peak S={S}) — remove it from "
                           f"KNOWN_UNFIREABLE")
    assert not revived, "\n".join(revived)


def _peak_at(rule_d: dict, cfg: dict, *, conf: float, rank: int, src: int,
             deal_value: str | None = None) -> int:
    """Peak S for one evidence quality — rank/corroboration/known deal value."""
    rule = rule_from_dict(rule_d)
    best = 0
    for i in range(1, SEARCH_DAYS * 4):
        ctx = _context(rule_d, i / 4, conf)
        for f in ctx.facts.values():
            f["authority_rank"], f["src_count"] = rank, src
        if deal_value:
            ctx.facts["deal.value"] = {"value": deal_value, "confidence": conf,
                                       "authority_rank": rank, "occurred_at": NOW,
                                       "src_count": src}
        S, _ = score_rule(ctx, rule, NOW, cfg)
        best = max(best, S)
    return best


# The evidence ladder, weakest first. This is the cross-source intelligence property in
# one table: one email says something → we act cautiously; a second independent source
# agrees → more; the CRM (system of record) says it → more still; and a KNOWN deal value
# replaces the i_floor guess with fact.
EVIDENCE_LADDER = [
    ("one email extraction",      dict(conf=FACT_CONF_BY_RANK[2], rank=2, src=1)),
    ("two independent sources",   dict(conf=FACT_CONF_BY_RANK[2], rank=2, src=2)),
    ("system of record (CRM)",    dict(conf=FACT_CONF_BY_RANK[3], rank=3, src=1)),
    ("CRM + known deal value",    dict(conf=FACT_CONF_BY_RANK[3], rank=3, src=1,
                                       deal_value="40000")),
]


def test_corroboration_never_lowers_a_score():
    """MONOTONICITY — the core cross-source guarantee. Learning that a SECOND source
    agrees, or that the system of record agrees, or what the deal is actually worth, may
    never make a signal score LOWER. Break this and the engine punishes integration:
    connect more tools, see fewer signals. Every rule, every rung."""
    cfg = SALES_V1["scoring_defaults"]
    regressions = []
    for pack_id, rule_d in _all_rules():
        scores = [(name, _peak_at(rule_d, cfg, **kw)) for name, kw in EVIDENCE_LADDER]
        for (lo_name, lo), (hi_name, hi) in zip(scores, scores[1:]):
            if hi < lo:
                regressions.append(f"{pack_id}/{rule_d['id']}: {lo_name}={lo} but "
                                   f"{hi_name}={hi} — better evidence scored WORSE")
    assert not regressions, "\n".join(regressions)


def test_better_evidence_wakes_up_more_rules():
    """The ladder must actually pay: strictly more of the corpus becomes reachable as
    evidence improves. If these counts ever flatten, corroboration/authority stopped
    reaching the gate and the whole 'connect your tools' promise is decorative."""
    cfg = SALES_V1["scoring_defaults"]
    s_min = cfg["gate"]["s_min"]
    counts = [sum(1 for _p, r in _all_rules() if _peak_at(r, cfg, **kw) >= s_min)
              for _name, kw in EVIDENCE_LADDER]
    assert counts == sorted(counts), f"evidence ladder is not monotonic: {counts}"
    assert counts[0] >= 1, "the weakest tier (email-only) must still produce signals"
    assert counts[-1] > counts[0], (
        f"connecting a CRM and learning deal value changed nothing: {counts}")


def test_every_known_unfireable_name_exists():
    """No stale names: an entry for a deleted rule would hide a real regression."""
    ids = {rule_d["id"] for _p, rule_d in _all_rules()}
    stale = sorted(KNOWN_UNFIREABLE - ids)
    assert not stale, f"KNOWN_UNFIREABLE names rules that no longer exist: {stale}"
