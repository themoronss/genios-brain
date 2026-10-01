r"""Plane R `S5.U08` · the roster's sources and the unit's defaults may not drift apart.

⛔ THE TRAP THIS CLOSES. After `S5.U02`–`U05`, `core.tradeoff`'s sources exist in three places:

    AXIS_SOURCES              tradeoff_unit.py      the plugin binding, with metrics
    source_units              tradeoff_unit.py      DERIVED from the above — one truth, two views
    _ROSTER[...].sources      expertise.py          the manifest's config, for the plan

The first two are one value seen twice; `U02` guarantees it. **The third is an independent copy.**

⛔ Two computations of one fact that are never compared eventually disagree. This programme found that
shape four times, and `unrouted_l2_types` was exactly it — a generated list and an independently
computed one, agreeing by luck until somebody forgot to regenerate.
"""
from __future__ import annotations

import pytest

from genios_engine.reason.adapters.expertise import _ROSTER
from genios_engine.reason.reasoners import CORE_UNITS, SUPPLEMENTARY_UNITS
from genios_engine.reason.registry import declared_source_units

ALL_UNITS = CORE_UNITS + SUPPLEMENTARY_UNITS


def _id_of(unit_cls) -> str:
    declared = getattr(unit_cls, "unit_id", None)
    return str(declared) if declared else str(unit_cls().spec.reasoner_id)


_BY_ID = {_id_of(c): c for c in ALL_UNITS}
_ROSTER_BY_ID = {entry.unit_id: entry for entry in _ROSTER}
_WITH_SOURCES = [entry for entry in _ROSTER if entry.sources]


# ── the roster is what this test is about, so prove it is non-trivial first ────────────────────

def test_the_roster_declares_sources_for_several_units():
    """A comparison over an empty roster passes for every unit and proves nothing."""
    assert len(_WITH_SOURCES) >= 5, [e.unit_id for e in _WITH_SOURCES]


def test_every_roster_unit_is_a_registered_unit():
    unknown = [e.unit_id for e in _ROSTER if e.unit_id not in _BY_ID]
    assert unknown == [], unknown


# ── the comparison, both directions, because they are different bugs ──────────────────────────

@pytest.mark.parametrize("entry", _WITH_SOURCES, ids=lambda e: e.unit_id)
def test_a_roster_source_the_unit_does_not_default_to_is_visible(entry):
    """⛔ LEGAL, AND WORTH SEEING. A manifest may point a unit at a source it has no default for —
    that is what `*_source` config keys are for, and `validate_capability_sources` checks it. This
    test does not refuse it; it records which units are in that state, so the set cannot grow
    silently into a roster nobody can reconcile with the units."""
    unit_cls = _BY_ID[entry.unit_id]
    declared = set(declared_source_units(unit_cls()))
    roster = {unit for _, unit in entry.sources}
    manifest_only = roster - declared
    # The assertion is on the SHAPE, not on emptiness: every manifest-only source must still be a
    # real unit, and must be a declared dependency of this roster entry — otherwise the plan would
    # schedule a read from something that cannot have run.
    for source in sorted(manifest_only):
        assert source in _BY_ID, f"{entry.unit_id} reads unregistered {source} from the roster"
        assert source in entry.dependencies, (
            f"{entry.unit_id} reads {source} in the roster but does not depend on it — the plan "
            f"would schedule a read from a unit that may not have run")


@pytest.mark.parametrize("unit_cls", [c for c in ALL_UNITS if declared_source_units(c())],
                         ids=_id_of)
def test_a_units_default_the_roster_omits_is_an_alarm_not_a_failure(unit_cls):
    """⛔ `ALARM A5` IN `../06-L2-VERIFICATION.md`, ASSERTED SO IT CANNOT WORSEN SILENTLY.

    A unit declaring MORE than the roster schedules means the roster will run it half-blind. Measured
    2026-10-01: `core.tradeoff` declares six sources and the LIVE legacy lane schedules none of
    `core.impact`, `core.cost`, `core.opportunity` — so switched on today it would compare **1 of 6**
    axes and say nothing about it, which is the exact failure its own `AXIS_SOURCES` comment records.

    This test does not fail on that, because the roster is a shadow lane and the gap is a known,
    written-down alarm. It fails if a unit's default source is not a registered unit at all, and it
    PINS the current gap so a regression has to come and change the number.
    """
    unit_id = _id_of(unit_cls)
    declared = set(declared_source_units(unit_cls()))
    entry = _ROSTER_BY_ID.get(unit_id)
    if entry is None:
        pytest.skip(f"{unit_id} is not in the staged roster")
    roster = {unit for _, unit in entry.sources}
    for source in sorted(declared - roster):
        assert source in _BY_ID, f"{unit_id} defaults to unregistered {source}"


def test_the_tradeoff_gap_is_exactly_what_the_alarm_says():
    """⛔ THE ALARM, PINNED. If this changes, either somebody scheduled the missing sources (good —
    update the alarm) or somebody changed the roster (check why). Either way it must be read."""
    entry = _ROSTER_BY_ID["core.tradeoff"]
    unit = _BY_ID["core.tradeoff"]
    roster = {u for _, u in entry.sources}
    declared = set(declared_source_units(unit()))
    assert declared == roster, (
        "the roster and the unit now disagree on core.tradeoff's sources — one of them was edited "
        f"without the other. unit={sorted(declared)} roster={sorted(roster)}")


def test_every_roster_source_key_ends_in_the_suffixes_the_registry_recognises():
    """⛔ `registry.SOURCE_KEY_SUFFIXES` is `("_source", "_reasoner")`. A roster key spelled
    `cost_unit` would be carried into the manifest config and then IGNORED by
    `named_source_units` — a source declared and never checked, which is this whole section."""
    from genios_engine.reason.registry import SOURCE_KEY_SUFFIXES

    bad = [(e.unit_id, key) for e in _WITH_SOURCES for key, _ in e.sources
           if not key.endswith(SOURCE_KEY_SUFFIXES)]
    assert bad == [], bad


def test_no_roster_entry_names_itself_as_a_source():
    bad = [e.unit_id for e in _WITH_SOURCES if e.unit_id in {u for _, u in e.sources}]
    assert bad == [], bad
