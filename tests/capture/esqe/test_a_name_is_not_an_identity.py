"""L1 G6.3 / G6.5 — a bundle joins only on identity it can prove, and says why it joined.

Blueprint G6.3: *"same display name is not sufficient proof of identity"*; G6.2: *"abstain when competing
matches cannot be resolved safely … record unresolved candidate links separately"*; G6 exit: *"every
association is explainable; ambiguous links are preserved as unresolved"*.

Before: the proximity join keyed on `canonical_hint or surface_form`, so two mails a week apart that each
named "Priya" — two different people — became one bundle, and nothing in the bundle said why any two
signals were together. Two subjects merged into one group became `subject_key=None` with no word of it.

Now:
  * a PERSON known only by the name written (no canonical hint) is never a join key; when two signals
    of different groups share one inside the window, both bundles carry it as an unresolved candidate;
  * an organisation's written name and any resolved hint still join, as before;
  * every join that formed a group is a link record in `candidate_relationships` (method + key);
  * competing subjects in one group are stated in `unresolved`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.capture.esqe.bundle import build_bundles, group_signals

T0 = datetime(2026, 10, 1, 9, tzinfo=timezone.utc)


class _Mention:
    def __init__(self, surface_form, entity_type="person", canonical_hint=None):
        self.surface_form, self.entity_type, self.canonical_hint = (surface_form, entity_type,
                                                                    canonical_hint)


class _Extraction:
    def __init__(self, mentions):
        self.entities = tuple(mentions)


class _Signal:
    def __init__(self, sid, *, mentions=(), thread=None, subject=None, days=0):
        self.signal_id, self.thread_key, self.subject_key = sid, thread, subject
        self.occurred_at = T0 + timedelta(days=days)
        self.extraction = _Extraction(mentions)
        self.coverage = None


def _ids(groups):
    return [tuple(s.signal_id for s in g) for g in groups]


def test_two_people_with_one_first_name_are_not_one_bundle():
    a = _Signal("s1", mentions=[_Mention("Priya")], thread="t1")
    b = _Signal("s2", mentions=[_Mention("Priya")], thread="t2", days=2)
    assert _ids(group_signals([a, b])) == [("s1",), ("s2",)]

    bundles = build_bundles("o", "tr", [a, b])
    for bundle in bundles:
        assert any("'priya'" in u and "name only" in u for u in bundle.unresolved), bundle.unresolved


def test_a_resolved_person_still_joins():
    a = _Signal("s1", mentions=[_Mention("Priya", canonical_hint="priya@acme.test")])
    b = _Signal("s2", mentions=[_Mention("Priya S.", canonical_hint="priya@acme.test")], days=2)
    assert _ids(group_signals([a, b])) == [("s1", "s2")]


def test_an_organisation_by_its_written_name_still_joins():
    a = _Signal("s1", mentions=[_Mention("Acme", entity_type="organization")])
    b = _Signal("s2", mentions=[_Mention("ACME", entity_type="organization")], days=3)
    assert _ids(group_signals([a, b])) == [("s1", "s2")]


def test_every_join_is_a_link_record_with_its_method():
    a = _Signal("s1", thread="t1", subject="deal:acme")
    b = _Signal("s2", thread="t1", subject="deal:acme", days=40)
    c = _Signal("s3", mentions=[_Mention("Acme", entity_type="organization")], subject="deal:acme",
                days=41)
    (bundle,) = build_bundles("o", "tr", [a, b, c])
    links = [r for r in bundle.candidate_relationships if " ~ " in r]
    assert len(links) == 2, "one record per join that formed the group (n-1)"
    assert any(r.startswith("s1 ~ s2: same thread:t1") for r in links), links
    assert any("s3" in r and "subject:deal:acme" in r for r in links), links


def test_competing_subjects_are_stated_not_hidden():
    a = _Signal("s1", thread="t1", subject="deal:acme")
    b = _Signal("s2", thread="t1", subject="deal:globex", days=1)
    (bundle,) = build_bundles("o", "tr", [a, b])
    assert bundle.subject_key is None
    assert any("competing subjects" in u and "deal:acme" in u and "deal:globex" in u
               for u in bundle.unresolved), bundle.unresolved


def test_a_name_shared_outside_the_window_is_not_a_candidate():
    a = _Signal("s1", mentions=[_Mention("Priya")], thread="t1")
    b = _Signal("s2", mentions=[_Mention("Priya")], thread="t2", days=30)
    for bundle in build_bundles("o", "tr", [a, b]):
        assert not any("priya" in u for u in bundle.unresolved)
