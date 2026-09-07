"""Fixtures for the L3.1 compiler-input tests (wave Y3).

`tests/packs/` carries no `__init__.py`, so pytest's basedir for this directory is the directory
itself and it goes on `sys.path` — which is why the sibling `import l3_inputs` below (and in the
test modules) resolves deterministically rather than depending on collection order. The same
plain import inside `tests/` does NOT resolve, because `tests/__init__.py` makes the repo root
the basedir there; that is the trap `test_repeat_compile_does_not_grow_the_database` documents.
"""
from __future__ import annotations

import pytest

import l3_inputs


@pytest.fixture
def authoring_root(tmp_path):
    """A factory for a one-domain corpus on disk, with whatever `when:` the test authors."""
    def _factory(**kwargs):
        return l3_inputs.build_authoring_root(tmp_path, **kwargs)
    return _factory
