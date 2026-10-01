r"""Plane D `U02` · the committed registry cannot disagree with what the generator would produce.

⛔ THE PLAN FOR THIS UNIT WAS WRONG, AND THE CORRECTION IS THE UNIT. It read *"`unrouted_l2_types` is
generated, not hand-kept."* It IS generated — `_tools/index.py:205` emits the block, its comment and
all, from `all_l2 - bound_globally` computed at line 61. Measured 2026-09-30: regenerating all three
domains was byte-identical, so nothing was hand-kept and nothing had drifted.

⛔ THE REAL GAP IS THAT NOTHING NOTICED WHEN IT DID. `index.py` has to be RUN. Add a situation that
binds a type, commit without regenerating, and the one file everyone reads for routing coverage says
a bound type is unrouted — in the safe-looking direction, while every tool reports OK. Meanwhile
`validate.py` computed the same set independently and never compared the two.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest
import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
CORPUS = REPO / "Domain Expertise"
VALIDATE = CORPUS / "_tools/validate.py"
REGISTRIES = sorted(CORPUS.glob("* Expertise/registry/situation-capability-map.yaml"))


def _validate() -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(VALIDATE)], cwd=REPO,
                          capture_output=True, text=True)


def test_the_corpus_validates_clean_right_now():
    """The baseline this whole guard rests on. If this fails, nothing below means anything."""
    result = _validate()
    assert result.returncode == 0, result.stdout[-2000:]
    assert "0 error(s)" in result.stdout


def test_there_is_a_registry_for_every_domain():
    assert len(REGISTRIES) == 3, [p.parent.parent.name for p in REGISTRIES]


@pytest.mark.parametrize("registry", REGISTRIES, ids=lambda p: p.parent.parent.name)
def test_every_registry_declares_the_unrouted_block(registry):
    """An absent block is not an empty one. The check can only compare what is written down."""
    data = yaml.safe_load(registry.read_text()) or {}
    assert "unrouted_l2_types" in data


def test_all_three_domains_agree_on_the_global_list():
    """⛔ The block's own comment says *"Global, not this domain's fault"*, and there is one copy per
    domain. Three copies of a global fact must be identical, or the file a reader happens to open
    decides what they believe."""
    lists = {r.parent.parent.name: (yaml.safe_load(r.read_text()) or {}).get("unrouted_l2_types")
             for r in REGISTRIES}
    assert len(set(map(tuple, lists.values()))) == 1, lists


def _staleness():
    """`validate.py`'s comparison, imported as a function.

    ⛔ IMPORTED, NOT RE-IMPLEMENTED. A copy of a rule passes forever while the rule drifts — the
    reason `feedback/attribution` reads `TAXONOMY` rather than restating it.
    """
    import importlib.util
    import sys

    tools = CORPUS / "_tools"
    sys.path.insert(0, str(tools))
    try:
        spec = importlib.util.spec_from_file_location("dx_validate", VALIDATE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)                                   # type: ignore[union-attr]
    finally:
        sys.path.remove(str(tools))
    return module.registry_staleness


def test_an_agreeing_registry_is_not_stale():
    assert _staleness()(["a", "b"], ["a", "b"]) is None
    assert _staleness()([], []) is None


def test_a_missing_entry_is_stale_and_named():
    """⛔ The direction that fails SAFE-LOOKING: the list reads shorter than the truth, because the
    failure mode is forgetting to add, not forgetting to remove."""
    verdict = _staleness()(["commitment_unresolved", "founder_bottleneck"], ["founder_bottleneck"])
    assert verdict is not None
    assert "commitment_unresolved" in verdict
    assert "index.py" in verdict, "the error must name the one command that fixes it"


def test_an_extra_entry_is_stale_and_says_it_IS_bound():
    """Drift the other way: the list claims a type is unrouted when something binds it. Harder to
    notice, because the list merely looks longer."""
    verdict = _staleness()(["a"], ["a", "a_type_something_binds"])
    assert verdict is not None
    assert "a_type_something_binds" in verdict
    assert "which ARE bound" in verdict


def test_the_same_members_in_a_different_order_is_stale():
    """⛔ The file is generated SORTED, so a reordering means somebody edited it by hand."""
    verdict = _staleness()(["a", "b"], ["b", "a"])
    assert verdict is not None
    assert "different order" in verdict


def test_the_check_is_a_function_so_proving_it_needs_no_file_edit():
    """⛔ THE REASON THIS SHAPE EXISTS, KEPT AS A TEST. The first version of these tests edited a real
    registry, ran the tool and restored the file — and then failed, because this suite runs more than
    one pytest process and both copies mutated the same file in the same repository. A guard that must
    modify the corpus to prove it works cannot be trusted in CI, and the fix for a flaky test is never
    to weaken the check it guards."""
    import inspect

    src = inspect.getsource(_staleness())
    assert "Path" not in src and "read_text" not in src, (
        "the comparison touches the filesystem again; it must stay pure")


def test_the_validator_does_not_write():
    """⛔ A validator that rewrites the corpus turns a read into a write and makes `git status`
    unreadable after a routine check. `index.py` remains the only writer.

    ⛔ AND EVERY SUBPROCESS TEST IN THIS FILE IS READ-ONLY, DELIBERATELY. Nothing here edits a corpus
    file, so two pytest processes can run it at once — which this suite does.
    """
    before = {r: r.read_text() for r in REGISTRIES}
    _validate()
    for registry, text in before.items():
        assert registry.read_text() == text, f"{registry.name} was modified by a validation run"


def test_the_error_message_names_the_only_writer():
    src = VALIDATE.read_text()
    assert "it is the only writer" in src


def test_the_validator_still_warns_per_unrouted_type():
    """The existing warnings are not replaced by the new error. They answer different questions —
    *which types are unrouted* and *is the committed list correct*."""
    out = _validate().stdout
    assert "no situation in any domain binds it" in out
