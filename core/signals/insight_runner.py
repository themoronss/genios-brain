"""Graph-path — turn computed SIGNALS into human SUGGESTIONS (proactive_insights).

This is the piece that makes the 2nd-brain visible: symbolic signals
(importance / momentum) already compute per scan; here we read them per subject
and, when an *important* relationship is *cooling*, emit a real insight carrying
a concrete Next-Best-Action. Mirrors run_timing_detectors: read v2 state, write
proactive_insights (same sink, 24h signature dedupe, no commit — caller owns it).

Symbolic-only for now (importance + momentum) so it fires on what's already
live. When neural signals (ball_in_court / sentiment) land at ingest, the richer
`modules/relationship` rules take over.
"""

from __future__ import annotations

import hashlib
import uuid as _uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.actions.recommender import build_next_best_action
from core.proactive.store import InsightRow
from core.signals.types import SIG_DOMAIN, SIG_IMPORTANCE, SIG_MOMENTUM

_SUPPRESS_WINDOW_HOURS = 24
IMPORTANCE_MIN = 0.5
MOMENTUM_MAX = -0.3  # cooling


def _sig(subject: str, disc: str = "") -> str:
    return hashlib.sha256(f"relationship_cooling|{subject}|{disc}".encode()).hexdigest()[:32]


def run_relationship_detectors(session: Session, *, org_id: str) -> dict[str, Any]:
    """Emit 'important relationship cooling' insights (with NBA) from signals."""
    cutoff = datetime.now(UTC) - timedelta(hours=_SUPPRESS_WINDOW_HOURS)
    seen = {
        r[0]
        for r in session.execute(
            text(
                "SELECT signature_hash FROM proactive_insights "
                "WHERE org_id = :o AND created_at >= :c"
            ),
            {"o": org_id, "c": cutoff},
        ).fetchall()
    }

    # signals grouped by subject
    subjects: dict[str, dict[str, Any]] = {}
    for r in session.execute(
        text(
            "SELECT subject_node_id, subject_name, signal_type, value_num, value_cat "
            "FROM signals WHERE org_id = :o"
        ),
        {"o": org_id},
    ).fetchall():
        s = subjects.setdefault(r.subject_node_id, {"name": r.subject_name, "sig": {}})
        s["sig"][r.signal_type] = r.value_num if r.value_num is not None else r.value_cat

    fired = 0
    for node_id, data in subjects.items():
        sig = data["sig"]
        name = data["name"]
        importance = float(sig.get(SIG_IMPORTANCE) or 0.0)
        momentum = float(sig.get(SIG_MOMENTUM) or 0.0)
        if not (importance >= IMPORTANCE_MIN and momentum <= MOMENTUM_MAX):
            continue

        h = _sig(name)
        if h in seen:
            continue
        seen.add(h)

        nba = build_next_best_action(
            subject_name=name, recommend="reply_now", signals=sig,
            reason="important relationship cooling",
        )
        title = f"{name} — important relationship cooling"
        memory_view = (
            f"{name}: importance {round(importance, 2)} · momentum "
            f"{round(momentum, 2)} (cooling)"
        )
        session.add(
            InsightRow(
                id=str(_uuid.uuid4()),
                org_id=org_id,
                type="risk",
                primary_entity=name,
                root_cause_edge="",
                derivation_chain_jsonb=[
                    {
                        "rule_id": "relationship:important_cooling",
                        "rule_module": "relationship",
                        "conclusion": "important_relationship_going_cold",
                        "matched_facts": {"importance": importance, "momentum": momentum,
                                          "domain": sig.get(SIG_DOMAIN)},
                        "reason": nba.prescription,
                        "hard": False,
                    }
                ],
                foresight_jsonb=None,
                scores_jsonb={
                    "rule_id": "relationship:important_cooling",
                    "priority": "high",
                    "title": title,
                    "category": "relationship_cooling",
                    "client_name": name,
                    "memory_view": memory_view,
                    "genios_view": nba.prescription,
                },
                grounding_refs_jsonb=[node_id],
                signature_hash=h,
                delivery_route="notify",
            )
        )
        fired += 1

    return {"insights_fired": fired, "subjects_evaluated": len(subjects)}
