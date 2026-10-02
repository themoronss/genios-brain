r"""The v2 spine cutover cannot be taken with its ambiguity-marker unwired.

⛔ WHAT IS TRUE TODAY. `deliver/spine.py` is a complete, correct, mechanically disjoint second
delivery path, and **nothing in production calls any of it.** `outbox.drain` is the live path and
takes `dedupe_key is null`; the spine's claimer takes `is not null`. `outbox.py:838` wrote the hazard
down before closing it: *"Risk was zero only because the v2 path has never written a row yet; the
moment it does, both workers could select the same one and double-send."*

⛔ WHAT THIS MODULE EXISTS FOR. `spine.recover_expired_claims` is the one component of that path
exercised by **nothing — not production, not a test.** Its docstring states the harm: *"An expired
worker may have POSTed to a provider before dying; we must never silently retry over that
ambiguity."* So on the day the cutover is taken, it would be taken with that step unwired and nothing
in the repo would say so.

> ⛔ **An uncalled function on an un-cut-over path is not a bug; it is an unguarded cutover.** The two
> want opposite fixes: a bug wants wiring now, an unguarded cutover wants a guard that fires when the
> cutover is taken. Wiring a recovery into a path that processes zero rows would be presence without
> effect.

**The core assertion below is vacuously true today, and that is correct.** It fails the build on the
commit that takes the cutover without the recovery.
"""
from __future__ import annotations

import ast
from pathlib import Path

from genios_engine.deliver import delivery_health as H
from genios_engine.executive.unreached import qualified_call_counts
from genios_engine.platform import receipts as R

_SPINE = Path(H.__file__).resolve().parent / "spine.py"

#: The spine's two claiming entry points. Calling either from production IS taking the cutover.
_CUTOVER_ENTRY_POINTS = ("claim_due",)

#: What must be wired before, or at the same time as, the cutover.
_RECOVERY = "recover_expired_claims"


def test_the_claimer_and_the_recovery_are_wired_together_or_not_at_all() -> None:
    """⛔ THE GUARD. Today both are zero. If a commit wires the claimer, it must wire the recovery."""
    counts = qualified_call_counts(H.engine_sources())
    claimed = sum(counts.get(("spine", name), 0) for name in _CUTOVER_ENTRY_POINTS)
    recovered = counts.get(("spine", _RECOVERY), 0)
    assert not (claimed and not recovered), (
        f"spine.claim_due now has {claimed} production caller(s) and "
        f"spine.{_RECOVERY} has {recovered}. The cutover has been taken without the step that "
        "marks an expired worker's unsettled attempt `unknown` -- so a fresh worker will retry "
        "over a provider POST that may already have landed")


def test_both_are_still_declared_as_an_un_cut_over_tier() -> None:
    """⛔ The other direction. If either becomes reached, the declaration is the lie, not the call."""
    for name in ("spine.claim_due", f"spine.{_RECOVERY}"):
        assert name in H.UNCUT_OVER, f"{name} must be declared while it is uncalled"
        tier = H.UNCUT_OVER[name][0]
        assert tier == 3, f"{name} is the claiming tier, got tier {tier}"
    assert H.now_called() == (), f"a declared entry acquired a caller: {H.now_called()}"


def test_the_claiming_tier_has_no_production_evidence() -> None:
    """⛔ The cutover is a GRADIENT. Tier 1 is shadow-measured; tiers 2-4 are not, and tier 3 is the
    one that touches the network."""
    for name in ("spine.claim_due", f"spine.{_RECOVERY}"):
        assert H.UNCUT_OVER[name][2] is None, (
            f"{name} claims a measurement -- if one now exists, this test should name it")


# ---------------------------------------------------------------------------------------------
# ⛔ the receipt, and the blind spot it must NOT inherit
# ---------------------------------------------------------------------------------------------

def _receipt():
    found = [r for r in R.receipts(None) if "unsettled" in r.claim]
    assert len(found) == 1, f"expected exactly one unsettled-attempt receipt, found {len(found)}"
    return found[0]


def test_an_unsettled_attempt_has_a_receipt() -> None:
    receipt = _receipt()
    assert receipt.layer == "L5"
    assert receipt.expect(0) and not receipt.expect(1), (
        "zero unsettled attempts passes; one does not")


def test_the_receipt_does_not_inherit_the_recoverys_fence_blind_spot() -> None:
    """⛔ THE DESIGN DECISION, PINNED. `recover_expired_claims` joins `a.claim_token =
    d.fence_token`, and `claim_due` writes a NEW fence when it reclaims -- so the orphans that
    matter most, the ones already handed to a fresh worker, can never match the recovery's own
    predicate again. A receipt built on that join would miss exactly the permanently-unrecoverable
    cases.

    **A guard must not inherit the blind spot of the thing it guards.**
    """
    sql = _receipt().sql
    assert "fence_token" not in sql, (
        "the receipt joins on the fence, so it can only see orphans nobody has reclaimed yet -- "
        "which is the subset that is still recoverable")
    assert "claim_expires_at" not in sql, (
        "an expired claim is reset to a future lease on reclaim, so this predicate silently stops "
        "matching the rows it was written for")
    assert "settled_at is null" in sql and "'started'" in sql


def test_the_window_is_far_longer_than_any_lease_or_timeout() -> None:
    """⛔ The number is justified, not picked. `claim_due(lease_seconds=300)` and
    `push._TIMEOUT_S = 4.0`, so an hour is twelve leases and nine hundred timeouts -- a merely slow
    attempt cannot be reported as an ambiguous one. *The fix for a false alarm is always to loosen
    the check*, so the window is set wide enough never to need loosening."""
    from genios_engine.deliver import push, spine
    import inspect

    sql = _receipt().sql
    assert "interval '1 hour'" in sql
    lease = inspect.signature(spine.claim_due).parameters["lease_seconds"].default
    assert 3600 >= 12 * lease, f"an hour is less than twelve leases of {lease}s"
    assert 3600 > 100 * push._TIMEOUT_S


def test_no_tautology_can_neutralise_the_receipt() -> None:
    """⛔ THE M1 MUTATION SHAPE. In L4, `and not exists (` -> `and false and not exists (` left every
    substring in place and ten tests passed."""
    sql = _receipt().sql.lower()
    for poison in ("and false", "or true", "and true", "where false", "where true", "1=1"):
        assert poison not in sql, f"the receipt predicate is neutralised by {poison!r}"
    # contiguity: the two halves of the claim must not have been prised apart
    assert "a.outcome = 'started'" in sql
    assert sql.index("a.outcome = 'started'") < sql.index("a.settled_at is null")


def test_the_receipt_reads_the_attempts_table_that_actually_exists() -> None:
    """⛔ `0043_l52_delivery_control_plane.sql` is APPLIED, unlike `0186`-`0190` -- so unlike L5's
    lane receipt this one can RUN today. It returns 0 because the v2 path has written nothing, and
    it starts answering the moment the cutover is taken. ⛔ A receipt that cannot fail is not a
    gate; this one cannot fail *yet*, which is a different statement and the reason it exists."""
    root = Path(H.__file__).resolve().parents[2]
    ddl = (root / "migrations" / "0043_l52_delivery_control_plane.sql").read_text(encoding="utf-8")
    tree_cols = {"outcome", "settled_at", "started_at", "claim_token"}
    create = ddl[ddl.index("create table if not exists delivery_attempts"):]
    create = create[:create.index(");")]
    for col in tree_cols:
        assert col in create, f"delivery_attempts has no {col} column in the applied schema"
    assert "delivery_attempts" in _receipt().sql


def test_the_guard_actually_READS_the_call_counts() -> None:
    """⛔ The mutation that survived fifteen tests in L4: a value imported and never used. Docstring
    excluded BY IDENTITY, never by value."""
    import inspect
    tree = ast.parse(inspect.getsource(
        test_the_claimer_and_the_recovery_are_wired_together_or_not_at_all).lstrip())
    body = tree.body[0].body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    called = {n.func.id for stmt in body for n in ast.walk(stmt)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "qualified_call_counts" in called, (
        "the cutover guard does not actually count calls -- it would pass on any codebase")
    assert _SPINE.is_file(), "spine.py has moved; this guard is addressing a file that is not there"


# ---------------------------------------------------------------------------------------------
# ⛔ the recovery's CONTRACT, provable without a database
# ---------------------------------------------------------------------------------------------
#
# `tests/test_delivery_spine.py` gives `recover_expired_claims` its first behavioural tests, against
# real PostgreSQL — the spine's SQL uses `for update skip locked` and a partial-index `on conflict`,
# which a fake cannot model. ⛔ Those tests SKIP wherever no database is configured, and this
# checkout is one of those places: they are written and have not been run here.
#
# So the three predicates those tests depend on are asserted structurally too. A behavioural test
# that skips everywhere it is run is not a guard, and **a skip is not a pass.**

def _recovery_sql() -> str:
    import inspect
    from genios_engine.deliver import spine
    return " ".join(inspect.getsource(spine.recover_expired_claims).split()).lower()


def test_the_recovery_only_touches_an_attempt_with_no_outcome() -> None:
    """⛔ `delivered` must never become `unknown`: overwriting a known outcome turns a successful
    send into an ambiguity. The predicate is `settled_at is null`, and it is load-bearing."""
    sql = _recovery_sql()
    assert "a.settled_at is null" in sql
    assert "a.outcome = 'started'" in sql
    assert "outcome = 'unknown'" in sql, "the recovery must write `unknown`, not `failed`"


def test_the_recovery_is_bounded_by_the_lease_and_not_by_the_clock_alone() -> None:
    """A worker inside its lease owns its attempt. Without the `claim_expires_at` bound the recovery
    would mark every in-flight attempt `unknown` on the next tick."""
    sql = _recovery_sql()
    assert "d.claim_expires_at is not null" in sql
    assert "d.claim_expires_at < :at" in sql


def test_the_recovery_settles_what_it_recovers() -> None:
    """A recovered attempt must not be recoverable twice, or the count is meaningless."""
    assert "settled_at = :at" in _recovery_sql()


def test_no_tautology_can_neutralise_the_recovery() -> None:
    """⛔ The M1 mutation shape, applied to the recovery's own SQL rather than the receipt's."""
    sql = _recovery_sql()
    for poison in ("and false", "or true", "and true", "where false", "where true", "1=1"):
        assert poison not in sql, f"the recovery predicate is neutralised by {poison!r}"


def test_the_recovery_still_joins_on_the_fence_and_the_receipt_still_does_not() -> None:
    """⛔ THE ASYMMETRY, ASSERTED AS A PAIR — because it is only correct as a pair.

    The recovery joins `a.claim_token = d.fence_token`, so it can only reach orphans whose row has
    not yet been reclaimed. That is recorded rather than fixed: changing it is a behaviour change on
    a path nobody runs. The receipt is therefore deliberately fence-free, so the
    permanently-unrecoverable cases are still COUNTED even though they cannot be recovered.

    If somebody fixes the recovery's join, this test fails and says so — which is the point.
    """
    assert "a.claim_token = d.fence_token" in _recovery_sql(), (
        "the recovery's fence join has changed -- that may be an improvement, and if so the "
        "receipt's fence-independence rationale and test_an_attempt_under_a_different_fence_is_"
        "not_recovered both need rewriting")
    assert "fence_token" not in _receipt().sql
