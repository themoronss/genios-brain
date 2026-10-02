r"""The inbox landed. The `kind` did not — and the rows are read and dropped on the floor.

⛔ WHAT WAS WRONG. `unit_preference_learning` and `unit_temporary_memory` both returned `[]` with
the docstring *"Empty until the inbox lands"*, and `orchestrator.run_learning` justified its
unconsumed counter with *"Empty at both ends today, so it costs nothing — **but the day something
starts writing to that table**, rows would be read and dropped on the floor with no counter moving
anywhere."*

⛔⛔ **That day had already come.** Measured 2026-10-02:

    migrations/0046_l6_learning_hardening.sql   learning_event_inbox — "trusted structured
                                                events/memory, idempotent, with a lease"
    reason/moments/store.record_feedback        ⛔ INSERTS a row for every moment-feedback action
    api/moment_routes.py:746                    ⛔ reached in PRODUCTION
    feedback/store.py                           loaded into EVERY weekly batch as `batch.inbox`
    feedback/units.py                            ⛔ NO unit references it
    orchestrator.run_learning                    counts the rows it is about to drop as
                                                 `inbox_unconsumed`, into `learning_runs.counts`

⛔ THE GAP IS A `kind`, NOT A TABLE. Every row written today carries
`payload.kind == "moment_feedback"` — a card action, not an explicit first-person instruction with
a subject, a scope and exceptions. **A table is a migration; a `kind` is a SURFACE where a founder
states a preference**, and there is none. That decides who can close it.

⛔ AND EVERYTHING DOWNSTREAM OF `unit_temporary_memory` IS ALREADY BUILT. The Atlas's worked example
— *"Pause outreach for seven days"* (`L7-18`) — needs `LearningTarget.RUNTIME`, `govern()` routing
Runtime to `TEMPORARY`, `publish_runtime` writing `temporary_memories` with a `NOT NULL expires_at`,
`preflight`'s three expiry checks, and `expire_leases`. **All five exist**, and the inbox even
carries a `lease_until` column for exactly this. **The missing input is the whole of the gap.**

⛔ SO THE COUNTER GOT A READER, AND IT IS THIS LAYER'S FIRST CORRECTNESS RECEIPT. Measured in the
re-crosscheck: `feedback/` had **four receipts and all four were PRESENCE checks** — every one
satisfied by a single successful tick. `inbox_unconsumed` was written into `learning_runs.counts`
and read by nothing. *The reader is half the unit.*

⛔ AND THE CLAIM GUARDS THE VISIBILITY, NOT THE DROP. `inbox_unconsumed > 0` is the KNOWN state of a
declared gap, and `platform/receipts.py`'s own rule applies: *a gate that is always red is a gate
nobody reads; the claim is the one that is true today and false when it gets worse.*
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import re

import pytest

from genios_engine.contracts.learning import LearningTarget
from genios_engine.feedback import orchestrator as O
from genios_engine.feedback import target_policy as T
from genios_engine.platform.receipts import receipts

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_ENGINE = _ROOT / "genios_engine"
_INBOX = "learning_event_inbox"
_CLAIM = "no completed learning run hides whether it dropped inbox rows"

#: The old, stale sentence. Both files now QUOTE it in order to correct it, so every guard below
#: checks ATTRIBUTION rather than presence — ⛔ the lesson `S2` paid for, where asserting a false
#: phrase was absent failed on the correction that quoted it.
_STALE = "Empty until the inbox lands"
_STALE_PREMISE = "Empty at both\n    # ends today"
_MARKERS = ("CORRECTED", "said", "until 2026-10-02", "no longer true")


def _receipt():
    found = [r for r in receipts(None) if r.claim == _CLAIM]
    assert len(found) == 1, f"expected exactly one receipt claiming {_CLAIM!r}, found {len(found)}"
    return found[0]


def _src(rel: str) -> str:
    return (_ENGINE / rel).read_text(encoding="utf-8")


# =============================================================================================
# 1 · the layer's first correctness receipt
# =============================================================================================

def test_the_receipt_is_an_l7_gate_that_can_fail() -> None:
    """⛔ *A receipt that cannot fail is not a gate.* Zero passes; one does not."""
    receipt = _receipt()
    assert receipt.layer == "L7"
    assert receipt.expect(0) is True
    assert receipt.expect(1) is False
    assert receipt.fleet_wide is False, "this is a per-tenant question"


def test_feedback_is_no_longer_a_layer_with_zero_correctness_receipts() -> None:
    """⛔ THE FINDING THIS CLOSES. The re-crosscheck measured `feedback/` at **4 receipts, all four
    presence checks** — every one satisfied by a single successful tick, so a loop that runs weekly
    and writes four append-only ledgers could be entirely wrong and pass all of them.

    ⛔ Asserted as a floor, not an equality: a later step adding a second correctness receipt must
    not fail this."""
    l7 = [r for r in receipts(None) if r.layer == "L7"]
    correctness = [r for r in l7 if r.expect(0) is True]
    presence = [r for r in l7 if r.expect(0) is False]
    assert len(correctness) >= 1, "feedback/ is back to presence checks only"
    assert _CLAIM in {r.claim for r in correctness}
    assert len(presence) >= 4, "a presence receipt was removed rather than added to"


def test_the_receipt_reads_the_counts_column() -> None:
    """⛔ `learning_runs.counts` was written by `run_learning` and read by nothing: the layer's
    other `learning_runs` receipt asks only *'has it run?'*. This is its first reader."""
    sql = " ".join(_receipt().sql.split())
    assert "learning_runs" in sql
    assert "counts->>'inbox_unconsumed'" in sql
    assert "status = 'completed'" in sql, (
        "a claimed-but-unfinished run has no counts yet and must not be read as hiding them")


def test_the_claim_guards_the_visibility_and_not_the_drop() -> None:
    """⛔ `inbox_unconsumed > 0` is the DECLARED gap, not a regression, so a receipt on the drop
    itself would be red on every tenant with any moment feedback — and `platform/receipts.py`'s own
    rule is *a gate that is always red is a gate nobody reads.* The claim is about the COUNT being
    recorded at all."""
    sql = " ".join(_receipt().sql.split())
    assert "is null" in sql, "the claim must be about a MISSING count, not a non-zero one"
    assert "> 0" not in sql and "!= 0" not in sql
    assert "inbox_unconsumed" in _receipt().detail


# =============================================================================================
# 2 · ⛔ the chain — the inbox is written, loaded, and consumed by nothing
# =============================================================================================

def test_the_inbox_table_exists() -> None:
    sql = (_ROOT / "migrations" / "0046_l6_learning_hardening.sql").read_text(encoding="utf-8")
    assert re.search(rf"create table if not exists {_INBOX}\b", sql, re.I)


def test_the_inbox_carries_a_lease_column_for_a_dated_directive() -> None:
    """⛔ The column that makes `unit_temporary_memory`'s input representable the day it arrives."""
    sql = (_ROOT / "migrations" / "0046_l6_learning_hardening.sql").read_text(encoding="utf-8")
    block = sql[sql.index(f"create table if not exists {_INBOX}"):]
    block = block[:block.index(");")]
    for column in ("payload", "lease_until", "observed_at", "actor", "source_ref"):
        assert re.search(rf"^\s*{column}\s", block, re.M), column


def test_the_inbox_has_a_production_writer() -> None:
    """⛔ This is what made the orchestrator's *'empty at both ends'* premise stale."""
    assert re.search(rf"insert into {_INBOX}\b", _src("reason/moments/store.py"), re.I)
    assert "record_feedback" in _src("api/moment_routes.py"), (
        "the inbox writer is no longer reachable from a route — re-measure the premise")


def test_the_inbox_is_loaded_into_every_batch() -> None:
    assert _INBOX in _src("feedback/store.py")
    assert "inbox" in inspect.getsource(O.run_learning)


def test_no_analysis_unit_consumes_the_inbox() -> None:
    """⛔ The other half of the finding, asserted so the day a unit starts reading `batch.inbox`
    this test fails and the declaration is updated deliberately rather than going stale.

    ⛔⛔ THIS TEST FAILED ON CORRECT CODE THE FIRST TIME IT RAN, for the third instance of the same
    class in one session. It read `assert "batch.inbox" not in units` — and the corrected docstring
    I had just written **explains** that the inbox is *"loaded into every weekly batch as
    `batch.inbox`"*. **A docstring that explains a gap contains the words of the gap.**

    ⛔ `S2` learned *check attribution, not presence* for PROSE. This is the sharper form:
    **a claim about CODE must be checked against the AST, not against the text.** An attribution
    window would also have worked here and would have been the wrong tool — the question is not
    *"who said this"* but *"does any unit read this attribute"*, and only the AST answers it.
    """
    tree = ast.parse(_src("feedback/units.py"))
    readers = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for ref in ast.walk(node):
            if (isinstance(ref, ast.Attribute) and ref.attr == "inbox"
                    and isinstance(ref.value, ast.Name)):
                readers.append(f"{node.name} reads {ref.value.id}.inbox")
            # `getattr(batch, "inbox", ())` is the other way to reach it — the orchestrator uses
            # exactly that form, so a guard that only knew about attribute access would miss it.
            if (isinstance(ref, ast.Call) and isinstance(ref.func, ast.Name)
                    and ref.func.id == "getattr" and len(ref.args) >= 2
                    and isinstance(ref.args[1], ast.Constant) and ref.args[1].value == "inbox"):
                readers.append(f"{node.name} getattrs inbox")
    assert readers == [], f"a unit now consumes the inbox: {readers}"


def test_the_unconsumed_count_is_persisted() -> None:
    """⛔ A counter nobody stores cannot be read by a receipt. It goes into `learning_runs.counts`."""
    src = inspect.getsource(O.run_learning)
    assert "inbox_unconsumed" in src
    assert '"inbox_unconsumed": inbox_unconsumed' in src
    assert "counts = cast(:c as jsonb)" in src


# =============================================================================================
# 3 · ⛔ the gap is a `kind`, not a table
# =============================================================================================

def test_the_only_kind_written_today_is_a_card_action() -> None:
    """⛔ What decides who can close this. Every row carries `kind: "moment_feedback"` — a card
    action, not an explicit first-person instruction with a subject, a scope and exceptions."""
    src = _src("reason/moments/store.py")
    assert '"kind": "moment_feedback"' in src
    kinds = set(re.findall(r'"kind":\s*"([a-z_]+)"', src))
    assert kinds == {"moment_feedback"}, f"a new inbox kind appeared: {sorted(kinds)}"


def test_the_inbox_has_exactly_one_writer_in_the_engine() -> None:
    """⛔ If a second writer appears with a different `kind`, the declaration's reason — *'the gap
    is a `kind`, not a table'* — may no longer hold."""
    writers = [str(p.relative_to(_ROOT)) for p in _ENGINE.rglob("*.py")
               if re.search(rf"insert into {_INBOX}\b",
                            p.read_text(encoding="utf-8", errors="ignore"), re.I)]
    assert writers == ["genios_engine/reason/moments/store.py"], writers


def test_there_is_no_preference_target() -> None:
    """⛔ A bounded personal preference has no target of its own — it would arrive as `BEHAVIOR`
    with a resolved `subject_principal`. The sink exists; the input does not."""
    assert "PREFERENCE" not in {m.name for m in LearningTarget}
    assert {m.name for m in LearningTarget} == {
        "ORGANIZATION", "BEHAVIOR", "ADAPTIVE", "RUNTIME", "METRICS", "KNOWLEDGE_SUGGESTION"}


# =============================================================================================
# 4 · ⛔ everything downstream of the temporary-memory unit already exists
# =============================================================================================

@pytest.mark.parametrize("what,rel,needle", [
    ("the RUNTIME target", "contracts/learning.py", r'RUNTIME = "runtime"'),
    ("govern routes RUNTIME to TEMPORARY", "feedback/governance.py",
     r"LearningState\.TEMPORARY, \"runtime_lease\""),
    ("publish_runtime writes temporary_memories", "feedback/publisher.py",
     r"insert into temporary_memories"),
    ("preflight bounds the expiry", "feedback/governance.py", r"runtime_ttl_over_ceiling"),
    ("expire_leases retires them", "feedback/brain_pipeline.py", r"def expire_leases"),
])
def test_the_lease_machinery_is_complete(what: str, rel: str, needle: str) -> None:
    """⛔ Five pieces, all built. **The missing input is the whole of the gap** — which is why `S5`
    is a declaration and not a build."""
    assert re.search(needle, _src(rel)), f"{what} is gone from {rel}"


def test_the_expiry_is_not_null_at_the_database() -> None:
    """The one property the Adaptive brain has that the other two do not."""
    sql = (_ROOT / "migrations" / "0045_l6_learning.sql").read_text(encoding="utf-8")
    block = sql[sql.index("create table if not exists temporary_memories"):]
    block = block[:block.index(");")]
    line = next(ln for ln in block.splitlines() if ln.strip().startswith("expires_at"))
    assert "not null" in line.lower(), line


# =============================================================================================
# 5 · ⛔ the stale sentences survive only as quotations — S2's lesson, applied
# =============================================================================================

@pytest.mark.parametrize("rel", ["feedback/units.py", "feedback/target_policy.py"])
def test_the_stale_docstring_survives_only_as_a_quotation(rel: str) -> None:
    """⛔ `S2` asserted a false phrase was ABSENT and failed on the correction that quoted it —
    *a grep for a known-false phrase matches the record of its own correction.* So this checks
    ATTRIBUTION: the phrase may appear, and every occurrence must sit near a marker identifying it
    as the old wording. A relapse adds an unmarked occurrence and fails."""
    lines = _src(rel).splitlines()
    unattributed = []
    for i, line in enumerate(lines):
        if _STALE not in line:
            continue
        window = "\n".join(lines[max(0, i - 4):i + 5])
        if not any(marker in window for marker in _MARKERS):
            unattributed.append(i + 1)
    assert unattributed == [], (
        f"{rel}: the stale claim is asserted, not quoted, at line(s) {unattributed} — "
        "the inbox landed")


def test_both_units_state_the_correction_in_their_own_words() -> None:
    """The positive half: forbidding the stale sentence proves nothing if the true one is absent."""
    units = _src("feedback/units.py")
    assert "THE INBOX LANDED" in units.upper()
    assert "moment_feedback" in units
    assert "the gap is a `kind`, not a table" in units.lower() or \
           "THE GAP IS A `kind`, NOT A TABLE" in units


def test_the_orchestrator_premise_is_corrected() -> None:
    """⛔ *'Empty at both ends today'* was the premise the counter's whole justification rested on,
    and the comment's own prediction is what happened."""
    src = inspect.getsource(O.run_learning)
    assert "CORRECTED 2026-10-02" in src
    assert "record_feedback" in src
    assert "moment_routes.py:746" in src


def test_both_stub_declarations_name_a_mover() -> None:
    """⛔ *A silence with no named mover is an undeclared silence with paperwork.* `UNIT_TARGETS`
    has no mover column, so for these two the mover lives inside the reason — and it must be
    there."""
    for unit in ("unit_preference_learning", "unit_temporary_memory"):
        declared, why = T.UNIT_TARGETS[unit]
        assert declared is None, unit
        assert "MOVES WHEN" in why, f"{unit} declares no mover"
        assert _INBOX in why or "inbox" in why, f"{unit} does not name the inbox"


def test_the_declaration_refuses_a_model_as_the_answer() -> None:
    """⛔ Recorded so nobody closes this by pointing an LLM at free text. The Atlas: *"Adding a
    model directly to empty units would produce eloquent ungrounded preferences. First wire typed
    evidence; then use a model narrowly where language ambiguity is irreducible."*"""
    why = T.UNIT_TARGETS["unit_preference_learning"][1]
    assert "First wire typed evidence" in why
    assert "ungrounded preferences" in why


def test_neither_stub_became_a_delegation() -> None:
    """⛔ `adaptive_lease` writes `unit_temporary_memory`'s sink but INFERS its input from card
    verdicts; this unit wants a founder to SAY one. **Same sink, different input**, so recording it
    as a delegation would be a lie about which capability exists."""
    assert "unit_temporary_memory" not in T.DELEGATED
    assert "unit_preference_learning" not in T.DELEGATED
    assert T.undelegated_silent_units() == ()


# =============================================================================================
# 6 · the units still propose nothing, and that is the declared state
# =============================================================================================

def test_both_units_still_return_an_empty_list() -> None:
    tree = ast.parse(_src("feedback/units.py"))
    for name in ("unit_preference_learning", "unit_temporary_memory"):
        node = next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == name)
        assert T._returns_only_empty(node), f"{name} now proposes — update its declaration"
        assert T._targets_in(node) == frozenset(), f"{name} now names a target"
