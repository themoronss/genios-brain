"""The reasoners read `owner.availability` / `owner.status` / `owner.availability_bp`; nothing wrote
them. They now resolve from the owner's `person.availability` windows — in the exact vocabulary
the dependency and resource units already understand."""
from __future__ import annotations

from datetime import date, datetime, timezone

from genios_engine.context.availability import (AvailabilityWindow, current_window,
                                                owner_availability_facts)
from genios_engine.reason.reasoners.dependency_unit import OWNER_AVAILABLE, OWNER_UNAVAILABLE
from genios_engine.reason.reasoners.resource_unit import (_REDUCED_STATUSES,
                                                          _UNAVAILABLE_STATUSES)

TODAY = date(2026, 9, 17)


def _w(kind, start, end, *, rank=2, fv="fv1", at=datetime(2026, 9, 10, tzinfo=timezone.utc)):
    return AvailabilityWindow(person_node_id="n_anisha", person_key="anisha@acme.io",
                              display_name="Anisha", kind=kind, start=start, end=end,
                              cover="priya@acme.io", authority_rank=rank, confidence=0.85,
                              occurred_at=at, fact_version_id=fv)


def _index(*windows):
    return {"anisha@acme.io": list(windows), "anisha": list(windows)}


def test_owner_on_leave_reads_as_unavailable_in_both_units():
    facts = {"deal.owner": {"value": "Anisha@Acme.io"}}
    out = owner_availability_facts(facts, _index(_w("leave", date(2026, 9, 15),
                                                     date(2026, 9, 22))), on=TODAY)
    status = out["owner.availability"]["value"]
    assert status in OWNER_UNAVAILABLE and status in _UNAVAILABLE_STATUSES
    assert out["owner.status"]["value"] == status
    assert out["owner.availability_bp"]["value"] == 0
    assert out["owner.availability_window"]["value"] == {
        "kind": "leave", "from": "2026-09-15", "to": "2026-09-22", "cover": "priya@acme.io"}
    # provenance travels: the reasoner's evidence ref points at the real fact version
    assert out["owner.availability"]["fact_version_id"] == "fv1"
    assert out["owner.availability"]["authority_rank"] == 2


def test_every_absent_kind_maps_into_both_unavailable_vocabularies():
    for kind in ("leave", "ooo", "sick", "travel"):
        out = owner_availability_facts({"deal.owner": "anisha@acme.io"},
                                       _index(_w(kind, TODAY, TODAY)), on=TODAY)
        assert out["owner.status"]["value"] in OWNER_UNAVAILABLE & _UNAVAILABLE_STATUSES


def test_busy_is_reduced_and_leaves_basis_points_to_the_unit():
    out = owner_availability_facts({"deal.owner": "anisha@acme.io"},
                                   _index(_w("busy", TODAY, TODAY)), on=TODAY)
    assert out["owner.status"]["value"] in _REDUCED_STATUSES
    assert out["owner.status"]["value"] not in OWNER_AVAILABLE | OWNER_UNAVAILABLE
    assert "owner.availability_bp" not in out      # no measured figure → tunable mapping decides


def test_upcoming_absence_is_surfaced_not_current():
    out = owner_availability_facts({"relationship.owner": "anisha@acme.io"},
                                   _index(_w("leave", date(2026, 9, 21), date(2026, 9, 25))),
                                   on=TODAY)
    assert "owner.availability" not in out         # she is here today
    assert out["owner.next_unavailable"]["value"]["from"] == "2026-09-21"


def test_name_valued_owner_resolves_by_display_name():
    out = owner_availability_facts({"deal.owner": {"value": "Anisha"}},
                                   _index(_w("ooo", TODAY, None)), on=TODAY)
    assert out["owner.availability"]["value"] == "out_of_office"


def test_open_ended_window_expires_after_its_horizon():
    w = _w("ooo", date(2026, 9, 1), None)          # an auto-reply that never said when it ends
    assert w.covers(date(2026, 9, 14)) and not w.covers(date(2026, 9, 15))
    assert owner_availability_facts({"deal.owner": "anisha@acme.io"}, _index(w),
                                    on=TODAY) == {}


def test_no_owner_or_no_window_emits_nothing():
    idx = _index(_w("leave", TODAY, TODAY))
    assert owner_availability_facts({}, idx, on=TODAY) == {}
    assert owner_availability_facts({"deal.owner": "someone@else.io"}, idx, on=TODAY) == {}


def test_absence_outranks_reduced_capacity_then_authority():
    busy = _w("busy", TODAY, TODAY, rank=3, fv="b")
    leave = _w("leave", TODAY, TODAY, rank=2, fv="l")
    assert current_window([busy, leave], TODAY).fact_version_id == "l"
    cal = _w("ooo", TODAY, TODAY, rank=3, fv="cal")
    assert current_window([leave, cal], TODAY).fact_version_id == "cal"
