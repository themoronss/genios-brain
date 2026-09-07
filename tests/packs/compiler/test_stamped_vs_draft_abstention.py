"""L3.1-U3 · the stale comment, and the gate it described.

`deliver/pipeline.py` carried a comment reading *"the corpus currently holds 152 capabilities, 0
of them accepted, so every prescription shipped on unreviewed authority"*. That world is over —
all 155 authored capabilities clear the admission ceremony today — and a comment describing a
dead world is worse than no comment: a reader concludes every compiled card is downgraded and
stops looking.

Doc 01's acceptance is one test: *"a stamped capability's signal passes abstention un-downgraded;
an unstamped draft's does not"*, plus *"re-verify the abstention gate reads the LIVE admission
state rather than any cached assumption"*. The live-state half is the important one: the
acceptance is a HASH over the routed bytes, recomputed on every compile, so an edit after review
un-accepts the capability by itself.
"""
from __future__ import annotations

import pytest
from l3_inputs import CAPABILITY, build_situation, build_slice

from genios_engine.contracts.abstention import Level, is_actionable
from genios_engine.deliver.pipeline import _apply_abstention
from genios_engine.packs.compiler import DomainCompiler, ExpertBrainCatalog, InMemoryRuntimeBrains
from genios_engine.packs.compiler.authoring import default_authoring_root
from genios_engine.packs.compiler.capability_resolver import _admission_reason
from genios_engine.packs.compiler.errors import UnsupportedCoverage


def _compile(root, *, require_admission: bool):
    return DomainCompiler(catalog=ExpertBrainCatalog(root),
                          runtime_brains=InMemoryRuntimeBrains(),
                          require_admission=require_admission).compile(
        build_situation(), build_slice())


def _emitted_level(package) -> str:
    """The projection `domain_shadow._persist_live` puts on the signals row, from the package's
    own metadata. Spelled here because that function needs a live database, a tenant pack and a
    reasoning bundle to reach — and the one thing under test is which way this branch goes."""
    return (Level.PRESCRIPTIVE if str(package.metadata.get("review_state")) == "accepted"
            else Level.OBSERVATION)


def test_the_whole_shipped_corpus_is_stamped_now():
    """The number the stale comment got wrong, measured rather than asserted from memory. If this
    goes red the comment in `deliver/pipeline.py` is stale again and must move with it."""
    catalog = ExpertBrainCatalog(default_authoring_root())
    capabilities = [capability for record in catalog.domains.values()
                    for capability in record.capabilities.values()]
    gaps = {capability.id: _admission_reason(capability) for capability in capabilities}
    unadmitted = {k: v for k, v in gaps.items() if v is not None}
    assert not unadmitted, f"the corpus is no longer fully stamped: {unadmitted}"
    # A FLOOR, not an equality. The corpus is still being authored, and pinning the exact count
    # would make this test a tripwire for anyone adding a capability rather than for the thing it
    # guards — which is that the number is no longer 152-with-0-accepted.
    assert len(capabilities) >= 155


def test_a_stamped_capability_passes_abstention_un_downgraded(authoring_root):
    package = _compile(authoring_root(when="[]", admitted=True), require_admission=True)
    assert package.metadata["review_state"] == "accepted"
    assert package.metadata["admission_gaps"] == ()

    signal = {"signal_id": "sig_1", "level": _emitted_level(package)}
    assert is_actionable(signal["level"])
    # No tenant pack authority at all — the expertise alone must carry it, which is the half of
    # `_apply_abstention` the compiled lane depends on.
    after = _apply_abstention(signal, {"expertise": {"review_state": package.metadata[
        "review_state"]}})
    assert after["level"] == Level.PRESCRIPTIVE
    assert "abstained_because" not in after


def test_an_unstamped_draft_is_downgraded(authoring_root):
    package = _compile(authoring_root(when="[]", admitted=False), require_admission=False)
    assert package.metadata["review_state"] == "draft"
    assert package.metadata["admission_gaps"]

    # A draft never reaches the gate as an instruction in the first place — `_persist_live` emits
    # it as an observation — and the gate refuses to promote it if it somehow did.
    assert _emitted_level(package) == Level.OBSERVATION
    downgraded = _apply_abstention(
        {"signal_id": "sig_2", "level": Level.PRESCRIPTIVE},
        {"expertise": {"review_state": package.metadata["review_state"]}})
    assert downgraded["level"] == Level.OBSERVATION
    assert "no accepted expertise" in downgraded["abstained_because"]


def test_an_edit_after_review_un_accepts_the_capability_by_itself(authoring_root):
    """THE LIVE-STATE HALF. The acceptance is `admission.accepted_content_hash` over the content
    MINUS the admission block, and `capability_resolver` recomputes it on every compile. Nothing
    is cached, so editing the file after a human accepted it withdraws the authority without
    anybody having to remember to.
    """
    root = authoring_root(when="[]", admitted=True)
    assert _compile(root, require_admission=True).metadata["review_state"] == "accepted"

    capability = (root / "Sales Expertise" / "capabilities" / "01-qualification"
                  / "lead-qualification" / "capability.yaml")
    capability.write_text(capability.read_text().replace(
        "description: Qualify the live opportunity.",
        "description: Qualify the live opportunity, and push for a close date."))

    with pytest.raises(UnsupportedCoverage) as raised:
        _compile(root, require_admission=True)
    assert "content_changed_since_acceptance" in str(raised.value)
    assert raised.value.reason == "unreviewed"

    # In MEASUREMENT mode the same edited content still compiles — route coverage stays
    # measurable — but it compiles as a draft, so nothing built from it may instruct.
    measured = _compile(root, require_admission=False)
    assert measured.metadata["review_state"] == "draft"
    assert measured.metadata["admission_gaps"] == (
        f"{CAPABILITY}:content_changed_since_acceptance",)
