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
from datetime import datetime

from sqlalchemy import text

from genios_engine.reason.authority import (
    AUDITED_CARD_JUDGMENTS_CTES,
    authority_time,
)

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


def _finite(name: str, value) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        out = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def _count(name: str, value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def wilson_lower_bound(successes: int, n: int, z: float = 1.96) -> float:
    """Lower bound of the Wilson score interval — a small sample can't claim a high rate. n=0 → 0."""
    wins = _count("successes", successes)
    sample_size = _count("n", n)
    z_score = _finite("z", z)
    if sample_size < 0 or wins < 0 or wins > sample_size:
        raise ValueError("counts must satisfy 0 <= successes <= n")
    if z_score <= 0:
        raise ValueError("z must be greater than zero")
    if sample_size == 0:
        return 0.0
    p = wins / sample_size
    denom = 1 + z_score * z_score / sample_size
    centre = p + z_score * z_score / (2 * sample_size)
    margin = z_score * math.sqrt(
        (p * (1 - p) + z_score * z_score / (4 * sample_size)) / sample_size)
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
    prob = min(1.0, max(0.0, _finite("base_rate", base_rate)))
    if isinstance(signal_reason_codes, (str, bytes)) or signal_reason_codes is None:
        raise ValueError("signal_reason_codes must be an iterable of reason-code strings")
    drivers = []
    seen: set[str] = set()
    for rc in signal_reason_codes:
        if not isinstance(rc, str):
            raise ValueError("each signal reason code must be a string")
        if rc in seen:
            continue
        seen.add(rc)
        w = _SIGNAL_WEIGHTS.get(rc)
        if w:
            prob += w
            drivers.append({"signal": rc, "delta": w})
    prob = round(max(_PROB_FLOOR, min(_PROB_CEIL, prob)), 3)
    return {"probability": prob, "slip_risk": round(1 - prob, 3), "drivers": drivers}


def play_win_rates(store, org_id: str, *, eval_time: datetime | None = None) -> dict:
    """Per-play Wilson lower-bound win rate from card outcomes. A play "wins" when its card was acted
    on (run_play / do_it_myself); it "loses" on a relevance-wrong. Timing/snooze are excluded (they
    aren't judgments of the play). Returns {play: {wins, n, rate_lb}} — the recommender's trust map."""
    rates: dict = {}
    as_of = authority_time(eval_time)
    with store.engine.connect() as c:
        rows = c.execute(text(
            "with " + AUDITED_CARD_JUDGMENTS_CTES + " "
            "select pack_id, pack_version, play, count(*) filter (where cause in "
            "('run_play','do_it_myself')) as wins, "
            "count(*) filter (where cause in ('run_play','do_it_myself') or "
            "(cause='wrong' and (detail->>'reason') in "
            "('not_relevant','wrong_facts'))) as n "
            "from canonical_judgments group by pack_id, pack_version, play "
            "order by pack_id, pack_version, play"),
            {"o": org_id, "as_of": as_of}).fetchall()
    for r in rows:
        wins, n = int(r.wins), int(r.n)
        key = play_stat_key(r.pack_id, r.pack_version, r.play)
        rates[key] = {"pack_id": r.pack_id, "pack_version": r.pack_version,
                      "play_id": r.play, "wins": wins, "n": n,
                      "rate_lb": round(wilson_lower_bound(wins, n), 3)}
    return rates


def play_stat_key(pack_id: str, pack_version: str, play_id: str) -> str:
    """Unambiguous measured-play identity for JSON-safe dictionaries."""
    return f"{pack_id}@{pack_version}:{play_id}"
