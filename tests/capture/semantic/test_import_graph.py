"""G3 · the typed sink's isolation — Wave W3.

Two import rules, and both encode a fault this codebase has already paid for:

    pytest tests/capture/semantic -q                      # 0 skips
    pytest tests/capture/semantic/test_import_graph.py -q

* `capture/semantic/vocabulary.py` imports nothing from `packs/` and nothing from
  `context/extract/vocab.py`. The extraction vocabulary is what the model is allowed to SAY;
  the rule vocabulary is what the packs are allowed to MATCH. Deriving one from the other means
  a new rule silently changes what the extractor may report, and a promotion has to edit a
  boundary type to add a word;
* nothing under `packs/` or `reason/` imports `capture/semantic/open_lane.py`. The open lane
  holds what the vocabulary had no word for — unreviewed, unpromoted. A reasoner reading it
  directly would be acting on exactly the free-form field names that reached 268 distinct
  values in one org, 192 of them used exactly once (see `context/extract/vocab.py`).

Both are properties of the source tree, so they are asserted with `ast`, the way
`tests/test_layer_topology.py` already does it — no imports executed, no ordering to get wrong.

Two notes on how they are asserted, because a weak version of either would pass forever:

* the first rule is widened from "not the rule vocabulary" to "nothing above `contracts/`",
  and the reason is that `context/extract/vocab.py` is not the only rules-derived word list in
  the tree — `context/vocabulary.py` holds `CANONICAL_OBS_KINDS`, which that module reads, and
  importing it would rebuild the same circle one file further out. The sink's word list is
  curated by a human and promoted with a version bump; it has no legitimate reason to read
  anything that a tenant's configuration can change;
* the second rule is asserted even though `open_lane.py` has not landed yet. It is not vacuous:
  the day a pack imports that module the assertion goes red, which is exactly when it must, and
  writing it now means the rule exists BEFORE the file it protects — the same ordering as W3
  before W4.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

WAVE = "W3"
GATE = "G3"

_ROOT = Path(__file__).resolve().parents[3] / "genios_engine"

#: The modules this gate owns. Both are the prompt side of the sink: one holds the words, the
#: other renders the shape, and neither may learn either from what the rules currently match.
SINK_MODULES = ("capture/semantic/vocabulary.py", "capture/semantic/schema_gen.py")

#: `genios_engine.<root>` prefixes the sink may not import, with the reason each is refused.
FORBIDDEN_FOR_SINK = {
    "packs": "a pack is tenant-configurable domain vocabulary; deriving the sink from it caps "
             "discovery at what somebody already wrote a rule for",
    "reason": "the reasoner is the CONSUMER of an extraction; a sink shaped by its consumer "
              "cannot report anything the consumer does not already ask for",
    "context": "context/extract/vocab.py builds its word list from the rules' own has_obs "
               "clauses, and context/vocabulary.py is where those kinds live — either import "
               "rebuilds the circle",
    "expertise": "expertise packages are compiled from the same domain corpus as the packs",
}

#: The module nothing on the rule side may read. Doc 04, L1.4.5-U1, point 4: *no rule may read
#: this table* — enforced here rather than in a comment.
OPEN_LANE = "genios_engine.capture.semantic.open_lane"

#: Where that rule applies. `packs/` writes the rules; `reason/` runs them.
RULE_SIDE = ("packs", "reason")


def _imported_modules(py: Path) -> set[str]:
    """Every module name `py` imports, absolute-ised. No code is executed.

    Relative imports are resolved against the file's own package, because `from ..context.extract
    import vocab` is the same dependency as the absolute spelling and a test that only understood
    one of the two would be a rule with a documented way around it.
    """
    tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
    package = ".".join(py.relative_to(_ROOT.parent).with_suffix("").parts[:-1])
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = ".".join(package.split(".")[:len(package.split(".")) - node.level + 1])
                module = f"{base}.{node.module}" if node.module else base
            else:
                module = node.module or ""
            found.add(module)
            found.update(f"{module}.{alias.name}" for alias in node.names)
    return found


def _python_files(*roots: str) -> list[Path]:
    files = [py for root in roots for py in (_ROOT / root).rglob("*.py")]
    assert files, f"no python files under {roots} — the walk found nothing to check"
    return files


@pytest.mark.gate
@pytest.mark.parametrize("module", SINK_MODULES)
@pytest.mark.parametrize("forbidden,why", sorted(FORBIDDEN_FOR_SINK.items()))
def test_the_typed_sink_imports_no_rule_side_module(module, forbidden, why):
    """The extraction vocabulary is independent of the rule vocabulary, as a fact about the tree."""
    path = _ROOT / module
    assert path.exists(), f"{module} has not landed"
    prefix = f"genios_engine.{forbidden}"
    offending = sorted(name for name in _imported_modules(path)
                       if name == prefix or name.startswith(f"{prefix}."))
    assert not offending, f"{module} imports {offending} — {why}"


@pytest.mark.gate
@pytest.mark.parametrize("module", SINK_MODULES)
def test_the_typed_sink_imports_nothing_above_contracts(module):
    """The positive form of the same rule, which the per-root list alone cannot give.

    A new top-level package added next year is forbidden here by default rather than by somebody
    remembering to extend `FORBIDDEN_FOR_SINK`. `contracts/` is the one allowance — the sink is
    DERIVED from `ExtractionResult`, which is the entire point of L1.4.4-U2 — plus this package
    itself, so `schema_gen` may read `vocabulary`.
    """
    allowed = ("genios_engine.contracts", "genios_engine.capture.semantic")
    strays = sorted(name for name in _imported_modules(_ROOT / module)
                    if name.startswith("genios_engine.")
                    and not name.startswith(allowed))
    assert not strays, (f"{module} imports {strays}; the typed sink may read contracts/ and its "
                        "own package only, so that no tenant-configurable module can change what "
                        "the model is allowed to say")


@pytest.mark.gate
@pytest.mark.parametrize("root", RULE_SIDE)
def test_no_rule_side_module_reads_the_open_lane(root):
    """Doc 04, L1.4.5-U1: *no rule may read this table.*

    The open lane is where a model's un-vocabularised noticing lands, unreviewed and unpromoted.
    A rule branching on a `proposed_kind` would be branching on a free-form name — the 268-names
    failure, restored, with the promotion step that exists to prevent it skipped.
    """
    offenders = sorted(str(py.relative_to(_ROOT.parent)) for py in _python_files(root)
                       if any(name == OPEN_LANE or name.startswith(f"{OPEN_LANE}.")
                              for name in _imported_modules(py)))
    assert not offenders, (f"{offenders} import the open lane; a discovered observation reaches "
                           "the rules only by promotion into the vocabulary (L1.4.5-U2)")
