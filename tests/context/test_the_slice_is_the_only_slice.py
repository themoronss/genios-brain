"""L2-3 · the reasoner's context is HANDED, never fetched — and four of five criteria already hold.

⛔ **PREMISE CHECK: THE STEP FILE CONTRADICTS ITSELF, AND §0 WINS.**

§0 (written by the re-analysis, later): *"This step therefore **extends the existing builder for a
new consumer**, and does not write a second one. A second slice builder would be a second answer
to 'what may this reader see', which is the visibility defect waiting to happen."*

§4 (written first): *"It does not replace `SituationContextSlice`… **This is a sibling with a
different consumer.**"*

**§0 is right, and L2-1 just paid the bill for the alternative** — two classes sharing one job left
fifteen parameters across the Domain Expertise compiler annotated with the wrong one of them. A
second slice type would be that again, on the field that decides who may read what.

⛔ **AND FOUR OF THE FIVE COMPLETION CRITERIA WERE ALREADY TRUE, WITH NOTHING WATCHING THEM.**
That is L2-0's finding in a different place, so this file is the watching.

    2 · frozen, carrying graph_version + evaluation_time   ✅ SituationContextSlice, both present
    3 · one bounded read                                   ✅ _bulk_load_facts / _bulk_load_obs are
                                                              ONE org-wide query each, and
                                                              build_context_slice does ZERO I/O
    4 · visibility through the existing rule                ✅ _org_visible_clause, whose own
                                                              docstring names "a situation slice"
    5 · recorded with the situation                        ⛔ HALF — the HASH is stored, the slice
                                                              is not. See the findings.
"""
from __future__ import annotations

import inspect

import pytest

pytestmark = pytest.mark.unit


def test_there_is_exactly_one_slice_type_and_one_builder():
    """⛔ The §0/§4 conflict, settled as a build failure rather than as a paragraph."""
    import genios_engine.context.situation_bso as bso
    from genios_engine.contracts import domain_expertise as de

    builders = [n for n in dir(bso) if "context_slice" in n and callable(getattr(bso, n, None))]
    assert builders == ["build_context_slice"], (
        f"a second slice builder appeared: {builders}. §0 of the step: 'a second slice builder "
        f"would be a second answer to what may this reader see'")
    slices = [n for n in dir(de) if n.endswith("ContextSlice")]
    assert slices == ["SituationContextSlice"], f"a second slice type appeared: {slices}"


def test_the_slice_is_frozen_and_stamps_both_versions():
    """Criterion 2 — already true. Two replays of the same slice are provably the same input."""
    from genios_engine.contracts.domain_expertise import SituationContextSlice

    assert SituationContextSlice.__dataclass_params__.frozen
    for field in ("graph_version", "evaluation_time", "selector_version"):
        assert field in SituationContextSlice.__dataclass_fields__


def test_the_builder_performs_no_io_at_all():
    """⛔ Criterion 3, the strongest form. The builder cannot do an N+1 because it cannot query:
    facts, observations and neighbours all ARRIVE as arguments.

    A builder that could open a connection is a builder somebody will later let fetch.
    """
    from genios_engine.context.situation_bso import build_context_slice

    src = inspect.getsource(build_context_slice)
    for forbidden in ("execute(", "connect(", "engine", "select ", "store."):
        assert forbidden not in src, (
            f"build_context_slice reaches for {forbidden!r} — the slice is HANDED, never fetched")


def test_the_graph_is_read_in_bulk_and_not_per_node():
    """Criterion 3 at the caller. One org-wide query each, not one per node."""
    from genios_engine.reason.runner import _bulk_load_facts, _bulk_load_obs

    for fn in (_bulk_load_facts, _bulk_load_obs):
        src = inspect.getsource(fn)
        assert src.count("c.execute(") == 1, (
            f"{fn.__name__} issues more than one query; the bulk path exists to replace N "
            f"round-trips with one")


def test_every_fact_read_for_a_slice_excludes_a_private_seat_fact():
    """⛔ Criterion 4 — already true, and the rule NAMES this consumer.

    `_org_visible_clause`: *"A stance learned from seat 1's screen may inform seat 1's own query
    and entity 360 — never a team rule, a signal, **a situation slice** or a card."*

    Guarded at both fact loaders, because dropping it from one leaves the other looking correct.
    """
    from genios_engine.reason.runner import _bulk_load_facts, _load_context

    for fn in (_bulk_load_facts, _load_context):
        assert "_org_visible_clause" in inspect.getsource(fn), (
            f"{fn.__name__} stopped filtering private facts out of the slice")


def test_the_visibility_clause_still_excludes_private():
    """Sensitivity — the guard above proves it is CALLED; this proves what it does."""
    from genios_engine.reason.runner import _org_visible_clause

    class _Pg:
        dialect = type("d", (), {"name": "postgresql"})()

    clause = _org_visible_clause(_Pg(), "f.")
    assert "visibility_scope is distinct from 'private'" in clause
    # SQLite test schemas carry no visibility column — declared in the function's own docstring.
    assert _org_visible_clause(type("c", (), {"dialect": None})(), "f.") == ""


# =================================================================================================
# What the slice carries, measured against §2 of the step
# =================================================================================================

def test_the_receipt_travels_inside_the_fact():
    """§2 asks for *"observed facts about its entities, with evidence refs"*. They are there — on
    each fact, not in a separate list."""
    from genios_engine.reason.runner import _load_context

    src = inspect.getsource(_load_context)
    for key in ("source_ref_id", "fact_version_id", "independence_group", "src_count"):
        assert f'"{key}"' in src, f"a fact stopped carrying {key}, which is its pointer to a receipt"


def test_the_slices_empty_evidence_field_is_declared_rather_than_forgotten():
    """⛔ `SituationContextSlice.evidence` is written by nothing, read by nothing, and IS part of
    the content address. That is a field in exactly the state L2-0 spent a step on — except here
    it is empty by design, and the design has to be stated.

    Filling it is not free: `to_semantic_dict` includes it, so every slice hash, every expertise
    package content address and every stored package row would move. That table reached 995 MB and
    took the project read-only the last time an address churned.
    """
    from genios_engine.context.slice_silence import EMPTY_BY_DESIGN, reason_for

    assert "evidence" in EMPTY_BY_DESIGN
    assert "ENDS WHEN" in (reason_for("evidence") or "")


def test_every_slice_field_nothing_writes_is_declared():
    """⛔ Both directions. A field the builder never sets and the declaration never mentions is the
    next vestigial field, and nobody would know."""
    from genios_engine.context.slice_silence import undeclared_unwritten_fields

    missing = undeclared_unwritten_fields()
    assert not missing, (
        f"`build_context_slice` never sets {sorted(missing)}, and `EMPTY_BY_DESIGN` does not say "
        f"why. Declare it with a reason and what would end it, or set it.")
