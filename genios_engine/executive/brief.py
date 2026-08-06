"""The Decision Brief — brief.v1, the executive unit of output.

An executive never reads raw data; they read a brief: situation, why it matters, the
recommendation, the evidence, the risks, the alternatives, the confidence, and what
happens if nothing is done. Everything below is DETERMINISTIC COMPOSITION over
already-stored truth (the signal row, the node's facts, pack templates, measured play
outcomes). No LLM writes a brief; if phrasing is ever added it goes behind
executive.validate. Law 08 holds: a play below five observations says "new play, no
data yet" — never an invented percentage.

Boundary (the L5 spec's explicit call): a brief carries NO owner, NO channel, NO
schedule. who/when/where is Layer 6's job."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.executive.modes import mode_of_signal
from genios_engine.executive.validate import validate_text
from genios_engine.executive.verbs import band_of, select_verb

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
        st = (play_stats or {}).get(play_id) or {}
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
    """Open signals → ranked briefs. Reads only columns that exist since 0005 so it
    keeps working regardless of the in-flight L4 signal-table extensions."""
    eval_time = eval_time or datetime.now(timezone.utc)
    scoring_cfg, templates = {}, {}
    if registry is not None:
        try:
            effective, _sid = registry.effective(org_id)
            if effective:
                scoring_cfg = effective.get("scoring", {}) or {}
                templates = effective.get("templates", {}) or {}
        except Exception:      # noqa: BLE001 — pack config is an enricher, never a blocker
            pass

    play_stats = {}
    try:
        from genios_engine.reason.foresight import play_win_rates
        play_stats = play_win_rates(store, org_id) or {}
    except Exception:      # noqa: BLE001 — adaptive stats are an enricher
        play_stats = {}

    with store.engine.connect() as c:
        sigs = c.execute(text(
            "select s.signal_id, s.rule_id, s.level, s.subject_node_id, s.score, "
            "s.score_inputs, s.reason_code, s.evidence, s.play, s.eval_time, "
            "n.display_name "
            "from signals s left join graph_nodes n on n.node_id=s.subject_node_id "
            "and n.org_id=s.org_id and n.valid_to is null "
            "where s.org_id=:o and s.status='open' "
            "order by s.score desc, s.created_at desc limit :l"),
            {"o": org_id, "l": max(1, min(int(limit), 100))}).fetchall()
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
            templates=templates, scoring_cfg=scoring_cfg, eval_time=eval_time))
    return out
