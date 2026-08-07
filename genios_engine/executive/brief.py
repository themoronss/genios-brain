"""The Decision Brief — brief.v1, the executive unit of output.

An executive never reads raw data; they read a brief: situation, why it matters, the
recommendation, the evidence, the risks, the alternatives, the confidence, and what
happens if nothing is done. Everything below is DETERMINISTIC COMPOSITION over
already-stored truth (the signal row, the node's facts, pack templates, measured play
outcomes). No LLM writes a brief; if phrasing is ever added it goes behind
executive.validate. Law 08 holds: a play below five observations says "new play, no
data yet" — never an invented percentage.

Boundary (the L5 spec's explicit call): a brief carries NO owner, NO channel, NO
schedule. who/when/where is Layer 5.2's job."""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import text

from genios_engine.executive.authority import (
    AUTHORITATIVE_REASON_CODE_SQL,
    AUTHORITATIVE_SCORE_INPUTS_SQL,
    AUTHORITATIVE_SCORE_SQL,
    AUTHORITATIVE_SIGNAL_JOINS,
    AUTHORITATIVE_SIGNAL_PREDICATE,
    EXECUTIVE_LEVEL_SQL,
    EXECUTIVE_RULE_ID_SQL,
    authoritative_play_win_rates,
    authority_time,
)
from genios_engine.executive.modes import mode_of_signal
from genios_engine.executive.validate import validate_text
from genios_engine.executive.verbs import band_of, select_verb
from genios_engine.reason.foresight import play_stat_key

BRIEF_VERSION = "brief.v1"
MIN_PLAY_N = 5                     # Law 08: below this, a play is "new", never a percentage


def _val(f):
    v = f.get("value") if isinstance(f, dict) else f
    return str(v).strip('"') if v is not None else None


def compose_brief(*, signal: dict, facts: dict, entity_name: str | None,
                  play_stats: dict | None, templates: dict | None,
                  scoring_cfg: dict | None, eval_time: datetime) -> dict:
    """Pure composition: (signal row, node facts, pack data, clock) → brief.v1 dict.
    Deterministic and replayable — same inputs, byte-same brief."""
    rc = str(signal.get("reason_code") or signal.get("rule_id") or "signal")
    level = str(signal.get("level") or "prescriptive")
    score = int(signal.get("score") or 0)
    score_inputs = signal.get("score_inputs") or {}
    if isinstance(score_inputs, str):
        try:
            score_inputs = json.loads(score_inputs)
        except ValueError:
            score_inputs = {}
    confidence_pct = int(score_inputs.get("C") or 0)
    band = band_of(score, (scoring_cfg or {}).get("bands"))
    mode = mode_of_signal(level)

    # situation — pack template first (tenant-authored words win), deterministic fallback
    entity = entity_name or "this contact"
    situation = None
    tpl = (templates or {}).get(rc) or {}
    fb = tpl.get("fallback") or {}
    if fb.get("situation"):
        try:
            situation = str(fb["situation"]).format(entity=entity, stage=_val(facts.get("deal.stage")) or "")
        except (KeyError, IndexError):
            situation = None
    if not situation:
        situation = f"{entity}: {rc.replace('_', ' ')}"

    # why it matters — the arithmetic, said plainly (numbers from the score inputs only)
    deal_value = _val(facts.get("deal.value"))
    why = f"score {score} ({band} band), confidence {confidence_pct}"
    if deal_value:
        why += f"; value at stake {deal_value}"

    # prediction (already computed upstream by foresight; carried on the signal or absent)
    close_prob = signal.get("close_probability_pct")

    verb, verb_reason = select_verb(
        level=level, band=band, confidence_pct=confidence_pct,
        close_probability_pct=close_prob,
        cfg=(scoring_cfg or {}).get("verbs"))

    # play + measured honesty (Law 08)
    play_id = signal.get("play")
    play = None
    if play_id:
        stat_key = play_stat_key(
            str(signal.get("pack_id") or ""),
            str(signal.get("pack_version") or ""),
            str(play_id),
        )
        st = (play_stats or {}).get(stat_key) or {}
        n = int(st.get("n") or 0)
        play = {"play_id": play_id,
                "measured": ({"win_rate_lb_pct": int(round(float(st.get("rate_lb", 0)) * 100)),
                              "n": n} if n >= MIN_PLAY_N
                             else {"label": "new play — no data yet", "n": n})}

    # risks — negative facts the node already carries (no speculation)
    risks = []
    if _val(facts.get("thread.ball_in_court")) == "us":
        risks.append("the ball is in our court — silence reads as neglect")
    if signal.get("open_discrepancies"):
        risks.append(f"{signal['open_discrepancies']} unresolved record conflict(s) on this entity")

    # cost of inaction — only what the arithmetic supports; nothing invented
    cost = None
    if level == "prescriptive" and deal_value:
        cost = f"deal value {deal_value} continues to decay while unanswered"

    evidence = signal.get("evidence") or []
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except ValueError:
            evidence = []

    brief = {
        "version": BRIEF_VERSION,
        "signal_id": signal.get("signal_id"),
        "entity": entity, "entity_id": signal.get("subject_node_id"),
        "mode": mode, "level": level, "band": band,
        "situation": situation[:200],
        "why_it_matters": why,
        "recommendation": {"verb": verb, "reason": verb_reason, "play": play},
        "evidence": evidence,
        "risks": risks,
        "confidence_pct": confidence_pct,
        "score": score, "score_inputs": score_inputs,
        "cost_of_inaction": cost,
        "provenance": {"rule_id": signal.get("rule_id"),
                       "config_snapshot_id": signal.get("config_snapshot_id"),
                       "eval_time": str(signal.get("eval_time") or ""),
                       "composed_at": eval_time.isoformat()},
    }
    # belt + braces: even deterministic composition is checked against its own facts
    ok, offending = validate_text(situation, facts, {"entity": entity, "reason": rc})
    brief["grounded"] = bool(ok)
    if not ok:
        brief["grounding_note"] = offending
    return brief


# ── store-reading loader (org-scoped; SELECTs only stable pre-L4 columns) ─────────
def load_briefs(store, org_id: str, *, registry=None, limit: int = 20,
                eval_time: datetime | None = None) -> list[dict]:
    """Authoritative open decisions → ranked briefs at one explicit evaluation time.

    ``registry`` remains in the public API for compatibility, but current registry state is
    intentionally not used: every brief is rendered from the exact config snapshot bound to
    its audited decision.
    """
    eval_time = authority_time(eval_time)
    _ = registry

    play_stats = {}
    try:
        play_stats = authoritative_play_win_rates(store, org_id, eval_time=eval_time) or {}
    except Exception:      # noqa: BLE001 — adaptive stats are an enricher
        play_stats = {}

    with store.engine.connect() as c:
        c.execute(text(
            "select graph_version from graph_versions where org_id=:o for share"),
            {"o": org_id})
        sigs = c.execute(text(
            "select s.signal_id, " + EXECUTIVE_RULE_ID_SQL + " as rule_id, "
            + EXECUTIVE_LEVEL_SQL + " as level, rr.root_node_id as subject_node_id, "
            + AUTHORITATIVE_SCORE_SQL + " as score, "
            + AUTHORITATIVE_SCORE_INPUTS_SQL + " as score_inputs, "
            + AUTHORITATIVE_REASON_CODE_SQL + " as reason_code, "
            "coalesce(authority_payload.payload->'evidence', selected_rc.evidence_refs) "
            "as evidence, selected_rc.play_id as play, "
            "authority_cfg.pack_id as pack_id, "
            "authority_cfg.effective->>'version' as pack_version, "
            "rr.evaluation_time as eval_time, rr.config_snapshot_id, "
            "authority_cfg.effective->'scoring' as scoring_cfg, "
            "authority_cfg.effective->'templates' as templates, n.display_name "
            "from signals s " + AUTHORITATIVE_SIGNAL_JOINS +
            "left join reasoning_context_payloads authority_payload "
            "on authority_payload.org_id=authority_ctx.org_id and "
            "authority_payload.context_snapshot_id=authority_ctx.context_snapshot_id "
            "left join graph_nodes n on n.node_id=rr.root_node_id "
            "and n.org_id=s.org_id and n.valid_to is null "
            "where s.org_id=:o and s.status='open' and "
            + AUTHORITATIVE_SIGNAL_PREDICATE + " "
            "order by selected_rc.final_utility_bp desc, rr.completed_at desc, "
            "rr.capability_id asc, rr.root_node_id asc, s.signal_id asc limit :l"),
            {"o": org_id, "l": max(1, min(int(limit), 100)),
             "authority_time": eval_time}).fetchall()
        node_ids = list({r.subject_node_id for r in sigs})
        facts_by_node: dict[str, dict] = {}
        if node_ids:
            for r in c.execute(text(
                    "select subject_node_id nid, field, value, occurred_at from graph_facts "
                    "where org_id=:o and subject_node_id = any(:n) "
                    "and valid_to is null and status='active'"),
                    {"o": org_id, "n": node_ids}):
                facts_by_node.setdefault(r.nid, {})[r.field] = {
                    "value": r.value, "occurred_at": r.occurred_at}
            disc = {r.nid: int(r.c) for r in c.execute(text(
                "select subject_node_id nid, count(*) c from discrepancies "
                "where org_id=:o and subject_node_id = any(:n) and status='open' "
                "group by subject_node_id"), {"o": org_id, "n": node_ids})}
        else:
            disc = {}

    out = []
    for r in sigs:
        sig = dict(r._mapping)
        sig["open_discrepancies"] = disc.get(r.subject_node_id, 0)
        out.append(compose_brief(
            signal=sig, facts=facts_by_node.get(r.subject_node_id, {}),
            entity_name=r.display_name, play_stats=play_stats,
            templates=(r.templates if isinstance(r.templates, dict) else {}),
            scoring_cfg=(r.scoring_cfg if isinstance(r.scoring_cfg, dict) else {}),
            eval_time=eval_time))
    return out
