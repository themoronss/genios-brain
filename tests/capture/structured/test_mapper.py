"""G2 · the structured bypass lane (L1.3.9 · ALG-21) — Wave W2.

Doc 03's acceptance, in the order it states it:

    Required: a HubSpot deal fixture produces an `ExtractionResult` with a `Money`, a
    `ResolvedDate` and `field_confidence == 10000`, **and zero LLM calls**; the synthesized
    evidence span has `verified=True`; an unregistered structured source falls through to
    `needs_extraction` and increments `unmapped_structured`.

Three of those four are asserted here as stated. The fourth — the routing of an unregistered
structured source — is asserted against what the GATE actually does, which is to PARK rather
than to run a model over raw JSON; `test_gate_parks_an_unmapped_structured_source_and_counts_it`
carries the divergence and the reason, and the metric doc 03 asked for is asserted either way.

Two mechanical rules run through the file:

* **Zero LLM is proved by explosion, never by counting.** A counter that is never read is a
  counter that passes when the fake is wired wrong. Every LLM double here RAISES on use, and
  `test_the_exploding_classifier_can_actually_fail` proves the explosive is live by detonating
  it — a test that cannot fail is worse than no test.
* **`verified=True` is proved by re-verification, never by reading the flag.** The flag is one
  bool and any code could set it; what makes it mean something is that
  `spans.verify_span` — ALG-08 itself — grades the stored span against the source text
  `structured_source_index` publishes and returns VERIFIED. That round trip is the assertion.

The plan's third G2 criterion — "an identical (amount, date, authority) yields an identical
`importance_bp` whichever lane produced it" — is NOT asserted here and is not faked.
`importance_bp` is ALG-17, built at W7 (L1.6.7), and `ExtractionResult` forbids the field by
construction today. It is a G7 criterion. What CAN be asserted at W2 is the property it rests
on — that the two lanes produce the same TYPE, validated by the same validator, with no field
distinguishing them but the token counts — and
`test_the_two_lanes_are_indistinguishable_to_everything_downstream` asserts exactly that.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest

from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.gate.gate import run_gate
from genios_engine.capture.structured.coverage import (BP_FULL, ConnectedObject, mapping_coverage)
from genios_engine.capture.structured.mapper import (
    DEFAULT_STRUCTURED_INTENT,
    STRUCTURED_FIELD_CONFIDENCE_BP,
    STRUCTURED_PROFILE,
    STRUCTURED_PROMPT_VERSION,
    STRUCTURED_SCHEMA_VERSION,
    STRUCTURED_STANCE,
    StructuredMappingError,
    absent_fields,
    map_to_extraction,
    mapped_field_confidence,
    route_structured,
    source_ref_for,
    structured_authority,
    structured_fields_of,
    structured_source_index,
    structured_validation_stage,
)
from genios_engine.capture.structured.product_usage import (
    ACCOUNT_TARGET,
    DEFAULT_USAGE_TABLE,
    EVENT_TARGET,
    OCCURRED_TARGET,
    PRODUCT_USAGE_NODE_TYPE,
    VALUE_TARGET,
    product_usage_mapping,
)
from genios_engine.capture.structured.lane import structured_vocabulary
from genios_engine.capture.structured.registry import (FieldMap, StructuredMapping, get_mapping,
                                                       mapping_from_dict)
from genios_engine.capture.validate.schema import (DECLARED_FIELDS,
                                                   SchemaRule, ValidationStage,
                                                   validate_extraction_schema)
from genios_engine.capture.validate.spans import SpanVerdict, verify_span
from genios_engine.contracts.evidence import MAX_QUOTE_CHARS, EvidenceSpan
from genios_engine.contracts.extraction import ExtractionResult
from genios_engine.contracts.source_event import Actor, SourceEvent
from genios_engine.contracts.trace import EventTrace
from genios_engine.contracts.units import DateCertainty, Money

WAVE = "W2"
GATE = "G2"

EVAL_TIME = datetime(2026, 9, 5, 9, 0, tzinfo=timezone.utc)

#: The vocabulary S-3 checks against — THE one, from `capture/semantic/vocabulary.py`, through
#: the lane's own accessor.
#:
#: W2·D4: this used to be six frozensets typed out by hand beside the real ones, which is a lane
#: asserted against an invented vocabulary — it passes forever, because the copy is the thing
#: that gets updated when a word is promoted. The gap that forced the copy (doc 04's profile set
#: has no `structured` member, doc 03 mandates that literal) is closed in `vocabulary.py`, which
#: is where `STRUCTURED_PROFILE`'s own comment said the fix belonged. `ExtractionVocabulary` is
#: still supplied by the caller, because it has no default and will not get one.
VOCABULARY = structured_vocabulary()

#: The doc's own fixture: a HubSpot deal with an amount, a stage, a close date and a contact.
HUBSPOT_DEAL: dict[str, Any] = {
    "id": "deal_9912",
    "dealname": "Chat360 Pilot",
    "dealstage": "contractsent",
    "amount": "84000",
    "deal_currency_code": "USD",
    "closedate": 1795046400000,          # milliseconds, which is what HubSpot states
    "contact_email": ["Priya@Chat360.io", "ops@chat360.io"],
}

GCAL_EVENT: dict[str, Any] = {
    "id": "evt_1",
    "summary": "Chat360 <> GeniOS",
    "start": {"dateTime": "2026-09-10T14:00:00+05:30"},
    "end": {"dateTime": "2026-09-10T15:00:00+05:30"},
    "status": "confirmed",
    "attendees": [{"email": "Priya@Chat360.io", "displayName": "Priya"},
                  {"email": "rohit@genios.ai"}],
}

STRIPE_SUBSCRIPTION: dict[str, Any] = {
    "id": "sub_1", "status": "active", "current_period_end": 1795046400,   # seconds
}

DB_ACCOUNT: dict[str, Any] = {
    "account_id": "acct_7", "plan": "startup", "status": "active", "seats_used": 12,
}


# ---------------------------------------------------------------------------------------------
# Doubles. Both of them raise.
# ---------------------------------------------------------------------------------------------


class ExplodingClassifier:
    """An S2 relevance classifier that detonates if the gate ever consults it.

    The gate slot is a Protocol, so this is a legal classifier in every way except that using it
    is fatal. Counting calls would let a mis-wired fixture pass silently; raising cannot.
    """

    name = "exploding-relevance"

    def classify(self, ctx: GateContext, prepared: Any) -> Any:
        raise AssertionError(
            "the S2 relevance classifier was consulted for a structured event — the bypass "
            "exists precisely so a typed object never reaches a model")


def _explode(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("a model client was constructed or called on the structured lane")


@pytest.fixture
def no_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the process's real model client unusable for the duration of a test.

    `LLMClient` is the single Anthropic seam in this codebase, so breaking its constructor AND
    its call method means any accidental model use inside the lane — a lazy import, a helper
    that reaches for a client, a future edit — fails loudly instead of quietly costing money and
    confidence. Nothing in the structured lane should notice.
    """
    from genios_engine.context.llm import client as llm_client
    monkeypatch.setattr(llm_client.LLMClient, "__init__", _explode, raising=True)
    monkeypatch.setattr(llm_client.LLMClient, "call", _explode, raising=True)


def _extract(mapping_key: tuple[str, str], raw: dict[str, Any], *,
             tz: str = "UTC", locale: str | None = None) -> ExtractionResult:
    mapping = get_mapping(*mapping_key)
    assert mapping is not None, mapping_key
    return map_to_extraction(mapping, raw, eval_time=EVAL_TIME, tz=tz, locale=locale)


def _gate_context(source: str, object_type: str, *, structured: bool = True) -> GateContext:
    event = SourceEvent(
        event_id="evt_g2", org_id="org_1", connection_id="conn_1", source=source,
        object_type=object_type, source_object_id="obj_1",
        dedup_key=f"{source}:{object_type}:obj_1",
        actor=Actor(type="system", email="ops@genios.ai"),
        occurred_at=datetime(2026, 9, 4, tzinfo=timezone.utc))
    # A mutable source with no version stamp parks at S0.5 before the structured branch is
    # reached, which would make these tests assert the wrong stage. Real CRM/DB objects carry
    # one; the fixture says so.
    return GateContext(event=event, is_structured=structured, content_version="v2",
                       raw={"subject": "deal moved", "snippet": "stage change"})


# ---------------------------------------------------------------------------------------------
# ZERO LLM CALLS — the acceptance line that defines the component.
# ---------------------------------------------------------------------------------------------


@pytest.mark.gate
def test_a_hubspot_deal_produces_an_extraction_with_zero_model_calls(no_model: None) -> None:
    """G2's headline: the highest-value object in the system crosses L1 without a model.

    `no_model` has broken the only model client in the process. If any part of the mapping path
    reached for one, this raises rather than returning.
    """
    result = _extract(("hubspot", "deal"), HUBSPOT_DEAL)

    assert isinstance(result, ExtractionResult)
    assert result.input_tokens == 0 and result.output_tokens == 0
    assert result.is_structured_lane is True
    assert result.model_snapshot == "mapping:hubspot.deal.v1"
    assert result.prompt_version == STRUCTURED_PROMPT_VERSION
    assert result.schema_version == STRUCTURED_SCHEMA_VERSION
    assert result.extraction_profile == STRUCTURED_PROFILE


@pytest.mark.gate
def test_the_gate_short_circuits_a_mapped_structured_event_without_the_classifier() -> None:
    """S1.5 routes to the structured lane before S2 exists as a possibility."""
    trace = EventTrace(org_id="org_1", event_id="evt_g2")
    result = run_gate(_gate_context("hubspot", "deal"), trace, relevance=ExplodingClassifier())

    assert result.action == "short_circuit" and result.route == "structured"
    stage = trace.records[-1]
    assert stage.stage == "S1.5" and stage.reason_code == "structured_mapped"
    assert stage.detail["mapping_id"] == "hubspot.deal.v1"


def test_the_no_model_fixture_can_actually_fail(no_model: None) -> None:
    """The second explosive is live too.

    `test_a_hubspot_deal_produces_an_extraction_with_zero_model_calls` is only worth anything if
    a model call under this fixture would actually blow up. This detonates it by hand.
    """
    from genios_engine.context.llm.client import LLMClient

    with pytest.raises(AssertionError, match="model client was constructed"):
        LLMClient(api_key="k", model="m")


def test_the_exploding_classifier_can_actually_fail() -> None:
    """The explosive is live.

    Without this, `test_the_gate_short_circuits_...` would pass just as happily against a
    classifier that had been quietly disconnected from the gate — and a green test that cannot
    go red is a worse signal than no test, because it is believed.
    """
    trace = EventTrace(org_id="org_1", event_id="evt_g2")
    context = _gate_context("gmail", "message", structured=False)
    with pytest.raises(AssertionError, match="relevance classifier was consulted"):
        run_gate(context, trace, relevance=ExplodingClassifier())


# ---------------------------------------------------------------------------------------------
# EVIDENCE — what a verified span MEANS for a typed field (doc 03 step 4).
# ---------------------------------------------------------------------------------------------


LANE_FIXTURES = [
    pytest.param(("hubspot", "deal"), HUBSPOT_DEAL, "UTC", id="hubspot-deal"),
    pytest.param(("gcal", "calendar_event"), GCAL_EVENT, "Asia/Kolkata", id="gcal-event"),
    pytest.param(("stripe", "subscription"), STRIPE_SUBSCRIPTION, "UTC", id="stripe-subscription"),
    pytest.param(("postgres", "public.customer_accounts"), DB_ACCOUNT, "UTC", id="postgres-row"),
]


@pytest.mark.gate
@pytest.mark.parametrize(("mapping_key", "raw", "tz"), LANE_FIXTURES)
def test_every_span_carries_the_checkmark_and_earns_it(
        mapping_key: tuple[str, str], raw: dict[str, Any], tz: str) -> None:
    """Doc 03's "the synthesized evidence span has verified=True", proved the only way that
    means anything: by re-running ALG-08 over the stored span and the published source text.

    Reading `span.verified` alone would assert that this module set a bool. Re-verifying asserts
    that the bool is TRUE OF THE WORLD — that the quote really is at those offsets in text
    anyone else can fetch — which is the entire difference between a receipt and a claim.
    """
    mapping = get_mapping(*mapping_key)
    result = map_to_extraction(mapping, raw, eval_time=EVAL_TIME, tz=tz)
    index = structured_source_index(mapping, raw)

    assert result.all_evidence, "a mapped object with no receipt is not an extraction"
    for span in result.all_evidence:
        assert span.verified is True, span.source_ref
        assert span.source_ref in index, "a span pointing at text nobody publishes is unresolvable"
        verdict, regraded = verify_span(span, index[span.source_ref])
        assert verdict is SpanVerdict.VERIFIED, (span.source_ref, verdict)
        assert regraded == span, "re-verification must reproduce the stored span exactly"


@pytest.mark.gate
@pytest.mark.parametrize(("mapping_key", "raw", "tz"), LANE_FIXTURES)
def test_every_claim_span_is_indexed_in_all_evidence(
        mapping_key: tuple[str, str], raw: dict[str, Any], tz: str) -> None:
    """S-7's invariant, which is what makes ALG-08 able to walk the whole extraction in one
    pass: a span carried by a claim but missing from `all_evidence` is never verified and never
    reported unverified."""
    result = _extract(mapping_key, raw, tz=tz)
    carried = set(result.evidence_from_claims())
    assert carried <= set(result.all_evidence)


def test_a_fabricated_span_does_not_verify_against_the_published_source_text() -> None:
    """The check used above is capable of saying no.

    Same source text, same ref, a quote nobody wrote — and ALG-08 grades it UNVERIFIED and
    strips the checkmark. Without this row, `test_every_span_carries_the_checkmark_and_earns_it`
    would be consistent with `verify_span` returning VERIFIED for anything at all.
    """
    mapping = get_mapping("hubspot", "deal")
    index = structured_source_index(mapping, HUBSPOT_DEAL)
    ref = source_ref_for("hubspot.deal.v1", "amount")
    invented = EvidenceSpan(source_ref=ref, quote="99000", start_offset=0, end_offset=5,
                            verified=True)

    verdict, graded = verify_span(invented, index[ref])

    assert verdict is SpanVerdict.UNVERIFIED
    assert graded.verified is False


@pytest.mark.parametrize(("field_name", "expected"), [
    ("dealname", "structured:hubspot.deal.v1#dealname"),
    ("amount", "structured:hubspot.deal.v1#amount"),
    ("closedate", "structured:hubspot.deal.v1#closedate"),
])
def test_source_ref_is_the_field_path_doc_03_states(field_name: str, expected: str) -> None:
    """``structured:<mapping_id>#<field>`` — the shape `authority.py`'s prefix table already
    ranks at STRUCTURED_SOURCE, so a ref built any other way would silently rank at 0."""
    assert source_ref_for("hubspot.deal.v1", field_name) == expected


def test_the_published_source_text_is_the_field_value_itself() -> None:
    """The lane's coordinate system, stated: a mapped field's spans resolve against that field's
    own rendered value and against nothing else."""
    index = structured_source_index(get_mapping("hubspot", "deal"), HUBSPOT_DEAL)

    assert index[source_ref_for("hubspot.deal.v1", "amount")] == "84000"
    assert index[source_ref_for("hubspot.deal.v1", "dealname")] == "Chat360 Pilot"
    assert index[source_ref_for("hubspot.deal.v1", "closedate")] == "1795046400000"
    assert (index[source_ref_for("hubspot.deal.v1", "contact_email")]
            == "Priya@Chat360.io, ops@chat360.io")


def test_an_over_long_value_is_quoted_within_the_receipt_cap() -> None:
    """`MAX_QUOTE_CHARS` exists so a receipt is checkable at a glance. A 2,000-character CRM
    description still gets a real, exactly-resolving pointer into its first 400 characters —
    not a truncated copy that resolves against nothing."""
    long_text = "x" * 2000
    result = _extract(("gcal", "calendar_event"),
                      {**GCAL_EVENT, "description": long_text}, tz="UTC")
    index = structured_source_index(get_mapping("gcal", "calendar_event"),
                                    {**GCAL_EVENT, "description": long_text})
    ref = source_ref_for("gcal.event.v1", "description")
    span = next(s for s in result.all_evidence if s.source_ref == ref)

    assert len(span.quote) == MAX_QUOTE_CHARS
    assert index[ref] == long_text
    assert verify_span(span, index[ref])[0] is SpanVerdict.VERIFIED


# ---------------------------------------------------------------------------------------------
# S-9 — the cross-wave interaction with W1's "the extractor may not stamp its own receipt".
# ---------------------------------------------------------------------------------------------


@pytest.mark.gate
def test_the_extraction_conforms_at_the_stage_this_lane_declares() -> None:
    """`POST_VERIFICATION` is not a loophole here, it is a true statement: ALG-08 has run on
    every span this lane emits, so the checkmark is L1.5.1's signature and S-9 has nothing left
    to protect."""
    result = _extract(("hubspot", "deal"), HUBSPOT_DEAL)

    assert structured_validation_stage() is ValidationStage.POST_VERIFICATION
    report = validate_extraction_schema(result, vocabulary=VOCABULARY,
                                        stage=structured_validation_stage())
    assert report.conforms, report.violations


@pytest.mark.gate
def test_s9_still_fires_on_the_same_object_at_the_arrival_stage() -> None:
    """The rule is untouched and still fail-closed.

    This pins the decision rather than merely benefiting from it: the same extraction validated
    at `EXTRACTOR_OUTPUT` is refused, and refused for S-9 alone. If a later wave loosened S-9
    globally to make the structured lane fit, this row goes red — which is the alarm that a
    stage-scoped rule has quietly become an unscoped one.
    """
    result = _extract(("hubspot", "deal"), HUBSPOT_DEAL)

    report = validate_extraction_schema(result, vocabulary=VOCABULARY,
                                        stage=ValidationStage.EXTRACTOR_OUTPUT)
    assert not report.conforms
    assert report.failed_rules == (SchemaRule.S9,)


# ---------------------------------------------------------------------------------------------
# CONFIDENCE and AUTHORITY — doc 03 steps 5 and 6.
# ---------------------------------------------------------------------------------------------


@pytest.mark.gate
@pytest.mark.parametrize(("mapping_key", "raw", "targets"), [
    pytest.param(("hubspot", "deal"), HUBSPOT_DEAL,
                 ("deal.title", "deal.stage", "deal.amount", "deal.close_date"), id="deal"),
    pytest.param(("stripe", "subscription"), STRIPE_SUBSCRIPTION,
                 ("subscription.status", "subscription.current_period_end"), id="subscription"),
    pytest.param(("postgres", "public.customer_accounts"), DB_ACCOUNT,
                 ("product_account.plan", "product_account.status",
                  "product_account.seats_used"), id="db-row"),
])
def test_every_mapped_field_is_at_full_confidence(mapping_key: tuple[str, str],
                                                  raw: dict[str, Any],
                                                  targets: tuple[str, ...]) -> None:
    """Doc 03 step 5, in the keys doc 03 uses. A typed field is not a guess, and 8000 would let
    a model's opinion about the same fact outrank the column it was read from."""
    stated = mapped_field_confidence(get_mapping(*mapping_key), raw)

    assert set(stated) == set(targets)
    assert set(stated.values()) == {STRUCTURED_FIELD_CONFIDENCE_BP}
    assert STRUCTURED_FIELD_CONFIDENCE_BP == 10_000
    assert all(isinstance(bp, int) and not isinstance(bp, bool) for bp in stated.values())


def test_an_absent_column_is_omitted_from_confidence_rather_than_zeroed() -> None:
    """Zero basis points says "we looked and believe nothing". A column that never arrived is a
    different fact and belongs in `absent_fields`, not in the confidence map at a score."""
    partial = {k: v for k, v in HUBSPOT_DEAL.items() if k != "closedate"}
    mapping = get_mapping("hubspot", "deal")

    stated = mapped_field_confidence(mapping, partial)

    assert "deal.close_date" not in stated
    assert absent_fields(mapping, partial) == ("closedate",)


def test_result_field_confidence_uses_keys_the_schema_validator_accepts() -> None:
    """The cross-wave resolution, pinned.

    W1's S-3 refuses a `field_confidence` key that is not a field of `ExtractionResult`, so the
    contract-level map is keyed by result field and the per-target view lives in
    `mapped_field_confidence`. `stance` is deliberately absent: this lane always emits
    `neutral`, but that is OUR convention rather than something the source stated, and claiming
    10000 in our own convention is the one place this map could become a lie.
    """
    result = _extract(("hubspot", "deal"), HUBSPOT_DEAL)

    assert set(result.field_confidence) <= set(DECLARED_FIELDS)
    assert result.field_confidence["amounts"] == STRUCTURED_FIELD_CONFIDENCE_BP
    assert result.field_confidence["dates_mentioned"] == STRUCTURED_FIELD_CONFIDENCE_BP
    assert result.field_confidence["entity_mentions"] == STRUCTURED_FIELD_CONFIDENCE_BP
    assert result.field_confidence["intent"] == STRUCTURED_FIELD_CONFIDENCE_BP
    assert "stance" not in result.field_confidence


@pytest.mark.gate
@pytest.mark.parametrize(("source", "object_type"), [
    ("hubspot", "deal"), ("gcal", "calendar_event"),
    ("stripe", "subscription"), ("postgres", "public.customer_accounts"),
])
def test_a_structured_object_ranks_at_authority_four(source: str, object_type: str) -> None:
    """Doc 03 step 6 — above email prose (2) and attachments (3), below canon (5) and a signed
    document (6). Read off ALG-14's own cascade, not a literal, so re-tuning the ladder moves
    this and the conflict resolver together."""
    weight = structured_authority(source, object_type)

    assert weight.rank == 4
    assert weight.recognised is True


# ---------------------------------------------------------------------------------------------
# NORMALIZE — money through ALG-10 (doc 03 step 3). One row per stated condition.
# ---------------------------------------------------------------------------------------------


def _money_mapping(field_map: FieldMap) -> StructuredMapping:
    return StructuredMapping(
        mapping_id="test.money.v1", source="hubspot", object_type="deal",
        identity_field="id", node_type="deal", fields=[field_map], intent="pipeline_update")


MONEY_ROWS = [
    pytest.param({"amount": "84000", "cur": "USD"}, None, 8_400_000, "USD", "84000",
                 id="string-integer-dollars"),
    pytest.param({"amount": 84000, "cur": "USD"}, None, 8_400_000, "USD", "84000",
                 id="int-column"),
    pytest.param({"amount": 84000.5, "cur": "USD"}, None, 8_400_050, "USD", "84000.5",
                 id="float-column-normalised-in-integers"),
    pytest.param({"amount": "84000", "cur": "JPY"}, None, 84_000, "JPY", "84000",
                 id="zero-exponent-currency"),
    pytest.param({"amount": "25000.50", "cur": "INR"}, None, 2_500_050, "INR", "25000.50",
                 id="decimals"),
    pytest.param({"amount": "$84,000", "cur": "USD"}, "en-US", 8_400_000, "USD", "$84,000",
                 id="literal-carries-its-own-symbol"),
]


@pytest.mark.parametrize(("raw", "locale", "minor_units", "currency", "as_written"), MONEY_ROWS)
def test_a_typed_amount_is_normalised_by_alg_10(raw: dict[str, Any], locale: str | None,
                                                minor_units: int, currency: str,
                                                as_written: str) -> None:
    """Integer minor units plus the declared ISO code, with the SOURCE's literal retained.

    `as_written` is the source's bytes and never our prefixed form: the whole point of the field
    is that a human can see what was actually written next to what we made of it.
    """
    mapping = _money_mapping(FieldMap("amount", "deal.amount", "money", currency_field="cur"))

    result = map_to_extraction(mapping, raw, eval_time=EVAL_TIME, locale=locale)

    assert result.amounts == [Money(minor_units=minor_units, currency=currency,
                                    as_written=as_written)]
    assert isinstance(result.amounts[0].minor_units, int)


def test_a_fixed_currency_mapping_needs_no_currency_column() -> None:
    """A single-settlement-currency source states the code once, in the mapping."""
    mapping = _money_mapping(FieldMap("amount", "deal.amount", "money", currency="EUR"))

    result = map_to_extraction(mapping, {"amount": "1200"}, eval_time=EVAL_TIME)

    assert result.amounts == [Money(minor_units=120_000, currency="EUR", as_written="1200")]


MONEY_REFUSALS = [
    pytest.param({"amount": "84000"}, "currency column and this object carries no value",
                 id="currency-column-empty"),
    pytest.param({"amount": "84000", "cur": ""}, "carries no value",
                 id="currency-column-blank"),
    pytest.param({"amount": "not a number", "cur": "USD"}, "ALG-10 refused",
                 id="unparseable-literal"),
    pytest.param({"amount": "€84000", "cur": "USD"}, "one of the two is wrong",
                 id="literal-contradicts-the-declared-currency"),
]


@pytest.mark.parametrize(("raw", "message"), MONEY_REFUSALS)
def test_an_amount_that_cannot_be_normalised_raises_rather_than_writing_null(
        raw: dict[str, Any], message: str) -> None:
    """Doc 03: "a field that maps to nothing raises rather than writing null", and the money
    row of its failure table: "no default".

    A null here is the silent version of every one of these bugs, and each of them would ship a
    number at `field_confidence == 10000`.
    """
    mapping = _money_mapping(FieldMap("amount", "deal.amount", "money", currency_field="cur"))

    with pytest.raises(StructuredMappingError, match=message):
        map_to_extraction(mapping, raw, eval_time=EVAL_TIME)


FIELD_MAP_REFUSALS = [
    pytest.param({"value_type": "money"}, "exactly one of currency_field or currency",
                 id="money-declares-no-currency"),
    pytest.param({"value_type": "money", "currency": "USD", "currency_field": "cur"},
                 "exactly one of currency_field or currency", id="money-declares-both"),
    pytest.param({"value_type": "number", "currency": "USD"},
                 "only a money field carries one", id="non-money-declares-a-currency"),
    pytest.param({"value_type": "decimal"}, "unknown value_type", id="unknown-value-type"),
]


@pytest.mark.parametrize(("kwargs", "message"), FIELD_MAP_REFUSALS)
def test_a_malformed_field_map_is_refused_at_construction(kwargs: dict[str, Any],
                                                          message: str) -> None:
    """The mapping is data, and a data error caught at import time is one nobody debugs at 2am
    from a wrong number on a card."""
    with pytest.raises(ValueError, match=message):
        FieldMap("amount", "deal.amount", **kwargs)


def test_the_config_surface_carries_the_currency_declaration_too() -> None:
    """A tenant mapping their own billing table gets the same guard, because
    `mapping_from_dict` builds the same `FieldMap`."""
    mapping = mapping_from_dict({
        "mapping_id": "acme.invoice.v1", "source": "postgres",
        "object_type": "public.acme_invoices", "identity_field": "id", "node_type": "invoice",
        "intent": "invoice_event",
        "fields": [{"source_field": "total_cents", "target": "invoice.total",
                    "value_type": "money", "currency": "INR"}]})

    result = map_to_extraction(mapping, {"total_cents": "25000"}, eval_time=EVAL_TIME)

    assert result.amounts == [Money(minor_units=2_500_000, currency="INR", as_written="25000")]


# ---------------------------------------------------------------------------------------------
# NORMALIZE — dates through ALG-09 (doc 03 step 3).
# ---------------------------------------------------------------------------------------------


def _date_mapping() -> StructuredMapping:
    return StructuredMapping(
        mapping_id="test.date.v1", source="hubspot", object_type="deal", identity_field="id",
        node_type="deal", fields=[FieldMap("when", "deal.close_date", "timestamp")],
        intent="pipeline_update")


DATE_ROWS = [
    pytest.param(1795046400000, "UTC", date(2026, 11, 19), id="epoch-milliseconds"),
    pytest.param(1795046400, "UTC", date(2026, 11, 19), id="epoch-seconds"),
    pytest.param("1795046400000", "UTC", date(2026, 11, 19), id="epoch-as-a-string"),
    pytest.param("2026-11-30", "UTC", date(2026, 11, 30), id="iso-date"),
    pytest.param("2026-11-30T09:15:00+00:00", "UTC", date(2026, 11, 30), id="iso-datetime"),
    pytest.param("2026-11-30T09:15:00Z", "UTC", date(2026, 11, 30), id="iso-zulu"),
    pytest.param(datetime(2026, 11, 30, 9, 15, tzinfo=timezone.utc), "UTC", date(2026, 11, 30),
                 id="aware-datetime-object"),
    pytest.param(date(2026, 11, 30), "UTC", date(2026, 11, 30), id="date-object"),
    pytest.param({"dateTime": "2026-09-10T14:00:00+05:30"}, "Asia/Kolkata", date(2026, 9, 10),
                 id="google-calendar-timed-envelope"),
    pytest.param({"date": "2026-09-10"}, "UTC", date(2026, 9, 10), id="google-calendar-all-day"),
]


@pytest.mark.parametrize(("raw_value", "tz", "expected_day"), DATE_ROWS)
def test_a_typed_timestamp_resolves_to_the_day_it_denotes(raw_value: Any, tz: str,
                                                          expected_day: date) -> None:
    """Every shape a real structured source emits lands on the same calendar day, through the
    SAME ALG-09 the prose path uses — so a CRM close date and a "by the 30th" in an email are
    the same kind of object by the time anything reads them."""
    result = map_to_extraction(_date_mapping(), {"when": raw_value},
                               eval_time=EVAL_TIME, tz=tz)

    assert len(result.dates_mentioned) == 1
    resolved = result.dates_mentioned[0]
    assert resolved.certainty is DateCertainty.EXACT
    assert resolved.as_written == expected_day.isoformat()
    assert resolved.evidence and resolved.evidence[0].verified is True


def test_the_org_timezone_decides_which_calendar_day_a_deadline_falls_on() -> None:
    """2026-11-30T19:30Z is 30 November in London and 1 December in Delhi. A deadline on the
    wrong day is a card that fires late, and UTC-by-default is how that happens silently."""
    raw = {"when": "2026-11-30T19:30:00+00:00"}

    in_london = map_to_extraction(_date_mapping(), raw, eval_time=EVAL_TIME, tz="Europe/London")
    in_delhi = map_to_extraction(_date_mapping(), raw, eval_time=EVAL_TIME, tz="Asia/Kolkata")

    assert in_london.dates_mentioned[0].as_written == "2026-11-30"
    assert in_delhi.dates_mentioned[0].as_written == "2026-12-01"


def test_the_resolution_is_pinned_to_the_caller_s_clock_not_to_now() -> None:
    """`resolved_against` is what makes a replay of a March object resolve against March. The
    module reads no clock; `eval_time` is the only one there is."""
    result = map_to_extraction(_date_mapping(), {"when": "2026-11-30"},
                               eval_time=EVAL_TIME, tz="UTC")

    assert result.dates_mentioned[0].resolved_against == EVAL_TIME


DATE_REFUSALS = [
    pytest.param(datetime(2026, 11, 30, 9, 15), "naive datetime", id="naive-datetime-object"),
    pytest.param("2026-11-30T09:15:00", "states no offset", id="iso-string-with-no-offset"),
    pytest.param("next quarter maybe", "is not an ISO-8601 timestamp", id="prose-in-a-typed-column"),
    pytest.param(True, "is not a timestamp", id="boolean-in-a-timestamp-column"),
    pytest.param(["2026-11-30"], "cannot read a timestamp out of list",
                 id="list-in-a-timestamp-column"),
]


@pytest.mark.parametrize(("raw_value", "message"), DATE_REFUSALS)
def test_a_timestamp_that_cannot_be_placed_on_a_calendar_raises(raw_value: Any,
                                                                message: str) -> None:
    """Each of these written as a null is a deadline that quietly disappears, or one that lands
    on the wrong day because a silent offset was assumed to be UTC."""
    with pytest.raises(StructuredMappingError, match=message):
        map_to_extraction(_date_mapping(), {"when": raw_value}, eval_time=EVAL_TIME, tz="UTC")


def test_an_unknown_timezone_raises_rather_than_defaulting_to_utc() -> None:
    with pytest.raises(StructuredMappingError, match="unknown timezone"):
        map_to_extraction(_date_mapping(), {"when": "2026-11-30"},
                          eval_time=EVAL_TIME, tz="Mars/Olympus")


# ---------------------------------------------------------------------------------------------
# ABSENCE vs SCHEMA DRIFT — doc 03's first failure mode.
# ---------------------------------------------------------------------------------------------


ABSENCE_ROWS = [
    pytest.param({}, id="key-missing"),
    pytest.param({"closedate": None}, id="explicit-null"),
    pytest.param({"closedate": ""}, id="empty-string"),
    pytest.param({"closedate": "   "}, id="whitespace-only"),
]


@pytest.mark.parametrize("override", ABSENCE_ROWS)
def test_an_absent_field_is_skipped_and_never_fabricated(override: dict[str, Any]) -> None:
    """An open deal has no close date, and refusing the whole object over it would drop the
    pipeline this lane exists to carry. What must not happen is a `ResolvedDate` appearing for a
    column that said nothing."""
    raw = {k: v for k, v in HUBSPOT_DEAL.items() if k != "closedate"} | override

    result = map_to_extraction(get_mapping("hubspot", "deal"), raw, eval_time=EVAL_TIME)

    assert result.dates_mentioned == []
    assert "deal.close_date" not in mapped_field_confidence(get_mapping("hubspot", "deal"), raw)
    assert "closedate" in absent_fields(get_mapping("hubspot", "deal"), raw)


def test_an_object_matching_none_of_its_mapping_s_fields_is_schema_drift() -> None:
    """The total case is different from the partial one and is refused.

    A provider that renames its properties produces objects like this — full of data, none of it
    where the mapping looks — and emitting an empty extraction would report a live pipeline as a
    quiet one, at full confidence, for as long as nobody checked.
    """
    with pytest.raises(StructuredMappingError, match="drifted from the provider's schema"):
        map_to_extraction(get_mapping("hubspot", "deal"),
                          {"deal_name_v2": "Pilot", "amount_v2": "84000"}, eval_time=EVAL_TIME)


def test_an_empty_object_is_not_drift() -> None:
    """Nothing arrived, so nothing can have moved. There is no evidence of a rename here and
    inventing one would make every empty sync page look like a provider outage."""
    result = map_to_extraction(get_mapping("hubspot", "deal"), {}, eval_time=EVAL_TIME)

    assert result.all_evidence == []
    assert result.amounts == [] and result.dates_mentioned == []


# ---------------------------------------------------------------------------------------------
# RELATIONS — the cross-tool bridge, expressed as claims.
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("mapping_key", "raw", "surfaces", "canonicals"), [
    pytest.param(("hubspot", "deal"), HUBSPOT_DEAL,
                 ["Priya@Chat360.io", "ops@chat360.io"],
                 ["priya@chat360.io", "ops@chat360.io"], id="crm-contacts"),
    pytest.param(("gcal", "calendar_event"), GCAL_EVENT,
                 ["Priya@Chat360.io", "rohit@genios.ai"],
                 ["priya@chat360.io", "rohit@genios.ai"], id="calendar-attendees"),
])
def test_declared_relations_become_entity_mentions_with_merge_keys(
        mapping_key: tuple[str, str], raw: dict[str, Any], surfaces: list[str],
        canonicals: list[str]) -> None:
    """The receipt quotes what the source WROTE; `canonical_hint` is the merge key.

    Keeping the two separate is what lets a CRM contact and a calendar attendee become one
    person while each still points at its own source's spelling.
    """
    result = _extract(mapping_key, raw, tz="UTC")

    assert [m.surface_form for m in result.entity_mentions] == surfaces
    assert [m.canonical_hint for m in result.entity_mentions] == canonicals
    assert {m.entity_type for m in result.entity_mentions} == {"person"}
    assert {m.confidence_bp for m in result.entity_mentions} == {STRUCTURED_FIELD_CONFIDENCE_BP}


def test_a_plus_tagged_address_merges_but_is_quoted_as_written() -> None:
    """`norm_email` strips the +tag for identity. The span must not: a receipt that quotes a
    string the source never contained cannot be found in it."""
    raw = {**GCAL_EVENT, "attendees": [{"email": "Priya+cal@Chat360.io"}]}

    result = _extract(("gcal", "calendar_event"), raw, tz="UTC")

    mention = result.entity_mentions[0]
    assert mention.surface_form == "Priya+cal@Chat360.io"
    assert mention.canonical_hint == "priya@chat360.io"
    assert mention.evidence[0].quote == "Priya+cal@Chat360.io"


def test_the_same_person_named_twice_is_one_mention() -> None:
    """Two spellings of one address is one person, and two mentions would double their weight
    in every count downstream."""
    raw = {**GCAL_EVENT,
           "attendees": [{"email": "Priya@Chat360.io"}, {"email": "priya+x@chat360.io"}]}

    result = _extract(("gcal", "calendar_event"), raw, tz="UTC")

    assert [m.canonical_hint for m in result.entity_mentions] == ["priya@chat360.io"]


def test_an_absent_relation_field_is_a_no_op() -> None:
    """A deal with no contact on it is a deal, not an error."""
    raw = {k: v for k, v in HUBSPOT_DEAL.items() if k != "contact_email"}

    result = map_to_extraction(get_mapping("hubspot", "deal"), raw, eval_time=EVAL_TIME)

    assert result.entity_mentions == []


# ---------------------------------------------------------------------------------------------
# LANE CONVERGENCE and determinism.
# ---------------------------------------------------------------------------------------------


@pytest.mark.gate
def test_the_two_lanes_are_indistinguishable_to_everything_downstream() -> None:
    """Doc 03's routing rule: "FROM S3 ONWARD nothing may branch on whether the ExtractionResult
    came from a model or a mapping."

    Same type, same declared fields, same validator, same verdict. The one field that differs is
    the token count, which `is_structured_lane` reads for cost attribution and which the
    contract explicitly forbids branching behaviour on.

    NOT asserted here: that the two produce an identical `importance_bp`. That is ALG-17 at W7
    (L1.6.7); `ExtractionResult` refuses the field by construction today, so the criterion is
    unsatisfiable at G2 and is a G7 one. Faking it would be worse than deferring it.
    """
    structured = _extract(("hubspot", "deal"), HUBSPOT_DEAL)
    quote = "the pilot lands at $84,000 and closes on 30 November"
    span = verify_span(EvidenceSpan(source_ref="prepared_content:evt_1", quote=quote,
                                    start_offset=0, end_offset=len(quote)), quote)[1]
    semantic = ExtractionResult(
        intent="inform", stance="neutral", topics=["stage_change"],
        amounts=[Money(minor_units=8_400_000, currency="USD", as_written="$84,000")],
        all_evidence=[span], field_confidence={"amounts": 8_700},
        model_snapshot="claude-haiku-4-5-20251001", prompt_version="p7",
        schema_version=STRUCTURED_SCHEMA_VERSION, extraction_profile="email",
        input_tokens=1_200, output_tokens=310)

    assert type(structured) is type(semantic)
    assert set(structured.model_dump()) == set(semantic.model_dump())
    for candidate in (structured, semantic):
        assert validate_extraction_schema(
            candidate, vocabulary=VOCABULARY,
            stage=ValidationStage.POST_VERIFICATION).conforms
    assert structured.is_structured_lane is True
    assert semantic.is_structured_lane is False


@pytest.mark.parametrize(("mapping_key", "raw", "tz"), LANE_FIXTURES)
def test_the_same_object_and_clock_produce_a_byte_identical_extraction(
        mapping_key: tuple[str, str], raw: dict[str, Any], tz: str) -> None:
    """Replay determinism. No clock is read, no dict order leaks, no float is renormalised —
    so a decision made in March reproduces in September."""
    first = _extract(mapping_key, raw, tz=tz)
    second = _extract(mapping_key, raw, tz=tz)

    assert first.model_dump() == second.model_dump()


def test_the_mapping_intent_is_translated_into_the_closed_contract_set() -> None:
    """The registry's intent is Layer 2's emission vocabulary; the contract's is doc 04's closed
    set. A calendar move is a `schedule`; a system of record otherwise STATES things."""
    assert _extract(("gcal", "calendar_event"), GCAL_EVENT, tz="UTC").intent == "schedule"
    assert _extract(("hubspot", "deal"), HUBSPOT_DEAL).intent == DEFAULT_STRUCTURED_INTENT
    assert _extract(("stripe", "subscription"), STRIPE_SUBSCRIPTION).intent == "inform"
    assert _extract(("hubspot", "deal"), HUBSPOT_DEAL).stance == STRUCTURED_STANCE


def test_the_value_projection_the_shipped_lane_reads_is_unchanged() -> None:
    """`apply_mapping` is the half that carries the VALUES and L2's `commit_structured` already
    reads it. This lane adds receipts and normalised dimensioned values beside it; it does not
    replace it, and a second projection would be a second thing to keep in step."""
    projected = structured_fields_of(get_mapping("hubspot", "deal"), HUBSPOT_DEAL)

    assert projected["deal.stage"] == "contractsent"
    assert projected["deal.amount"] == "84000"
    assert projected["deal.title"] == "Chat360 Pilot"


# ---------------------------------------------------------------------------------------------
# ROUTING and the `unmapped_structured` metric.
# ---------------------------------------------------------------------------------------------


ROUTE_ROWS = [
    pytest.param("hubspot", "deal", "hubspot.deal.v1", 0, id="registered-crm-object"),
    pytest.param("gcal", "calendar_event", "gcal.event.v1", 0, id="registered-calendar-event"),
    pytest.param("postgres", DEFAULT_USAGE_TABLE, "postgres.product_usage_events.v1", 0,
                 id="registered-usage-table"),
    pytest.param("hubspot", "ticket", None, 1, id="unmapped-object-type"),
    pytest.param("postgres", "public.orders", None, 1, id="unmapped-client-table"),
]


@pytest.mark.parametrize(("source", "object_type", "mapping_id", "unmapped"), ROUTE_ROWS)
def test_route_structured_answers_and_counts(source: str, object_type: str,
                                             mapping_id: str | None, unmapped: int) -> None:
    """The lookup and doc 03's metric in one typed answer, so the negative case is countable
    without every call site remembering to count it."""
    route = route_structured(source, object_type)

    assert (route.mapping.mapping_id if route.mapping else None) == mapping_id
    assert route.mapped is (mapping_id is not None)
    assert route.unmapped_structured == unmapped


@pytest.mark.gate
def test_gate_parks_an_unmapped_structured_source_and_counts_it() -> None:
    """DIVERGENCE FROM DOC 03, asserted rather than hidden.

    Doc 03's failure table says an unregistered structured source falls to `needs_extraction`
    and a model runs over raw JSON. The shipped gate PARKS instead, and this test pins that:
    parking is free and recoverable, `parked/drain.py` re-drains `mapping_missing` the moment a
    mapping is registered, and the object then takes the bypass it was always entitled to
    instead of paying for a model call at model confidence. The METRIC doc 03 asked for is the
    half worth keeping, and it rides the trace.
    """
    trace = EventTrace(org_id="org_1", event_id="evt_g2")

    result = run_gate(_gate_context("postgres", "public.orders"), trace,
                      relevance=ExplodingClassifier())

    assert result.action == "park" and result.reason_code == "mapping_missing"
    stage = trace.records[-1]
    assert stage.stage == "S1.5"
    assert stage.detail["unmapped_structured"] == 1


# ---------------------------------------------------------------------------------------------
# L1.3.9-U2 · mapping coverage.
# ---------------------------------------------------------------------------------------------


def test_a_fully_mapped_connection_reports_complete_coverage() -> None:
    report = mapping_coverage([ConnectedObject("hubspot"), ConnectedObject("gcal")])

    assert report.unmapped == ()
    assert report.unmapped_structured == 0
    assert report.coverage_bp == BP_FULL
    assert {row.mapping_id for row in report.mapped} == {"hubspot.deal.v1", "gcal.event.v1"}


def test_an_unmapped_client_table_is_the_actionable_row() -> None:
    """The case the metric exists for: a connected structured object type that will pay for a
    model call it did not need on every sync until somebody writes four lines of mapping."""
    report = mapping_coverage([ConnectedObject("hubspot"),
                               ConnectedObject("postgres", "public.orders")])

    assert [(row.source, row.object_type) for row in report.unmapped] == [
        ("postgres", "public.orders")]
    assert report.unmapped_structured == 1
    assert report.coverage_bp == 5_000


def test_a_source_whose_tables_are_the_tenant_s_is_reported_as_unenumerated() -> None:
    """Three states, not two. `postgres` declares no object types because they belong to the
    customer, so counting it as unmapped would invent a gap and counting it as mapped would hide
    one — and neither belongs in a coverage ratio."""
    report = mapping_coverage([ConnectedObject("postgres")])

    assert [row.source for row in report.unenumerated] == ["postgres"]
    assert report.unmapped_structured == 0
    assert report.coverage_bp == BP_FULL


@pytest.mark.parametrize(("source", "structured"), [
    pytest.param("hubspot", True, id="crm-is-structured"),
    pytest.param("stripe", True, id="billing-is-structured"),
    pytest.param("gmail", False, id="mail-is-not"),
    pytest.param("slack", False, id="chat-is-not"),
])
def test_only_structured_sources_are_assessed_for_a_mapping(source: str,
                                                            structured: bool) -> None:
    """"Structured" is asked of ALG-14's own tables rather than of a private list here, so a
    source cannot be ranked at authority 4 while being reported as unstructured."""
    report = mapping_coverage([ConnectedObject(source)])

    assert all(row.structured is structured for row in report.rows), report.rows


def test_the_same_source_connected_twice_is_counted_once() -> None:
    """A caller assembling this from a connections table will hand duplicates; a count has to be
    a count of object types, not of connection rows."""
    report = mapping_coverage([ConnectedObject("postgres", "public.orders"),
                               ConnectedObject("postgres", "public.orders")])

    assert len(report.rows) == 1
    assert report.unmapped_structured == 1


def test_no_connections_is_full_coverage_not_zero() -> None:
    """Nothing is uncovered, so a red dashboard would be describing a tenant who has done
    nothing wrong."""
    report = mapping_coverage([])

    assert report.rows == () and report.coverage_bp == BP_FULL


def test_a_blank_source_is_ignored_rather_than_assessed() -> None:
    assert mapping_coverage([ConnectedObject("  "), ConnectedObject("")]).rows == ()


# ---------------------------------------------------------------------------------------------
# L1.3.9-U3 · product-usage event intake.
# ---------------------------------------------------------------------------------------------


USAGE_EVENT: dict[str, Any] = {
    "id": "u_1", "event_name": "report_exported", "account_id": "acct_7",
    "occurred_at": "2026-09-04T11:02:00+00:00", "quantity": 3,
    "user_email": "Priya@Chat360.io",
}


def test_the_built_in_usage_mapping_is_registered_on_the_product_usage_source() -> None:
    """L1.1's P2 source, carried by the lane that already exists. `postgres` is buildable and
    declares `product_usage`; `connectors/database.py` reads it off a watermark."""
    mapping = get_mapping("postgres", DEFAULT_USAGE_TABLE)

    assert mapping is not None
    assert mapping.mapping_id == "postgres.product_usage_events.v1"
    assert mapping.node_type == PRODUCT_USAGE_NODE_TYPE
    assert [f.target for f in mapping.fields] == [EVENT_TARGET, ACCOUNT_TARGET,
                                                  OCCURRED_TARGET, VALUE_TARGET]


@pytest.mark.gate
def test_a_usage_event_crosses_the_lane_with_no_model_and_full_confidence(
        no_model: None) -> None:
    """Usage data is the missing half of every churn signal, and it is structured by nature —
    so it takes the bypass like every other typed object."""
    mapping = get_mapping("postgres", DEFAULT_USAGE_TABLE)

    result = map_to_extraction(mapping, USAGE_EVENT, eval_time=EVAL_TIME, tz="UTC")

    assert result.is_structured_lane is True
    assert result.dates_mentioned[0].as_written == "2026-09-04"
    assert [m.canonical_hint for m in result.entity_mentions] == ["priya@chat360.io"]
    assert set(mapped_field_confidence(mapping, USAGE_EVENT).values()) == {
        STRUCTURED_FIELD_CONFIDENCE_BP}
    assert validate_extraction_schema(result, vocabulary=VOCABULARY,
                                      stage=structured_validation_stage()).conforms


def test_a_usage_quantity_is_a_number_unless_the_tenant_declares_a_currency() -> None:
    """Seats and API calls are counts. Usage-BASED BILLING is money, and then it goes through
    ALG-10 like every other amount — which is only possible because the tenant said so."""
    counted = product_usage_mapping(
        source="postgres", object_type="public.usage", identity_field="id",
        event_field="event_name", account_field="account_id", occurred_field="occurred_at",
        value_field="quantity")
    billed = product_usage_mapping(
        source="postgres", object_type="public.usage_billed", identity_field="id",
        event_field="event_name", account_field="account_id", occurred_field="occurred_at",
        value_field="amount", value_currency="INR")

    assert counted.fields[-1].value_type == "number"
    assert counted.fields[-1].authority == "direct_observation"
    assert billed.fields[-1].value_type == "money" and billed.fields[-1].currency == "INR"

    result = map_to_extraction(billed, {"event_name": "overage", "account_id": "a",
                                        "occurred_at": "2026-09-04", "amount": "2500"},
                               eval_time=EVAL_TIME)
    assert result.amounts == [Money(minor_units=250_000, currency="INR", as_written="2500")]


USAGE_GUARD_ROWS = [
    pytest.param("gmail", "declares capability 'communication'", id="mail-source"),
    pytest.param("hubspot", "declares capability 'crm'", id="crm-source"),
    pytest.param("nowhere", "is not in the source registry", id="undescribed-source"),
]


@pytest.mark.parametrize(("source", "message"), USAGE_GUARD_ROWS)
def test_a_usage_mapping_over_a_non_usage_source_is_refused(source: str, message: str) -> None:
    """A churn cohort assembled from mail metadata labelled as usage is worse than an empty
    one: it is a wrong answer wearing a confidence of 10000."""
    with pytest.raises(ValueError, match=message):
        product_usage_mapping(source=source, object_type="x", identity_field="id",
                              event_field="e", account_field="a", occurred_field="o")


def test_the_usage_mapping_is_configuration_and_round_trips_through_the_config_surface() -> None:
    """Doc 03-U3: "this is a configuration surface, not a new subsystem". A tenant whose columns
    are named differently describes them; nothing here is code."""
    built = product_usage_mapping(
        source="postgres", object_type="public.events_v2", identity_field="row_id",
        event_field="verb", account_field="tenant", occurred_field="ts",
        user_email_field="actor_email", mapping_id="acme.usage.v1")

    result = map_to_extraction(built, {"row_id": 1, "verb": "login", "tenant": "acct_7",
                                       "ts": 1788000000, "actor_email": "ops@chat360.io"},
                               eval_time=EVAL_TIME, tz="UTC")

    assert built.mapping_id == "acme.usage.v1"
    assert result.model_snapshot == "mapping:acme.usage.v1"
    assert [m.canonical_hint for m in result.entity_mentions] == ["ops@chat360.io"]
    assert result.dates_mentioned[0].as_written == "2026-08-29"
