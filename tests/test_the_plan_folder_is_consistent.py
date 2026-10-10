"""The YC-II W27 plan folder says one thing in every place it says it.

    .venv/bin/python -m pytest -q tests/test_the_plan_folder_is_consistent.py

`yc2_w27_align` M34.C3.L-logic.V0.U01. The audit before STEP-12 (`10-BEFORE-STEP-12` §2) found every
step carrying status drift — files that say one thing in their name and another in their title,
decisions proposed in `09` and missing from `06`, findings left open with nobody to close them, and
built steps whose Verify names a test that does not exist. A plan that says something false is a
plan nobody can trust, so the folder is now held to five things:

  * a step file's status word, and the people it names as owners, are the same in its name and its
    title (the shape `tests/test_programme_step_status_is_consistent.py` holds for `YCW27`);
  * `06`'s table holds every decision from D1 to the last, each once;
  * every open finding in `03` names who closes it — a step, a decision, a person, or the tree unit
    that will (a milestone `M<n>`, a block `yc2_w27…`);
  * every path a BUILT step's §6 Verify names exists (a step still TO BUILD names what it will write).

Written first, red until `M34.C3` U02 and U03 correct the folder: each red it found on 10 Oct is
declared below as a STRICT expected failure naming the unit that corrects it, so the suite stays green
while the folder is wrong and the marker must come off the day it is right.
"""
from __future__ import annotations

import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
FOLDER = REPO_ROOT / "speedrun008" / "YC-II W27"

#: The status words a step file may carry — in its name with hyphens, in its title with spaces.
STATUSES = ("PENDING", "TO BUILD", "DONE", "NEXT", "RETIRED")
PEOPLE = ("rohit", "harsh")
#: Who may close an open finding: a step, a decision, a person, or a unit of the tree.
OWNER = re.compile(r"STEP-\d\d|\bD\d+\b|\bRohit\b|\bHarsh\b|\bM\d+\b|M\d+\.C\d+|yc2_w27")

pytestmark = pytest.mark.skipif(not FOLDER.is_dir(), reason="the plan folder is not in this checkout")

#: What the guard found on 10 Oct, and the unit that corrects each — strict, so a fixed one fails
#: until its marker is removed.
DRIFT: dict[str, str] = {
    # Empty since M34.C3 U02 and U03 (10 Oct) corrected all seven: STEP-03's owners; D15-D19; eleven
    # findings with no owner; the verify paths of STEP-06, STEP-07, STEP-09 and STEP-10.
}


def _drift(key: str):
    return (pytest.mark.xfail(strict=True, raises=AssertionError, reason=DRIFT[key])
            if key in DRIFT else ())


def _params(kind: str, paths: list[pathlib.Path]) -> list:
    return [pytest.param(p, id=p.name[:7], marks=_drift(f"{kind}:{p.name[:7]}")) for p in paths]


def _steps() -> list[pathlib.Path]:
    return sorted(FOLDER.glob("STEP-*.md"))


def _title(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8").split("\n", 1)[0]


def _name_status(path: pathlib.Path) -> str | None:
    return next((s for s in STATUSES if f"-{s.replace(' ', '-')}-" in path.name), None)


def _title_status(path: pathlib.Path) -> str | None:
    return next((s for s in STATUSES if re.search(rf"\b{re.escape(s)}\b", _title(path))), None)


def test_the_folder_has_its_step_files():
    """If this goes to zero every test below passes vacuously."""
    assert [p.name[:7] for p in _steps()] == [f"STEP-{n:02d}" for n in range(19)]


@pytest.mark.parametrize("path", _steps(), ids=lambda p: p.name[:7])
def test_a_step_files_status_word_is_its_names(path):
    assert _name_status(path) is not None, f"{path.name}: no status word in the name"
    assert _title_status(path) == _name_status(path), (
        f"{path.name}: the name says {_name_status(path)!r}, the title {_title(path)!r}")


@pytest.mark.parametrize("path", _params("owners", _steps()))
def test_a_step_files_owners_are_its_names(path):
    after = path.name.split("-owner-", 1)[1].split("-") if "-owner-" in path.name else []
    owners = {p for p in PEOPLE if p in after}
    clause = _owner_clause(_title(path))
    if not owners:
        assert clause is None, f"{path.name}: the title names owners the name does not"
        return
    assert clause is not None, f"{path.name}: the name names {sorted(owners)}, the title no owner"
    assert {p for p in PEOPLE if re.search(rf"\b{p}\b", clause)} == owners, (
        f"{path.name}: the name names {sorted(owners)}, the title {_title(path)!r}")


def _owner_clause(title: str) -> str | None:
    """The people a title names as owners: what follows `owner`, its asides in brackets left out
    (`(push ✅ 9 Oct)`, `(… for Rohit's org only)`), up to the next ` · ` or ` — `, lower-cased."""
    m = re.search(r"\bowner\b:?\s*(.*)", title, re.I)
    if m is None:
        return None
    clause = m.group(1)
    while re.search(r"\([^()]*\)", clause):
        clause = re.sub(r"\([^()]*\)", "", clause)
    return re.split(r" · | — ", clause, maxsplit=1)[0].lower()


def _decisions() -> list[int]:
    text = (FOLDER / "06-DECISIONS.md").read_text(encoding="utf-8")
    return [int(n) for n in re.findall(r"^\| \*\*D(\d+)\*\*", text, re.M)]


@pytest.mark.parametrize("kind", [pytest.param("06", marks=_drift("decisions"))])
def test_every_decision_number_exists_once(kind):
    numbers = _decisions()
    assert numbers, "06 holds no decision table"
    duplicated = sorted({n for n in numbers if numbers.count(n) > 1})
    missing = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
    assert not duplicated and not missing, (
        f"06's table: D{duplicated} twice, D{missing} missing" if duplicated
        else f"06's table is missing {['D%d' % n for n in missing]}")


def _open_findings() -> list[tuple[str, str]]:
    text = (FOLDER / "03-FINDINGS.md").read_text(encoding="utf-8")
    out = []
    for line in text.splitlines():
        if not re.match(r"^\| F\d+ \|", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if re.match(r"(?i)(open|partly)\b", cells[-1]):
            out.append((cells[0], cells[-1]))
    return out


@pytest.mark.parametrize("kind", [pytest.param("03", marks=_drift("open_findings"))])
def test_every_open_finding_names_its_owner(kind):
    opened = _open_findings()
    assert opened, "03 holds no open finding — has the table moved?"
    orphans = [f"{fid}: {status[:90]}" for fid, status in opened if not OWNER.search(status)]
    assert not orphans, "open findings nobody owns:\n  " + "\n  ".join(orphans)


def _verify_paths(path: pathlib.Path) -> list[str]:
    section = re.search(r"^## 6 · Verify\s*$(.*?)(?=^## |\Z)", path.read_text(encoding="utf-8"),
                        re.M | re.S)
    if section is None:
        return []
    return sorted(set(re.findall(r"(?<![\w/.-])((?:tests|scripts|genios_engine)/[\w/.-]+\.(?:py|sh|sql))",
                                 section.group(1))))


@pytest.mark.parametrize("path", _params("verify", [p for p in _steps()
                                                     if _name_status(p) != "TO BUILD"]))
def test_every_path_a_built_steps_verify_names_exists(path):
    missing = [p for p in _verify_paths(path) if not (REPO_ROOT / p).exists()]
    assert not missing, f"{path.name} §6 names what does not exist: {missing}"
