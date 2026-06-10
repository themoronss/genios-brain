"""
Mig 079 unit tests — pure functions only, no DB.

Covers:
  - expand._tokenize, build_expanded_tsquery
  - fuse._jaccard, _token_set, _mmr_pick, _recency_boost
  - hebbian Hebbian / decay math (formulas as inline assertions)

Integration tests (alias trigram lookup, Hebbian SQL) are out of scope here
— they need a live Postgres with mig 079 applied. Run those manually with:
  pytest tests/integration/test_mig_079_db.py  (when added)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.retrieval import expand, fuse
from app.tasks import hebbian_nightly as hb


# ── expand.py ──────────────────────────────────────────────────────────────


class TestExpandTokenize:
    def test_lowercases(self):
        toks = expand._tokenize("Pricing CALL")
        assert toks == ["pricing", "call"]

    def test_min_token_len_filter(self):
        # Tokens <3 chars are dropped
        toks = expand._tokenize("a is on the QQQ")
        assert "qqq" in toks
        for short in ("a", "is", "on"):
            assert short not in toks

    def test_handles_empty(self):
        assert expand._tokenize("") == []
        assert expand._tokenize(None) == []

    def test_strips_punctuation(self):
        toks = expand._tokenize("hello, world!!")
        assert toks == ["hello", "world"]


class TestBuildExpandedTsquery:
    def test_returns_or_expression(self):
        out = expand.build_expanded_tsquery({
            "tokens": ["pricing", "objection"],
            "aliases": ["acme", "acme corp"],
        })
        # Order is preserved; duplicates removed; OR-joined.
        assert "pricing" in out
        assert "acme" in out
        assert " | " in out

    def test_dedupes_overlap(self):
        out = expand.build_expanded_tsquery({
            "tokens": ["acme"],
            "aliases": ["acme"],
        })
        assert out == "acme"

    def test_empty_input(self):
        assert expand.build_expanded_tsquery({"tokens": [], "aliases": []}) == ""


# ── fuse.py ────────────────────────────────────────────────────────────────


class TestJaccard:
    def test_identical_sets(self):
        assert fuse._jaccard({"a", "b", "c"}, {"a", "b", "c"}) == 1.0

    def test_disjoint(self):
        assert fuse._jaccard({"a"}, {"b"}) == 0.0

    def test_partial_overlap(self):
        # |intersect|=1, |union|=3 → 1/3
        assert abs(fuse._jaccard({"a", "b"}, {"b", "c"}) - 1/3) < 1e-9

    def test_empty_returns_zero(self):
        assert fuse._jaccard(set(), {"a"}) == 0.0


class TestTokenSet:
    def test_pulls_from_subject_summary_body(self):
        item = {"subject": "Pricing call", "summary": "Discussed Q3", "body": "deal closed"}
        toks = fuse._token_set(item)
        assert "pricing" in toks
        assert "discussed" in toks
        assert "closed" in toks

    def test_min_len_filter_in_token_set(self):
        # 'at' (len 2) should be filtered
        item = {"subject": "at home", "summary": "", "body": ""}
        assert "at" not in fuse._token_set(item)


class TestRecencyBoost:
    def test_recent_gets_boost(self):
        item = {"sent_at": datetime.now(timezone.utc).isoformat()}
        assert fuse._recency_boost(item) > 0

    def test_old_gets_zero(self):
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        assert fuse._recency_boost({"sent_at": old}) == 0.0

    def test_missing_field(self):
        assert fuse._recency_boost({}) == 0.0


class TestMmrPick:
    def test_pure_relevance_when_lambda_one(self):
        cands = [
            {"id": "a", "rrf_score": 0.9, "subject": "alpha unique"},
            {"id": "b", "rrf_score": 0.5, "subject": "beta unique"},
            {"id": "c", "rrf_score": 0.1, "subject": "gamma unique"},
        ]
        out = fuse._mmr_pick(cands, k=3, lam=1.0)
        assert [c["id"] for c in out] == ["a", "b", "c"]

    def test_diversifies_near_duplicates(self):
        # a and b have heavy token overlap; c is distinct.
        # MMR should pick a (highest rel), then c (diversity), then b.
        cands = [
            {"id": "a", "rrf_score": 0.90, "subject": "pricing call with rohit"},
            {"id": "b", "rrf_score": 0.85, "subject": "pricing call with rohit again"},
            {"id": "c", "rrf_score": 0.40, "subject": "warehouse expansion plan"},
        ]
        out = fuse._mmr_pick(cands, k=3, lam=0.4)
        ids = [c["id"] for c in out]
        # First pick is highest-relevance always
        assert ids[0] == "a"
        # With diversity-heavy lambda, c should outrank b for second slot
        assert ids[1] == "c"

    def test_handles_empty(self):
        assert fuse._mmr_pick([], k=5, lam=0.7) == []

    def test_k_larger_than_input(self):
        cands = [{"id": "a", "rrf_score": 0.5, "subject": "x"}]
        out = fuse._mmr_pick(cands, k=10, lam=0.7)
        assert len(out) == 1


# ── hebbian.py ─────────────────────────────────────────────────────────────


class TestHebbianMath:
    """The SQL math in plain Python so the formula is documented and
    verified at unit-test time."""

    @staticmethod
    def update(weight: float, alpha: float = hb.ALPHA) -> float:
        return min(1.0, weight + alpha * (1.0 - weight))

    @staticmethod
    def decay(weight: float, factor: float = hb.DECAY_FACTOR) -> float:
        return max(0.0, weight - factor)

    def test_neutral_baseline_strengthens(self):
        new = self.update(0.500)
        assert abs(new - 0.55) < 1e-9

    def test_already_high_approaches_one(self):
        new = self.update(0.9)
        assert abs(new - 0.91) < 1e-9
        # Cannot exceed 1.0
        new2 = self.update(0.999)
        assert new2 <= 1.0

    def test_floor_at_zero_after_decay(self):
        new = self.decay(0.02)
        assert new == 0.0  # 0.02 - 0.05 floors at 0

    def test_decay_typical(self):
        new = self.decay(0.5)
        assert abs(new - 0.45) < 1e-9

    def test_ltp_threshold_constants(self):
        # Sanity: constants haven't drifted from spec
        assert hb.LTP_THRESHOLD == 5
        assert hb.ALPHA == 0.10
        assert hb.DECAY_FACTOR == 0.05
        assert hb.DECAY_AGE_DAYS == 30


