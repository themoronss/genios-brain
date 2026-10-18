"""⛔ U03 · Atlas L2-04 — *"explicit complete authority/ownership/resource/use-restriction views
… are absent"*, graded STILL TRUE on 2026-10-01.

One of the four is `context/authority_view.py`, so the claim has partly expired. The other three
do not have a read surface, and `ATLAS_L2_04_VIEWS` says which is which, what was measured, and
who the mover is.

⛔⛔ WHY THIS FILE IS CAREFUL ABOUT HOW IT MEASURES. The first re-measurement of this claim was
taken by grepping for module filenames, and it was wrong twice: `ownership` was reported absent
while its data is written on every sweep, and `projections.py` was briefly read as covering L2-04
when it holds DOMAIN lenses and answers none of the four questions. *A name that is not
distinctive is not evidence.* So the checks below are about surfaces and production callers, and
where a judgement is unavoidable it is declared rather than inferred.

⛔ AND ONE CLAIM WAS CORRECTED RATHER THAN CHECKED. `authority_view.py` opened with *"the eighth
view over the one graph"*. Nothing in the repository enumerates eight views; the phrase appeared
exactly once engine-wide and `L2.1.4` is the only view-numbered module in `context/`. The list is
in doc 01, which is not in the repo. The line is now attributed instead of counted, and
`test_the_unverifiable_count_is_not_restated` holds it that way.

⛔⛔ AND ONE CLAIM FALSIFIED ITSELF. The entry for `use_restriction` said the term appears in **0
files engine-wide** — and writing that sentence put the term in a file. *The observer can alter
what it measures.* The count now excludes its own declaration, and the test below checks the
qualifier is still there, because without it the entry is false the moment it is written.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from genios_engine.context import authority_view as AV

VIEWS = AV.ATLAS_L2_04_VIEWS
CONTEXT = Path(AV.__file__).resolve().parent
ENGINE = CONTEXT.parent


def _production_importers(module: str) -> list[str]:
    """Every non-test module that imports `genios_engine.context.<module>`, by AST."""
    out: list[str] = []
    for path in sorted(ENGINE.rglob("*.py")):
        if path.name == f"{module}.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:                                     # pragma: no cover
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").endswith(
                    f"context.{module}"):
                out.append(path.name)
            elif isinstance(node, ast.Import):
                if any((a.name or "").endswith(f"context.{module}") for a in node.names):
                    out.append(path.name)
    return sorted(set(out))


# ------------------------------------------------------------------- the declaration, both ways

def test_all_four_atlas_views_are_accounted_for():
    """⛔ Forward: the Atlas names four and the table answers for four. A table that quietly
    dropped one would read as a complete answer."""
    assert set(VIEWS) == {"authority", "ownership", "resource", "use_restriction"}, sorted(VIEWS)


def test_the_table_is_not_empty_and_every_entry_is_graded():
    """⛔ An empty or ungraded table makes every assertion over it vacuous."""
    assert len(VIEWS) == 4
    for name, (state, mover) in VIEWS.items():
        assert state.startswith(("✅", "⛔")), f"{name}: ungraded -- {state[:40]!r}"
        assert mover.startswith(("MOVES WHEN", "MOVES WITH")), f"{name}: {mover[:40]!r}"


def test_exactly_one_is_graded_built_and_it_is_the_one_with_a_module():
    """Backward: the grade has to match the code, not the memory of it."""
    built = [n for n, (state, _) in VIEWS.items() if state.startswith("✅")]
    assert built == ["authority"], built
    assert (CONTEXT / "authority_view.py").exists()


def test_the_built_view_has_a_production_caller_so_it_is_a_surface():
    """⛔ A read surface nothing reads is a draft. This is the distinction the `ownership` entry
    turns on, so the built one has to actually clear it."""
    importers = _production_importers("authority_view")
    assert importers, "authority_view is imported by nothing in production -- regrade it"
    assert "store.py" in importers, importers


def test_the_three_absent_ones_have_no_view_module_of_their_own():
    """Backward: if somebody builds one, this fails and the table has to be regraded.

    ⛔ Deliberately a NECESSARY condition and not a sufficient one. A module appearing proves the
    grade is stale; a module absent does not by itself prove there is no surface, which is exactly
    the mistake the first measurement made. The sufficient half is a human reading the entry.
    """
    for name, (state, _) in VIEWS.items():
        if state.startswith("✅"):
            continue
        candidates = sorted(p.name for p in CONTEXT.glob(f"*{name}*view*.py"))
        assert not candidates, (
            f"{name} now has {candidates}; `ATLAS_L2_04_VIEWS` still grades it absent")


def _cited_paths(text: str) -> list[str]:
    """Backticked `pkg/module.py` citations in a declaration's prose."""
    return re.findall(r"`([a-z_]+/[a-z_/]+\.py)`", text)


def test_every_absent_entry_CITES_A_FILE_THAT_EXISTS():
    """⛔ FOUND BY A MUTATION THAT DID NOT DO WHAT ITS LABEL SAID. The first version of this test
    asked whether the grade contained one of five hand-listed tokens — an OR over a fixed set,
    which an entry citing the wrong module would still satisfy, and which a mutation stripping the
    *reasoning* rather than the *citation* passed straight through.

    Now each absent grade must cite at least one real file, and the file must be on disk. ⛔ A
    citation that does not resolve is worse than none: it reads as a measurement somebody took.
    """
    for name, (state, _) in VIEWS.items():
        if state.startswith("✅"):
            continue
        cited = _cited_paths(state)
        assert cited, (
            f"{name}'s grade cites no file. "
            "'Absent' with nothing behind it is the opinion this unit was built to replace")
        resolved = [c for c in cited if (ENGINE / c).exists()]
        assert resolved, (
            f"{name} cites {cited} and none of them exist under {ENGINE.name}/. A dangling "
            "citation reads as evidence and is not")


def test_the_zero_file_claim_still_holds_where_it_is_made():
    """⛔ `use_restriction` is the one entry whose evidence is an ABSENCE, so it cannot cite a
    file — it claims a count of zero, and that count is re-measured here rather than trusted."""
    state = VIEWS["use_restriction"][0]
    assert "0 files" in state, "the entry's evidence is a count; it has to state the count"
    assert "other than this declaration" in state, (
        "the count must exclude the file that declares it, or the declaration falsifies itself")
    declaring = Path(AV.__file__).resolve().name
    hits = sorted(p.name for p in ENGINE.rglob("*.py")
                  if p.name != declaring and "use_restriction" in p.read_text(encoding="utf-8"))
    assert hits == [], (
        f"`use_restriction` now appears in {hits}; the entry claims 0 files engine-wide other "
        "than its own declaration, and the claim is now false")


def test_the_absent_ones_are_handed_over_and_not_left_as_work():
    """⛔ Three new read surfaces is a roadmap decision. An entry that did not say so would read
    as a to-do this programme had skipped."""
    for name, (state, mover) in VIEWS.items():
        if state.startswith("✅"):
            continue
        assert "Rohit's" in mover, f"{name}: {mover}"


def test_ownership_is_graded_on_the_surface_and_not_on_the_data():
    """⛔ THE RETRACTION, PINNED. The data IS written; the surface is not. An entry that said
    "absent" flatly would be the original error written down permanently."""
    state = VIEWS["ownership"][0]
    assert "commitment.owner" in state and "fact" in state, (
        "the ownership entry must record that the DATA exists, or the next reader repeats the "
        "measurement that called it missing")
    assert "surface" in state


def test_use_restriction_is_distinguished_from_visibility():
    """⛔ The nearest built thing answers a different question, and conflating them is a privacy
    failure rather than a naming one."""
    state = VIEWS["use_restriction"][0]
    assert "visibility_rules" in state
    assert "AUDIENCE" in state or "audience" in state


# ----------------------------------------------------------- the count that could not be checked

def test_the_unverifiable_count_is_not_restated():
    """⛔ `"the eighth view over the one graph"` asserted an ordinal against a list that is not in
    the repository. The line now attributes it. If the bare count comes back, so does the problem.
    """
    text = (CONTEXT / "authority_view.py").read_text(encoding="utf-8")
    assert "The eighth view over the one graph" not in text, (
        "the uncheckable ordinal is back; attribute the count to doc 01 or enumerate the views in "
        "code so it can be checked")
    assert "not in this repository" in text or "not in the repo" in text, (
        "the correction has to say WHY the count is not checkable, or it reads as a style edit")


def test_nothing_else_in_the_engine_restates_the_count():
    """⛔ Broadened on purpose: the first measurement of this claim looked in one file. A second
    copy of an uncheckable number is the same defect in a new place."""
    offenders = [p.name for p in ENGINE.rglob("*.py")
                 if "eighth view over the one graph" in p.read_text(encoding="utf-8")]
    assert not offenders, offenders
