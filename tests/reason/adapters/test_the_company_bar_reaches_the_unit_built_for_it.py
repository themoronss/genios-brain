"""The organisation's approval threshold reached the unit as a config key nobody wrote.

    pytest tests/reason/adapters/test_the_company_bar_reaches_the_unit_built_for_it.py -q

`ApprovalThresholdPlugin.contribute` opens with `_config_amount(view,
"approval_threshold_amount")` and returns `()` when it is absent — commented "the tenant
declared no approval rule". Nobody wrote that key.

So an org whose uploaded SOP says *"contracts above $50,000 require founder approval"* —
span-verified, approver resolved, confirmed by a human, published to the Organization brain
and projected into `authority_rules` — got a card on a $120k renewal that behaved exactly as
if the company had no approval rule. The manager was told to commit; the founder got no card.
The unit was built, tested, and unreachable.

The seam is one unit over: `constraint_config["blocked_play_ids"]` is the same move for the
same brain, under a comment naming the same defect — *"a seam built for exactly this and never
wired to the brain that should drive it."*
"""

from __future__ import annotations

import pytest

from genios_engine.reason.adapters.expertise import _approval_config

pytestmark = pytest.mark.unit


class _Package:
    def __init__(self, *rules):
        self.organization_rules = rules


def approval(**kw):
    base = {"category": "approval", "authority_pending": False,
            "threshold_minor_units": 5_000_000, "currency": "USD"}
    return {**base, **kw}


# =============================================================================================
# The bar arrives.
# =============================================================================================
def test_a_confirmed_money_rule_becomes_the_units_threshold():
    got = _approval_config(_Package(approval()))

    assert got["approval_threshold_amount"] == 5_000_000
    assert got["approval_threshold_currency"] == "USD"


def test_a_tenant_with_no_rules_still_gets_nothing():
    """The plugin's own reading of an absent key — "the tenant declared no approval rule" —
    must stay true for a tenant that really has none."""
    assert _approval_config(_Package()) == {}


def test_the_tightest_bar_wins():
    """Taking the loosest would let a $60k contract past a $50k rule because a $100k rule also
    exists."""
    got = _approval_config(_Package(approval(threshold_minor_units=12_000_000),
                                    approval(threshold_minor_units=5_000_000)))

    assert got["approval_threshold_amount"] == 5_000_000


# =============================================================================================
# Three refusals, each for a failure it prevents.
# =============================================================================================
def test_an_unresolved_approver_sets_no_bar():
    """A bar with no approver behind it would block the card and name nobody."""
    assert _approval_config(_Package(approval(authority_pending=True))) == {}


def test_a_ratio_rule_is_skipped_rather_than_converted():
    """"Above 15%" is not an amount, and `approval_value_field` reads money. Folding one into
    the other is exactly the confusion `threshold_basis_points` was given its own field to
    prevent."""
    got = _approval_config(_Package(
        {"category": "approval", "authority_pending": False,
         "threshold_basis_points": 1500, "threshold_minor_units": None}))

    assert got == {}


def test_an_unbounded_approval_rule_sets_no_amount():
    assert _approval_config(_Package(approval(threshold_minor_units=None))) == {}


def test_a_non_approval_rule_is_not_read_as_one():
    assert _approval_config(_Package(approval(category="communication"))) == {}


def test_a_malformed_threshold_is_skipped_not_defaulted():
    """Defaulting would invent a bar the company never set, which is worse than the bar it
    already had: none."""
    assert _approval_config(_Package(approval(threshold_minor_units="fifty thousand"))) == {}


def test_a_ratio_rule_does_not_hide_a_money_rule():
    """Both in one tenant is ordinary — a discount policy and a contract policy."""
    got = _approval_config(_Package(
        {"category": "approval", "authority_pending": False, "threshold_basis_points": 1500},
        approval(threshold_minor_units=5_000_000)))

    assert got["approval_threshold_amount"] == 5_000_000


# =============================================================================================
# The weld itself.
# =============================================================================================
def test_the_config_is_merged_into_the_policy_unit_and_not_over_its_bindings():
    """`_bind_roles` has already resolved this unit's fact paths, and those bindings are how
    the plugin finds the amount to compare against the bar."""
    import inspect

    from genios_engine.reason.adapters import expertise

    source = inspect.getsource(expertise._roster_specs)

    assert 'if unit.unit_id == "core.policy" and approval_config:' in source
    assert "config = {**config, **approval_config}" in source


def test_the_plugin_still_reads_the_key_this_writes():
    """Two names for one thing is the defect this whole branch keeps finding."""
    import inspect

    from genios_engine.reason.reasoners import policy_unit

    source = inspect.getsource(policy_unit.ApprovalThresholdPlugin.contribute)

    assert '"approval_threshold_amount"' in source
