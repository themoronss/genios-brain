"""U09 · the wire that did not exist — residue becomes a question Layer 1 can answer.

    pytest tests/context/test_residue_raises_a_need.py -q

`residue.py` has computed the demand since the day it shipped: *"the layer measures what it could
not explain."* `signal_unreached` counts *"the Layer 1 verdicts no Layer 2 reading consumes."* That
number reached the model angles and reached `capture/` never — so the system knew exactly what it
was missing and had no way to go and get it.

⛔ THE DESIGN IS THE EXCLUSION, NOT THE INCLUSION. Only ONE of the four residue kinds is an
evidence question:

    signal_unreached     → a need
    node_evidence_unread → NOT — the evidence is HELD; no reading spoke about it
    ball_in_court        → NOT — "they replied and we went quiet" is a fact about US
    open_loop            → NOT — an ask attached to nothing is a linking gap

Raising needs for all four would send Layer 1 fetching for what it already delivered, and every one
of those needs would then close successfully — teaching the system that its questions are always
answered. That is worse than not asking.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.context.evidence_needs import (DEFAULT_UNACCEPTABLE, NEED_WORTHY_KINDS,
                                                  need_from_residue, need_id_for,
                                                  needs_from_residue)
from genios_engine.context.residue import (RESIDUE_BALL_IN_COURT, RESIDUE_NODE_EVIDENCE,
                                           RESIDUE_OPEN_LOOP, RESIDUE_SIGNAL)

pytestmark = pytest.mark.unit

_T0 = datetime(2026, 9, 20, tzinfo=timezone.utc)
_T1 = datetime(2026, 9, 29, tzinfo=timezone.utc)


def _row(kind=RESIDUE_SIGNAL, subject_ref="signal:SIG-101", detail=None):
    return {"residue_kind": kind, "subject_ref": subject_ref,
            "detail": detail if detail is not None else {"signal_type": "contract_renewal"},
            "first_seen_at": _T0, "last_seen_at": _T1}


# =================================================================================================
# 1 · ⛔ only one kind becomes a need
# =================================================================================================
def test_an_unreached_signal_becomes_a_need():
    need = need_from_residue(_row(), org_id="org_x", trace_id="8f2a")
    assert need is not None
    assert need.subject_ref == "signal:SIG-101"
    assert "contract_renewal" in need.question


@pytest.mark.parametrize("kind", [RESIDUE_NODE_EVIDENCE, RESIDUE_BALL_IN_COURT, RESIDUE_OPEN_LOOP])
def test_the_other_three_kinds_raise_nothing(kind):
    """They are missing READINGS, not missing evidence. Fetching more would deliver what we already
    have — and the need would close successfully every time, which teaches the wrong lesson."""
    assert need_from_residue(_row(kind=kind), org_id="org_x", trace_id="t") is None


def test_the_worthy_set_is_closed_and_small():
    assert NEED_WORTHY_KINDS == {RESIDUE_SIGNAL}


# =================================================================================================
# 2 · ⛔ a need with no subject is refused, not filed
# =================================================================================================
def test_a_subjectless_residue_row_raises_nothing():
    """The executor would have nothing to fetch for and no way to know when it was done — a row
    that sits open forever, which is the exact state this step exists to end."""
    assert need_from_residue(_row(subject_ref=None), org_id="org_x", trace_id="t") is None


# =================================================================================================
# 3 · ⛔ the id stops the queue growing forever
# =================================================================================================
def test_the_same_question_about_the_same_subject_is_one_need():
    """Residue is re-derived every sweep — that is what "unexplained as of the last sweep" means.
    Without a stable id the table would measure how long we have been waiting, not what for."""
    a = need_from_residue(_row(), org_id="org_x", trace_id="sweep-1")
    b = need_from_residue(_row(), org_id="org_x", trace_id="sweep-2")
    assert a.need_id == b.need_id


def test_a_different_subject_is_a_different_need():
    a = need_from_residue(_row(subject_ref="signal:A"), org_id="o", trace_id="t")
    b = need_from_residue(_row(subject_ref="signal:B"), org_id="o", trace_id="t")
    assert a.need_id != b.need_id


def test_a_different_tenant_is_a_different_need():
    assert need_id_for("org1", "q", "s") != need_id_for("org2", "q", "s")


def test_two_rows_about_one_subject_produce_one_need():
    """One question, one fetch, one charge."""
    needs = needs_from_residue([_row(), _row()], org_id="org_x", trace_id="t")
    assert len(needs) == 1


# =================================================================================================
# 4 · what the need says
# =================================================================================================
def test_it_carries_why_it_matters():
    """A need that cannot say why it changes the decision is not decision-relevant, and fetching
    for it spends the tenant's budget on curiosity."""
    need = need_from_residue(_row(), org_id="o", trace_id="t")
    assert need.why_it_matters.strip()


def test_a_paraphrase_can_never_close_it():
    """⛔ A summary of a message is not the message. Closing on one would let a paraphrase stand in
    for the text a span has to be verifiable against."""
    need = need_from_residue(_row(), org_id="o", trace_id="t")
    for source in DEFAULT_UNACCEPTABLE:
        assert need.accepts(source) is False


def test_the_acceptable_list_is_left_open_on_purpose():
    """We do not know which connector holds it, and an enumerated list would refuse the answer from
    a source nobody anticipated. The NEGATIVE list does the work."""
    need = need_from_residue(_row(), org_id="o", trace_id="t")
    assert need.acceptable_sources == ()
    assert need.accepts("drive") is True


def test_the_window_is_the_period_the_residue_spanned():
    need = need_from_residue(_row(), org_id="o", trace_id="t")
    assert need.window_from == _T0 and need.window_to == _T1


# =================================================================================================
# 5 · ⛔ it flows through data, never by calling capture
# =================================================================================================
def test_this_module_does_not_reach_into_capture():
    """A sweep that fetched inline would make a graph pass wait on a network. The need is a row;
    the executor picks it up — the same mechanism `feedback/` uses to reach `reason/`."""
    import inspect

    from genios_engine.context import evidence_needs

    source = inspect.getsource(evidence_needs)
    assert "genios_engine.capture" not in source
