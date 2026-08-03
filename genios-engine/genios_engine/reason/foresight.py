"""Foresight (C4) — deterministic base-rate prediction. Two questions a rep actually asks:

  • "Will this deal close?"  → deal_close_probability: the tenant's OWN won/(won+lost) base rate,
    modulated by the open signals on the deal (objection/competitor/going-dark pull it down; a
    buying signal pulls it up), bounded and honest. Confidence is the Wilson lower bound on the
    base rate — a rate from 3 closed deals is treated as far less certain than one from 50.
  • "Does this play actually work?" → play_win_rates: per-play Wilson lower-bound success rate from
    card outcomes, so the recommender can prefer plays that have EARNED trust for this tenant.

No LLM, no gradients — arithmetic over history. Everything cold-starts to a stated prior with n=0,
never a fabricated certainty."""
from __future__ import annotations

import math

from sqlalchemy import text

# how much each open concern moves a deal's close-probability off the base rate (bounded, additive).
# Negative = drag, positive = lift. Constants are HYPs — tune from outcomes, not vibes.
_SIGNAL_WEIGHTS = {
    "objection_open": -0.12, "competitor_in_live_deal": -0.12, "going_dark_after_proposal": -0.15,
    "deal_sentiment_negative": -0.15, "stalled_deal": -0.10, "single_threaded_deal": -0.08,
    "cooling_deal": -0.10, "unanswered_email": -0.05, "champion_quiet": -0.08,
    "buying_signal": +0.15,
}
_PROB_FLOOR, _PROB_CEIL = 0.05, 0.95
_BASE_RATE_PRIOR = 0.20          # cold-start close rate before this tenant has closed history
_MIN_CLOSED = 5                  # below this, lean on the prior (blended), don't trust the raw rate


def wilson_lower_bound(successes: int, n: int, z: float = 1.96) -> float:
    """Lower bound of the Wilson score interval — a small sample can't claim a high rate. n=0 → 0."""
    if n <= 0:
        return 0.0
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return max(0.0, (centre - margin) / denom)


def _closed_counts(store, org_id: str) -> tuple[int, int]:
    """(won, lost) from deal.status facts. Matches won/lost/closed_won/closed_lost, case-insensitive."""
    won = lost = 0
    with store.engine.connect() as c:
        for r in c.execute(text(
                "select lower(trim(both '\"' from value::text)) st, count(*) n "
                "from graph_facts where org_id=:o and field='deal.status' and valid_to is null "
                "and status='active' group by 1"), {"o": org_id}):
            st = r.st or ""
            if "won" in st:
                won += int(r.n)
            elif "lost" in st:
                lost += int(r.n)
    return won, lost


def tenant_close_base_rate(store, org_id: str) -> dict:
    """Blend the tenant's raw won-rate with the cold-start prior by evidence weight, so 1 win out of
    1 closed deal doesn't read as a 100% base rate. Returns {rate, won, lost, n, confidence}."""
    won, lost = _closed_counts(store, org_id)
    n = won + lost
    raw = (won / n) if n else _BASE_RATE_PRIOR
    # evidence-weighted blend toward the prior until _MIN_CLOSED deals have accrued
    w = min(1.0, n / float(_MIN_CLOSED))
    rate = round(w * raw + (1 - w) * _BASE_RATE_PRIOR, 3)
    return {"rate": rate, "won": won, "lost": lost, "n": n,
            "confidence": round(wilson_lower_bound(won, n), 3) if n else 0.0}


def deal_close_probability(base_rate: float, signal_reason_codes) -> dict:
    """Base rate ± the open concerns/opportunities on THIS deal, bounded. Returns {probability,
    slip_risk, drivers} — slip_risk = 1 − probability (the "will this slip" framing)."""
    prob = float(base_rate)
    drivers = []
    for rc in signal_reason_codes:
        w = _SIGNAL_WEIGHTS.get(rc)
        if w:
            prob += w
            drivers.append({"signal": rc, "delta": w})
    prob = round(max(_PROB_FLOOR, min(_PROB_CEIL, prob)), 3)
    return {"probability": prob, "slip_risk": round(1 - prob, 3), "drivers": drivers}


def play_win_rates(store, org_id: str) -> dict:
    """Per-play Wilson lower-bound win rate from card outcomes. A play "wins" when its card was acted
    on (run_play / do_it_myself); it "loses" on a relevance-wrong. Timing/snooze are excluded (they
    aren't judgments of the play). Returns {play: {wins, n, rate_lb}} — the recommender's trust map."""
    rates: dict = {}
    with store.engine.connect() as c:
        rows = c.execute(text(
            "select s.play, "
            "  count(*) filter (where ce.cause in ('run_play','do_it_myself')) as wins, "
            "  count(*) filter (where ce.cause in ('run_play','do_it_myself') "
            "                    or (ce.cause='wrong' and (ce.detail->>'reason') "
            "                        in ('not_relevant','wrong_facts'))) as n "
            "from card_events ce join cards k on k.card_id=ce.card_id "
            "join signals s on s.signal_id=k.signal_id "
            "where ce.org_id=:o and s.play is not null group by s.play"), {"o": org_id}).fetchall()
    for r in rows:
        wins, n = int(r.wins), int(r.n)
        rates[r.play] = {"wins": wins, "n": n, "rate_lb": round(wilson_lower_bound(wins, n), 3)}
    return rates
