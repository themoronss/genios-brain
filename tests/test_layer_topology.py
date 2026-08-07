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

from genios_engine.LAYERS import CROSS_CUTTING, LAYERS

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
