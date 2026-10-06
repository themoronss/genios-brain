"""STEP-04 · one answer to "who is us" — no module builds its own.

    pytest tests/platform/test_one_answer_to_who_is_us.py -q

Tree `yc2_w27_s04 · M22.C2.L-integration.V3.U19`. "Is this address, this person, this company one of
us?" was answered in twenty places (`speedrun008/YC-II W27/` STEP-04 §8.2, and two more found while
writing this guard: meeting prep and screen recall), from three or four sources, and they disagreed —
so the founder's second address was a service, his company an outside firm, and he the subject of
his own cards. STEP-04 made every one of them ask `platform/self_identity`. This guard keeps it that
way: it reads every SQL string in `genios_engine/` and `scripts/` BY THE AST — implicit concatenation,
`+` and f-strings evaluated, a call's result left as a hole — and fails on the shapes the twenty
sites used to re-derive us:

  union               one statement unioning two of the sources (seats, `orgs`, connections)
  inline-exclusion    `… in (select … from org_seats …)`
  connected-as-ours   `external_account_id like '%@%'` — a connected account read as ours
  seat-enumeration    every seat's address, listed — not one seat looked up by id or address
  reads-declarations  `from org_self_identities` — the declarations are read by the identity only

Outside `platform/self_identity.py`, a hit is allowed only where it is DECLARED below with its
reason, and every declaration must still be needed (a stale one fails too). What it cannot see, said
plainly: a read of the owner's own address (`select email from orgs where id = :o`) is not flagged —
eight modules read it to write to the owner. Those callers are held by their behaviour tests.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ("genios_engine", "scripts")
THE_ANSWER = "genios_engine/platform/self_identity.py"

_SOURCES = (re.compile(r"\bfrom org_seats\b"), re.compile(r"\bfrom orgs\b"),
            re.compile(r"\bfrom connections\b"))
_INLINE_EXCLUSION = re.compile(r"\bin \(\s*select [^()]*\bfrom org_seats\b")
_CONNECTED_AS_OURS = re.compile(r"external_account_id like '%@%'")
_SELECTS_SEAT_EMAIL = re.compile(
    r"\bselect\b(?:(?!\bfrom\b).)*\bemail\b(?:(?!\bfrom\b).)*\bfrom org_seats\b")
_ONE_SEAT = re.compile(r"seat_id ?(=|in\b)|email\)? ?= ?(lower|:|any)|= ?any\(")
_DECLARATIONS = re.compile(r"\bfrom org_self_identities\b")

#: (file, function) → why it may read what the rules flag. Each is a directory, a route or a
#: frozen measurement — none of them decides whether somebody is us.
DECLARED: dict[tuple[str, str], str] = {
    ("genios_engine/api/admin_routes.py", "_seat_emails"):
        "an operator's view of a tenant's seats and their addresses — a directory, never a test",
    ("genios_engine/api/intelligence_routes.py", "_org_level_hit"):
        "one cache key per seat address, to find an answer stored before per-seat answers existed",
    ("genios_engine/reason/meetings/passes.py", "_active_seats"):
        "seat routing: which seat a meeting belongs to, by the seat's own address",
    ("genios_engine/reason/verify/passes.py", "_active_seats"):
        "seat routing: which seat answers for a subject, by the seat's own address",
    ("scripts/workstream_funnel.py", "inbound_mail"):
        "STEP-00's baseline probe: its numbers are the recorded before-state, and redefining its "
        "sender test would falsify every comparison made against it",
}

#: The shapes the twenty sites used, copied from the code STEP-04 replaced (`f0ee8225`). Each must
#: be caught — the guard's own negative control.
HISTORICAL = {
    "context/runner._internal_emails (U01)":
        "select lower(email) as e from org_seats where org_id=:o and active and email is not null "
        "union select lower(email) from orgs where id=:o and email is not null union "
        "select lower(external_account_id) from connections where org_id=:o "
        "and external_account_id is not null and external_account_id like '%@%'",
    "context/meeting_touch._MEETINGS (U03)":
        "and lower(coalesce(att.canonical_key, '')) not in ( select lower(email) from org_seats "
        "where org_id = :o and active and email is not null union select lower(email) from orgs "
        "where id = :o and email is not null union select lower(external_account_id) from "
        "connections where org_id = :o and external_account_id like '%@%' )",
    "api/routes.KNOWN_FROM_SENT_SQL (U07)":
        "and lower(e.actor ->> 'email') in ( select lower(s.email) from org_seats s where "
        "s.org_id = :o and s.email is not null ) and nullif(trim(recipient), '') is not null",
    "context/backfill.backfill_correlations (U09)":
        "select lower(email) as e from org_seats where org_id = :o and active and email is not null",
    "reason/meetings/prep.read (U24)":
        "select lower(email) as e from org_seats where org_id = :o and email is not null",
}


def rules_hit(sql: str) -> list[str]:
    """Which of the five shapes one SQL string has."""
    v = " ".join(sql.split()).lower()
    hits = []
    if "union" in v and sum(bool(p.search(v)) for p in _SOURCES) >= 2:
        hits.append("union")
    if _INLINE_EXCLUSION.search(v):
        hits.append("inline-exclusion")
    if _CONNECTED_AS_OURS.search(v):
        hits.append("connected-as-ours")
    if _SELECTS_SEAT_EMAIL.search(v) and not _ONE_SEAT.search(v):
        hits.append("seat-enumeration")
    if _DECLARATIONS.search(v):
        hits.append("reads-declarations")
    return hits


def _string(node: ast.AST) -> str | None:
    """A string expression's text: adjacent literals are one constant already; `+` and f-strings are
    joined, and anything computed — a call, a name — is a `?` hole."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "?" for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _string(node.left), _string(node.right)
        if left is not None or right is not None:
            return (left if left is not None else "?") + (right if right is not None else "?")
    return None


def violations() -> dict[tuple[str, str], list[str]]:
    """(file, function) → the rules its SQL strings hit, over every scanned module."""
    found: dict[tuple[str, str], list[str]] = {}
    for top in SCANNED:
        for path in sorted((ROOT / top).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            tree = ast.parse(path.read_text())
            parent: dict[ast.AST, ast.AST] = {}
            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    parent[child] = node
            for node in ast.walk(tree):
                text = _string(node)
                if text is None or _string(parent.get(node)) is not None:
                    continue                       # judged once, at the whole expression
                hits = rules_hit(text)
                if not hits:
                    continue
                owner, up = "<module>", parent.get(node)
                while up is not None:
                    if isinstance(up, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        owner = up.name
                        break
                    up = parent.get(up)
                found.setdefault((rel, owner), []).extend(hits)
    return found


def test_every_historical_shape_is_caught():
    """The negative control: what the twenty sites wrote is what this guard fails on."""
    missed = [name for name, sql in HISTORICAL.items() if not rules_hit(sql)]
    assert not missed, f"the guard would not catch: {missed}"


def test_the_one_answer_is_where_it_says():
    """A positive control on the live code: the identity's own union is seen — through its
    f-string — so a rule that silently stopped matching would fail here first."""
    hits = {k: v for k, v in violations().items() if k[0] == THE_ANSWER}
    assert any("union" in v and "connected-as-ours" in v for v in hits.values()), hits


def test_no_module_builds_its_own_answer():
    stray = {k: v for k, v in violations().items()
             if k[0] != THE_ANSWER and k not in DECLARED}
    assert not stray, (
        "a module decides who is us on its own — ask `platform/self_identity.identity_for` "
        f"(or `identity_sql` inside one statement), or declare why it is not a test: {stray}")


def test_every_declaration_is_still_needed():
    found = violations()
    stale = [k for k in DECLARED if k not in found]
    assert not stale, f"declared but no longer reading what the rules flag — delete: {stale}"
