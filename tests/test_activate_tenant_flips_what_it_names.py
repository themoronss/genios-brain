"""GeniOS-012 U12-02 · `scripts/activate_tenant.py` switches on every feature it accepts.

    pytest tests/test_activate_tenant_flips_what_it_names.py -q

`_plan_for` appended only the Layer 4 features named in `PLAN` (the five wave features). Every other
feature passed `require_feature` and was then dropped without a word, so

    python scripts/activate_tenant.py --org <org> --features expert_review,l2_reasoning --apply

printed "nothing to do" and switched on neither — the two switches GeniOS-011/07 Phase A told the
operator to flip with this very script. A name the script accepts is now a name it plans, in an
order that respects `l4_activation.PRECONDITIONS`, and a name it will not flip is a refusal.
"""

from __future__ import annotations

import pytest

from scripts import activate_tenant as script


def _features(plan):
    return [name for layer, _kind, name in plan if layer == "L4"]


def test_a_feature_outside_the_wave_list_is_planned():
    """The two GeniOS-012 Step 1 switches are planned, not dropped."""
    plan = script._plan_for(("admin",), ("expert_review", "l2_reasoning"))
    assert _features(plan) == ["expert_review", "l2_reasoning"]


def test_preconditions_come_before_the_feature_that_needs_them():
    """`l2_cards` needs `l2_reasoning` and `expert_review`; asked for first, it is still flipped last."""
    plan = script._plan_for(("admin",), ("l2_cards", "l2_reasoning", "expert_review"))
    names = _features(plan)
    assert set(names) == {"l2_cards", "l2_reasoning", "expert_review"}
    assert names.index("l2_cards") > names.index("l2_reasoning")
    assert names.index("l2_cards") > names.index("expert_review")


def test_wave_features_keep_their_wave_order_before_the_rest():
    plan = script._plan_for(("admin",), ("expert_review", "ranking_v2", "roster_v2"))
    assert _features(plan) == ["roster_v2", "ranking_v2", "expert_review"]


def test_founder_office_is_a_domain_it_plans():
    plan = script._plan_for(("admin", "founder_office"), ())
    assert [name for layer, _k, name in plan if layer == "L3"] == ["admin", "founder_office"]


def test_a_retired_feature_is_refused_before_anything_is_planned():
    """`situation_reasoner` is retired: `activate` would refuse it half-way through the plan, after
    L1 and L2 were already on. It is refused up front instead."""
    with pytest.raises(ValueError, match="situation_reasoner"):
        script._plan_for(("admin",), ("expert_review", "situation_reasoner"))


def test_an_unknown_feature_is_refused():
    with pytest.raises(ValueError):
        script._plan_for(("admin",), ("expert_reveiw",))


def test_the_old_selection_is_unchanged():
    """The existing contract (`tests/test_activate_tenant.py`) still holds."""
    plan = script._plan_for(("admin", "sales"), ("ranking_v2",))
    assert [(layer, name) for layer, _k, name in plan] == [
        ("L1", "semantic"), ("L2", "analytic"), ("L2", "patterns"),
        ("L3", "admin"), ("L3", "sales"), ("L4", "ranking_v2")]
