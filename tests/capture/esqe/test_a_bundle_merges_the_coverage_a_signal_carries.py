"""STEP-10 · a bundle merges the coverage its signals now carry — the typed block, not only its dict.

    .venv/bin/python -m pytest tests/capture/esqe/test_a_bundle_merges_the_coverage_a_signal_carries.py -q

`capture/esqe/bundle.merged_coverage` (tree `yc2_w27_s10 · M29.C5.L-logic.V2.U04`). Found replaying the golden
set after STEP-10's coverage units landed: per-signal coverage had been NULL on every signal (`STEP-18` B5), so
bundling only ever met `None` and fell to `{}`. Written at last, it reaches the bundler as the frozen
`SignalCoverage` the publisher builds — and `merged_coverage` called `.get` on it: "could not group 1 published
signal(s)", seventeen times in one golden run, every bundle of a covered signal lost. The stored row carries
`coverage.as_dict()`; the bundler now reads the typed block through that same shape, so a signal in memory and
a signal from its row merge alike, and the weakest member still sets the group's licence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from genios_engine.capture.coverage.signal_coverage import SignalCoverage, SourceCoverage
from genios_engine.capture.esqe.bundle import merged_coverage

pytestmark = pytest.mark.unit

AUG = datetime(2026, 8, 1, tzinfo=timezone.utc)
SEP = datetime(2026, 9, 1, tzinfo=timezone.utc)
OCT = datetime(2026, 10, 1, tzinfo=timezone.utc)


@dataclass
class _Signal:
    coverage: object


def _typed(indexed: int, total: int | None, *, frm=AUG, to=SEP, source="gmail") -> SignalCoverage:
    return SignalCoverage(window_from=frm, window_to=to, sources=(SourceCoverage(
        source=source, indexed=indexed, claimed_total=total, is_estimate=True,
        cursor_exhausted=True),))


def test_the_typed_block_the_publisher_builds_is_merged():
    merged = merged_coverage([_Signal(_typed(95, 100)), _Signal(_typed(8, 100, frm=SEP, to=OCT))])
    assert [(s["source"], s["completeness_bp"]) for s in merged["sources"]] == [("gmail", 800)]
    assert (merged["window_from"], merged["window_to"]) == (AUG, OCT)


def test_a_typed_block_and_a_stored_one_merge_alike():
    typed = _typed(8, 100)
    assert merged_coverage([_Signal(typed)]) == merged_coverage([_Signal(typed.as_dict())])


def test_unknown_still_beats_known_on_the_typed_block():
    merged = merged_coverage([_Signal(_typed(95, 100)), _Signal(_typed(40, None))])
    assert merged["sources"][0]["completeness_bp"] is None


def test_a_signal_with_no_coverage_adds_nothing():
    assert merged_coverage([_Signal(None), _Signal(_typed(95, 100))])["sources"][0][
        "completeness_bp"] == 9500
