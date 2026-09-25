"""The import-direction ratchet. A package may import same-or-lower layers only.

This is what converts "please don't hardcode sales in L2" and "context must not read
expertise" from code-review opinions into build failures. It is installed while the
DAG is clean, so any red here is a NEW violation — fix the import, not the test.
(Cross-layer needs are met by injection: platform/wiring resolves and passes values
down as parameters; lower layers never import up.)
"""
from __future__ import annotations

import ast
from pathlib import Path

from genios_engine.LAYERS import ALL_DECLARED, CROSS_CUTTING, LAYERS

_ROOT = Path(__file__).resolve().parents[1] / "genios_engine"


def _imports_of(py: Path) -> set[str]:
    """Top-level genios_engine subpackages imported by a file (ast, no execution)."""
    tree = ast.parse(py.read_text(), filename=str(py))
    out: set[str] = set()
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        elif isinstance(node, ast.ImportFrom) and node.level > 0:
            continue                                   # relative import: same package
        for n in names:
            parts = n.split(".")
            if parts[0] == "genios_engine" and len(parts) > 1:
                out.add(parts[1])
    return out


def test_import_direction():
    violations: list[str] = []
    for pkg, layer in LAYERS.items():
        for py in (_ROOT / pkg).rglob("*.py"):
            for imported in _imports_of(py):
                if imported in CROSS_CUTTING or imported not in LAYERS:
                    continue                           # platform/contracts/api: exempt
                if LAYERS[imported] > layer:
                    violations.append(
                        f"{py.relative_to(_ROOT.parent)} (layer {layer}) imports "
                        f"genios_engine.{imported} (layer {LAYERS[imported]}) — upward")
    assert not violations, "\n".join(violations)


def test_contracts_import_nothing_above_platform():
    """contracts/ is the boundary vocabulary — it may depend on platform/stdlib only."""
    bad: list[str] = []
    for py in (_ROOT / "contracts").rglob("*.py"):
        for imported in _imports_of(py):
            if imported not in ("platform", "contracts"):
                bad.append(f"{py.name} imports genios_engine.{imported}")
    assert not bad, "\n".join(bad)


def test_every_layer_package_exists():
    for pkg in LAYERS:
        assert (_ROOT / pkg / "__init__.py").exists(), f"declared layer package missing: {pkg}"


def test_every_package_is_mapped():
    """⛔ L3-00 · the other half of the guard above, and it was missing.

    `test_every_layer_package_exists` proves every DECLARED name is a real package. Nothing proved
    every REAL package is declared — and `genios_engine/mcp` was in neither `LAYERS` nor
    `CROSS_CUTTING` for as long as it has existed.

    An unmapped package escapes `test_import_direction` in BOTH directions. As a source it is never
    visited, because that test iterates `LAYERS.items()`. As a target it is skipped, by
    `if imported in CROSS_CUTTING or imported not in LAYERS: continue`. So `capture` (1) could
    import an unmapped package that imports `feedback` (7), and the ratchet this file exists to be
    would stay green on an upward path laundered through a name nobody declared.

    A totality guard that runs one way is half a guard, and this is the module whose entire job is
    to be the single place a layer number lives.
    """
    on_disk = {p.name for p in _ROOT.iterdir()
               if p.is_dir() and (p / "__init__.py").exists() and not p.name.startswith("_")}
    unmapped = on_disk - ALL_DECLARED
    assert not unmapped, (
        f"packages under genios_engine/ that are in neither LAYERS nor CROSS_CUTTING: "
        f"{sorted(unmapped)}. An unmapped package is invisible to the import ratchet in both "
        "directions — declare it as a layer or as cross-cutting, do not leave it to behave "
        "correctly by accident.")


def test_cross_cutting_and_layers_do_not_overlap():
    """A package that is both a layer and cross-cutting would be checked by the direction rule and
    exempted from it at the same time, and which one wins depends on statement order."""
    both = set(LAYERS) & CROSS_CUTTING
    assert not both, f"declared as BOTH a layer and cross-cutting: {sorted(both)}"


def test_the_translation_table_lists_exactly_the_layer_packages():
    """⛔ `docs/LAYER_MAP.md` is named authoritative by `LAYERS.py`'s own docstring, so it may not
    drift from it. Four numbering vocabularies now exist (package / this file / old dossier /
    product), which is exactly the condition under which a stale table stops being documentation
    and starts being a wrong answer somebody acts on.

    ⛔ THE FIRST DRAFT OF THIS TEST WAS A BLUNT GREP and its mutation probe stayed green: it asked
    whether "`pkg/`" appeared ANYWHERE in the file, so a package named in prose — or in either of
    the file's two tables — satisfied it. That is the same mistake recorded at L1 step 14, L1 step
    18 and L2-6, and it passed here for the same reason it passed there: the assertion was about
    the document, not about the structure the document is trusted for. It now requires the package
    to be the FIRST CELL OF A TABLE ROW, which is the only position that makes it a mapping.
    """
    doc = (_ROOT.parent / "docs" / "LAYER_MAP.md").read_text()
    rows = {line.split("|")[1].strip() for line in doc.splitlines()
            if line.startswith("|") and line.count("|") >= 3}
    for pkg in LAYERS:
        assert f"`{pkg}/`" in rows, (
            f"LAYER_MAP.md has no table ROW for the layer package {pkg!r} — it may be mentioned "
            "in prose, which is not a mapping. Every package in LAYERS needs a row that says what "
            "it is called in each vocabulary.")
