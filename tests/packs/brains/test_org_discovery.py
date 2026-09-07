"""N-3 · Organization-Brain discovery (CLG-09) — the gate, the pipeline, and the J4 rows.

Two halves, matching the two modules. `packs/brains/org_discovery.py` is pure judgment and every
test of it is hermetic: a document, a list of model candidates, a verdict. `feedback/
org_rule_ingest.py` is the driver, and every test of it runs against REAL PostgreSQL in a
rolled-back transaction — because the things that actually go wrong here (a state the lifecycle
forbids, a CHECK constraint that is supposed to fire, one active version per subject, a
half-open authority window) are properties of the database and cannot be asserted against a mock.
"""
from __future__ import annotations

import inspect
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.validate.spans import SpanVerdict
from genios_engine.contracts.learning import (
    LearningEvidence,
    LearningObject,
    LearningPolicy,
    LearningState,
    LearningTarget,
    Visibility,
    VisibilityScope,
)
from genios_engine.feedback import org_rule_ingest
from genios_engine.packs.brains import org_discovery as og

NOW = datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc)
STATED = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)

POLICY_TEXT = (
    "Acme Approvals Policy, revision 4.\n"
    "We care a great deal about spending discipline and review our vendors often.\n"
    "Contracts above $50,000 require founder approval before signature.\n"
    "Hiring for any role must be approved by the founder.\n"
    "Expenses are usually settled at the end of the month.\n")

QUOTE_50K = "Contracts above $50,000 require founder approval before signature."
QUOTE_HIRING = "Hiring for any role must be approved by the founder."
QUOTE_DESCRIPTIVE = "Expenses are usually settled at the end of the month."


def _at(haystack: str, needle: str) -> tuple[int, int]:
    start = haystack.index(needle)
    return start, start + len(needle)


def doc(*, kind: str = "policy", locale: str | None = "en-US",
        body: str = POLICY_TEXT, org_id: str = "org_t", event_id: str = "evt_1",
        occurred_at: datetime = STATED, version_key: str = "v1") -> og.CanonDocument:
    return og.CanonDocument(org_id=org_id, event_id=event_id, kind=kind, title="Approvals Policy",
                            text=body, occurred_at=occurred_at, version_key=version_key,
                            locale=locale)


def candidate(quote: str, *, source: str = POLICY_TEXT, category: str = "approval",
              subject_type: str = "contract", threshold: str | None = "$50,000",
              approver: str | None = "founder", offsets: tuple[int, int] | None = None) -> dict:
    start, end = offsets if offsets is not None else _at(source, quote)
    return {"category": category, "subject_type": subject_type, "quote": quote,
            "start_offset": start, "end_offset": end,
            "threshold_as_written": threshold, "approver_as_written": approver}


def _reasons(result: og.DiscoveryResult) -> list[str]:
    return [r.reason for r in result.refusals]


# ══════════════════════════════════════════════════════════════════════════════════════════════
# CLG-09 — the gate. Pure, hermetic, no database.
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_the_fifty_thousand_dollar_fixture_produces_exactly_one_rule():
    """Doc 02's acceptance, verbatim: one candidate rule, a verifying span, Money in minor units."""
    result = og.gate_candidates(doc(), [candidate(QUOTE_50K)],
                                resolve_approver=lambda _n: "node_founder")

    assert len(result.rules) == 1 and not result.refusals
    rule = result.rules[0]
    assert rule.category == "approval" and rule.subject_type == "contract"
    assert rule.verdict is SpanVerdict.VERIFIED and rule.span.verified is True
    assert rule.statement == QUOTE_50K
    assert rule.threshold is not None
    assert (rule.threshold.minor_units, rule.threshold.currency) == (5_000_000, "USD")
    assert rule.threshold.as_written == "$50,000"
    assert rule.disposition is og.Disposition.ADMITTED
    assert rule.approver_node_id == "node_founder" and rule.authority_pending is False
    assert rule.subject == "orgrule:approval:contract"
    assert result.accounted_for


def test_an_invented_threshold_is_dropped_before_the_parser_ever_sees_it():
    """The model points at characters. Characters that are not in the sentence it cited are the
    invented-threshold case, and it must die before it can become an integer somebody signs."""
    result = og.gate_candidates(doc(), [candidate(QUOTE_50K, threshold="$75,000")],
                                resolve_approver=lambda _n: "node_founder")

    assert not result.rules
    assert _reasons(result) == ["threshold_not_in_quote"]
    assert result.counters()["refused_threshold_not_in_quote"] == 1
    assert result.accounted_for


def test_a_threshold_the_parser_cannot_reproduce_is_dropped_and_named():
    """"$50,000" is USD, CAD or AUD. With no declared locale ALG-10 REFUSES rather than guessing,
    and a refusal that decides who has to sign must be visible, not silently defaulted."""
    result = og.gate_candidates(doc(locale=None), [candidate(QUOTE_50K)],
                                resolve_approver=lambda _n: "node_founder")

    assert not result.rules
    assert _reasons(result) == ["threshold_unparseable"]
    assert "ambiguous_separator" in result.refusals[0].detail


def test_an_unambiguous_currency_needs_no_declared_locale():
    """The refusal above is about the DOLLAR sign, not about thresholds. ₹ names one currency."""
    body = "Purchase orders above ₹25,00,000 require founder approval.\n"
    quote = "Purchase orders above ₹25,00,000 require founder approval."
    result = og.gate_candidates(
        doc(locale=None, body=body),
        [candidate(quote, source=body, subject_type="order", threshold="₹25,00,000")],
        resolve_approver=lambda _n: "node_founder")

    assert len(result.rules) == 1
    assert (result.rules[0].threshold.minor_units, result.rules[0].threshold.currency) == (
        250_000_000, "INR")


def test_a_hallucinated_sentence_is_dropped_by_alg08():
    result = og.gate_candidates(
        doc(), [candidate("Contracts above $50,000 require board approval.",
                          offsets=(0, len("Contracts above $50,000 require board approval.")),
                          threshold=None)],
        resolve_approver=lambda _n: "node_founder")

    assert not result.rules and _reasons(result) == ["span_unverified"]


def test_a_sentence_in_a_handbook_is_not_a_rule():
    """The kind gate: `normalize_kind('handbook') == 'wiki'`, and a wiki binds nobody. The whole
    document refuses ONCE — the kind is a fact about the source's authority, not about a
    sentence — and no candidate is ever examined."""
    result = og.gate_candidates(doc(kind="wiki"), [candidate(QUOTE_50K)])

    assert not result.rules
    assert _reasons(result) == ["kind_not_rule_bearing"]
    assert result.accounted_for
    assert "wiki" not in og.RULE_BEARING_CANON_KINDS


def test_a_description_without_deontic_force_is_not_a_rule():
    """"Expenses are usually settled at the end of the month" is a habit, not an obligation."""
    result = og.gate_candidates(
        doc(), [candidate(QUOTE_DESCRIPTIVE, category="process", subject_type="expense",
                          threshold=None, approver=None)])

    assert not result.rules and _reasons(result) == ["no_deontic_force"]


def test_deontic_force_is_read_from_the_document_not_from_the_models_label():
    """A model that calls a description an `approval` still cannot make it one: the lexicon runs
    on the VERIFIED quote, which is the document's own words."""
    result = og.gate_candidates(
        doc(), [candidate(QUOTE_DESCRIPTIVE, category="approval", subject_type="expense",
                          threshold=None, approver="founder")])

    assert _reasons(result) == ["no_deontic_force"]


def test_a_rule_must_name_the_class_of_thing_it_governs():
    result = og.gate_candidates(doc(), [candidate(QUOTE_50K, subject_type="vendor")],
                                resolve_approver=lambda _n: "node_founder")

    assert _reasons(result) == ["subject_type_not_in_quote"]


def test_the_category_vocabulary_is_closed():
    result = og.gate_candidates(doc(), [candidate(QUOTE_50K, category="escalation")])

    assert _reasons(result) == ["unknown_category"]
    assert og.ORG_RULE_CATEGORIES == {"approval", "criticality", "policy", "process"}


def test_a_malformed_subject_type_is_refused_rather_than_sanitised():
    result = og.gate_candidates(doc(), [candidate(QUOTE_50K, subject_type="Contract Value!!")])

    assert _reasons(result) == ["malformed_subject_type"]


def test_an_approval_rule_with_no_approver_is_not_a_rule():
    result = og.gate_candidates(doc(), [candidate(QUOTE_50K, approver=None)])

    assert _reasons(result) == ["approver_missing"]


def test_an_approver_who_is_not_in_the_document_is_refused():
    result = og.gate_candidates(doc(), [candidate(QUOTE_50K, approver="the board")])

    assert _reasons(result) == ["approver_not_in_quote"]


def test_an_unresolved_approver_goes_to_human_review_rather_than_being_dropped():
    """Doc 02: "approver resolves to a known person/role node — else HUMAN_REVIEW". The rule is
    still proposed; what it cannot do is bind, because `AuthorityRule` requires a node id."""
    result = og.gate_candidates(doc(), [candidate(QUOTE_50K)],
                                resolve_approver=lambda _n: None)

    assert len(result.rules) == 1 and not result.refusals
    rule = result.rules[0]
    assert rule.disposition is og.Disposition.HUMAN_REVIEW
    assert rule.authority_pending is True and rule.approver_node_id is None
    assert rule.approver_as_written == "founder"


def test_a_non_approval_rule_needs_no_approver_because_the_document_is_the_authority():
    body = "Customer refunds must be issued within 30 days of the request.\n"
    quote = "Customer refunds must be issued within 30 days of the request."
    result = og.gate_candidates(
        doc(body=body), [candidate(quote, source=body, category="policy", subject_type="refund",
                                   threshold=None, approver=None)])

    assert len(result.rules) == 1
    assert result.rules[0].disposition is og.Disposition.ADMITTED
    assert result.rules[0].authority_pending is False


def test_a_rule_restated_twice_in_one_document_is_one_rule():
    """Version noise (invariant #8) starts here: two identical proposals would supersede each
    other for no reason."""
    result = og.gate_candidates(doc(), [candidate(QUOTE_50K), candidate(QUOTE_50K)],
                                resolve_approver=lambda _n: "node_founder")

    assert len(result.rules) == 1 and _reasons(result) == ["duplicate_rule"]
    assert result.accounted_for


def test_the_statement_stored_is_the_documents_bytes_not_the_models_copy():
    """ALG-08 relocates a real quote whose offsets are wrong and REWRITES the span. What lands in
    the brain is the source's characters at the offsets that were actually found."""
    result = og.gate_candidates(doc(), [candidate(QUOTE_50K, offsets=(0, len(QUOTE_50K)))],
                                resolve_approver=lambda _n: "node_founder")

    rule = result.rules[0]
    assert rule.verdict is SpanVerdict.VERIFIED_RELOCATED
    assert rule.statement == QUOTE_50K
    assert POLICY_TEXT[rule.span.start_offset:rule.span.end_offset] == rule.statement
    assert rule.confidence_bp == 9000        # ALG-08's 9/10, as integer basis points


def test_a_tidied_quote_is_replaced_by_the_documents_actual_bytes():
    """M-6's rule, one layer down: the model's COPY of a sentence is not the sentence.

    ALG-08 grades a whitespace-different quote VERIFIED_WHITESPACE — a real citation with a
    cosmetic disagreement — and rewrites the span onto the source. What must land in the brain is
    the document's characters, because a re-flowed quote stored as the company's rule is a rule
    the company never wrote.
    """
    body = "Contracts above  $50,000\nrequire founder approval.\n"
    tidy = "Contracts above $50,000 require founder approval."
    result = og.gate_candidates(
        doc(body=body), [candidate(tidy, source=body, offsets=(0, len(tidy)))],
        resolve_approver=lambda _n: "node_founder")

    rule = result.rules[0]
    assert rule.verdict is SpanVerdict.VERIFIED_WHITESPACE
    assert rule.statement != tidy, "the model's tidied copy was stored as the company's rule"
    assert rule.statement == body[rule.span.start_offset:rule.span.end_offset]
    assert rule.statement == "Contracts above  $50,000\nrequire founder approval."


def test_a_candidate_that_is_neither_a_rule_nor_a_refusal_is_reported_as_unaccounted():
    """`accounted_for` is the no-silent-drop check, so it has to be able to say NO."""
    dropped = og.DiscoveryResult(doc=doc(), rules=(), refusals=(), candidates_seen=1)
    assert dropped.accounted_for is False
    kept = og.DiscoveryResult(doc=doc(), rules=(),
                              refusals=(og.Refusal("duplicate_rule"),), candidates_seen=1)
    assert kept.accounted_for is True
    # And the document-level refusal path stands alone: one refusal, however many candidates.
    refused_doc = og.gate_candidates(doc(kind="wiki"), [candidate(QUOTE_50K)] * 3)
    assert refused_doc.accounted_for is True
    assert og.DiscoveryResult(doc=doc(kind="wiki"), candidates_seen=3).accounted_for is False


def test_every_candidate_becomes_a_rule_or_a_named_refusal():
    """The no-silent-drop contract as arithmetic."""
    result = og.gate_candidates(
        doc(),
        [candidate(QUOTE_50K),
         candidate(QUOTE_50K, threshold="$75,000"),
         candidate(QUOTE_DESCRIPTIVE, category="process", subject_type="expense",
                   threshold=None, approver=None),
         candidate(QUOTE_50K, category="nonsense"),
         candidate(QUOTE_HIRING, subject_type="hiring", threshold=None)],
        resolve_approver=lambda _n: "node_founder")

    assert result.candidates_seen == 5
    assert len(result.rules) + len(result.refusals) == 5
    assert result.accounted_for
    assert set(_reasons(result)) == {"threshold_not_in_quote", "no_deontic_force",
                                     "unknown_category"}


def test_no_refusal_reason_may_be_invented():
    """The counters, the ledger rows and these tests share one closed vocabulary."""
    with pytest.raises(ValueError):
        og.Refusal("it_looked_wrong")


def test_the_proposed_value_carries_no_model_authored_prose():
    """A model cannot editorialise into the Organization brain because there is nowhere for prose
    to land: every string in the value is either from a closed set, from ALG-10, from the
    identity layer, or is the document's own bytes."""
    result = og.gate_candidates(doc(), [candidate(QUOTE_50K)],
                                resolve_approver=lambda _n: "node_founder")
    value = og.proposed_value(doc(), result.rules[0])

    assert value["statement"] == QUOTE_50K                       # the document's bytes
    assert value["category"] in og.ORG_RULE_CATEGORIES           # a closed set
    assert value["threshold_minor_units"] == 5_000_000           # ALG-10's integer
    assert value["approver_node_id"] == "node_founder"           # the identity layer
    assert value["authority_source"] == "discovered"
    assert value["document"]["stated_at"] == STATED.isoformat()
    free_text = {k: v for k, v in value.items()
                 if isinstance(v, str) and k not in
                 {"category", "subject_type", "statement", "statement_hash", "currency",
                  "threshold_as_written", "approver_as_written", "approver_node_id",
                  "authority_source"}}
    assert not free_text, f"unexpected free-text field(s) in the brain value: {sorted(free_text)}"


def test_the_proposal_states_its_evidence_honestly():
    """One verified span in one document is ONE observation on ONE day. The unit does not dress a
    declaration up as a recurrence to get past floors that were written for recurrences."""
    result = og.gate_candidates(doc(), [candidate(QUOTE_50K)],
                                resolve_approver=lambda _n: "node_founder")
    policy = LearningPolicy(org_id="org_t", revision=1)
    obj = og.build_proposal(doc(), result.rules[0], policy=policy)

    assert obj.target is LearningTarget.ORGANIZATION
    assert obj.unit == og.DISCOVERY_UNIT
    assert obj.evidence.observations == 1 and obj.evidence.distinct_days == 1
    assert obj.evidence.distinct_entities == 1
    assert obj.evidence.confidence_bp == 10000
    assert obj.evidence.source_refs == ("prepared_content:evt_1",)
    # The times come from the DOCUMENT, never from a clock — the same object next week is the
    # same object, which is what makes `persist` idempotent across sweeps.
    assert obj.first_seen_at == STATED and obj.last_seen_at == STATED
    assert obj.visibility.scope is VisibilityScope.ORGANIZATION and obj.lineage_complete


def test_two_readings_of_the_same_document_are_the_same_proposal():
    """Content addressing is the idempotency, and it must not depend on when the run happened."""
    policy = LearningPolicy(org_id="org_t", revision=1)
    first = og.gate_candidates(doc(), [candidate(QUOTE_50K)],
                               resolve_approver=lambda _n: "node_founder").rules[0]
    second = og.gate_candidates(doc(), [candidate(QUOTE_50K)],
                                resolve_approver=lambda _n: "node_founder").rules[0]

    assert (og.build_proposal(doc(), first, policy=policy).learning_id
            == og.build_proposal(doc(), second, policy=policy).learning_id)


def test_the_authority_rule_id_is_keyed_on_the_subject_not_the_document():
    """A superseding policy must CLOSE its predecessor's window, not open a parallel rule."""
    assert (og.authority_rule_id("orgrule:approval:contract")
            == og.authority_rule_id("orgrule:approval:contract"))
    assert (og.authority_rule_id("orgrule:approval:contract")
            != og.authority_rule_id("orgrule:approval:hiring"))


def test_the_layer_three_half_reaches_no_store_and_no_clock():
    """The import ratchet is the mechanism; this is the property it protects. A producer that
    could call its own governance, or read a clock, would make the split cosmetic."""
    src = inspect.getsource(og)
    assert "genios_engine.feedback" not in src
    assert "datetime.now" not in src and "utcnow" not in src
    assert "conn.execute" not in src.replace(
        inspect.getsource(og.resolve_approver_node), "")     # the resolver takes a conn; nothing else


# ══════════════════════════════════════════════════════════════════════════════════════════════
# The driver, against real PostgreSQL
# ══════════════════════════════════════════════════════════════════════════════════════════════

class _Extractor:
    """A stand-in for the T2 site. Records whether it was called — the cost gate needs proof."""

    def __init__(self, candidates=None) -> None:
        self.candidates = candidates if candidates is not None else [candidate(QUOTE_50K)]
        self.calls = 0

    def propose(self, *, text, kind, title):        # noqa: A002 — the protocol's signature
        self.calls += 1
        return list(self.candidates)


class _BrokenExtractor:
    def propose(self, *, text, kind, title):        # noqa: A002
        raise RuntimeError("model unavailable")


class _Shim:
    """`engine.begin()` as a SAVEPOINT on the test's connection, so a ROUTE's own transaction
    block runs for real and the outer transaction still rolls the whole thing back.

    Copied in shape from `tests/test_account_erasure.py::erasure_conn` and for the same reason it
    gives: the route FUNCTION is called, never transcribed. A test that re-implements what the
    console does would keep passing the day the console stops doing it.
    """

    def __init__(self, c):
        self._c = c

    @contextmanager
    def begin(self):
        nested = self._c.begin_nested()
        try:
            yield self._c
        except Exception:
            nested.rollback()
            raise
        else:
            nested.commit()


@pytest.fixture()
def conn(live_db_url, monkeypatch):
    """A real-Postgres transaction, rolled back. The scratch database, never the configured one."""
    if not live_db_url:
        pytest.skip("no database configured")
    from genios_engine.api import learning_routes
    from genios_engine.platform.db import get_engine
    c = get_engine(live_db_url).connect()
    tx = c.begin()
    org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); c.close(); pytest.skip("no org")
    c.execute(text("update orgs set locale = 'en-US' where id = :o"), {"o": org})
    monkeypatch.setattr(learning_routes, "_graph", type("G", (), {"engine": _Shim(c)})())
    try:
        yield c, org
    finally:
        tx.rollback(); c.close()


def seed_canon(c, org, *, event_id="evt_policy_1", kind="policy", body=POLICY_TEXT,
               version_key="policy:approvals@v1", occurred_at=STATED,
               source_object_id="policy:approvals") -> str:
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        "source_object_id, dedup_key, actor, occurred_at, internal_kind) "
        "values (:e, :o, 'knowledge', 'internal', :k, :soid, :dk, cast('{}' as jsonb), :at, :k)"),
        {"e": event_id, "o": org, "k": kind, "soid": source_object_id, "dk": version_key,
         "at": occurred_at})
    c.execute(text(
        "insert into prepared_content (event_id, org_id, prepared_content_id, clean_text) "
        "values (:e, :o, :p, :t)"),
        {"e": event_id, "o": org, "p": f"pc_{event_id}", "t": body})
    return event_id


def seed_founder(c, org, node_id="node_founder_1"):
    """A canon `employee_profile` titled "Founder" is how a ROLE resolves — the identity layer's
    real key, not a special case invented for this unit."""
    c.execute(text(
        "insert into graph_aliases (org_id, alias_type, alias_key, node_id, origin) "
        "values (:o, 'canon', 'founder', :n, 'anchor') on conflict do nothing"),
        {"o": org, "n": node_id})
    return node_id


def _states(c, org, learning_id) -> list[str]:
    """The lifecycle WALK, rebuilt from the from/to pairs rather than from a row order.

    `learning_transitions` has no sequence column and every row here shares one `occurred_at`
    (the clock is read once, at the process boundary, and passed down), so any ORDER BY would be
    asserting on an accident. Following the chain is also the stronger claim: it proves the rungs
    connect, not merely that five rows exist.
    """
    edges = {r[0]: r[1] for r in c.execute(text(
        "select coalesce(from_state, ''), to_state from learning_transitions "
        "where org_id=:o and learning_id=:l"), {"o": org, "l": learning_id})}
    walk, state = [], ""
    while state in edges:
        state = edges.pop(state)
        walk.append(state)
    assert not edges, f"transitions not on the chain: {edges}"
    return walk


def test_a_discovered_rule_lands_in_the_console_and_not_in_the_brain(conn):
    """Doc 02's acceptance end to end: the rule is proposed, it waits for a human, and NOTHING
    reached `learned_brain_entries` on its own."""
    c, org = conn
    seed_founder(c, org)
    event_id = seed_canon(c, org)
    extractor = _Extractor()

    out = org_rule_ingest.run_org_discovery(c, org_id=org, event_id=event_id,
                                            extractor=extractor, now=NOW)

    assert out["proposed"] == 1 and out["admitted"] == 1 and out["refused"] == 0
    row = c.execute(text(
        "select learning_id, state, target, subject, proposed_value from learning_objects "
        "where org_id=:o and unit=:u"), {"o": org, "u": og.DISCOVERY_UNIT}).mappings().one()
    assert row["state"] == LearningState.HUMAN_REVIEW.value
    assert row["target"] == "organization"
    assert row["subject"] == "orgrule:approval:contract"
    assert row["proposed_value"]["threshold_minor_units"] == 5_000_000
    assert row["proposed_value"]["approver_node_id"] == "node_founder_1"
    assert c.execute(text("select count(*) from learned_brain_entries where org_id=:o"),
                     {"o": org}).scalar() == 0
    assert c.execute(text("select count(*) from authority_rules where org_id=:o"),
                     {"o": org}).scalar() == 0


def test_the_proposal_climbs_every_rung_and_the_floors_verdict_is_recorded(conn):
    """Doc 02 says a discovery ENTERS AT OBSERVED. Every rung is a real transition row, and the
    recurrence floors are RUN and their verdict stored — they are not skipped, they are recorded
    and then a human decides, which is what `govern` already chose for an Organization target."""
    c, org = conn
    seed_founder(c, org)
    event_id = seed_canon(c, org)

    org_rule_ingest.run_org_discovery(c, org_id=org, event_id=event_id,
                                      extractor=_Extractor(), now=NOW)

    learning_id = c.execute(text("select learning_id from learning_objects "
                                 "where org_id=:o and unit=:u"),
                            {"o": org, "u": og.DISCOVERY_UNIT}).scalar()
    assert _states(c, org, learning_id) == ["observed", "candidate", "validated", "governed",
                                            "human_review"]
    detail = c.execute(text(
        "select detail from learning_transitions where org_id=:o and learning_id=:l "
        "and to_state='validated'"), {"o": org, "l": learning_id}).scalar()
    # One document is one observation, so the RECURRENCE floors do not hold — and the receipt
    # says so in the ledger rather than in a comment.
    assert detail["floors_ok"] is False
    assert detail["floors_reason"] == "insufficient_observations"


def test_a_tenant_that_turned_review_off_still_faces_the_floors(conn):
    """The floors bite wherever no human will look. `organization_requires_review` is settable;
    turning it off must not also turn the recurrence floors off."""
    c, org = conn
    seed_founder(c, org)
    event_id = seed_canon(c, org)
    loose = LearningPolicy(org_id=org, revision=1, organization_requires_review=False)

    out = org_rule_ingest.run_org_discovery(c, org_id=org, event_id=event_id,
                                            extractor=_Extractor(), now=NOW, policy=loose)

    assert out["proposed"] == 0
    assert out["not_admitted_insufficient_observations"] == 1
    assert c.execute(text("select count(*) from learned_brain_entries where org_id=:o"),
                     {"o": org}).scalar() == 0


def test_three_confirmed_rules_reach_the_organization_brain(conn):
    """J4: org entries (discovered + admin-confirmed) >= 3. The confirmation is the only thing
    that publishes, and it publishes through `feedback.publisher`, not through this unit."""
    c, org = conn
    node = seed_founder(c, org)
    body = (POLICY_TEXT
            + "Customer refunds must be issued within 30 days of the request.\n"
            + "The billing service is a critical system and must not be paused without approval.\n")
    event_id = seed_canon(c, org, body=body)
    cands = [
        candidate(QUOTE_50K, source=body),
        candidate(QUOTE_HIRING, source=body, subject_type="hiring", threshold=None),
        candidate("Customer refunds must be issued within 30 days of the request.", source=body,
                  category="policy", subject_type="refund", threshold=None, approver=None),
    ]
    org_rule_ingest.run_org_discovery(c, org_id=org, event_id=event_id,
                                      extractor=_Extractor(cands), now=NOW)

    ids = [r[0] for r in c.execute(text(
        "select learning_id from learning_objects where org_id=:o and unit=:u"),
        {"o": org, "u": og.DISCOVERY_UNIT})]
    assert len(ids) == 3
    for learning_id in ids:
        _confirm(c, org, learning_id)

    entries = c.execute(text(
        "select subject, version, value from learned_brain_entries "
        "where org_id=:o and brain='organization' and active order by subject"),
        {"o": org}).mappings().all()
    assert len(entries) == 3
    assert [e["subject"] for e in entries] == ["orgrule:approval:contract",
                                               "orgrule:approval:hiring",
                                               "orgrule:policy:refund"]
    assert all(e["version"] == 1 for e in entries)

    projected = org_rule_ingest.project_authority_rules(c, org_id=org, at=NOW)
    assert projected["upserted"] == 2            # the two approvals; a refund policy names nobody
    rules = c.execute(text(
        "select subject_type, threshold_minor_units, currency, approver_node_id, source, "
        "evidence_ref, valid_from, valid_until from authority_rules where org_id=:o "
        "order by subject_type"), {"o": org}).mappings().all()
    assert [r["subject_type"] for r in rules] == ["contract", "hiring"]
    assert rules[0]["threshold_minor_units"] == 5_000_000 and rules[0]["currency"] == "USD"
    assert all(r["source"] == "discovered" and r["approver_node_id"] == node for r in rules)
    assert all(r["evidence_ref"] == f"prepared_content:{event_id}" for r in rules)
    # The window opens when the DOCUMENT said so, not when the admin happened to click.
    assert rules[0]["valid_from"] == STATED and rules[0]["valid_until"] is None


def _confirm(c, org, learning_id):
    """The console's confirmation, driven through the REAL owner route.

    `POST /v1/learning/objects/{id}/review` is the only surface that turns a discovered rule into
    an authoritative one, and it is what J4's "writes outside the L6 pipeline = 0" is measured
    against: the route publishes through `feedback.publisher` and then projects the Authority
    row, both inside its own transaction. Calling the handler rather than reproducing it is the
    point — a copy of the console's steps would keep passing the day the console changed.
    """
    from genios_engine.api import learning_routes
    from genios_engine.platform.auth import AuthCtx

    body = learning_routes.review(
        learning_id, approve=True,
        ctx=AuthCtx(org_id=org, actor_id="seat_admin", scopes=["owner"]))
    assert body["state"] == "promoted"
    assert body["expert_brain_changed"] is False
    assert body["published"] not in (None, "object_unreadable", "identity_mismatch",
                                     "rejected"), body
    return body


def test_a_brain_write_with_brain_expert_is_refused_by_the_database(conn):
    """J4, LAW 3: the Expert Brain is human territory and it is enforced at the DB, not by policy.

    The attempt is made, the error is caught, and its identity is asserted — a test that only
    checked the constraint EXISTS would still pass if somebody dropped it and re-added it as a
    comment.
    """
    from sqlalchemy.exc import IntegrityError

    c, org = conn
    savepoint = c.begin_nested()
    with pytest.raises(IntegrityError) as raised:
        c.execute(text(
            "insert into learned_brain_entries (org_id, brain, subject, version, learning_id, "
            "value, visibility_scope, visibility) values "
            "(:o, 'expert', 'orgrule:approval:contract', 1, 'lo_x', cast('{}' as jsonb), "
            "'organization', cast('{}' as jsonb))"), {"o": org})
    savepoint.rollback()
    assert "learned_brain_no_expert" in str(raised.value)

    # And there is no vocabulary for it above the database either: the enum the publisher
    # dispatches on has no such member, so no code path could construct the attempt.
    assert "expert" not in {t.value for t in LearningTarget}


def test_nothing_outside_the_publisher_writes_a_brain_entry(conn):
    """J4: writes outside the L6 pipeline = 0. Asserted structurally — the ONE insert into
    `learned_brain_entries` in the whole engine lives in `feedback/publisher.publish_brain`."""
    import pathlib

    root = pathlib.Path(og.__file__).resolve().parents[3] / "genios_engine"
    writers = []
    for py in root.rglob("*.py"):
        body = py.read_text()
        for verb in ("insert into learned_brain_entries", "update learned_brain_entries",
                     "insert into temporary_memories"):
            if verb in body:
                writers.append(py.relative_to(root).as_posix())
    assert sorted(set(writers)) == ["feedback/publisher.py"]


def test_a_superseding_document_supersedes_rather_than_forks(conn):
    """Invariant #8 — one active version per (org, brain, subject) — and doc 02's stale-policy
    row: the old authority rule gets a `valid_until`, it is not edited and it is not left open."""
    c, org = conn
    node = seed_founder(c, org)
    first = seed_canon(c, org)
    org_rule_ingest.run_org_discovery(c, org_id=org, event_id=first,
                                      extractor=_Extractor(), now=NOW)
    _confirm(c, org, c.execute(text("select learning_id from learning_objects "
                                    "where org_id=:o and unit=:u"),
                               {"o": org, "u": og.DISCOVERY_UNIT}).scalar())

    revised_body = POLICY_TEXT.replace("$50,000", "$25,000")
    revised_quote = QUOTE_50K.replace("$50,000", "$25,000")
    second = seed_canon(c, org, event_id="evt_policy_2", body=revised_body,
                        version_key="policy:approvals@v2", occurred_at=LATER)
    org_rule_ingest.run_org_discovery(
        c, org_id=org, event_id=second, now=NOW,
        extractor=_Extractor([candidate(revised_quote, source=revised_body,
                                        threshold="$25,000")]))
    newer = c.execute(text(
        "select learning_id from learning_objects where org_id=:o and unit=:u "
        "and state='human_review'"), {"o": org, "u": og.DISCOVERY_UNIT}).scalar()
    _confirm(c, org, newer)

    entries = c.execute(text(
        "select version, active, value from learned_brain_entries where org_id=:o "
        "and subject='orgrule:approval:contract' order by version"), {"o": org}).mappings().all()
    assert [(e["version"], e["active"]) for e in entries] == [(1, False), (2, True)]
    assert entries[1]["value"]["threshold_minor_units"] == 2_500_000

    windows = c.execute(text(
        "select threshold_minor_units, valid_from, valid_until from authority_rules "
        "where org_id=:o order by valid_from"), {"o": org}).mappings().all()
    assert len(windows) == 2, "one rule_id, two half-open windows — not two live rules"
    assert windows[0]["valid_until"] == LATER, "March's rule must be CLOSED, not edited"
    assert windows[1]["valid_from"] == LATER and windows[1]["valid_until"] is None
    assert windows[1]["threshold_minor_units"] == 2_500_000
    assert c.execute(text("select count(distinct rule_id) from authority_rules where org_id=:o"),
                     {"o": org}).scalar() == 1
    assert node                              # the approver stayed the same across the supersession


def test_a_rule_whose_approver_cannot_be_named_never_binds(conn):
    """Doc 02: an "inferred"-shaped rule auto-enforcing cannot happen. Here the mechanism is
    concrete — the brain entry publishes, but `authority_rules` gets nothing, because
    `AuthorityRule.approver_node_id` is required and nobody could supply one."""
    c, org = conn
    event_id = seed_canon(c, org)          # no founder alias seeded: the approver does not resolve
    org_rule_ingest.run_org_discovery(c, org_id=org, event_id=event_id,
                                      extractor=_Extractor(), now=NOW)
    learning_id = c.execute(text("select learning_id from learning_objects "
                                 "where org_id=:o and unit=:u"),
                            {"o": org, "u": og.DISCOVERY_UNIT}).scalar()
    value = c.execute(text("select proposed_value from learning_objects "
                           "where org_id=:o and learning_id=:l"),
                      {"o": org, "l": learning_id}).scalar()
    assert value["authority_pending"] is True and value["approver_node_id"] is None
    assert value["approver_as_written"] == "founder"

    _confirm(c, org, learning_id)
    assert c.execute(text("select count(*) from learned_brain_entries where org_id=:o and active"),
                     {"o": org}).scalar() == 1
    assert c.execute(text("select count(*) from authority_rules where org_id=:o"),
                     {"o": org}).scalar() == 0


def test_a_retired_rule_stops_binding_and_march_still_answers(conn):
    """A brain entry rolled back or deactivated closes its authority window at `at` — it is never
    deleted, because the row is the evidence that the rule existed and that it ended."""
    c, org = conn
    seed_founder(c, org)
    event_id = seed_canon(c, org)
    org_rule_ingest.run_org_discovery(c, org_id=org, event_id=event_id,
                                      extractor=_Extractor(), now=NOW)
    _confirm(c, org, c.execute(text("select learning_id from learning_objects "
                                    "where org_id=:o and unit=:u"),
                               {"o": org, "u": og.DISCOVERY_UNIT}).scalar())

    from genios_engine.feedback.publisher import rollback_brain
    assert rollback_brain(c, org_id=org, brain="organization",
                          subject="orgrule:approval:contract", at=NOW) == "rolled_back_to_empty"
    counts = org_rule_ingest.project_authority_rules(c, org_id=org, at=NOW)

    assert counts["upserted"] == 0 and counts["closed"] == 1
    row = c.execute(text("select valid_from, valid_until from authority_rules where org_id=:o"),
                    {"o": org}).mappings().one()
    assert row["valid_from"] == STATED and row["valid_until"] == NOW


def test_the_cost_gate_refuses_a_wiki_before_the_model_is_called(conn):
    """The kind gate is also the bill. A tenant's wiki must not pay for a T2 extraction."""
    c, org = conn
    event_id = seed_canon(c, org, kind="wiki", version_key="wiki:handbook@v1",
                          source_object_id="wiki:handbook")
    extractor = _Extractor()

    out = org_rule_ingest.run_org_discovery(c, org_id=org, event_id=event_id,
                                            extractor=extractor, now=NOW)

    assert out["skipped"] == "kind_not_rule_bearing"
    assert extractor.calls == 0, "the model was called for a document that cannot carry a rule"
    assert c.execute(text("select outcome from org_rule_discovery_runs where org_id=:o"),
                     {"o": org}).scalar() == "kind_not_rule_bearing"
    assert c.execute(text("select reason_code from learning_input_rejections "
                          "where org_id=:o and seam=:s"),
                     {"o": org, "s": og.DISCOVERY_SEAM}).scalar() == "kind_not_rule_bearing"


def test_every_refusal_is_named_and_counted_in_two_places(conn):
    """Doc 06's weld-receipt discipline applied to this unit: a candidate that vanished without a
    counter is the failure this whole file exists to avoid."""
    c, org = conn
    seed_founder(c, org)
    event_id = seed_canon(c, org)
    cands = [candidate(QUOTE_50K),
             candidate(QUOTE_50K, threshold="$75,000"),
             candidate(QUOTE_DESCRIPTIVE, category="process", subject_type="expense",
                       threshold=None, approver=None)]

    out = org_rule_ingest.run_org_discovery(c, org_id=org, event_id=event_id,
                                            extractor=_Extractor(cands), now=NOW)

    assert out["candidates"] == 3 and out["refused"] == 2 and out["proposed"] == 1
    assert out["refused_threshold_not_in_quote"] == 1 and out["refused_no_deontic_force"] == 1
    ledger = sorted(r[0] for r in c.execute(text(
        "select reason_code from learning_input_rejections where org_id=:o and seam=:s"),
        {"o": org, "s": og.DISCOVERY_SEAM}))
    assert len(ledger) == 2
    assert ledger[0].startswith("no_deontic_force") and ledger[1].startswith(
        "threshold_not_in_quote")
    receipt = c.execute(text("select counters from org_rule_discovery_runs where org_id=:o"),
                        {"o": org}).scalar()
    assert receipt["candidates"] == 3 and receipt["refused"] == 2


def test_reading_the_same_document_version_twice_costs_nothing(conn):
    """Idempotency has two layers and both are asserted: the receipt stops the model call, and
    content addressing would stop the duplicate proposal even if it did not."""
    c, org = conn
    seed_founder(c, org)
    event_id = seed_canon(c, org)
    extractor = _Extractor()
    org_rule_ingest.run_org_discovery(c, org_id=org, event_id=event_id, extractor=extractor,
                                      now=NOW)

    again = org_rule_ingest.run_org_discovery(c, org_id=org, event_id=event_id,
                                              extractor=extractor, now=NOW)

    assert again["skipped"] == "already_discovered"
    assert extractor.calls == 1
    assert c.execute(text("select count(*) from learning_objects where org_id=:o and unit=:u"),
                     {"o": org, "u": og.DISCOVERY_UNIT}).scalar() == 1


def test_an_edited_policy_is_read_again(conn):
    """The receipt is keyed on the document VERSION, so an edit re-opens it. Keying on the event
    alone would make an edited policy permanently unreadable."""
    c, org = conn
    seed_founder(c, org)
    seed_canon(c, org)
    org_rule_ingest.run_org_discovery(c, org_id=org, event_id="evt_policy_1",
                                      extractor=_Extractor(), now=NOW)

    assert org_rule_ingest.already_discovered(
        c, org_id=org, event_id="evt_policy_1", version_key="policy:approvals@v1") is True
    assert org_rule_ingest.already_discovered(
        c, org_id=org, event_id="evt_policy_1", version_key="policy:approvals@v2") is False


def test_a_model_failure_leaves_the_document_unread_rather_than_half_read(conn):
    c, org = conn
    event_id = seed_canon(c, org)

    out = org_rule_ingest.run_org_discovery(c, org_id=org, event_id=event_id,
                                            extractor=_BrokenExtractor(), now=NOW)

    assert out["skipped"] == "extractor_failed"
    assert c.execute(text("select outcome from org_rule_discovery_runs where org_id=:o"),
                     {"o": org}).scalar() == "extractor_failed"
    assert c.execute(text("select count(*) from learning_objects where org_id=:o and unit=:u"),
                     {"o": org, "u": og.DISCOVERY_UNIT}).scalar() == 0


def test_the_sweep_finds_exactly_the_unread_rule_bearing_documents(conn):
    """What the two canon doors actually schedule."""
    c, org = conn
    seed_canon(c, org, event_id="evt_a")
    seed_canon(c, org, event_id="evt_b", kind="sop", version_key="sop:onboarding@v1",
               source_object_id="sop:onboarding")
    seed_canon(c, org, event_id="evt_c", kind="wiki", version_key="wiki:handbook@v1",
               source_object_id="wiki:handbook")

    assert set(org_rule_ingest.undiscovered_events(c, org_id=org)) == {"evt_a", "evt_b"}

    org_rule_ingest.run_org_discovery(c, org_id=org, event_id="evt_a",
                                      extractor=_Extractor([]), now=NOW)
    assert org_rule_ingest.undiscovered_events(c, org_id=org) == ["evt_b"]


def test_an_approver_resolves_through_the_identity_layers_own_keys(conn):
    """Three keys, and no others: an email alias, an observed person name, a canon role title."""
    c, org = conn
    c.execute(text("insert into graph_aliases (org_id, alias_type, alias_key, node_id, origin) "
                   "values (:o, 'email', 'cfo@acme.io', 'node_cfo', 'anchor')"), {"o": org})
    c.execute(text("insert into graph_aliases (org_id, alias_type, alias_key, node_id, origin) "
                   "values (:o, 'person_name', 'rohit sharma', 'node_rohit', 'observed')"),
              {"o": org})
    seed_founder(c, org)

    assert org_rule_ingest.resolve_approver_node(c, org_id=org, name="CFO@acme.io") == "node_cfo"
    assert org_rule_ingest.resolve_approver_node(
        c, org_id=org, name="Rohit Sharma") == "node_rohit"
    assert org_rule_ingest.resolve_approver_node(
        c, org_id=org, name="Founder") == "node_founder_1"
    assert org_rule_ingest.resolve_approver_node(c, org_id=org, name="the board") is None


def test_the_tenants_locale_is_read_and_never_guessed(conn):
    c, org = conn
    seed_canon(c, org)
    assert org_rule_ingest.org_locale(c, org_id=org) == "en-US"
    assert org_rule_ingest.load_canon_document(c, org_id=org,
                                               event_id="evt_policy_1").locale == "en-US"

    c.execute(text("update orgs set locale = null where id = :o"), {"o": org})
    assert org_rule_ingest.load_canon_document(c, org_id=org,
                                               event_id="evt_policy_1").locale is None


def test_the_discovery_receipt_is_erased_with_the_tenant(conn):
    """Driven through the real `_wipe`, not asserted against the list — a name in a list that
    nothing executes is exactly how a table leaks silently."""
    from genios_engine.api import account_routes

    c, org = conn
    seed_founder(c, org)
    seed_canon(c, org)
    org_rule_ingest.run_org_discovery(c, org_id=org, event_id="evt_policy_1",
                                      extractor=_Extractor(), now=NOW)
    assert c.execute(text("select count(*) from org_rule_discovery_runs where org_id=:o"),
                     {"o": org}).scalar() == 1

    wiped = account_routes._wipe(c, org)

    assert wiped["org_rule_discovery_runs"] == 1
    assert c.execute(text("select count(*) from org_rule_discovery_runs where org_id=:o"),
                     {"o": org}).scalar() == 0


def test_the_authority_projection_covers_every_contract_field(conn):
    """The upsert is hand-written SQL because it must share the caller's transaction. A field
    added to `AuthorityRule` and forgotten here would be silently dropped on the way to L2."""
    from genios_engine.contracts.authority import AuthorityRule

    sql = str(org_rule_ingest._AUTHORITY_UPSERT)
    for name in AuthorityRule.model_fields:
        assert name in sql, f"{name} is on AuthorityRule but not in the projection's column list"
    del conn


# ══════════════════════════════════════════════════════════════════════════════════════════════
# Reached from a real path
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_both_canon_doors_schedule_discovery():
    """"On canon ingest" is doc 02's trigger, and there are exactly two canon doors: the writing
    door and a tagged upload. A unit only tests can reach is not shipped."""
    from genios_engine.api import knowledge_routes, upload_routes

    for module, fn in ((knowledge_routes, knowledge_routes.write_knowledge),
                       (upload_routes, upload_routes.upload_resource)):
        src = inspect.getsource(fn)
        # The CALL, not the import: a door that imports the sweep and never schedules it is a
        # door that does not trigger N-3, and it reads identically to one that does.
        assert "add_task(sweep_org_rule_discovery" in src, (
            f"{module.__name__} imports the sweep but never schedules it")


def test_the_console_projection_rides_inside_the_approvals_own_transaction():
    """The projection must be INSIDE the route's `engine.begin()` block and after the publish.

    An approval that commits without the authority row it authorises is the same split
    `learning_routes` already fixed once for the approval/publish pair; the live path is asserted
    by `_confirm`, and this pins the ordering the live path depends on.
    """
    from genios_engine.api import learning_routes

    src = inspect.getsource(learning_routes.review)
    call = "project_confirmed_rule(c,"
    assert call in src, "the review route imports the projection but never calls it"
    assert src.index("_publish_approved(c,") < src.index(call)
    assert src.index(call) < src.index("return {"), "the projection escaped the transaction block"


def test_the_extractor_is_never_asked_for_a_number_or_a_paraphrase():
    """The T2 prompt's shape IS the anti-hallucination design: pointers, not content."""
    from genios_engine.packs.brains.org_rule_extract import PROMPT

    assert "EXACT sentence" in PROMPT and "character for character" in PROMPT
    assert "NEVER compute or normalise a number" in PROMPT
    assert "literal substring of" in PROMPT
    assert '{"rules": []}' in PROMPT.replace("{{", "{").replace("}}", "}")


def test_no_model_is_configured_means_no_discovery_rather_than_a_stub():
    from genios_engine.packs.brains.org_rule_extract import make_org_rule_extractor

    assert make_org_rule_extractor() is None      # conftest clears the key for the whole process
    assert org_rule_ingest.sweep_org_rule_discovery(
        "org_nobody", engine=object())["skipped"] == "no_extractor"


def test_the_proposal_is_shaped_by_the_learning_contract_not_by_this_unit():
    """A sanity net under `build_proposal`: the contract is what refuses a float, a naive
    datetime or an expert target, and it must be the thing constructing the object."""
    with pytest.raises(ValueError):
        LearningObject(org_id="org_t", unit=og.DISCOVERY_UNIT, target=LearningTarget.ORGANIZATION,
                       subject="orgrule:approval:contract", proposed_value={},
                       evidence=LearningEvidence(observations=1, independent_refs=1,
                                                 distinct_days=1, positive=1, negative=0,
                                                 confidence_bp=10001),
                       visibility=Visibility(scope=VisibilityScope.ORGANIZATION),
                       first_seen_at=STATED, last_seen_at=STATED, policy_key="policy:org_t:1")
