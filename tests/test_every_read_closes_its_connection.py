"""`03` F65 · no read leaves its connection open: a connection is never opened inside an expression.

    pytest tests/test_every_read_closes_its_connection.py -q

`yc2_w27_s18` M48.C2.L-data.V0.U09 (L3 Context Graph, `context/backfill`) and M48.C2.L-data.V1.U10
(L2 Plane R, `reason/runner`, STEP-18 §8.3 s18-F1).

⛔ WHAT WAS WRONG. `context/backfill.name_thread_nodes` read with
`store.engine.connect().execute(...)`: the connection is checked out, used once, and never closed or
returned — CPython hands it back when the last reference drops, but a traceback that holds the frame,
or any interpreter without reference counting, keeps it checked out of a pool that production sizes
at a dozen. Its twin, `reason/runner._bulk_load_situations`, runs on every sweep for every org. The
AST is read, not the text: `<anything>.connect()` used directly as the target of a call — `.execute`,
`.scalar`, `.scalars`, `.exec_driver_sql` — in `genios_engine/` and `scripts/`.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READS = frozenset({"execute", "scalar", "scalars", "exec_driver_sql"})


def unclosed_reads(source: str) -> list[int]:
    """Lines where a connection is opened and read in one expression, and so never closed."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in READS and isinstance(node.func.value, ast.Call)
                and isinstance(node.func.value.func, ast.Attribute)
                and node.func.value.func.attr == "connect"):
            out.append(node.lineno)
    return sorted(out)


def _sites() -> dict[str, list[int]]:
    sites = {}
    for folder in ("genios_engine", "scripts"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            lines = unclosed_reads(path.read_text(encoding="utf-8"))
            if lines:
                sites[str(path.relative_to(ROOT))] = lines
    return sites


def test_the_detector_finds_the_shape_and_spares_the_closed_one():
    """The positive control: a guard that cannot see the defect passes for the wrong reason."""
    assert unclosed_reads("rows = store.engine.connect().execute(text('select 1')).all()\n") == [1]
    assert unclosed_reads("x = engine.connect().scalar(q)\n") == [1]
    assert unclosed_reads("with store.engine.connect() as c:\n    rows = c.execute(q).all()\n") == []
    assert unclosed_reads("conn = engine.connect()\n") == [], "a bare connect is the caller's to close"


def test_name_thread_nodes_closes_its_read():
    """`03` F65 — the site the finding named."""
    assert "genios_engine/context/backfill.py" not in _sites()


def test_no_read_leaves_its_connection_open():
    assert _sites() == {}, "a connection opened inside an expression is never closed: use `with`"
