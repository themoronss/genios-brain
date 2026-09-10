"""The words' own acceptance — a situation may not instruct on somebody else's signature.

    pytest tests/packs/compiler/test_situation_admission.py -q

THE HOLE. `capability_resolver._admission_reason` asks a named human to accept a CAPABILITY's
exact bytes, and its comment says why: *"an author flipping `stub: true → false` in a text editor
granted production authority, and the first content to gain customer authority on activation
would have been 12 machine-written unreviewed drafts (`metadata.created_by: ai`)."*

A SITUATION was never asked anything. `authoring.py` parses no `admission` block for one and
`_admission_reason` takes a capability, so a situation's `identity.status` and
`metadata.review_status` were read by nothing at all. A machine-written situation file whose
owning capability is approved and hash-accepted shipped a fully PRESCRIPTIVE card — the ceremony
satisfied by somebody else's signature, on words that human never saw.

MEASURED ON THIS CORPUS before the gate was written: **24 of 62 authored situations** would not
clear it. Fifteen have `review_status: unreviewed` and no reviewer at all. Two of the twenty-four
were added by this branch, which is how the defect was found.

IT FLAGS, IT DOES NOT REMOVE, and that asymmetry is the whole design. An unadmitted capability is
dropped in live mode because its expertise is what the answer is made of. A situation's DETECTION
is Layer 2's and is evidence-backed whatever a reviewer thinks of the prose; only the prose is
unreviewed. So the gap lands in `admission_gaps` → `plan.admitted=False` → `review_state='draft'`
→ `deliver/pipeline._apply_abstention` downgrades the card to an observation. The finding still
ships. It stops instructing.
"""

from __future__ import annotations

import glob

import pytest
import yaml

from genios_engine.packs.compiler.capability_resolver import situation_admission_reason

pytestmark = pytest.mark.unit

APPROVED = {"identity": {"status": "stable"},
            "metadata": {"review_status": "approved", "reviewed_by": "harsh"}}


def variant(**over) -> dict:
    doc = {"identity": dict(APPROVED["identity"]), "metadata": dict(APPROVED["metadata"])}
    for key, value in over.items():
        section, _, field = key.partition("__")
        if value is None:
            doc[section].pop(field, None)
        else:
            doc[section][field] = value
    return doc


# =============================================================================================
# The three questions, each of which a human actually answers.
# =============================================================================================
def test_a_fully_accepted_situation_may_instruct():
    assert situation_admission_reason(variant()) is None


def test_a_draft_identity_may_not():
    """Same first question the capability ceremony asks. `status: draft` is the author saying
    the file is not finished, and a card built from it is finished by definition."""
    assert situation_admission_reason(variant(identity__status="draft")) == "identity_status_draft"


def test_an_absent_identity_status_is_not_a_pass():
    """Fail closed. A file that says nothing about its own readiness has not declared it ready."""
    assert situation_admission_reason(variant(identity__status=None)) == "identity_status_absent"


@pytest.mark.parametrize("status", ["draft", "unreviewed", "experimental", ""])
def test_anything_but_approved_is_refused(status):
    assert situation_admission_reason(
        variant(metadata__review_status=status)) == "review_not_approved"


def test_approved_by_nobody_is_refused():
    """`review_status: approved` with no reviewer is a field somebody set, not a person who
    read it — the exact difference the capability rule's `no_named_reviewer` exists to draw."""
    assert situation_admission_reason(variant(metadata__reviewed_by="")) == "no_named_reviewer"
    assert situation_admission_reason(variant(metadata__reviewed_by="   ")) == "no_named_reviewer"
    assert situation_admission_reason(variant(metadata__reviewed_by=None)) == "no_named_reviewer"


def test_a_situation_with_no_metadata_at_all_is_refused():
    assert situation_admission_reason({"identity": {"status": "stable"}}) == "review_not_approved"


def test_an_empty_document_is_refused_rather_than_crashing():
    """The resolver hands whatever the file parsed to. An empty or malformed one must fail
    closed, not raise into a compile that would then have no route at all."""
    assert situation_admission_reason({}) is not None
    assert situation_admission_reason(None) is not None


def test_the_order_of_refusal_is_stable():
    """A file failing all three reports the FIRST question, so a fixer works one step at a time
    rather than being handed a list they cannot act on."""
    assert situation_admission_reason(
        {"identity": {"status": "draft"}, "metadata": {}}) == "identity_status_draft"


# =============================================================================================
# The corpus, as it actually stands. This is a census, not a target.
# =============================================================================================
def _authored():
    for path in sorted(glob.glob("Domain Expertise/**/situations/*.yaml", recursive=True)):
        doc = yaml.safe_load(open(path)) or {}
        yield (doc.get("identity") or {}).get("id") or path, doc


def test_the_gate_reaches_the_corpus_and_is_not_vacuous():
    """A guard that refuses nothing passes forever. This pins BOTH halves: some situations
    clear the ceremony and some do not, so the gate is doing work in each direction."""
    verdicts = {sid: situation_admission_reason(doc) for sid, doc in _authored()}

    assert verdicts, "no authored situations found — the glob is wrong"
    assert any(v is None for v in verdicts.values()), "nothing clears the gate"
    assert any(v is not None for v in verdicts.values()), "nothing is refused by it"


def test_the_two_situations_this_branch_added_are_refused_until_a_human_accepts_them():
    """THE CASE THAT FOUND THE HOLE. Both were written by this session, both are
    `review_status: draft`, and both were producing prescriptive cards through
    `admin.executive_support.inbox_and_correspondence` — a capability a human accepted years of
    other words under.

    This test is not permanent. When Harsh reviews either file and sets `status: stable` /
    `review_status: approved` / `reviewed_by:`, this assertion is what should be deleted, and
    deleting it is the record that the acceptance happened.
    """
    by_id = dict(_authored())

    for sid in ("admin.sit.organization_gone_quiet", "admin.sit.campaign_awaiting_reply"):
        assert sid in by_id, f"{sid} is no longer authored"
        assert situation_admission_reason(by_id[sid]) == "identity_status_draft", sid


def test_every_refusal_names_a_reason_a_person_can_act_on():
    """A gap that reads `identity_status_None` or an empty string tells a fixer nothing."""
    known = {"review_not_approved", "no_named_reviewer"}
    for sid, doc in _authored():
        reason = situation_admission_reason(doc)
        if reason is None:
            continue
        assert reason in known or reason.startswith("identity_status_"), (sid, reason)
        assert reason.strip() and "None" not in reason, (sid, reason)
