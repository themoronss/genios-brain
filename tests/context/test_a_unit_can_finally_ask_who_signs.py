"""AUTH-3 — the Policy unit held a number and no person.

    pytest tests/context/test_a_unit_can_finally_ask_who_signs.py -q

`_authority_facts` already lands the Founder Bottleneck counts on the slice — but on the
APPROVER'S OWN node, which is the right home for "you are the only approver for three classes"
and the wrong one for "who signs THIS". A reasoning unit holds a contract and reads the
contract's facts; it never holds the approver's node, so the answer sat one hop from every
unit that needed it.

So an £80K renewal told the AE "the organisation requires a signature" and could not say
whose — *what can I actually do* resolved to *find out who signs*. The CFO who IS the
enforceable approver received no card at all, because nothing routed on `approver_node_id`.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.context.patterns.store import _approver_facts
from genios_engine.contracts.authority import AuthorityRule

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 10, tzinfo=timezone.utc)
ORG = "org1"


class _View:
    """Just enough view: the real one resolves through the same `resolve` these tests use."""

    def __init__(self, *rules):
        self._rules = rules

    def resolve(self, org_id, *, subject_type, evaluated_at, **kw):
        from genios_engine.context.authority_view import resolve

        return resolve(self._rules, subject_type=subject_type, evaluated_at=evaluated_at, **kw)


def rule(**kw):
    base = {"rule_id": "r1", "subject_type": "contract", "approver_node_id": "n-cfo",
            "source": "admin_declared", "evidence_ref": "doc:sop#3", "valid_from": NOW}
    return AuthorityRule(**{**base, **kw})


def paths(facts):
    return {f.field_path: f.value for f in facts}


# =============================================================================================
# The answer arrives on the subject.
# =============================================================================================
def test_an_enforceable_rule_names_the_approver_on_the_subject():
    got = paths(_approver_facts(_View(rule()), ORG, eval_time=NOW, subject_type="contract"))

    assert got["authority.approver_node_id"] == "n-cfo"
    assert got["authority.rule_id"] == "r1"
    assert got["authority.outcome"] == "enforceable"


def test_the_delegate_travels_too():
    """The half that answers "what should stay with somebody else". Usually null, and that IS
    the Founder Bottleneck finding rather than a missing value."""
    got = paths(_approver_facts(_View(rule(delegate_node_id="n-vp")), ORG,
                                eval_time=NOW, subject_type="contract"))

    assert got["authority.delegate_node_id"] == "n-vp"


def test_no_delegate_writes_no_delegate_fact():
    got = paths(_approver_facts(_View(rule()), ORG, eval_time=NOW, subject_type="contract"))

    assert "authority.delegate_node_id" not in got


# =============================================================================================
# What must not be written.
# =============================================================================================
def test_a_merely_suggested_approver_is_not_put_on_the_subject():
    """An unconfirmed observation on the subject's facts would let a rule GATE on it — the same
    line `resolve_approver_seat` holds one layer up, and the reason
    `runtime_brains._validate_axis` raises when a Behavior brain declares a permission."""
    got = paths(_approver_facts(_View(rule(source="inferred")), ORG,
                                eval_time=NOW, subject_type="contract"))

    assert "authority.approver_node_id" not in got
    assert got["authority.outcome"] == "suggested"


def test_the_outcome_is_written_even_when_nobody_is_named():
    """A unit that can only tell "found" from "absent" renders an org with an unconfirmed
    suggestion identically to an org with no governance at all, and those need OPPOSITE next
    actions — which is the argument `AuthorityOutcome` already makes for having three values."""
    got = paths(_approver_facts(_View(), ORG, eval_time=NOW, subject_type="contract"))

    assert got == {"authority.outcome": "no_authority_rule"}


def test_no_view_writes_nothing():
    assert _approver_facts(None, ORG, eval_time=NOW, subject_type="contract") == ()


# =============================================================================================
# Where the fact lands.
# =============================================================================================
def test_the_facts_are_stamped_with_the_anchor_they_are_given_to():
    """Computed once for the org and belonging to each subject that asks, so the subject id is
    filled in at the anchor rather than carried from a resolution that has no anchor in hand."""
    import inspect

    from genios_engine.context.patterns import store

    source = inspect.getsource(store.slices_for)

    assert "replace(f, subject_node_id=row.node_id) for f in approver_facts" in source


def test_an_unstamped_fact_is_loud_rather_than_unattributed():
    facts = _approver_facts(_View(rule()), ORG, eval_time=NOW, subject_type="contract")

    assert all(f.subject_node_id == "@unstamped" for f in facts), \
        "a visible sentinel, so a fact that escaped stamping shows up in a trace"


def test_the_bottleneck_counts_still_live_on_the_approver():
    """The two are different questions with different homes, and merging them would put "you
    are the only approver for three classes" on a contract."""
    import inspect

    from genios_engine.context.patterns import store

    source = inspect.getsource(store._authority_facts)

    assert "out[load.approver_node_id]" in source
