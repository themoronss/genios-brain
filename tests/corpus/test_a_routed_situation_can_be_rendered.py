"""A situation that routes and cannot render is worse than one that does not route.

`card_builder` takes `capability_render` from the situation's own `render` block, carried on the
audited capability snapshot, and falls through to the TENANT PACK when it is absent. Its comment
records what that cost once already: *"the lookup therefore returned `{}` for every compiled card —
an empty render_hint, so the prompt carried no guidance and eighteen cards came back reading alike,
and an empty fallback, so a rejected line shipped as the default `{stage}` slot: the word 'open'."*

The failure is worse now than it was then, because `CardStore` has since grown a blank-card gate:
a card with no headline is refused inside the lease. So a routed situation with no `render` block
produces situations every sweep, compiles them, and then silently drops every card at the last
step.

`condition-now-satisfied.yaml` was in exactly that state. It shipped with no `render` block and
said why — "a situation that routes nothing has no card to write" — and that was true when it was
written. `domain_spec` later bound the `condition_met` anchor to it, and nothing rechecked the
note. It is the HIGHEST-PRIORITY situation in the Admin corpus at 8,200bp, it is the twin
`correlation_timeline` was built for, and it could not reach a reader.

This test is the recheck that did not happen.
"""
import pathlib

import pytest
import yaml

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_CORPUS = _ROOT / "Domain Expertise"


def _routed_types() -> set[str]:
    """Every L2 situation type some domain's GENERATED registry actually claims."""
    found: set[str] = set()
    for path in _CORPUS.glob("*/registry/situation-capability-map.yaml"):
        found |= set((yaml.safe_load(path.read_text()) or {}).get("map") or {})
    return found


def _situations() -> list[tuple[pathlib.Path, dict]]:
    out = []
    for path in _CORPUS.glob("*/capabilities/*/*/situations/*.yaml"):
        doc = yaml.safe_load(path.read_text())
        if isinstance(doc, dict):
            out.append((path, doc))
    return out


def _admitted(doc: dict) -> bool:
    """Whether this document can reach a LIVE prescriptive card.

    The admission ceremony is three things together — `identity.status == 'stable'`,
    `metadata.review_status == 'approved'`, and an acceptance hash — and a document short of any
    of them routes in the MEASUREMENT compile only. `test_l3_route_vocabulary_contract` records
    the same rule for `condition_awaiting_review`: draft "on purpose: it routes in the measurement
    compile and cannot reach a live prescriptive card until a named human accepts it".

    So a draft with no `render` block is not a dropped card; it is an unfinished document. Holding
    drafts to this rule would turn a real defect into a queue of style failures and the real one
    would be lost in it.
    """
    identity, meta = doc.get("identity") or {}, doc.get("metadata") or {}
    return (str(identity.get("status") or "") == "stable"
            and str(meta.get("review_status") or "") == "approved"
            and bool((doc.get("admission") or {}).get("accepted_content_hash")))


def _routed_situations() -> list[tuple[str, pathlib.Path, dict]]:
    """Routed AND admitted — the set that can actually reach a reader."""
    routed = _routed_types()
    out = []
    for path, doc in _situations():
        types = [str(t) for t in (doc.get("matches") or {}).get("l2_situation_types") or []]
        if any(t in routed for t in types) and _admitted(doc):
            out.append((str((doc.get("identity") or {}).get("id") or path.stem), path, doc))
    return sorted(out)


def test_there_are_routed_situations_to_check() -> None:
    assert len(_routed_situations()) >= 10, "the routing scan found almost nothing — it is broken"


def test_a_draft_is_exempt_because_it_cannot_reach_a_reader_anyway() -> None:
    """THE SCOPE OF THE RULE, pinned so it is not quietly widened. Eight situations had no
    `render` block when this was written; seven are Customer Support drafts that cannot reach a
    live card at all, and exactly one — `admin.sit.condition_now_satisfied`, stable, approved,
    hashed and the highest-priority card in the Admin corpus — could route and could not render.
    Widening this test to drafts would bury that one in seven style failures."""
    drafts = [str((doc.get("identity") or {}).get("id"))
              for _path, doc in _situations() if not _admitted(doc)]
    assert drafts, "no drafts found — the admission check is probably inverted"
    assert "admin.sit.condition_now_satisfied" not in drafts, (
        "the one that was genuinely broken is admitted, and must stay inside this rule")


@pytest.mark.parametrize("sid", [s[0] for s in _routed_situations()])
def test_every_routed_situation_has_the_copy_a_card_needs(sid: str) -> None:
    """THE RECHECK THAT DID NOT HAPPEN. A `render` block is not decoration: it IS
    `capability_render`, and without it the compiled lane has no copy at all."""
    doc = {s[0]: s[2] for s in _routed_situations()}[sid]
    render = doc.get("render") or {}
    fallback = render.get("fallback") or {}

    assert render, (
        f"{sid} routes and has no `render` block. `card_builder` reads `capability_render` from "
        f"it and falls through to the tenant pack, which authors none of the L2 situation types — "
        f"so the headline is empty and `CardStore` refuses the card inside the lease. It will "
        f"produce situations every sweep and never a card.")
    assert str(fallback.get("headline") or "").strip(), (
        f"{sid} routes with no fallback headline. The fallback is what ships when the model's "
        f"line is refused, which on the live org was 35 of 56 cards — the majority.")
    assert str(fallback.get("situation") or "").strip(), f"{sid} routes with no fallback body."
    assert str(render.get("render_hint") or "").strip(), (
        f"{sid} routes with no render_hint, so the prompt carries no guidance and its cards read "
        f"like every other card — the defect `card_builder` records as eighteen alike.")


def test_the_highest_priority_admin_card_can_render() -> None:
    """Named on its own because it is the one that was broken, and because a satisfied condition
    has the shortest half-life of anything this domain surfaces: the evidence that satisfied it is
    public, and everyone else waiting on the same condition can see it too."""
    by_id = {s[0]: s[2] for s in _routed_situations()}
    doc = by_id["admin.sit.condition_now_satisfied"]
    assert doc["priority_bp"] == 8200
    assert "{entity}" in doc["render"]["fallback"]["headline"]
