"""DC · the tool that guards the corpus was reporting green on half a run.

    pytest tests/packs/test_the_corpus_gate_tells_the_truth.py -q

`_tools/validate.py` has two passes: STRUCTURE (every file against its JSON Schema) and SEMANTICS
(the checks no schema can express). When `jsonschema` was not installed it printed a NOTICE, ran
SEMANTICS only, and then finished with `0 error(s) — OK`.

IT COST EXACTLY WHAT THAT ALWAYS COSTS. Three situation files on this branch carried
`review_status: draft`, which is not in the schema's enum (`unreviewed`, `in_review`,
`approved`). Every local run of the validator reported them green. The audit that found it was
reading the schema, not running the tool — and the three files were the three L2 types this
branch itself added.

The project's own rule is that a skip is not a pass. The validator now refuses to run at all
without the dependency; `--allow-partial` exists for an environment that genuinely cannot install
it, and it changes the summary line too, so a partial run can never be quoted as a full one.

Two more reporting defects in the same family, where a number answered a different question from
its label:

  * `index.py` printed `len(pending)` — a count of TYPES — under "N blocked on a missing L2
    type", which reads as situations. Sales showed 1 against 0 blocked situations, Support 9
    against 7.
  * `shadow_compile` had no count at all for a situation whose L2 domain no corpus claims, so
    `shadow_situations` absorbed them alongside rows a tenant could switch on tomorrow.
"""

from __future__ import annotations

import glob
import importlib.util
import inspect
import subprocess
import sys

import pytest
import yaml

pytestmark = pytest.mark.unit


def _validator():
    spec = importlib.util.spec_from_file_location("v", "Domain Expertise/_tools/validate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# =============================================================================================
# A skip is not a pass.
# =============================================================================================
def test_the_validator_refuses_to_run_without_its_structural_half():
    source = inspect.getsource(_validator().main)

    assert "A skip is not a pass." in source
    assert '"--allow-partial" not in sys.argv' in source
    assert "return 2" in source


def test_a_partial_run_says_so_in_its_summary():
    """The number that gets quoted is the last line. A partial run that ends `0 error(s) — OK`
    is the claim this guard exists to make unmakeable."""
    source = inspect.getsource(_validator().main)

    assert "SEMANTICS only — the STRUCTURE pass did not run." in source


def test_the_corpus_passes_its_own_validator_in_full():
    """The end-to-end assertion, and the one that would have caught the three files. Runs the
    real tool in a subprocess so the dependency is genuinely present rather than mocked."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "Domain Expertise/_tools/validate.py"],
        capture_output=True, text=True, timeout=300)

    assert "SEMANTICS only" not in result.stdout, "the structural pass did not run"
    assert result.returncode == 0, result.stdout[-3000:]


# =============================================================================================
# The three files, and what the schema actually allows.
# =============================================================================================
def test_every_situation_declares_a_review_status_the_schema_admits():
    """`draft` is a valid `identity.status` and NOT a valid `metadata.review_status` — two fields,
    two enums, and the second one was written from memory."""
    schema = yaml.safe_load(open("Domain Expertise/_schema/situation.schema.json"))
    allowed = set(schema["properties"]["metadata"]["properties"]["review_status"]["enum"])

    for path in sorted(glob.glob("Domain Expertise/**/situations/*.yaml", recursive=True)):
        doc = yaml.safe_load(open(path)) or {}
        status = (doc.get("metadata") or {}).get("review_status")
        assert status in allowed, f"{path}: {status!r} not in {sorted(allowed)}"


def test_unreviewed_is_the_word_for_a_situation_nobody_has_read():
    """And it behaves identically at the gate: `situation_admission_reason` maps anything that is
    not `approved` to a gap, so correcting the word changed no behaviour — only the truth of it."""
    from genios_engine.packs.compiler.capability_resolver import situation_admission_reason

    doc = {"identity": {"status": "stable"},
           "metadata": {"review_status": "unreviewed", "reviewed_by": "x"}}

    assert situation_admission_reason(doc) == "review_not_approved"


# =============================================================================================
# Numbers that answer their own label.
# =============================================================================================
def test_the_index_counts_blocked_situations_not_blocked_types():
    source = open("Domain Expertise/_tools/index.py").read()

    assert "blocked = {sid for sids in pending.values() for sid in sids}" in source
    assert "blocked on " in source and "missing L2 type(s)" in source


def test_an_unactivatable_situation_is_counted_separately():
    """A situation whose L2 domain no corpus claims compiles in measurement mode and emits
    nothing on EVERY tenant configuration — including one with every corpus switched on. That is
    a different fact from "not switched on yet", and `shadow_situations` was absorbing both."""
    from genios_engine.reason import domain_shadow

    source = inspect.getsource(domain_shadow.shadow_compile)

    assert 'counts["unactivatable_domain"]' in source
    assert "if row_domain is None:" in source


def test_the_map_still_refuses_to_invent_a_corpus():
    """The fix is a COUNT, not a remap. Pointing `general` at `admin` to get some coverage would
    put Admin doctrine on a general situation, which is worse than silence."""
    from genios_engine.reason.domain_shadow import l3_domain_for

    assert l3_domain_for("general") is None
    assert l3_domain_for("fundraising") is None
    assert l3_domain_for("admin") == "admin"
    assert l3_domain_for("support") == "customer_support"


def test_l3_domain_for_is_total_over_junk():
    """It is called with whatever `context_situations.domain` holds, including nothing."""
    from genios_engine.reason.domain_shadow import l3_domain_for

    assert l3_domain_for(None) is None
    assert l3_domain_for("") is None
    assert l3_domain_for("  ADMIN  ") == "admin"


# =============================================================================================
# The composition root that had nothing to compose.
# =============================================================================================
def test_the_dead_composition_root_is_gone_and_recorded():
    from genios_engine.packs import domain_wiring

    assert not hasattr(domain_wiring, "make_domain_compiler")
    assert domain_wiring.__all__ == ["expert_catalog"]

    from tests import test_nothing_is_written_and_never_read as guard

    assert "packs/domain_wiring.make_domain_compiler" in guard.RETIRED
