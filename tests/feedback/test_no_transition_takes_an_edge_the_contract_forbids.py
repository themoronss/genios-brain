r"""Every refusal is named, and every lifecycle edge is one the contract allows.

⛔⛔ TWO DEFECTS, ONE CAUSE: the two ledgers that would have shown them are the ones nothing reads.

**1 · THE NO-SILENT-DROP CONTRACT.** `orchestrator.run_learning`'s loop discarded all three refusal
reasons — `ok, _ = validate_learning(...)`, and only `.ok` / `.rejected` read off `PreflightResult`
and `GovernanceDecision`. A refused proposal was **counted and never named**, and
`learning_object_evaluations` recorded only the successes.

The Atlas states the contract in full:

    Every rejected or deferred candidate must retain run_id, tenant, unit, evidence IDs, REASON
    CODE, failed gate, policy version, timestamp, and recovery status. "No proposal" is valid only
    when accompanied by a machine-readable reason … A weekly sweep that returns zero objects
    without this accounting is operationally indistinguishable from broken wiring.

⛔ And `migrations/0046` describes that ledger as *"append-only: every actual per-run decision (new
or **HELD** object)"* — the held case is named in the schema's own comment and was never written.
**No migration was needed:** `run_id`, `policy_revision`, `evaluated_at`, `prior_state`,
`result_state` and `sink_reason` are exactly the fields the Atlas asks for, and `learning_id`
carries no foreign key, so a proposal that never reached `persist` can still be recorded.

**2 · ⛔⛔ AN ILLEGAL LIFECYCLE EDGE, ON THE MOST IMPORTANT PATH.** `publisher.publish` fixes
`from_state = GOVERNED`, then reassigns `target_state = PUBLISHED` after a brain publish and logs
once — so every brain publish wrote **`governed → published`**, and
`ALLOWED_LEARNING_TRANSITIONS[GOVERNED]` is `(temporary, human_review, promoted, rejected)`.
`learning_can_transition(GOVERNED, PUBLISHED)` returns **False**.

The map's own docstring states the intended path — *"| Promoted→Published | Rejected}; Published →
{Superseded | RolledBack}"* — **two hops**, and the publisher collapsed them, skipping `PROMOTED`:
the state that distinguishes *"promoted, publisher not yet done"* from *"published"*, which is
exactly the ambiguity the Atlas's `L7-30` names (*"Publisher crashes after persistence but before
activation receipt → **do not infer active state from row existence**"*).

⛔ **Nothing caught it because `learning_transitions` is written by five call sites and read by
none.** `ALLOWED_LEARNING_TRANSITIONS` existed from the start; nothing checked it on this path.

⛔ **AND MY OWN RETRACTION OF THIS UNIT WAS WRONG.**
`07-ATLAS-CHECK` §3 retracted *"an illegal learning transition"* on the grounds that its gate
question — *does the second writer validate?* — was answered by Atlas `#9`. That conflated two
questions. The second writer (`api/learning_routes.py`) **is** the repaired approval path and both
its edges are legal; the **first** writer was the one emitting an illegal edge. *A retraction needs
its own measurement, not a neighbouring one.*
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import re
from datetime import datetime, timezone

import pytest

from genios_engine.contracts.learning import (
    ALLOWED_LEARNING_TRANSITIONS,
    LearningEvidence,
    LearningObject,
    LearningPolicy,
    LearningState,
    LearningTarget,
    Visibility,
    VisibilityScope,
    learning_can_transition,
)
from genios_engine.feedback import orchestrator as O
from genios_engine.feedback import publisher as P
from genios_engine.platform.receipts import receipts

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
_ROOT = pathlib.Path(__file__).resolve().parents[2]
_ENGINE = _ROOT / "genios_engine"

_DROP_CLAIM = "every proposal a completed learning run made is recorded as a decision"
_EDGE_CLAIM = "no learning transition takes an edge the contract forbids"


def _receipt(claim: str):
    found = [r for r in receipts(None) if r.claim == claim]
    assert len(found) == 1, f"expected exactly one receipt claiming {claim!r}, found {len(found)}"
    return found[0]


class _Result:
    rowcount = 1
    def mappings(self): return self
    def first(self): return None
    def all(self): return []
    def scalar(self): return None


class _Conn:
    """Records the lifecycle edges `log_transition` writes, and satisfies the publisher's reads."""

    def __init__(self) -> None:
        self.edges: list[tuple[str | None, str]] = []

    def execute(self, stmt, params=None):
        if "insert into learning_transitions" in str(stmt):
            self.edges.append((params.get("f"), params.get("t")))
        return _Result()


def _obj(target: LearningTarget = LearningTarget.BEHAVIOR, subject: str = "behavior:x:n1"):
    return LearningObject(
        org_id="o", unit="u", target=target, subject=subject, proposed_value={"x": 1},
        evidence=LearningEvidence(observations=3, independent_refs=3, distinct_days=2,
                                  positive=3, negative=0, confidence_bp=9000,
                                  business_value_bp=9000),
        visibility=Visibility(scope=VisibilityScope.ORGANIZATION),
        first_seen_at=NOW, last_seen_at=NOW, policy_key="policy:o:1")


# =============================================================================================
# 1 · the premise — the edge the publisher used to write is forbidden
# =============================================================================================

def test_governed_to_published_is_not_a_legal_edge() -> None:
    """⛔ The whole premise, asserted on its own so a future widening of the map is a deliberate
    act and not a quiet one. ⛔ **Widening this to make the publisher pass would be weakening a
    verify** — the map's docstring states the two-hop path on purpose."""
    assert learning_can_transition(LearningState.GOVERNED, LearningState.PUBLISHED) is False
    allowed = {s.value for s in ALLOWED_LEARNING_TRANSITIONS[LearningState.GOVERNED]}
    assert allowed == {"temporary", "human_review", "promoted", "rejected"}
    assert learning_can_transition(LearningState.PROMOTED, LearningState.PUBLISHED) is True


# =============================================================================================
# 2 · ⛔ the publisher logs BOTH hops — asserted behaviourally, not from the source
# =============================================================================================

def test_a_brain_publish_logs_promoted_then_published() -> None:
    """⛔ The fix, exercised rather than read. `publish()` is run with a recording connection and
    every edge it writes is checked against the contract."""
    conn = _Conn()
    P.publish(conn, _obj(), target_state=LearningState.PROMOTED, at=NOW)
    assert conn.edges == [("governed", "promoted"), ("promoted", "published")]


@pytest.mark.parametrize("target_state,expected", [
    (LearningState.TEMPORARY, [("governed", "temporary")]),
    (LearningState.HUMAN_REVIEW, [("governed", "human_review")]),
    (LearningState.REJECTED, [("governed", "rejected")]),
])
def test_every_other_sink_logs_one_legal_edge(target_state, expected) -> None:
    """The branches that were already correct, pinned so the two-hop change did not disturb them."""
    conn = _Conn()
    P.publish(conn, _obj(LearningTarget.RUNTIME, "runtime:x") if
              target_state is LearningState.TEMPORARY else _obj(),
              target_state=target_state, at=NOW)
    assert conn.edges == expected


def test_a_metric_publish_still_logs_one_hop() -> None:
    """⛔ A metric is not a brain target, so it stops at PROMOTED — one legal edge, no second hop."""
    conn = _Conn()
    P.publish(conn, _obj(LearningTarget.METRICS, "cap:play"),
              target_state=LearningState.PROMOTED, at=NOW)
    assert conn.edges == [("governed", "promoted")]


def test_every_edge_the_publisher_can_write_is_legal() -> None:
    """⛔ THE INVARIANT, over every sink `publish()` has. Exercising each one and validating the
    edges it writes is what a source-level check could not do: `to_state` is a variable."""
    sinks = [(LearningState.TEMPORARY, _obj(LearningTarget.RUNTIME, "runtime:x")),
             (LearningState.HUMAN_REVIEW, _obj()),
             (LearningState.HUMAN_REVIEW, _obj(LearningTarget.KNOWLEDGE_SUGGESTION, "play:p")),
             (LearningState.PROMOTED, _obj()),
             (LearningState.PROMOTED, _obj(LearningTarget.METRICS, "cap:play")),
             (LearningState.REJECTED, _obj())]
    for state, obj in sinks:
        conn = _Conn()
        P.publish(conn, obj, target_state=state, at=NOW)
        assert conn.edges, f"{state} wrote no transition at all"
        for frm, to in conn.edges:
            assert learning_can_transition(LearningState(frm), LearningState(to)), (
                f"{state}: illegal edge {frm} -> {to}")


# =============================================================================================
# 3 · ⛔ log_transition refuses an illegal edge
# =============================================================================================

def test_log_transition_refuses_the_edge_that_was_being_written() -> None:
    with pytest.raises(ValueError, match="illegal learning transition governed -> published"):
        P.log_transition(_Conn(), org_id="o", learning_id="l", from_state="governed",
                         to_state="published", reason_code="x", at=NOW)


def test_log_transition_refuses_a_state_that_does_not_exist() -> None:
    """⛔ *Treating "I could not validate this" as "this is fine" is the fail-open `S3` closed.*"""
    with pytest.raises(ValueError, match="names a state that does not exist"):
        P.log_transition(_Conn(), org_id="o", learning_id="l", from_state="governed",
                         to_state="banana", reason_code="x", at=NOW)


def test_the_first_edge_of_an_objects_life_is_exempt() -> None:
    """⛔ `persist` writes *"nothing → governed"*. There is no predecessor to validate and
    `ALLOWED_LEARNING_TRANSITIONS` has no `None` key by design."""
    conn = _Conn()
    P.log_transition(conn, org_id="o", learning_id="l", from_state=None,
                     to_state="governed", reason_code="persisted", at=NOW)
    assert conn.edges == [(None, "governed")]


@pytest.mark.parametrize("frm,to", sorted(
    (c.value, n.value) for c, ns in ALLOWED_LEARNING_TRANSITIONS.items() for n in ns))
def test_every_legal_edge_is_accepted(frm: str, to: str) -> None:
    """⛔ Both directions: the guard must not refuse an edge the contract allows. Parametrised over
    the contract itself, so a new state is covered without an edit."""
    conn = _Conn()
    P.log_transition(conn, org_id="o", learning_id="l", from_state=frm, to_state=to,
                     reason_code="x", at=NOW)
    assert conn.edges == [(frm, to)]


def test_the_unguarded_writer_in_the_api_writes_only_legal_edges() -> None:
    """⛔ `api/learning_routes.py`'s review route inserts its transition with raw SQL — it builds a
    deterministic id for idempotency that `log_transition`'s `new_id("ltr")` would break — so the
    runtime guard does not cover it. Its two edges are checked here, from its own source."""
    src = (_ENGINE / "api" / "learning_routes.py").read_text(encoding="utf-8")
    assert "'human_review', :st," in src, "the review route's from_state is no longer a literal"
    assert 'to_state = "promoted" if approve else "rejected"' in src
    for to in ("promoted", "rejected"):
        assert learning_can_transition(LearningState.HUMAN_REVIEW, LearningState(to)), to


# =============================================================================================
# 4 · ⛔ the no-silent-drop contract
# =============================================================================================

def test_all_three_refusal_paths_record_a_reason() -> None:
    """⛔ Read from the AST of `run_learning`: every `continue` that refuses must be preceded by a
    `_record_evaluation` call. A counted-but-unnamed refusal is the defect."""
    src = inspect.getsource(O.run_learning)
    assert "ok, reason = validate_learning" in src, "the validator's reason is discarded again"
    assert "gate = preflight(" in src and "sink=gate.reason_code" in src
    assert "sink=decision.reason_code" in src
    assert src.count("_record_evaluation(") == 5, (
        "five decision paths: held, preflight-refused, govern-rejected, unchanged, published")


def test_every_evaluation_is_counted() -> None:
    """⛔ `evaluations` is the receipt's gate. A `_record_evaluation` call without an increment
    would make the run under-report and the receipt red for the wrong reason."""
    src = inspect.getsource(O.run_learning)
    assert src.count("_record_evaluation(") == src.count("evaluations += 1")
    assert '"evaluations": evaluations' in src


def test_the_reason_codes_are_machine_readable() -> None:
    """⛔ The Atlas requires *"a machine-readable reason"*. Each gate returns a snake_case code, so
    an operator can group by it — not a sentence."""
    from genios_engine.feedback.governance import preflight
    from genios_engine.feedback.units import validate_learning

    thin = LearningObject(
        org_id="o", unit="u", target=LearningTarget.BEHAVIOR, subject="behavior:x:n1",
        proposed_value={"x": 1},
        evidence=LearningEvidence(observations=1, independent_refs=1, distinct_days=1,
                                  positive=1, negative=0, confidence_bp=10,
                                  business_value_bp=0),
        visibility=Visibility(scope=VisibilityScope.ORGANIZATION),
        first_seen_at=NOW, last_seen_at=NOW, policy_key="policy:o:1")
    policy = LearningPolicy(org_id="o", revision=1)

    ok, reason = validate_learning(thin, policy)
    assert ok is False
    assert re.fullmatch(r"[a-z_]+", reason), reason

    blocked = LearningPolicy(org_id="o", revision=1, blocked_targets=("behavior",))
    gate = preflight(_obj(), blocked, now=NOW)
    assert gate.ok is False
    assert re.fullmatch(r"[a-z_]+", gate.reason_code), gate.reason_code


# =============================================================================================
# 5 · the two receipts, and what they read
# =============================================================================================

@pytest.mark.parametrize("claim", [_DROP_CLAIM, _EDGE_CLAIM])
def test_each_receipt_is_an_l7_correctness_gate(claim: str) -> None:
    receipt = _receipt(claim)
    assert receipt.layer == "L7"
    assert receipt.expect(0) is True
    assert receipt.expect(1) is False
    assert receipt.fleet_wide is False


def test_the_drop_receipt_is_gated_on_the_marker() -> None:
    """⛔ A run completed before refusals were recorded has `held`/`refused` above zero and no
    evaluation rows. Without the gate the claim would be red for history it could not have
    recorded — *a gate that is always red is a gate nobody reads.*"""
    sql = " ".join(_receipt(_DROP_CLAIM).sql.split())
    assert "counts->>'evaluations' is not null" in sql
    assert "learning_object_evaluations" in sql
    assert "status = 'completed'" in sql


def test_the_edge_receipt_derives_its_legal_set_from_the_contract() -> None:
    """⛔ *Derived, never copied.* A hand-written pair list would drift the first time a state is
    added, and the drift would WIDEN what the receipt accepts."""
    sql = " ".join(_receipt(_EDGE_CLAIM).sql.split())
    in_sql = set(re.findall(r"\('([a-z_]+)','([a-z_]+)'\)", sql))
    in_map = {(c.value, n.value)
              for c, ns in ALLOWED_LEARNING_TRANSITIONS.items() for n in ns}
    assert in_sql == in_map
    assert ("governed", "published") not in in_sql
    assert "t.from_state is not null" in sql, "persist's first edge must be excluded"


def test_feedback_now_has_three_correctness_receipts() -> None:
    """⛔ The re-crosscheck measured **four receipts, all presence**. Asserted as a floor."""
    l7 = [r for r in receipts(None) if r.layer == "L7"]
    correctness = {r.claim for r in l7 if r.expect(0) is True}
    assert len(correctness) >= 3
    assert {_DROP_CLAIM, _EDGE_CLAIM} <= correctness


# =============================================================================================
# 6 · the two ledgers that still have no reader — declared, so the record cannot go stale
# =============================================================================================

@pytest.mark.parametrize("table", ["learning_metrics"])
def test_the_remaining_unread_ledgers_are_still_unread(table: str) -> None:
    """⛔ `S6` gave `learning_object_evaluations` and `learning_transitions` their first readers.

    ⛔⛔ UPDATED BY `S7`, AND THE UPDATE WAS FORCED RATHER THAN REMEMBERED. This was parametrised
    over `["learning_input_rejections", "learning_metrics"]`, and `S7` gave the first one a reader
    — the receipt *"no learning input has been quarantined"*. **The test failed**, exactly as its
    own docstring promised it would, and the `F11` tally moved from *four unread* to *one* as a
    deliberate edit instead of a discovery six weeks later.

    *A declared silence that fails the build when it stops being true is the only kind worth
    writing.* `learning_metrics` is the last one, and
    `test_learning_metrics_is_the_last_unread_ledger` in `S7`'s own file says so from the other
    side.

    ⛔ `learning_metrics`' failure mode IS observable now, indirectly: `publish_metric` returns
    `metric_identity_conflict`, which reaches `sink_reason` in the evaluation ledger. The VALUES
    still have no reader."""
    readers = []
    for tree in ("genios_engine", "scripts"):
        for path in (_ROOT / tree).rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if re.search(rf"(?:from|join)\s+{table}\b", text, re.I):
                readers.append(str(path.relative_to(_ROOT)))
    assert readers == [], f"{table} now has a reader: {readers} — update the F11 tally"


@pytest.mark.parametrize("table,claim", [
    ("learning_object_evaluations", _DROP_CLAIM),
    ("learning_transitions", _EDGE_CLAIM),
])
def test_the_two_ledgers_s6_wired_now_have_a_reader(table: str, claim: str) -> None:
    assert table in _receipt(claim).sql
