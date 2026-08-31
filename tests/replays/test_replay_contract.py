"""Contract tests over the replay suite itself.

Before any replay can be trusted as an exit gate, the suite has to be trustworthy: all twelve
present, every mutation transcribed, every blocked assertion naming what blocks it, and the
harness genuinely unable to reach a model. These assertions are cheap and they are the reason a
green replay run means something.
"""
from __future__ import annotations

import pytest

from tests.replays.harness import NoLLM, PINNED, REPLAY_NOW, load_specs

EXPECTED_REPLAYS = 12


def test_all_twelve_replays_are_transcribed():
    """A missing replay is a silently missing exit gate.

    The program's phases each cite replays by number; if one is absent the phase reports green
    against a smaller bar than the one it claims.
    """
    specs = load_specs()
    ids = [s.replay_id for s in specs]
    assert len(specs) == EXPECTED_REPLAYS, f"expected {EXPECTED_REPLAYS} replays, found {ids}"
    assert ids == [f"{n:02d}" for n in range(1, EXPECTED_REPLAYS + 1)], f"gaps in replay ids: {ids}"


def test_every_replay_declares_at_least_one_mutation():
    """A replay with no mutations is a description, not a test.

    The mutation table is the entire discriminating power: it is what distinguishes "the card
    looked reasonable" from "the decision changed for the stated reason".
    """
    thin = [s.replay_id for s in load_specs() if len(s.mutations) < 2]
    assert not thin, f"replays with fewer than two mutations: {thin}"


def test_every_blocked_mutation_names_what_blocks_it():
    """"Blocked" without a named cause is indistinguishable from "we skipped it"."""
    unnamed = [
        f"{s.replay_id}: {m.mutation[:60]}"
        for s in load_specs() for m in s.blocked if not m.blocked_on.strip()
    ]
    assert not unnamed, ("blocked mutations with no named blocker:\n  " + "\n  ".join(unnamed))


def test_the_harness_cannot_reach_a_model():
    """Determinism is the property under test, so the model must be unreachable, not merely unused.

    A permissive stub would let a replay pass because a model happened to answer well — which is
    the opposite of what a replay proves.
    """
    with pytest.raises(AssertionError, match="reached the LLM"):
        NoLLM().call("anything")


def test_the_replay_world_is_pinned():
    """A replay that reads the wall clock is not reproducible, and neither are its verdicts."""
    assert REPLAY_NOW.tzinfo is not None, "the replay clock must be timezone-aware"
    assert PINNED["graph_version"] and PINNED["config_snapshot_id"] and PINNED["corpus_version"], (
        "a decision must be attributable to a specific graph, config and corpus version")


def test_coverage_of_blocked_versus_runnable_is_visible():
    """Publish the split rather than letting a mostly-blocked suite read as passing.

    This is the number the program's exit gates should be read against: a phase claiming a replay
    family is satisfied must move mutations out of `blocked`, not merely keep the suite green.
    """
    specs = load_specs()
    total = sum(len(s.mutations) for s in specs)
    blocked = sum(len(s.blocked) for s in specs)
    print(f"\ngolden replays: {len(specs)} · mutations {total} · "
          f"runnable {total - blocked} · blocked {blocked}")
    for s in specs:
        print(f"  {s.replay_id} {s.slug:<44} {len(s.runnable):>2} runnable / "
              f"{len(s.blocked):>2} blocked   {s.failure_class[:48]}")
    assert total > 0
