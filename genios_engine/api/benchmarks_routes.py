"""Public benchmarks scorecard — honest, min-N gated, no PII.

Reimplemented for the v2 engine. The original v1 tier-1 tables (recommendations, context_calls,
calibration_models) were dropped, so metrics are recomputed from v2 sources where they exist and
returned as {value:null, reason:"insufficient_data"} otherwise (never fabricated). Public + cached;
the whole point of a benchmark is that it is the same for everyone and gameable by no one.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from genios_engine.platform import card_lifecycle
from genios_engine.platform.cache import get_cache
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()

_MIN_N = 30
_WINDOW_DAYS = 30
#: v3 since STEP-16: the acted rate counts what you did (F76) — a cached v2 body must not answer for it.
_CACHE_KEY = "benchmarks:scorecard:v3"
_CACHE_TTL = 3600


def _insufficient(n: int = 0) -> dict:
    return {"value": None, "n": n, "reason": "insufficient_data"}


def _scale(conn) -> dict:
    def count(sql: str) -> int:
        try:
            return int(conn.execute(text(sql)).scalar() or 0)
        except Exception:
            return 0
    # Tenant count gets the same min-N honesty as every metric below it. The scorecard is public on
    # purpose — a benchmark nobody can game has to be — but a raw "orgs: 2" tells a competitor our
    # exact customer count while telling a reader nothing about whether the product works. Below the
    # gate we report the gate, not the number; the metrics themselves are unaffected.
    orgs = count("select count(*) from orgs")
    return {
        "orgs": orgs if orgs >= _MIN_N else None,
        "orgs_reason": None if orgs >= _MIN_N else "below_min_n",
        "decisions_30d": count("select count(*) from decisions "
                               "where created_at > now() - interval '30 days'"),
        "entities": count("select count(*) from graph_nodes "
                          "where valid_to is null and node_type in ('person','company')"),
        "facts": count("select count(*) from graph_facts where valid_to is null and status='active'"),
        "edges": count("select count(*) from graph_edges where valid_to is null"),
    }


def _faithfulness(conn) -> dict:
    """Fraction of active facts that are grounded (confidence above zero) — the v2 proxy."""
    try:
        n = int(conn.execute(text(
            "select count(*) from graph_facts where valid_to is null and status='active'")
        ).scalar() or 0)
        if n < _MIN_N:
            return _insufficient(n)
        grounded = int(conn.execute(text(
            "select count(*) from graph_facts where valid_to is null and status='active' "
            "and confidence >= 0.5")).scalar() or 0)
        return {"value": round(grounded / n, 4), "n": n, "method": "groundedness_proxy_v2"}
    except Exception:
        return _insufficient()


# ── the acted rate: what you did with the cards, not what was delivered (STEP-16, `03` F76, `s16-F8`) ──
#
# ⛔ WHAT WAS WRONG. Acted was `claimed` + `delivered` — a card DELIVERED counted as one you acted on, though
# delivering is ours; the card's own `acted` and `resolved` states were never counted; `dismissed` is no card
# state; and every expiry was ignored, a card REPLACED by a fresher one and a card whose rule CLEARED among
# them — the engine moving on, counted against the founder (`yc2_w27_s16` M47.C3.L-logic.V0.U04).
#
# NOW, over the cards of the window: TAKEN is a card `acted` on `run_play` or `do_it_myself` (the button its
# last action event names), or `resolved`; CALLED WRONG — `acted` on `wrong` — is its own count; IGNORED is
# what was in front of you and ended with nothing: its window LAPSED, or you DISMISSED it from the extension.
# The rate is taken ÷ (taken + called wrong + lapsed + dismissed). A card the engine retired (replaced,
# cleared, held by the budget, no longer authorised, its plan gone, muted, its subject one of us) is not
# ignored and is in no denominator; a card still open, or an ending with no recorded cause, is counted
# beside the rate and never in it.

#: Why a card left that is not you ignoring it — STEP-06's causes for the engine moving on.
MOVED_ON = frozenset(card_lifecycle.CAUSES - {card_lifecycle.LAPSED, card_lifecycle.EXTENSION})
#: The buttons that are you taking a card.
TAKEN_ACTIONS = frozenset({"run_play", "do_it_myself"})

#: Each card of the window: its state, the last button pressed on it, and the cause its ending recorded.
_ACTED_ROWS = (
    "select k.state, "
    "(select ce.cause from card_events ce where ce.org_id = k.org_id and ce.card_id = k.card_id "
    " and ce.kind = 'human.card_action' order by ce.occurred_at desc, ce.id desc limit 1) as pressed, "
    "(select ce.cause from card_events ce where ce.org_id = k.org_id and ce.card_id = k.card_id "
    " and ce.kind in ('card.expired', 'window.lapsed', 'card.dismissed', 'card.retired') "
    " order by ce.occurred_at desc, ce.id desc limit 1) as ended, count(*) as c "
    "from cards k where k.created_at > now() - interval '30 days' group by 1, 2, 3")


def acted_counts(rows) -> dict[str, int]:
    """What each card of the window came to — `(state, pressed, ended, n)` rows, pure."""
    out = {"taken": 0, "called_wrong": 0, "lapsed": 0, "dismissed": 0, "moved_on": 0, "open": 0,
           "unattributed": 0}
    for state, pressed, ended, n in rows:
        n = int(n)
        if state == "resolved" or (state == "acted" and pressed in TAKEN_ACTIONS):
            out["taken"] += n
        elif state == "acted" and pressed == "wrong":
            out["called_wrong"] += n
        elif state == "expired" and ended == card_lifecycle.LAPSED:
            out["lapsed"] += n
        elif state == "expired" and ended == card_lifecycle.EXTENSION:
            out["dismissed"] += n
        elif state == "expired" and ended in MOVED_ON:
            out["moved_on"] += n
        elif state in card_lifecycle.OPEN_STATES:
            out["open"] += n
        else:
            out["unattributed"] += n
    return out


def acted_rate(counts: dict[str, int]) -> dict:
    """Taken ÷ (taken + called wrong + lapsed + dismissed), min-N gated; its parts beside it."""
    considered = counts["taken"] + counts["called_wrong"] + counts["lapsed"] + counts["dismissed"]
    if considered < _MIN_N:
        return _insufficient(considered)
    return {"value": round(counts["taken"] / considered, 4), "n": considered, **counts,
            "method": "taken_of_ended_by_you_v3"}


def _acted_rate(conn) -> dict:
    """The acted rate over the cards of the window, when there are enough."""
    try:
        return acted_rate(acted_counts(conn.execute(text(_ACTED_ROWS)).all()))
    except Exception:
        return _insufficient()


@router.get("/v1/benchmarks/scorecard")
def scorecard() -> dict:
    cache = get_cache()
    try:
        cached = cache.get_json(_CACHE_KEY)
        if cached:
            return cached
    except Exception:
        pass

    body = {
        "version": "v2",
        "build_sha": os.environ.get("GENIOS_BUILD_SHA", "dev"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": _WINDOW_DAYS,
        "min_n_gate": _MIN_N,
        "k_anonymous": True,
    }
    if _graph is not None:
        with _graph.engine.connect() as conn:
            body["scale"] = _scale(conn)
            body["tier1"] = {
                "acted_rate": _acted_rate(conn),
                "faithfulness": _faithfulness(conn),
                # No latency or calibration store in the v2 engine yet — reported honestly.
                "context_latency": {"p50": None, "p95": None, "p99": None,
                                    "reason": "insufficient_data"},
                "calibration_ece": _insufficient(),
            }
            body["per_detector"] = []          # k-anon suppressed until ≥3 orgs of evidence
    else:
        body["scale"], body["tier1"], body["per_detector"] = {}, {}, []

    try:
        cache.set_json(_CACHE_KEY, _CACHE_TTL, body)
    except Exception:
        pass
    return body


@router.get("/v1/benchmarks/methodology")
def methodology() -> dict:
    return {
        "version": "v2",
        "min_n": _MIN_N,
        "k_anonymous": True,
        "refresh_interval_sec": _CACHE_TTL,
        "sources": [
            "decisions (30d volume + confidence)",
            "graph_facts (grounded fact proxy)",
            "cards (taken — acted on run_play or do_it_myself, or resolved — of taken, called wrong, "
            "lapsed and dismissed; a card the engine replaced or cleared is not ignored)",
            "graph_nodes / graph_edges (scale)",
        ],
        "notes": [
            "Metrics below the minimum sample gate return insufficient_data, never a guess.",
            "Per-detector breakdowns are suppressed below 3 orgs (k-anonymity).",
            "No PII leaves this endpoint; only aggregate counts and rates.",
            "context_latency and calibration_ece have no v2 source yet and are reported null.",
        ],
    }
