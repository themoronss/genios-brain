"""U03 · grouping what arrived together — and U04 · the coverage that licenses a claim about it.

    pytest tests/capture/esqe/test_bundle.py -q

Two rules carry this module, and both are easy to "simplify" into a defect:

  1. ⛔ **Identity joins have no window; proximity joins do.** A thread is a thread whether its
     messages are four minutes or four months apart. An ENTITY is not: "Acme" in January and
     "Acme" in September are the same company and not the same event, and without a window every
     mention of a frequent counterparty collapses into one ever-growing bundle that means nothing.

  2. ⛔ **Merged coverage takes the WEAKEST per source, never an average.** A claim about a group is
     only as licensed as its least-covered member. Averaging manufactures a licence nobody has.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.esqe.bundle import (ENTITY_WINDOW, build_bundle, build_bundles,
                                               bundle_id_for, entity_keys, group_signals,
                                               join_keys, merged_coverage)

pytestmark = pytest.mark.unit

_T0 = datetime(2026, 9, 29, 9, 0, tzinfo=timezone.utc)


class _Mention:
    def __init__(self, canonical_hint=None, surface_form=None):
        self.canonical_hint = canonical_hint
        self.surface_form = surface_form


class _Extraction:
    def __init__(self, entities=()):
        self.entities = entities


class _Signal:
    """Only the fields the grouper reads. Deliberately not the real model: this module is a pure
    function over a handful of names, and a fixture built from the full contract would test
    pydantic rather than the grouping."""

    def __init__(self, signal_id, *, thread_key=None, subject_key=None, entities=(),
                 occurred_at=_T0, coverage=None):
        self.signal_id = signal_id
        self.thread_key = thread_key
        self.subject_key = subject_key
        self.extraction = _Extraction(tuple(_Mention(canonical_hint=e) for e in entities))
        self.occurred_at = occurred_at
        self.coverage = coverage or {}


# =================================================================================================
# 1 · the keys, and why they are namespaced
# =================================================================================================
def test_identity_keys_are_namespaced():
    """A thread key and a subject key are both opaque strings. Unprefixed, one could join a thread
    to a contract that happened to hash the same way — a join nobody could explain afterwards."""
    keys = join_keys(_Signal("s1", thread_key="abc", subject_key="abc"))
    assert keys == {"thread:abc", "subject:abc"}


def test_entity_keys_are_separate_from_identity_keys():
    """Kept apart because they are windowed and identity keys are not."""
    signal = _Signal("s1", thread_key="t", entities=("Acme",))
    assert join_keys(signal) == {"thread:t"}
    assert entity_keys(signal) == {"entity:acme"}


def test_entity_keys_are_case_folded():
    assert entity_keys(_Signal("s", entities=("ACME",))) == entity_keys(
        _Signal("s", entities=("acme",)))


# =================================================================================================
# 2 · identity joins — no window
# =================================================================================================
def test_one_thread_is_one_group_however_far_apart():
    """⛔ Splitting a thread on a clock produces two half-threads that each look like a complete
    conversation."""
    groups = group_signals([
        _Signal("s1", thread_key="t1", occurred_at=_T0),
        _Signal("s2", thread_key="t1", occurred_at=_T0 + timedelta(days=120)),
    ])
    assert len(groups) == 1


def test_a_shared_subject_joins_regardless_of_time():
    groups = group_signals([
        _Signal("s1", subject_key="contract:CTR-441", occurred_at=_T0),
        _Signal("s2", subject_key="contract:CTR-441", occurred_at=_T0 + timedelta(days=90)),
    ])
    assert len(groups) == 1


# =================================================================================================
# 3 · proximity joins — windowed
# =================================================================================================
def test_the_same_entity_inside_the_window_joins():
    groups = group_signals([
        _Signal("s1", entities=("Acme",), occurred_at=_T0),
        _Signal("s2", entities=("Acme",), occurred_at=_T0 + timedelta(days=2)),
    ])
    assert len(groups) == 1


def test_the_same_entity_outside_the_window_does_not():
    """⛔ Without this, every mention of a frequent counterparty collapses into one bundle."""
    groups = group_signals([
        _Signal("s1", entities=("Acme",), occurred_at=_T0),
        _Signal("s2", entities=("Acme",), occurred_at=_T0 + ENTITY_WINDOW + timedelta(days=1)),
    ])
    assert len(groups) == 2


def test_a_signal_with_no_instant_is_joined_not_dropped():
    """It is missing a date, not proven to be far away. Dropping it would shrink a bundle for a
    reason the bundle could not then state."""
    groups = group_signals([
        _Signal("s1", entities=("Acme",), occurred_at=_T0),
        _Signal("s2", entities=("Acme",), occurred_at=None),
    ])
    assert len(groups) == 1


# =================================================================================================
# 4 · a group of one is an answer
# =================================================================================================
def test_a_signal_that_shares_nothing_is_its_own_group():
    groups = group_signals([_Signal("s1", thread_key="a"), _Signal("s2", thread_key="b")])
    assert [len(g) for g in groups] == [1, 1]


def test_transitive_grouping():
    """s1–s2 by thread, s2–s3 by entity: all three are one group."""
    groups = group_signals([
        _Signal("s1", thread_key="t1"),
        _Signal("s2", thread_key="t1", entities=("Acme",)),
        _Signal("s3", entities=("Acme",)),
    ])
    assert len(groups) == 1 and len(groups[0]) == 3


# =================================================================================================
# 5 · ⛔ the id is the idempotence
# =================================================================================================
def test_the_same_signals_in_any_order_make_the_same_id():
    """The group is a SET. An order-sensitive id would make a replayed page a second bundle."""
    assert bundle_id_for("org", ["b", "a", "c"]) == bundle_id_for("org", ["a", "b", "c"])


def test_a_different_org_makes_a_different_id():
    assert bundle_id_for("org1", ["a"]) != bundle_id_for("org2", ["a"])


def test_a_different_member_makes_a_different_id():
    assert bundle_id_for("org", ["a", "b"]) != bundle_id_for("org", ["a", "c"])


# =================================================================================================
# 6 · ⛔ U04 · coverage — weakest per source, never averaged
# =================================================================================================
def _cov(source, bp, **over):
    entry = {"source": source, "indexed": 1, "claimed_total": 10, "is_estimate": False,
             "cursor_exhausted": False, "completeness_bp": bp}
    entry.update(over)
    return entry


def test_the_weakest_member_sets_the_groups_coverage():
    merged = merged_coverage([
        _Signal("s1", coverage={"sources": [_cov("gmail", 9500)]}),
        _Signal("s2", coverage={"sources": [_cov("gmail", 800)]}),
    ])
    assert merged["sources"][0]["completeness_bp"] == 800


def test_it_is_never_an_average():
    """9500 and 800 average to 5150 — a licence neither member has."""
    merged = merged_coverage([
        _Signal("s1", coverage={"sources": [_cov("gmail", 9500)]}),
        _Signal("s2", coverage={"sources": [_cov("gmail", 800)]}),
    ])
    assert merged["sources"][0]["completeness_bp"] != 5150


def test_unknown_beats_any_percentage():
    """⛔ *"We do not know what we read"* is weaker than any number, and a caller must be able to
    tell it from a low one."""
    merged = merged_coverage([
        _Signal("s1", coverage={"sources": [_cov("gmail", 9500)]}),
        _Signal("s2", coverage={"sources": [_cov("gmail", None, claimed_total=None)]}),
    ])
    assert merged["sources"][0]["completeness_bp"] is None


def test_sources_stay_separate():
    merged = merged_coverage([
        _Signal("s1", coverage={"sources": [_cov("gmail", 800), _cov("gcal", 10000)]}),
    ])
    by_source = {s["source"]: s["completeness_bp"] for s in merged["sources"]}
    assert by_source == {"gmail": 800, "gcal": 10000}


def test_no_blended_number_is_produced():
    merged = merged_coverage([_Signal("s1", coverage={"sources": [_cov("gmail", 800)]})])
    assert "completeness_bp" not in merged


def test_the_window_is_the_widest_the_members_span():
    """A claim about the group covers the whole period the group occupies."""
    merged = merged_coverage([
        _Signal("s1", coverage={"window_from": "2026-08-01", "window_to": "2026-08-31",
                                "sources": []}),
        _Signal("s2", coverage={"window_from": "2026-09-01", "window_to": "2026-09-30",
                                "sources": []}),
    ])
    assert merged["window_from"] == "2026-08-01"
    assert merged["window_to"] == "2026-09-30"


# =================================================================================================
# 7 · the boundary object
# =================================================================================================
def test_a_group_with_one_subject_names_it_and_proposes_relationships():
    bundle = build_bundle("org", "trace", [
        _Signal("s1", subject_key="contract:CTR-441", entities=("Acme",)),
        _Signal("s2", subject_key="contract:CTR-441"),
    ])
    assert bundle.subject_key == "contract:CTR-441"
    assert bundle.candidate_relationships == ("s1 concerns contract:CTR-441",
                                              "s2 concerns contract:CTR-441")
    assert bundle.entity_keys == ("entity:acme",)


def test_a_group_with_two_subjects_names_neither():
    """⛔ Two subjects in one group is not a bundle with two subjects — it is a group the joins
    over-merged, and naming one of them would hide that."""
    bundle = build_bundle("org", "trace", [
        _Signal("s1", thread_key="t", subject_key="contract:A"),
        _Signal("s2", thread_key="t", subject_key="contract:B"),
    ])
    assert bundle.subject_key is None
    assert bundle.candidate_relationships == ()


def test_an_unnameable_group_says_so_rather_than_leaving_it_blank():
    """It is what an EvidenceNeed is raised from."""
    bundle = build_bundle("org", "trace", [_Signal("s1", thread_key="t")])
    assert "no subject could be named for this group" in bundle.unresolved


def test_build_bundles_covers_every_signal_exactly_once():
    signals = [_Signal("s1", thread_key="t1"), _Signal("s2", thread_key="t1"),
               _Signal("s3", thread_key="t2")]
    bundles = build_bundles("org", "trace", signals)
    seen = [sid for b in bundles for sid in b.signal_ids]
    assert sorted(seen) == ["s1", "s2", "s3"], "a signal was dropped or double-counted"
