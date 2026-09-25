"""The `qualified_signals` INSERT's three halves have to agree, and once they did not.

WHAT HAPPENED. Step 3 added `subject_key` to `_COLUMNS` (migration 0177) and stopped there. The
VALUES list still carried the placeholders it had before, and `as_params()` still built the dict
it had before — so the statement named 39 columns and supplied 38 expressions. Postgres refuses
that outright:

    INSERT has more target columns than expressions

and `put()` catches every exception by design — *"a signal store never kills a sweep"* — so the
refusal arrived as one WARNING line and a return of 0. On the first real-Postgres run of the
gate suite that was **321 qualified signals silently not stored for one tenant**, and every
downstream gate then failed with "the sweep stored NO scored signal", which reads as a scoring
defect and is not one.

Nothing hermetic could see it: the failure is in the SQL, so it needs a database to be refused
by, and `-m pg` had never been run. `as_params`' own docstring said the column list and the
values "cannot drift out of step at a call site" — true, and beside the point, because they
drifted at the DEFINITION.

WHY THIS TEST IS A STRING COMPARISON AND NOT A ROUND TRIP. A round trip proves today's columns
work; it does not fail when somebody adds the fortieth column to `_COLUMNS` alone. Counting the
three halves does, it needs no database, and it runs in the hermetic lane where the next person
holding a migration will actually see it.
"""

from __future__ import annotations

import re

from genios_engine.capture.esqe import signal_store as S

#: Every `:name` in the VALUES list, in order. `cast(:sec as jsonb)` contributes `sec` once.
_BIND = re.compile(r":([a-z_][a-z0-9_]*)")


def _values_clause() -> str:
    """The VALUES list of `put()`'s INSERT, read off the source rather than re-typed here."""
    import inspect
    body = inspect.getsource(S.PostgresSignalStore.put)
    start = body.index("values (")
    end = body.index("on conflict", start)
    return body[start:end]


def test_the_column_list_and_the_values_list_are_the_same_length():
    columns = [c.strip() for c in S._COLUMNS.split(",") if c.strip()]
    binds = _BIND.findall(_values_clause())
    assert len(columns) == len(binds), (
        f"the INSERT names {len(columns)} columns and supplies {len(binds)} expressions — "
        "Postgres refuses the statement and `put()` swallows the refusal, so the sweep reports "
        f"success and stores nothing.\ncolumns: {columns}\nbinds:   {binds}")


def test_every_placeholder_in_the_insert_is_a_key_as_params_builds():
    """A placeholder with no parameter is the same outage with a different exception."""
    params = set(_one_row().as_params())
    binds = set(_BIND.findall(_values_clause()))
    assert binds <= params, (
        f"the INSERT binds {sorted(binds - params)}, which `as_params()` does not build")
    assert params <= binds, (
        f"`as_params()` builds {sorted(params - binds)}, which the INSERT never names — a value "
        "computed and then dropped on the floor")


def test_subject_key_is_one_of_them():
    """The specific column whose omission cost 321 signals, pinned by name so a revert is loud."""
    assert "subject_key" in S._COLUMNS
    assert "skey" in _BIND.findall(_values_clause())
    assert "skey" in _one_row().as_params()


def _one_row():
    """A minimally-populated row — this file asserts on KEYS, never on values."""
    from datetime import datetime, timezone
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return S.QualifiedSignalRow(
        signal_id="sig_1", org_id="o", subject_key="party:someone@example.test",
        event_id="evt_1", trace_id="evt_1", signal_type="contract_renewal",
        secondary_types=(), importance_bp=1, importance_components={},
        importance_version="alg17-v1", confidence_bp=1, confidence_vector={},
        domain_hints=(), visibility={}, coverage_ready=False, extraction_ref="x",
        # V-4 refuses a claim with no receipt, so even a keys-only fixture carries one.
        evidence_refs=({"quote": "q", "source_ref": "s", "verified": True},),
        conflict_ids=(), state="active", supersedes=None,
        expires_at=None, internal_kind=None, occurred_at=now, envelope={},
        authority_rank=1, ingested_at=now, content_hash="0" * 64, qualification_reason="r",
        superseded_by=None)
