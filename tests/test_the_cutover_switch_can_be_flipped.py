"""L3-19 · the cards-from-situations lane was built, tested, green — and unreachable.

⛔ THE DEFECT. `deliver/card_source.FEATURE` named the activation `"cards_from_situations"` as a
string literal. `platform/l4_activation.L4_FEATURES` — the closed set `require_feature` validates
against — did not contain it. So:

  * `require_feature("cards_from_situations")` RAISED, so no tenant could ever be switched on;
  * `deliver/pipeline._situation_lane` was therefore False on every pass in production, and
    `out["cards_lane"]` read `"signal"` permanently, for every tenant, whatever anyone did.

⛔ **THE BLAST RADIUS TODAY IS THE LABEL, NOT LOST CARDS — stated precisely because overclaiming
it would be its own defect.** `tally_source` runs the collapse measurement on every sweep
*regardless* of the flag, so `cards_from_situation` / `cards_uninterpreted` / `cards_from_signal`
were always being counted. And card ROUTING is deliberately not switched on the flag yet: L2-7's
criterion 5 requires both paths to be counted on one sweep before either is retired.

What was broken is the SWITCH ITSELF. The moment the routing is wired — which is the next step, and
the only thing the comparison is waiting for — it would have hit a `ValueError` on a name the
validator refuses, and the feature would have had to be registered then, under deadline, instead of
now. That is "built and never switched on" arriving through the ONE DOOR `l4_activation` exists to
hold.
Its own docstring names the failure it was guarding against — *"a row written under `bundel` that
reads as an activated tenant and narrates nothing"* — and the mirror image went unnoticed: a READER
looking for a name the WRITER refuses. A closed set checked in one direction is half a guard.

⛔ AND A SECOND COPY HAD ALREADY DRIFTED. `intelligence_onboarding.L4_DEFAULT_FEATURES` was five
literal strings whose comment claimed they were "Layer 4's features in wave order
(`l4_activation.PRECONDITIONS`)". `situation_reasoner` had joined `L4_FEATURES` and `PRECONDITIONS`
and never joined that list, so `make_tenant_live` silently never switched on the Context Reasoner.
It is now derived, with the exclusions declared and reasoned.
"""
from __future__ import annotations

import ast
from pathlib import Path

from genios_engine.deliver.card_source import FEATURE, cards_from_situations
from genios_engine.platform import l4_activation as l4
from genios_engine.platform.intelligence_onboarding import L4_DEFAULT_FEATURES, NOT_DEFAULT_ON

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "genios_engine"


def _module_feature_constants() -> dict[str, str]:
    """Every module-level `FEATURE*` string constant in the engine → `{value: where}`.

    ⛔ READ FROM THE AST at module scope only, so a local variable or a mention inside a docstring
    cannot enter the inventory — the same discipline as `reason/situation_binding`.
    """
    found: dict[str, str] = {}
    for path in ENGINE.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):                       # pragma: no cover
            continue
        for node in tree.body:                               # module scope ONLY
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if (isinstance(target, ast.Name) and target.id.startswith("FEATURE")
                        and isinstance(node.value, ast.Constant)
                        and isinstance(node.value.value, str)):
                    found[node.value.value] = f"{path.relative_to(ROOT)}::{target.id}"
    return found


# =================================================================================================
# 1 · ⛔ THE GUARD THAT WOULD HAVE CAUGHT IT — both directions
# =================================================================================================

def test_every_feature_constant_in_the_engine_is_in_the_closed_set():
    """⛔ THE DIRECTION THAT WAS MISSING. A module that names an activation the validator refuses
    is a module whose whole feature is dead, and nothing about it looks wrong: its own tests pass,
    its flag reads False, and False is a legal answer."""
    orphans = {value: where for value, where in _module_feature_constants().items()
               if value not in l4.L4_FEATURES}
    assert orphans == {}, (
        f"{len(orphans)} feature constant(s) name an activation `require_feature` will REFUSE: "
        f"{orphans}. Either register the name in L4_FEATURES with a wave, preconditions and an "
        "effect, or the code gating on it can never run for any tenant.")


def test_every_registered_feature_is_defined_as_a_constant_somewhere():
    """The other direction: a name in the closed set that no module spells is a switch with
    nothing behind it — an operator can turn it on and nothing changes."""
    defined = set(_module_feature_constants())
    missing = sorted(set(l4.L4_FEATURES) - defined)
    assert missing == [], f"{missing} are registered but no module defines them as a constant"


def test_the_cutover_feature_is_spelt_exactly_once():
    """⛔ TWO SPELLINGS OF ONE NAME IS HOW THE DEFECT HAPPENED. `card_source.FEATURE` is now the
    imported constant, not a second literal — so the two can no longer disagree.

    ⛔ AND THIS ASSERTION IS ABOUT THE ASSIGNMENT, NOT ABOUT TEXT. Its first draft counted the
    string anywhere in the module and went red on correct code, because `__all__` exports a
    FUNCTION called `cards_from_situations` whose name is the same word. That is the tenth
    occurrence of one family in this project and it is always the same shape: an assertion about
    text near a thing rather than about the thing. What matters is the SHAPE of the binding — a
    `Name` that resolves to the closed set, never a `Constant` that can drift away from it.
    """
    tree = ast.parse((ENGINE / "deliver" / "card_source.py").read_text(encoding="utf-8"))
    bindings = [node.value for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "FEATURE" for t in node.targets)]
    assert len(bindings) == 1, "card_source must bind FEATURE exactly once"
    assert isinstance(bindings[0], ast.Name), (
        "deliver/card_source binds FEATURE to a literal again; import "
        "FEATURE_CARDS_FROM_SITUATIONS from platform.l4_activation so there is one spelling")
    assert bindings[0].id == "FEATURE_CARDS_FROM_SITUATIONS"
    assert FEATURE is l4.FEATURE_CARDS_FROM_SITUATIONS


# =================================================================================================
# 2 · ⛔ THE SWITCH ACTUALLY WORKS NOW — behavioural, not textual
# =================================================================================================

def test_require_feature_accepts_the_cutover_name():
    """The assertion that was false before this step. It raised."""
    assert l4.require_feature(FEATURE) == "cards_from_situations"


def test_the_lane_turns_on_when_the_tenant_is_activated_and_not_before():
    """End to end through the real predicate, so a rename of the constant that missed one side
    fails here rather than in production silence."""
    assert cards_from_situations(activated=frozenset({FEATURE})) is True
    assert cards_from_situations(activated=frozenset({"bundle"})) is False
    assert cards_from_situations(activated=frozenset()) is False
    assert cards_from_situations(activated=None) is False


def test_an_unregistered_name_is_still_refused():
    """The guard this module was always right about, kept: a typo must raise, not write a row."""
    for bad in ("cards_from_situation", "bundel", ""):
        try:
            l4.require_feature(bad)
        except ValueError:
            continue
        raise AssertionError(f"require_feature accepted {bad!r}")


# =================================================================================================
# 3 · ⛔ REGISTRATION IS TOTAL — a feature with no wave, precondition or effect is half-registered
# =================================================================================================

def test_every_feature_has_a_wave_a_precondition_row_and_an_effect():
    """⛔ FOUR TABLES, ONE VOCABULARY. A feature present in the set and absent from `EFFECTS`
    reaches an operator's console as a switch with no explanation, which is what
    `EFFECTS`' own comment says must never happen: *"an operator who can see a switch is on and
    cannot see what it turned on will assume it turned on everything."*"""
    for feature in l4.L4_FEATURES:
        assert feature in l4.FEATURE_WAVES, f"{feature} has no wave"
        assert feature in l4.PRECONDITIONS, f"{feature} has no precondition row"
        assert feature in l4.EFFECTS, f"{feature} has no effect sentence"
        assert len(l4.EFFECTS[feature]) > 80, f"{feature}'s effect says nothing useful"
    for table, name in ((l4.FEATURE_WAVES, "FEATURE_WAVES"), (l4.PRECONDITIONS, "PRECONDITIONS"),
                        (l4.EFFECTS, "EFFECTS")):
        extra = sorted(set(table) - set(l4.L4_FEATURES))
        assert extra == [], f"{name} describes unregistered features {extra}"


def test_the_cutovers_cross_layer_precondition_is_declared():
    """⛔ MEASURED IN L3-13: only the compiled lane writes `signals.situation_id`, and it needs a
    live L3 domain. Without this row an operator switches the lane on for a domain-less tenant,
    every card lands in the uninterpreted bucket, and the console says `live`."""
    assert l4.CROSS_LAYER_PRECONDITIONS[FEATURE] == ("l3_domain",)
    assert "l3_domain" in l4.CROSS_LAYER_EFFECTS


# =================================================================================================
# 4 · ⛔ THE DEFAULTS ARE DERIVED, AND THE EXCLUSIONS CARRY REASONS
# =================================================================================================

def test_the_onboarding_defaults_are_derived_from_the_closed_set():
    """⛔ THE SECOND COPY, REMOVED. It had already drifted — `situation_reasoner` never joined it,
    so `make_tenant_live` silently never switched on the Context Reasoner."""
    assert L4_DEFAULT_FEATURES == tuple(f for f in l4.L4_FEATURES if f not in NOT_DEFAULT_ON)
    src = (ENGINE / "platform" / "intelligence_onboarding.py").read_text(encoding="utf-8")
    assert '("roster_v2", "ranking_v2", "bundle", "critique", "brief")' not in src, (
        "the literal tuple is back; derive it from L4_FEATURES so a new feature cannot be "
        "forgotten in silence")


def test_provisioning_behaviour_is_unchanged_by_the_derivation():
    """⛔ THE POINT OF THE EXCLUSION LIST. Deriving the defaults must not quietly switch on a
    model-cost feature or a cutover for every newly provisioned tenant."""
    assert L4_DEFAULT_FEATURES == ("roster_v2", "ranking_v2", "bundle", "critique", "brief")


def test_every_excluded_feature_is_registered_and_says_why():
    """An exclusion for a name that is not a feature protects nothing, and one without a reason
    gets deleted by the next reader who wants a simpler default."""
    for feature, why in NOT_DEFAULT_ON.items():
        assert feature in l4.L4_FEATURES, f"{feature} is excluded but is not a feature"
        assert len(why) > 100, f"{feature}'s exclusion gives no real reason"
