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

A step is BUILT when its file's name says so, or when `tree.yaml` says so of its block
(`yc2_w27_s<NN>: status: built`) — `yc2_w27_s17` M40.C5.L-logic.V0.U02 (S17X-G2): STEP-17 and
STEP-18 are built in the tree and named TO BUILD on disk, so the guard read the name and held neither.

Written first, red until `M34.C3` U02 and U03 correct the folder: each red it found on 10 Oct is
declared below as a STRICT expected failure naming the unit that corrects it, so the suite stays green
while the folder is wrong and the marker must come off the day it is right.
"""
from __future__ import annotations

import functools
import pathlib
import re
import sys

import pytest
import yaml

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
    return [pytest.param(p, id=_step_id(p), marks=_drift(f"{kind}:{_step_id(p)}")) for p in paths]


def _steps() -> list[pathlib.Path]:
    return sorted(FOLDER.glob("STEP-*.md"))


def _step_id(path: pathlib.Path) -> str:
    """`STEP-13`, or `STEP-13b` for a step planned between two others (`06` D64) — never the first
    seven characters, which read STEP-13b as a second STEP-13 (and its block as `yc2_w27_s13`)."""
    return re.match(r"STEP-\d\d[a-z]?", path.name).group(0)


#: The step files the folder holds, in order: STEP-00 to STEP-18, and STEP-13b (`06` D64, Rohit 12 Oct —
#: the GeniOS Engine in the expert's hands, planned after STEP-13 closes).
STEP_IDS = [f"STEP-{n:02d}" for n in range(14)] + ["STEP-13b"] + [f"STEP-{n:02d}" for n in range(14, 19)]


def _title(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8").split("\n", 1)[0]


def _name_status(path: pathlib.Path) -> str | None:
    return next((s for s in STATUSES if f"-{s.replace(' ', '-')}-" in path.name), None)


def _title_status(path: pathlib.Path) -> str | None:
    return next((s for s in STATUSES if re.search(rf"\b{re.escape(s)}\b", _title(path))), None)


def test_the_folder_has_its_step_files():
    """If this goes to zero every test below passes vacuously."""
    assert [_step_id(p) for p in _steps()] == STEP_IDS


@pytest.mark.parametrize("path", _steps(), ids=_step_id)
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


def _verify_section(path: pathlib.Path) -> str | None:
    """A step's Verify section, WHATEVER ITS NUMBER. ⛔ `yc2_w27_s17` M40.C5.L-logic.V0.U01 (STEP-17
    S17-F5): this read `## 6 · Verify` only, so STEP-01's (§7) and STEP-08's (§5) were never read —
    a built step's Verify could name a test that does not exist and nothing would say so."""
    section = re.search(r"^## \d+ · Verify\s*$(.*?)(?=^## |\Z)", path.read_text(encoding="utf-8"),
                        re.M | re.S)
    return None if section is None else section.group(1)


def _verify_paths(path: pathlib.Path) -> list[str]:
    section = _verify_section(path)
    if section is None:
        return []
    return sorted(set(re.findall(r"(?<![\w/.-])((?:tests|scripts|genios_engine)/[\w/.-]+\.(?:py|sh|sql))",
                                 section)))


@functools.lru_cache(maxsize=1)
def _tree() -> dict:
    return yaml.safe_load((REPO_ROOT / "tree.yaml").read_text(encoding="utf-8")) or {}


def _tree_status(path: pathlib.Path) -> str | None:
    """The status `tree.yaml` gives the step's block — `yc2_w27_s<NN>` for `STEP-<NN>`, `yc2_w27_s13b` for
    `STEP-13b` — or None
    for a step with no block of its own."""
    block = _tree().get(f"yc2_w27_s{_step_id(path)[5:]}")
    return str(block.get("status")) if isinstance(block, dict) and "status" in block else None


def _is_built(name_status: str | None, tree_status: str | None) -> bool:
    """Built by its file's name (anything but TO BUILD), or by its block in `tree.yaml`."""
    return name_status != "TO BUILD" or tree_status == "built"


def _built() -> list[pathlib.Path]:
    return [p for p in _steps() if _is_built(_name_status(p), _tree_status(p))]


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=(
    "yc2_w27_s18 is `building` while M50 (Claude 5 thinks by default, 13 Oct) is built; "
    "M50.C5.L-interface.V2.U20 sets it back to `built` and removes this marker"))
def test_built_is_read_from_the_tree_as_well_as_the_name():
    """S17X-G2. A step named TO BUILD whose block the tree calls built is built; one the tree calls
    anything else is not; a name that says built is built whatever the tree says."""
    assert _is_built("TO BUILD", "built")
    assert not _is_built("TO BUILD", "approved_in_progress")
    assert not _is_built("TO BUILD", None)
    assert _is_built("PENDING", None) and _is_built("DONE", "approved_in_progress")
    built = {_step_id(p) for p in _built()}
    assert {"STEP-17", "STEP-18"} <= built, sorted(built)
    statuses = {_step_id(p): _tree_status(p) for p in _steps()}
    assert statuses["STEP-17"] == statuses["STEP-18"] == "built", statuses


def test_the_tree_status_is_the_blocks_own_word(monkeypatch):
    """Read off the step's own block, whatever it says — and a step with no block has none."""
    monkeypatch.setattr(sys.modules[__name__], "_tree", lambda: {
        "yc2_w27_s13": {"status": "approved_in_progress"}, "yc2_w27_s14": {"source": "no status"},
        "yc2_w27_s17": {"status": "built"}})
    status = {_step_id(p): _tree_status(p) for p in _steps()}
    assert (status["STEP-13"], status["STEP-14"], status["STEP-17"], status["STEP-00"]) == (
        "approved_in_progress", None, "built", None), status
    built = {_step_id(p) for p in _built()}
    assert "STEP-17" in built and not {"STEP-13", "STEP-14", "STEP-18"} & built, sorted(built)


@pytest.mark.parametrize("path", _built(), ids=_step_id)
def test_a_built_step_says_how_to_verify_it(path):
    """A built step with no Verify section would pass the test below on nothing."""
    assert _verify_section(path) is not None, f"{path.name} has no Verify section"


def test_a_verify_section_is_read_whatever_its_number():
    """The two the old reader never saw: STEP-01's Verify is §7 and names two paths."""
    (step01,) = [p for p in _steps() if p.name.startswith("STEP-01-")]
    assert re.search(r"^## 7 · Verify", step01.read_text(encoding="utf-8"), re.M)
    assert len(_verify_paths(step01)) >= 2, _verify_paths(step01)


@pytest.mark.parametrize("path", _params("verify", _built()))
def test_every_path_a_built_steps_verify_names_exists(path):
    missing = [p for p in _verify_paths(path) if not (REPO_ROOT / p).exists()]
    assert not missing, f"{path.name} §6 names what does not exist: {missing}"
