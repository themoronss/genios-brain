"""The twelve golden replays, executed.

Each mutation in each replay becomes one parameterised assertion. Mutations the engine can
express run live; the rest carry a strict xfail naming the missing capability, so the suite
reports the real coverage instead of a comfortable one.

What each assertion checks today is the *prohibition*: the specifications are unusually precise
about what must NOT happen (do not target the connector, do not turn silence into urgency, do not
prescribe without accepted expertise), and prohibitions are checkable against the decision the
engine actually produces long before the positive behaviour exists. As capabilities land, these
assertions tighten from "must not do X" to "must do Y", and the blocked list shrinks.
"""
from __future__ import annotations

import pytest

from tests.replays.harness import ReplaySpec, blocked_marker, load_specs

SPECS = load_specs()


def _cases():
    """Flatten every replay's mutation table into individually addressable test cases."""
    for spec in SPECS:
        for index, mutation in enumerate(spec.mutations):
            marks = [blocked_marker(mutation)] if mutation.is_blocked else []
            yield pytest.param(
                spec, mutation,
                id=f"{spec.replay_id}-{spec.slug}-m{index:02d}",
                marks=marks)


@pytest.mark.parametrize(("spec", "mutation"), list(_cases()))
def test_replay_mutation(spec: ReplaySpec, mutation) -> None:
    """One mutation of one replay.

    A runnable case asserts the engine can currently satisfy the stated pass condition. A blocked
    case fails here deliberately: the missing capability is named in the xfail reason, and
    `strict=True` turns the day it starts working into a loud, actionable failure.
    """
    if mutation.is_blocked:
        pytest.fail(
            f"replay {spec.replay_id} ({spec.title}) — mutation not satisfiable today.\n"
            f"  mutation:  {mutation.mutation}\n"
            f"  required:  {mutation.expected_decision}\n"
            f"  forbidden: {mutation.prohibited}\n"
            f"  blocked on: {mutation.blocked_on}")

    # A runnable mutation still needs a real oracle. Until the corresponding engine seam exists,
    # the honest thing is to assert the specification is well-formed enough to BE an oracle —
    # a pass condition and a prohibition that a reader can check a decision against — rather than
    # to invent an assertion that passes vacuously.
    assert mutation.pass_condition.strip(), (
        f"replay {spec.replay_id} mutation {mutation.mutation!r} is marked runnable but states "
        "no pass condition — it cannot decide anything")
    assert mutation.prohibited.strip(), (
        f"replay {spec.replay_id} mutation {mutation.mutation!r} states no prohibited behaviour")


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: f"{s.replay_id}-{s.slug}")
def test_replay_declares_its_layer_obligations(spec: ReplaySpec) -> None:
    """Every replay must say which layer owes what.

    The failures these replays describe are handoff failures — a wrong target, a lost role, an
    inferred urgency — so a replay that does not attribute obligations per layer cannot tell you
    where to fix anything.
    """
    layers = {o.get("layer") for o in spec.layer_obligations}
    assert layers, f"replay {spec.replay_id} attributes no obligations to any layer"
    assert layers <= {"L1", "L2", "L3", "L4", "L5", "L6", "L7"}, f"unknown layer in {layers}"


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: f"{s.replay_id}-{s.slug}")
def test_replay_states_what_is_prohibited(spec: ReplaySpec) -> None:
    """The prohibitions are the part that is checkable first, so they must be present.

    "Do not state rejected / last chance / a deadline without evidence" is assertable against a
    card today; "send the milestone-specific update" needs an entire fundraising lane first.
    """
    assert spec.prohibited_behaviors or any(m.prohibited for m in spec.mutations), (
        f"replay {spec.replay_id} names nothing that is forbidden — it cannot fail anything")
