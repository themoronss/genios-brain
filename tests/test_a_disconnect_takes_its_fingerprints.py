"""STEP-18 B20 · a disconnect-with-wipe deletes the fingerprints of the events it deletes.

    pytest tests/test_a_disconnect_takes_its_fingerprints.py -q

⛔ WHAT WAS WRONG. `integration_disconnect(wipe_data=true)` deleted a source's `raw_payloads` and
`source_events` and left `message_fingerprints` behind. A message's claim names its event, and a
claim by an event that no longer exists still suppressed every later copy: after a reconnect, each
re-synced message was skipped as `seen_on_screen` and nothing was extracted — silently. The tenant
reset (`api/account_routes`) has always deleted the table; this path never did.

Read from the AST, not the text: the route's own comment names the table.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROUTES = Path(__file__).resolve().parents[1] / "genios_engine" / "api" / "routes.py"


def _flatten(node: ast.AST) -> str:
    """A `"a" + name + "b"` expression as one string, in source order; a name reads `{name}`."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _flatten(node.left) + _flatten(node.right)
    if isinstance(node, ast.Name):
        return "{" + node.id + "}"
    return "{?}"


def _sql_strings(fn: ast.FunctionDef) -> list[tuple[int, str]]:
    """(line, SQL) for every `text(...)` call in the function, whitespace normalised."""
    return [(node.lineno, " ".join(_flatten(node.args[0]).lower().split()))
            for node in ast.walk(fn)
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "text"
            and node.args]


def _disconnect() -> ast.FunctionDef:
    tree = ast.parse(ROUTES.read_text(encoding="utf-8"))
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "integration_disconnect")


def test_the_wipe_deletes_the_fingerprints_before_the_events_they_name():
    sql = _sql_strings(_disconnect())
    fps = [line for line, s in sql if s.startswith("delete from message_fingerprints")]
    events = [line for line, s in sql if s.startswith("delete from source_events")]
    assert events, "the wipe no longer deletes source_events — re-read this test's premise"
    assert fps, ("the disconnect deletes events and leaves their fingerprints: a reconnect would "
                 "skip every re-synced message as seen_on_screen")
    assert max(fps) < min(events), (
        "the fingerprints must be selected through source_events, so they go first")


def test_the_fingerprint_delete_is_scoped_like_the_rest_of_the_wipe():
    """A workspace wipe never touches a member's mailbox, and a member's never the org's — the
    fingerprint delete selects through the same `source_events` scope as the payload delete."""
    sql = dict((s.split(" where ")[0], s) for _line, s in _sql_strings(_disconnect()))
    fp = sql["delete from message_fingerprints"]
    payloads = sql["delete from raw_payloads"]
    assert fp.split(" in ", 1)[1] == payloads.split(" in ", 1)[1], (fp, payloads)
