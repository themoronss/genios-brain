"""STEP-14 · no real name in a prompt — the founder's investors, contacts and programs never ride in the code that
writes a model's prompt.

    pytest tests/deliver/test_no_real_name_in_a_prompt.py -q

Tree `yc2_w27_s14` M43.C5.L-integration.V1.U02 (s14-F17). The narrator's headline examples were *"Send Titan Capital
your traction metrics"*, *"Answer Divyanshu's pricing question"*, *"Get Leslie's calendar availability"* — the
founder's own mailbox, in a prompt every tenant's cards were written from (M43.C5.L-interface.V0.U01 replaced them
with the golden set's invented names). This holds it, read from the AST and never from the text:

  * WHICH MODULES. Every module of `deliver/` and `reason/expert/` a model prompt opens in — the sites
    `tests/replays/harness.SITE_MARKERS` names (the narrator, the expert's review) — and every module of those two
    packages it imports, whose words it prints (the dossier, the slots). Derived, so a prompt that moves, or a module
    it starts printing, is read without editing this file.
  * WHICH STRINGS. Every string literal of those modules — f-string parts included — except a docstring, which no
    model is sent.
  * WHICH NAMES. `tests/replays/founder_case.REAL_NAMES`, the golden set's deny-list, matched as it matches a case.
"""
from __future__ import annotations

import ast
import pathlib

from tests.replays.founder_case import real_names_in
from tests.replays.harness import SITE_MARKERS

ROOT = pathlib.Path(__file__).resolve().parents[2]
ENGINE = ROOT / "genios_engine"
#: The packages whose prompts this holds.
PACKAGES = ("deliver", "reason/expert")


def _in_packages(rel: str) -> bool:
    return any(rel.startswith(p + "/") and rel.count("/") == p.count("/") + 1 for p in PACKAGES)


def _imported(rel: str) -> set[str]:
    """The modules of `PACKAGES` that `rel` imports, by path relative to the engine."""
    tree = ast.parse((ENGINE / rel).read_text())
    package = rel.rsplit("/", 1)[0]
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split("/")[: len(package.split("/")) - (node.level - 1)]
                mod = "/".join(base + ([*node.module.split(".")] if node.module else []))
            else:
                mod = (node.module or "").removeprefix("genios_engine.").replace(".", "/")
            names = [mod + "/" + a.name for a in node.names]
            for cand in (mod, *names):
                if (ENGINE / (cand + ".py")).is_file() and _in_packages(cand + ".py"):
                    out.add(cand + ".py")
    return out


def prompt_modules() -> tuple[str, ...]:
    sites = {module for _site, module, _marker in SITE_MARKERS if _in_packages(module)}
    return tuple(sorted(sites | {m for s in sites for m in _imported(s)}))


def _docstrings(tree: ast.AST) -> set[int]:
    return {id(node.body[0].value) for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body
            and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)}


def real_names_in_literals(source: str) -> list[tuple[int, str]]:
    """(line, name) for every deny-listed name in a string literal of `source` — docstrings aside."""
    tree = ast.parse(source)
    docs = _docstrings(tree)
    return [(node.lineno, name) for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs
            for name in real_names_in(node.value)]


def test_the_prompt_modules_are_the_narrator_the_expert_and_what_they_print():
    modules = prompt_modules()
    for expected in ("deliver/render.py", "reason/expert/prompt.py", "reason/expert/dossier.py", "deliver/slots.py"):
        assert expected in modules, (expected, modules)
    assert all(_in_packages(m) for m in modules), modules


def test_no_real_name_in_a_prompt():
    found = {m: hits for m in prompt_modules() if (hits := real_names_in_literals((ENGINE / m).read_text()))}
    assert found == {}, f"a real name in a prompt's literal: {found}"


def test_a_planted_name_is_found_where_the_model_would_read_it():
    """The negative control: a real name planted in a literal of each module — the narrator's example, the
    expert's role, a dossier's heading — is found; the same name in a docstring is not."""
    render = (ENGINE / "deliver/render.py").read_text()
    assert real_names_in_literals(render.replace("Send Kestrel Capital", "Send Titan Capital", 1)) != []
    prompt = (ENGINE / "reason/expert/prompt.py").read_text()
    assert "You are the founder's chief of staff" in prompt
    assert [n for _l, n in real_names_in_literals(prompt.replace("You are the founder's chief of staff",
                                                                 "You are Boardy's chief of staff", 1))] == ["Boardy"]
    assert real_names_in_literals('def f():\n    """Divyanshu asked."""\n    return f"Ask {x} — Manik said"\n') \
        == [(3, "Manik")]
    assert real_names_in_literals('"""Titan Capital wrote."""\nX = 1\n') == []
