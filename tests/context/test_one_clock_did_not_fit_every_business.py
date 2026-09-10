"""CTX-L2 · CTX-L4 · CORR-02 — three clocks, one number each, for every business at once.

    pytest tests/context/test_one_clock_did_not_fit_every_business.py -q

45 days was every domain's answer to "the correlation went cold", 45/180 aged every situation
in every domain, and `AbsenceType.STALE` was unreachable because `stale_after` defaulted to
None and the one production caller never passed it.

A support ticket is stale in three days; a fundraising conversation is perfectly alive at
ninety. `deal.value` from last quarter is probably still right; `thread.ball_in_court` from
last quarter is meaningless. A single number cannot be right for both halves of either pair —
it is wrong for whichever one it was not calibrated on, silently, forever.

`DomainSpec` carries the clocks now, and Layer 3 can already `register()` one at import time.
Its docstring says "no thresholds", and `situations.py` already drew the line this uses: a
lifecycle rule — WHEN does a thing stop being live — is a fact about a domain, where a
threshold is a decision, and decisions still belong to Layer 4.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.context.correlation import (
    CORRELATION_WINDOW_DAYS,
    joins_window,
    window_for,
)
from genios_engine.context.domain_spec import DomainSpec, register, spec_for
from genios_engine.context.quality.missing import expectations_from_spec
from genios_engine.context.situations import (
    ARCHIVE_AFTER_DAYS,
    DORMANT_AFTER_DAYS,
    _is_terminal,
    decide_lifecycle,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 10, tzinfo=timezone.utc)


@pytest.fixture
def restore_specs():
    """Every test here registers a spec; the registry is process-wide."""
    held = {d: spec_for(d) for d in ("sales", "support", "admin")}
    yield
    for domain, spec in held.items():
        register(spec)


# =============================================================================================
# CORR-02 — "the situation went cold".
# =============================================================================================
def test_a_domain_that_says_nothing_keeps_the_engine_default():
    assert window_for("sales") == CORRELATION_WINDOW_DAYS


def test_a_support_desk_can_go_cold_in_three_days(restore_specs):
    register(DomainSpec(domain="support", correlation_window_days=3))

    assert window_for("support") == 3
    assert window_for("sales") == CORRELATION_WINDOW_DAYS


def test_the_window_actually_reaches_the_join(restore_specs):
    """A number nobody passes is the defect, not the number."""
    old = NOW - timedelta(days=10)

    assert joins_window(group_first=old, group_last=old, event_at=NOW, window_days=45)
    assert not joins_window(group_first=old, group_last=old, event_at=NOW, window_days=3)


def test_an_unknown_domain_does_not_lose_the_window():
    assert window_for("a-domain-nobody-registered") == CORRELATION_WINDOW_DAYS


# =============================================================================================
# CTX-L2 — dormancy and archival.
# =============================================================================================
def _decide(*, days_quiet, **kw):
    return decide_lifecycle(
        current_status="active", resolved_by=None,
        last_seen_at=NOW - timedelta(days=days_quiet), resolved_at=None,
        terminal_by_fact=False, now=NOW, **kw)


def test_the_default_dormancy_is_unchanged():
    assert _decide(days_quiet=DORMANT_AFTER_DAYS + 1).status == "dormant"
    assert _decide(days_quiet=DORMANT_AFTER_DAYS - 1).status == "active"


def test_a_desk_can_call_a_ticket_dormant_in_three_days():
    assert _decide(days_quiet=5, dormant_after_days=3).status == "dormant"


def test_a_raise_can_stay_live_at_ninety_days():
    """The default would have called this dead at 46."""
    assert _decide(days_quiet=90, dormant_after_days=180).status == "active"


def test_the_archive_clock_moves_too():
    resolved = decide_lifecycle(
        current_status="resolved", resolved_by="statement",
        last_seen_at=NOW - timedelta(days=400), resolved_at=NOW - timedelta(days=30),
        terminal_by_fact=False, now=NOW, archive_after_days=7)

    assert resolved.status == "archived"


def test_the_ageing_sweep_reads_the_same_clock():
    """`decide_lifecycle` honoured the domain while `age_uncorrelated_situations` applied one
    global 45/180 — so the two paths disagreed about when the SAME row went dormant, depending
    only on whether a correlation still backed it."""
    import inspect

    from genios_engine.context import situations

    source = inspect.getsource(situations.age_uncorrelated_situations)

    assert "spec.dormant_after_days or DORMANT_AFTER_DAYS" in source
    assert "spec.archive_after_days or ARCHIVE_AFTER_DAYS" in source


# =============================================================================================
# The terminal rule is a declared fact, not a deal stage.
# =============================================================================================
def test_a_pipeline_still_ends_on_its_stage():
    assert _is_terminal(DomainSpec(domain="sales"), {"deal.stage": "Closed Won"})
    assert not _is_terminal(DomainSpec(domain="sales"), {"deal.stage": "negotiation"})


def test_a_clinic_can_end_on_its_own_fact():
    spec = DomainSpec(domain="clinic",
                      terminal_when=("case.status", frozenset({"discharged", "closed"})))

    assert _is_terminal(spec, {"case.status": "Discharged"})
    assert not _is_terminal(spec, {"case.status": "admitted"})
    assert not _is_terminal(spec, {"deal.stage": "closedwon"}), "the deal rule no longer applies"


def test_the_declared_values_are_normalised_the_way_a_stage_is():
    """A CRM writes CLOSEDWON, closed_won and Closed Won; a hospital system is no tidier."""
    spec = DomainSpec(domain="clinic", terminal_when=("case.status", frozenset({"Signed Off"})))

    assert _is_terminal(spec, {"case.status": "signed_off"})


# =============================================================================================
# CTX-L4 — an expiry per claim type, so STALE is reachable at all.
# =============================================================================================
def test_a_plain_label_still_means_never_stale(restore_specs):
    register(DomainSpec(domain="sales",
                        expected_fields={"sales_deal": {"deal.value": "the amount"}}))

    got = expectations_from_spec("sales", "sales_deal")

    assert got[0].label == "the amount"
    assert got[0].stale_after is None


def test_a_claim_can_declare_how_long_it_stays_true(restore_specs):
    """`deal.value` from last quarter is probably still right; `thread.ball_in_court` from last
    quarter is meaningless. One call-wide switch could only ever be wrong for one of them,
    which is presumably why nobody ever flipped it."""
    register(DomainSpec(domain="sales", expected_fields={"sales_deal": {
        "deal.value": "the amount",
        "thread.ball_in_court": {"label": "whose move", "stale_after_days": 14},
    }}))

    by_field = {e.field: e for e in expectations_from_spec("sales", "sales_deal")}

    assert by_field["deal.value"].stale_after is None
    assert by_field["thread.ball_in_court"].stale_after == timedelta(days=14)
    assert by_field["thread.ball_in_court"].label == "whose move"


def test_a_dated_claim_reaches_the_classifier():
    """The field is worth nothing if `classify_absence` still reads only its argument."""
    import inspect

    from genios_engine.context.quality import missing

    source = inspect.getsource(missing.classify_absence)

    assert "expiry = expectation.stale_after or stale_after" in source
