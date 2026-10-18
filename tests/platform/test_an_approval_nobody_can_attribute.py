r"""`U2` · 410 actions announce a sign-off requirement that nothing can attribute.

⛔ WHAT WAS MEASURED, 2026-10-01. `execution_actions` holds 794 rows and **410 carry
`requires_approval`** — 52% of every action this layer has ever planned (182, 121 and 107 across
the three orgs). `authority_rules` holds **zero** rows, so `AuthorityView.resolve` answers
`no_authority_rule` for every subject and `assignment.resolve_approver_seat` correctly returns
`None` for every call.

`resolve_approver_seat`'s own docstring states the cost: *"a card that says 'this needs sign-off'
and cannot say whose is less useful than one that can, and far better than one that quietly drops
the requirement."* ⛔ **Nothing counted how often the less-useful state happens.** That is what
receipt #32 is.

⛔ WHY THE WIRING WAS *NOT* BUILT, AND THIS IS THE POINT OF THE UNIT. `02-PLAN.md` called U2 "the
safest of the four gaps — eight tests already exist, no product decision". Measuring it refuted
that: the wiring is blocked **twice**.

    neither `execution_actions` nor `executions` has an approver column
      -> consuming an answer needs a contract field AND a migration
      -> `0186`-`0190` have never run in production (H1)
    `authority_rules` is empty
      -> the column would be filled by `None` on every one of the 410 rows

And `executive/unreached.py` had already declared the mover — *"that needs the org to have
published authority rules at all"* — so wiring it would have **deleted the only place that reason
is written down**, in exchange for a call that still names nobody.

> ⛔ **A mover without a number is a wish.** The entry now carries 410 / 794 / 0, and a receipt
> counts it.

⛔ AND ZERO IS A TRUE PASS HERE, UNLIKE RECEIPT #31. The era receipt returns `-1` for an empty
window because an era that produced nothing is a dead pipeline. Here, no gated actions genuinely
means no requirement is unattributed. **The two receipts make opposite choices about emptiness on
purpose**, and this file pins that difference so a later reader does not "fix" one to match the
other.

## Living log — the numbers this file is pinned to

    2026-10-01   RED, correctly
                   org_66bca8…  182     org_e97e86…  121     org_2f1bc0…  107
                   all orgs     410     and the per-org sum matches exactly
                 authority_rules: 0 rows
                 ⛔ removing the `requires_approval` gate returns 0 and PASSES — the
                   conjunction is load-bearing, exactly as in #31
"""
from __future__ import annotations

import inspect

from genios_engine.executive import unreached
from genios_engine.platform import receipts as R
from genios_engine.platform.receipts import receipts

CLAIM = "every action that needs sign-off can name who signs"


def _receipt(org: str | None = "org_x"):
    found = [r for r in receipts(org) if r.claim == CLAIM]
    assert len(found) == 1, f"expected exactly one {CLAIM!r} receipt, found {len(found)}"
    return found[0]


# ── the conjunction, not a count ──────────────────────────────────────────────────

def test_it_counts_gated_actions_and_not_all_actions() -> None:
    """⛔ `requires_approval` on its own is HEALTHY — it is the autonomy gate
    (`contracts/execution.py:233`) doing its job. 410 gated actions is the layer being careful.
    A receipt that counted them would be red for correct behaviour."""
    sql = " ".join(_receipt().sql.split())
    assert "a.requires_approval" in sql
    assert "authority_rules" in sql

    # ⛔ CONTIGUOUS, NOT MERELY PRESENT — and this is the second time in two units that mutation
    # testing found the same half-guard in my own test. The first version asserted
    # `"not exists" in sql`, and `and not exists (` -> `and false and not exists (` left both
    # substrings in place while making the whole subquery irrelevant: on production the receipt
    # went from 410 (correctly red) to 0 (green). **Presence is not effect.**
    assert "where a.requires_approval and not exists (" in sql, (
        "the gate and the conjunction must be adjacent. Anything inserted between them — "
        "`and false` is the one-token version — neutralises the subquery while leaving every "
        "substring a presence check looks for")


def test_no_tautology_can_neutralise_either_half() -> None:
    """⛔ THE GENERAL FORM OF THE MUTATION ABOVE, because `and false` is only the shortest one.

    A receipt is one SQL string and a predicate; a single injected constant turns it into a
    reassurance. This checks the whole query for the constants that do it, in both polarities,
    rather than trusting the one adjacency assertion above.
    """
    sql = " ".join(_receipt().sql.split()).lower()
    for tautology in ("and false", "or true", "and true", "where false", "where true", "1=1"):
        assert tautology not in sql, (
            f"{tautology!r} in the query — a receipt with a constant in it answers about the "
            "constant, not about the deployment")


def test_an_in_force_rule_is_required_and_not_merely_a_row() -> None:
    """Three ways to hold a rule and still name nobody. Each must be excluded."""
    sql = " ".join(_receipt().sql.split())
    assert "r.approver_node_id is not null" in sql, (
        "a threshold with no approver names nobody — counting it as coverage would go green on a "
        "rule that cannot answer")
    assert "r.valid_from <= now()" in sql, "a rule that starts next quarter is not in force"
    assert "r.valid_until is null or r.valid_until > now()" in sql, (
        "⛔ an EXPIRED rule is not an enforceable one. Without this the receipt goes green for a "
        "tenant whose only rule lapsed last year")


def test_zero_is_a_true_pass_here_and_the_contrast_with_the_era_receipt_is_deliberate() -> None:
    """⛔ THE TWO RECEIPTS DISAGREE ABOUT EMPTINESS ON PURPOSE.

    `_ERA_SELECTS_NOTHING_SQL` returns `-1` when its window is empty, because an era that
    produced no runs is a dead pipeline and a green receipt there is a lie. Here, no gated actions
    genuinely means no requirement is unattributed — so `0` is a true pass and there is no
    sentinel.

    Pinned so a later reader does not make one consistent with the other and break whichever they
    did not read.
    """
    assert _receipt().expect(0) is True
    assert _receipt().expect(410) is False
    assert _receipt().expect(1) is False
    era_sql = " ".join(R._ERA_SELECTS_NOTHING_SQL(None).split())
    mine_sql = " ".join(_receipt(None).sql.split())
    assert "then -1" in era_sql, "the era receipt's sentinel moved; this contrast is now stale"
    assert "-1" not in mine_sql, (
        "this receipt must NOT acquire an empty-window sentinel — emptiness is a true pass here")


# ── the honesty that survives not building the wiring ─────────────────────────────

def test_the_unreached_entry_is_still_there_because_the_function_is_still_not_called() -> None:
    """⛔ THE TEST THAT MAKES THIS UNIT HONEST.

    `02-PLAN.md` U2 said to delete this entry *in the same commit* as the wiring. The wiring was
    not built — it is blocked on a migration and on the org publishing any rule — so deleting the
    entry would be exactly the lie
    `tests/test_the_executive_says_what_it_does_not_call` exists to catch: a declaration claiming a
    function is called when it is not.
    """
    assert "assignment.resolve_approver_seat" in unreached.UNREACHED, (
        "the entry was deleted while the function is still uncalled. A receipt counting the gap "
        "is not the same as consuming an answer")


def test_the_mover_now_carries_its_number() -> None:
    """⛔ A mover without a number is a wish. It said *"that needs the org to have published
    authority rules at all"* and gave no count, so nobody could tell a one-off from 52% of every
    action the layer plans."""
    _why, mover = unreached.UNREACHED["assignment.resolve_approver_seat"]
    for number in ("410", "794", "zero"):
        assert number in mover, (
            f"the mover must carry {number!r} — the measurement is what turns a deferral into a "
            f"decision somebody can weigh")
    assert "0186" in mover and "migration" in mover, (
        "the mover must name BOTH blockers: the missing column/migration and the empty rule "
        "table. Naming one makes the other invisible")


def test_the_builder_explains_why_the_wiring_is_absent() -> None:
    """The receipt's own docstring must point at the plan, so a reader who finds a red receipt and
    no wiring does not conclude somebody forgot."""
    doc = inspect.getdoc(R._UNATTRIBUTED_APPROVALS_SQL) or ""
    assert "not built" in doc or "NOT BUILT" in doc
    assert "0186" in doc, "the docstring must name the migration blocker"
    assert "02-PLAN.md" in doc, "and point at where the unit is recorded"


# ── wired like every other receipt ────────────────────────────────────────────────

def test_it_is_an_l4_receipt_and_org_filtered() -> None:
    r = _receipt("org_x")
    assert r.layer == "L4", "approval authority is L4's question — who signs, and with what right"
    assert r.fleet_wide is False, "authority rules are per tenant"
    assert ":org" in r.sql and "a.org_id" in r.sql, (
        "the filter must be on the ACTION's org, since the subquery correlates on it")
    assert ":org" not in _receipt(None).sql


def test_the_detail_states_the_measured_truth() -> None:
    detail = _receipt().detail
    assert "410" in detail and "794" in detail, (
        "the detail must carry the measurement, not restate the query")
    assert "sign-off" in detail


def test_the_receipt_calls_the_builder_rather_than_inlining_sql() -> None:
    source = inspect.getsource(R.receipts)
    assert "_UNATTRIBUTED_APPROVALS_SQL(org)" in source


def test_the_count_of_L4_RECEIPTS_is_what_moves_not_the_global_total() -> None:
    """⛔ THE ASSERTION I WROTE FIRST WAS THE ONE THIS CODEBASE HAD ALREADY REJECTED.

    Two earlier versions of this test pinned `len(receipts(None))` — first 31, then 32 — and the
    full suite failed on neither. It failed on
    `tests/platform/test_activation_changes_the_pass.py::test_the_l4_receipt_count_grew_by_exactly_three`,
    which pins **L4's own** count and whose docstring already explains why:

    > *"SCOPED TO L4, AND THAT IS STRICTER THAN THE GLOBAL TOTAL IT REPLACED, NOT LOOSER. The
    > original pinned `len(R.receipts(...)) == 26`, so the very next layer to add a receipt of its
    > own broke a test about L4 — and the cheap fix for that is to bump the number, **which is how
    > a decision gate becomes a rubber stamp.**"*

    ⛔ I had grepped for `len(receipts(` , found only my own two, and concluded no canonical guard
    existed. It existed and counted per layer, so the grep could not see it. **A grep that finds
    nothing is not evidence that nothing is there** — the same lesson this programme has now
    recorded thirteen times.

    So the count literal belongs where it already is, per layer, and the only thing this file
    asserts is that **its** receipt is the L4 one that moved the number.
    """
    l4 = [r for r in receipts("org_1") if r.layer == "L4"]
    assert CLAIM in [r.claim for r in l4], (
        "this receipt is L4's, so it is L4's count that moves — and "
        "test_the_l4_receipt_count_grew_by_exactly_three is where that number is decided")
