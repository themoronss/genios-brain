"""STEP-13b · the engine reader issues no insert, update or delete.

    .venv/bin/python -m pytest -q tests/packs/test_the_engine_reader_writes_nothing.py

Tree `yc2_w27_s13b · M37.C2.L-data.V2.U02`. `learned_for` reads two tenant-governed tables
(`learned_brain_entries`, `temporary_memories`); nothing here writes a brain, mutes a rule or touches
the `distinct_days` gate. An AST guard, not a convention: every string handed to `sqlalchemy.text()`
anywhere in `engine_reader.py` is read as a Python literal and must open with `select` and must not
carry an `insert into`, `update ` or `delete from` anywhere in it — the same check
`tests/context/test_what_the_company_says_of_itself.py::test_the_reader_writes_nothing` already holds
on `context/company_record.py`, applied here to its sibling reader.
"""
from __future__ import annotations

import ast
from pathlib import Path

from genios_engine.packs.compiler import engine_reader as R


def test_the_reader_issues_no_insert_update_or_delete():
    tree = ast.parse(Path(R.__file__).read_text())
    statements = [" ".join(ast.literal_eval(node.args[0]).split()).lower() for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "text"
                 and node.args and isinstance(node.args[0], ast.Constant)]
    assert statements, "learned_for hands SQL to text() — this guard has nothing to hold without it"
    for sql in statements:
        assert sql.startswith("select "), sql
        for verb in ("insert into", "update ", "delete from", "drop ", "truncate ", "alter "):
            assert verb not in sql, sql
