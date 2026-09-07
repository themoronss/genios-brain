"""L2.6.3-U1 · the Candidate Scorer — every row in the spec's ACCEPTANCE list.

Two numbers, kept apart. *"Five conditions held"* and *"we are confident about the facts
underneath"* are different claims, and a scorer that averaged them would report a strong pattern
over thin evidence identically to a weak pattern over solid evidence.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from genios_engine.context.patterns import scorer as scorer_module
from genios_engine.context.patterns.candidate import build_candidate
from genios_engine.context.patterns.contract import BASE_MATCH_STRENGTH_BP
from genios_engine.context.patterns.matcher import match
from genios_engine.context.patterns.scorer import (MIN_IDENTITY_SCORE, PROMOTION_FLOOR_BP,
                                                   CandidateScore, match_strength_bp,
                                                   score_candidate)

STRONG_QUALITY = {"evidence": 80, "freshness": 70, "consistency": 90, "identity": 95,
                  "coverage": 60}
WEAK_QUALITY = {"evidence": 30, "freshness": 20, "consistency": 40, "identity": 90,
                "coverage": 10}


@pytest.fixture
def candidate(pattern, graph_slice, fact, observation, eval_time):
    """One candidate, with as many optional signals satisfied as the caller asks for."""
    def _build(*, optional: tuple[int, ...] = (), satisfied: int = 0):
        signals = [{"kind": "observation", "kind_name": f"signal_{i}", "weight_bp": weight}
                   for i, weight in enumerate(optional)]
        p = pattern(pattern_id="scored", optional_signals=signals)
        world = graph_slice(
            facts=(fact("subscription.status", "active"),),
            observations=tuple(observation(f"signal_{i}") for i in range(satisfied)))
        result = match(p, world, eval_time=eval_time)
        return build_candidate(result, world, eval_time=eval_time)
    return _build


def test_all_required_conditions_and_zero_optional_is_the_fixed_base(candidate):
    """Required conditions are BINARY: they all held or there is no candidate, so they contribute
    a fixed base and cannot produce a partial score."""
    score = score_candidate(candidate())
    assert isinstance(score, CandidateScore)
    assert score.match_strength_bp == BASE_MATCH_STRENGTH_BP


def test_two_optional_signals_add_their_weights(candidate):
    score = score_candidate(candidate(optional=(1500, 1000), satisfied=2))
    assert score.match_strength_bp == BASE_MATCH_STRENGTH_BP + 2500


def test_the_sum_clamps_at_the_scale(candidate):
    score = score_candidate(candidate(optional=(9000, 9000), satisfied=2))
    assert score.match_strength_bp == 10_000


def test_quality_is_carried_and_never_averaged_into_strength(candidate):
    """The same match over strong and weak facts scores identically on STRENGTH and differently on
    QUALITY. Collapsing the two destroys both."""
    strong = score_candidate(candidate(), STRONG_QUALITY)
    weak = score_candidate(candidate(), WEAK_QUALITY)
    assert strong.match_strength_bp == weak.match_strength_bp
    assert strong.quality_carry != weak.quality_carry
    assert dict(weak.quality_carry)["evidence"] == 30


def test_promotion_is_false_below_the_floor_and_true_at_it(candidate):
    """The boundary row. `PROMOTION_FLOOR_BP` equals the base on purpose: every required condition
    holding IS the bar, and an optional signal can never be what carries a candidate over it."""
    at_floor = score_candidate(candidate(), STRONG_QUALITY)
    assert at_floor.promote is True
    assert at_floor.floor_bp == PROMOTION_FLOOR_BP

    raised = score_candidate(candidate(), STRONG_QUALITY, floor_bp=BASE_MATCH_STRENGTH_BP + 1)
    assert raised.promote is False
    assert "below the floor" in raised.withheld_reason


def test_a_pattern_matched_about_an_unresolvable_entity_is_held_back(candidate):
    """A perfectly matched pattern about an entity we cannot identify is a card addressed to
    nobody. `identity` is the one quality axis that can hold a candidate back."""
    unsure = score_candidate(candidate(), {**STRONG_QUALITY,
                                           "identity": MIN_IDENTITY_SCORE - 1})
    assert unsure.promote is False
    assert "cannot resolve" in unsure.withheld_reason
    assert score_candidate(candidate(),
                           {**STRONG_QUALITY, "identity": MIN_IDENTITY_SCORE}).promote is True


def test_the_strength_arithmetic_has_one_home(candidate):
    """The evaluator computes it while looking at the signals and the scorer reports it. A second
    copy of the sum is how a candidate comes to disagree with its own match."""
    built = candidate(optional=(1500,), satisfied=1)
    assert score_candidate(built).match_strength_bp == built.match_strength_bp
    assert match_strength_bp(optional_weights_bp=(1500,)) == built.match_strength_bp


def test_the_score_has_no_importance_field():
    """A candidate score that leaked into ranking would re-introduce a second, incompatible
    importance scale beside BLG-18's — with none of the stored components that explain it."""
    fields = set(CandidateScore.__dataclass_fields__)
    assert "importance_bp" not in fields
    assert not [f for f in fields if "importance" in f]
    source = Path(scorer_module.__file__).read_text()
    assert "importance_bp=" not in source


def test_the_module_is_integer_only():
    """Doctrine 2. A float at the promotion boundary is a decision that is not reproducible."""
    import re
    source = Path(scorer_module.__file__).read_text()
    code = "\n".join(line for line in source.splitlines()
                     if not line.strip().startswith("#"))
    code = re.sub(r'"""(?:.|\n)*?"""', "", code)
    assert not re.search(r"\b\d+\.\d+\b", code), "a float literal in a score path"
    assert "round(" not in code
    assert "statistics" not in code
