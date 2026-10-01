r"""`D.U08` · reviewed by a human, still `draft` — and five of them were RIGHT.

⛔ **READ THIS RETRACTION FIRST. The check below was built on a false reading, and the corpus said
so.** Every one of the five situations this file was written to report is declared in its domain
registry's `pending_l2_types`, and `tests/packs/test_the_corpus_states_its_own_health.py` states in
its own words that they **MUST NOT be flipped** — one of them records that flipping it *"would cost
a false assurance"*. For those five, `draft` + `approved` is not a half-state at all: **the content
is approved and the lifecycle is held on purpose, because the L2 type the situation needs does not
exist yet.**

> **A document in two states is not automatically in a half-state.** Check whether somebody
> declared the combination before calling it an oversight.

So `review_done_but_not_flipped` now takes a `protected` set, loaded from the domain's own registry,
and reports **zero** situations. The check keeps its value — a genuinely forgotten flip, on a
situation nobody declared pending, still fails it — but it no longer cries wolf on five correct
files. This is the eighth time in this programme that a state was called a defect before the
declaration that created it was read.

---

The original premise, kept because the mechanism is real:

⛔ THE STATE. `capability_resolver.situation_admission_reason` requires **both**
`identity.status == "stable"` and `metadata.review_status == "approved"`. A document carrying the
second and not the first is neither unreviewed nor incomplete — **the review is done and nobody
flipped the word.** It cannot instruct, and it looks exactly like a draft nobody has got to yet.

⛔ IT HAS HAPPENED BEFORE IN THIS REPO, AND WAS FOUND BY HAND. Commit `90f8edf0` is titled, exactly,
*"Six situations were finished and nobody flipped the word."* Six then. Measured 2026-10-01: **five
more**, all `reviewed_by: harsh`, all with `reviewed_at == last_updated` so the approval covers the
bytes that are in the file now.

    CAPABILITIES   155   stable+approved 155                       waiting: 0
    SITUATIONS      69   stable+approved  46
                         draft+unreviewed 18   <- genuinely awaiting a review
                         draft+approved    5   <- ⛔ waiting on one word

⛔ AND IT CORRECTS A COUNT THIS PROGRAMME HAD BEEN REPEATING. Every document in the YCW27 folder
said *"23 unreviewed situations"*. Five of the 23 are not unreviewed at all. **A count without its
dimension is not a measurement** — this programme's own first rule, applied to its own number. The
23 are two states with two different movers: eighteen need a reader, five need an editor.

⛔ THE CHECK WARNS AND DOES NOT FLIP. `identity.status` is the authoring lifecycle and the author
owns it; `review_status` is the human ceremony. The gate wants both so that neither alone can grant
production authority, and a tool that flipped the first on the strength of the second would be the
forgery the ceremony exists to prevent.
"""
from __future__ import annotations

import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
CORPUS = REPO / "Domain Expertise"
VALIDATE = CORPUS / "_tools/validate.py"


def _check():
    """`validate.py`'s rule, imported as a function — never re-implemented here.

    A copy of a rule passes forever while the rule drifts. Same reason `_staleness()` in the
    sibling test file imports rather than restates, and the same reason that function is pure: a
    guard that must modify the corpus to prove it works cannot be trusted in CI.
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
    return module.review_done_but_not_flipped


# --------------------------------------------------------------------------------------------
# the rule, on constructed documents
# --------------------------------------------------------------------------------------------

def test_approved_and_stable_is_not_flagged() -> None:
    """The 155 capabilities and 46 live situations are in this state. It is the goal, not a gap."""
    assert _check()({"a.sit.x": {"identity": {"status": "stable"},
                                 "metadata": {"review_status": "approved"}}}) == []


def test_draft_and_unreviewed_is_not_flagged() -> None:
    """Eighteen situations are here. They need a reader, which is a different fact and a different
    mover, so this check must stay silent about them or it stops meaning anything."""
    assert _check()({"a.sit.x": {"identity": {"status": "draft"},
                                 "metadata": {"review_status": "unreviewed"}}}) == []


def test_approved_but_draft_is_flagged_and_names_the_mover() -> None:
    out = _check()({"a.sit.x": {
        "identity": {"status": "draft"},
        "metadata": {"review_status": "approved", "reviewed_by": "harsh",
                     "reviewed_at": "2026-08-29", "last_updated": "2026-08-29"}}})
    assert len(out) == 1
    note = out[0]
    assert "harsh" in note, "a gap with no named mover cannot be cleared by anybody"
    assert "never flipped" in note
    assert "ANOTHER REVIEW" not in note, "the approval covers these bytes; a flip is the answer"


def test_a_file_edited_after_its_review_asks_for_another_review_not_a_flip() -> None:
    """⛔ The opposite action. If the bytes changed after the approval, the approval does not cover
    them, and flipping the status would grant authority to content nobody approved."""
    out = _check()({"a.sit.x": {
        "identity": {"status": "draft"},
        "metadata": {"review_status": "approved", "reviewed_by": "harsh",
                     "reviewed_at": "2026-08-29", "last_updated": "2026-09-30"}}})
    assert len(out) == 1
    assert "ANOTHER REVIEW" in out[0]
    assert "does not cover these bytes" in out[0]


def test_an_approval_with_no_named_reviewer_still_reports_somebody_to_chase() -> None:
    out = _check()({"a.sit.x": {"identity": {"status": "draft"},
                                "metadata": {"review_status": "approved"}}})
    assert len(out) == 1 and "nobody named" in out[0]


def test_the_result_is_ordered_so_two_runs_agree() -> None:
    docs = {f"a.sit.{n}": {"identity": {"status": "draft"},
                           "metadata": {"review_status": "approved"}} for n in "cba"}
    assert _check()(docs) == sorted(_check()(docs))


# --------------------------------------------------------------------------------------------
# and against the real corpus
# --------------------------------------------------------------------------------------------

def _situations() -> dict[str, dict]:
    """Every authored situation, loaded by the PRODUCT's own catalog.

    ⛔ Not a glob of my own. The first version of this helper walked `*/situations/*.yaml`, found
    **nothing**, and the corpus test passed vacuously until a sibling assertion caught it. The
    corpus layout is the catalog's business, and a test that re-derives it is a second
    implementation that can disagree with the first.
    """
    from genios_engine.packs.compiler.authoring import (ExpertBrainCatalog,
                                                        default_authoring_root)

    catalog = ExpertBrainCatalog(default_authoring_root())
    return {sid: (doc.content or {})
            for record in catalog.domains.values()
            for sid, doc in record.situations.items()}


@pytest.mark.skipif(not CORPUS.is_dir(), reason="the corpus is not in this checkout")
def test_the_corpus_has_situations_to_check() -> None:
    """Guards the test below against passing because it found nothing."""
    assert len(_situations()) >= 50, f"expected the authored situations, found {len(_situations())}"


def _protected() -> set[str]:
    """Every situation its domain registry declares `pending_l2_types`.

    ⛔ Read from the registry, never listed here. The exemption and the declaration that creates it
    must be the same fact or this test drifts back into the error it records.
    """
    import yaml

    out: set[str] = set()
    for domain in sorted(CORPUS.glob("* Expertise")):
        smap = domain / "registry" / "situation-capability-map.yaml"
        if not smap.is_file():
            continue
        data = yaml.safe_load(smap.read_text(encoding="utf-8")) or {}
        for entry in (data.get("pending_l2_types") or {}).values():
            out.update((entry or {}).get("situations") or [])
    return out


@pytest.mark.skipif(not CORPUS.is_dir(), reason="the corpus is not in this checkout")
def test_the_registry_declares_the_situations_that_may_not_be_flipped() -> None:
    """Guards the exemption against silently becoming empty — which is exactly how the first
    version of the fix failed: it read a `registry` name that was a loop variable in scope and got
    nothing, so the check kept reporting all five."""
    prot = _protected()
    assert len(prot) >= 5, f"expected the pending_l2_types declarations, found {sorted(prot)}"
    assert "admin.sit.asset_in_custody" in prot
    assert "customer_support.sit.issue_under_diagnosis" in prot


@pytest.mark.skipif(not CORPUS.is_dir(), reason="the corpus is not in this checkout")
def test_nothing_is_reported_because_every_held_lifecycle_is_declared() -> None:
    """⛔ The retraction, as an assertion. Measured 2026-10-01: zero.

    A sixth situation appearing at draft+approved **without** a `pending_l2_types` declaration
    turns this red, which is the check's whole remaining purpose."""
    notes = _check()(_situations(), _protected())
    ids = sorted(note.split(":")[0] for note in notes)
    assert ids == [], (
        "a situation is approved and held at draft with nothing declaring it pending: " + repr(ids))


@pytest.mark.skipif(not CORPUS.is_dir(), reason="the corpus is not in this checkout")
def test_without_the_exemption_it_still_finds_the_five() -> None:
    """The mechanism is unchanged — only the verdict about those five is. If this stops finding
    them, the detector broke rather than the corpus changing."""
    ids = sorted(n.split(":")[0] for n in _check()(_situations()))
    assert set(ids) >= {
        "admin.sit.asset_in_custody",
        "customer_support.sit.issue_under_diagnosis",
    }, f"the detector no longer sees the declared-pending five: {ids}"
