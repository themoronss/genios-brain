"""The reset clock has a live reader, it is one layer DOWN, and the copy is forced.

`feedback_health.UNREACHED` declared `reset.latest_reset_at` as *"a surface that was never
built"* because it looked for a caller inside `feedback/`. ⛔ The reader exists: `deliver/outbox.py`
asks the same question at SEND time and cancels a card built before the latest reset.

⛔ IT MAY NOT CALL THE HELPER. `LAYERS` gives `deliver` 6 and `feedback` 7, so `deliver -> feedback`
is an upward import `tests/test_layer_topology.py` fails the build on. The duplication is **forced
by the topology**, and this file is what stops the two copies diverging silently.

⛔ THE SQL IS READ FROM THE AST, NOT THE FILE TEXT, and that is the whole point of the extractor
tests below: `outbox.py` carries a COMMENT reading *"it never read `organization_resets`"*, so a
plain text search over the file would be satisfied by the sentence that says the opposite of what
is being asserted. *A claim about code needs the AST* — and for a SQL CONSTRUCT the honest unit is
the string literal actually handed to `text(...)`.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from genios_engine.LAYERS import LAYERS
from genios_engine.feedback.feedback_health import UNREACHED

_ENGINE = Path(__file__).resolve().parents[2] / "genios_engine"
_HELPER = _ENGINE / "feedback" / "reset.py"
_READER = _ENGINE / "deliver" / "outbox.py"

#: The five clauses that make a string "the reset-clock question". Not a byte comparison: the two
#: copies differ in whitespace (`org_id = :o` against `org_id=:o`) and always will.
_CLAUSES = ("select created_at", "from organization_resets", "where org_id",
            "order by created_at desc", "limit 1")


def _sql_literals(source: str) -> tuple[str, ...]:
    """Every string literal inside a ``text(...)`` call — docstrings and comments excluded.

    Collected from the whole call subtree so a query assembled as ``text("..." + CONST + "...")``
    is read too; `outbox.py` builds its authority re-proof that way.
    """
    out: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
        if name != "text":
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                out.append(inner.value)
    return tuple(out)


def _asks_the_question(literals: tuple[str, ...]) -> tuple[str, ...]:
    squashed = tuple(re.sub(r"\s+", " ", s).lower() for s in literals)
    return tuple(s for s in squashed if all(c in s for c in _CLAUSES))


def _declaration() -> tuple[str, str]:
    assert "reset.latest_reset_at" in UNREACHED, (
        "the declaration was removed; if the helper gained a caller inside feedback/ the "
        "duplication is no longer forced and this whole file should be re-read")
    return UNREACHED["reset.latest_reset_at"]


# ── the two copies ─────────────────────────────────────────────────────────────────────────────

def test_the_helper_asks_the_reset_clock_question():
    assert _asks_the_question(_sql_literals(_HELPER.read_text(encoding="utf-8"))), (
        "feedback/reset.py no longer carries the reset-clock query")


def test_the_live_reader_one_layer_down_asks_it_too():
    assert _asks_the_question(_sql_literals(_READER.read_text(encoding="utf-8"))), (
        "deliver/outbox.py no longer reads the reset clock — a card built before a pivot would "
        "be delivered under the old identity")


def test_the_two_copies_ask_THE_SAME_question():
    helper = _asks_the_question(_sql_literals(_HELPER.read_text(encoding="utf-8")))
    reader = _asks_the_question(_sql_literals(_READER.read_text(encoding="utf-8")))
    assert helper and reader
    # Same clauses, in the same order of appearance — the question, not the formatting.
    def shape(s: str) -> tuple[str, ...]:
        return tuple(sorted(_CLAUSES, key=s.index))
    assert shape(helper[0]) == shape(reader[0]), (
        f"the two copies have diverged:\n  feedback/reset.py : {helper[0]}\n"
        f"  deliver/outbox.py: {reader[0]}")


# ── the guard on the guard: the match may not come from prose ──────────────────────────────────

@pytest.mark.parametrize("prose", [
    '# it never read organization_resets\n',
    '"""select created_at from organization_resets where org_id order by created_at desc limit 1"""\n',
    'MSG = "select created_at from organization_resets where org_id=:o order by created_at desc limit 1"\n',
])
def test_the_extractor_ignores_everything_that_is_not_handed_to_text(prose):
    assert not _asks_the_question(_sql_literals(prose)), (
        "the extractor matched prose; outbox.py's own comment says the OPPOSITE of what this "
        "file asserts, so a text search would prove the reverse of the truth")


def test_the_extractor_does_find_it_inside_a_text_call():
    src = ('from sqlalchemy import text\n'
           'q = text("select created_at from organization_resets where org_id=:o '
           'order by created_at desc limit 1")\n')
    assert _asks_the_question(_sql_literals(src))


# ── why the copy is forced, and that it still is ───────────────────────────────────────────────

def test_the_upward_import_is_illegal():
    assert LAYERS["deliver"] < LAYERS["feedback"], (
        "deliver is no longer below feedback; the duplication may no longer be forced and the "
        "declaration's reason must be re-read")


def test_the_live_reader_does_not_import_the_helpers_package():
    tree = ast.parse(_READER.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "genios_engine.feedback"):
            imported.append(node.module or "")
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names
                         if a.name.startswith("genios_engine.feedback")]
    assert not imported, (
        f"deliver/outbox.py now imports {imported} — that is the upward import the topology "
        "forbids, and if it is legal now the declaration is wrong again")


# ── the declaration says the true thing, and keeps saying it ───────────────────────────────────

def test_the_declaration_names_the_reader_it_used_to_say_did_not_exist():
    why, _ = _declaration()
    assert "deliver/outbox.py" in why, (
        "the declaration no longer names the live reader, which is the single fact it got wrong")


def test_the_declaration_explains_why_the_copy_is_forced():
    """⛔ THE PHRASE, NOT THE WORD. This asserted `"topology" in why` and a mutation that deleted
    *"the duplication is forced by the topology"* SURVIVED — because the word still occurred inside
    the path `tests/test_layer_topology.py`, which the same sentence cites. *A file's NAME can be
    the counter-evidence*, and here it was the false witness."""
    why, _ = _declaration()
    assert "upward import" in why
    assert "forced by the topology" in why, (
        "the declaration no longer says the duplication is FORCED — without that, a reader is "
        "left to conclude the copy is sloppiness and may 'tidy' it into the upward import the "
        "build forbids")


def test_the_old_wrong_sentence_is_quoted_ONLY_as_a_correction():
    """⛔ Attribution, not absence. The correction must quote the wrong sentence to retract it —
    a guard that forbade the words would fail on the fix and pass on a relapse."""
    why, _ = _declaration()
    stale = "a surface that was never built"
    if stale in why:
        head = why[:why.index(stale)]
        assert "CORRECTED" in head or "used to read" in head, (
            "the retracted sentence is present with no marker saying it is retracted — that "
            "reads as a live claim")


def test_every_path_the_declaration_CITES_exists():
    """⛔ A citation is a claim, so it gets checked. The declaration cites the test that enforces
    the topology; a rename would leave a confident pointer at nothing, and *a stale comment reads
    as a measurement*. The MECHANISM is asserted executably above
    (`test_the_upward_import_is_illegal`), so the declaration is free not to cite anything — it is
    not free to cite something that is gone."""
    why, mover = _declaration()
    repo = Path(__file__).resolve().parents[2]
    cited = re.findall(r"(?:tests|genios_engine|migrations)/[\w./-]+\.(?:py|sql)", why + " " + mover)
    missing = [c for c in cited if not (repo / c).exists()]
    assert not missing, f"the declaration cites paths that no longer exist: {missing}"


def test_the_mover_names_the_pair_it_moves_with():
    _, mover = _declaration()
    assert mover.startswith("MOVES WITH"), (
        "this entry moves when its PAIR moves — the outbox copy — which is what MOVES WITH means")
    assert "outbox" in mover


# ── and the Atlas clause that is NOT implemented, declared so it cannot drift ───────────────────

def test_the_learning_layer_still_does_not_read_the_reset_log():
    """⛔ Atlas #6 asks that a reset *'fails promotion until a separate governed supersession'*
    handles the durable rows. Nothing in `feedback/` reads `organization_resets` except the writer
    itself, and blocking promotion after every reset would stop learning for a tenant that merely
    seated a teammate (`seat_joined` calls the same function). That is Rohit's policy decision.
    This records the fact so the day somebody wires it, the decision is taken deliberately."""
    readers = []
    for path in sorted((_ENGINE / "feedback").glob("*.py")):
        if path.name == "reset.py":
            continue
        if any("organization_resets" in s for s in _sql_literals(path.read_text(encoding="utf-8"))):
            readers.append(path.name)
    assert not readers, (
        f"{readers} now read organization_resets — Atlas #6's 'fails promotion' clause is being "
        "implemented, which is a governance decision, not a tidy-up")


def test_the_cancel_the_reader_takes_is_NAMED():
    """A refusal nobody can see is a silent stop: the cancel must carry its own reason."""
    src = _READER.read_text(encoding="utf-8")
    assert "org corrected its identity after this card was built" in src
