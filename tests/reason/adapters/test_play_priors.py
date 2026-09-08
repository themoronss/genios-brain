"""K1 · the three ranking components that used to be constant, and the maps that carry the measured half.

The defect is measured rather than described. Before `adapters/play_priors`, every play the
compiled lane produced was constructed without `impact_bp`, `effort_bp` or `risk_bp`, so all three
took `PlayDefinition`'s 5,000 defaults — 4,500 of the formula's 10,000 basis points of weight
resting on numbers identical across every candidate on every situation. `success_probability_bp`
was the same wherever the tenant had no measured outcomes, which is every tenant on day one.

Two halves have to hold for the formula to actually decide, and this file pins both:

* the PRIORS spread — a play's standing components are read off what its author declared, so two
  different playbooks get two different numbers;
* the DELTAS reach a unit that reads them — the authored `{play_id: bp}` maps are the ONLY path
  from a measured unit output to the score, and a map authored under a key no unit reads is a
  silent no-op that looks exactly like a working one.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from genios_engine.reason.adapters.play_priors import (
    EFFORT_DELTA_KEY,
    IMPACT_DELTA_KEY,
    NEUTRAL_BP,
    RISK_REDUCTION_KEY,
    SUCCESS_DELTA_KEY,
    derive_play_priors,
    play_deltas,
)

pytestmark = pytest.mark.unit

#: A thoroughly authored playbook: reviewed, observable, with declared outcomes and real breadth.
RICH = {
    "identity": {"status": "stable"},
    "steps": [
        {"order": 1, "actor": "human", "done_when": "a"},
        {"order": 2, "actor": "system", "done_when": "b"},
        {"order": 3, "actor": "agent", "done_when": "c"},
    ],
    "outcomes": ["revenue retained"],
    "metrics": ["churn rate"],
    "objects_used": ["a", "b", "c"],
    "variants": ["enterprise"],
    "when_to_use": {"conditions": ["x"], "signals": ["y"], "do_not_use_when": ["z"]},
    "limits": ["one"],
    "failure_modes": ["breaks"],
}

#: A thin one: a draft, one unexplained human step, nothing declared about worth or downside.
THIN = {
    "identity": {"status": "draft"},
    "steps": [{"order": 1, "name": "do the thing"}],
}


def test_two_differently_authored_playbooks_get_different_components():
    """The whole point. Identical numbers here is the defect returning."""
    rich = derive_play_priors(RICH, situation_fit=False)
    thin = derive_play_priors(THIN, situation_fit=False)

    assert rich.impact_bp != thin.impact_bp
    assert rich.effort_bp != thin.effort_bp
    assert rich.risk_bp != thin.risk_bp
    assert rich.success_bp != thin.success_bp


def test_the_thin_playbook_declares_nothing_and_lands_on_the_neutral_impact():
    """A play nobody described the worth of is UNMEASURED, not worthless — the base is the
    midpoint and the receipt says which terms fired."""
    priors = derive_play_priors(THIN, situation_fit=False)

    assert priors.impact_bp == NEUTRAL_BP
    assert priors.receipt["impact"]["declares_outcomes"] is False
    assert priors.receipt["impact"]["objects_used"] == 0


def test_situation_fit_raises_impact_and_says_so_in_the_receipt():
    without = derive_play_priors(RICH, situation_fit=False)
    with_fit = derive_play_priors(RICH, situation_fit=True)

    assert with_fit.impact_bp > without.impact_bp
    assert with_fit.receipt["impact"]["situation_fit"] is True
    assert without.receipt["impact"]["situation_fit_bp"] == 0


def test_a_human_step_costs_more_than_an_automated_one():
    """Effort's whole reason for existing: nine automated steps and nine human ones are the same
    step count and not the same afternoon."""
    human = derive_play_priors(
        {"steps": [{"actor": "human"}, {"actor": "human"}]}, situation_fit=False)
    system = derive_play_priors(
        {"steps": [{"actor": "system"}, {"actor": "system"}]}, situation_fit=False)

    assert human.effort_bp > system.effort_bp


def test_an_unstated_actor_is_priced_as_human_not_as_free():
    """897 of the corpus's 910 steps declare an actor, so a blank is an omission — and pricing an
    omission at zero would make an under-specified playbook look cheap."""
    unstated = derive_play_priors({"steps": [{"name": "x"}]}, situation_fit=False)
    human = derive_play_priors({"steps": [{"actor": "human"}]}, situation_fit=False)

    assert unstated.effort_bp == human.effort_bp


def test_a_draft_is_riskier_and_less_likely_to_succeed_than_a_reviewed_play():
    draft = derive_play_priors({**RICH, "identity": {"status": "draft"}}, situation_fit=False)
    stable = derive_play_priors({**RICH, "identity": {"status": "stable"}}, situation_fit=False)

    assert draft.risk_bp > stable.risk_bp
    assert draft.success_bp < stable.success_bp


def test_an_unrecognised_status_is_treated_as_a_draft_not_as_reviewed():
    """Guessing the other way ships unreviewed advice as safe."""
    unknown = derive_play_priors({**RICH, "identity": {"status": "wat"}}, situation_fit=False)
    draft = derive_play_priors({**RICH, "identity": {"status": "draft"}}, situation_fit=False)

    assert unknown.risk_bp == draft.risk_bp
    assert unknown.receipt["risk"]["status_recognised"] is False


def test_risk_stays_under_its_ceiling_because_every_compiled_play_is_read_only():
    """A review artifact must never score as dangerously as an executed action."""
    catastrophic = derive_play_priors({
        "identity": {"status": "draft"},
        "steps": [{"actor": "human"}],
        "failure_modes": [f"f{i}" for i in range(20)],
        "limits": [f"l{i}" for i in range(20)],
        "when_to_use": {"do_not_use_when": [f"d{i}" for i in range(20)]},
    }, situation_fit=False)

    assert catastrophic.risk_bp <= catastrophic.receipt["risk"]["ceiling_bp"]
    assert catastrophic.receipt["risk"]["capped"] is True


def test_the_derivation_is_pure_and_reproducible():
    """Load-bearing, not tidy: these numbers reach `CapabilityManifest.version` through the
    manifest's content address, so a derivation that varied would mint a new capability version
    for an unchanged corpus."""
    first = derive_play_priors(RICH, situation_fit=True)
    second = derive_play_priors(dict(RICH), situation_fit=True)

    assert (first.impact_bp, first.effort_bp, first.risk_bp, first.success_bp) == \
           (second.impact_bp, second.effort_bp, second.risk_bp, second.success_bp)
    assert first.receipt == second.receipt


def test_every_term_names_the_field_it_read():
    """Law 6. A component that reached a card without an explanation is a number a reviewer can
    only re-derive by re-running the compiler."""
    receipt = derive_play_priors(RICH, situation_fit=True).receipt

    assert set(receipt) == {"impact", "effort", "risk", "success"}
    assert receipt["effort"]["steps_by_actor"] == {"agent": 1, "human": 1, "system": 1}
    assert receipt["risk"]["failure_modes"] == 1
    assert receipt["success"]["every_step_observable"] is True


# ── the deltas ───────────────────────────────────────────────────────────────────────────────

def test_the_delta_maps_are_sorted_and_cover_every_play():
    """`reasoners/risk.py` documents that adjustment order reaches a result's semantic hash and
    that the manifest is re-sorted on its way through the audit store, so an unsorted map would
    report every replayed run as non-reproducible."""
    deltas = play_deltas({"z_play": RICH, "a_play": THIN, "m_play": RICH})

    for key in (IMPACT_DELTA_KEY, RISK_REDUCTION_KEY, SUCCESS_DELTA_KEY, EFFORT_DELTA_KEY):
        assert list(deltas[key]) == sorted(deltas[key]), f"{key} is not authored in sorted order"
        assert set(deltas[key]) == {"a_play", "m_play", "z_play"}


def test_a_play_that_declared_an_outcome_earns_a_larger_impact_ceiling():
    """Authoring one delta for every play would restore the constant one level up."""
    deltas = play_deltas({"rich": RICH, "thin": THIN})

    assert deltas[IMPACT_DELTA_KEY]["rich"] > deltas[IMPACT_DELTA_KEY]["thin"]
    assert deltas[RISK_REDUCTION_KEY]["rich"] > deltas[RISK_REDUCTION_KEY]["thin"]
    assert deltas[SUCCESS_DELTA_KEY]["rich"] > deltas[SUCCESS_DELTA_KEY]["thin"]


#: Which unit is supposed to read which key. A key authored under a name no unit reads is a silent
#: no-op that looks exactly like a working configuration — which is the precise defect this whole
#: module was written to remove, so the pairing is asserted against the unit sources rather than
#: trusted.
DELTA_CONSUMERS = {
    "impact_unit.py": IMPACT_DELTA_KEY,
    "risk.py": RISK_REDUCTION_KEY,
    "recommendation_unit.py": SUCCESS_DELTA_KEY,
}


@pytest.mark.parametrize("filename,key", sorted(DELTA_CONSUMERS.items()))
def test_each_delta_key_is_actually_read_by_the_unit_that_owns_it(filename, key):
    import genios_engine.reason.reasoners as reasoners_package

    source = (pathlib.Path(reasoners_package.__file__).resolve().parent / filename).read_text()

    assert key in source, (
        f"{filename} does not read {key!r} — authoring that key onto the compiled lane would "
        "ship config nothing consumes, which is indistinguishable from a working one")


def test_the_effort_delta_key_is_not_authored_because_no_unit_reads_it():
    """`packs/capabilities/deal_cooling_v2` authors `play_effort_bp` in `core.cost`'s config and
    NOTHING reads it: `cost_unit` corrects effort by comparing the play's declared `effort_bp`
    against `_step_effort` and has never looked for an authored map. Copying that onto the
    compiled lane would have shipped dead config for every playbook in the corpus.

    `play_deltas` still RETURNS the map — it is derived and available the day a unit grows a
    reader — but `adapters/expertise._DELTA_CONSUMERS` must not wire it to `core.cost`."""
    import genios_engine.reason.reasoners as reasoners_package
    from genios_engine.reason.adapters.expertise import _DELTA_CONSUMERS

    cost_source = (pathlib.Path(reasoners_package.__file__).resolve().parent
                   / "cost_unit.py").read_text()

    assert EFFORT_DELTA_KEY not in cost_source, (
        "cost_unit grew a reader for play_effort_bp — wire it into _DELTA_CONSUMERS")
    assert "core.cost" not in _DELTA_CONSUMERS, (
        "core.cost is wired to a delta key it does not read")


def test_the_compiled_lane_authors_every_delta_key_it_claims_to():
    """The wiring assertion. `_DELTA_CONSUMERS` is what turns a derived map into config a unit can
    see; a refactor that drops it puts every measured unit back to moving no score at all."""
    from genios_engine.reason.adapters.expertise import _DELTA_CONSUMERS

    assert set(_DELTA_CONSUMERS.values()) == {
        IMPACT_DELTA_KEY, RISK_REDUCTION_KEY, SUCCESS_DELTA_KEY}

    tree = ast.parse(pathlib.Path(
        __import__("genios_engine.reason.adapters.expertise", fromlist=["x"]).__file__).read_text())
    called = {node.func.id for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}

    assert "play_deltas" in called, "the roster no longer derives the delta maps"
    assert "derive_play_priors" in called, "the play builder no longer derives the priors"
