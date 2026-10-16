"""Every statement that reads an `expert_reviews` row selects every column `_stored` builds a `StoredReview` from.

    .venv/bin/python -m pytest -q tests/reason/expert/test_every_read_of_a_review_selects_what_a_stored_review_is_made_of.py

Found on the STEP-14 + STEP-15 merge (16 Oct): `store.current_judgments` (STEP-15, M44.C2.L-data.V0.U01) wrote its
own select list; STEP-13/STEP-14 then taught `_stored` three more columns (`checked_at`, `dossier`, `card_lines` —
0202, 0221) and extended the other three reads. The merge was textually clean — the four statements are far apart —
and the brief's every golden replay died on `NoSuchColumnError: checked_at` instead. A statement that feeds
`_stored` and a `_stored` that reads a column it does not select are two halves that no merge conflict joins, so
this joins them: the columns `_stored` subscripts, read out of its own source, against each statement's select
list. Pure — no database.
"""
from __future__ import annotations

import ast
import inspect
import re
import textwrap

import pytest

from genios_engine.reason.expert import store as R

pytestmark = pytest.mark.unit

#: The four statements whose rows go through `_stored` (`current_judgments` adds the gate's word beside them).
READS = ("_READ", "_LATEST_VALID", "_LATEST_STANDING", "_CURRENT")


def _columns_stored_reads() -> set[str]:
    """What `_stored` takes from a row: every `m["…"]` it subscripts, and the one attribute (`file_id`) it
    does not — from its source, so a column added to `_stored` is a column this test demands."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(R._stored)))
    cols = {n.slice.value for n in ast.walk(tree)
            if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == "m"
            and isinstance(n.slice, ast.Constant) and isinstance(n.slice.value, str)}
    return cols


def _selected(statement) -> set[str]:
    """The column names a `select` returns: the bare name after any `r.` prefix, the alias after `as`."""
    head = str(statement).split(" from ", 1)[0]
    head = re.sub(r"^\s*select\s+(distinct\s+on\s*\([^)]*\)\s*)?", "", head, flags=re.I)
    out = set()
    for part in head.split(","):
        part = re.sub(r"\s+as\s+(\w+)\s*$", r" \1", part.strip(), flags=re.I).split()[-1]
        out.add(part.split(".")[-1])
    return out


def test_stored_reads_the_columns_this_test_expects_it_to():
    """The guard's own control: the extraction finds the columns of the STEP-13/14 shape, so a parse that read
    nothing could not pass the tests below by finding nothing to demand."""
    assert {"status", "review", "checked", "checked_at", "dossier", "card_lines", "triggers"} \
        <= _columns_stored_reads()


@pytest.mark.parametrize("name", READS)
def test_a_read_of_a_review_selects_every_column_stored_builds_it_from(name):
    missing = sorted((_columns_stored_reads() | {"file_id"}) - _selected(getattr(R, name)))
    assert not missing, (f"store.{name} does not select {missing}, which `_stored` reads from its rows — "
                         "a golden replay of the brief fails on the first one")


def test_the_current_read_adds_only_the_gates_word():
    extra = _selected(R._CURRENT) - _selected(R._READ)
    assert extra == {"gate_outcome"}, extra
