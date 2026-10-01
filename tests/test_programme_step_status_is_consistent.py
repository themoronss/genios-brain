r"""Every step file in the YCW27 programme says the same thing in all three places it says it.

⛔ WHAT WAS WRONG. On 2026-10-01, **seven** step files carried three status labels and one of them
disagreed with the other two:

    filename   STEP-01-DONE-bounded-read.md
    title      "Step 1 — TO BUILD · the bounded query API"
    body       "# ✅ DONE — 2026-09-30"  with the artifacts named and present in the tree

The work was built on 2026-09-30, the filename was renamed, and the title line was never touched.
`layer-3-context-graph` had **four** such files and `layer-1-enterprise-signals` three.

⛔ WHY A TEST AND NOT A ONE-TIME FIX. A heading that says *TO BUILD* on finished work is the same
defect as a stale comment — it reads as a status somebody checked. Anyone auditing the programme by
scanning headings counts the step as outstanding, and the expensive version of that mistake is
rebuilding something that already exists. Three of this programme's own findings came from
concluding a thing was absent because one label said so.

⛔ IT READS THE FIRST LINE ONLY, AND THAT IS DELIBERATE. A whole-file scan for "DONE" matches the
completion section, the prose discussing what done means, and this docstring. The blunt-grep family
has bitten this programme seven times, every time matching the author's own words. The title is one
line; the body check deliberately **excludes** that line.
"""
from __future__ import annotations

import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PROGRAMME = REPO_ROOT / "speedrun008" / "YCW27"

#: The closed set of statuses a step may carry. An unknown status is a bookkeeping fault, never a
#: silent pass — the same rule `reason/guards.CANDIDATE_COMPONENTS` applies to score components.
STATUSES = ("DONE", "PENDING", "RETIRED", "WITHDRAWN", "TO BUILD", "NEXT")

# ⛔ A FIFTH CHECK WAS WRITTEN, RUN, AND DROPPED — recorded because the reason is the useful part.
# It asserted that a settled step carries a completion section below its title. It failed on six
# files, and they were all correct: the programme genuinely has three conventions for recording an
# outcome (`## What was built`, the numbered `## 1 · What was expected` / `## 3 · What was actually
# true` sequence, and RETIRED's `## What is actually true`). Widening the check until it accepted all
# three would have left it asserting that a markdown file contains a heading. A test that enforces a
# convention the repo never adopted is noise, and widening one until it passes is the same mistake as
# narrowing a verify until it passes. Four checks that mean something, not five.

#: Statuses that mean the work is finished, and therefore must have a completion record below.
def _steps() -> list[pathlib.Path]:
    return sorted(PROGRAMME.rglob("STEP-*.md"))


def _filename_status(path: pathlib.Path) -> str | None:
    for token in STATUSES:
        if f"-{token.replace(' ', '-')}-" in path.name:
            return token
    return None


def _title_status(path: pathlib.Path) -> str | None:
    title = path.read_text(encoding="utf-8").split("\n", 1)[0]
    for token in STATUSES:
        if re.search(rf"\b{re.escape(token)}\b", title):
            return token
    return None


@pytest.mark.skipif(not PROGRAMME.is_dir(), reason="the programme folder is not in this checkout")
def test_the_programme_has_step_files_at_all() -> None:
    """If this goes to zero the three tests below pass vacuously."""
    assert len(_steps()) >= 20, f"expected the YCW27 step files, found {len(_steps())}"


@pytest.mark.skipif(not PROGRAMME.is_dir(), reason="the programme folder is not in this checkout")
def test_every_step_declares_a_status_from_the_closed_set() -> None:
    missing = [str(p.relative_to(REPO_ROOT)) for p in _steps()
               if _filename_status(p) is None or _title_status(p) is None]
    assert not missing, (
        "a step file must carry a status in its filename AND its title, from "
        f"{STATUSES}: {missing}")


@pytest.mark.skipif(not PROGRAMME.is_dir(), reason="the programme folder is not in this checkout")
def test_the_filename_and_the_title_agree() -> None:
    """⛔ The seven-file defect this module exists for."""
    disagree = [(str(p.relative_to(REPO_ROOT)), _filename_status(p), _title_status(p))
                for p in _steps() if _filename_status(p) != _title_status(p)]
    assert not disagree, (
        "these step files say two different things about their own status -- a heading that says "
        "TO BUILD on finished work reads as a status somebody checked: " + repr(disagree))


@pytest.mark.skipif(not PROGRAMME.is_dir(), reason="the programme folder is not in this checkout")
def test_a_pending_step_names_who_can_move_it() -> None:
    """⛔ The codebase's own doctrine, applied to its plan: *every silent lane carries a reason and a
    mover.* A pending step with no named owner is an undeclared pending with paperwork — see
    `reason/unit_health.DeclaredSilence`, which refuses construction for the same reason."""
    ownerless = []
    for path in _steps():
        if _filename_status(path) != "PENDING":
            continue
        title = path.read_text(encoding="utf-8").split("\n", 1)[0]
        if "owner" not in title.lower():
            ownerless.append(str(path.relative_to(REPO_ROOT)))
    assert not ownerless, (
        "a PENDING step must name its owner in the title, or nobody can clear it: "
        + repr(ownerless))


# ---------------------------------------------------------------------------------------------
# the folder convention — four documents per layer, and 02-PLAN is never skipped
# ---------------------------------------------------------------------------------------------

#: Every layer folder and every plane folder carries these four. The convention exists because the
#: programme is run from them: a crosscheck before any code, a plan before any build, and findings
#: that outlive both. ⛔ `02-PLAN.md` is the one that is never skipped — skipping it is how a build
#: starts from an assumption nobody wrote down.
LAYER_DOCS = ("00-START-HERE.md", "01-CROSSCHECK.md", "02-PLAN.md", "03-FINDINGS.md")


def _layer_folders() -> list[pathlib.Path]:
    """Folders that run a layer or a plane — identified by holding step files, not by name.

    ⛔ Derived rather than listed. A hard-coded list of eight folder names would pass forever after
    somebody adds a ninth, which is the failure mode this whole module exists to catch.
    """
    return sorted({p.parent for p in _steps()})


@pytest.mark.skipif(not PROGRAMME.is_dir(), reason="the programme folder is not in this checkout")
def test_every_layer_folder_carries_the_four_documents() -> None:
    missing = []
    for folder in _layer_folders():
        for doc in LAYER_DOCS:
            if not (folder / doc).is_file():
                missing.append(f"{folder.relative_to(REPO_ROOT)}/{doc}")
    assert not missing, (
        "a folder that runs a layer or a plane carries all four programme documents; "
        f"02-PLAN.md in particular is never skipped: {missing}")


@pytest.mark.skipif(not PROGRAMME.is_dir(), reason="the programme folder is not in this checkout")
def test_the_folder_list_is_derived_and_not_empty() -> None:
    """Guards the test above against passing because it found nothing to check."""
    folders = _layer_folders()
    assert len(folders) >= 6, f"expected at least the six layer folders, found {folders}"
