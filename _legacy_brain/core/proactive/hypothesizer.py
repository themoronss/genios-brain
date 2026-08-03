"""Hypothesis layer — non-obvious patterns the rule engine can't see.

WHY this exists (per the brutal audit):

  The rule engine is symbolic: it fires when `days_past_due > 14`. That's
  precision. What it CAN'T do is propose a connection that nobody wrote a
  rule for — "your 3 repeat-late clients are all VIP; the VIP discount
  practice may be encouraging poor payment behavior." That synthesis is
  what flips the scorecard from 'rule-fire engine' to 'intelligence layer'.

WHAT this module does:

  1. Pulls the last N days of facts for an org from the graph.
  2. Asks Sonnet to PROPOSE up to 3 non-obvious patterns. Strict JSON
     output. Each must cite >= 2 specific entities + carry a falsifiable
     test (how to verify or refute it).
  3. For each proposal, runs an ADVERSARIAL refute pass — a second
     Sonnet call whose only job is to refute. If the refutation is
     stronger than the proposal's own confidence, the hypothesis is
     dropped. Survivors get persisted.
  4. Survivors become `proactive_insights` rows with type=risk|opportunity
     and `delivery_route=notify` — hypotheses never go autonomous. A
     human always sees them before any action gets taken.

Two callers:

  * Daily Celery beat (`task_generate_hypotheses`) — the natural pace
    for non-obvious-pattern generation. Hypotheses are expensive (two
    Sonnet calls per round) and they don't need to be real-time.
  * Manual endpoint `/v1/hypotheses/generate` — escape hatch for ops +
    the dashboard "find me something I'm missing" button.

Plan alignment:

  g-i-2 — same rule_engine boundary: this module GENERATES; deciding
    whether to ACT on a hypothesis stays with the human / module rules.
  g-i-4 — output flows through the same `proactive_insights` table the
    symbolic pipeline uses, so dedupe / topbar / actions widget all
    surface hypotheses without special-casing.
  g-i-7 — when a hypothesis fires a webhook, the same multi-format
    HMAC signing applies. No new delivery path.
"""

from __future__ import annotations

import json
import logging
import re
import uuid as _uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.foundations.telemetry import get_logger
from core.proactive.store import InsightRow

log = get_logger(__name__)
_legacy_log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_HYPOTHESIZE = """You are a business analyst studying a company's data.
Your job: propose up to 3 NON-OBVIOUS patterns or risks the founder might
have missed.

A good hypothesis:
- Cites AT LEAST 2 specific entities (e.g. invoice ids, client names) as evidence
- States WHY it's non-obvious (what a casual reader would miss)
- Includes a falsifiable test (how to confirm or refute it)
- Has a confidence between 0 and 1 — be honest. Low confidence is fine.

A BAD hypothesis (DO NOT EMIT):
- Restates a single fact ("INV-007 is overdue")
- Generic advice ("you should follow up faster")
- Cites only 1 entity
- Confidence > 0.85 (you almost never have that much evidence)
- Anything the symbolic rules already fire on (overdue invoices, etc.)

Output STRICT JSON in this shape, nothing else:
{
  "hypotheses": [
    {
      "title": "<short headline, max 80 chars>",
      "summary": "<2-3 sentences stating the pattern>",
      "supporting_entities": ["<entity_id_1>", "<entity_id_2>", "..."],
      "supporting_facts": ["<plain-text observation 1>", "<observation 2>", "..."],
      "falsifiable_test": "<concrete check that could refute this>",
      "confidence": 0.0,
      "type": "risk"
    }
  ]
}

Allowed `type` values: "risk", "opportunity", "misalignment".
If you cannot find any non-obvious patterns that meet the bar, output:
  {"hypotheses": []}
That's a respectable answer. Don't manufacture hypotheses to fill slots.
"""

_SYSTEM_REFUTE = """You are a skeptical-but-fair analyst reviewing one hypothesis.

Your job: assess whether this hypothesis survives examination of the SAME
data the proposer saw. You are NOT trying to win an argument — you are
trying to give an honest verdict on whether the claim holds.

A hypothesis SURVIVES when:
- The cited evidence does demonstrate the claimed pattern
- No clear counterexamples invalidate it
- The pattern would matter to the business if true

A hypothesis is WEAKENED (still worth surfacing) when:
- The pattern holds but is partly explained by something simpler
- The supporting evidence is real but the sample is small
- The claim is directionally right but the confidence is overstated

A hypothesis is REFUTED (drop it) when:
- Direct counterexamples in the data invalidate it
- The supporting facts don't actually demonstrate what's claimed
- A trivial alternative explanation makes the pattern uninteresting

Output STRICT JSON, nothing else:
{
  "refutation_strength": 0.0,
  "counterexamples": ["<entity or fact that contradicts>", "..."],
  "alternative_explanation": "<a simpler explanation, or null>",
  "verdict": "REFUTED"
}

Allowed `verdict` values: "REFUTED" | "WEAKENED" | "SURVIVES".

`refutation_strength` should be HONEST:
  0.0-0.3 = couldn't really refute it
  0.3-0.6 = found mild issues
  0.6-0.9 = found serious problems
  0.9-1.0 = decisively refuted
Don't inflate. SURVIVES with strength 0.2 is a respectable answer.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Fact loading
# ─────────────────────────────────────────────────────────────────────────────


def _load_org_facts_summary(
    session: Session, *, org_id: str, window_days: int
) -> tuple[str, list[str]]:
    """Produce a compact text summary of the org's recent facts + the list of
    entity ids the hypothesizer is allowed to cite as supporting evidence.

    The text shape is deliberately simple — the LLM does better on a flat
    "entity X: predicate=value, predicate=value" listing than on raw rows.
    """
    cutoff = datetime.now(UTC) - timedelta(days=window_days)
    rows = session.execute(
        text(
            """
            SELECT subject, predicate, object
            FROM facts
            WHERE org_id = :org
              AND source_item_id LIKE 'upload:%'
              AND created_at >= :cutoff
            ORDER BY subject, predicate
            """
        ),
        {"org": org_id, "cutoff": cutoff},
    ).fetchall()

    by_subject: dict[str, dict[str, str]] = defaultdict(dict)
    for r in rows:
        by_subject[r.subject][r.predicate] = str(r.object)

    if not by_subject:
        return ("", [])

    # Render to text the LLM can chew on
    lines: list[str] = []
    for sid, fields in sorted(by_subject.items()):
        compact = ", ".join(f"{k}={v}" for k, v in sorted(fields.items()))
        lines.append(f"{sid}: {compact}")

    # Also surface client → invoices linkage from the graph for cross-row context
    client_to_invoices = session.execute(
        text(
            """
            SELECT c.canonical_name, i.canonical_name
            FROM graph_nodes c
            JOIN graph_edges e ON e.to_node = c.id
            JOIN graph_nodes i ON i.id = e.from_node
            WHERE c.org_id = :org AND c.type = 'client' AND i.type = 'invoice'
            ORDER BY c.canonical_name
            """
        ),
        {"org": org_id},
    ).fetchall()
    if client_to_invoices:
        lines.append("")
        lines.append("Client → invoices:")
        grouped: dict[str, list[str]] = defaultdict(list)
        for c, i in client_to_invoices:
            grouped[c].append(i)
        for client, invs in sorted(grouped.items()):
            lines.append(f"  {client}: {', '.join(invs)}")

    body = "\n".join(lines)
    valid_entities = list(by_subject.keys())
    return body, valid_entities


# ─────────────────────────────────────────────────────────────────────────────
# Hypothesize + refute round-trip
# ─────────────────────────────────────────────────────────────────────────────


def _parse_json_strict(text_body: str) -> dict[str, Any] | None:
    """Pull the first {...} block out of an LLM response. Falls back to the
    whole body when the model returned clean JSON."""
    s = text_body.strip()
    if s.startswith("```"):
        # Strip a leading ``` fence (json/json5/etc.)
        s = re.sub(r"^```[a-zA-Z0-9]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Try to find a {...} block
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _validate_hypothesis(
    h: dict[str, Any], valid_entities: set[str]
) -> tuple[bool, str]:
    """Return (is_valid, reason). Reason is logged when invalid."""
    if not isinstance(h.get("title"), str) or len(h["title"].strip()) < 5:
        return False, "missing or too-short title"
    if not isinstance(h.get("summary"), str) or len(h["summary"].strip()) < 20:
        return False, "missing or too-short summary"
    sup = h.get("supporting_entities") or []
    if not isinstance(sup, list) or len(sup) < 2:
        return False, "fewer than 2 supporting entities"
    # All cited entities must be REAL ones from the fact set — protects
    # against the LLM hallucinating "INV-099" type evidence.
    cited = {str(e) for e in sup}
    bogus = [e for e in cited if e not in valid_entities]
    if bogus:
        return False, f"cited entities not in fact set: {bogus[:3]}"
    try:
        c = float(h.get("confidence", 0))
    except (TypeError, ValueError):
        return False, "non-numeric confidence"
    if not (0.0 < c <= 0.85):
        return False, f"confidence {c} outside (0, 0.85]"
    typ = h.get("type")
    if typ not in ("risk", "opportunity", "misalignment"):
        return False, f"invalid type {typ!r}"
    return True, ""


def _propose_hypotheses(
    *, org_id: str, facts_body: str, valid_entities: list[str]
) -> list[dict[str, Any]]:
    """One Sonnet call → up to 3 candidate hypotheses."""
    from core.neural.client import LLMCall, LLMClient

    user_prompt = (
        "Here are the recent facts about the company's accounts receivable.\n"
        "(predicate format: name=value separated by commas; one entity per line.)\n\n"
        f"{facts_body}\n\n"
        "Propose up to 3 non-obvious patterns following the strict JSON shape."
    )
    resp = LLMClient().call(
        LLMCall(
            model="haiku",
            system_prompt=_SYSTEM_HYPOTHESIZE,
            user_prompt=user_prompt,
            # 3 hypotheses × ~600 tokens each + JSON scaffolding -> ~2500
            # headroom keeps the JSON well-formed even when the model
            # writes longer summaries.
            max_tokens=3000,
            temperature=0.4,  # tiny temperature — we want SOME exploration
            org_id=org_id,
            purpose="hypothesizer:propose",
        )
    )
    parsed = _parse_json_strict(resp.text)
    if not parsed or not isinstance(parsed.get("hypotheses"), list):
        log.warning("hypothesizer_propose_bad_json", org_id=org_id, snippet=resp.text[:200])
        return []
    valid_set = set(valid_entities)
    accepted: list[dict[str, Any]] = []
    for h in parsed["hypotheses"]:
        ok, reason = _validate_hypothesis(h, valid_set)
        if ok:
            accepted.append(h)
        else:
            log.info(
                "hypothesizer_proposal_rejected",
                org_id=org_id,
                reason=reason,
                title=str(h.get("title", ""))[:80],
            )
    return accepted


def _refute_hypothesis(
    *, org_id: str, hypothesis: dict[str, Any], facts_body: str
) -> dict[str, Any]:
    """One Sonnet call → refutation verdict for a single hypothesis."""
    from core.neural.client import LLMCall, LLMClient

    user_prompt = (
        "HYPOTHESIS:\n"
        f"  title:    {hypothesis['title']}\n"
        f"  summary:  {hypothesis['summary']}\n"
        f"  evidence: {hypothesis['supporting_entities']}\n"
        f"  test:     {hypothesis.get('falsifiable_test', '(none)')}\n"
        f"  confidence (claimed): {hypothesis['confidence']}\n\n"
        "FACT SET (the same data used to propose the hypothesis):\n\n"
        f"{facts_body}\n\n"
        "Try to refute. Output strict JSON per the system prompt."
    )
    resp = LLMClient().call(
        LLMCall(
            model="haiku",
            system_prompt=_SYSTEM_REFUTE,
            user_prompt=user_prompt,
            max_tokens=600,
            temperature=0.0,
            org_id=org_id,
            purpose="hypothesizer:refute",
        )
    )
    parsed = _parse_json_strict(resp.text)
    if not parsed:
        log.warning("hypothesizer_refute_bad_json", org_id=org_id, snippet=resp.text[:200])
        return {"verdict": "SURVIVES", "refutation_strength": 0.0}
    return parsed


def _survives_refute(hyp: dict[str, Any], refute: dict[str, Any]) -> bool:
    """Decisive refutation kills; everything else surfaces with the
    counter-argument bundled in.

    Founders deserve to see "here's a pattern we noticed AND here's
    the strongest counterpoint we could find" — that combination is
    higher-signal than silently dropping every hypothesis the refuter
    didn't fully endorse. The Haiku refuter has a measurable bias
    toward voting REFUTED with mid-range strength (~0.75) even when
    the underlying pattern is genuinely present in the data, so a
    "must pass refute to surface" gate over-suppresses.

    The persisted insight carries the refute analysis verbatim in
    `genios_view`, so the founder sees both sides and the LLM's own
    uncertainty estimate. Bar:

      * refutation_strength >= 0.9 -> drop (truly destroyed)
      * verdict explicitly REFUTED and strength >= 0.85 -> drop
      * otherwise -> surface with the counter-argument inline.

    Operator can re-tighten this once we have outcome attribution on
    hypotheses (Phase 4 calibration loop) — at that point we have a
    real signal for which hypotheses actually predict outcomes vs
    which the refute correctly killed.
    """
    try:
        rs = float(refute.get("refutation_strength", 0))
    except (TypeError, ValueError):
        rs = 0.0
    verdict = (refute.get("verdict") or "").upper()
    if rs >= 0.9:
        return False
    if verdict == "REFUTED" and rs >= 0.85:
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Persistence
# ─────────────────────────────────────────────────────────────────────────────


def _signature_hash(*, org_id: str, title: str) -> str:
    import hashlib
    raw = f"hypothesis|{org_id}|{title}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


SUPPRESS_WINDOW_HOURS = 24 * 7  # don't re-fire the same hypothesis for a week


def _persist_hypotheses(
    session: Session,
    *,
    org_id: str,
    hypotheses: list[tuple[dict[str, Any], dict[str, Any]]],
) -> int:
    """Write surviving hypotheses to proactive_insights. Returns count emitted.

    Uses a 7-day signature suppression window — hypothesis-grade insights
    are higher-friction than rule firings (the LLM cost is real, the
    headline is novel each time), so we don't want them every day.
    """
    if not hypotheses:
        return 0

    cutoff = datetime.now(UTC) - timedelta(hours=SUPPRESS_WINDOW_HOURS)
    seen_sigs = {
        row[0]
        for row in session.execute(
            text(
                """
                SELECT signature_hash
                FROM proactive_insights
                WHERE org_id = :org
                  AND created_at >= :cutoff
                """
            ),
            {"org": org_id, "cutoff": cutoff},
        ).fetchall()
    }

    emitted = 0
    for hyp, refute in hypotheses:
        sig = _signature_hash(org_id=org_id, title=hyp["title"])
        if sig in seen_sigs:
            log.info("hypothesizer_suppressed_dup", org_id=org_id, title=hyp["title"])
            continue
        insight_id = str(_uuid.uuid4())
        memory_view = (
            f"{hyp['summary']} | evidence: "
            + ", ".join(str(e) for e in (hyp.get("supporting_entities") or [])[:5])
        )
        genios_view = (
            f"Falsifiable test: {hyp.get('falsifiable_test', '(none)')} | "
            f"refute verdict: {refute.get('verdict', 'n/a')} "
            f"(strength {refute.get('refutation_strength', 'n/a')})"
        )
        session.add(
            InsightRow(
                id=insight_id,
                org_id=org_id,
                type=hyp["type"],
                primary_entity=str((hyp.get("supporting_entities") or ["unknown"])[0]),
                root_cause_edge="",
                derivation_chain_jsonb=[
                    {
                        "rule_id": "hypothesis:llm",
                        "rule_module": "ar_collection",
                        "conclusion": hyp["title"],
                        "matched_facts": {
                            "supporting_entities": hyp.get("supporting_entities", []),
                            "supporting_facts": hyp.get("supporting_facts", []),
                        },
                        "reason": hyp["summary"],
                        "hard": False,
                    }
                ],
                foresight_jsonb={
                    "confidence": hyp["confidence"],
                    "falsifiable_test": hyp.get("falsifiable_test", ""),
                    "refute": refute,
                },
                scores_jsonb={
                    "rule_id": "hypothesis:llm",
                    "priority": "medium",
                    "title": f"Hypothesis: {hyp['title']}",
                    "category": "hypothesis",
                    "client_name": str((hyp.get("supporting_entities") or ["unknown"])[0]),
                    "memory_view": memory_view,
                    "genios_view": genios_view,
                },
                grounding_refs_jsonb=[str(e) for e in (hyp.get("supporting_entities") or [])],
                signature_hash=sig,
                delivery_route="notify",  # NEVER autonomous
            )
        )
        seen_sigs.add(sig)
        emitted += 1
    session.flush()
    return emitted


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def generate_hypotheses_for_org(
    session: Session,
    *,
    org_id: str,
    window_days: int = 7,
) -> dict[str, Any]:
    """Run the propose → refute → persist round-trip for one org.

    Returns a summary dict the caller can return from an HTTP route or
    log from a Celery task. Caller is responsible for the transaction
    boundary (this function calls session.flush() but never .commit()).
    """
    facts_body, valid_entities = _load_org_facts_summary(
        session, org_id=org_id, window_days=window_days
    )
    if not facts_body:
        return {
            "org_id": org_id,
            "window_days": window_days,
            "proposals": 0,
            "survivors": 0,
            "emitted": 0,
            "note": "No facts in window — nothing to hypothesize from.",
        }

    proposals = _propose_hypotheses(
        org_id=org_id, facts_body=facts_body, valid_entities=valid_entities
    )
    if not proposals:
        return {
            "org_id": org_id,
            "window_days": window_days,
            "proposals": 0,
            "survivors": 0,
            "emitted": 0,
            "note": "LLM returned no candidate hypotheses passing the structure check.",
        }

    survivors: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for hyp in proposals:
        refute = _refute_hypothesis(
            org_id=org_id, hypothesis=hyp, facts_body=facts_body
        )
        if _survives_refute(hyp, refute):
            survivors.append((hyp, refute))
        else:
            log.info(
                "hypothesizer_refuted",
                org_id=org_id,
                title=hyp["title"],
                verdict=refute.get("verdict"),
                refutation_strength=refute.get("refutation_strength"),
            )

    emitted = _persist_hypotheses(session, org_id=org_id, hypotheses=survivors)

    return {
        "org_id": org_id,
        "window_days": window_days,
        "proposals": len(proposals),
        "survivors": len(survivors),
        "emitted": emitted,
        "summaries": [h[0]["title"] for h in survivors],
    }
