"""A comment that defers to a record must defer to a record that EXISTS.

Four comments in this engine — `comparator.py:155`, `history.py:432`, `qualification.py:714` and
`signal_store.py:28` — sent the reader to a record called `spec_gaps`. There is no such file, no
such directory and no such section: the assumptions three units were built under were deferred to a
place, and the place was never created. The reviewer who found it stated the cost exactly — *"a
reviewer starting X5 cannot find the assumptions X3 made"* — and the cost is the same every time,
because the deferral reads as diligence right up until somebody follows it.

Writing the missing entries into `docs/plans/L2_MISSING_UNIT_SPECS.md` §3 closes the four. This
file is what stops the fifth: a source grep over `genios_engine/` for the deferral idiom, resolving
every backticked target against something real — a repository path, a name defined in the tree, or
a documented section. It is deliberately a GREP and not a convention, because a convention is what
the four comments were already following.

WHAT COUNTS AS RESOLVED, AND WHY EACH RULE IS HERE
--------------------------------------------------
* a path (`docs/plans/X.md`, `capture/structured/targets.py`) resolves when the file is on disk,
  under the repo root or under `genios_engine/`;
* a bare or dotted name (`MetricUnit`, `cohort.percentile_bp`) resolves when the last segment is
  defined anywhere in `genios_engine/`, `tests/` or `scripts/` — a def, a class, an assignment, an
  attribute or a module. Deliberately generous: this test hunts DANGLING references, and a name
  that exists somewhere is findable by the next reader with one grep;
* a glob (`_MISSING_*`) resolves when at least one defined name matches it;
* a URL or hostname is not a deferral at all — `see \x60www.x.com\x60` in `tokens.py` is the verb
  "see", not a pointer, and excluding it by shape is honest where excluding it by file would not be.
"""
from __future__ import annotations

import ast
import fnmatch
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE = REPO_ROOT / "genios_engine"

#: The deferral idiom, as this tree actually writes it. `per` is left OUT on purpose: "per
#: `DATE_POLICY`" is a statement about behaviour, not a pointer at a record, and including it
#: would make the test noisy in the one place noise is fatal — a test nobody trusts gets skipped.
_DEFERRAL = re.compile(
    r"(?:see|noted\s+in|recorded\s+in|documented\s+in|flagged\s+in|tracked\s+in|listed\s+in)\s+"
    r"(?:the\s+)?(?:module\s+note\s+in\s+)?`([^`\n]{2,80})`", re.IGNORECASE)

#: Not a record reference. See the module docstring's last bullet.
_NOT_A_POINTER = re.compile(r"^(?:https?://|www\.)")

#: EMPTY, and it stays empty. It held three entries that dangled because the files belonged to
#: other agents mid-wave; the gate round repointed all three and deleted them from here:
#:
#:   comparator.py / history.py `spec_gaps` -> now `docs/plans/L2_MISSING_UNIT_SPECS.md` §3 A-10
#:       and §3 A-11, the sections that actually hold those two assumptions.
#:   derived.py `_stage_pairs` -> the name never existed; the comment meant `_STAGE_BY_KIND`,
#:       defined on the next line, and now says so.
#:
#: The assertion below is a SUBSET, not an equality, so repointing one makes this list stale
#: rather than red. Never add an entry to make a new dangle pass — a dangle is a five-minute fix
#: and the record it points at is the thing the next wave has to read.
QUARANTINE: set[tuple[str, str]] = set()


def _defined_names() -> set[str]:
    """Every name a reader could land on with one grep: definitions, bindings, module stems."""
    names: set[str] = set()
    roots = (ENGINE, REPO_ROOT / "tests", REPO_ROOT / "scripts")
    for root in roots:
        for path in root.rglob("*.py"):
            names.add(path.stem)
            try:
                tree = ast.parse(path.read_text())
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.add(node.name)
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    names.add(node.id)
                elif isinstance(node, ast.Attribute):
                    names.add(node.attr)
    return names


def _resolves(target: str, names: set[str]) -> bool:
    target = target.strip().rstrip(".,;:").rstrip("()").strip()
    if not target or _NOT_A_POINTER.match(target):
        return True
    if "/" in target:
        candidate = target.split()[0]
        if (REPO_ROOT / candidate).exists() or (ENGINE / candidate).exists():
            return True
        # `capture/structured/mapper.STRUCTURED_PROFILE` — a module path with an attribute on it.
        head = candidate.rsplit("/", 1)[0] + "/" + candidate.rsplit("/", 1)[1].split(".")[0]
        return (ENGINE / f"{head}.py").exists() or (REPO_ROOT / f"{head}.py").exists()
    if target.endswith((".md", ".yaml", ".yml", ".sql")):
        return any(True for _ in REPO_ROOT.rglob(target))
    if "*" in target:
        return any(fnmatch.fnmatchcase(name, target) for name in names)
    if target.endswith(".py"):
        return target[:-3] in names
    last = target.split(".")[-1].split("[")[0].strip()
    return last in names or target.split(".")[0] in names


def _dangling() -> list[tuple[str, int, str]]:
    names = _defined_names()
    found: list[tuple[str, int, str]] = []
    for path in sorted(ENGINE.rglob("*.py")):
        rel = str(path.relative_to(REPO_ROOT))
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            for match in _DEFERRAL.finditer(line):
                if not _resolves(match.group(1), names):
                    found.append((rel, lineno, match.group(1)))
    return found


def test_no_comment_defers_to_a_record_that_does_not_exist():
    """The whole point of the file. `spec_gaps` cost a wave; this is what makes the next one cheap.

    A failure here is not a lint complaint. It means somebody wrote down where the reasoning lives
    and the reasoning does not live there — which is worse than saying nothing, because the reader
    stops looking."""
    unexpected = [row for row in _dangling() if (row[0], row[2]) not in QUARANTINE]
    assert not unexpected, (
        "these comments point at a record that does not exist — write the record (for an "
        "assumption made under a doc contradiction, that is docs/plans/L2_MISSING_UNIT_SPECS.md "
        f"§3) and point the comment at it: {unexpected}")


def test_no_file_defers_to_spec_gaps_any_more():
    """`spec_gaps` was the record four modules sent their reader to and nobody ever wrote. It cost
    a wave: a reviewer starting X5 could not find out which reading of doc 04 X3 had built against.

    All four are repointed now — `qualification.py` and `signal_store.py` in the fix round,
    `comparator.py` and `history.py` in the gate round — so the assertion is the strong one: the
    string appears NOWHERE under `genios_engine/`, and a fifth occurrence is a failure rather than
    a silent regression. Each of the four points at the section that actually holds its
    assumption, which is what makes the pointer worth more than the silence it replaced.
    """
    offenders = [str(path.relative_to(REPO_ROOT)) for path in sorted(ENGINE.rglob("*.py"))
                 if "spec_gaps" in path.read_text()]
    assert offenders == [], offenders
    for repointed in ("genios_engine/capture/esqe/qualification.py",
                      "genios_engine/capture/esqe/signal_store.py",
                      "genios_engine/context/analytic/comparator.py",
                      "genios_engine/context/analytic/history.py"):
        assert "docs/plans/L2_MISSING_UNIT_SPECS.md" in (REPO_ROOT / repointed).read_text()


def test_nothing_in_the_engine_dangles_at_all():
    """The quarantine is empty and this is what keeps it empty: every deferral in the tree
    resolves, with no exception list standing between the grep and the answer."""
    assert _dangling() == []


def test_the_section_those_comments_now_point_at_holds_every_flag_they_name():
    """A pointer at a section is only worth more than `spec_gaps` while the section says the thing.
    A-9..A-13 are the five assumptions the four comments were deferring; §3 must carry all of them,
    and §1's own count and the plans index must agree, per the workspace plan-file convention."""
    spec = (REPO_ROOT / "docs" / "plans" / "L2_MISSING_UNIT_SPECS.md").read_text()
    for flag in ("A-9", "A-10", "A-11", "A-12", "A-13"):
        assert f"### {flag} · " in spec, flag
    assert "The thirteen contradictions in §3" in spec
    index = (REPO_ROOT / "docs" / "plans" / "README.md").read_text()
    assert "13 flags open" in index
    assert "§3 flags **thirteen** contradictions" in index


def test_the_quarantine_only_shrinks():
    """Every quarantined entry must still name a real file. An entry for a file that has moved or
    gone is a licence nobody is using any more, and a stale licence is how a suppression list turns
    into a permanent exemption."""
    for rel, _target in QUARANTINE:
        assert (REPO_ROOT / rel).exists(), rel
