"""L3-14 · half of what Layer 2 publishes is never asked for by an authored capability.

⛔ THE STEP THIS FILE REPLACES WAS VOID. L3-14 asked to "lift `about` out of `signals` into an
addressable edge", on the argument that the edge "dies when a signal is archived". L3-13 measured
that false — there is no `delete from signals` anywhere in the tree — so the step had no premise
left. Checking what WAS true instead produced this, which is larger than the step it replaces.

THE ENGINE IS NOT THE CONSTRAINT. `Domain Expertise/_schema/vocabulary.yaml` declares 141 substrate
fact paths to capability authors. 71 are used. **70 are used by none of the 1,425 authored
capabilities**, and 57 of those are not even reachable under a leaf-name coincidence.

The sharpest case is `derived.history.*` — four facts `context/correlation_history.py` computes on
every sweep, including *"we already told them this and they marked it wrong"*, declared in the same
list as `derived.momentum` / `engagement` / `sentiment` which authors use 83 / 191 / 154 times.
It is used **zero** times.

⛔ THIS FILE REPORTS A DIRECTION, NOT A FLOOR. A field may be declared before the capability that
will use it — that is how a substrate grows. What may not happen is the number rising in silence.
"""
from __future__ import annotations

from pathlib import Path

from genios_engine.packs.substrate_demand import (HISTORY_FIELDS, Demand, families, field_paths,
                                                  measure)

CORPUS = Path("Domain Expertise")
VOCABULARY = CORPUS / "_schema" / "vocabulary.yaml"

#: Measured 2026-09-25. CEILINGS, not equalities — the corpus consuming more must never be a build
#: failure, and consuming less must always be one.
UNCONSUMED_CEILING = 70
STRICT_CEILING = 57
DECLARED_AT_MEASUREMENT = 141


def _demand() -> Demand:
    corpus_text = "\n".join(
        path.read_text(errors="ignore") for path in CORPUS.rglob("*.yaml")
        if "_schema" not in str(path))
    return measure(field_paths(VOCABULARY.read_text(encoding="utf-8")), corpus_text)


# =================================================================================================
# 1 · ⛔ THE NUMBER, PINNED IN THE DIRECTION THAT MATTERS
# =================================================================================================

def test_the_unconsumed_substrate_may_shrink_and_may_not_grow():
    """⛔ THE HEADLINE. If this fails upward, a new fact was published with no author asking for
    it — which is the defect this whole file names, repeating. If it fails downward, somebody
    authored against the substrate and the docstrings above are now out of date: update them,
    lower the ceiling, and keep the ratchet tight."""
    demand = _demand()
    assert len(demand.unconsumed) <= UNCONSUMED_CEILING, (
        f"{len(demand.unconsumed)} declared substrate fields are asked for by no capability, up "
        f"from {UNCONSUMED_CEILING}. Publishing a fact nobody consumes costs a write on every "
        f"sweep and buys nothing. New: {sorted(set(demand.unconsumed))[:8]}")
    assert len(demand.strict_unconsumed) <= STRICT_CEILING


def test_the_declared_substrate_is_still_the_list_this_was_measured_against():
    """A vocabulary that shrank would make the ceiling above pass for the wrong reason — fewer
    unconsumed fields because fewer fields, not because anybody authored anything."""
    demand = _demand()
    assert len(demand.declared) >= DECLARED_AT_MEASUREMENT, (
        f"substrate.fact_paths has {len(demand.declared)} entries, below the "
        f"{DECLARED_AT_MEASUREMENT} this was measured against — the ceilings no longer mean what "
        "they say")
    assert len(demand.consumed) + len(demand.unconsumed) == len(demand.declared), (
        "every declared field must land on exactly one side")


def test_roughly_half_the_substrate_is_unasked_for():
    """The claim as a RATIO, so it survives the list growing. This is the sentence that answers
    'why is the output thin' — it is not that the engine computes too little."""
    demand = _demand()
    assert len(demand.unconsumed) >= len(demand.declared) // 3, (
        "if the unconsumed share has genuinely collapsed, this test and every docstring citing "
        "'half the substrate' must be rewritten rather than relaxed")


# =================================================================================================
# 2 · ⛔ THE SHARPEST CASE, NAMED SO ITS FIX IS ANNOUNCED
# =================================================================================================

def test_no_capability_asks_for_the_history_the_engine_computes_every_sweep():
    """⛔ THIS TEST IS MEANT TO BE BROKEN ONE DAY, BY AN AUTHOR RATHER THAN AN ENGINEER.

    `context/correlation_history.publish_histories` runs inside the L2 sweep at
    `context/runner.py:752` and writes these four for every anchor. Nothing reads them.

    When a capability finally asks for one, this fails — and that is the point: the failure is the
    only reliable trigger to come back and rewrite the claims in `packs/substrate_demand`,
    `speedrun008/plan/layer-3/findings/step-14-*` and the handoff, which all state the zero.
    """
    demand = _demand()
    unconsumed = set(demand.unconsumed)
    still_unasked = [f for f in HISTORY_FIELDS if f in unconsumed]
    assert still_unasked == list(HISTORY_FIELDS), (
        f"a capability now asks for {sorted(set(HISTORY_FIELDS) - unconsumed)} — GOOD. Update "
        "packs/substrate_demand's docstring, the L3-14 findings and handoff §5, then narrow this "
        "test to whichever fields are still unasked.")


def test_the_history_fields_are_really_declared_to_authors():
    """The zero above would be trivially true if the fields were never offered. They are — in
    `substrate.fact_paths`, the REAL substrate, not `planned_substrate`."""
    declared = set(field_paths(VOCABULARY.read_text(encoding="utf-8")))
    for field in HISTORY_FIELDS:
        assert field in declared, f"{field} is no longer declared — the claim changes shape"


def test_the_named_history_set_is_exactly_what_the_vocabulary_declares():
    """⛔ FOUND BY MUTATION 7, WHICH STAYED GREEN. Deleting a field from `HISTORY_FIELDS` shrank
    what the test above covers and nothing failed — the constant was asserting itself. Checked in
    BOTH directions against the vocabulary now: a field added to `derived.history.*` that nobody
    lists here is as much a hole as a field listed here that no longer exists.

    Same failure the totality guards exist for (`LAYERS`, `EDGE_TYPES`, `SIGNAL_WRITERS`), and the
    same fix — a closed set is only closed when both sides are checked.
    """
    declared = field_paths(VOCABULARY.read_text(encoding="utf-8"))
    from_vocabulary = tuple(f for f in declared if f.startswith("derived.history."))
    assert set(HISTORY_FIELDS) == set(from_vocabulary), (
        f"HISTORY_FIELDS names {sorted(HISTORY_FIELDS)} but the vocabulary declares "
        f"{sorted(from_vocabulary)}. Reconcile them — the zero this file reports is only "
        "meaningful over the whole family.")
    assert len(HISTORY_FIELDS) == len(set(HISTORY_FIELDS)), "no duplicates"


def test_the_families_authors_do_use_are_still_the_contrast():
    """The comparison that makes the zero mean something: the same list, same section, heavily
    used. If these fell out of use the argument would be 'authors ignore the vocabulary', which is
    a different and less interesting claim."""
    demand = _demand()
    consumed = set(demand.consumed)
    for field in ("derived.momentum", "derived.engagement", "derived.sentiment"):
        assert field in consumed, f"{field} is no longer consumed — the contrast is gone"


# =================================================================================================
# 3 · ⛔ THE MEASUREMENT ITSELF — a leaf is not a path
# =================================================================================================

def test_a_leaf_name_is_never_counted_as_consumption():
    """⛔ THE BLUNT-GREP GUARD. `document.created_at` and an unrelated `created_at` elsewhere in a
    capability are not the same field. Counting the leaf would have reported 13 fields as consumed
    on a coincidence, and the headline number would have been quietly wrong in the safe direction.
    """
    demand = measure(("document.created_at",), "some_other: created_at\n")
    assert demand.consumed == ()
    assert demand.unconsumed == ("document.created_at",)
    assert demand.ambiguous == ("document.created_at",), "leaf hits are reported, never counted"
    assert demand.strict_unconsumed == (), "and excluded from the conservative number"


def test_a_short_leaf_is_not_even_reported_as_ambiguous():
    """`replied`, `intent` — words too common to be evidence in either direction."""
    assert measure(("thread.replied",), "replied: yes").ambiguous == ()


def test_an_exact_path_is_what_counts():
    demand = measure(("derived.history.times_seen", "derived.momentum"),
                     "when: derived.momentum > 0")
    assert demand.consumed == ("derived.momentum",)
    assert demand.unconsumed == ("derived.history.times_seen",)


def test_the_parser_stops_at_the_next_section():
    """⛔ `obs_kinds:` follows `fact_paths:` in the vocabulary. Absorbing it would inflate the
    denominator with things that are not fact paths at all, and every ratio above would be wrong.
    """
    parsed = field_paths(
        "substrate:\n"
        "  fact_paths:\n"
        "    - thread.days_waiting\n"
        "    # a comment, and a blank line follow\n"
        "\n"
        "    - derived.momentum      # trailing comments are stripped\n"
        "  obs_kinds:\n"
        "    - not_a_fact_path\n")
    assert parsed == ("thread.days_waiting", "derived.momentum")


def test_the_parser_returns_nothing_rather_than_guessing():
    """A vocabulary without the section must not silently measure zero declared fields as a pass —
    `test_the_declared_substrate_is_still_the_list` is what catches that, and it can only do so if
    this returns empty rather than raising."""
    assert field_paths("substrate:\n  obs_kinds:\n    - x\n") == ()


def test_families_groups_by_the_segment_the_vocabulary_groups_by():
    assert families(("derived.history.times_seen", "derived.history.prior_outcome",
                     "thread.days_waiting")) == {"history": 2, "days_waiting": 1}
