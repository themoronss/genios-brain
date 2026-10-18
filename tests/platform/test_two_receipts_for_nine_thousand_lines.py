r"""Two L5 receipts, each measured before it was written — and two candidates rejected.

⛔ WHAT WAS WRONG. L5 is **9,431 lines**, the layer that physically touches the customer, and it
carried **2 of the programme's 33 receipts** — 4,715 lines per guard against L4's 881. One of the two
(`every delivered card carries a lane`) **ERRORs** because `cards.output_lane` awaits migration
`0190`, so the layer had ONE working production guard.

⛔ CORRECTED 2026-10-02 — THAT PARAGRAPH'S COUNT IS WRONG, AND THIS FILE'S OWN GUARD COULD NOT
CATCH IT. `Receipt.layer` is a hand-written string, and `genios_engine/LAYERS.py` warns in its
docstring that *"Atlas 5.2 is our `deliver` (6), and Atlas 6 is our `feedback` (7) — so always name
the package, never the digit alone."* I filtered on the digit. Resolved by the table each receipt
queries, `deliver/`'s four tables (`cards`, `delivery_outbox`, `delivery_attempts`, `org_channels`)
are guarded by **8** receipts — 4 labelled `L5` and **4 labelled `L6`** — and before this programme
by **5**, of which **4 worked**: only `every delivered card carries a lane` ERRORs. So it was
**1,886** lines per guard, not 4,715, and 1,886 was already true before the pass began. The fifth
`L5`-labelled receipt, `decisions become tracked commitments`, reads `executions` and guards
`executive/`, not this layer.

⛔ NOTHING BELOW IS RETRACTED. The two receipts are real, each shown able to go red; the two
rejections were rejected for being structurally 0 forever; the 12-hour window came from a measured
6.0-hour sweep interval. **No assertion in this file depended on the count — which is exactly why
the wrong number survived.** *A guard that asserts the label is correct cannot notice that the label
means nothing.* Full record:
`speedrun008/YCW27/layer-5-delivery/08-CORRECTION-a-receipt-label-is-not-a-package.md`

⛔ THE PLAN LISTED FIVE CANDIDATES AND SAID EACH GETS A SCOPE MEASUREMENT FIRST. Two were rejected
for measured reasons, and that is the valuable half of this step:

    A · a delivery row with no attempt         ⛔ the v2 path has written no rows -> structurally 0
                                                  forever. **A receipt that cannot fail is not a
                                                  gate.**
    D · a card delivered on an adapter-less
        channel                                ⛔ impossible: `outbox.py:935` parks when
                                                  `get_channel()` is None. 0 forever.
    C · UNDELIVERABLE kept apart from
        failed_terminal                        ⛔ already guarded by
                                                  `test_proactive_channel_resolution.py:722`. It is
                                                  a CODE property, and a receipt would ask
                                                  production a question code already decides.

⛔ AND THE WINDOW WAS MEASURED, NOT PICKED. My instinct was one hour. `CardStore.sweep_lifecycle`
runs on `run_maintenance_sweep`'s HEAVY tick, whose interval is `config.sync_interval_hours` —
measured at **6.0**. A one-hour grace would have fired on every card that expired in the normal
six-hour gap between ticks: **latency reported as an alarm**, and *the fix for a false alarm is
always to loosen the check.*
"""
from __future__ import annotations

import pytest

from genios_engine.platform import receipts as R

#: ⛔ Referred to by CLAIM, never by number. Receipt numbers are POSITIONAL — inserting STEP-10's
#: two moved STEP-06's from #21 to #23 — so a number in a test or a document goes stale the next
#: time anybody adds one earlier in the list. Every test in this repo already filters by claim; the
#: documents did not, and that is corrected rather than papered over.
_WINDOW = "no card outlives its own window in a live state"
_PARKED = "a card parked for want of a channel is revived when one appears"


def _receipt(claim: str):
    found = [r for r in R.receipts(None) if r.claim == claim]
    assert len(found) == 1, f"expected exactly one receipt claiming {claim!r}, found {len(found)}"
    return found[0]


# ---------------------------------------------------------------------------------------------
# 1 · both exist, both are L5, and both can fail
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("claim", [_WINDOW, _PARKED])
def test_the_receipt_is_an_l5_gate_that_can_fail(claim: str) -> None:
    """⛔ *A receipt that cannot fail is not a gate.* Zero passes; one does not. Asserted for both,
    because the two rejected candidates were rejected for failing exactly this."""
    receipt = _receipt(claim)
    assert receipt.layer == "L5"
    assert receipt.expect(0) is True
    assert receipt.expect(1) is False
    assert receipt.detail and len(receipt.detail) > 80, "a receipt whose detail says nothing"


@pytest.mark.parametrize("claim", [_WINDOW, _PARKED])
def test_no_tautology_can_neutralise_the_receipt(claim: str) -> None:
    """⛔ THE M1 MUTATION SHAPE. In L4, `and not exists (` -> `and false and not exists (` left every
    substring in place and ten tests passed."""
    sql = _receipt(claim).sql.lower()
    for poison in ("and false", "or true", "and true", "where false", "where true", "1=1"):
        assert poison not in sql, f"the predicate is neutralised by {poison!r}"


# ---------------------------------------------------------------------------------------------
# 2 · ⛔ the window, and the arithmetic that justifies it
# ---------------------------------------------------------------------------------------------

def test_the_window_is_two_full_maintenance_cycles() -> None:
    """⛔ MEASURED AGAINST THE SCHEDULER, NOT CHOSEN. `sweep_lifecycle` runs on the heavy tick, so
    the grace must exceed it or the receipt reports the normal gap between ticks as a defect.

    Asserted arithmetically so a change to `sync_interval_hours` fails HERE rather than producing a
    receipt that cries wolf on every tenant.
    """
    from genios_engine.platform.config import get_settings
    from genios_engine.platform import scheduler

    tick_hours = float(get_settings().sync_interval_hours)
    assert "interval '12 hours'" in _receipt(_WINDOW).sql
    assert 12 >= 2 * tick_hours, (
        f"the heavy tick is now {tick_hours}h, so a 12-hour grace is less than two cycles -- the "
        "receipt would report cards the sweep simply has not reached yet")
    assert scheduler._SWEEP_TIMEOUT_S <= 12 * 3600, (
        "one sweep may now run longer than the grace window")


def test_the_window_receipt_asks_about_the_states_the_sweep_claims() -> None:
    """⛔ The receipt and the sweep must describe ONE population. `sweep_lifecycle` expires
    `('queued','surfaced','snoozed')`; a receipt asking about a different set would be asking whether
    some other sweep ran."""
    import inspect

    from genios_engine.deliver.store import CardStore

    sweep = " ".join(inspect.getsource(CardStore.sweep_lifecycle).split())
    sql = _receipt(_WINDOW).sql
    for state in ("queued", "surfaced", "snoozed"):
        assert f"'{state}'" in sql, f"the receipt ignores {state}, which the sweep expires"
        assert f"'{state}'" in sweep, f"the sweep no longer expires {state} -- re-derive the receipt"
    assert "expires_at <" in sql and "expires_at" in sweep


# ---------------------------------------------------------------------------------------------
# 3 · ⛔ the parked receipt, and the registry SQL cannot see
# ---------------------------------------------------------------------------------------------

def test_the_parked_receipt_matches_the_rows_own_channel() -> None:
    """⛔ The park is PER CHANNEL. A row parked for `teams` is not revived because `slack` appeared,
    so `c.channel = d.channel` is what keeps this a question about THIS row rather than the org."""
    sql = _receipt(_PARKED).sql
    assert "c.channel = d.channel" in sql, (
        "the receipt asks whether the ORG has any channel, which would report a teams backlog as "
        "cleared by a slack registration")
    assert "c.active" in sql, "an inactive registration is not a channel"
    assert "d.status = 'undeliverable'" in sql


def test_the_channel_set_is_injected_from_the_registry_not_hard_coded() -> None:
    """⛔ `deliverable_channels` intersects `org_channels` with the channels that HAVE AN ADAPTER,
    and that half lives in a Python registry SQL cannot see. Naming 'slack' in the query would rot
    the day a second adapter lands; building the literal from `_implemented_channels()` keeps both
    halves of the judgement in one place — the same injection receipt #31 uses for its era
    boundary."""
    from genios_engine.deliver.routing import AGENT_TRANSPORTS
    from genios_engine.deliver.units import _implemented_channels

    usable = _implemented_channels() - AGENT_TRANSPORTS
    sql = _receipt(_PARKED).sql
    for ch in usable:
        assert f"'{ch}'" in sql, f"{ch} has an adapter and is missing from the receipt"
    for ch in AGENT_TRANSPORTS:
        assert f"'{ch}'" not in sql, (
            f"{ch} is an agent transport -- those rows resolve against `agent_registry`, not "
            "`org_channels`, and a human delivery may never ride one")
    assert "'in_app'" not in sql, (
        "in_app is the PULL surface with no adapter; treating that row as a transport is what "
        "produced production's entire delivery history: 3 rows, all failed_terminal")


# ---------------------------------------------------------------------------------------------
# 4 · ⛔ the rejections, made checkable instead of left in prose
# ---------------------------------------------------------------------------------------------

def test_the_rejected_candidates_premises_still_hold() -> None:
    """⛔ TWO CANDIDATES WERE REJECTED BECAUSE THEY COULD NOT FAIL. That is a statement about the
    code, so it can rot — and if it does, the candidate becomes viable and somebody should
    reconsider it. This is what makes the rejection reviewable rather than a paragraph.

      * *a delivery row with no attempt*: 0 forever while nothing calls `spine.materialize`
      * *a card delivered on an adapter-less channel*: impossible while the drain parks on
        `get_channel() is None`
    """
    import inspect

    from genios_engine.deliver import delivery_health as H
    from genios_engine.deliver import outbox

    assert "spine.materialize" in H.UNCUT_OVER, (
        "spine.materialize left the un-cut-over tier -- the v2 path may now write rows, so "
        "'a delivery row with no attempt' can fail and candidate A should be re-measured")

    # ⛔ `_drain_claimed`, not `drain`: `drain` claims rows and delegates, and the adapter check
    # lives in the function that actually sends. My first version of this test read `drain` and
    # failed on correct code -- a reminder that "the drain" is two functions.
    sender = " ".join(inspect.getsource(outbox._drain_claimed).split())
    assert "get_channel(" in sender and "_park(" in sender, (
        "the send path no longer parks on a missing adapter -- candidate D stopped being "
        "impossible and should be re-measured")
    assert "no adapter for this channel" in sender, (
        "the park reason that makes candidate D impossible is gone")


def test_the_lane_receipt_is_still_the_one_that_cannot_run() -> None:
    """⛔ Recorded as a state, not a count: L5's oldest receipt ERRORs because `cards.output_lane`
    awaits `0190` (Harsh, `HANDOFF-HARSH.md` H1). The two added here read `cards` and
    `delivery_outbox` columns that exist in APPLIED migrations, so unlike that one they execute
    today — which is why *a receipt that cannot fail yet* and *a receipt that cannot run* are
    different sentences."""
    lane = _receipt("every delivered card carries a lane, or is labelled unrouted")
    assert "output_lane" in lane.sql
    for claim in (_WINDOW, _PARKED):
        assert "output_lane" not in _receipt(claim).sql, (
            "a new receipt depends on the unapplied column, so it would ERROR rather than answer")
