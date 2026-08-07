"""Attention: deterministic ordering hint. And the constitutional rule — attention may
order retrieval, it may NEVER gate evaluation (starvation-loop guard)."""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

from genios_engine.context.attention import score_node

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


def _score(**kw):
    base = dict(now=NOW, last_inbound=None, last_outbound=None, ball_in_court=None,
                commitment_due=None, question_at=None, pos_recent=0, neg_recent=0,
                max_open_signal=0)
    base.update(kw)
    return score_node(**base)


def test_cold_node_scores_low():
    score, band, _ = _score()
    assert score == 0 and band == "low"


def test_hot_thread_with_overdue_commitment_and_question_is_critical():
    score, band, inputs = _score(
        last_inbound=(NOW - timedelta(days=1)).isoformat(),
        ball_in_court="us",
        commitment_due=(NOW - timedelta(days=2)).isoformat(),     # overdue
        question_at=NOW - timedelta(days=3),
        neg_recent=2, pos_recent=0,
        max_open_signal=73)
    # 40 recency + 15 ball + 25 overdue + 15 question + 10 neg + 14 signal → clamped 100
    assert score >= 75 and band == "critical"
    assert inputs["commitment"] == 25 and inputs["ball"] == 15


def test_scoring_is_deterministic_integer():
    a = _score(last_inbound=(NOW - timedelta(days=5)).isoformat(), pos_recent=3)
    b = _score(last_inbound=(NOW - timedelta(days=5)).isoformat(), pos_recent=3)
    assert a == b
    assert isinstance(a[0], int)


def test_old_activity_decays():
    fresh, _, _ = _score(last_inbound=(NOW - timedelta(days=2)).isoformat())
    stale, _, _ = _score(last_inbound=(NOW - timedelta(days=60)).isoformat())
    assert fresh > stale
    assert stale == 0


def test_attention_never_gates_evaluation():
    """No module under reason/ may read or write context_attention. Evaluation scope is
    every node, every sweep — narrowing it by attention closes the starvation loop
    (low attention → never evaluated → no signals → attention never rises)."""
    root = Path(__file__).resolve().parents[1] / "genios_engine" / "reason"
    offenders = []
    for py in root.rglob("*.py"):
        if "context_attention" in py.read_text():
            offenders.append(py.name)
    assert not offenders, f"reason/ must not touch context_attention: {offenders}"


def test_context_is_sole_writer():
    """Only context/ may INSERT/UPDATE context_attention (deliver/ may read for ordering)."""
    root = Path(__file__).resolve().parents[1] / "genios_engine"
    offenders = []
    for pkg in ("deliver", "feedback", "capture", "packs"):
        for py in (root / pkg).rglob("*.py"):
            src = py.read_text()
            if "context_attention" in src and any(
                    w in src for w in ("insert into context_attention",
                                       "update context_attention",
                                       "delete from context_attention")):
                offenders.append(f"{pkg}/{py.name}")
    assert not offenders, f"only context/ writes context_attention: {offenders}"
