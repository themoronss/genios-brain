r"""An empty prohibition list is a DECISION; a NULL one is an ABSENCE — and they are not the same.

⛔ WHAT WAS WRONG. `learning_policies.blocked_targets` and `.blocked_subject_prefixes` are nullable
`jsonb` (migration 0045), and `orchestrator`'s seed writes `cast('[]' as jsonb)` with this comment:

    Seeded EMPTY rather than NULL: an empty prohibition list is a decision ("nothing is
    blocked"), NULL is an absence. Keeping them distinct is what lets the guard below tell
    a deliberate empty policy from one that failed to load.

⛔ **There was no guard below.** `_as_tuple` returned `()` for `None`, for a dict, for a bare
string, and for a list of integers alike — so a tenant whose *"never learn about these targets"*
list failed to load was indistinguishable from a tenant who blocks nothing, and
`governance.preflight` reported `admitted` for the exact target they meant to forbid. **The
database kept the two apart and the load collapsed them one line later.**

⛔ AND `_as_tuple` COULD NOT KEEP THE PROMISE IN ITS OWN DOCSTRING. It said it was *"refusing to
silently invent an empty one"* and that treating a NULL as "nothing is blocked" is *"the failure
mode this whole field guards against"* — while returning `()` for exactly that. It received only
the value, never the revision, so **nothing in its signature made the promise keepable.** *A
docstring can promise a behaviour the signature makes impossible.*

⛔ THE ATLAS NAMES THIS AS A REQUIRED REPAIR (Layer 7 gap #10): *"unknown/malformed policy fields
block the run rather than defaulting to permissive empty tuples"*, with acceptance evidence
*"round-trip fixtures prove both block lists survive seed/load/restart and preflight rejects the
exact target/prefix under the loaded revision."*

⛔ TWO REFUSALS, FOR TWO DIFFERENT REASONS, AND BOTH ARE NEEDED:
  · `governance.preflight` — because **all three producers** reach the pipeline through it
    (`orchestrator.run_learning`, `brain_pipeline.admit_proposals`,
    `org_rule_ingest.run_org_discovery`), and only two of them pass through `run_learning`.
  · `orchestrator.run_learning` — because it stops the pass **before `_claim_week`**. ⛔ After the
    claim this would be WORSE than the fail-open it replaces: `on conflict (org_id, week_key) do
    nothing` means a claimed week stays claimed, so a policy row fixed on Tuesday would not be
    learned from until the following Monday. **A fail-closed placed after the claim converts a
    policy problem into a lost week.**

⛔ AND THE REFUSAL HAD TO BE MADE VISIBLE IN THE SAME UNIT. `run_learning_sweep` returned
`{orgs, passes, skipped}`, so a tenant who turned learning off, a tenant whose week was already
claimed, and a tenant whose transaction raised were **the same number**. A fail-closed nobody can
see is a silent stop. *The reader is half the unit*, and `skipped_by_reason` is that half.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
from datetime import datetime, timezone

import pytest

from genios_engine.contracts.learning import (
    PROHIBITIONS_ABSENT,
    PROHIBITIONS_LOADED,
    PROHIBITIONS_MALFORMED,
    PROHIBITIONS_STATES,
    LearningEvidence,
    LearningObject,
    LearningPolicy,
    LearningTarget,
    Visibility,
    VisibilityScope,
)
from genios_engine.feedback import orchestrator as O
from genios_engine.feedback.governance import preflight

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _obj(target: LearningTarget = LearningTarget.METRICS, subject: str = "cap:play"):
    return LearningObject(
        org_id="o", unit="u", target=target, subject=subject, proposed_value={"x": 1},
        evidence=LearningEvidence(observations=3, independent_refs=3, distinct_days=2,
                                  positive=3, negative=0, confidence_bp=9000,
                                  business_value_bp=9000),
        visibility=Visibility(scope=VisibilityScope.ORGANIZATION),
        first_seen_at=NOW, last_seen_at=NOW, policy_key="policy:o:1")


# =============================================================================================
# 1 · the resolver — every shape a jsonb column can hand back
# =============================================================================================

@pytest.mark.parametrize("value,expected_list,expected_state", [
    (["organization"],   ("organization",), PROHIBITIONS_LOADED),
    (["a", "b"],         ("a", "b"),        PROHIBITIONS_LOADED),
    ([],                 (),                PROHIBITIONS_LOADED),   # ⛔ a DECISION
    (None,               (),                PROHIBITIONS_ABSENT),   # ⛔ an ABSENCE
    ({"a": 1},           (),                PROHIBITIONS_MALFORMED),
    ("organization",     (),                PROHIBITIONS_MALFORMED),
    (0,                  (),                PROHIBITIONS_MALFORMED),
    ([1, 2],             (),                PROHIBITIONS_MALFORMED),
    ([""],               (),                PROHIBITIONS_MALFORMED),
    (["rule_", ""],      (),                PROHIBITIONS_MALFORMED),
])
def test_each_stored_shape_resolves_to_its_own_state(value, expected_list, expected_state) -> None:
    assert O._prohibition_list(value) == (expected_list, expected_state)


def test_an_empty_list_is_trusted_and_a_null_is_not() -> None:
    """⛔ THE DISTINCTION THE WHOLE UNIT EXISTS FOR, asserted on its own so a future edit that
    collapses the two fails here first and reads as the defect rather than as a detail."""
    assert O._prohibition_list([]) == ((), PROHIBITIONS_LOADED)
    assert O._prohibition_list(None) == ((), PROHIBITIONS_ABSENT)


def test_the_two_bad_shapes_fail_in_opposite_directions() -> None:
    """⛔ Why neither may be silently repaired. A non-string can never equal a target value, so a
    list of ints blocks NOTHING; `"x".startswith("")` is always True, so an empty prefix blocks
    EVERYTHING. The old code's `str(v) for v in value if v` turned the first into a quiet fail-open
    and dropped the second."""
    assert "organization" not in (1, 2)                     # a list of ints blocks nothing
    assert "any-subject".startswith("")                     # an empty prefix blocks everything
    assert O._prohibition_list([1, 2])[1] == PROHIBITIONS_MALFORMED
    assert O._prohibition_list([""])[1] == PROHIBITIONS_MALFORMED


@pytest.mark.parametrize("targets,prefixes,expected_state", [
    (["x"],  ["y"],       PROHIBITIONS_LOADED),
    ([],     [],          PROHIBITIONS_LOADED),      # ⛔ exactly what the seed writes
    (["x"],  None,        PROHIBITIONS_ABSENT),
    (None,   ["y"],       PROHIBITIONS_ABSENT),
    (["x"],  {"z": 1},    PROHIBITIONS_MALFORMED),
    (None,   {"z": 1},    PROHIBITIONS_MALFORMED),   # malformed is the worse of the two
])
def test_both_columns_take_the_worse_state(targets, prefixes, expected_state) -> None:
    _blocked, _prefix, state = O._prohibitions(targets, prefixes)
    assert state == expected_state


def test_an_untrusted_list_is_not_partially_usable() -> None:
    """⛔ When either column is bad, BOTH come back empty rather than handing over the half that
    loaded. The pass is blocked either way, and a half-populated policy is the shape somebody later
    reads as complete."""
    blocked, prefix, state = O._prohibitions(["organization"], None)
    assert (blocked, prefix) == ((), ())
    assert state == PROHIBITIONS_ABSENT


def test_the_unkeepable_helper_is_gone() -> None:
    """⛔ `_as_tuple` promised in its docstring exactly what it did not do. It is replaced rather
    than patched, because its signature — one value, no revision — made the promise impossible."""
    assert not hasattr(O, "_as_tuple"), "the helper whose docstring it could not honour is back"


# =============================================================================================
# 2 · the contract — the absence is representable, and nothing else is
# =============================================================================================

def test_the_default_policy_is_trusted() -> None:
    """A policy authored in code — including the protective seeded default — is trusted by
    construction. ⛔ Only a policy RECONSTRUCTED from a row can be untrustworthy."""
    p = LearningPolicy(org_id="o", revision=1)
    assert p.prohibitions_state == PROHIBITIONS_LOADED
    assert p.prohibitions_loaded is True


@pytest.mark.parametrize("state", sorted(PROHIBITIONS_STATES))
def test_every_declared_state_is_constructible(state: str) -> None:
    """⛔ The constructor must NOT refuse an untrusted policy: it has to be constructible in order
    to represent the failure. The refusal belongs at the gate, not at construction."""
    p = LearningPolicy(org_id="o", revision=1, prohibitions_state=state)
    assert p.prohibitions_loaded is (state == PROHIBITIONS_LOADED)


def test_an_unknown_state_is_refused() -> None:
    """An unknown state would make `prohibitions_loaded` lie in the permissive direction."""
    with pytest.raises(ValueError, match="unknown prohibitions_state"):
        LearningPolicy(org_id="o", revision=1, prohibitions_state="probably_fine")


def test_the_policy_identity_did_not_change() -> None:
    """⛔ `LearningPolicy` is not content-addressed — `policy_key` is derived from org and revision
    alone — which is why a field could be added at all. `LearningObject` is the hashed one, and a
    new member on its enums would change identities already minted."""
    assert LearningPolicy(org_id="o", revision=7).policy_key == "policy:o:7"
    assert LearningPolicy(org_id="o", revision=7,
                          prohibitions_state=PROHIBITIONS_ABSENT).policy_key == "policy:o:7"


# =============================================================================================
# 3 · preflight — the gate all three producers share
# =============================================================================================

@pytest.mark.parametrize("state", [PROHIBITIONS_ABSENT, PROHIBITIONS_MALFORMED])
def test_preflight_refuses_every_proposal_under_an_unloaded_policy(state: str) -> None:
    policy = LearningPolicy(org_id="o", revision=1, prohibitions_state=state)
    result = preflight(_obj(), policy, now=NOW)
    assert result.ok is False
    assert result.reason_code == f"policy_prohibitions_{state}"


def test_preflight_still_admits_under_a_loaded_policy() -> None:
    policy = LearningPolicy(org_id="o", revision=1)
    assert preflight(_obj(), policy, now=NOW).ok is True


def test_the_two_refusals_are_told_apart_by_name() -> None:
    """⛔ THE FAIL-OPEN THIS CLOSES, and the thing that makes the fix worth having. Under a loaded
    block list the refusal is the tenant's DECISION (`target_blocked`); under an unloaded one it is
    our ABSENCE (`policy_prohibitions_absent`). Both refuse — ⛔ **and before this change the
    second one ADMITTED.**"""
    blocked = LearningPolicy(org_id="o", revision=1, blocked_targets=("organization",))
    unloaded = LearningPolicy(org_id="o", revision=2, prohibitions_state=PROHIBITIONS_ABSENT)
    target = _obj(LearningTarget.ORGANIZATION, "org:icp")

    assert preflight(target, blocked, now=NOW).reason_code == "target_blocked"
    assert preflight(target, unloaded, now=NOW).reason_code == "policy_prohibitions_absent"


def test_the_prohibitions_gate_runs_before_the_block_list_checks() -> None:
    """⛔ ORDER, ASSERTED STRUCTURALLY. After the two checks below it, the gate would never be
    reached for an allowed target: an empty list admits, `preflight` returns `admitted`, and the
    refusal never happens. Measured from the source, not inferred from behaviour."""
    src = inspect.getsource(preflight)
    lines = src.splitlines()
    gate = next(i for i, ln in enumerate(lines) if "prohibitions_loaded" in ln)
    blocked = next(i for i, ln in enumerate(lines) if "blocked_targets" in ln)
    prefixes = next(i for i, ln in enumerate(lines) if "blocked_subject_prefixes" in ln)
    assert gate < blocked < prefixes, (
        "the prohibitions gate must precede both block-list checks")


def test_consent_is_still_checked_first() -> None:
    """A tenant who disabled learning gets `consent_disabled`, not a policy complaint — the two are
    different facts and the more fundamental one wins."""
    policy = LearningPolicy(org_id="o", revision=1, learning_enabled=False,
                            prohibitions_state=PROHIBITIONS_ABSENT)
    assert preflight(_obj(), policy, now=NOW).reason_code == "consent_disabled"


# =============================================================================================
# 4 · ⛔ run_learning — the check must come BEFORE the weekly claim
# =============================================================================================

def test_run_learning_blocks_before_it_claims_the_week() -> None:
    """⛔⛔ THE MOST IMPORTANT ASSERTION IN THIS FILE. `_claim_week` inserts
    `on conflict (org_id, week_key) do nothing`, so a claimed week stays claimed and every later
    tick answers `already_ran_this_week`. A fail-closed placed after the claim would convert a
    policy problem into a **lost week** — strictly worse than the fail-open it replaces.

    Asserted on the AST rather than by behaviour, because the harm only appears on the SECOND tick
    and no unit test would see it."""
    tree = ast.parse(inspect.getsource(O.run_learning))
    fn = tree.body[0]
    gate = next(n.lineno for n in ast.walk(fn)
                if isinstance(n, ast.Attribute) and n.attr == "prohibitions_loaded")
    claim = next(n.lineno for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == "_claim_week")
    assert gate < claim, (
        f"the prohibitions gate is at line {gate} and _claim_week at {claim} — a fail-closed after "
        "the claim burns the tenant's week")


def test_the_claim_is_still_idempotent_on_conflict() -> None:
    """⛔ The premise of the test above, asserted so it cannot rot. If the claim stopped being
    `do nothing` on conflict, the ordering argument would change and this file should be re-read."""
    src = inspect.getsource(O._claim_week)
    assert "on conflict (org_id, week_key) do nothing" in src


def test_the_skip_reason_names_the_state() -> None:
    """The returned reason distinguishes a legacy NULL from a bad write, because they are different
    problems: one needs a backfill, the other needs a writer fixed."""
    src = inspect.getsource(O.run_learning)
    assert 'f"policy_prohibitions_{policy.prohibitions_state}"' in src
    assert '"policy_revision": policy.revision' in src


# =============================================================================================
# 5 · ⛔ the reader — a refusal nobody can see is a silent stop
# =============================================================================================

class _FakeConn:
    def __enter__(self): return self
    def __exit__(self, *a): return False


class _FakeEngine:
    def begin(self): return _FakeConn()


def test_the_sweep_reports_why_each_tenant_was_skipped(monkeypatch) -> None:
    """⛔ Before this, `consent_disabled`, `already_ran_this_week` and a crashed tenant were the
    same number — so the new fail-closed would have been invisible."""
    outcomes = {
        "org_a": {"skipped": "consent_disabled"},
        "org_b": {"skipped": "already_ran_this_week"},
        "org_c": {"skipped": "policy_prohibitions_absent"},
        "org_d": {"org_id": "org_d", "proposals": 2},
    }
    monkeypatch.setattr(O, "learning_orgs", lambda engine: sorted(outcomes))
    monkeypatch.setattr(O, "run_learning", lambda c, *, org_id, now: outcomes[org_id])

    result = O.run_learning_sweep(_FakeEngine(), now=NOW)
    assert result["orgs"] == 4
    assert result["passes"] == 1
    assert result["skipped"] == 3
    assert result["skipped_by_reason"] == {
        "consent_disabled": 1, "already_ran_this_week": 1, "policy_prohibitions_absent": 1}


def test_a_crashed_tenant_is_not_reported_as_consent(monkeypatch) -> None:
    """⛔ The `except` still counts a crash as a skip — one tenant's failure is not the rest's — but
    it records the TYPE. `{"error": True}` hid a NameError in the executive sweep for 15 days."""
    def boom(c, *, org_id, now):
        raise RuntimeError("policy table is on fire")

    monkeypatch.setattr(O, "learning_orgs", lambda engine: ["org_x"])
    monkeypatch.setattr(O, "run_learning", boom)

    result = O.run_learning_sweep(_FakeEngine(), now=NOW)
    assert result["skipped"] == 1
    assert result["passes"] == 0
    assert result["skipped_by_reason"] == {"error:RuntimeError": 1}


def test_the_sweep_kept_its_existing_keys(monkeypatch) -> None:
    """⛔ `skipped_by_reason` is ADDITIVE. `api/routes.py` puts this dict straight into the
    heartbeat response, so removing or renaming a key would change what an operator reads."""
    monkeypatch.setattr(O, "learning_orgs", lambda engine: [])
    result = O.run_learning_sweep(_FakeEngine(), now=NOW)
    assert set(result) == {"orgs", "passes", "skipped", "skipped_by_reason"}


# =============================================================================================
# 6 · the storage the distinction depends on
# =============================================================================================

def test_the_seed_still_writes_an_empty_array_and_not_null() -> None:
    """⛔ If the seed ever wrote NULL, every seeded tenant's policy would load as `absent` and no
    tenant would ever learn. The fail-closed is only safe because the seed is explicit."""
    src = inspect.getsource(O.load_or_seed_policy)
    assert "cast('[]' as jsonb), cast('[]' as jsonb)" in src
    assert "blocked_targets=" in src, "loaded into the policy, not merely selected"


def test_both_columns_are_still_nullable_in_the_schema() -> None:
    """⛔ The absence has to be representable at the database too. A `not null default '[]'` would
    make `absent` unreachable — which would be fine, and would make this whole unit redundant, so
    it must not change silently underneath it."""
    sql = (_ROOT / "migrations" / "0045_l6_learning.sql").read_text(encoding="utf-8")
    for column in ("blocked_targets", "blocked_subject_prefixes"):
        line = next(ln for ln in sql.splitlines() if ln.strip().startswith(column))
        assert "jsonb" in line and "not null" not in line.lower(), line
