"""Visibility contract — scope/principals narrowing, and the excluded_subjects denylist."""
from __future__ import annotations

from genios_engine.contracts.visibility import ORG, PARTICIPANTS, PRIVATE, PUBLIC, Visibility, narrowest


def test_default_visibility_is_unaffected_by_exclusion():
    v = Visibility()
    assert v.can_view("anyone@x.com", org_member=True) is True
    assert v.can_view(None, org_member=False) is False


def test_excluded_subject_cannot_view_even_at_public_scope():
    v = Visibility(scope=PUBLIC, excluded_subjects=["founder@antler.test"])
    assert v.can_view("random@world.com") is True
    assert v.can_view("Founder@Antler.Test") is False        # case-insensitive


def test_excluded_subject_cannot_view_even_at_org_scope():
    v = Visibility(scope=ORG, excluded_subjects=["founder@antler.test"])
    assert v.can_view("colleague@antler.test", org_member=True) is True
    assert v.can_view("founder@antler.test", org_member=True) is False


def test_excluded_subject_cannot_view_even_if_also_a_principal():
    # The doc's exact Antler shape: a founder is technically a "participant" in the evidence
    # (it's their own work) but must never see the derived insight about it.
    v = Visibility(scope=PARTICIPANTS,
                   principals=["operator@antler.test", "founder@antler.test"],
                   excluded_subjects=["founder@antler.test"])
    assert v.can_view("operator@antler.test") is True
    assert v.can_view("founder@antler.test") is False


def test_non_excluded_participant_still_views_normally():
    v = Visibility(scope=PARTICIPANTS, principals=["a@x.com", "b@x.com"])
    assert v.can_view("a@x.com") is True
    assert v.can_view("c@x.com") is False


def test_narrowest_unions_exclusions_even_when_only_one_side_carries_one():
    a = Visibility(scope=ORG)                                       # no exclusion
    b = Visibility(scope=ORG, excluded_subjects=["founder@antler.test"])
    merged = narrowest(a, b)
    assert merged.scope == ORG
    assert merged.excluded_subjects == ["founder@antler.test"]
    assert merged.can_view("founder@antler.test") is False


def test_narrowest_unions_exclusions_from_both_sides():
    a = Visibility(scope=PARTICIPANTS, principals=["op@x.com"], excluded_subjects=["a@x.com"])
    b = Visibility(scope=PARTICIPANTS, principals=["op@x.com"], excluded_subjects=["b@x.com"])
    merged = narrowest(a, b)
    assert set(merged.excluded_subjects) == {"a@x.com", "b@x.com"}


def test_narrowest_still_narrows_scope_and_intersects_principals_as_before():
    org = Visibility(scope=ORG)
    private = Visibility(scope=PRIVATE, principals=["owner@x.com"])
    merged = narrowest(org, private)
    assert merged.scope == PRIVATE
    assert merged.principals == ["owner@x.com"]
