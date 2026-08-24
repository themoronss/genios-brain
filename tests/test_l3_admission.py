"""L3-03/04: production authority requires a named human accepting the exact bytes routed.

`identity.stub` was the entire admission ceremony — an author flipping `stub: true → false` in
a text editor granted production authority, and the first content to gain customer authority on
activation would have been machine-written unreviewed drafts. `accepted` was unrepresentable:
no field anywhere could say a human had accepted anything.
"""
from types import SimpleNamespace

from genios_engine.packs.compiler.capability_resolver import _admission_reason
from genios_engine.platform.canonical import semantic_hash


def _capability(**over):
    content = {
        "identity": {"id": "sales.x.y", "status": "stable", "stub": False},
        "metadata": {"review_status": "approved", "reviewed_by": "harsh"},
        "description": "Qualify the live opportunity.",
    }
    content.update(over)
    # acceptance pins the hash of what was REVIEWED — content minus the admission record itself
    content["admission"] = {"accepted_content_hash": semantic_hash(
        {k: v for k, v in content.items() if k != "admission"})}
    return SimpleNamespace(content=content, content_hash=semantic_hash(content))


def test_a_fully_accepted_capability_is_admitted():
    assert _admission_reason(_capability()) is None


def test_a_stub_flip_alone_grants_nothing():
    """The exact hole: stub=false with no review is still four gates short of authority."""
    cap = _capability(metadata={})
    assert _admission_reason(cap) == "review_not_approved"


def test_approval_without_a_named_reviewer_is_not_approval():
    cap = _capability(metadata={"review_status": "approved", "reviewed_by": "  "})
    assert _admission_reason(cap) == "no_named_reviewer"


def test_draft_status_never_carries_authority():
    cap = _capability(identity={"id": "sales.x.y", "status": "draft", "stub": False})
    assert _admission_reason(cap) == "identity_status_draft"


def test_an_edit_after_review_silently_un_accepts():
    """The hash pin is the difference between accepting a FILE and accepting its CONTENT."""
    cap = _capability()
    cap.content["description"] = "Edited after the reviewer signed off."
    assert _admission_reason(cap) == "content_changed_since_acceptance"


def test_acceptance_without_a_hash_is_not_acceptance():
    cap = _capability()
    cap.content["admission"] = {}
    assert _admission_reason(cap) == "no_accepted_hash"
