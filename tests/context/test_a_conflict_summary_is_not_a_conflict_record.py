"""49 cards held on `conflict_open` while carrying their conflicts perfectly well.

    pytest tests/context/test_a_conflict_summary_is_not_a_conflict_record.py -q

THE GATE IS RIGHT. `conflict_open` holds a candidate whose metadata names conflict ids but whose
object carries no typed conflict — *"publishing the candidate as settled would erase the
disagreement by omission"*. Nothing about that reasoning is wrong.

IT WAS MEASURING THE WRONG THING. `_typed_lanes` validates each stored row against `Conflict` and
DROPS what does not validate, silently. `Conflict` is ALG-12's record of a disagreement: frozen,
`extra="forbid"`, and requiring `claims` and `detected_at`. What a BSO stores is a different
object — a SUMMARY — and `_CONFLICT_SELECT` omits exactly those two fields on purpose:

  * `detected_at` is "DELIBERATELY ABSENT — the metadata this lands in is hashed into the
    expertise package's content address, and a clock there mints a fresh package row per
    situation per sweep (the 995 MB read-only incident's mechanism)"
  * `claims` is "counted rather than copied … it holds both sides of a disagreement verbatim,
    including the losing claim's quoted text, and a BSO is a summary"

So every row failed validation for two required fields it must not carry, plus five extras the
frozen contract forbids. Every conflict was dropped, `carried["conflicts"]` was always empty, and
the gate fired on all 52 situations that had conflicts at all.

MEASURED ON THE PILOT 2026-09-16: 52 situations carry conflict pointers and 52 carry the typed
records in metadata — the seam works. 49 of them were held anyway.

THE FIX IS A SECOND CONTRACT, NOT A LOOSER ONE. `Conflict` stays exactly as it is; a BSO validates
its summary against a contract shaped like the summary it actually stores. Widening `Conflict`
would let a caller store a disagreement with no claims in it, which is the thing `extra="forbid"`
and the frozen flag exist to prevent.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts.situation import ConflictSummary

pytestmark = pytest.mark.unit

STORED = {
    "conflict_id": "cfl_6f4baf9c741ffbb5c8738348f82385c1",
    "signal_id": "evt_586a4706fa374a59b42f2c07",
    "field": "date.value",
    "subject_key": "thread:19fbbdb312f23c3a:date",
    "resolution": "unresolved_surface_both",
    "resolved_value": None,
    "event_ids": ["evt_586a4706fa374a59b42f2c07"],
    "claim_count": 2,
}


def test_the_row_a_bso_actually_stores_validates() -> None:
    """Taken verbatim off the live tenant. Before this contract existed it failed with seven
    errors — two missing required fields and five forbidden extras."""
    assert ConflictSummary.model_validate(STORED).field == "date.value"


def test_it_counts_the_claims_rather_than_copying_them() -> None:
    """A BSO is a summary. Copying both sides verbatim would put the losing claim's quoted text
    into an object that is hashed into a package address."""
    assert "claims" not in ConflictSummary.model_fields
    assert "claim_count" in ConflictSummary.model_fields


def test_it_carries_no_clock() -> None:
    """THE 995 MB RULE. `detected_at` in metadata that reaches the expertise package's content
    address mints a fresh ~238 kB package row per situation per sweep. That mechanism took one
    tenant's database read-only."""
    assert "detected_at" not in ConflictSummary.model_fields


def test_it_still_refuses_what_it_does_not_know() -> None:
    """Frozen and extra-forbidding for the same reason `Conflict` is: a summary that silently
    accepts `winner=...` is a summary somebody will believe stored something."""
    with pytest.raises(Exception):
        ConflictSummary.model_validate({**STORED, "winner": "left"})


def test_an_unresolved_conflict_is_still_unresolved() -> None:
    """The whole point of carrying it. `resolved_value: None` with an `unresolved_*` resolution is
    the shape the gate exists to protect — it must survive the projection."""
    s = ConflictSummary.model_validate(STORED)
    assert s.resolved_value is None
    assert "unresolved" in s.resolution


def test_the_record_contract_is_untouched() -> None:
    """`Conflict` is ALG-12's permanent record of a disagreement. Widening it to accept a summary
    would let a caller store a conflict with no claims in it."""
    from genios_engine.contracts.conflict import Conflict

    required = {k for k, v in Conflict.model_fields.items() if v.is_required()}
    assert {"claims", "detected_at"} <= required, "the record contract was loosened"


def test_the_publisher_validates_summaries_not_records() -> None:
    """Wired at the seam that was dropping them."""
    import ast
    import inspect

    from genios_engine.context import situation_publisher

    src = inspect.getsource(situation_publisher)
    tree = ast.parse(src)
    # AnnAssign, not Assign — `_TYPED_LANES: tuple[...] = (...)` carries an annotation, and
    # matching only `ast.Assign` finds nothing and fails for the wrong reason.
    lanes = [n for n in ast.walk(tree)
             if isinstance(n, (ast.Assign, ast.AnnAssign))
             and any(getattr(t, "id", "") == "_TYPED_LANES"
                     for t in (n.targets if isinstance(n, ast.Assign) else [n.target]))]
    assert lanes, "_TYPED_LANES was not found"
    names = {n.id for n in ast.walk(lanes[0]) if isinstance(n, ast.Name)}
    assert "ConflictSummary" in names, "the conflicts lane still validates against the record"
