"""P4 group B — changed-file unit tests (hermetic, no database, no model)."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from types import SimpleNamespace

from genios_engine.context.graph_store import challenger_digest
from genios_engine.context.pipeline import _decision_decline
from genios_engine.reason.moments import draft_review as DR
from genios_engine.reason.moments import engagement as E
from genios_engine.reason.verify import passes as P
from genios_engine.reason.verify import store as V

NOW = datetime(2026, 9, 13, 9, tzinfo=timezone.utc)
QUOTE = "we have decided to go with another vendor for this rollout"


# ── carry-over: the decline is read off the reliable decision.* fact ────────────────────────────
def test_decline_is_read_from_a_decision_fact_whatever_slot_holds_the_words():
    assert _decision_decline([{"field": "decision.status", "subject": "vendor choice",
                               "value": "made", "evidence_text": QUOTE}]) == QUOTE
    assert _decision_decline([{"field": "decision.status", "subject": "Acme rollout",
                               "value": "declined", "evidence_text": ""}]) == "declined"


def test_no_decline_without_a_decision_fact_or_without_lost_words():
    assert _decision_decline([]) is None
    assert _decision_decline([{"field": "decision.status", "value": "pending",
                               "evidence_text": "we will decide next week"}]) is None
    # the words on a deal.* fact are the deal branch's business, not this rule's
    assert _decision_decline([{"field": "deal.stage", "value": QUOTE}]) is None


_CTX = "\n\ncontext — do not extract\n"
_LI = ("Priya: Thanks for the demo. After discussing internally we have decided to go with "
       "another vendor for this rollout. Appreciate your time.")


def test_counterparty_words_with_a_negative_reading_are_a_decline():
    from genios_engine.context.pipeline import _counterparty_decline as cd
    hit = cd(_LI + _CTX + "You: sharing the proposal", intent="inform", stance="negative")
    assert hit == ("After discussing internally we have decided to go with another vendor for "
                   "this rollout.")
    assert cd(_LI, intent="reject", stance="neutral") is not None
    assert cd(_LI, intent="inform", stance="neutral") is None          # no negative reading


def test_counterparty_decline_false_positive_guards():
    from genios_engine.context.pipeline import _counterparty_decline as cd
    # choosing US, although "decided against" / "other vendor" appear
    assert cd("We decided against the other vendor and will go with you.",
              intent="reject", stance="negative") is None
    # negated
    assert cd("We have not declined, we just need another week.", intent="reject",
              stance="negative") is None
    assert cd("We are not going with another vendor.", intent="reject",
              stance="negative") is None
    # the lost words only in the context section / quoted history
    assert cd("Priya: Thanks, will revert next week." + _CTX
              + "You: are you going with another vendor?", intent="reject",
              stance="negative") is None
    assert cd("Thanks.\n> we have decided to go with another vendor", intent="reject",
              stance="negative") is None
    assert cd("Noted.\n\nOn Mon, 8 Sep 2026 Rohit wrote:\nif you go with another vendor…",
              intent="reject", stance="negative") is None


def test_challenger_digest_is_a_value_identity():
    assert challenger_digest("lost") == challenger_digest("lost")
    assert challenger_digest({"a": 1, "b": 2}) == challenger_digest({"b": 2, "a": 1})
    assert challenger_digest("lost") != challenger_digest("won")


# ── seat filter ─────────────────────────────────────────────────────────────────────────────────
def _row(**kw):
    base = dict(id="disc_1", subject_node_id="node_deal", field="deal.status",
                held={"value": "open", "rank": 3, "source": "hubspot"},
                challenger={"value": "lost", "rank": 2, "source": "screen_session",
                            "event_id": "evt_1", "occurred_at": "2026-09-12 10:00:00+00:00"},
                status="open", created_at=NOW, updated_at=NOW, display_name="Acme — deal",
                node_type="deal", ch_scope=None, ch_principals=None, ch_event_source=None,
                h_scope=None, h_principals=None, h_at=None, h_source="hubspot",
                h_value_type="string", challenger_digest=challenger_digest("lost"),
                snoozed_until=None, resolution=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_an_org_discrepancy_is_visible_to_every_seat_and_to_an_api_key():
    r = _row()
    assert V.visible(r, "a@us.io") and V.visible(r, None)
    assert V.private_principals(r) is None


def test_a_private_side_is_visible_only_to_its_principals():
    r = _row(ch_scope="private", ch_principals=["a@us.io"])
    assert V.visible(r, "a@us.io")
    assert not V.visible(r, "b@us.io")
    assert not V.visible(r, None)
    assert V.private_principals(r) == frozenset({"a@us.io"})


def test_public_shape_is_the_frozen_contract():
    out = V.public(_row())
    assert {"id", "subject", "field", "held", "challenger", "created_at"} <= set(out)
    assert set(out["held"]) >= {"value", "source", "at"}
    assert out["challenger"]["value"] == "lost"
    assert out["challenger"]["at"] == "2026-09-12T10:00:00Z"


# ── verify moment ───────────────────────────────────────────────────────────────────────────────
def test_verify_situation_carries_accept_keep_snooze_with_the_discrepancy_id():
    sit = P.compose(_row(), seat_id="seat_owner")
    assert [a["id"] for a in sit["actions"]] == ["accept", "keep", "snooze"]
    assert all(a["payload"]["discrepancy_id"] == "disc_1" for a in sit["actions"])
    assert sit["kind"] == "verify" and sit["priority"] == "high"
    assert sit["key"] == "discrepancy:disc_1"
    other = P.compose(_row(challenger={"value": "won", "rank": 2}), seat_id="seat_owner")
    assert other["digest"] != sit["digest"]


def test_recipient_of_a_private_discrepancy_is_a_principal_never_an_outside_owner(monkeypatch):
    seats = {"a@us.io": "seat_a", "owner@us.io": "seat_owner"}
    monkeypatch.setattr(P, "owner_seat", lambda *a, **k: "seat_owner")
    assert P.recipient(None, "org", _row(), seats) == "seat_owner"
    assert P.recipient(None, "org", _row(ch_scope="private", ch_principals=["a@us.io"]),
                       seats) == "seat_a"
    assert P.recipient(None, "org", _row(ch_scope="private", ch_principals=["x@else.io"]),
                       seats) is None


# ── P-13 ────────────────────────────────────────────────────────────────────────────────────────
def test_duplicate_outreach_names_the_earlier_seat():
    m = E.compose(company_name="Acme", company="node_acme",
                  others=[("Anisha", datetime(2026, 9, 11, tzinfo=timezone.utc))], now=NOW)
    assert m["headline"] == "Anisha also contacted Acme this week"
    assert "2 d ago" in m["body"] and m["capability_id"] == E.CAPABILITY_ID


# ── draft review ────────────────────────────────────────────────────────────────────────────────
_CHANGE = {"node_id": "node_deal", "field": "deal.stage", "old": "negotiation",
           "new": "closed lost", "changed_at": "2026-09-12T08:00:00Z"}


def test_stale_value_check_fires_only_when_the_draft_states_the_old_value_alone():
    [n] = DR.stale_notes([_CHANGE], "Great to hear we are still in negotiation.")
    assert "negotiation" in n["text"] and "closed lost" in n["text"]
    assert n["evidence"][0]["kind"] == "fact_change"
    assert DR.stale_notes([_CHANGE], "Sorry it ended closed lost after the negotiation.") == []
    assert DR.stale_notes([_CHANGE], "Renegotiation soon?") == []          # word boundary
    assert DR.stale_notes([{**_CHANGE, "old": "2026-09-10T00:00:00Z", "new": "2026-09-18"}],
                          "due 2026-09-10T00:00:00Z") == []


def test_notes_never_copy_the_draft_and_are_capped_at_two():
    draft = "Hi Priya, attaching the signed order form and the onboarding plan for next week."
    notes = DR.finalize([{"text": "Say: " + draft[:50]}, {"text": "The deal is marked lost."},
                         {"text": "The deal is marked lost."}, {"text": "Their title changed."},
                         {"text": "A third note."}], draft)
    assert [n["text"] for n in notes] == ["The deal is marked lost.", "Their title changed."]


def test_moment_has_no_rewrite_field_and_carries_only_the_draft_hash():
    draft = "Hi Priya, still in negotiation?"
    digest = DR.draft_digest(draft)
    m = DR.moment_content([{"text": "The stage changed.", "evidence": [], "source": "stale"}],
                          digest=digest)
    assert set(m) == {"kind", "priority", "headline", "body", "actions", "evidence",
                      "ttl_seconds", "capability_id", "capability_version"}
    assert m["capability_id"] == "moment.draft_review" and m["body"] == "• The stage changed."
    assert {"kind": "draft", "sha256": digest} in m["evidence"]
    assert draft not in repr(m)


def test_review_answers_none_when_the_budget_runs_out(monkeypatch):
    monkeypatch.setattr(DR, "_compute", lambda *a, **k: time.sleep(1.0) or {"x": 1})
    t0 = time.monotonic()
    assert DR.review(None, org_id="o", email=None, participants=[], entities=[], draft="hi",
                     now=NOW, timeout_s=0.2) is None
    assert time.monotonic() - t0 < 0.6
