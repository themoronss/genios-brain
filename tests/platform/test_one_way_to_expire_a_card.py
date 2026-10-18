"""STEP-06 · one way to expire a card — no other code sets `expired`.

    pytest tests/platform/test_one_way_to_expire_a_card.py -q

Tree `yc2_w27_s06 · M24.C1.L-integration.V3.U01`. Twelve places set a card `expired` and nine wrote
nothing about it (`speedrun008/YC-II W27/` STEP-06 §8.2). From STEP-06 on, `platform/card_lifecycle`
is the only writer of that state, and it always writes the reason. This guard reads every SQL string
in `genios_engine/` and `scripts/` BY THE AST — implicit concatenation, `+` and f-strings evaluated, a
call's result left as a hole — and fails on any statement that sets a card `expired` outside that
module. A thirteenth site fails it; so does any of the twelve, put back the way it was.

What it cannot see, said plainly: a state passed as a bound parameter (`set state = :state` with
`'expired'` in the parameters). The one such statement today, `deliver/actions.py`, sets `acted`,
`snoozed` or `queued` — never `expired` — and writes its own event.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ("genios_engine", "scripts")
THE_WRITER = "genios_engine/platform/card_lifecycle.py"

_SETS_EXPIRED = re.compile(r"\bupdate\s+cards\b[^;]*?\bset\b[^;]*?\bstate\s*=\s*'expired'",
                           re.IGNORECASE | re.DOTALL)

#: The twelve statements STEP-06 replaced, as they stood at `69172196`. Each must still be caught.
HISTORICAL = (
    "update cards set state='expired' where org_id=:o and signal_id=any(:ids) "
    "and state in ('queued','surfaced','snoozed','claimed','delivered')",
    "update cards set state='expired' where org_id=:o and signal_id=:id "
    "and state in ('queued','surfaced','snoozed','claimed','delivered')",
    "update cards set state='expired' where org_id=:o "
    "and signal_id=:id and state in ('queued','surfaced','snoozed','claimed','delivered')",
    "update cards set state='expired' where state in ('queued','surfaced','snoozed') "
    "and expires_at < :now returning card_id, org_id",
    "update cards set state='expired' where card_id=:card and org_id=:o",
    "update cards set state = 'expired' where org_id = :o and card_id = :c "
    "   and state = any(:open)",
)


def _string(node: ast.AST) -> str | None:
    """The SQL a node spells: a literal, an f-string with its holes as `?`, or a `+` of those."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "?" for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _string(node.left), _string(node.right)
        if left is not None or right is not None:
            return (left or "?") + (right or "?")
    return None


def _outermost_strings(tree: ast.AST):
    """Every string expression, taken whole: a `+` chain is read once, not again in its parts."""
    inner: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            for child in (node.left, node.right):
                inner.add(id(child))
        if isinstance(node, ast.JoinedStr):
            inner.update(id(v) for v in node.values)
    for node in ast.walk(tree):
        if id(node) in inner:
            continue
        sql = _string(node)
        if sql is not None:
            yield node.lineno, sql


def violations() -> list[str]:
    found = []
    for top in SCANNED:
        for path in sorted((ROOT / top).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel == THE_WRITER or "/." in rel:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for line, sql in _outermost_strings(tree):
                if _SETS_EXPIRED.search(sql):
                    found.append(f"{rel}:{line}")
    return found


def test_every_historical_shape_is_caught():
    for sql in HISTORICAL:
        assert _SETS_EXPIRED.search(sql), sql


def test_a_planted_thirteenth_site_is_caught():
    source = ('def f(c):\n'
              '    c.execute(text("update cards set state=\'expired\' "\n'
              '                   f"where org_id=:o and card_id={1}"))\n')
    hits = [sql for _, sql in _outermost_strings(ast.parse(source)) if _SETS_EXPIRED.search(sql)]
    assert len(hits) == 1, hits


def test_the_writer_is_where_it_says():
    text = (ROOT / THE_WRITER).read_text(encoding="utf-8")
    assert len(_SETS_EXPIRED.findall(text)) == 2      # the targeted move and the lapse sweep


def test_no_other_code_sets_a_card_expired():
    assert violations() == []
