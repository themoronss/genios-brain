"""A card that cannot say WHAT was said is not intelligence — and 48 of 55 could not.

Measured on the design partner's production org on 2026-08-31, read-only, over the 55 live cards:

    cards                                     55
    carrying a quotable evidence line          7
    app surface                               41
    level                       {prescriptive: 41, review: 14}

What the app actually showed for the largest group:

    "Thread with nikhil@addis.im is owed a reply
     They wrote several days ago and no reply has gone back."

That card knows THAT somebody wrote and cannot say WHAT they wrote, so its Run Play button
offered to draft a reply to a message whose contents were nowhere in the process.

THE HOP THAT WAS BROKEN was the last one, not the oldest suspicion. Measured per hop:

  * L1 stores the body in full. 349 payloads, median 1,612 bytes, max 22,200, none under 400.
    The long-standing ~280-character truncation is not present on this data.
  * L2 extracts real quotable sentences — 405 of 526 observations carry evidence text, 304 of
    them distinct, up to 319 characters: "Why don't you use the cal link in my signature to find
    us a time?", "Sorry, had to travel. Earliest reschedule if possible".
  * DELIVERY could not reach any of it. `load_evidence_quotes` asked for observations whose
    `subject_node_id` IS THE CARD'S OWN NODE. L2 mints every observation onto a PERSON (512 of
    526) or a service (14) and never onto a thread or a company — and 38 of the 55 cards are
    keyed on a company or a thread. For all 38 the join returned ZERO ROWS. Not evidence with
    empty text: no rows at all.

So the loader resolves the subject to its observations by NODE TYPE, and attributes every line to
a speaker. The attribution is not decoration: 161 of the 526 observations were extracted from the
FOUNDER'S OWN outgoing mail, and an unlabelled list of sentences is how "they asked about
pricing" gets written off a sentence we sent.

The tests below are about the behaviour a reader sees. Part 1 runs hermetically on the gate; Part
2 runs the real SQL against a real Postgres, because the failure being fixed here is a query that
was green in every test and matched zero rows on the live graph.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.contracts.abstention import ACTIONABLE, Level
from genios_engine.deliver import card_builder

EVAL = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)

#: The account holder. Anything sent from here is OUR words, whatever it says.
OURS = "mrrohitswerashi@gmail.com"
#: The other side of the conversation the card is about.
THEIRS = "nitesh.pant@devdashlabs.com"


def _q(kind, quote, author, *, mine=(OURS,)):
    """A quote shaped the way the loader emits one, including the speaker it resolved."""
    return {"kind": kind, "quote": quote, "author": author,
            "from_counterparty": (None if author is None else author not in mine)}


#: A real line off the design partner's graph, and the whole point of the exercise: this is a
#: sentence a manager could act on.
REAL_ASK = _q("question", "Why don't you use the cal link in my signature to find us a time?",
              THEIRS)

#: `customer_support.sit.first_response_overdue` — 11 of the 55 live cards, every one of them
#: keyed on a thread node and every one of them quoting nothing. Deliberately NOT marked
#: `states_absence`: somebody really is waiting, so the absence gate must not be what catches it.
FINDING_TEMPLATE = {
    "artifact_kind": "draft_reply",
    "render_hint": "name the person who wrote and how long they have been waiting",
    "fallback": {"headline": "{who} is owed a reply",
                 "situation": "They wrote {days} days ago and no reply has gone back."},
}


@pytest.fixture
def draft(monkeypatch):
    """Build a card the way the live pipeline does, with the graph reads stubbed out."""
    monkeypatch.setattr(card_builder, "load_node",
                        lambda *_a, **_k: ("devdashlabs.com", "company", {}, {}))
    monkeypatch.setattr(card_builder, "_real_sources", lambda *_a, **_k: set())
    monkeypatch.setattr(card_builder, "resolve_assignee", lambda *_a, **_k: ("u1", "rule"))

    def _build(quotes, *, template=FINDING_TEMPLATE, reason_code="first_response_overdue"):
        signal = {"signal_id": "sig_1", "subject_node_id": "n1", "reason_code": reason_code,
                  "level": "prescriptive", "score": 70, "capability_render": template}
        return card_builder.build_draft(object(), "org_1", signal,
                                        {"pack_id": "sales"}, EVAL, quotes=quotes)
    return _build


# ── 1 · what counts as having something to quote ────────────────────────────────────────────
def test_our_own_outgoing_sentence_is_never_evidence_of_what_they_asked():
    """161 of the 526 observations on this org were extracted from the founder's own sent mail.

    `graph_source_refs.evidence` records what was said and never who said it, so before the author
    was carried through, our follow-up — "I am writing this again in order to get an update on the
    details I shared with you" — was indistinguishable from the counterparty asking us something.
    A card built on that would tell the founder to answer himself.
    """
    ours = _q("followup_sent",
              "I am writing this again in order to get an update on the details I shared", OURS)
    assert ours["from_counterparty"] is False
    assert card_builder.quotable([ours]) == []
    assert card_builder.quotable([ours, REAL_ASK]) == [REAL_ASK]


def test_a_quote_nobody_can_be_shown_to_have_said_is_not_used_either():
    """`from_counterparty` is tri-state, and the third state is the honest one. When the event that
    minted an observation is gone, no one can say whose words these are — and "they asked X" on a
    sentence we cannot attribute is exactly the invention this codebase refuses to make. It
    abstains rather than guessing, on the same reasoning that leaves `deal.value` underived."""
    orphan = _q("question", "Can you send pricing before Thursday?", None)
    assert orphan["from_counterparty"] is None
    assert card_builder.quotable([orphan]) == []


@pytest.mark.parametrize("kind", ["mention:person", "mention:company", "mention:entity",
                                  "email_relevance"])
def test_an_extracted_name_is_not_a_statement(kind):
    """These kinds record that a NAME occurred, not that anything was said. Measured average text
    length on this org: `mention:person` 31 characters ("Boardy Boardman"), `mention:company` 36
    ("pablo@yappjam.com"), `mention:entity` 37 — and `email_relevance` carries no text at all in
    any of its 121 rows. A card whose only quote is somebody's name still cannot say what that
    person asked, which is the entire reason to hold a quote."""
    assert card_builder.quotable([_q(kind, "Boardy Boardman", THEIRS)]) == []


def test_the_bar_is_one_sentence_and_terseness_is_not_a_failure():
    """This gate must never become a quality filter. The founder's rule is fewer HOLLOW cards, not
    fewer cards — so the shortest real thing anybody said is enough to clear it. "Yes, it works for
    me." is four words off a live thread and it is a finding: it settles a question."""
    assert card_builder.quotable([_q("positive_reply", "Yes, it works for me.", THEIRS)])


# ── 2 · what the gate does to the card ──────────────────────────────────────────────────────
def test_a_card_that_can_quote_nobody_leaves_the_app_but_still_answers_a_question(draft):
    """The app asks "what should I do right now" and this card cannot answer it: it can say
    somebody wrote and not what they wrote. Ask and the API ask "tell me what you know", which the
    typed facts answer perfectly well, so the card is not discarded — it is demoted."""
    card = draft([])
    assert card["surfaces"] == ["ask", "api"]
    assert "app" not in card["surfaces"]


def test_a_card_that_can_quote_nobody_stops_claiming_the_authority_to_instruct(draft):
    """`review` is the level the vocabulary already reserves for "something is missing and a human
    must look", and the missing thing is the message itself."""
    card = draft([])
    assert card["level"] == Level.REVIEW
    assert card["level"] not in ACTIONABLE


def test_it_offers_no_button_to_draft_a_reply_it_cannot_write(draft):
    """Run Play on a card with no evidence promised a draft response to a message whose contents
    were never in the process — 35 of the 56 live renders came back `raw_slot` with an empty
    artifact body while the button still advertised one. Snooze and wrong stay: the reader must
    still be able to clear it."""
    card = draft([])
    assert {a["type"] for a in card["actions"]} == {"snooze", "wrong"}


def test_the_abstention_names_the_missing_thing_so_it_reads_as_a_verdict_not_a_bug(draft):
    """An abstention with no stated cause is indistinguishable from something breaking. The reader
    has to be able to tell "we never captured what they said" from "the renderer failed"."""
    assert "open the thread" in (draft([])["abstained_because"] or "")


def test_one_real_sentence_restores_the_app_queue_and_the_draft_button(draft):
    """The other half of the gate, and the half that proves it is not just suppression. The same
    card, same situation, same everything — with one line the other side actually wrote — keeps
    full authority, because now it can say what the reply has to answer."""
    card = draft([REAL_ASK])
    assert "app" in card["surfaces"]
    assert card["level"] == "prescriptive"
    assert any(a["type"] == "run_play" for a in card["actions"])


def test_a_card_carrying_only_our_own_words_is_treated_as_carrying_nothing(draft):
    """The two halves composed. A thread where only WE have spoken is precisely the case the app
    must not present as "here is what they asked" — and it is common, because a first-response
    card is often built on a thread the founder himself opened."""
    card = draft([_q("followup_sent", "Sharing a few details for your reference", OURS),
                  _q("mention:person", "Nitesh Pant", THEIRS)])
    assert "app" not in card["surfaces"]
    assert card["level"] == Level.REVIEW


# ── 3 · the renderer is told who spoke ──────────────────────────────────────────────────────
def test_the_prompt_attributes_every_line_to_a_speaker():
    """The model was handed one undifferentiated block of sentences and asked to write what "they"
    asked. With our own outgoing mail in that block, misattribution was not a risk but a
    certainty. The speaker is named per line, and the unattributable case says so."""
    from genios_engine.deliver.render import _prompt

    prompt = _prompt("first_response_overdue", FINDING_TEMPLATE, {}, {},
                     [REAL_ASK, _q("followup_sent", "Any update on the details?", OURS),
                      _q("question", "Can you send pricing?", None)])
    assert f"{THEIRS} wrote" in prompt
    assert "the account holder wrote" in prompt
    assert "source unattributed" in prompt
    assert "NEVER present something the account holder wrote" in prompt


def test_the_authors_address_is_grounded_so_the_card_may_name_who_wrote():
    """The invention guard rejects any name that is not in the corpus. "nitesh.pant@devdashlabs.com
    asked about a time" — the whole content of the card — was rejected as an invented name whenever
    that address was not already a fact value. It came off the source event, so it is grounded for
    exactly the reason the quote itself is."""
    from genios_engine.deliver.render import _corpus

    corpus_text, _ = _corpus({}, {}, (), [REAL_ASK])
    assert THEIRS in corpus_text
    assert "cal link" in corpus_text


# ── 4 · the query reaches the rows, against a real database ─────────────────────────────────
#
# Every test below runs the shipped SQL on real Postgres. The bug being fixed was a query that
# passed every hermetic test and matched ZERO rows on the live graph, so a fixture that encodes
# the shape the pipeline does not write would reproduce the fault rather than catch it.
ORG = "org_quote_reach_tests"

#: Reused rather than re-copied. It discovers its NOT-NULL columns from `information_schema`, so a
#: later migration adding one does not turn this file into skips.
from tests.test_deal_status_survives_a_sync import _seed_org  # noqa: E402


def _seed(store):
    """One thread, one company, two people, wired the way the live pipeline writes them.

    `works_at` is PERSON -> COMPANY (`context/pipeline.py::_works_at`), a thread node is keyed
    `thread:<gmail thread id>` and `source_events.parent_object_id` holds that same id bare —
    which is the join the loader now makes. Two threads exist on purpose: a card about one
    conversation must not quote a sentence from the other.
    """
    _seed_org(store, ORG)
    with store.engine.begin() as c:
        for t in ("graph_source_refs", "graph_observations", "graph_edges", "graph_nodes",
                  "source_events"):
            c.execute(text(f"delete from {t} where org_id = :o"), {"o": ORG})
        cols = {r.column_name: r.data_type for r in c.execute(text(
            "select column_name, data_type from information_schema.columns where "
            "table_name='source_events' and is_nullable='NO' and column_default is null")).all()}

        def event(eid, thread, actor):
            vals = {"event_id": eid, "org_id": ORG, "source": "gmail",
                    "object_type": "email_message", "outcome": "emitted", "occurred_at": EVAL,
                    "parent_object_id": thread, "source_object_id": eid,
                    "actor": json.dumps({"email": actor}), "domain_hints": json.dumps([])}
            for name, dt in cols.items():
                vals.setdefault(name, EVAL if ("time" in dt or "date" in dt)
                                else 0 if ("int" in dt or "numeric" in dt) else
                                "{}" if "json" in dt else f"{name}_{eid}")
            c.execute(text(f"insert into source_events ({','.join(vals)}) values "
                           f"({','.join(':' + k for k in vals)})"), vals)

        def node(nid, ntype, key, name):
            c.execute(text(
                "insert into graph_nodes (node_id, version, org_id, node_type, canonical_key, "
                "display_name, identity_strength, attributes, valid_from) values "
                "(:i,1,:o,:t,:k,:d,'strong','{}'::jsonb,:v)"),
                {"i": nid, "o": ORG, "t": ntype, "k": key, "d": name, "v": EVAL})

        def observe(oid, subject, kind, quote, eid, *, at=EVAL):
            c.execute(text(
                "insert into graph_observations (observation_id, org_id, subject_node_id, kind, "
                "status, confidence, occurred_at, created_by_event_id) values "
                "(:i,:o,:n,:k,'active',0.9,:t,:e)"),
                {"i": oid, "o": ORG, "n": subject, "k": kind, "t": at, "e": eid})
            c.execute(text(
                "insert into graph_source_refs (source_ref_id, org_id, observation_id, event_id, "
                "source, evidence) values (:i,:o,:b,:e,'gmail',cast(:v as jsonb))"),
                {"i": f"sr_{oid}", "o": ORG, "b": oid, "e": eid,
                 "v": json.dumps({"text": quote})})

        # IDS ARE NAMESPACED because `graph_edges_pkey` is `edge_version_id` ALONE — globally
        # unique, not per-org. `test_account_contact_metrics` seeds an edge it also calls
        # "e_works" too, and with `on conflict do nothing` whichever file ran second silently
        # lost its edge and failed on a row it had every reason to expect: a scratch database is
        # shared, so an id that is not namespaced is a booby trap for the next file.
        def edge(eid, etype, frm, to):
            c.execute(text(
                "insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, "
                "from_node_id, to_node_id, authority_rank, confidence, valid_from) values "
                "(:v,:i,:o,:t,:f,:d,1,0.9,:s)"),
                {"v": f"ev_{eid}", "i": eid, "o": ORG, "t": etype, "f": frm, "d": to, "s": EVAL})

        node(f"{ORG}_person", "person", f"email:{THEIRS}", THEIRS)
        node(f"{ORG}_other", "person", "email:someone@elsewhere.test", "someone@elsewhere.test")
        node(f"{ORG}_company", "company", "domain:devdashlabs.com", "devdashlabs.com")
        node(f"{ORG}_thread", "thread", "thread:19fa8b57842adaa4", f"Thread with {THEIRS}")
        edge(f"{ORG}_works", "works_at", f"{ORG}_person", f"{ORG}_company")
        edge(f"{ORG}_corr", "corresponded_with", f"{ORG}_person", f"{ORG}_thread")

        event(f"{ORG}_evt_in", "19fa8b57842adaa4", THEIRS)
        event(f"{ORG}_evt_other", "19cbc88fec917fdd", THEIRS)
        event(f"{ORG}_evt_ours", "19fa8b57842adaa4", OURS)
        # In the thread the card is about, from the other side — the sentence the card owes.
        observe(f"{ORG}_obs_ask", f"{ORG}_person", "question", REAL_ASK["quote"], f"{ORG}_evt_in")
        # Same person, DIFFERENT conversation. A thread card must not reach this.
        observe(f"{ORG}_obs_elsewhere", f"{ORG}_person", "objection", "We already have a vendor for this.",
                f"{ORG}_evt_other", at=EVAL - timedelta(days=1))
        # Our own words, in the same thread.
        observe(f"{ORG}_obs_ours", f"{ORG}_person", "followup_sent", "Any update on what I shared?",
                f"{ORG}_evt_ours")


@pytest.fixture(scope="module")
def seeded(pg_store):
    _seed(pg_store)
    return pg_store


def test_a_thread_card_reaches_the_words_spoken_in_that_thread(seeded):
    """The 11 first-response cards are all keyed on a thread node, and observations never sit on
    one — so the old query returned zero rows for every one of them and the app showed "they wrote
    several days ago" with no idea what about. The thread id the node is keyed on is the same id
    the event carries, which is the join that was never made."""
    quotes = card_builder.load_evidence_quotes(seeded, ORG, f"{ORG}_thread", identities=(OURS,))
    assert REAL_ASK["quote"] in [q["quote"] for q in quotes]


def test_a_thread_card_does_not_borrow_a_sentence_from_another_conversation(seeded):
    """Scoping to the PEOPLE on a thread would have been easier and would have let a card about one
    conversation quote an objection raised in a different one. The card names a thread, so the
    evidence is held to that thread."""
    quotes = card_builder.load_evidence_quotes(seeded, ORG, f"{ORG}_thread", identities=(OURS,))
    assert "We already have a vendor for this." not in [q["quote"] for q in quotes]


def test_a_company_card_reaches_the_words_of_the_people_who_work_there(seeded):
    """27 of the 55 cards are keyed on a company node, which holds no observations of its own.
    Company evidence is honest at account width — the card names the company and these are its
    people — so unlike a thread it is not held to one conversation."""
    quotes = card_builder.load_evidence_quotes(seeded, ORG, f"{ORG}_company", identities=(OURS,))
    said = [q["quote"] for q in quotes]
    assert REAL_ASK["quote"] in said
    assert "We already have a vendor for this." in said


def test_a_person_card_still_reaches_its_own_observations(seeded):
    """The 7 of 55 that already worked. A fix that reaches new rows by losing the ones that were
    already right has not moved the number it claims to move."""
    quotes = card_builder.load_evidence_quotes(seeded, ORG, f"{ORG}_person", identities=(OURS,))
    assert REAL_ASK["quote"] in [q["quote"] for q in quotes]


def test_the_speaker_survives_the_trip_from_the_source_event(seeded):
    """The attribution has to come off real rows, not a dict a test wrote. `source_events.actor`
    is the only place that knows who spoke, and the whole no-misattribution guarantee rests on
    this join holding on the live schema."""
    quotes = card_builder.load_evidence_quotes(seeded, ORG, f"{ORG}_thread", identities=(OURS,))
    by_quote = {q["quote"]: q for q in quotes}
    assert by_quote[REAL_ASK["quote"]]["from_counterparty"] is True
    assert by_quote[REAL_ASK["quote"]]["author"] == THEIRS
    assert by_quote["Any update on what I shared?"]["from_counterparty"] is False


def test_the_tenants_own_mail_is_excluded_from_what_the_card_may_quote(seeded):
    """End to end on real rows: our follow-up is loaded (the renderer may still use it as context)
    and is not something the card may present as what the other side asked."""
    quotes = card_builder.load_evidence_quotes(seeded, ORG, f"{ORG}_thread", identities=(OURS,))
    assert "Any update on what I shared?" in [q["quote"] for q in quotes]
    assert "Any update on what I shared?" not in [q["quote"] for q in card_builder.quotable(quotes)]
