"""No two test files import under one module name — or the whole suite stops at collection.

    pytest tests/test_no_two_test_modules_share_an_import_name.py -q

⛔ WHY (2026-10-07, STEP-07 QA, `yc2_w27_s07 · M25.C8.L-integration.V0.U02`). `tests/contracts/
test_company_brief.py` and `tests/platform/test_company_brief.py` were both green — run folder by folder,
as every guard run before a commit ran them. The whole suite in ONE process stopped at collection
(*"import file mismatch"*), because pytest's default import mode imports a file in a folder with no
`__init__.py` under its bare basename, and the second `test_company_brief` was already taken. CI's
hermetic job runs exactly that one process. This computes every test file's import name the way pytest
does, so the clash fails here, in a second, instead of there, in the first minute of a CI run.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def import_name(path: Path) -> str:
    """The module name pytest's `prepend` import mode gives a test file: its basename, preceded by
    every enclosing folder that is a package (has `__init__.py`), up to the first that is not."""
    parts = [path.stem]
    folder = path.parent
    while (folder / "__init__.py").exists():
        parts.insert(0, folder.name)
        folder = folder.parent
    return ".".join(parts)


def test_every_test_file_has_an_import_name_of_its_own():
    by_name: dict[str, list[str]] = defaultdict(list)
    for path in sorted(TESTS.rglob("test_*.py")):
        if "__pycache__" in path.parts:
            continue
        by_name[import_name(path)].append(str(path.relative_to(TESTS.parent)))
    clashes = {name: files for name, files in by_name.items() if len(files) > 1}
    assert not clashes, (
        "test files that import under one name — the whole-suite run stops at collection: "
        f"{clashes}. Rename one (a unique basename), or make its folder a package")


def test_the_rule_is_pytests_own(tmp_path):
    """A planted clash: two bare folders, one basename — the names agree; a package keeps them apart."""
    for folder in ("a", "b", "c"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "test_same.py").write_text("")
    (tmp_path / "c" / "__init__.py").write_text("")
    assert import_name(tmp_path / "a" / "test_same.py") == import_name(tmp_path / "b" / "test_same.py")
    assert import_name(tmp_path / "c" / "test_same.py") == "c.test_same"
