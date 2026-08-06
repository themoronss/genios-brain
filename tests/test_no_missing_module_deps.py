"""Every committed module's intra-package imports must resolve to a committed file.

THE BUG THIS EXISTS TO CATCH (it happened): a broad `git add` staged a file whose
in-flight edits imported a module the author never committed. HEAD then imported
`genios_engine.reason.adapters`, which did not exist in the repository — so the L3+L5
sweep died with ModuleNotFoundError on every tick, swallowed by the sweep's own
try/except. The graph kept updating; the brain silently stopped reasoning. Nothing in
the suite noticed, because the *working tree* had the module and only HEAD did not.

Three properties are checked, and they are different:
  1. STATIC MODULE — every `genios_engine.*` import resolves to a file that exists on
     disk. In CI (a clean checkout of the commit) "on disk" means "committed", which
     is exactly the guarantee we want.
  2. STATIC SYMBOL — every name imported FROM a genios_engine module is actually
     defined there. Module-level checking alone missed a real case: a test importing
     `play_stat_key` from a committed module where only the uncommitted working-tree
     copy defined it. The module existed; the name did not.
  3. IMPORTABLE — the entrypoints actually import. A lazy import inside a function
     hides from (1) at import time but still breaks the path that calls it, so the
     static checks are primary.

Scope note: tests/ is checked too. A test that binds to an uncommitted API is the
same defect wearing different clothes — it turns CI red on a clean checkout.
"""
from __future__ import annotations

import ast
import importlib
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1] / "genios_engine"
PKG = "genios_engine"


def _module_exists(dotted: str) -> bool:
    """Is `genios_engine.a.b` a real file/package under the source tree?"""
    rel = dotted.split(".")
    base = ROOT.joinpath(*rel)
    return base.with_suffix(".py").exists() or (base / "__init__.py").exists()


def _imported_modules(py: pathlib.Path) -> set[str]:
    """Every genios_engine submodule this file imports, absolute and relative,
    normalized to a dotted path RELATIVE to the genios_engine package."""
    out: set[str] = set()
    tree = ast.parse(py.read_text(), filename=str(py))
    # relative imports are package-relative — meaningful only inside genios_engine.
    # A file under tests/ has no genios_engine-relative position, so it contributes
    # absolute imports only.
    inside = py.is_relative_to(ROOT)
    here = py.relative_to(ROOT).parent.as_posix().replace("/", ".") if inside else ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith(PKG + "."):
                    out.add(a.name[len(PKG) + 1:])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module and node.module.startswith(PKG + "."):
                out.add(node.module[len(PKG) + 1:])
            elif node.level > 0 and inside:          # relative: from .x / from ..y import z
                parts = [p for p in here.split(".") if p]
                up = node.level - 1
                base = parts[:len(parts) - up] if up else parts
                tail = (node.module or "").split(".") if node.module else []
                dotted = ".".join([*base, *[t for t in tail if t]])
                if dotted:
                    out.add(dotted)
    return out


TESTS = pathlib.Path(__file__).resolve().parent


def _sources():
    for base in (ROOT, TESTS):
        for py in sorted(base.rglob("*.py")):
            if "__pycache__" not in py.parts:
                yield py


def test_every_intra_package_import_resolves():
    missing: list[str] = []
    for py in _sources():
        for mod in sorted(_imported_modules(py)):
            if not _module_exists(mod):
                missing.append(f"{py.name} imports {PKG}.{mod} — NOT in the repository")
    assert not missing, (
        "code depends on modules that are not committed:\n" + "\n".join(missing))


def _defined_names(mod_path: pathlib.Path) -> set[str]:
    """Top-level names a module provides, by AST (no import side effects)."""
    names: set[str] = set()
    tree = ast.parse(mod_path.read_text(), filename=str(mod_path))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.asname or a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):          # re-exports count as provided
            for a in node.names:
                names.add(a.asname or a.name)
    return names


def test_every_imported_symbol_exists():
    """`from genios_engine.x import y` — y must be defined in the committed x."""
    broken: list[str] = []
    for py in _sources():
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.level != 0:
                continue
            if not node.module or not node.module.startswith(PKG + "."):
                continue
            dotted = node.module[len(PKG) + 1:]
            target = ROOT.joinpath(*dotted.split("."))
            file = (target.with_suffix(".py") if target.with_suffix(".py").exists()
                    else target / "__init__.py")
            if not file.exists():
                continue                                # module-level test owns this case
            provided = _defined_names(file)
            for a in node.names:
                if a.name == "*":
                    continue
                # a submodule of a package is a valid import target too
                if (a.name not in provided
                        and not (target / f"{a.name}.py").exists()
                        and not (target / a.name / "__init__.py").exists()):
                    broken.append(f"{py.name}: {PKG}.{dotted} has no '{a.name}'")
    assert not broken, ("code imports names that the committed modules do not define:\n"
                        + "\n".join(broken))


def test_entrypoints_import():
    """The three modules a deploy touches first. A ModuleNotFoundError here is an
    outage, not a test failure — the sweep swallows it and reasoning stops silently."""
    for mod in ("genios_engine.main",
                "genios_engine.api.routes",
                "genios_engine.reason.runner"):
        importlib.import_module(mod)
