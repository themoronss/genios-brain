"""L2-8 · the cutover, enumerated — and it is not three flips, it is seven.

⛔ **THE STEP FILE SAYS THREE, AND SAYS WHY THAT MATTERS:** *"any one alone leaves the system in a
state that looks working and is not."* It was written before L2-0…L2-7 ran, and four of those
steps each left a switch behind **deliberately**, each with the same discipline: declared,
evidenced, and **not armed until somebody had the number**.

Nothing enumerated them. Four switches sitting in four findings files is four switches somebody
rediscovers one at a time — the *"prose stale, code right"* drift this repository has caught five
times, and the same gap L2-6 found when three completed steps had deferred work onto L2-5 with
nothing collecting it.

**So the cutover is a table with a row per switch, checked at import**, exactly as
`SITUATION_STAGES`, `DARK_DOMAINS`, `ADMISSION_REASONS` and `CHECKS` are.

⛔ **AND THE PARITY GATE IS A NUMBER WRITTEN DOWN BEFORE THE RUN.** §3: *"Written down BEFORE the
run, not chosen after seeing it. A threshold picked post-hoc is not a gate."* The shadow pass has
been counting for months and nobody has read its tallies; the moment somebody does, a number
chosen afterwards will be a number chosen to pass.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# =================================================================================================
# U2 · every switch, with its owner, its mover and what it breaks alone
# =================================================================================================

def test_every_switch_names_the_step_that_left_it():
    from genios_engine.reason.cutover import SWITCHES

    for name, switch in SWITCHES.items():
        assert switch.owner, f"{name} has no owning step"
        assert switch.flips, f"{name} does not say what to change"
        assert switch.alone, f"{name} does not say what it breaks if flipped alone"


def test_the_seven_switches_are_the_ones_the_layer_actually_left():
    """⛔ Three from `shadow_compile`'s own contract, four from L2-0…L2-7."""
    from genios_engine.reason.cutover import SWITCHES

    assert set(SWITCHES) == {
        "publisher", "require_admission", "execution_mode",     # the step file's three
        "fundraising_route",                                    # L2-4
        "observing_laws",                                       # L2-2
        "cards_from_situations",                                # L2-7
        "situation_reasoner",                                   # L2-5
    }


def test_every_switch_is_still_off_and_a_test_says_which():
    """⛔ **THE GUARD THAT MAKES THIS TABLE WORTH HAVING.** A switch that flips without its row
    being updated is a cutover nobody recorded — and `live_lane` records what an unrecorded flip
    costs: *"the one configuration in which the stated safety property is false is the one a global
    flag creates."*"""
    from genios_engine.reason.cutover import SWITCHES, is_armed

    for name, switch in SWITCHES.items():
        assert is_armed(name) is switch.armed, (
            f"{name} says armed={switch.armed} and the code disagrees — update the row WITH the "
            f"flip, or the cutover is happening and nothing says so")


def test_nothing_is_armed_yet():
    from genios_engine.reason.cutover import SWITCHES

    assert not [n for n, s in SWITCHES.items() if s.armed], (
        "a switch was armed before the parity gate was measured")


def test_a_switch_that_needs_a_measurement_names_which_one():
    """*"A threshold picked post-hoc is not a gate"* — and a switch with no stated precondition is
    a switch somebody flips because it seemed fine."""
    from genios_engine.reason.cutover import SWITCHES

    for name, switch in SWITCHES.items():
        assert switch.precondition, f"{name} can be flipped for no stated reason"


def test_the_order_is_declared_because_one_alone_is_the_failure():
    """§2: *"any one alone leaves the system in a state that looks working and is not."*"""
    from genios_engine.reason.cutover import CUTOVER_ORDER, SWITCHES

    assert set(CUTOVER_ORDER) == set(SWITCHES)
    assert CUTOVER_ORDER.index("require_admission") < CUTOVER_ORDER.index("execution_mode"), (
        "publishing before admission is enforced would let unreviewed doctrine carry authority")


# =================================================================================================
# U1 · the parity gate — a number, fixed before the run
# =================================================================================================

def test_the_parity_gate_is_a_number_and_not_a_sentence():
    from genios_engine.reason.cutover import PARITY_GATE

    assert PARITY_GATE
    for name, rule in PARITY_GATE.items():
        assert isinstance(rule.threshold, int) and not isinstance(rule.threshold, bool), (
            f"{name}'s threshold is not an integer — V-8, and a gate you cannot compare is prose")
        assert rule.reading, f"{name} does not say which tally it reads"
        assert rule.why, f"{name} is a number with no reason, which is a number somebody moves"


def test_the_gate_was_written_before_the_measurement_exists():
    """⛔ The whole point. The shadow pass has been counting for months and nobody has read it;
    a number chosen after the first read is a number chosen to pass."""
    from genios_engine.reason.cutover import PARITY_GATE, PARITY_MEASURED_AT

    assert PARITY_MEASURED_AT is None, (
        "the parity gate now has a measurement beside it — check the thresholds were not moved "
        "to fit it")
    assert len(PARITY_GATE) >= 3


def test_the_gate_reads_tallies_the_sweep_actually_emits():
    """⛔ A gate that reads a key nothing writes passes forever. That is the defect L2-0 spent a
    step on, pointed at the cutover itself."""
    import inspect
    import re

    from genios_engine.reason import domain_shadow
    from genios_engine.reason.cutover import PARITY_GATE

    src = inspect.getsource(domain_shadow.shadow_compile)
    emitted = set(re.findall(r"counts\[[\"']([a-z0-9_:]+)[\"']\]", src))
    emitted |= set(re.findall(r'counts\.get\([\"\']([a-z0-9_:]+)[\"\']', src))
    for name, rule in PARITY_GATE.items():
        assert rule.reading in emitted, (
            f"{name} reads `{rule.reading}`, which the sweep never writes — the gate would pass "
            f"on a tally that does not exist")


def test_a_gate_can_be_evaluated_against_a_tally_dict():
    from genios_engine.reason.cutover import evaluate_parity

    passing = {"compiled": 200, "reasoned": 200, "error": 0, "persist_error": 0,
               "no_route": 0, "reasoner_failed": 0}
    verdict = evaluate_parity(passing)
    assert verdict.passed is True and verdict.failures == ()

    failing = dict(passing, error=99)
    assert evaluate_parity(failing).passed is False
    assert any("error" in f for f in evaluate_parity(failing).failures)


def test_an_absent_tally_fails_the_gate_rather_than_passing_it():
    """⛔ *"`None` is not a low number — it is nobody having measured."* A missing tally must not
    read as a clean run."""
    from genios_engine.reason.cutover import evaluate_parity

    verdict = evaluate_parity({})
    assert verdict.passed is False
    assert all("not measured" in f or "missing" in f for f in verdict.failures), verdict.failures
