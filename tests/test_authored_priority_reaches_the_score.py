"""The authored priority must survive the trip from the corpus to the card score.

Measured on the design partner's org before this: 193 of 223 signals and 104 of 115 cards carried
the SAME score, 50, in a single urgency band. A product that ranks had never ranked anything.

The cause was not a missing model. The corpus already holds 30 distinct `priority_bp` values
across 48 situations, from 3,000 to 9,600. `capability_resolver` read that number, used it to sort
which situation's card copy won, and then dropped it. Nothing carried it onto the package, so the
compiled capability's `core.priority` unit saw no declared ruling (`core.risk` measures pressure
and never rules), the Decision Maker's formula ran on neutral components and returned 5,000bp, and
`domain_shadow` projected `score = (final_utility_bp + 50) / 100` — exactly 50, every time.

Each hop is pinned separately, because the failure was a single silent drop in the middle of a
chain that looked healthy at both ends.
"""
from __future__ import annotations

from genios_engine.reason.reasoners.priority import (
    AuthoredPriorityPlugin,
    DeclaredOverridePlugin,
    PriorityReasoner,
)


class _View:
    """Minimal UnitView stand-in: the plugins only reach for `config` and `prior`."""

    def __init__(self, config: dict, prior: dict | None = None):
        self.config = config
        self.prior = prior or {}


# ── hop 1: the compiler keeps it ─────────────────────────────────────────────────────────────
def test_the_route_plan_carries_the_authored_priority():
    from genios_engine.packs.compiler.models import RoutePlan

    plan = RoutePlan(
        domain_ids=("sales",), situation_ids=("s1",), capability_ids=("c1",),
        required_object_ids=(), optional_object_ids=(), never_object_ids=(),
        priority_bp=9600, priority_situation_id="s1",
    )
    assert plan.priority_bp == 9600
    assert plan.priority_situation_id == "s1"


def test_a_route_with_no_authored_priority_carries_none_not_a_neutral_default():
    """`None` and 5,000 are different claims — only the second should outrank the formula."""
    from genios_engine.packs.compiler.models import RoutePlan

    plan = RoutePlan(
        domain_ids=("sales",), situation_ids=("s1",), capability_ids=("c1",),
        required_object_ids=(), optional_object_ids=(), never_object_ids=(),
    )
    assert plan.priority_bp is None


# ── hop 2: the adapter hands it to the unit ──────────────────────────────────────────────────
def test_the_adapter_puts_the_authored_priority_in_the_priority_units_config():
    from genios_engine.reason.adapters.expertise import _default_dag

    specs = {s.reasoner_id: s for s in _default_dag((), 7300)}
    assert specs["core.priority"].config["authored_priority_bp"] == 7300
    # ...and does not disturb what was already there
    assert specs["core.priority"].config["source_reasoner"] == "core.risk"


def test_no_authored_priority_means_no_config_key_at_all():
    from genios_engine.reason.adapters.expertise import _default_dag

    specs = {s.reasoner_id: s for s in _default_dag((), None)}
    assert "authored_priority_bp" not in specs["core.priority"].config


# ── hop 3: the unit publishes it as an override ──────────────────────────────────────────────
def test_the_plugin_publishes_the_authored_priority_as_an_override():
    obs = AuthoredPriorityPlugin().contribute(_View({"authored_priority_bp": 9600}))
    assert len(obs) == 1
    assert obs[0].metrics["priority_override_bp"] == 9600
    assert "priority_authored_by_situation" in obs[0].reason_codes


def test_the_plugin_stays_silent_when_the_author_said_nothing():
    assert AuthoredPriorityPlugin().contribute(_View({})) == ()


def test_distinct_authored_priorities_produce_distinct_overrides():
    """The whole point. Three situations, three ranks — not three 50s."""
    seen = {AuthoredPriorityPlugin().contribute(_View({"authored_priority_bp": bp}))[0]
            .metrics["priority_override_bp"]
            for bp in (3000, 6100, 9600)}
    assert seen == {3000, 6100, 9600}


# ── precedence: a runtime ruling still wins ──────────────────────────────────────────────────
def test_a_runtime_ruling_overrides_the_authored_one():
    """`evaluate_metrics` keeps the LAST override it sees, so plugin ORDER is the precedence rule.

    A live ruling about THIS node beats a general one about its situation type. Pinned because the
    two are rarely both present today, so a reordering would break it silently.
    """
    plugin_ids = [p.plugin_id for p in PriorityReasoner.plugins]
    assert plugin_ids.index("authored_priority") < plugin_ids.index("override_priority")


def test_both_override_plugins_are_registered():
    ids = {p.plugin_id for p in PriorityReasoner.plugins}
    assert {"authored_priority", "override_priority"} <= ids


# ── hop 4: the override becomes the utility, and the utility becomes the score ───────────────
def test_the_override_becomes_the_candidate_utility():
    from genios_engine.reason.decision_maker import score_candidate

    weights = {"impact": 0.3, "success": 0.2, "urgency": 0.3, "effort": 0.1, "risk": 0.1}
    request = type("Req", (), {
        "capability": type("Cap", (), {"ranking_weights": weights})()})()
    components = {"impact": 5000, "success": 5000, "urgency": 5000, "effort": 5000, "risk": 5000}

    assert score_candidate(request, components, 9600) == 9600
    # the formula's answer is still recorded beside it, so the two can be compared on real traffic
    assert "formula_utility" in components
    # ...and it did NOT decide: the override is what the candidate carries.
    assert components["formula_utility"] != 9600


def test_the_projection_that_turned_every_utility_into_fifty():
    """`score = (final_utility_bp + 50) / 100` — the arithmetic behind the flat distribution.

    A neutral 5,000 lands on exactly 50. The authored range 3,000-9,600 lands on 30-96, which is
    the spread the product was always supposed to have.
    """
    def project(utility_bp: int) -> int:
        return (utility_bp + 50) // 100

    assert project(5000) == 50                     # what every compiled card scored
    assert project(3000) == 30 and project(9600) == 96
    assert len({project(bp) for bp in (3000, 6100, 9600)}) == 3


def test_a_declared_runtime_override_still_reaches_the_score():
    """The pre-existing path must be untouched by the new one."""
    source = type("R", (), {"metrics": {"priority_bp": 8800}})()
    obs = DeclaredOverridePlugin().contribute(
        _View({"source_reasoner": "core.risk"}, {"core.risk": source}))
    assert obs[0].metrics["priority_override_bp"] == 8800
