"""L2.7.7-U1's units, one at a time — the parts H6's gate exercises only in aggregate.

`test_resolution.py` is the GATE: doc 07's acceptance rows, the golden set's two numbers, and the
drain. This file is where each unit is pinned on its own, because a suite that only measures the
whole cascade cannot say WHICH guard caught a wrong close — and the day one of them is loosened
by accident, the aggregate rate moves by one fixture and nothing points at the cause.

The order below is the order of the five steps: authority, gate, prompt, judge, ledger, then the
store and the queue that carry them.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from genios_engine.context.lifecycle.authority import (
    authority_bp,
    is_ignored_speaker,
    role_for_obligation,
    role_for_scope,
)
from genios_engine.context.lifecycle.contract import (
    AUTHORITY_BP,
    CERTAINTY_BP,
    CLOSE_FLOOR_BP,
    DECISION_APPLY,
    DECISION_REJECT,
    DECISION_REVIEW,
    PROMPT_VERSION,
    REVIEW_FLOOR_BP,
    ROLE_EXTERNAL,
    ROLE_INTERNAL,
    ROLE_MACHINE,
    ROLE_OWNER,
    SHORT_MESSAGE_CHARS,
    Message,
    Obligation,
    ResolutionClaim,
)
from genios_engine.context.lifecycle.gate import (
    MAX_CALLS_PER_ORG_PER_DAY,
    SKIP_ALREADY_EXAMINED,
    SKIP_BUDGET_ORG,
    SKIP_HUMAN_RESOLVED,
    SKIP_NO_NEW_SIGNAL,
    SKIP_NO_TEXT,
    SKIP_SPEAKER_IGNORED,
    SKIP_STATUS,
    candidate_prior,
    gate_decision,
    status_is_eligible,
)
from genios_engine.context.lifecycle.judge import SITUATION_SCOPE, judge
from genios_engine.context.lifecycle.ledger import derive_statement_state
from genios_engine.context.lifecycle.prompt import build_prompt, cache_key, parse_description
from genios_engine.context.lifecycle.store import (
    LOOKBACK_DAYS,
    calls_today,
    claims_for,
    decide_review,
    obligations_for,
    pending_reviews,
    situations_to_examine,
    unexamined_messages,
    write_claim,
)
from genios_engine.context.situations import (
    RESOLVED_BY_FACT,
    RESOLVED_BY_HUMAN,
    RESOLVED_BY_STATEMENT,
    STATEMENT_NONE,
    STATEMENT_PARTIAL,
    STATEMENT_RESOLVED,
    STATUS_ACTIVE,
    STATUS_DORMANT,
    STATUS_PARTIALLY_RESOLVED,
    STATUS_RESOLVED,
    decide_lifecycle,
)

from .conftest import AT, answer_for

OWNER = "priya@ourco.example"
COLLEAGUE = "meera@ourco.example"
VENDOR = "priya@acme.example"
US = frozenset({OWNER, COLLEAGUE, "rohit@ourco.example"})
OB = Obligation("ob_msa", "countersign the MSA", OWNER)

LONG = ("The countersigned MSA came back this morning and I have filed it in the shared drive, "
        "so there is nothing outstanding on the paperwork now.")
QUOTE = "The countersigned MSA came back this morning"


def _message(text_: str = LONG, *, sender: str = OWNER, when: datetime = AT) -> Message:
    return Message(event_id="evt_unit", text=text_, sender_email=sender, occurred_at=when)


def _judge(text_: str = LONG, *, sender: str = OWNER, verdict: str = "RESOLVED",
           certainty: str = "EXPLICIT_COMPLETION", scope=("ob_msa",), quote: str = QUOTE,
           obligations=(OB,), start_offset: int | None = None) -> ResolutionClaim:
    description = parse_description(answer_for(text_, verdict=verdict, certainty=certainty,
                                               scope=list(scope), quote=quote,
                                               start_offset=start_offset))
    assert description is not None
    return judge(description, situation_id="sit_unit", message=_message(text_, sender=sender),
                 obligations=obligations, internal_emails=US)


# =================================================================================================
# authority.py — who said it
# =================================================================================================

def test_the_machine_test_runs_first_and_nothing_overrides_it():
    """`no-reply@ourco.example` is same-domain AND a robot. A cascade that asked "is this us?"
    first would hand an autoresponder INTERNAL authority, which is doc 12 case 7 exactly."""
    role = role_for_obligation("no-reply@ourco.example", OB,
                               internal_emails=US | {"no-reply@ourco.example"})
    assert role == ROLE_MACHINE and is_ignored_speaker(role)
    with pytest.raises(ValueError):
        authority_bp(ROLE_MACHINE)


def test_the_three_weights_are_doc_sevens_table_in_basis_points():
    assert role_for_obligation(OWNER, OB, internal_emails=US) == ROLE_OWNER
    assert role_for_obligation(COLLEAGUE, OB, internal_emails=US) == ROLE_INTERNAL
    assert role_for_obligation(VENDOR, OB, internal_emails=US) == ROLE_EXTERNAL
    assert (authority_bp(ROLE_OWNER), authority_bp(ROLE_INTERNAL),
            authority_bp(ROLE_EXTERNAL)) == (10_000, 8_000, 6_000)
    assert AUTHORITY_BP[ROLE_OWNER] > AUTHORITY_BP[ROLE_INTERNAL] > AUTHORITY_BP[ROLE_EXTERNAL]


def test_an_unattributable_sender_is_refused_rather_than_weighed_weakly():
    """None is not "the weakest role". 6000 bp of authority for "we do not know who wrote this"
    is an invention, and the caller refuses it."""
    assert role_for_obligation(None, OB, internal_emails=US) is None
    assert role_for_obligation("   ", OB, internal_emails=US) is None
    assert is_ignored_speaker(None)


def test_a_mixed_scope_takes_the_weakest_role_the_speaker_holds():
    """Owning a trivial obligation must not carry a close of the one that matters."""
    mine = Obligation("ob_mine", "send the deck", OWNER)
    theirs = Obligation("ob_theirs", "return the DPA", VENDOR)
    assert role_for_scope(OWNER, [mine], internal_emails=US) == ROLE_OWNER
    assert role_for_scope(OWNER, [mine, theirs], internal_emails=US) == ROLE_INTERNAL
    assert role_for_scope(VENDOR, [mine, theirs], internal_emails=US) == ROLE_EXTERNAL


def test_an_email_is_compared_case_insensitively():
    """`Priya@OurCo.Example` and `priya@ourco.example` are one person; a set test that said
    otherwise would silently demote the owner to a counterparty."""
    assert role_for_obligation("Priya@OurCo.Example", OB, internal_emails=US) == ROLE_OWNER


def test_an_obligation_with_no_recorded_owner_has_no_owner_speaker():
    """Nobody speaks with OWNER authority about an obligation the graph never attributed. The
    alternative — assuming the sender must be the owner — is how a counterparty acquires 10000."""
    unowned = Obligation("ob_x", "someone does something", None)
    assert role_for_obligation(OWNER, unowned, internal_emails=US) == ROLE_INTERNAL
    assert role_for_obligation(VENDOR, unowned, internal_emails=US) == ROLE_EXTERNAL


# =================================================================================================
# gate.py — whether to spend a call
# =================================================================================================

def _gate(**overrides):
    base = dict(status=STATUS_ACTIVE, resolved_by=None, terminal_by_fact=False,
                has_new_signal=True, already_examined=False, has_text=True,
                speaker_role=ROLE_OWNER, calls_today_for_situation=0, calls_today_for_org=0)
    base.update(overrides)
    return gate_decision(**base)


def test_the_gate_fires_only_on_the_three_conditions_doc_seven_names():
    assert _gate().fires is True
    assert _gate(has_new_signal=False).reason == SKIP_NO_NEW_SIGNAL
    assert _gate(already_examined=True).reason == SKIP_ALREADY_EXAMINED
    assert _gate(has_text=False).reason == SKIP_NO_TEXT
    assert _gate(speaker_role=ROLE_MACHINE).reason == SKIP_SPEAKER_IGNORED
    assert _gate(speaker_role=None).reason == SKIP_SPEAKER_IGNORED
    assert _gate(status=STATUS_DORMANT).reason == SKIP_STATUS


def test_a_human_resolution_is_never_reopened_by_a_sentence():
    """A person's decision is not overturned by an email, and the existing lifecycle already
    reopens a human resolution on new evidence — without a model."""
    assert _gate(status=STATUS_RESOLVED, resolved_by=RESOLVED_BY_HUMAN).reason == (
        SKIP_HUMAN_RESOLVED)
    assert status_is_eligible(STATUS_RESOLVED, RESOLVED_BY_HUMAN) is False
    assert status_is_eligible(STATUS_RESOLVED, RESOLVED_BY_FACT) is False


def test_a_statement_closed_situation_is_still_examined():
    """Doc 07 failure mode 5 needs this: by the time *"actually not yet"* arrives, the first
    message has already moved the situation out of ACTIVE. A gate that read `status == ACTIVE`
    literally would make CONTRADICTED unreachable in the case it was written for."""
    assert status_is_eligible(STATUS_RESOLVED, RESOLVED_BY_STATEMENT)
    assert status_is_eligible(STATUS_PARTIALLY_RESOLVED, RESOLVED_BY_STATEMENT)
    assert _gate(status=STATUS_RESOLVED, resolved_by=RESOLVED_BY_STATEMENT).fires


def test_the_org_ceiling_is_reported_as_budget_and_not_as_silence():
    spent = _gate(calls_today_for_org=MAX_CALLS_PER_ORG_PER_DAY)
    assert spent.fires is False and spent.reason == SKIP_BUDGET_ORG and spent.budget_exhausted
    assert _gate(has_new_signal=False,
                 calls_today_for_org=MAX_CALLS_PER_ORG_PER_DAY).budget_exhausted is False, (
        "a situation with nothing to read must not be reported as a budget miss")


def test_the_candidate_prior_reads_layer_ones_decision_states():
    made = [{"subject": "MSA countersignature", "state": "made"}]
    assert candidate_prior(made, "countersign the MSA; return the DPA") is False
    assert candidate_prior([{"subject": "the MSA", "state": "made"}], "the MSA") is True
    assert candidate_prior([{"subject": "the MSA", "state": "pending"}], "the MSA") is False
    assert candidate_prior(None, "the MSA") is False
    assert candidate_prior([{"subject": "the MSA", "state": "made"}], "") is False


# =================================================================================================
# prompt.py — what is asked, and what is accepted back
# =================================================================================================

def test_the_prompt_carries_both_hinglish_polarities():
    """Doc 12 case 6 has two halves and the second one is the dangerous half. A prompt that
    listed only the completions would turn every Hinglish future tense into a close."""
    prompt = build_prompt(subject="Acme renewal", obligations=[OB], message=_message())
    assert "ho gaya" in prompt and "kar diya" in prompt
    assert "kal kar denge" in prompt and "INTENT_ONLY" in prompt


def test_the_message_is_fenced_and_the_prior_is_stated_as_an_observation():
    prompt = build_prompt(subject="Acme renewal", obligations=[OB], message=_message(),
                          prior=True)
    assert "<<<CONTENT_" in prompt and "<<<END_" in prompt
    assert LONG in prompt
    assert "That is about the DECISION, not about the work" in prompt, (
        "a prior stated as a conclusion is a leading question at the one site whose false "
        "positive closes a live thread")
    assert "recorded a decision as *made*" not in build_prompt(
        subject="Acme renewal", obligations=[OB], message=_message())


def test_a_situation_with_no_obligations_is_still_scopeable():
    prompt = build_prompt(subject="the Acme renewal", obligations=[], message=_message())
    assert "- situation: the Acme renewal" in prompt


def test_an_answer_outside_the_vocabulary_is_refused_rather_than_repaired():
    good = answer_for(LONG, verdict="RESOLVED", certainty="EXPLICIT_COMPLETION",
                      scope=["ob_msa"], quote=QUOTE)
    assert parse_description(good) is not None
    assert parse_description({**good, "verdict": "CLOSED"}) is None
    assert parse_description({**good, "certainty": "VERY_SURE"}) is None
    assert parse_description({**good, "quote": ""}) is None
    assert parse_description({**good, "start_offset": -1}) is None
    assert parse_description({**good, "end_offset": good["start_offset"]}) is None
    assert parse_description("RESOLVED") is None


def test_the_cache_key_moves_with_the_obligation_set_and_not_with_the_clock():
    args = dict(org_id="org", situation_id="sit", event_id="evt", model="m")
    one = cache_key(obligations=[OB], **args)
    assert one == cache_key(obligations=[OB], **args)
    assert one != cache_key(obligations=[OB, Obligation("ob_dpa", "return the DPA")], **args)
    assert one != cache_key(**{**args, "model": "other"}, obligations=[OB])
    assert one.startswith("m4:")


# =================================================================================================
# judge.py — the decision
# =================================================================================================

def test_a_quote_that_is_not_in_the_message_produces_no_resolution():
    claim = _judge(quote="the contract was signed on Tuesday")
    assert claim.decision == DECISION_REJECT and claim.effective_bp == 0
    assert claim.span_verdict not in ("verified", "verified_whitespace")


def test_wrong_offsets_are_relocated_and_charged_alg_eights_own_penalty():
    """The words are real and the measurement is not: 9/10, imported from ALG-08 rather than
    restated, because a second copy of that fraction is a second policy."""
    # The quote really opens this message; the model says it starts 20 characters in.
    claim = _judge(start_offset=20)
    assert claim.span_verdict == "verified_relocated"
    assert claim.certainty_bp == CERTAINTY_BP["EXPLICIT_COMPLETION"] * 9 // 10 == 8_100
    assert claim.decision == DECISION_APPLY


def test_an_intent_band_can_never_carry_a_resolution_however_well_quoted():
    claim = _judge(certainty="INTENT_ONLY")
    assert claim.verdict == "NOT_RESOLVED" and claim.decision == DECISION_REJECT
    assert "intent" in claim.reason


def test_a_verdict_that_names_nothing_we_asked_about_is_refused():
    assert _judge(scope=["ob_something_else"]).decision == DECISION_REJECT
    assert _judge(scope=[]).decision == DECISION_REJECT
    # …and with no obligations at all, the situation sentinel is the only accepted scope.
    whole = _judge(scope=[SITUATION_SCOPE], obligations=())
    assert whole.decision == DECISION_APPLY and whole.scope == (SITUATION_SCOPE,)
    assert _judge(scope=["ob_msa"], obligations=()).decision == DECISION_REJECT


def test_covering_some_obligations_is_a_partial_and_the_downgrade_is_ours():
    two = (OB, Obligation("ob_dpa", "return the DPA", OWNER))
    claim = _judge(obligations=two)
    assert claim.verdict == "PARTIALLY_RESOLVED" and claim.decision == DECISION_APPLY
    assert claim.scope == ("ob_msa",)
    both = _judge(scope=["ob_msa", "ob_dpa"], obligations=two)
    assert both.verdict == "RESOLVED"


def test_a_single_short_message_never_closes_however_certain_it_reads():
    short = "Signed. Done."
    assert len(short) < SHORT_MESSAGE_CHARS
    claim = _judge(short, quote="Signed.")
    assert claim.effective_bp >= CLOSE_FLOOR_BP, "the arithmetic still says close"
    assert claim.decision == DECISION_REVIEW, "and the one-liner rule still refuses"
    assert "short message" in claim.reason


def test_the_two_floors_are_where_doc_sevens_table_puts_them():
    owner = _judge()
    colleague = _judge(sender=COLLEAGUE)
    vendor = _judge(sender=VENDOR)
    assert (owner.effective_bp, colleague.effective_bp, vendor.effective_bp) == (9_000, 7_200,
                                                                                5_400)
    assert owner.decision == colleague.decision == DECISION_APPLY
    assert vendor.decision == DECISION_REVIEW
    assert REVIEW_FLOOR_BP <= vendor.effective_bp < CLOSE_FLOOR_BP
    faint = _judge(sender=VENDOR, certainty="AMBIGUOUS")
    assert faint.effective_bp == 1_800 and faint.decision == DECISION_REJECT


def test_a_contradiction_applies_with_no_floor_at_all():
    """The floors exist to stop us CLOSING things. Applying them to a re-open would point the
    whole cascade backwards: re-opening costs a nudge, staying closed costs the thread."""
    weakest = _judge(sender=VENDOR, verdict="CONTRADICTED", certainty="AMBIGUOUS")
    assert weakest.decision == DECISION_APPLY and weakest.effective_bp < CLOSE_FLOOR_BP
    assert weakest.verdict == "CONTRADICTED"


def test_a_machine_speaker_is_refused_even_when_the_gate_was_bypassed():
    """Belt and braces: the judge is callable from a replay or a backfill that never met the
    gate, and the fourth row of the authority table is IGNORED ENTIRELY, not merely light."""
    claim = _judge(sender="no-reply@acme.example")
    assert claim.decision == DECISION_REJECT and claim.authority_bp == 0


def test_every_claim_carries_the_receipt_and_the_reason():
    claim = _judge()
    assert claim.quote == QUOTE and claim.source_ref == "prepared_content:evt_unit"
    assert claim.end_offset - claim.start_offset == len(QUOTE)
    assert claim.reason and claim.prompt_version == PROMPT_VERSION
    assert claim.stated_at == AT, "the claim is timed by the message, not by a clock"


# =================================================================================================
# ledger.py — many claims, one word
# =================================================================================================

def _claim(verdict: str, scope, *, when: datetime, decision: str = DECISION_APPLY,
           event: str = "e") -> ResolutionClaim:
    return ResolutionClaim(
        situation_id="sit", event_id=event, stated_at=when, verdict=verdict,
        certainty="EXPLICIT_COMPLETION", scope=tuple(scope), speaker_email=OWNER,
        speaker_role=ROLE_OWNER, authority_bp=10_000, certainty_bp=9_000, effective_bp=9_000,
        decision=decision, reason="unit", quote=QUOTE)


def test_the_latest_statement_wins_whichever_order_it_is_read_in():
    done = _claim("RESOLVED", ["ob_msa"], when=AT, event="e1")
    not_yet = _claim("CONTRADICTED", ["ob_msa"], when=AT + timedelta(days=1), event="e2")
    assert derive_statement_state([done, not_yet], ["ob_msa"]).state == STATEMENT_NONE
    assert derive_statement_state([not_yet, done], ["ob_msa"]).state == STATEMENT_NONE, (
        "the reducer must order by when the sentence was WRITTEN, not by arrival")
    later_close = replace(done, stated_at=AT + timedelta(days=2), event_id="e3")
    assert derive_statement_state([done, not_yet, later_close],
                                  ["ob_msa"]).state == STATEMENT_RESOLVED


def test_scope_accumulates_across_days_without_restating_the_first_half():
    monday = _claim("PARTIALLY_RESOLVED", ["ob_a", "ob_b", "ob_c"], when=AT, event="e1")
    thursday = _claim("RESOLVED", ["ob_d", "ob_e"], when=AT + timedelta(days=3), event="e2")
    open_ids = ["ob_a", "ob_b", "ob_c", "ob_d", "ob_e"]
    assert derive_statement_state([monday], open_ids).state == STATEMENT_PARTIAL
    assert derive_statement_state([monday, thursday], open_ids).state == STATEMENT_RESOLVED


def test_a_new_obligation_drops_a_closed_situation_back_to_partial():
    """The comparison is against TODAY's open set, so a situation cannot stay closed because it
    was closed before the rest of the work arrived."""
    done = _claim("RESOLVED", ["ob_a"], when=AT)
    assert derive_statement_state([done], ["ob_a"]).state == STATEMENT_RESOLVED
    grown = derive_statement_state([done], ["ob_a", "ob_new"])
    assert grown.state == STATEMENT_PARTIAL and grown.outstanding == ("ob_new",)


def test_a_queued_claim_never_moves_the_lifecycle():
    """A review entry is a question waiting for a human. If it moved the lifecycle the floor
    would be decorative."""
    held = _claim("RESOLVED", ["ob_msa"], when=AT, decision=DECISION_REVIEW)
    assert derive_statement_state([held], ["ob_msa"]).state == STATEMENT_NONE


def test_the_resolution_is_timed_by_the_statement_that_carried_it():
    done = _claim("RESOLVED", [SITUATION_SCOPE], when=AT)
    assert derive_statement_state([done], []).resolved_at == AT


# =================================================================================================
# situations.decide_lifecycle — the seam
# =================================================================================================

def test_an_unsupplied_stated_resolution_is_not_the_ledger_saying_no():
    """`refresh_situations` knows nothing about claims. If its silence read as "the ledger
    supports nothing", every statement-resolved situation would reopen on every drain."""
    kept = decide_lifecycle(current_status=STATUS_RESOLVED, resolved_by=RESOLVED_BY_STATEMENT,
                            last_seen_at=AT, resolved_at=AT, terminal_by_fact=False, now=AT)
    assert (kept.status, kept.resolved_by) == (STATUS_RESOLVED, RESOLVED_BY_STATEMENT)
    undone = decide_lifecycle(current_status=STATUS_RESOLVED, resolved_by=RESOLVED_BY_STATEMENT,
                              last_seen_at=AT, resolved_at=AT, terminal_by_fact=False, now=AT,
                              stated_resolution=STATEMENT_NONE)
    assert (undone.status, undone.reopened) == (STATUS_ACTIVE, True)


def test_a_partial_survives_a_refresh_that_did_not_read_the_ledger():
    kept = decide_lifecycle(current_status=STATUS_PARTIALLY_RESOLVED,
                            resolved_by=RESOLVED_BY_STATEMENT, last_seen_at=AT, resolved_at=None,
                            terminal_by_fact=False, now=AT)
    assert kept.status == STATUS_PARTIALLY_RESOLVED


def test_a_statement_never_overrides_a_human_or_a_fact():
    human = decide_lifecycle(current_status=STATUS_RESOLVED, resolved_by=RESOLVED_BY_HUMAN,
                             last_seen_at=None, resolved_at=AT, terminal_by_fact=False, now=AT,
                             stated_resolution=STATEMENT_RESOLVED)
    assert human.resolved_by == RESOLVED_BY_HUMAN
    fact = decide_lifecycle(current_status=STATUS_ACTIVE, resolved_by=None, last_seen_at=AT,
                            resolved_at=None, terminal_by_fact=True, now=AT,
                            stated_resolution=STATEMENT_NONE)
    assert fact.resolved_by == RESOLVED_BY_FACT


def test_the_existing_lifecycle_rules_are_untouched():
    """This unit is ADDITIVE. The fact path, the human path and dormancy behave exactly as they
    did, and the default argument is what guarantees it for every existing caller."""
    new = decide_lifecycle(current_status=None, resolved_by=None, last_seen_at=AT,
                           resolved_at=None, terminal_by_fact=False, now=AT)
    assert (new.status, new.resolved_by) == (STATUS_ACTIVE, None)
    quiet = decide_lifecycle(current_status=STATUS_ACTIVE, resolved_by=None,
                             last_seen_at=AT - timedelta(days=60), resolved_at=None,
                             terminal_by_fact=False, now=AT)
    assert quiet.status == STATUS_DORMANT
    reopened = decide_lifecycle(current_status=STATUS_RESOLVED, resolved_by=RESOLVED_BY_HUMAN,
                                last_seen_at=AT, resolved_at=AT - timedelta(days=1),
                                terminal_by_fact=False, now=AT)
    assert (reopened.status, reopened.reopened) == (STATUS_ACTIVE, True)


# =================================================================================================
# store.py and the review queue — on real PostgreSQL
# =================================================================================================

ORG_STORE = "org_m4_store"


@pytest.fixture()
def seeded(pg_store):
    """One org, one active situation with two member messages, one open commitment, one closed.

    The closed commitment is the assertion that matters in `obligations_for`: a discharged
    promise is not outstanding, so a claim about it cannot be what makes a partial partial.
    """
    ask_at, reply_at = AT - timedelta(days=2), AT - timedelta(hours=3)
    with pg_store.engine.begin() as conn:
        _wipe(conn, ORG_STORE)
        conn.execute(text("insert into orgs (id, name) values (:o, 'store') "
                          "on conflict (id) do nothing"), {"o": ORG_STORE})
        for node_id, node_type, name, key in (
                ("n_store_co", "company", "Acme", "acme-store.example"),
                ("n_store_person", "person", "Priya", OWNER),
                ("n_store_open", "commitment", "countersign the MSA", "cmt:open:store"),
                ("n_store_closed", "commitment", "send the deck", "cmt:closed:store")):
            conn.execute(text(
                "insert into graph_nodes (node_id, version, org_id, node_type, display_name, "
                "  canonical_key) values (:n, 1, :o, :t, :d, :k) on conflict do nothing"),
                {"n": node_id, "o": ORG_STORE, "t": node_type, "d": name, "k": key})
        conn.execute(text(
            "insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, "
            "  from_node_id, to_node_id) values ('ev_store', 'e_store', :o, 'owns', "
            "  'n_store_person', 'n_store_open') on conflict do nothing"), {"o": ORG_STORE})
        for event_id, when, body in (("evt_store_ask", ask_at, "Please countersign the MSA."),
                                     ("evt_store_reply", reply_at, LONG)):
            conn.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, "
                "  object_type, source_object_id, dedup_key, actor, occurred_at, outcome) "
                "values (:e, :o, 'c', 'gmail', 'message', :e, :e, cast(:a as jsonb), :at, "
                "  'emitted') on conflict (event_id) do nothing"),
                {"e": event_id, "o": ORG_STORE, "a": '{"email": "%s"}' % OWNER, "at": when})
            conn.execute(text(
                "insert into prepared_content (event_id, org_id, prepared_content_id, "
                "  clean_text) values (:e, :o, :p, :t) on conflict (event_id) do nothing"),
                {"e": event_id, "o": ORG_STORE, "p": f"pc_{event_id}", "t": body})
        for node, status, fv in (("n_store_open", "open", "fv_store_open"),
                                 ("n_store_closed", "done", "fv_store_closed")):
            conn.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "  field, value, value_type, status, occurred_at, valid_from, "
                "  created_by_event_id) values (:fv, :fv, :o, :n, 'commitment.text', "
                "  cast(:v as jsonb), 'string', 'active', :at, :at, 'evt_store_ask') "
                "on conflict do nothing"),
                {"fv": fv + "_text", "o": ORG_STORE, "n": node, "v": '"a promise"', "at": ask_at})
            conn.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "  field, value, value_type, status, occurred_at, valid_from, "
                "  created_by_event_id) values (:fv, :fv, :o, :n, 'commitment.status', "
                "  cast(:v as jsonb), 'enum', 'active', :at, :at, 'evt_store_ask') "
                "on conflict do nothing"),
                {"fv": fv + "_status", "o": ORG_STORE, "n": node, "v": f'"{status}"',
                 "at": ask_at})
        conn.execute(text(
            "insert into context_correlations (correlation_id, org_id, anchor_node_id, "
            "  anchor_type, domain, generation, first_event_at, last_event_at, event_count) "
            "values ('corr_store', :o, 'n_store_co', 'company', 'sales', 1, :f, :l, 2) "
            "on conflict do nothing"), {"o": ORG_STORE, "f": ask_at, "l": reply_at})
        for event_id in ("evt_store_ask", "evt_store_reply"):
            conn.execute(text(
                "insert into context_correlation_members (org_id, correlation_id, event_id, "
                "  joined_via) values (:o, 'corr_store', :e, 'thread') on conflict do nothing"),
                {"o": ORG_STORE, "e": event_id})
        conn.execute(text(
            "insert into context_situations (situation_id, org_id, correlation_id, "
            "  anchor_node_id, situation_type, domain, status, first_seen_at, last_seen_at, "
            "  computed_at) values ('sit_store', :o, 'corr_store', 'n_store_co', 'opportunity', "
            "  'sales', 'active', :f, :l, :l) on conflict do nothing"),
            {"o": ORG_STORE, "f": ask_at, "l": reply_at})
    yield pg_store
    with pg_store.engine.begin() as conn:
        _wipe(conn, ORG_STORE)
        conn.execute(text("delete from orgs where id=:o"), {"o": ORG_STORE})


def _wipe(conn, org: str) -> None:
    for table in ("situation_resolution_claims", "context_situations",
                  "context_correlation_members", "context_correlations", "prepared_content",
                  "source_events", "graph_facts", "graph_edges", "graph_nodes"):
        conn.execute(text(f"delete from {table} where org_id=:o"), {"o": org})


@pytest.mark.pg
def test_the_reads_find_the_situation_its_messages_and_its_open_obligations(seeded):
    with seeded.engine.connect() as conn:
        situations = situations_to_examine(conn, ORG_STORE)
        assert [s.situation_id for s in situations] == ["sit_store"]
        obligations = obligations_for(conn, ORG_STORE, ["corr_store"])["corr_store"]
        assert [o.obligation_id for o in obligations] == ["n_store_open"], (
            "a discharged commitment is not outstanding and must not make a close partial")
        assert obligations[0].owner_email == OWNER, "the owner comes off the `owns` edge"
        messages = unexamined_messages(conn, ORG_STORE, ["corr_store"], eval_time=AT)
        assert [m["event_id"] for m in messages] == ["evt_store_reply", "evt_store_ask"], (
            "newest first: the budget must be spent where a resolution is most likely")
        assert messages[0]["sender_email"] == OWNER and messages[0]["text"] == LONG


@pytest.mark.pg
def test_a_message_older_than_the_lookback_is_out_of_reach(seeded):
    """The window is a deliberate floor on what we will read: without it the first sweep after
    this unit ships would spend the whole budget on eighteen months of the oldest mail — the
    least likely place for a live resolution to be."""
    from genios_engine.context.situations import DORMANT_AFTER_DAYS
    assert LOOKBACK_DAYS < DORMANT_AFTER_DAYS, (
        "the read window must be shorter than the dormancy window, or this pass keeps paying to "
        "re-read situations that have already gone quiet")
    with seeded.engine.connect() as conn:
        inside = unexamined_messages(conn, ORG_STORE, ["corr_store"],
                                     eval_time=AT + timedelta(days=LOOKBACK_DAYS - 1))
        assert [m["event_id"] for m in inside] == ["evt_store_reply"], (
            "the newer message is inside the window and the older one is not")
        late = unexamined_messages(conn, ORG_STORE, ["corr_store"],
                                   eval_time=AT + timedelta(days=LOOKBACK_DAYS + 1))
        assert late == []


@pytest.mark.pg
def test_a_claim_round_trips_and_is_written_once_per_message(seeded):
    claim = _judge()
    claim = replace(claim, situation_id="sit_store", event_id="evt_store_reply")
    with seeded.engine.begin() as conn:
        write_claim(conn, ORG_STORE, claim, review_state=None)
        write_claim(conn, ORG_STORE, claim, review_state=None)
    with seeded.engine.connect() as conn:
        stored = claims_for(conn, ORG_STORE, ["sit_store"])["sit_store"]
        assert len(stored) == 1, "the ledger doubled a judgement on a re-run"
        assert stored[0].scope == ("ob_msa",) and stored[0].quote == QUOTE
        assert stored[0].effective_bp == 9_000 and stored[0].speaker_role == ROLE_OWNER
        assert stored[0].stated_at == AT
        # And the message is now EXAMINED — which is what stops the next sweep paying again.
        assert unexamined_messages(conn, ORG_STORE, ["corr_store"], eval_time=AT) == [
            m for m in unexamined_messages(conn, ORG_STORE, ["corr_store"], eval_time=AT)
            if m["event_id"] != "evt_store_reply"]


@pytest.mark.pg
def test_the_daily_budget_is_counted_against_eval_time_and_not_a_clock(seeded):
    claim = replace(_judge(), situation_id="sit_store", event_id="evt_store_reply")
    with seeded.engine.begin() as conn:
        write_claim(conn, ORG_STORE, claim, review_state=None)
    with seeded.engine.connect() as conn:
        today_total, per_situation = calls_today(conn, ORG_STORE, eval_time=datetime.now(
            tz=AT.tzinfo))
        assert today_total == 1 and per_situation["sit_store"] == 1
        # A different day sees none of it: the ceilings are per day, by `eval_time`'s day.
        tomorrow, _ = calls_today(conn, ORG_STORE,
                                  eval_time=datetime.now(tz=AT.tzinfo) + timedelta(days=1))
        assert tomorrow == 0


@pytest.mark.pg
def test_the_review_queue_holds_what_the_floor_refused_and_a_human_settles_it(seeded):
    held = replace(_judge(sender=VENDOR), situation_id="sit_store",
                   event_id="evt_store_reply")
    assert held.decision == DECISION_REVIEW
    with seeded.engine.begin() as conn:
        write_claim(conn, ORG_STORE, held, review_state="pending")
    with seeded.engine.connect() as conn:
        queue = pending_reviews(conn, ORG_STORE)
        assert len(queue) == 1
        assert queue[0]["quote"] == QUOTE and queue[0]["speaker_role"] == ROLE_EXTERNAL
        assert "below the" in queue[0]["reason"], "the queue must say why it was held"
        claim_id = queue[0]["claim_id"]
    with seeded.engine.begin() as conn:
        assert decide_review(conn, ORG_STORE, claim_id=claim_id, accepted=True,
                             reviewed_by="rohit", eval_time=AT) is True
        assert decide_review(conn, ORG_STORE, claim_id=claim_id, accepted=True,
                             reviewed_by="rohit", eval_time=AT) is False, (
            "a settled entry must not be settleable twice")
    with seeded.engine.connect() as conn:
        assert pending_reviews(conn, ORG_STORE) == []
        # The claim itself still says what it always said: a description the floor refused.
        stored = claims_for(conn, ORG_STORE, ["sit_store"])["sit_store"][0]
        assert stored.decision == DECISION_REVIEW


@pytest.mark.pg
def test_the_queue_routes_are_registered_and_do_not_collide_with_the_situation_wildcard():
    """`/api/org/{org_id}/situations/{situation_id}` is registered first and would swallow a
    queue hanging off that prefix — a route that exists, resolves, and is unreachable."""
    from fastapi.testclient import TestClient

    from genios_engine.main import app
    served = app.openapi()["paths"]
    assert "/api/org/{org_id}/resolution-reviews" in served
    assert "/api/org/{org_id}/resolution-reviews/{claim_id}" in served
    client = TestClient(app)
    assert client.get(f"/api/org/{ORG_STORE}/resolution-reviews").status_code != 404


@pytest.mark.pg
def test_the_queue_is_readable_over_http(seeded):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from genios_engine.api import lifecycle_routes
    from genios_engine.platform.auth import get_current_org
    if lifecycle_routes._graph is None:
        pytest.skip("graph store not configured for the API module")
    held = replace(_judge(sender=VENDOR), situation_id="sit_store", event_id="evt_store_reply")
    with seeded.engine.begin() as conn:
        write_claim(conn, ORG_STORE, held, review_state="pending")

    app = FastAPI()
    app.include_router(lifecycle_routes.router)
    app.dependency_overrides[get_current_org] = lambda: ORG_STORE
    client = TestClient(app)
    body = client.get(f"/api/org/{ORG_STORE}/resolution-reviews").json()
    assert body["count"] == 1
    entry = body["reviews"][0]
    assert entry["quote"] == QUOTE and entry["speaker_role"] == ROLE_EXTERNAL

    settled = client.post(f"/api/org/{ORG_STORE}/resolution-reviews/{entry['claim_id']}",
                          json={"accepted": True, "reviewed_by": "rohit"}).json()
    assert settled["review_state"] == "accepted"
    assert settled["situation_resolved"] is True and settled["resolved_by"] == "human", (
        "accepting a held claim is a HUMAN resolution, not a promotion of the model's")
    with seeded.engine.connect() as conn:
        row = conn.execute(text("select status, resolved_by from context_situations "
                                "where org_id=:o and situation_id='sit_store'"),
                           {"o": ORG_STORE}).mappings().one()
    assert (row["status"], row["resolved_by"]) == (STATUS_RESOLVED, RESOLVED_BY_HUMAN)
