"""The wiring half of native activation.

`test_native_publication.py` proves a decision projects into a sound row. These tests prove the
sweep actually reaches that code, on the right nodes, without colliding with the legacy path — the
failure mode the repo has already been bitten by once, where a correct derivation the runner never
called was indistinguishable from a broken one.

Everything here is asserted against source or manifests rather than a live database, matching
`test_deal_join_wiring.py`: the sweep's database path has no local harness, so the properties that
can be checked statically are the ones that must be.
"""

from __future__ import annotations

import inspect

from genios_engine.packs.capabilities import BUILTIN_CAPABILITIES, DEAL_COOLING_FULL_V2
from genios_engine.packs.general_v1 import GENERAL_V1
from genios_engine.packs.sales_v1 import SALES_V1
from genios_engine.reason import runner
from genios_engine.reason.publication import native_rule_id, native_rule_ids

PACKS = (SALES_V1, GENERAL_V1)


def _pack_rule_ids() -> set[str]:
    return {rule["id"] for pack in PACKS for rule in pack["rules"]}


# -- the sweep picks the capability up -----------------------------------------------------------

def test_the_full_roster_capability_is_scheduled_by_the_sweep():
    """Lock 1. Absent from this tuple the seventeen units run nowhere, however well they work."""
    assert DEAL_COOLING_FULL_V2 in BUILTIN_CAPABILITIES


def test_the_capability_matches_the_sweep_s_selection_rule():
    """The runner selects on `domain == pack_id` and `root_entity_type == node_type`. A capability
    whose domain does not name a real pack is scheduled for no node and fails silently."""
    assert DEAL_COOLING_FULL_V2.domain == SALES_V1["id"] == "sales"
    assert DEAL_COOLING_FULL_V2.root_entity_type == "deal"


def test_the_native_sweep_is_no_longer_pinned_to_shadow():
    """Lock 3. The native call must use the same execution mode the legacy path computes from pack
    state, not a hardcoded SHADOW — otherwise activating the pack changes nothing for natives."""
    source = inspect.getsource(runner.run)
    native_call = source[source.index("reason_native_capability("):]
    native_call = native_call[:native_call.index(")")]

    assert "mode=execution_mode" in native_call
    assert "ExecutionMode.SHADOW" not in native_call


def test_the_sweep_publishes_native_decisions():
    """The seam exists and the sweep calls it. Without this the capability reasons, persists a
    full audit trail, and then reaches nobody — which is exactly where it stood before."""
    source = inspect.getsource(runner.run)

    assert "build_native_publication(" in source
    assert "publish_native_signal(" in source


# -- it cannot fight the legacy path --------------------------------------------------------------

def test_no_native_rule_id_collides_with_a_pack_rule():
    """One open signal per (org, pack, pack_version, rule_id, subject) is enforced by a partial
    unique index. A native capability whose projected rule id equalled a pack rule's would make
    the two paths silently overwrite each other's claims on the same deal."""
    collisions = native_rule_ids(BUILTIN_CAPABILITIES) & _pack_rule_ids()

    assert collisions == set(), f"native/legacy rule id collision: {sorted(collisions)}"


def test_no_two_delivery_enabled_capabilities_share_a_rule_id():
    """Two live capabilities publishing under one rule id would compete for the same open signal,
    and the loser would be invisible rather than reported."""
    live = [c for c in BUILTIN_CAPABILITIES if c.live_delivery_enabled]
    ids = [native_rule_id(c.capability_id) for c in live]

    assert len(ids) == len(set(ids))


def test_the_comparison_baseline_stays_silent():
    """v1 remains scheduled so its decisions can be compared against v2's on the same node, and
    remains delivery-disabled so only one of them can speak."""
    baseline = [c for c in BUILTIN_CAPABILITIES
                if c.capability_id == "sales.deal_cooling"]

    assert len(baseline) == 1
    assert baseline[0].live_delivery_enabled is False


# -- lifecycle ------------------------------------------------------------------------------------

def test_native_rule_ids_participate_in_signal_lifecycle():
    """A native signal that nothing is entitled to retire stays open forever. The sweep's
    `pack_owns` set decides entitlement, so the native ids have to be in it."""
    source = inspect.getsource(runner.run)
    owns = source[source.index("pack_owns = "):]
    owns = owns[:owns.index("\n")]

    assert "native_rule_ids(" in owns


def test_a_failed_native_run_never_retires_its_previous_claim():
    """Rule 08 — stale beats wrong. A capability that could not reason has said nothing, so the
    subject must land in `indeterminate`, which lifecycle refuses to auto-resolve."""
    source = inspect.getsource(runner.run)
    native_block = source[source.index("for capability in node_capabilities:"):]
    native_block = native_block[:native_block.index("for rule in rules:")]

    assert native_block.count("indeterminate.add((native_rule, nd.node_id))") == 2


def test_every_non_publishing_native_outcome_is_recorded():
    """"Reasoned and stayed silent" and "never reasoned" must be distinguishable in the log, or a
    quiet rollout is indistinguishable from a broken one."""
    source = inspect.getsource(runner.run)
    native_block = source[source.index("for capability in node_capabilities:"):]
    native_block = native_block[:native_block.index("for rule in rules:")]

    for reason in ("native_reasoning_failed", "native_not_authorized", "cooldown"):
        assert f'"{reason}"' in native_block


# -- budget ---------------------------------------------------------------------------------------

def test_native_publication_spends_the_shared_daily_budget():
    """Natives must not open a second, uncapped spending lane. `_budget_used` counts every signal
    the org created today, so re-reading it after legacy emission is what makes the pool shared."""
    source = inspect.getsource(runner.run)
    block = source[source.index("native_remaining = "):]
    block = block[:block.index("native_sid = ")]

    assert "_budget_used(store, org_id, eval_time)" in source[source.index("native_remaining = "):]
    assert "_active_seats(store, org_id)" in source[source.index("native_remaining = "):]
    assert '"budget"' in block


def test_native_publication_ranks_before_it_spends():
    """Spending in node-scan order would let an arbitrary graph ordering decide what a human sees
    when the budget binds. The order must be total: score desc, then rule id, then subject."""
    source = inspect.getsource(runner.run)

    assert ("native_candidates.sort(key=lambda item: (-item[0].score, item[0].rule_id,"
            in source)
