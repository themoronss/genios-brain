"""`sick` is health information, and `team_away` promises it never reaches a colleague.

⛔ `reason/team/away.py` states it in its own docstring — *"**No leave reason ever leaves this
module**: windows are reported as who + when; the `sick` kind is reported as `leave`"* — and again
on the mapping itself: *"Kinds a person may see about a colleague. `sick` is health information →
reported as leave."*

⛔⛔ **Nothing asserted any of it.** The module was one of two in the engine that no test reached by
any means, which is how the audit's deleted naming column earned its one real finding. A one-line
change to `_PUBLIC_KIND`, or a new kind added to `AVAILABILITY_KINDS` and not mapped, tells every
seat in the org why a colleague is off.

⛔ THE EMITTED VOCABULARY IS DERIVED, NEVER SPELLED. `contracts/availability.AVAILABILITY_KINDS` is
the legal set and `ABSENT_KINDS` the absent half; what `team_away` may emit follows from those two
and `_PUBLIC_KIND`. A hand-written list here would stop covering whatever kind was added last.

⛔ NO DATABASE. `team_away`'s two collaborators are module-level imports, so the seam is the module
namespace — and the doubles below return the REAL `AvailabilityWindow` and `Person` dataclasses, not
stand-ins, so a field renamed in production breaks this test rather than passing it.
"""
from __future__ import annotations

from datetime import date

import pytest

from genios_engine.context.availability import AvailabilityWindow
from genios_engine.context.correlation_people import Person
from genios_engine.contracts.availability import ABSENT_KINDS, AVAILABILITY_KINDS
from genios_engine.reason.team import away as A

_START, _END = date(2026, 10, 5), date(2026, 10, 12)

#: What `team_away` may put in front of a colleague — derived from the contract, not listed.
_EMITTABLE = frozenset(A._PUBLIC_KIND.get(k, k) for k in ABSENT_KINDS)


class _Directory:
    def __init__(self, people: dict[str, Person]):
        self._by_node = people
        self._by_email = {p.email: p for p in people.values() if p.email}

    def for_node(self, node_id):
        return self._by_node.get(node_id)

    def for_email(self, email):
        return self._by_email.get(email)


def _window(kind: str, *, node="node_1", key="a@x.com", start=_START, end=None,
            cover=None) -> AvailabilityWindow:
    return AvailabilityWindow(
        person_node_id=node, person_key=key, display_name="Priya", kind=kind,
        start=start, end=end or date(2026, 10, 8), cover=cover, authority_rank=1,
        confidence=0.9, occurred_at=None, fact_version_id=f"fv_{kind}_{node}")


def _patch(monkeypatch, windows, people):
    monkeypatch.setattr(A, "org_visible_windows",
                        lambda conn, org_id, start, end: list(windows), raising=True)
    monkeypatch.setattr(A, "load_directory",
                        lambda conn, org_id: _Directory(people), raising=True)


def _seat(node="node_1", seat="seat_1", email="a@x.com", name="Priya") -> Person:
    return Person(node_id=node, email=email, name=name, seat_id=seat)


# ── the promise, over every kind the contract allows ───────────────────────────────────────────

@pytest.mark.parametrize("kind", sorted(AVAILABILITY_KINDS))
def test_no_kind_reaches_a_colleague_as_sick(monkeypatch, kind):
    """⛔ Total over the declared vocabulary, so a kind added to the contract and not mapped fails
    here rather than reaching a colleague."""
    _patch(monkeypatch, [_window(kind)], {"node_1": _seat()})
    rows = A.team_away(object(), "org_1", start=_START, end=_END)
    assert all(r["kind"] != "sick" for r in rows), (
        f"⛔ a `{kind}` window reached a colleague as `sick`. `away.py` promises *'no leave reason "
        "ever leaves this module'* — the mapping in `_PUBLIC_KIND` is the only thing keeping it")


def test_sick_is_reported_as_leave_and_not_merely_dropped(monkeypatch):
    """⛔ The mapping must TRANSFORM, not suppress: a dropped window would hide that somebody is
    away at all, which is the information the team view exists to give."""
    _patch(monkeypatch, [_window("sick")], {"node_1": _seat()})
    rows = A.team_away(object(), "org_1", start=_START, end=_END)
    assert len(rows) == 1, "the sick window vanished — the team no longer knows anyone is away"
    assert rows[0]["kind"] == "leave"
    assert rows[0]["seat_id"] == "seat_1" and rows[0]["name"] == "Priya"


@pytest.mark.parametrize("kind", sorted(ABSENT_KINDS))
def test_every_absent_kind_emits_something_in_the_declared_vocabulary(monkeypatch, kind):
    _patch(monkeypatch, [_window(kind)], {"node_1": _seat()})
    rows = A.team_away(object(), "org_1", start=_START, end=_END)
    assert len(rows) == 1, f"an absent `{kind}` window produced nothing"
    assert rows[0]["kind"] in _EMITTABLE, (rows[0]["kind"], sorted(_EMITTABLE))


def test_the_emitted_vocabulary_cannot_contain_a_health_kind():
    """⛔ Derived, so this is an assertion about the CONTRACT rather than about one call: nothing in
    what `team_away` may emit is the health kind the module names."""
    assert "sick" not in _EMITTABLE, sorted(_EMITTABLE)
    assert "sick" in AVAILABILITY_KINDS, (
        "the contract no longer has a `sick` kind — if health windows are modelled differently "
        "now, this whole file needs re-reading rather than deleting")


def test_no_mapping_names_a_kind_the_contract_does_not_have():
    """A stale mapping is a lie about what can arrive."""
    stale = sorted(set(A._PUBLIC_KIND) - set(AVAILABILITY_KINDS))
    assert not stale, f"`_PUBLIC_KIND` maps kinds that cannot occur: {stale}"


# ── and the row never carries anything but who and when ────────────────────────────────────────

def test_a_row_carries_only_who_and_when(monkeypatch):
    """⛔ *'windows are reported as who + when'* — a `cover`, a `reason` or a confidence leaking
    into the row would be the same failure in a different field."""
    # ⛔ The window really carries a cover, a confidence and a fact id. The assertion is that NONE
    # of them reaches the row — the first version of this test set the cover with a no-op
    # expression and proved nothing about the field it was named for.
    window = _window("sick", cover="somebody_else")
    assert window.cover == "somebody_else", "the fixture stopped carrying the field under test"
    _patch(monkeypatch, [window], {"node_1": _seat()})
    rows = A.team_away(object(), "org_1", start=_START, end=_END)
    assert set(rows[0]) == {"seat_id", "name", "start", "end", "kind"}, sorted(rows[0])
    assert "somebody_else" not in str(rows[0])


# ── the other two stated rules ─────────────────────────────────────────────────────────────────

def test_a_person_with_no_seat_is_not_listed(monkeypatch):
    """⛔ *'External people (no seat) are not listed.'* A counterparty's absence is not the team's
    business, and this is the only thing that keeps it out."""
    _patch(monkeypatch, [_window("leave", node="node_x", key="outside@other.com")],
           {"node_x": Person(node_id="node_x", email="outside@other.com",
                             name="Outsider", seat_id=None)})
    assert A.team_away(object(), "org_1", start=_START, end=_END) == []


def test_a_window_is_matched_by_email_when_the_node_is_unknown(monkeypatch):
    """The fallback the module writes explicitly: no node match, but a `person_key` with an `@`."""
    _patch(monkeypatch, [_window("leave", node="unknown_node", key="a@x.com")],
           {"other": _seat(node="other")})
    rows = A.team_away(object(), "org_1", start=_START, end=_END)
    assert [r["seat_id"] for r in rows] == ["seat_1"]


def test_the_same_seat_and_start_is_reported_once(monkeypatch):
    """Two facts about one absence are one absence."""
    _patch(monkeypatch, [_window("leave"), _window("sick")], {"node_1": _seat()})
    rows = A.team_away(object(), "org_1", start=_START, end=_END)
    assert len(rows) == 1, rows


def test_rows_are_ordered_by_start_then_name_then_seat(monkeypatch):
    people = {"n1": _seat(node="n1", seat="s1", email="b@x.com", name="Bo"),
              "n2": _seat(node="n2", seat="s2", email="c@x.com", name="Ana")}
    _patch(monkeypatch, [
        _window("leave", node="n1", key="b@x.com", start=date(2026, 10, 7)),
        _window("leave", node="n2", key="c@x.com", start=date(2026, 10, 6)),
    ], people)
    rows = A.team_away(object(), "org_1", start=_START, end=_END)
    assert [r["name"] for r in rows] == ["Ana", "Bo"], rows
