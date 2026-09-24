"""L2-7 · the card stops being one-per-signal — and the link it needs was being thrown away.

⛔ **THE PREMISE IS RIGHT AND THE DIAGNOSIS IS SHARPER THAN THE PLAN'S.** `deliver/pipeline.py`
loops over signals, so three signals about Nitesh become three cards. But signals are emitted
**per (pack, rule, node)** — `domain_shadow._emit_capability_signal` — so the fan-out is at the
RULE level: one situation compiles a package, the package fires several rules, and each rule
becomes a card.

⛔ **AND THE LINK THAT WOULD COLLAPSE THEM DOES NOT EXIST.** `signals` has no `situation_id`
column. `subject_node_id` is not a substitute: `context_situations` is keyed by
`(org_id, correlation_id)`, so **one node can carry several genuinely different situations** and
grouping cards by node would merge things that are not the same thing.

⛔ **AND `situation_id` IS IN SCOPE AT EMIT TIME AND THROWN AWAY.** `shadow_compile` reads
`row["situation_id"]` four times within twenty lines of the emit, and `_persist_live` →
`_emit_capability_signal` does not carry it. That is `not_carried` — the class of defect L1's
step 18 named: *"every measured loss is a value that is computed correctly and then not carried."*

**So this step carries it.** One nullable column, one writer, one selector, and the recall guard
that makes a NULL mean something rather than nothing.
"""
from __future__ import annotations

import inspect
import pathlib
import re

import pytest

pytestmark = pytest.mark.unit

MIGRATION = pathlib.Path("migrations/0182_signal_situation.sql")


def test_the_migration_adds_one_nullable_column_and_an_index():
    sql = MIGRATION.read_text().lower()
    assert "alter table signals" in sql
    assert "situation_id" in sql
    # ⛔ PARSED, NOT GREPPED. L1 steps 14 and 18 and L2-6 all matched a comment with a blunt
    # substring search; the third time it was this repository's own docstring. Read the column
    # DECLARATIONS.
    declarations = re.findall(r"add column if not exists\s+(\w+)\s+(\w+)([^,;]*)", sql)
    assert declarations, "no column declaration parsed"
    for name, _type, rest in declarations:
        assert "not null" not in rest, (
            f"{name} is NOT NULL — a signal that predates this column, or one whose situation "
            f"never formed, must still be storable. NULL is the uninterpreted case and it is a "
            f"real answer")


def test_the_emitter_carries_the_situation_id():
    """⛔ The wiring check. A column no writer names is null forever — `started_at` on
    `l1_sync_runs`, which steps 14 and 18 both wrote that sentence down for."""
    from genios_engine.reason import domain_shadow

    emit = inspect.getsource(domain_shadow._emit_capability_signal)
    assert "situation_id" in emit, "the emitter does not name the column"

    persist = inspect.getsource(domain_shadow._persist_live)
    assert "situation_id" in persist, "the value never reaches the emitter"

    sweep = inspect.getsource(domain_shadow.shadow_compile)
    assert "situation_id=" in sweep or "situation_id =" in sweep, (
        "the sweep has row['situation_id'] in scope and still does not pass it")


def test_the_selector_groups_by_situation_and_not_by_node():
    """⛔ `subject_node_id` is not a substitute. One node carries several situations, because
    `context_situations` is unique on `(org_id, correlation_id)` — grouping by node merges a
    support case with an admin follow-up because the same person is in both."""
    from genios_engine.deliver.pipeline import _open_situations_without_cards

    sql = inspect.getsource(_open_situations_without_cards)
    assert "situation_id" in sql
    assert "group by" in sql.lower() or "distinct" in sql.lower(), (
        "the selector returns one row per signal, which is the loop it replaces")


def test_the_old_selector_is_untouched():
    """§4: *"It does not delete the signal path. It runs beside it, flagged, until the numbers
    agree."*"""
    from genios_engine.deliver import pipeline

    assert hasattr(pipeline, "_open_signals_without_cards")
    assert "situation_id" not in inspect.getsource(pipeline._open_signals_without_cards), (
        "the old selector was edited; L2-7-U1 says build the sibling BESIDE it")


# =================================================================================================
# U3 · the recall guard — the unit that decides whether fewer cards is a merge or a loss
# =================================================================================================

def test_a_signal_whose_situation_never_formed_is_uninterpreted_not_invisible():
    """⛔ **THE GUARD.** If every signal must belong to a situation to be seen, a correlator gap
    becomes a silent disappearance — the exact failure L2-4 exists to end.

    `situation_id IS NULL` is the uninterpreted case, and NULL is a real answer rather than a
    missing one."""
    from genios_engine.deliver.card_source import CardSource, classify

    assert classify(situation_id=None) is CardSource.UNINTERPRETED
    assert classify(situation_id="sit_1") is CardSource.SITUATION


def test_an_uninterpreted_card_is_counted_with_its_own_key():
    """*"Counted, never silent"* — the idiom `_cohort_absorbed` already uses for suppression:
    *"a suppression nobody can see the size of is indistinguishable from a bug that lost cards."*"""
    from genios_engine.deliver.card_source import tally_source

    counts: dict = {}
    tally_source(counts, situation_id=None)
    tally_source(counts, situation_id="sit_1")
    tally_source(counts, situation_id="sit_1")
    assert counts["cards_from_situation"] == 2
    assert counts["cards_uninterpreted"] == 1


def test_the_label_reaches_the_card_and_is_not_only_a_counter():
    """⛔ A number on a dashboard is not a label on a card. §3 of the step: the signal *"still
    surfaces, MARKED as uninterpreted"* — the founder must be able to tell an interpretation from
    a raw measurement."""
    from genios_engine.deliver.card_source import CardSource

    assert CardSource.UNINTERPRETED.label
    assert "uninterpreted" in CardSource.UNINTERPRETED.label.lower()
    assert CardSource.SITUATION.label


def test_the_two_sources_are_closed():
    from genios_engine.deliver.card_source import CardSource

    assert {s.value for s in CardSource} == {"situation", "uninterpreted"}


# =================================================================================================
# U4 · the flip, behind a per-tenant flag, with BOTH paths runnable
# =================================================================================================

def test_the_flag_is_per_tenant_and_off_by_default():
    """⛔ A global boolean is what `live_lane` recorded as the defect: *"one boolean for every
    tenant at once… it only ever turns lanes ON"*. Per tenant, and the way back is removing the
    row."""
    from genios_engine.deliver.card_source import cards_from_situations

    assert cards_from_situations(activated=frozenset()) is False
    assert cards_from_situations(activated=frozenset({"cards_from_situations"})) is True


def test_both_paths_are_measurable_on_one_sweep():
    """Criterion 5 — the old path and the new one compared before either is retired."""
    from genios_engine.deliver.card_source import COMPARISON_KEYS

    assert {"cards_from_situation", "cards_uninterpreted", "cards_from_signal"} <= COMPARISON_KEYS


# =================================================================================================
# ⛔ THE WIRE. A selector nothing calls is the defect this whole plan keeps finding —
# "a unit built, tested, green, and called by nothing on a real request path."
# =================================================================================================

def test_the_build_pass_measures_the_collapse_on_every_sweep():
    """⛔ Criterion 5 — *"both paths measured side by side on the same sweep before the old one is
    removed."* The measurement is read-only and runs whether the flag is on or off, because a
    comparison that only exists after the cutover cannot inform the cutover."""
    from genios_engine.deliver import pipeline

    src = inspect.getsource(pipeline.build_cards_for_org)
    assert "_open_situations_without_cards(" in src, (
        "the build pass never calls the situation selector, so the collapse is unmeasured")
    assert "tally_source(" in src or "cards_from_situation" in src, (
        "the pass does not record where its cards came from")


def test_every_comparison_key_is_initialised_so_a_zero_is_visible():
    """⛔ A key that appears only when it fires is a key nobody knows exists — the same
    declared-silence rule as `BY REASON` and `BY LAW`. Zeros are the comparison."""
    from genios_engine.deliver import pipeline
    from genios_engine.deliver.card_source import COMPARISON_KEYS

    src = inspect.getsource(pipeline.build_cards_for_org)
    for key in COMPARISON_KEYS:
        assert f'"{key}"' in src, f"{key} is never initialised, so its zero cannot be read"


def test_the_flag_decides_the_loop_and_defaults_to_the_old_path():
    """§4: the old path stays runnable for one release, and the way back is removing a row."""
    from genios_engine.deliver import pipeline

    src = inspect.getsource(pipeline.build_cards_for_org)
    assert "cards_from_situations(" in src, "nothing consults the per-tenant flag"


def test_the_measurement_can_never_kill_the_pass_it_measures():
    """⛔ **CAUGHT BY THE FULL SUITE, AND THE RULE WAS ALREADY WRITTEN DOWN.**

    The first draft called `_open_situations_without_cards` unguarded, and
    `test_worker_without_card_build_lease_never_invokes_renderer` went red with
    `'object' object has no attribute 'engine'` — a fake graph in a delivery test. The same thing
    would happen on a real tenant **before migration 0182 is applied**, because the column the
    selector reads would not exist.

    `BundleStore.record_call` states the rule: *"a receipt that can abort the thing it is a
    receipt for turns an accounting failure into a product failure. A lost row mis-states a
    dashboard; a raised exception here costs the narration."*

    So the collapse measurement is wrapped, and a pass that could not measure itself says so —
    `collapse_unmeasured` — rather than looking identical to one that measured zero.
    """
    import inspect

    from genios_engine.deliver import pipeline

    src = inspect.getsource(pipeline.build_cards_for_org)
    head, sep, tail = src.partition("_open_situations_without_cards(")
    assert sep, "the selector is not called"
    assert head.rstrip().endswith("try:") or "try:" in head[-200:], (
        "the collapse measurement is not guarded; a missing column or an unusual graph object "
        "would cost every card in the pass")
    assert "collapse_unmeasured" in src, (
        "a pass that could not measure itself is indistinguishable from one that measured zero")
