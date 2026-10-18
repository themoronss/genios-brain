r"""A seam we threw away is not a seam that had nothing — and the delivery seam was degraded forever.

⛔⛔ THREE DEFECTS IN ONE BLOCK, and the ledger that would have shown the first is the unread one.

**1 · A QUARANTINED SEAM WAS INDISTINGUISHABLE FROM AN EMPTY ONE.**
`feedback/store._read_optional_seam` catches a read that raises, records it in
`learning_input_rejections`, and returns `()`. Its own comment states the defect it half-fixed:

    `learning_input_rejections` exists (migration 0046) and its own comment calls it "sanitized
    isolation of a malformed/lineage-less input" — and nothing in the codebase ever wrote to it.
    So the layer's isolation ledger recorded nothing, and an input the system deliberately
    quarantined was indistinguishable from one that never arrived. That is the no-silent-drop
    contract failing in the one place built to uphold it.

⛔ **The WRITE was built and the READ never was**, and the return value stayed `()` — so the seam
arrived at `run_learning` identical to an empty one and `degraded_seams` reported both the same
way: *"no human has judged a card yet"* and *"the verdict table read raised and we threw it away"*
were one line.

The Atlas names it — **`L7-29`**: *"Sweep completes with every required input seam empty →
'Learning healthy' is reported for no-op execution → Mark degraded/insufficient-input → **Expose
per-seam freshness, coverage, and empty REASON** → **Empty canonical verdict seam breaches a
declared health SLO**."* And L5 learned the same shape one layer down: *a dead row cannot tell "we
chose not to send" from "we lost it".*

**2 · ⛔⛔ THE DELIVERY SEAM WAS REPORTED DEGRADED ON EVERY RUN, FOREVER.**
`degraded_seams` read `getattr(batch, "deliveries", ())` — and the field is **`delivery`**. The
default fired every time, so the seam was always listed and ⛔ **`degraded` was always True.**

> ⛔ **A flag that is always set is a flag nobody reads** — the same shape as `receipts.py`'s own
> *a gate that is always red is a gate nobody reads.*

⛔ **A `getattr` with a default converts a wrong attribute name into a plausible value.** On a
dataclass, `batch.delivery` would have raised `AttributeError` the first time it ran. The names now
live beside `LearningBatch` as `HEALTH_SEAMS` and this file asserts each one is a real field.

**3 · AND THE RATIO QUESTION ANSWERED ITSELF.** `08-PLAN-v2` planned a refusal-rate receipt over
`learning_input_rejections` once a denominator existed. ⛔ It already does, and **not there**:
`org_rule_discovery_runs.counters` holds `candidates`, `admitted`, `human_review`, `refused` and
`refused_<reason>` per run, in a table that **is** read. So the discovery route's accounting is
complete, `learning_input_rejections` is its per-candidate detail — and the gap was in the **other**
writer, the one that quarantines a batch seam.
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import re
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.feedback import orchestrator as O
from genios_engine.feedback import store as ST
from genios_engine.feedback import target_policy as T
from genios_engine.platform.receipts import receipts

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
SINCE = NOW - timedelta(days=28)

_QUARANTINE_CLAIM = "no learning input has been quarantined"
_LOST_CLAIM = "a completed learning run says which seams it lost, not only which were empty"


def _receipt(claim: str):
    found = [r for r in receipts(None) if r.claim == claim]
    assert len(found) == 1, f"expected exactly one receipt claiming {claim!r}, found {len(found)}"
    return found[0]


class _Scalar:
    def __init__(self, v): self._v = v
    def scalar(self): return self._v
    def mappings(self): return self
    def all(self): return []
    def __iter__(self): return iter(())


class _Conn:
    """Answers the existence probe, then raises on the seam read — the quarantine path.

    ⛔ A MISSING TABLE MAKES THE SEAM QUERY RAISE, because that is what PostgreSQL does. The first
    version of this double returned an empty result for a read of a table it had just said does not
    exist — so `test_a_table_that_does_not_exist_is_not_a_quarantine` passed for the wrong reason,
    and mutation `M4` (deleting the `_table_exists` guard entirely) **SURVIVED**. The double was
    kinder than the database, which made the test agree with a broken implementation.

    ⛔ *A test double that cannot fail the way production fails is a test that proves nothing.*
    """

    def __init__(self, *, exists: bool = True, raise_on: str | None = None) -> None:
        self.exists, self.raise_on = exists, raise_on
        self.rejections: list[tuple[str, str]] = []

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if "to_regclass" in sql:
            return _Scalar("public.x" if self.exists else None)
        if "insert into learning_input_rejections" in sql:
            self.rejections.append((params["seam"], params["code"]))
            return _Scalar(None)
        if "select * from" in sql:                      # the seam read itself
            if not self.exists:
                raise RuntimeError('relation does not exist')
            if self.raise_on and self.raise_on in sql:
                raise RuntimeError("column does not exist")
        return _Scalar(None)


# =============================================================================================
# 1 · ⛔ the typo guard — the seam names must be real fields
# =============================================================================================

def test_every_health_seam_is_a_real_batch_field() -> None:
    """⛔ THE GUARD THAT MAKES THE DEFECT IMPOSSIBLE. `degraded_seams` named `"deliveries"` and the
    field is `delivery`, so `getattr(..., ())` returned the default on every run."""
    fields = {f.name for f in dataclasses.fields(ST.LearningBatch)}
    missing = [s for s in ST.HEALTH_SEAMS if s not in fields]
    assert missing == [], f"health seams that are not LearningBatch fields: {missing}"


def test_the_delivery_seam_is_no_longer_degraded_when_it_has_rows() -> None:
    """⛔ The defect, exercised. One delivery row is enough to prove the old `getattr` default."""
    batch = ST.LearningBatch(org_id="o", since=SINCE, delivery=({"x": 1},))
    degraded = {name for name in ST.HEALTH_SEAMS if not getattr(batch, name)}
    assert "delivery" not in degraded
    assert degraded == {"outcomes", "feedback"}


def test_the_old_attribute_name_is_gone_from_the_orchestrator() -> None:
    """⛔ Checked on the AST of the health-seam expression rather than by grepping the file: this
    module's docstring quotes `"deliveries"` to explain the defect, and `units.py` legitimately uses
    the word as a `proposed_value` key. *A claim about code is checked against the code.*"""
    tree = ast.parse(inspect.getsource(O.run_learning))
    comprehension = next(n for n in ast.walk(tree) if isinstance(n, ast.SetComp))
    names = [c.value for c in ast.walk(comprehension)
             if isinstance(c, ast.Constant) and isinstance(c.value, str)]
    assert "deliveries" not in names, "the health-seam set names a field that does not exist"
    # And it reads the shared tuple rather than spelling the seams again.
    assert any(isinstance(n, ast.Name) and n.id == "HEALTH_SEAMS" for n in ast.walk(comprehension))


def test_a_degraded_run_is_still_detected() -> None:
    """Both directions: the fix must not make `degraded` unreachable."""
    batch = ST.LearningBatch(org_id="o", since=SINCE)
    assert {name for name in ST.HEALTH_SEAMS if not getattr(batch, name)} == set(ST.HEALTH_SEAMS)


# =============================================================================================
# 2 · ⛔ a quarantined seam is named, and a missing table is not one
# =============================================================================================

def test_a_raised_seam_read_is_recorded_and_named() -> None:
    conn = _Conn(raise_on="card_feedback_verdicts")
    quarantine: list[str] = []
    rows = ST._read_optional_seam(conn, "card_feedback_verdicts", "o", SINCE, "created_at",
                                  quarantine)
    assert rows == ()
    assert quarantine == ["card_feedback_verdicts"], "the caller is not told which seam was lost"
    assert conn.rejections and conn.rejections[0][0] == "card_feedback_verdicts"
    assert "RuntimeError" in conn.rejections[0][1], "the reason code must name what happened"


def test_a_table_that_does_not_exist_is_not_a_quarantine() -> None:
    """⛔ An absent seam is not a lost one. `card_feedback_verdicts` legitimately predates some
    deployments, and conflating the two would make the receipt red on a tenant whose schema is
    simply older."""
    conn = _Conn(exists=False)
    quarantine: list[str] = []
    assert ST._read_optional_seam(conn, "card_feedback_verdicts", "o", SINCE, "created_at",
                                  quarantine) == ()
    assert quarantine == []
    assert conn.rejections == []


def test_a_healthy_read_quarantines_nothing() -> None:
    conn = _Conn()
    quarantine: list[str] = []
    ST._read_optional_seam(conn, "learning_event_inbox", "o", SINCE, "observed_at", quarantine)
    assert quarantine == []


def test_the_batch_carries_which_seams_were_lost() -> None:
    """⛔ End to end through `load_batch`: the inbox read raises, and the batch says so."""
    conn = _Conn(raise_on="learning_event_inbox")
    batch = ST.load_batch(conn, org_id="o", now=NOW)
    assert batch.quarantined == ("learning_event_inbox",)
    assert batch.inbox == ()


def test_quarantined_is_sorted_so_two_runs_can_be_diffed() -> None:
    src = inspect.getsource(ST.load_batch)
    assert "quarantined=tuple(sorted(quarantine))" in src


def test_the_run_records_which_seams_it_lost() -> None:
    src = inspect.getsource(O.run_learning)
    assert '"quarantined_seams": sorted(batch.quarantined)' in src
    assert '"degraded_seams": sorted(degraded_seams)' in src, (
        "both must be present — one says empty, the other says lost")


# =============================================================================================
# 3 · the two receipts
# =============================================================================================

@pytest.mark.parametrize("claim", [_QUARANTINE_CLAIM, _LOST_CLAIM])
def test_each_receipt_is_an_l7_correctness_gate(claim: str) -> None:
    receipt = _receipt(claim)
    assert receipt.layer == "L7"
    assert receipt.expect(0) is True
    assert receipt.expect(1) is False
    assert receipt.fleet_wide is False


def test_the_quarantine_receipt_reads_the_isolation_ledger() -> None:
    """⛔ `learning_input_rejections`' first reader. Its WRITE was built with a comment naming the
    contract it upheld, and nothing ever asked it a question."""
    assert "learning_input_rejections" in _receipt(_QUARANTINE_CLAIM).sql


def test_the_quarantine_receipt_excludes_routine_discovery_refusals() -> None:
    """⛔ `org_rule_ingest.record_refusal` writes to the same table under
    `seam = "brains.org_discovery"` for every candidate the gate turns down — **routine, not an
    alarm**, and already counted per run in `org_rule_discovery_runs.counters`. Counting those
    would make this receipt red on healthy tenants."""
    sql = " ".join(_receipt(_QUARANTINE_CLAIM).sql.split())
    assert "brains.org_discovery" not in sql
    assert "j.seam in (" in sql


def test_the_quarantine_receipts_seam_list_is_derived() -> None:
    """⛔ *Derived, never copied.* A third optional seam must enter this query without an edit."""
    sql = " ".join(_receipt(_QUARANTINE_CLAIM).sql.split())
    in_sql = set(re.findall(r"'([a-z_]+)'", sql))
    assert in_sql == set(ST.QUARANTINABLE_SEAMS)
    assert ST.QUARANTINABLE_SEAMS == ("card_feedback_verdicts", "learning_event_inbox")


def test_the_lost_seam_receipt_is_gated_on_the_evaluations_marker() -> None:
    """⛔ A run that completed before either field existed is not judged against a contract it
    predates — `S6`'s marker does the same job here."""
    sql = " ".join(_receipt(_LOST_CLAIM).sql.split())
    assert "counts->>'evaluations' is not null" in sql
    assert "counts->>'quarantined_seams' is null" in sql
    assert "status = 'completed'" in sql


def test_the_org_filter_is_aliased_on_the_quarantine_receipt() -> None:
    """Both tables in scope carry `org_id`, so an unaliased filter would be ambiguous SQL."""
    sql = " ".join([r for r in receipts("org_x") if r.claim == _QUARANTINE_CLAIM][0].sql.split())
    assert "j.org_id = :org" in sql


# =============================================================================================
# 4 · ⛔ the measurement that shaped this unit, and the last unread ledger
# =============================================================================================

def test_the_discovery_route_already_counts_its_own_refusals() -> None:
    """⛔ Why `learning_input_rejections` is NOT where the discovery ratio belongs.
    `org_rule_discovery_runs.counters` holds the numerator and the denominator, and that table
    **is** read — by `already_discovered` and by the sweep's LEFT JOIN."""
    disc = (ST.__file__.rsplit("/", 2)[0] + "/packs/brains/org_discovery.py")
    src = open(disc, encoding="utf-8").read()
    for key in ("candidates", "admitted", "human_review", "refused"):
        assert f'"{key}"' in src, key
    ingest = (ST.__file__.rsplit("/", 1)[0] + "/org_rule_ingest.py")
    isrc = open(ingest, encoding="utf-8").read()
    assert "select 1 from org_rule_discovery_runs" in isrc, "the counters table is no longer read"
    assert "left join org_rule_discovery_runs" in isrc


def test_learning_metrics_is_the_last_unread_ledger() -> None:
    """⛔ `F11` measured four ledgers nothing reads. `S6` gave two readers, `S7` a third. ⛔ This
    asserts the remaining one so the tally is updated **deliberately rather than discovered.**"""
    import pathlib
    root = pathlib.Path(ST.__file__).resolve().parents[2]
    readers = []
    for tree in ("genios_engine", "scripts"):
        for path in (root / tree).rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"(?:from|join)\s+learning_metrics\b", text, re.I):
                readers.append(str(path.relative_to(root)))
    assert readers == [], f"learning_metrics now has a reader: {readers} — update the F11 tally"


def test_feedback_now_has_five_correctness_receipts() -> None:
    """⛔ The re-crosscheck measured **four receipts, all presence**. Asserted as a floor."""
    l7 = [r for r in receipts(None) if r.layer == "L7"]
    correctness = {r.claim for r in l7 if r.expect(0) is True}
    assert len(correctness) >= 5
    assert {_QUARANTINE_CLAIM, _LOST_CLAIM} <= correctness


# =============================================================================================
# 7 · ⛔ a cross-package guard: reset.py's reason for leaving Behavior alone must stay true
# =============================================================================================

def test_reset_does_not_claim_behaviour_has_no_live_content() -> None:
    """⛔⛔ `feedback/reset.py` justified not superseding the Behavior brain with *"`unit_behavior
    _evolution` … is presently an unwired stub that always returns `[]` — there is no live Behavior
    Brain content to decay."* **That was true when written and is false now**:
    `packs/brains/behavior_distill.distill` is 776 lines, proposes `LearningTarget.BEHAVIOR`, and is
    appended to the same weekly run by `brain_pipeline_proposals` (`S4`).

    ⛔ **A stale comment reads as a measurement, and the most expensive place for one is the
    sentence that explains why something was left undone.** The claim and the fact live in two
    different packages, so nothing tied them together until this test did.

    ⛔ Checked by ATTRIBUTION, not presence: the corrected docstring QUOTES the old sentence in
    order to say it is false — `S2`'s lesson. The stale claim may appear; every occurrence must sit
    near a marker identifying it as corrected."""
    import pathlib

    root = pathlib.Path(ST.__file__).resolve().parents[2]
    lines = (root / "genios_engine" / "feedback" / "reset.py").read_text(
        encoding="utf-8").splitlines()
    stale = "there is no live Behavior Brain content to decay"
    markers = ("CORRECTED", "NO LONGER TRUE", "was true when written")
    unattributed = [i + 1 for i, ln in enumerate(lines) if stale in ln
                    and not any(m in "\n".join(lines[max(0, i - 2):i + 12]) for m in markers)]
    assert unattributed == [], (
        f"reset.py asserts the stale justification at line(s) {unattributed} — "
        "behavior_distill is wired")

    # ⛔ And the premise, from the other package: if this ever stops being true, the paragraph
    # above becomes correct again and should be re-read rather than left corrected.
    assert T._proposes_something("unit_behavior_evolution") is False
    assert "unit_behavior_evolution" in T.DELEGATED
    producer, target, _why, _mover = T.DELEGATED["unit_behavior_evolution"]
    assert target == "BEHAVIOR" and "behavior_distill" in producer
