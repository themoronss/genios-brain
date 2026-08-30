"""A card that reports what the system does not KNOW must not claim the authority to instruct.

Measured on the design partner's production org on 2026-08-30, after a full fresh re-sync:

    47 cards.  level distribution: {'prescriptive': 47}.
    25 of the 47 said only that something was missing —
      "alystventures.com: no concerns documented"
      "errorcore.dev: no problem documented yet"
      "rizvi.nu: no problem recorded yet"
      "boardy.ai: no concerns logged yet"
    23 headlines opened on a bare hostname rather than a name.

Two gates should have caught it and neither fired on a single row:

  * `card_builder.clarity_verdict` keys on three LEGACY pack reason codes
    (unanswered_email / commitment_overdue / meeting_no_followup). Every live card came from the
    compiled lane, whose codes are `opportunity`, `first_response_overdue`,
    `investor_relationship`, `investor_contact` — 0 of 47 matched.
  * `pipeline._apply_abstention` asks whether the EXPERTISE was accepted, which it was. That is a
    question about authority in general, not about whether this card found anything.

So the situation author answers it instead, once, in the corpus, and the answer travels on the
audited capability snapshot. The tests below are about the behaviour a reader sees, not the
plumbing that carries it.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts.abstention import ACTIONABLE, Level
from genios_engine.deliver import card_builder

EVAL = datetime(2026, 8, 30, tzinfo=timezone.utc)

#: The real render block off `sales.sit.deal_without_a_stated_problem`, the situation behind 13 of
#: the 47 live cards. Its `matches.when` is literally `[{path: deal.status, ...}, {absent:
#: business_need}]` — the situation IS an absence.
ABSENT_TEMPLATE = {
    "artifact_kind": "draft_reply",
    "render_hint": "name the account and the question a human has to settle",
    "fallback": {
        "headline": "{entity} — open deal, no problem stated",
        "situation": "The {entity} deal is progressing and nothing on record says what problem "
                     "is being solved.",
        "states_absence": True,
    },
}

#: `customer_support.sit.first_response_overdue` — 23 of the 47 live cards. Deliberately NOT
#: marked: "they wrote nine days ago and no reply has gone back" is a fact about the world, and
#: somebody really is waiting on the other end of it.
FINDING_TEMPLATE = {
    "artifact_kind": "draft_reply",
    "render_hint": "name the person who wrote and how long they have been waiting",
    "fallback": {
        "headline": "{who} is owed a reply",
        "situation": "They wrote {days} days ago and no reply has gone back.",
    },
}


#: A single real sentence from the other side. These tests are about the ABSENCE gate, and a
#: separate gate (added 2026-08-31) drops any card that cannot quote anybody — see
#: `test_a_card_must_quote_what_was_said.py`. Handing every case one quote keeps the two apart, so
#: a failure here means what it says rather than "no evidence was stubbed".
_QUOTED = [{"kind": "question", "quote": "Can you send pricing before Thursday?",
            "author": "hv@errorcore.dev", "from_counterparty": True}]


@pytest.fixture
def draft(monkeypatch):
    """Build a card the way the live pipeline does, with the graph reads stubbed out."""
    monkeypatch.setattr(card_builder, "load_node",
                        lambda *_a, **_k: ("errorcore.dev", "company", {}, {}))
    monkeypatch.setattr(card_builder, "_real_sources", lambda *_a, **_k: set())
    monkeypatch.setattr(card_builder, "resolve_assignee", lambda *_a, **_k: ("u1", "rule"))

    def _build(template, *, level="prescriptive", reason_code="opportunity", quotes=_QUOTED):
        signal = {"signal_id": "sig_1", "subject_node_id": "n1", "reason_code": reason_code,
                  "level": level, "score": 70, "capability_render": template}
        return card_builder.build_draft(object(), "org_1", signal,
                                        {"pack_id": "sales"}, EVAL, quotes=quotes)
    return _build


# ── 1 · the level a card is allowed to claim ────────────────────────────────────────────────
def test_a_situation_defined_by_an_absence_never_ships_as_an_instruction(draft):
    """"errorcore.dev: no problem documented yet" was delivered at level `prescriptive` — the
    system granting itself the authority to give an order while saying, in the same sentence, that
    it had nothing to give an order about. All 13 cards from this situation shipped that way."""
    card = draft(ABSENT_TEMPLATE)
    assert card["level"] == Level.REVIEW
    assert card["level"] not in ACTIONABLE


def test_the_abstention_says_why_so_it_cannot_be_mistaken_for_a_bug(draft):
    """An abstention with no stated cause is indistinguishable from something breaking. The reader
    has to be able to tell "we have not been taught this" from "we never captured the fact"."""
    card = draft(ABSENT_TEMPLATE)
    assert "missing from the record" in (card["abstained_because"] or "")


def test_a_card_with_nothing_to_say_offers_no_button_that_claims_to_do_something(draft):
    """`Run play` on a card whose content is "we do not know what problem this solves" promises an
    action nobody could name. Snooze and wrong stay: the reader must still be able to clear it."""
    card = draft(ABSENT_TEMPLATE)
    assert {a["type"] for a in card["actions"]} == {"snooze", "wrong"}


# ── 2 · which surface it reaches ────────────────────────────────────────────────────────────
def test_an_empty_card_leaves_the_app_queue_but_still_answers_a_question(draft):
    """The app asks "what should I do right now", and this card cannot answer it — it was 16 of
    the 47 lines the founder had to read to discover the system knew nothing. Ask and the API ask
    "tell me what you know", which it answers perfectly well, so it is not discarded."""
    card = draft(ABSENT_TEMPLATE)
    assert card["surfaces"] == ["ask", "api"]
    assert "app" not in card["surfaces"]


def test_a_real_finding_keeps_the_app_queue_and_its_authority(draft):
    """The rule is fewer EMPTY cards, not fewer cards. "They wrote nine days ago and no reply has
    gone back" names a person waiting on the other end; suppressing that to improve a count would
    be the same failure wearing the opposite mask.

    It keeps that authority on the strength of the evidence behind it, which the fixture supplies:
    a card that also cannot quote anybody is a different failure and is caught by a different gate.
    """
    card = draft(FINDING_TEMPLATE, reason_code="first_response_overdue")
    assert card["level"] == "prescriptive"
    assert "app" in card["surfaces"]
    assert any(a["type"] == "run_play" for a in card["actions"])


# ── 3 · the declaration is authored, not inferred from prose ────────────────────────────────
def test_the_flag_is_read_from_the_capability_snapshot_not_matched_in_the_text():
    """Inferring "this says nothing" by regex-matching the rendered sentence makes a card's
    authority depend on how a model happened to word it, and every rewording is then a silent
    change of authority. The situation author declares it; the value rides the version-hashed
    capability snapshot, so it cannot drift under an already-audited card."""
    assert card_builder.states_absence(ABSENT_TEMPLATE) is True
    assert card_builder.states_absence(FINDING_TEMPLATE) is False
    assert card_builder.states_absence(None) is False
    assert card_builder.states_absence({}) is False
    # Prose that READS like an absence but was never declared as one keeps its authority.
    assert card_builder.states_absence(
        {"fallback": {"headline": "x", "situation": "nothing on record says what happens next"}}
    ) is False


# ── 4 · the corpus actually carries the declaration ─────────────────────────────────────────
def test_the_two_live_absence_situations_are_marked_in_the_corpus():
    """A flag nothing sets changes nothing. These are the two situations behind 17 of the design
    partner's 47 cards, and 16 of the 25 that read as an absence."""
    import yaml
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "Domain Expertise"
    marked = set()
    for path in root.glob("*/capabilities/**/situations/*.yaml"):
        content = yaml.safe_load(path.read_text()) or {}
        fallback = ((content.get("render") or {}).get("fallback") or {})
        if fallback.get("states_absence"):
            marked.add((content.get("identity") or {}).get("id"))
    assert "sales.sit.deal_without_a_stated_problem" in marked
    assert "sales.sit.inbound_fit_check" in marked
    # The first-response situation reports a person waiting, not a hole in the record.
    assert "customer_support.sit.first_response_overdue" not in marked


def test_no_authored_fallback_narrates_an_absence_without_declaring_it():
    """The copy fix, held in place. A fallback whose job is to describe an empty state has to mark
    the card as abstaining rather than narrate the emptiness at `prescriptive`. Two shipped that
    way to a real user — "Nobody has replied to {who} yet" on 8 cards, and "nothing on record says
    what happens next" on 1 — and both said less than the evidence behind them supported."""
    import re
    import yaml
    from pathlib import Path

    # The founder's own measurement regex. "no reply has gone back" is deliberately NOT in it:
    # that is a fact about the world. `\byet\b` is, because it is the single token that made 9 of
    # the 25 live cards read as an absence ("Nobody has replied to ... yet", "no reply yet") while
    # the evidence underneath them was a real finding.
    empty_state = re.compile(r"no problem|no concern|nothing on record|not documented"
                             r"|not assessed|no next step|nobody has|\byet\b", re.I)
    root = Path(__file__).resolve().parents[1] / "Domain Expertise"
    offenders = []
    for path in root.glob("*/capabilities/**/situations/*.yaml"):
        content = yaml.safe_load(path.read_text()) or {}
        fallback = ((content.get("render") or {}).get("fallback") or {})
        if not fallback or fallback.get("states_absence"):
            continue
        text = f"{fallback.get('headline', '')} {fallback.get('situation', '')}"
        if empty_state.search(text):
            offenders.append((content.get("identity") or {}).get("id"))
    assert offenders == [], (
        "these fallbacks narrate an empty state at full prescriptive authority — either state the "
        f"finding instead, or declare states_absence: {offenders}")
