"""Step 6 · domain mapping — four names, no confidence, and a proposer that cannot read.

    pytest tests/capture/domain/test_a_domain_says_how_sure_it_is.py -q

THREE OF THIS STEP'S WRITTEN PREMISES WERE WRONG, checked against the code on 2026-09-24 before a
line was planned. They are recorded here because the corrections are what the step actually is.

    "single-label, 1 or 0 domains"     WRONG — `domain_hints` loops and appends every match.
                                       The file's own comment still says "the FIRST match wins in
                                       `resolve_domain`", and `resolve_domain` no longer exists.
    "the never-filter rule has no test" WRONG — `tests/capture/esqe/test_domain.py` has 14, green,
                                       including the strongest form ("the tag list is
                                       byte-identical whether the tenant has full coverage, no
                                       coverage, or no coverage function at all"). 6-U4 struck.
    "four keyword tables"              STALE — four SHIPPED plus any number authored by an L3
                                       corpus through `domain.yaml` (`hints._authored_hints`).

WHAT IS ACTUALLY MISSING, and what this file is about:

  1. **No confidence.** `DomainHint` is `{domain, source}`. A pattern that fired on "term sheet"
     and one that fired on a stray "deck" render identically, and nothing downstream can tell
     "probably sales" from "certainly sales".
  2. **No ontology.** There is no single place that says which domains exist, so nothing can
     refuse a name that exists nowhere — and nothing records that it was proposed.
  3. **Nothing reads more words than a regex.** A keyword table only knows the language somebody
     thought to write down. A real mailbox is mostly ordinary sentences.

THE FAILURE THIS COSTS, in `hints.py`'s own words: letting the generic sales vocabulary claim
investor threads turned *"six VCs and three accelerator programmes into sales opportunities. Not
one of its sixteen sales situations was a customer."* A confidence is what makes that visible
before it reaches a card.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# =============================================================================================
# 6-U1 · a hint says how sure it is
# =============================================================================================
def test_a_domain_hint_carries_a_confidence():
    """`{domain, source}` cannot distinguish a pattern that fired on "term sheet" from one that
    fired on a stray "deck". Both reach `qualified_signals.domain_hints` as the same object."""
    from genios_engine.contracts.gated_event import DomainHint

    assert "confidence_bp" in DomainHint.model_fields


def test_the_confidence_is_integer_basis_points():
    """V-7. A float here reaches `domain_hints` jsonb and comes back as a number nobody can trace
    to a rule — and this is the field a model will eventually write into, which is exactly where
    a 0.85 gets in."""
    from genios_engine.contracts.gated_event import DomainHint

    with pytest.raises(Exception):
        DomainHint(domain="sales", source="keyword", confidence_bp=0.85)


def test_the_three_deterministic_sources_are_not_equally_sure():
    """A SOURCE PRIOR, A KEYWORD AND A FALLBACK ARE THREE DIFFERENT CLAIMS, and flattening them
    to one number is how the six-VCs failure stayed invisible:

        scope     the connection itself is that domain. The strongest thing L1 knows.
        keyword   this message used that vocabulary. Real evidence, weaker than the account.
        fallback  nothing matched and the caller said "it is business" — the weakest possible
                  statement, and it must never rank beside evidence.

    The ORDER is the assertion, not the literals. Pinning exact numbers would make a later
    recalibration look like a regression.
    """
    from genios_engine.capture.domain.hints import CONFIDENCE_BP

    assert CONFIDENCE_BP["scope"] > CONFIDENCE_BP["keyword"] > CONFIDENCE_BP["fallback"]
    assert all(0 <= v <= 10_000 for v in CONFIDENCE_BP.values())


def test_the_wire_shape_carries_the_confidence_to_layer_two():
    """A field on the contract that `as_dicts` drops is a field L2 never sees — the same loss
    step 3 spent its whole length closing at the other end of this seam."""
    from genios_engine.capture.esqe.domain import tag_domains

    tagging = tag_domains("hubspot", "the term sheet and the cap table")
    assert tagging.as_dicts, "fixture problem: nothing was tagged"
    for entry in tagging.as_dicts:
        assert "confidence_bp" in entry, f"the seam drops the confidence: {entry}"
        assert isinstance(entry["confidence_bp"], int)


# =============================================================================================
# 6-U2 · the ontology — one place that says which domains exist
# =============================================================================================
def test_the_registered_set_is_derived_from_both_tables_never_listed():
    """Shipped ∪ authored, read off the same tables `domain_hints` matches against.

    A hand-written list would be correct on the day it was typed and wrong the day a tenant
    authors a corpus — and the failure mode is the worst kind: a domain the matcher can produce
    and the ontology refuses.
    """
    from genios_engine.capture.domain.ontology import registered_domains

    assert {"fundraising", "sales", "support", "admin"} <= registered_domains()


def test_every_domain_the_matcher_can_produce_is_registered():
    """THE CONSISTENCY GUARD, and the reason the ontology is derived rather than declared.

    If `domain_hints` can return a name that `registered_domains()` does not contain, then the
    shipping path produces proposals its own validator refuses, and every one of them lands as
    `proposed_unknown` while being perfectly well known.
    """
    from genios_engine.capture.domain.hints import _SHIPPED_RANK, _SOURCE_PRIOR
    from genios_engine.capture.domain.ontology import registered_domains

    known = registered_domains()
    for name in (*_SHIPPED_RANK, *_SOURCE_PRIOR.values()):
        assert name in known, f"`{name}` is matchable but not registered"


def test_the_fallback_domain_is_itself_registered():
    """`FALLBACK_DOMAIN = "admin"` is stamped on messages nothing matched. A fallback the
    ontology refuses would turn every unmatched business message into an unknown proposal."""
    from genios_engine.capture.domain.hints import FALLBACK_DOMAIN
    from genios_engine.capture.domain.ontology import registered_domains

    assert FALLBACK_DOMAIN in registered_domains()


# =============================================================================================
# 6-U3 · a name we do not run is RECORDED, never dropped
# =============================================================================================
def test_a_proposal_outside_the_ontology_is_recorded_not_discarded():
    """E1. A proposer that says `procurement` for a tenant with no procurement corpus has told us
    something true about the message and something true about our own gaps. Dropping it silently
    is how `context/extract/vocab.py` ended up with 268 invented field names nobody reviewed."""
    from genios_engine.capture.domain.ontology import PROPOSED_UNKNOWN, validate_proposal

    verdict = validate_proposal("procurement")

    assert verdict.accepted is False
    assert verdict.outcome == PROPOSED_UNKNOWN
    assert verdict.domain == "procurement", "the name must survive to be reviewable"


def test_a_registered_proposal_is_accepted():
    """SENSITIVITY. A validator that refused everything would satisfy the row above."""
    from genios_engine.capture.domain.ontology import validate_proposal

    assert validate_proposal("sales").accepted is True


def test_a_blank_or_nonsense_proposal_is_refused_and_is_not_an_unknown_domain():
    """An empty string is not a domain somebody proposed — it is a malformed answer, and filing
    it in the discovery lane would put rows in front of a reviewer that name nothing."""
    from genios_engine.capture.domain.ontology import PROPOSED_MALFORMED, validate_proposal

    for bad in ("", "   ", None, 42):
        verdict = validate_proposal(bad)
        assert verdict.accepted is False
        assert verdict.outcome == PROPOSED_MALFORMED, bad


def test_the_name_is_normalised_before_it_is_judged():
    """`Sales`, ` sales ` and `SALES` are one domain. Judging them as three would file two
    perfectly good proposals as unknown and put noise in the review queue."""
    from genios_engine.capture.domain.ontology import validate_proposal

    for spelling in ("Sales", " sales ", "SALES"):
        verdict = validate_proposal(spelling)
        assert verdict.accepted is True, spelling
        assert verdict.domain == "sales", "the normalised name is what downstream must store"


# =============================================================================================
# 6-U5 · coverage is not the number — DISTRIBUTION is
# =============================================================================================
def test_the_sweep_reports_domain_coverage():
    """It lands on `SyncSummary` beside step 5's completeness fields, because "how many events got
    a real domain" is the same kind of per-sweep fact as "did this sweep finish"."""
    from genios_engine.capture.acquire.sync_runner import SyncSummary

    fields = SyncSummary.__dataclass_fields__
    assert "domain_tagged" in fields and "domain_fallback_only" in fields


def test_a_tagger_that_says_everything_is_visible_in_the_distribution():
    """E5, AND THE REASON COVERAGE ALONE IS THE WRONG METRIC.

    A proposer that returns all five domains for every message has **100% coverage and zero
    information**. Coverage cannot see it; a distribution can. This is the metric that would have
    caught the six-VCs failure — every investor thread tagged `sales` looks like excellent
    coverage right up until somebody reads a card.
    """
    from genios_engine.capture.domain.coverage import domain_distribution

    everything = domain_distribution([("sales", "fundraising", "support", "admin")] * 10)
    focused = domain_distribution([("sales",)] * 5 + [("fundraising",)] * 5)

    assert everything.mean_domains_per_event_bp > focused.mean_domains_per_event_bp
    assert everything.is_indiscriminate is True
    assert focused.is_indiscriminate is False


def test_an_event_tagged_only_by_the_fallback_is_not_counted_as_tagged():
    """The whole point of metric 4. `FALLBACK_DOMAIN` exists so unmatched business mail is not
    invisible — it is a placeholder, and counting it as coverage restates the problem as a
    solution."""
    from genios_engine.capture.domain.coverage import domain_distribution

    stats = domain_distribution([("admin",)], fallback_only=[True])

    assert stats.tagged == 0 and stats.fallback_only == 1


# =============================================================================================
# The rules this step must not break
# =============================================================================================
def test_the_extraction_cache_fingerprint_is_untouched():
    """⛔ THE ARCHITECTURE DECISION, made by the cost check before any code was written.

    `vocabulary_fingerprint()` folds in every closed set in `vocabulary._SETS` and is a component
    of the `l1_extraction_results` key. Adding a `domain` set to LLM-2's vocabulary would move it
    and **re-extract the entire corpus — a second full model bill on top of step 4's.**

    So the domain proposer is its OWN model call, not a field on LLM-2's prompt. This row is what
    stops a later edit quietly undoing that: if the fingerprint moves, the proposer has leaked
    into the extraction vocabulary.
    """
    from genios_engine.capture.semantic.vocabulary import vocabulary_fingerprint

    assert vocabulary_fingerprint() == "a3d5496aa0d3", (
        "the L1 extraction vocabulary changed during a DOMAIN step. If that was deliberate, the "
        "whole corpus re-extracts and somebody has to approve the bill — see step 6 §5.0")


def test_domain_tagging_still_never_filters():
    """REGRESSION GUARD on the rule that was already tested, and which this step is the most
    likely thing ever to break: everything here is about judging domains, and the one thing a
    domain judgement may never do is remove a signal."""
    from genios_engine.capture.esqe.domain import tag_domains

    covered_none = tag_domains("gmail", "the term sheet and the renewal contract",
                               coverage_fn=lambda d: {"coverage_ready": False})
    covered_all = tag_domains("gmail", "the term sheet and the renewal contract",
                              coverage_fn=lambda d: {"coverage_ready": True})

    assert covered_none.domains == covered_all.domains
    assert covered_none.degraded_compile is True and covered_all.degraded_compile is False


# =============================================================================================
# 6-U5, DRIVEN — the half step 5 got wrong and this step must not repeat
# =============================================================================================
def _sweep(*, text: str, source: str = "gmail"):
    """Run the REAL `run_sync` over one message and return its summary.

    Written this way on purpose. Step 5 put `claimed_total` on `SyncSummary`, read it with
    `getattr(batch, "claimed_total", None)` against a field no contract had, and shipped a metric
    that was None on every row with a green test beside it — because the test asked whether the
    container had somewhere to put a number rather than whether a number ever arrived.

    So metric 4 is asserted through the sweep that produces it, never on the dataclass.
    """
    from datetime import datetime, timezone

    from genios_engine.capture.acquire.sync_runner import run_sync
    from genios_engine.capture.connectors.base import RawObject, SourceBatch
    from genios_engine.capture.landing.repository import InMemorySourceEventRepository

    class _One:
        def __init__(self) -> None:
            self.source = source

        def initial_snapshot(self, cursor=None, limit=100):
            return SourceBatch(objects=[RawObject(
                source=source, object_type="email_message", source_object_id="o1",
                occurred_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
                actor_email="priya@acme.com",
                # A REAL SOURCE and REAL RECIPIENTS are both required for this to emit, and the
                # first version of this fixture had neither. `derive_visibility` returns None for
                # a family the registry does not know ("fake"), the gate parks at S0.6 as
                # `visibility_unknown` — *"unknown provenance gets parked, never published under
                # a guessed audience"* — and a parked event carries no gated object. Metric 4 was
                # then measured over zero events and read a perfect 0 with nothing wrong.
                recipients=("rohit@genios.ai",),
                raw={"subject": text, "snippet": text})], next_cursor=None)

        def incremental_changes(self, cursor=None, limit=100, since=None):
            return self.initial_snapshot(cursor, limit)

        def fetch_content(self, object_ref):
            return {"body": text}

    return run_sync(_One(), org_id="org_step6", connection_id="conn_step6",
                    repo=InMemorySourceEventRepository(), source=source, mode="backfill")


def test_metric_four_is_counted_by_the_sweep_that_produces_it():
    """A message using fundraising vocabulary must come out of a real sweep counted as tagged."""
    summary = _sweep(text="the term sheet and the cap table are attached for diligence")

    assert summary.scanned == 1
    assert summary.domain_tagged == 1, (
        "the sweep produced a domain and the metric did not count it — the field is a place to "
        "put a number rather than a number")
    assert summary.domain_fallback_only == 0


def test_an_ordinary_sentence_lands_in_the_fallback_column_not_the_coverage_one():
    """SENSITIVITY, and the whole reason metric 4 has two columns instead of one.

    *"are we still on for thursday"* is the mailbox this system actually sees, and no keyword
    table will ever match it. The pipeline stamps `FALLBACK_DOMAIN` so the event is not invisible
    — and that placeholder must land in `domain_fallback_only`, never in `domain_tagged`.

    A counter that incremented on everything would satisfy the row above while reporting 100%
    coverage on a mailbox of ordinary sentences, which is the exact illusion this metric exists
    to dispel.
    """
    summary = _sweep(text="are we still on for thursday")

    assert summary.emitted == 1, "fixture problem: the event never reached the gate's far side"
    assert summary.domain_tagged == 0, (
        "an ordinary sentence was counted as covered — metric 4 is now reporting the fallback "
        "as a solution to the problem the fallback exists to make visible")
    assert summary.domain_fallback_only == 1


def test_the_fallback_is_counted_apart_from_real_coverage():
    """`FALLBACK_DOMAIN` is `admin`, which is ALSO a real domain a keyword can match — so the
    counter tests the hint's SOURCE and never its name. Getting this backwards would count every
    genuine admin thread as a gap, and every unmatched message as covered."""
    from genios_engine.capture.esqe.domain import tag_domains

    placeholder = tag_domains("gmail", "are we still on for thursday", fallback="admin")
    real = tag_domains("gmail", "the invoice and the renewal contract")

    assert [h.source for h in placeholder.hints] == ["fallback"]
    assert placeholder.domains == ("admin",)
    assert all(h.source != "fallback" for h in real.hints), (
        "the fixture no longer distinguishes the two cases")


# =============================================================================================
# 6-U6 · the proposer — the model DESCRIBES, the ontology DECIDES
# =============================================================================================
class _FakeLLM:
    """A client that answers once with whatever it was given."""

    model = "fake-domain-model-1"

    def __init__(self, payload, *, ok: bool = True, raises: bool = False):
        self.payload, self.ok, self.raises, self.calls = payload, ok, raises, 0

    def call(self, prompt: str, *, max_tokens: int = 4096):
        self.calls += 1
        if self.raises:
            raise RuntimeError("provider is down")
        import types
        return types.SimpleNamespace(parsed=self.payload, raw="", ok=self.ok, error=None,
                                     input_tokens=100, output_tokens=20)


class _ExplodingLLM:
    """Proves a no-call path by ABSENCE OF AN EXCEPTION rather than by a counter that could be
    read off a stale attribute — the pattern `esqe/relevance.py` states for exactly this."""

    model = "never-called"

    def call(self, prompt: str, *, max_tokens: int = 4096):
        raise AssertionError("a model was called on a path that must spend nothing")


LONG = ("We reviewed the security questionnaire your team sent over and it is currently "
        "blocking the procurement sign-off on our side, so the renewal cannot proceed.")


def test_a_registered_proposal_is_accepted_and_an_unregistered_one_is_recorded():
    """The two halves of doctrine, in one call. `sales` is ours; `procurement` is not — and the
    one we do not run is the more useful of the two, because it names a gap in our coverage."""
    from genios_engine.capture.domain.proposer import propose_domains

    outcome = propose_domains(LONG, llm=_FakeLLM({"domains": ["sales", "procurement"]}))

    assert outcome.accepted == ("sales",)
    assert outcome.unknown == ("procurement",), "the name we do not run was dropped, not recorded"


def test_the_stored_confidence_is_ours_and_never_the_model_s():
    """DOCTRINE 1 — a model may DESCRIBE, never SCORE. A model's self-reported certainty becoming
    a stored confidence is that line being crossed, so the constant is this module's."""
    from genios_engine.capture.domain.hints import CONFIDENCE_BP, merge_proposals
    from genios_engine.capture.domain.proposer import PROPOSAL_CONFIDENCE_BP

    merged = merge_proposals([], ["sales"])

    assert merged[0].confidence_bp == PROPOSAL_CONFIDENCE_BP
    assert PROPOSAL_CONFIDENCE_BP < CONFIDENCE_BP["keyword"], (
        "a reading of the text must not outrank a fact about the text")
    assert PROPOSAL_CONFIDENCE_BP > CONFIDENCE_BP["fallback"], (
        "a real proposal must outrank the placeholder, or the proposer buys nothing")


def test_a_dead_proposer_leaves_the_keyword_hints_intact():
    """E7. Domain is an ENRICHMENT and never a hard dependency of capture: the message is already
    landed and already carries its deterministic hints by the time this runs."""
    from genios_engine.capture.domain.proposer import propose_domains

    outcome = propose_domains(LONG, llm=_FakeLLM(None, raises=True))

    assert outcome.proposals == () and outcome.skipped_reason == "call_failed"


def test_a_short_message_spends_no_model_call():
    """E10, and the concrete saving the separate-call architecture buys. "thanks" has no domain to
    read, and at a mailbox's scale paying for it is most of the bill.

    Proved with a client that RAISES, so the assertion is the absence of an exception rather than
    a count that could be stale."""
    from genios_engine.capture.domain.proposer import propose_domains

    outcome = propose_domains("thanks!", llm=_ExplodingLLM())

    assert outcome.called is False and outcome.skipped_reason == "too_short"


def test_a_malformed_answer_yields_nothing_and_does_not_raise():
    """An enrichment that could throw would turn an optional improvement into a capture failure."""
    from genios_engine.capture.domain.proposer import propose_domains

    for payload in ({}, {"domains": "not a list"}, {"wrong_key": ["sales"]}, None):
        assert propose_domains(LONG, llm=_FakeLLM(payload)).accepted == (), payload


def test_the_proposal_count_is_bounded():
    """A proposer returning six names has not read the message, it has listed the taxonomy."""
    from genios_engine.capture.domain.proposer import MAX_PROPOSALS, propose_domains

    outcome = propose_domains(LONG, llm=_FakeLLM(
        {"domains": ["sales", "support", "admin", "fundraising", "legal", "procurement"]}))

    assert len(outcome.proposals) <= MAX_PROPOSALS


# =============================================================================================
# 6-U7 · the merge — E8, the six-VCs failure
# =============================================================================================
def test_a_keyword_and_a_proposal_that_disagree_both_survive():
    """THE LOAD-BEARING ROW OF THIS STEP.

    `hints.py` records what picking a winner silently cost: the generic sales vocabulary claimed
    investor threads, and *"six VCs and three accelerator programmes became sales opportunities.
    Not one of its sixteen sales situations was a customer."* A merge that resolved the
    disagreement would recreate that failure with a model's authority behind it.
    """
    from genios_engine.capture.domain.hints import domain_hints, merge_proposals

    keyword = domain_hints("gmail", "the renewal contract and the budget")
    assert [h.domain for h in keyword] == ["sales"], "fixture problem"

    merged = merge_proposals(keyword, ["fundraising"])

    assert {h.domain for h in merged} == {"sales", "fundraising"}
    assert {h.source for h in merged} == {"keyword", "proposed"}, (
        "the sources were flattened, so a reader cannot tell what fired from what was read")


def test_agreement_corroborates_and_never_downgrades():
    """E9. A keyword already produced `sales` at 6000. The proposer agreeing must not replace it
    with the proposer's lower 4500 — agreement is corroboration, never doubt."""
    from genios_engine.capture.domain.hints import CONFIDENCE_BP, domain_hints, merge_proposals

    keyword = domain_hints("gmail", "the renewal contract and the budget")
    merged = merge_proposals(keyword, ["sales"])

    assert len(merged) == 1
    assert merged[0].source == "keyword"
    assert merged[0].confidence_bp == CONFIDENCE_BP["keyword"]


def test_a_real_proposal_replaces_the_fallback_rather_than_joining_it():
    """A `fallback` hint means "nothing matched". The moment something real matches it is no
    longer true, and leaving it beside a genuine domain counts the event in BOTH columns of
    metric 4 — tagged and fallback-only at once."""
    from genios_engine.capture.domain.hints import domain_hints, merge_proposals

    placeholder = domain_hints("gmail", "are we still on for thursday", fallback="admin")
    assert [h.source for h in placeholder] == ["fallback"], "fixture problem"

    merged = merge_proposals(placeholder, ["support"])

    assert [(h.domain, h.source) for h in merged] == [("support", "proposed")]


def test_the_merge_never_removes_a_deterministic_hint():
    """§9: tag, never route, never drop. The single rule this step is most likely to break, since
    everything in it is about judging domains."""
    from genios_engine.capture.domain.hints import domain_hints, merge_proposals

    keyword = domain_hints("hubspot", "the term sheet and the renewal contract")
    before = {(h.domain, h.source) for h in keyword}

    merged = merge_proposals(keyword, ["procurement_is_not_registered_so_never_arrives_here"])

    assert before <= {(h.domain, h.source) for h in merged}


# =============================================================================================
# The proposer reaches the SHIPPING tagger — not a helper beside it
# =============================================================================================
def test_the_proposer_reaches_tag_domains_itself():
    """`tag_domains` is the only entry the pipeline uses, so it is the only place the proposer can
    be wired and still be reached.

    Step 5 shipped a metric read through `getattr` against a field no contract had; step 6's own
    metric-4 counter was a field nothing filled until it was driven through `run_sync`. Same class
    of defect, twice. So the proposal path is asserted through the shipping function.
    """
    from genios_engine.capture.esqe.domain import tag_domains

    tagging = tag_domains("gmail", LONG, proposer=_FakeLLM({"domains": ["support"]}))

    assert "support" in tagging.domains
    assert any(h.source == "proposed" for h in tagging.hints)


def test_an_unknown_proposal_is_carried_on_the_tagging_and_not_in_the_hints():
    """6-U3 at the seam. The name must be REVIEWABLE and must not be mistaken for a real domain:
    in `proposed_unknown`, never in `hints`."""
    from genios_engine.capture.esqe.domain import tag_domains

    tagging = tag_domains("gmail", LONG, proposer=_FakeLLM({"domains": ["procurement"]}))

    assert tagging.proposed_unknown == ("procurement",)
    assert "procurement" not in tagging.domains, (
        "a name the ontology refused is in the tag list, so an unknown proposal is now "
        "indistinguishable from a registered domain")


def test_no_proposer_is_the_shipping_default_and_changes_nothing():
    """The strongest form of "optional": byte-identical output with the argument absent.

    Every existing caller passes no proposer. If that path differed at all, this step would have
    changed production behaviour for every tenant on the day it merged, before anybody chose to
    turn a model on.
    """
    from genios_engine.capture.esqe.domain import tag_domains

    with_none = tag_domains("hubspot", LONG)
    explicit = tag_domains("hubspot", LONG, proposer=None)

    assert with_none.as_dicts == explicit.as_dicts
    assert with_none.proposed_unknown == () == explicit.proposed_unknown


def test_a_proposer_that_explodes_still_produces_the_deterministic_tagging():
    """E7 at the seam, not just in the unit. Domain is an enrichment; a dead model must not cost
    a tenant their capture."""
    from genios_engine.capture.esqe.domain import tag_domains

    healthy = tag_domains("hubspot", LONG)
    broken = tag_domains("hubspot", LONG, proposer=_FakeLLM(None, raises=True))

    assert broken.as_dicts == healthy.as_dicts
