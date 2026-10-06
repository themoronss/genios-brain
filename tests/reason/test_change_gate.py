"""STEP-02 · the change gate's rule: skip a subject only when nothing it depends on moved, and its card
keeps its authority.

    pytest tests/reason/test_change_gate.py -q

`reason/change_gate.should_skip` (tree `yc2_w27_s02/M20.C3.L-logic.V0.U01`). Pure — no clock, no I/O.

A skip spends nothing, so the rule is written from the side of what a skip must never cost:

  * a decision on inputs that changed — the fingerprint is the decision's inputs, so a different
    one always runs;
  * a card that quietly loses its authority — nothing renews a signal's `authority_expires_at`
    today, and a re-run after expiry is what replaces the card, so a live subject is skipped only
    while its standing signal's authority has not lapsed (`RENEW_MARGIN` is zero, measured: a day's
    margin re-decided every sweep of a card's last 24 hours and renewed nothing);
  * a card the gate thinks is standing and is not — a live subject that emitted or kept a signal
    skips only while that signal is still open;
  * a retry — an outcome recorded as `indeterminate` (the evaluation failed, the model was
    unavailable, or the outcome hangs on a clock the fingerprint does not carry) runs every sweep.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.reason import change_gate as cg
from genios_engine.reason.fingerprint_store import (DEFERRED, EMITTED, INDETERMINATE, OUTCOMES,
                                                    SHADOW, STANDING, SUPPRESSED, StoredFingerprint)

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def _stored(outcome: str, fingerprint: str = "fp_a") -> StoredFingerprint:
    return StoredFingerprint(subject_key="k", lane="compiled", fingerprint=fingerprint,
                             outcome=outcome, run_id="run_1", decided_at=NOW - timedelta(hours=1),
                             last_checked_at=NOW - timedelta(minutes=15), skips=3)


def _gate(stored, *, fingerprint="fp_a", live=True, expires=NOW + timedelta(days=3)):
    return cg.should_skip(stored, fingerprint, live=live, standing_expires_at=expires,
                          eval_time=NOW)


def test_a_subject_never_decided_runs():
    assert _gate(None) == cg.GateVerdict(skip=False, reason=cg.NEW)


@pytest.mark.parametrize("outcome", OUTCOMES)
def test_a_changed_fingerprint_always_runs(outcome):
    assert _gate(_stored(outcome), fingerprint="fp_b") == cg.GateVerdict(skip=False,
                                                                         reason=cg.CHANGED)


@pytest.mark.parametrize("outcome", [EMITTED, STANDING])
def test_a_live_card_with_its_authority_good_for_days_is_skipped(outcome):
    assert _gate(_stored(outcome)) == cg.GateVerdict(skip=True, reason=cg.UNCHANGED)


@pytest.mark.parametrize("left", [timedelta(0), -timedelta(minutes=1), -timedelta(hours=1)])
def test_a_live_card_whose_authority_has_lapsed_is_re_decided(left):
    """At the instant it lapses, or after: the lane replaces the signal on this run, as it does
    today without the gate."""
    assert _gate(_stored(STANDING), expires=NOW + left) == cg.GateVerdict(skip=False,
                                                                          reason=cg.EXPIRING)


@pytest.mark.parametrize("left", [timedelta(minutes=1), timedelta(hours=6), timedelta(hours=23)])
def test_a_live_card_with_any_authority_left_is_skipped(left):
    """⛔ Not re-decided inside its last day: a re-run then renews nothing (the compiled lane
    answers `standing`, the expiry stays), so it would be paid for on every remaining sweep."""
    assert _gate(_stored(EMITTED), expires=NOW + left).skip


def test_the_margin_is_zero():
    assert cg.RENEW_MARGIN == timedelta(0)


def test_a_live_card_that_is_no_longer_open_is_re_decided():
    """Its signal was resolved or expired by something else — a person, the lifecycle — so the
    gate must not believe it is standing."""
    assert _gate(_stored(EMITTED), expires=None) == cg.GateVerdict(skip=False,
                                                                   reason=cg.NOT_STANDING)


@pytest.mark.parametrize("outcome", [DEFERRED, SUPPRESSED])
def test_a_live_verdict_that_showed_nothing_new_is_skipped_on_unchanged_inputs(outcome):
    """A DEFER the decider gave, or a suppression its inputs decide, comes back the same on the same
    inputs — asked again it is the "DEFER or DECISION by chance" STEP-02 §4 measures."""
    assert _gate(_stored(outcome), expires=None) == cg.GateVerdict(skip=True,
                                                                   reason=cg.UNCHANGED)


@pytest.mark.parametrize("live", [True, False])
def test_an_indeterminate_outcome_is_retried_every_sweep(live):
    assert _gate(_stored(INDETERMINATE), live=live) == cg.GateVerdict(skip=False,
                                                                      reason=cg.RETRY)


@pytest.mark.parametrize("outcome", [SHADOW, SUPPRESSED, DEFERRED, EMITTED, STANDING])
def test_a_shadow_row_skips_on_its_fingerprint_alone(outcome):
    """A run that may not deliver keeps no card alive, so no signal is consulted."""
    assert _gate(_stored(outcome), live=False, expires=None) == cg.GateVerdict(
        skip=True, reason=cg.UNCHANGED)


def test_a_naive_expiry_is_read_as_utc():
    naive = (NOW + timedelta(days=3)).replace(tzinfo=None)
    assert _gate(_stored(STANDING), expires=naive).skip


def test_every_reason_is_named():
    assert set(cg.REASONS) == {cg.NEW, cg.CHANGED, cg.UNCHANGED, cg.EXPIRING, cg.NOT_STANDING,
                               cg.RETRY}


def test_a_live_subject_whose_last_run_was_shadow_runs():
    """The fingerprint carries the lane, so this cannot happen on one fingerprint — and if it does,
    the gate runs the decision rather than guess what a shadow outcome means for a live card."""
    assert _gate(_stored(SHADOW)) == cg.GateVerdict(skip=False, reason=cg.CHANGED)
