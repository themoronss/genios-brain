"""The change gate's rule — skip a subject only when nothing its decision depends on moved (STEP-02).

Every sweep re-decides every subject. On the golden runner one more sweep that brings nothing new
costs F13 2 model calls and F29 12, and changes no card (`speedrun008/YC-II W27/` STEP-02 §8.1).
`should_skip` is the one place that decides whether a subject's decision may be skipped. Pure — no
clock, no I/O: the lane hands it the stored row (`reason/fingerprint_store`), the fingerprint of
this sweep's inputs (`reason/fingerprint`) and, for a live subject, when its standing signal loses
its authority.

What a skip must never cost:

  * a decision on changed inputs — a different fingerprint always runs;
  * a card that quietly loses its authority — nothing renews `authority_expires_at` today, and a
    re-run after expiry is what replaces the card, so a live subject is skipped only while its
    standing signal's authority has not lapsed, and decided on the first sweep after it has;
  * a card that is not standing — a live subject that emitted or kept a signal skips only while
    that signal is still open;
  * a retry — `indeterminate` (the evaluation failed, the model was unavailable, or the outcome
    hangs on a clock the fingerprint does not carry: a cooldown, a daily budget) runs every sweep.

A shadow row keeps no card alive, so it skips on its fingerprint alone.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from genios_engine.reason.fingerprint_store import (DEFERRED, EMITTED, INDETERMINATE, STANDING,
                                                    SUPPRESSED, StoredFingerprint)

#: A live card is re-decided once its signal has this much authority left, or less — ZERO: once it
#: has lapsed. ⛔ CORRECTED BY MEASUREMENT (2026-10-06). The first value was a day, so the re-run
#: would happen while the card still showed. But a re-run before expiry renews nothing — the
#: compiled lane answers "standing" and the expiry stays put — so a day's margin re-decided the
#: subject on every sweep of its last 24 hours: ~96 decider and R-1 pairs per card per week, found
#: by the golden acceptance on F27. On the first sweep after the authority lapses the lane replaces
#: the signal, which is what it does today without the gate.
RENEW_MARGIN = timedelta(0)

NEW = "new"                    # never decided
CHANGED = "changed"            # what the decision depends on moved
UNCHANGED = "unchanged"        # the one reason a subject is skipped
EXPIRING = "expiring"          # the standing card is about to lose its authority
NOT_STANDING = "not_standing"  # the card the last decision left is no longer open
RETRY = "retry"                # the last outcome was indeterminate
REASONS: tuple[str, ...] = (NEW, CHANGED, UNCHANGED, EXPIRING, NOT_STANDING, RETRY)


@dataclass(frozen=True)
class GateVerdict:
    skip: bool
    reason: str


def should_skip(stored: StoredFingerprint | None, fingerprint: str, *, live: bool,
                standing_expires_at: datetime | None, eval_time: datetime) -> GateVerdict:
    """Whether this sweep may skip the subject's decision, and why.

    `standing_expires_at` is the `authority_expires_at` of the subject's open signal, or None when
    it has none open. Read only for a live subject whose last decision left a card.
    """
    if stored is None:
        return GateVerdict(False, NEW)
    if stored.fingerprint != fingerprint:
        return GateVerdict(False, CHANGED)
    if stored.outcome == INDETERMINATE:
        return GateVerdict(False, RETRY)
    if not live:
        return GateVerdict(True, UNCHANGED)
    if stored.outcome in (EMITTED, STANDING):
        if standing_expires_at is None:
            return GateVerdict(False, NOT_STANDING)
        if standing_expires_at.tzinfo is None:
            standing_expires_at = standing_expires_at.replace(tzinfo=timezone.utc)
        if standing_expires_at <= eval_time + RENEW_MARGIN:
            return GateVerdict(False, EXPIRING)
        return GateVerdict(True, UNCHANGED)
    if stored.outcome in (DEFERRED, SUPPRESSED):
        return GateVerdict(True, UNCHANGED)
    # SHADOW on a live subject: the fingerprint carries the lane, so this is a row whose capability
    # was live and shadow at once — never skip what the rule above cannot reason about.
    return GateVerdict(False, CHANGED)
