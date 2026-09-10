"""L1-04 — a 29-row English job-title ladder, and one alias that inverted a real hierarchy.

    pytest tests/capture/esqe/test_the_ladder_is_not_only_english.py -q

`consultant` aliased to `contractor`, the 5000 floor. In a UK or Indian hospital a Consultant
is the SENIOR physician — the person whose sign-off the whole record turns on — and this table
filed them below an intern's manager. Same word, same seniority, in a law firm, in management
consulting and across most of the NHS. The alias was one industry's usage applied to every
industry, and it inverted the hierarchy it was trying to read.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.esqe.source_analyzer import (
    ROLE_AUTHORITY_BP,
    merged_ladder,
    role_authority_bp,
)

pytestmark = pytest.mark.unit


def test_a_consultant_is_no_longer_demoted_to_the_floor():
    """None is the honest answer: the cascade descends to the domain rungs and attributes the
    person on evidence the system has, rather than on a word somebody assumed meant outsider."""
    assert role_authority_bp("Consultant") is None
    assert role_authority_bp("Senior Consultant") is None


def test_a_clinic_can_say_what_a_consultant_is_worth():
    assert role_authority_bp("Consultant", {"consultant": 9500}) == 9500


@pytest.mark.parametrize(("title", "overlay", "expected"), [
    ("Proprietor", {"proprietor": 10000}, 10000),      # an exporter
    ("Silk", {"silk": 10000}, 10000),                  # a chambers
    ("Karta", {"karta": 10000}, 10000),                # a Hindu Undivided Family business
])
def test_a_business_the_shipped_table_was_never_asked_about(title, overlay, expected):
    assert role_authority_bp(title, overlay) == expected


def test_the_shipped_rungs_still_answer():
    for title, expected in (("CEO", 10000), ("CFO", 9500), ("VP", 9000), ("intern", 5000)):
        assert role_authority_bp(title) == expected


def test_an_overlay_may_restate_a_shipped_rung():
    """A tenant whose "manager" really is the decision-maker is not wrong; they are different."""
    assert role_authority_bp("manager") == 8000
    assert role_authority_bp("manager", {"manager": 10000}) == 10000


# =============================================================================================
# The floor rule survives any overlay.
# =============================================================================================
def test_a_rung_cannot_sink_below_an_unknown_person():
    """3000 is what an unknown sender is worth. A rung under it would make IDENTIFYING somebody
    a way to lose authority."""
    assert role_authority_bp("x", {"x": 0}) == 3000
    assert role_authority_bp("x", {"x": -100}) == 3000


def test_a_rung_cannot_exceed_a_basis_point():
    assert role_authority_bp("x", {"x": 50000}) == 10000


def test_a_non_numeric_rung_is_skipped_not_defaulted():
    """A default here would hand a made-up authority to a role the tenant mis-typed."""
    assert role_authority_bp("x", {"x": "very senior"}) is None
    assert role_authority_bp("CEO", {"x": "very senior"}) == 10000


def test_an_empty_overlay_changes_nothing():
    assert merged_ladder(None) is ROLE_AUTHORITY_BP
    assert merged_ladder({}) is ROLE_AUTHORITY_BP


def test_an_overlay_key_is_normalised_the_way_a_title_is():
    """A tenant writing "Chief Medical Officer" must reach the same rung as the title arriving
    from the graph does — otherwise the overlay looks broken to the person who wrote it."""
    assert role_authority_bp("Chief Medical Officer",
                             {"Chief Medical Officer": 9500}) == 9500


def test_the_guess_refusal_is_unchanged():
    """The table's own argument for refusing `Growth Ninja` is the argument for dropping the
    consultant alias, and it must keep applying."""
    assert role_authority_bp("Growth Ninja") is None
