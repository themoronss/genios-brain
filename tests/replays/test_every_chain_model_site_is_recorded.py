"""STEP-01 · a new model site cannot run unrecorded in a golden case.

    pytest tests/replays/test_every_chain_model_site_is_recorded.py -q

`tests/replays/model_sites.CHAIN_SITES` says, for every module that invokes a model, whether a
golden run hands it the recorded model (and through which door) or why the chain cannot reach
it. It is held equal to `_SITES`, the metering gate's register, in both directions — so the day a
site is added to the engine, this fails until somebody decides how a golden case treats it.
"""
from __future__ import annotations

import importlib

from tests.replays.harness import SITE_MARKERS
from tests.replays.model_sites import CHAIN_SITES, DOORS, KINDS, recorded_sites
from tests.test_every_llm_call_site_is_metered import _SITES

_DOOR_MODULES = {"routes": "genios_engine.api.routes",
                 "wiring": "genios_engine.platform.wiring",
                 "llm_decision_maker": "genios_engine.reason.llm_decision_maker",
                 "llm_sites": "genios_engine.reason.llm_sites"}


def test_the_register_is_the_metering_register():
    missing = sorted(set(_SITES) - set(CHAIN_SITES))
    stale = sorted(set(CHAIN_SITES) - set(_SITES))
    assert not missing, (
        f"model sites with no golden-run decision: {missing}. Add each to "
        "tests/replays/model_sites.CHAIN_SITES — recorded (and through which door) or off (and "
        "why the chain cannot reach it)")
    assert not stale, f"CHAIN_SITES names modules that no longer call a model: {stale}"


def test_every_entry_is_a_known_kind_with_its_door_or_its_reason():
    for module, (kind, how, sites) in CHAIN_SITES.items():
        assert kind in KINDS, f"{module}: kind {kind!r}"
        if kind == "recorded":
            assert how in DOORS, f"{module}: door {how!r} is not one of {sorted(DOORS)}"
            assert sites, f"{module}: a recorded site names the prompts it writes"
        else:
            assert len(how.strip()) >= 20 and not sites, (
                f"{module}: an {kind} site states why, in a sentence, and names no prompts")


def test_every_recorded_site_is_recognised_by_its_prompt():
    """The ideal reader answers by site, and the board counts calls by site — a recorded site
    whose prompt nobody can recognise would be answered as `unknown`."""
    marked = {site for site, _module, _marker in SITE_MARKERS}
    unmarked = sorted(recorded_sites() - marked)
    assert not unmarked, f"recorded sites with no prompt marker in harness.SITE_MARKERS: {unmarked}"


def test_every_door_is_used_and_exists():
    used = {how for kind, how, _ in CHAIN_SITES.values() if kind == "recorded"}
    assert used == set(DOORS), f"doors no recorded site uses: {sorted(set(DOORS) - used)}"
    for door in DOORS:
        module_alias, attribute = door.split(".", 1)
        module = importlib.import_module(_DOOR_MODULES[module_alias])
        assert hasattr(module, attribute), f"door {door}: {module.__name__} has no {attribute}"


def test_the_junk_filter_is_recorded():
    """The sharpest case: with no key the junk filter never runs, so a mail production junked
    would pass a golden case that left it off."""
    kind, door, sites = CHAIN_SITES["capture/gate/relevance.py"]
    assert kind == "recorded" and "junk_gate" in sites
