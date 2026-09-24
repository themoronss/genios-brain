"""L2-5 · the debts L2-2 and L2-3 deferred onto this step, paid — and in one place.

⛔ **L2-2 DEFERRED FOUR FIELDS AND A MIGRATION HERE**, for a reason it stated: *"A field with no
writer is the `started_at` mistake, so L2-2 and L2-5 ship together or L2-2 ships knowingly
empty."* **L2-5 is the writer.**

⛔ **AND L2-3 DEFERRED SLICE PERSISTENCE HERE**, for the same reason: *"the hash is stored, the
slice is not. A hash proves sameness and cannot reproduce the input — a fingerprint, not a
record."* Its only reader is a reasoner trace, which did not exist until now.

⛔ **THE SHAPE OF THE DEBT CHANGED, AND SAYING SO IS PART OF PAYING IT.** L2-2 assumed four
columns on `context_situations`. Measured: **v2 is never persisted as a row** — `publish_situation`
returns it in memory and only the admission RECEIPT is stored. And an interpretation has its own
lifecycle: it **expires** (`valid_until`) while the situation does not, it is re-made on the next
sweep, and a column would force one per situation and lose the history.

**So the home is a table, `situation_interpretations`, beside `situation_admission_decisions` —
the same pattern, for the same reason.** The four fields still land on v2, because
`proposal_gate` validates against `FIELD_CLAIMS` and a model cannot propose a field the contract
does not have.
"""
from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = pytest.mark.unit

MIGRATION = pathlib.Path("migrations/0183_situation_interpretations.sql")


# =================================================================================================
# L2-2's four fields — on v2, and classified, or the import-time guard fails
# =================================================================================================

@pytest.mark.parametrize("field", ["hypotheses", "implications", "reasoning_trace", "valid_until"])
def test_the_four_deferred_fields_exist_on_v2(field):
    from genios_engine.contracts.situation import BusinessSituationObject as V2

    assert field in V2.model_fields


def test_a_hypothesis_is_classified_as_hypothesised_and_nothing_else_is():
    """⛔ L2-2 created `ClaimState.HYPOTHESISED` and **nothing held one**. This is the field that
    makes the third claim state real rather than decorative."""
    from genios_engine.contracts.claim_state import FIELD_CLAIMS, ClaimState, fields_in

    assert FIELD_CLAIMS["hypotheses"].state is ClaimState.HYPOTHESISED
    assert fields_in(ClaimState.HYPOTHESISED) == frozenset({"hypotheses"})


def test_a_model_may_propose_a_hypothesis_and_an_implication():
    from genios_engine.contracts.claim_state import model_writable_fields

    assert {"hypotheses", "implications"} <= model_writable_fields()


def test_a_model_may_not_write_the_trace_or_the_expiry():
    """⛔ `reasoning_trace` points at the consult that produced the reading — **the gate mints it,
    not the model**, exactly as `EvidenceSpan.verified` may not be self-set. And `valid_until` is
    the GATE's, per L2-2's own table: *"an interpretation expires; a fact does not."*"""
    from genios_engine.contracts.claim_state import model_writable_fields

    assert not ({"reasoning_trace", "valid_until"} & model_writable_fields())


def test_the_totality_guard_still_holds_both_ways():
    from genios_engine.contracts import claim_state

    claim_state._check()


# =================================================================================================
# V-9 · the new interpretation fields owe a receipt like every other interpretation
# =================================================================================================

def test_a_hypothesis_with_no_receipt_is_named_by_v9():
    """⛔ *"'This fired because of these facts' is what makes a situation defensible."* A
    hypothesis is the LEAST certain thing this layer emits; it owes a citation most of all."""
    from genios_engine.contracts.situation import RECEIPT_REQUIRED

    assert "hypotheses" in RECEIPT_REQUIRED
    assert "implications" in RECEIPT_REQUIRED


# =================================================================================================
# The durable home — L2-3's debt paid in the same table
# =================================================================================================

def test_the_migration_creates_the_table_and_not_four_columns():
    sql = MIGRATION.read_text().lower()
    assert "create table if not exists situation_interpretations" in sql
    assert "alter table context_situations" not in sql, (
        "the four fields do NOT belong on the situation row — an interpretation expires while a "
        "situation does not, and a column would keep one reading and lose the history")


def test_the_table_records_the_slice_that_produced_the_reading():
    """⛔ L2-3's debt: *"a hash proves sameness and cannot reproduce the input."* A
    `reasoning_trace` pointing at a conclusion whose premises are gone is not a trace."""
    sql = MIGRATION.read_text().lower()
    assert "context_slice" in sql, "the slice is not recorded, so the reading cannot be replayed"
    assert "slice_digest" in sql, "nothing ties the reading to the cache key it was served under"


def test_the_reading_expires_and_the_situation_does_not():
    sql = MIGRATION.read_text().lower()
    assert "valid_until" in sql
    declarations = re.findall(r"^\s*(\w+)\s+(text|jsonb|timestamptz|int)([^,\n]*)", sql,
                              re.MULTILINE)
    by_name = {name: rest for name, _t, rest in declarations}
    assert "not null" not in by_name.get("valid_until", ""), (
        "a reading with no expiry is a reading that is true forever, which is the one thing an "
        "interpretation is not")


def test_the_writer_names_every_column_it_stores():
    """⛔ *"A column no writer names is null forever"* — `started_at` on `l1_sync_runs`, the
    sentence L1 steps 14 and 18 both wrote down."""
    import inspect

    from genios_engine.context import interpretation_store

    src = inspect.getsource(interpretation_store.record_interpretation)
    for column in ("situation_id", "slice_digest", "context_slice", "proposal", "outcome",
                   "valid_until", "reasoning_trace"):
        assert column in src, f"{column} has no writer"


def test_recording_never_raises_because_a_receipt_may_not_kill_its_subject():
    """⛔ The rule L2-7's full-suite failure taught, and `BundleStore.record_call` already states:
    *"a receipt that can abort the thing it is a receipt for turns an accounting failure into a
    product failure."*"""
    from genios_engine.context.interpretation_store import record_interpretation

    class _Exploding:
        def begin(self):
            raise RuntimeError("no database")

    # Must not raise.
    record_interpretation(_Exploding(), org_id="o", situation_id="s", slice_digest="d",
                          context_slice={}, proposal={}, outcome="accept",
                          reasoning_trace="t", valid_until=None)


def test_the_sweep_records_every_reading_including_the_ones_it_did_not_pay_for():
    """⛔ **THE WIRE.** A store nothing calls is the defect this plan keeps finding. And `unknown`
    is recorded too: *a sweep that asked nothing must not look like a sweep that was never run.*"""
    import inspect

    from genios_engine.reason import domain_shadow

    src = inspect.getsource(domain_shadow.shadow_compile)
    assert "record_interpretation(" in src, "the reading is never made durable"
    window = src[src.index("reason_over_situation("):][:1800]
    assert "record_interpretation(" in window, (
        "the reading is recorded somewhere other than beside the consult that produced it")
