"""L2-3-U0 · what a slice costs to put in a prompt — the number L2-5's cost check rests on.

⛔ **THE STEP SAYS WHY THIS IS A UNIT AND NOT AN AFTERTHOUGHT:** *"Before building the builder:
take ten real candidates and compute the slice size in tokens. **The cost check for L2-5 depends
on this number**, and guessing it would make that check theatre."*

And §2 states the stake: *"Cost in L2 comes from tokens, not calls, and the difference between a
10,000-token thread and a 900-token slice is the whole bill."*

**PURE, AND MEASURED FROM `to_semantic_dict()`.** Not from the dataclass and not from a `repr`:
the semantic dict is what the slice IS — the same bytes that pin its content address — and it
deliberately excludes `trace_id`, `evaluation_time` and `graph_version`, none of which a prompt
would carry either.

⛔ **NO MODEL IS CALLED AND NO TOKENISER IS IMPORTED.** A tokeniser is a dependency whose answer
changes under us; the estimate is characters over a stated divisor, and the divisor is declared so
a reader can check it rather than trust it. An estimate somebody can audit beats an exact number
that needs a network call.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _slice(**over):
    from datetime import UTC, datetime

    from genios_engine.contracts.domain_expertise import SituationContextSlice
    from genios_engine.contracts.visibility import Visibility

    base = dict(
        org_id="org_w", trace_id="trace_w",
        visibility=Visibility(scope="org", derived_from="test:slice"),
        id="slice:sit_w", graph_version=7, selector_version="selector.v1",
        evaluation_time=datetime(2026, 9, 24, tzinfo=UTC), root_entity_ids=("node_a",),
        facts={}, observations=(), neighbor_facts={}, neighbor_observations=(),
        edge_count=0, evidence=(), missing_fields=(), metadata={})
    base.update(over)
    return SituationContextSlice(**base)


def test_an_empty_slice_still_weighs_its_envelope():
    from genios_engine.context.slice_weight import weigh

    weight = weigh(_slice())
    assert weight.tokens > 0
    assert weight.chars > weight.tokens, "the estimate divides characters, it does not multiply"


def test_a_bigger_slice_weighs_more():
    from genios_engine.context.slice_weight import weigh

    small = weigh(_slice())
    big = weigh(_slice(facts={f"account.field_{i}": {"value": "x" * 40} for i in range(50)}))
    assert big.tokens > small.tokens * 2


def test_the_weight_is_the_content_address_bytes_and_not_the_dataclass():
    """⛔ `trace_id`, `evaluation_time` and `graph_version` are observation metadata — excluded
    from `to_semantic_dict` on purpose, and a prompt would not carry them either. Weighing the
    dataclass would count three fields no reasoner ever sees."""
    from genios_engine.context.slice_weight import weigh

    a = weigh(_slice(trace_id="trace_a"))
    b = weigh(_slice(trace_id="trace_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"))
    assert a.chars == b.chars, "the weigher counted a field the content address excludes"


def test_the_divisor_is_declared_so_the_estimate_can_be_audited():
    from genios_engine.context.slice_weight import CHARS_PER_TOKEN, weigh

    assert CHARS_PER_TOKEN >= 1
    weight = weigh(_slice())
    assert weight.tokens == weight.chars // CHARS_PER_TOKEN


def test_a_population_reports_p50_and_p90_and_not_a_mean():
    """⛔ A mean hides the slice that blows the budget. §2's whole point is the tail."""
    from genios_engine.context.slice_weight import weigh_all

    population = [_slice(facts={f"f{i}": {"value": "y" * (i * 20)}}) for i in range(1, 21)]
    report = weigh_all(population)
    assert report.count == 20
    assert report.p50 < report.p90 <= report.max
    assert not hasattr(report, "mean")


def test_an_empty_population_says_so_rather_than_reporting_zero():
    """⛔ Zero tokens and nothing measured are different facts — the same distinction L2-0 drew
    between an unscored refusal and one that scored nothing."""
    from genios_engine.context.slice_weight import weigh_all

    report = weigh_all([])
    assert report.count == 0
    assert report.p50 is None and report.p90 is None
    assert "nothing was measured" in report.sentence


# =================================================================================================
# ⛔ THE MEASUREMENT FOUND THAT THE SLICE'S ADVANTAGE IS NOT STRUCTURAL.
#
# Measured 2026-09-24 through the real `build_context_slice`:
#
#     facts / obs / neighbors        tokens
#        3 /   2 /   1                 326
#        8 /   6 /   4                 714     ← §2's "~900-token slice"
#       15 /  12 /   9                1279
#       30 /  25 /  20                2509
#       60 /  50 /  40                4934
#      100 /  80 /  60                8049     ← §2's "10,000-token thread"
#
# §2 claims *"the difference between a 10,000-token thread and a 900-token slice is the whole
# bill."* That holds for a small node and **stops holding for a busy one**: an anchor with a
# hundred facts produces a slice as expensive as the thread it replaced. The saving comes from
# the node being small, not from the slice being a slice.
#
# So the number has to be a BUDGET a caller can check, not a figure in a findings file.
# =================================================================================================

def test_a_budget_exists_and_says_what_it_is_for():
    from genios_engine.context.slice_weight import SLICE_TOKEN_BUDGET, budget_reason

    assert SLICE_TOKEN_BUDGET > 0
    assert "ENDS WHEN" in budget_reason()


def test_a_small_slice_is_within_budget_and_says_nothing():
    from genios_engine.context.slice_weight import over_budget, weigh

    assert over_budget(weigh(_slice())) is None


def test_an_oversized_slice_names_the_number_it_exceeded_by():
    """⛔ 'too big' is unactionable. 'it is 8049 against a budget of 2000' is a decision."""
    from genios_engine.context.slice_weight import SLICE_TOKEN_BUDGET, over_budget, weigh

    heavy = _slice(facts={f"account.field_{i}": {"value": "z" * 80} for i in range(300)})
    weight = weigh(heavy)
    sentence = over_budget(weight)
    assert sentence is not None
    assert str(weight.tokens) in sentence and str(SLICE_TOKEN_BUDGET) in sentence


def test_the_report_names_how_many_of_a_population_break_it():
    """One oversized slice is a curiosity; a tail of them is the bill."""
    from genios_engine.context.slice_weight import weigh_all

    population = ([_slice() for _ in range(8)]
                  + [_slice(facts={f"f{i}": {"value": "q" * 90} for i in range(300)})
                     for _ in range(2)])
    report = weigh_all(population)
    assert report.over_budget == 2
    assert "2 of 10" in report.sentence
