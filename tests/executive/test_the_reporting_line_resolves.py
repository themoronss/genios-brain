"""S1 · the reporting line — two sources, one order, and why the tree's spec was wrong.

    pytest tests/executive/test_the_reporting_line_resolves.py -q

⛔ `tree.yaml`'s `M12.C1.U01` said to read `reports_to` from `seat_responsibilities` and **never** from
`org_seats.manager_seat_id`. Following it would leave every seat with no manager unless somebody had
filed a dated responsibility for it — and rung 7 of the escalation ladder (`escalate → manager`) would
climb into nothing.

The code reads **both, in order**, and `assignment.py:250` says why the column alone was not enough:

> `org_seats.manager_seat_id` is a single mutable column: covering the North for June means overwriting
> it on 1 June and remembering to overwrite it back on 1 July. Nobody remembers, so July's escalations
> still climb to the acting manager — and the June state was **DESTROYED** by the July write.

⛔ THE LAYERING WAS ASSERTED ONLY IN COMMENTS. `tests/executive/` did not exist. This file is the
first test the directory has ever held.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.executive.assignment import (REPORTS_TO, Responsibility, SeatDirectory,
                                                StaticSeatDirectory)

pytestmark = pytest.mark.unit

JUNE = datetime(2026, 6, 15, tzinfo=timezone.utc)
JULY = datetime(2026, 7, 15, tzinfo=timezone.utc)


def _cover(seat: str, manager: str, frm: datetime, until: datetime | None) -> Responsibility:
    """A dated acting term — `reports_to` with `accountability='covers'`."""
    return Responsibility(seat_id=seat, scope_kind=REPORTS_TO, scope_key=manager,
                          accountability="covers", valid_from=frm, valid_until=until)


def _dir(**seats) -> StaticSeatDirectory:
    return StaticSeatDirectory(seats=seats)


# =================================================================================================
# 1 · the standing line — the column the tree said to delete
# =================================================================================================
def test_with_no_line_at_all_there_is_no_manager():
    """`None`, not a guess. An escalation with no manager must refuse, never pick somebody."""
    d = _dir(priya={"active": True})
    assert d.manager_of("priya") is None


def test_the_column_alone_resolves_the_manager():
    """⛔ THE CASE THE TREE'S SPEC WOULD HAVE BROKEN. Most seats have only this."""
    d = _dir(priya={"active": True, "manager_seat_id": "maya"}, maya={"active": True})
    assert d.manager_of("priya") == "maya"


def test_an_inactive_manager_is_not_returned():
    """A departed manager still named in the column is not an escalation target."""
    d = _dir(priya={"active": True, "manager_seat_id": "maya"}, maya={"active": False})
    assert d.manager_of("priya") is None


# =================================================================================================
# 2 · the dated override, on top of the line
# =================================================================================================
def test_a_dated_cover_outranks_the_column_while_it_is_in_force():
    d = _dir(priya={"active": True, "manager_seat_id": "maya",
                    "responsibilities": [_cover("priya", "daniel", JUNE, JULY)]},
             maya={"active": True}, daniel={"active": True})
    assert d.manager_of("priya", at=JUNE + timedelta(days=1)) == "daniel"


def test_an_expired_cover_falls_back_to_the_standing_line():
    """⛔ THE TEST THAT CARRIES THIS WHOLE FILE. This is the entire reason the dated form exists: a
    column overwrite DESTROYS the previous state, so the acting term keeps applying forever. A test
    that only checked the override applies would pass on an implementation that never stops."""
    d = _dir(priya={"active": True, "manager_seat_id": "maya",
                    "responsibilities": [_cover("priya", "daniel", JUNE, JULY)]},
             maya={"active": True}, daniel={"active": True})
    assert d.manager_of("priya", at=JULY + timedelta(days=1)) == "maya"


def test_a_cover_that_has_not_started_does_not_apply_yet():
    d = _dir(priya={"active": True, "manager_seat_id": "maya",
                    "responsibilities": [_cover("priya", "daniel", JULY, None)]},
             maya={"active": True}, daniel={"active": True})
    assert d.manager_of("priya", at=JUNE) == "maya"


def test_an_open_ended_cover_keeps_applying():
    d = _dir(priya={"active": True, "manager_seat_id": "maya",
                    "responsibilities": [_cover("priya", "daniel", JUNE, None)]},
             maya={"active": True}, daniel={"active": True})
    assert d.manager_of("priya", at=JULY) == "daniel"


def test_a_cover_naming_an_inactive_seat_falls_through_to_the_column():
    """A cover is an override, not a veto. If the acting manager has left, the standing line still
    holds — otherwise one stale row silently removes a seat's manager."""
    d = _dir(priya={"active": True, "manager_seat_id": "maya",
                    "responsibilities": [_cover("priya", "daniel", JUNE, None)]},
             maya={"active": True}, daniel={"active": False})
    assert d.manager_of("priya", at=JULY) == "maya"


# =================================================================================================
# 3 · ⛔ "who was her manager in June?", asked in September
# =================================================================================================
def test_the_same_directory_answers_differently_for_june_and_july():
    """⛔ THE PROPERTY THE DATED FORM EXISTS FOR, stated as one assertion. Nothing was overwritten
    between these two calls — the window did the work."""
    d = _dir(priya={"active": True, "manager_seat_id": "maya",
                    "responsibilities": [_cover("priya", "daniel", JUNE, JULY)]},
             maya={"active": True}, daniel={"active": True})
    assert d.manager_of("priya", at=JUNE + timedelta(days=1)) == "daniel"
    assert d.manager_of("priya", at=JULY + timedelta(days=1)) == "maya"


def test_at_defaults_to_now_so_every_existing_caller_is_unchanged():
    """`at` was added optional on purpose — a required parameter would have been a signature break
    across every caller of the ladder."""
    import inspect

    assert inspect.signature(StaticSeatDirectory.manager_of).parameters["at"].default is None


# =================================================================================================
# 4 · a cover is ownership, never permission
# =================================================================================================
def test_a_responsibility_says_a_card_is_yours_never_that_you_may_sign_it():
    """`Responsibility`'s own docstring: *"a regional manager owns the region and cannot sign the
    contract."* Authority is `authority_rules`, dated and source-ranked, and a second table implying
    permission would be two answers to one question."""
    r = _cover("priya", "daniel", JUNE, JULY)
    assert not hasattr(r, "may_approve")
    assert not hasattr(r, "authority")
    assert "SIGN" in (Responsibility.__doc__ or "")


def test_an_inferred_responsibility_may_never_narrow_a_view():
    """⛔ Hiding a real situation from somebody on the strength of a guess about their job is a silent
    false negative — the one failure the concept could introduce."""
    guessed = Responsibility(seat_id="priya", scope_kind="region", scope_key="west",
                             source="inferred")
    declared = Responsibility(seat_id="priya", scope_kind="region", scope_key="west",
                              source="admin_declared")
    assert guessed.narrows is False
    assert declared.narrows is True


def test_the_window_is_half_open_so_a_term_that_ended_yesterday_stops_today():
    r = _cover("priya", "daniel", JUNE, JULY)
    assert r.applies_at(JUNE) is True
    assert r.applies_at(JULY - timedelta(seconds=1)) is True
    assert r.applies_at(JULY) is False, "valid_until is exclusive, like AuthorityRule's window"


# =================================================================================================
# 5 · the protocol stays small on purpose
# =================================================================================================
#: ⛔ THE PROTOCOL SAYS THREE AND HAS SEVEN — a drift this test records rather than fixes.
#:
#: `SeatDirectory`'s docstring: *"Kept to three questions on purpose. A richer directory abstraction
#: would invite ownership logic to grow features nobody asked for; these three are what the rules and
#: the escalation ladder genuinely need."*
#:
#: Measured: `active_seat`, `responsibilities`, `manager_of`, **`admins`, `seat_for_node`,
#: `seats_for_scope`, `answerable_for`**. The exact growth the comment warned about happened, and the
#: comment was never updated to say it was accepted.
#:
#: ⛔ NOT FIXED HERE, EITHER WAY. Deleting four methods that callers use would break routing to close a
#: documentation gap; rewriting the docstring is a judgement about whether the growth was right, and
#: that is a decision with an owner. The honest action is to pin the CURRENT surface so the NEXT
#: addition is deliberate, and to say so.
_DIRECTORY_QUESTIONS = {"active_seat", "responsibilities", "manager_of",
                        "admins", "seat_for_node", "seats_for_scope", "answerable_for"}


def test_the_directory_protocol_has_not_grown_again():
    """⛔ *"A richer directory abstraction would invite ownership logic to grow features nobody asked
    for."* It grew from three to seven. This pins seven, so the eighth is a decision somebody makes on
    purpose rather than a method that appeared."""
    asked = {n for n in dir(SeatDirectory) if not n.startswith("_")}
    assert asked == _DIRECTORY_QUESTIONS


def test_the_three_the_ladder_genuinely_needs_are_still_there():
    """Whatever else grew, these are the ones the docstring names as load-bearing."""
    for name in ("active_seat", "responsibilities", "manager_of"):
        assert callable(getattr(SeatDirectory, name, None))


def test_the_docstring_still_claims_three_and_that_is_recorded():
    """⛔ Asserted in the positive so the drift is visible in a test result, not only in a comment. If
    somebody updates the docstring deliberately, this fails and gets deleted — on purpose."""
    doc = SeatDirectory.__doc__ or ""
    assert "three questions" in doc
    assert len(_DIRECTORY_QUESTIONS) == 7, "the docstring says three; the protocol has seven"


def test_the_static_directory_satisfies_the_protocol():
    """The in-memory twin exists so a routing decision can be reconstructed without the live org
    still looking the way it did that day."""
    assert isinstance(_dir(a={"active": True}), SeatDirectory)
