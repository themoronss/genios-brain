"""A threshold may be another fact, so one rule can behave differently for different customers.

    pytest tests/packs/compiler/test_a_rule_can_stop_being_a_number.py -q

Every authored threshold used to be `path OP <literal>` — somebody's guess at a number that
suits every customer at once. `outbound-awaiting-reply.yaml` is the confession: it gates on
`days_waiting >= 3` while its own description four lines above says the opposite — *"a fund that
answers in three weeks is not slow at day ten."* The author knew the right rule and had no way
to write it, so the file states it in prose and hopes the model applies it.

`{other_path: ...}` lets the rule be written:

    - path: outreach.days_waiting
      op: ">"
      value: {other_path: party.reply_cadence_days, mult: 1.5, floor: 3}

One rule. A fund that replies in a day is chased on day three; a fund that replies in a month is
not chased at all. Nothing about the rule changed between them — the counterparty did.
"""

from __future__ import annotations

import pytest

from genios_engine.packs.compiler.context_adapter import ContextAdapter, PredicateState

pytestmark = pytest.mark.unit


class _Situation:
    metadata: dict = {}
    entities: tuple = ()
    type = "awaiting_response"


def adapter(*, facts=None, neighbor=None, missing=frozenset(), unknowable=frozenset()):
    a = ContextAdapter.__new__(ContextAdapter)
    a.situation = _Situation()
    a.context = None
    a.facts = facts or {}
    a.neighbor_facts = neighbor or {}
    a.observations = set()
    a.neighbor_obs = set()
    a.missing_fields = missing
    a.unknowable_fields = unknowable
    a.absent_fields = frozenset()
    a.baselines = {}
    return a


#: The one rule, written once, used by every test below.
CHASE = {"path": "outreach.days_waiting", "op": ">",
         "value": {"other_path": "party.reply_cadence_days", "mult": 1.5, "floor": 3}}


def state(a, condition):
    return a.evaluate(condition).state


# =============================================================================================
# The same rule, two customers.
# =============================================================================================
def test_a_fast_counterparty_is_chased_early():
    """Replies in a day. Ten days of silence is far past anything normal for them."""
    a = adapter(facts={"outreach.days_waiting": 10, "party.reply_cadence_days": 1})

    assert state(a, CHASE) is PredicateState.TRUE


def test_a_slow_counterparty_is_not_chased_on_the_same_day():
    """Replies in three weeks. Ten days is not late — and a literal `>= 3` would have chased
    them, which is the sentence `outbound-awaiting-reply.yaml` argues against in prose."""
    a = adapter(facts={"outreach.days_waiting": 10, "party.reply_cadence_days": 21})

    assert state(a, CHASE) is PredicateState.FALSE


def test_the_floor_still_protects_the_very_fast_one():
    """A counterparty who answers within hours must not be chased the same afternoon. `floor`
    means what it already means for `baseline`, deliberately — one shape, two sources."""
    a = adapter(facts={"outreach.days_waiting": 2, "party.reply_cadence_days": 0})

    assert state(a, CHASE) is PredicateState.FALSE

    later = adapter(facts={"outreach.days_waiting": 4, "party.reply_cadence_days": 0})
    assert state(later, CHASE) is PredicateState.TRUE


def test_the_multiplier_is_applied_not_ignored():
    a = adapter(facts={"outreach.days_waiting": 5, "party.reply_cadence_days": 4})

    assert state(a, CHASE) is PredicateState.FALSE       # 5 is not > 6
    assert state(adapter(facts={"outreach.days_waiting": 7,
                                "party.reply_cadence_days": 4}), CHASE) is PredicateState.TRUE


# =============================================================================================
# The three-state rule is not bent.
# =============================================================================================
def test_an_unheld_right_hand_side_abstains_rather_than_defaulting():
    """THE ONE THAT MATTERS MOST. Substituting a default number would make the comparison answer
    a question nobody asked — and for a doctrine rule a wrong FALSE reads as *satisfied*."""
    a = adapter(facts={"outreach.days_waiting": 30})

    verdict = a.evaluate(CHASE)

    assert verdict.state is PredicateState.UNKNOWN
    assert any("party.reply_cadence_days" in m for m in verdict.missing)


def test_a_declared_gap_on_the_right_hand_side_abstains():
    a = adapter(facts={"outreach.days_waiting": 30},
                missing=frozenset({"party.reply_cadence_days"}))

    assert state(a, CHASE) is PredicateState.UNKNOWN


def test_a_non_numeric_right_hand_side_abstains_rather_than_raising():
    """An author naming a text field here has made a mistake. The honest answer is that the rule
    could not be decided — not that it failed, and not a traceback in the compile."""
    a = adapter(facts={"outreach.days_waiting": 30,
                       "party.reply_cadence_days": "usually quick"})

    assert state(a, CHASE) is PredicateState.UNKNOWN


def test_the_right_hand_side_may_live_one_hop_away():
    """A company anchor holds almost none of its own facts — 15 of 18 held literally zero on the
    design partner's org. A form that read only the root would be UNKNOWN nearly always."""
    a = adapter(facts={"outreach.days_waiting": 10},
                neighbor={"party.reply_cadence_days": 2})

    assert state(a, CHASE) is PredicateState.TRUE


def test_the_anchors_own_value_outranks_the_neighbourhood():
    a = adapter(facts={"outreach.days_waiting": 10, "party.reply_cadence_days": 21},
                neighbor={"party.reply_cadence_days": 1})

    assert state(a, CHASE) is PredicateState.FALSE


# =============================================================================================
# What must not have changed.
# =============================================================================================
def test_a_plain_literal_still_works():
    a = adapter(facts={"outreach.days_waiting": 10})

    assert state(a, {"path": "outreach.days_waiting", "op": ">=", "value": 3}) \
        is PredicateState.TRUE


def test_the_baseline_form_still_works():
    a = adapter(facts={"outreach.days_waiting": 10})
    a.baselines = {"reply_cadence": {"value": 4}}

    cond = {"path": "outreach.days_waiting", "op": ">",
            "value": {"baseline": "reply_cadence", "mult": 2}}

    assert state(a, cond) is PredicateState.TRUE          # 10 > 4 * 2

    slower = adapter(facts={"outreach.days_waiting": 7})
    slower.baselines = {"reply_cadence": {"value": 4}}
    assert state(slower, cond) is PredicateState.FALSE    # 7 is not > 8


def test_the_corpus_validator_checks_the_right_hand_path_too():
    """An author naming a path the substrate does not hold has written a rule that can only ever
    answer UNKNOWN — silently, on every situation, forever."""
    import importlib.util
    import pathlib

    lib = pathlib.Path(__file__).resolve().parents[3] / "Domain Expertise/_tools/_lib.py"
    spec = importlib.util.spec_from_file_location("_corpus_lib", lib)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    paths, _obs, _base = module.refs_in_condition(CHASE)

    assert "outreach.days_waiting" in paths
    assert "party.reply_cadence_days" in paths
