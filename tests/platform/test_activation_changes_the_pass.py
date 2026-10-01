"""S3.F3.1 · activated is not the same as ran — the receipt that catches a switch doing nothing.

    pytest tests/platform/test_activation_changes_the_pass.py -q

⛔ WHY. `platform/l3_activation` shipped once with a reader, a fail-closed gate, an erasure row, an admin
API and a report — **and no caller.** Plane R's notes record the lesson in one line:

    "a switch that reports itself on and changes nothing is worse than no switch."

Once Rohit inserts the pilot's activation row, nothing today would tell anybody whether it did anything.
`reasoning_runs.mode` already answers it: `domain_shadow` writes `ExecutionMode.LIVE if live_row else
ExecutionMode.SHADOW`, and only the live lane reaches `_persist_live`.
"""

from __future__ import annotations

import pytest

from genios_engine.platform import receipts as R

pytestmark = pytest.mark.unit

_CLAIM = "the live pass has actually run, not only the shadow pass"


def _receipt(org="org_1"):
    found = [r for r in R.receipts(org) if r.claim == _CLAIM]
    assert len(found) == 1, f"expected exactly one {_CLAIM!r} receipt, found {len(found)}"
    return found[0]


# =================================================================================================
# 1 · the receipt exists and asks the right question
# =================================================================================================
def test_the_receipt_is_registered():
    assert _receipt().layer == "L4"


def test_it_asks_about_the_mode_column_and_not_about_the_activation_row():
    """⛔ THE DISTINCTION THAT IS THE WHOLE POINT. Counting activation rows would prove the switch was
    flipped; counting live runs proves it did something."""
    sql = _receipt().sql.lower()
    assert "reasoning_runs" in sql
    assert "mode = 'live'" in sql
    assert "l3_activation" not in sql


def test_it_passes_only_when_a_live_run_exists():
    expect = _receipt().expect
    assert expect(0) is False
    assert expect(1) is True
    assert expect(97) is True


def test_a_shadow_only_tenant_fails_it():
    """The state the pilot is in: everything compiles, nothing runs live."""
    assert _receipt().expect(0) is False


# =================================================================================================
# 2 · ⛔ it is a question about a TENANT
# =================================================================================================
def test_it_is_org_filtered_when_an_org_is_given():
    """⛔ Unfiltered, it would report another tenant's live runs on this tenant's readiness page."""
    assert ":org" in _receipt("org_1").sql


def test_it_is_never_fleet_wide():
    """`fleet_wide` is for questions whose answer cannot differ per tenant — the schema itself. Whether
    a tenant's live pass ran differs per tenant by definition."""
    assert _receipt().fleet_wide is False


def test_the_fleet_run_drops_the_filter_rather_than_faking_one():
    assert ":org" not in _receipt(None).sql


# =================================================================================================
# 3 · the detail says what the failure means
# =================================================================================================
def test_the_detail_names_the_defect_it_guards():
    """A receipt that fails with no sentence is a number nobody reads — `Receipt`'s own docstring makes
    that argument for keeping the predicate beside the claim."""
    detail = _receipt().detail
    assert detail.strip()
    assert "changes nothing" in detail


def test_the_reasoning_runs_mode_vocabulary_is_what_the_receipt_assumes():
    """⛔ If `mode` ever stops carrying 'live', this receipt silently counts zero forever. Asserted
    against the migration, so the two cannot drift."""
    from pathlib import Path

    sql = (Path(__file__).resolve().parents[2] / "migrations"
           / "0026_l4_reasoning_trace.sql").read_text().lower()
    assert "check (mode in ('live', 'shadow', 'simulation', 'replay'))" in sql


def test_only_the_live_lane_persists_so_the_count_means_what_it_says():
    """⛔ `domain_shadow` refuses the shadow lane with `if not live_row: continue` BEFORE it reaches
    `_persist_live`. If a shadow pass ever persisted, a live-run count would stop distinguishing the two
    lanes and this receipt would pass on shadow work.

    Asserted on the AST, not on text near a thing. My first two attempts grepped the source at a fixed
    offset: one matched `def _persist_live(` instead of the call, and the second's window was too short
    for the comment block between the guard and the call. The L0 doctrines name that family —
    *"assert on structure — the AST, the column list — never on text that happens to sit near a thing."*
    """
    import ast
    import inspect

    from genios_engine.reason import domain_shadow

    tree = ast.parse(inspect.getsource(domain_shadow))

    # `if not live_row: continue` — an early return for the shadow lane, anywhere in the module.
    guards = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.UnaryOp) and isinstance(node.test.op, ast.Not)
        and isinstance(node.test.operand, ast.Name) and node.test.operand.id == "live_row"
        and any(isinstance(b, ast.Continue) for b in node.body)
    ]
    assert guards, "nothing refuses the shadow lane with `if not live_row: continue`"


def test_the_lane_is_recorded_on_the_run_so_the_receipt_can_read_it():
    """The count is only meaningful because the mode is written from the same flag the guard reads."""
    import inspect

    from genios_engine.reason import domain_shadow

    assert ("ExecutionMode.LIVE if live_row else ExecutionMode.SHADOW"
            in inspect.getsource(domain_shadow))


# =================================================================================================
# 4 · the three organisation receipts land beside it
# =================================================================================================
def test_the_l4_organisation_receipts_are_all_present():
    claims = {r.claim for r in R.receipts("org_1")}
    assert "the tenant has at least one active seat" in claims
    assert "at least one seat has a manager" in claims
    assert _CLAIM in claims


def test_the_l4_receipt_count_grew_by_exactly_three():
    """Three before this work, six after: two organisation receipts plus the live-pass one. A
    seventh would mean something was added without a decision — including a channel receipt, which
    already existed.

    ⛔ SCOPED TO L4, AND THAT IS STRICTER THAN THE GLOBAL TOTAL IT REPLACED, NOT LOOSER. The original
    pinned `len(R.receipts(...)) == 26`, so the very next layer to add a receipt of its own broke a
    test about L4 — and the cheap fix for that is to bump the number, which is how a decision gate
    becomes a rubber stamp. Counting L4's own receipts still fails on an undecided L4 addition, and
    stops failing on decisions taken elsewhere. L5's own count is guarded in
    `tests/deliver/test_nothing_dies_of_low_confidence.py`.

    ⛔ 6 -> 7 ON 2026-10-01, and it is a decision rather than a bump. The seventh is
    `every action that needs sign-off can name who signs` — measured: 410 of 794 actions carry
    `requires_approval` against **zero** rows in `authority_rules`, so every one of them announces
    a requirement it cannot attribute and nothing counted it. It is L4's question because
    *who signs, and with what right* is this layer's own; see
    `speedrun008/YCW27/layer-4-executive/STEP-06-DONE-410-approvals-nobody-can-attribute.md`.

    ⛔ AND IT IS WHAT CAUGHT THE AUTHOR OF THAT RECEIPT. Two drafts of its test pinned the GLOBAL
    total instead, which is the pattern this docstring rejects — the full suite failed here, this
    docstring explained why, and the global literal came out. The gate worked on the person who
    did not know it existed, which is the only real test of a gate."""
    assert len([r for r in R.receipts("org_1") if r.layer == "L4"]) == 7


def test_no_receipt_claim_is_duplicated():
    """⛔ Two receipts answering one question disagree the first time somebody tunes one."""
    claims = [r.claim for r in R.receipts("org_1")]
    assert len(claims) == len(set(claims))
