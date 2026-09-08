from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.context.correlation_resource import (
    ContractResource,
    SpendAttribution,
    SpendCoverage,
    SpendEvent,
    SpendFinding,
    correlate_contract_spend,
    summarize_contract_spend,
)


NOW = datetime(2026, 9, 7, tzinfo=timezone.utc)


def contract(**changes) -> ContractResource:
    fields = dict(contract_id="ctr_1", vendor_node_id="vendor_1",
                  starts_at=NOW - timedelta(days=30), ends_at=NOW + timedelta(days=30),
                  committed_minor_units=1_000_000, currency="USD")
    fields.update(changes)
    return ContractResource(**fields)


def spend(**changes) -> SpendEvent:
    fields = dict(spend_id="sp_1", vendor_node_id="vendor_1", occurred_at=NOW,
                  minor_units=10_000, currency="USD")
    fields.update(changes)
    return SpendEvent(**fields)


def test_explicit_reference_is_exact():
    link = correlate_contract_spend([contract()], [spend(contract_ref="ctr_1")],
                                    eval_time=NOW)[0]
    assert link.attribution is SpendAttribution.EXACT
    assert link.contract_id == "ctr_1" and link.counts_toward_spend


def test_unique_vendor_and_term_is_strong():
    link = correlate_contract_spend([contract()], [spend()], eval_time=NOW)[0]
    assert link.attribution is SpendAttribution.STRONG
    assert link.contract_id == "ctr_1"


def test_outside_term_is_unattributed_and_never_counted_as_spent():
    item = spend(occurred_at=NOW - timedelta(days=60))
    link = correlate_contract_spend([contract()], [item], eval_time=NOW)[0]
    summary = summarize_contract_spend([contract()], [link], spend_coverage_ready=True)[0]
    assert link.attribution is SpendAttribution.UNATTRIBUTED
    assert not link.counts_toward_spend
    assert summary.spent_minor_units == 0
    assert summary.unattributed_minor_units == item.minor_units


def test_missing_spend_coverage_is_unknown_not_zero():
    summary = summarize_contract_spend([contract()], [], spend_coverage_ready=None)[0]
    assert summary.coverage is SpendCoverage.UNKNOWN
    assert summary.spent_minor_units is None and summary.unattributed_minor_units is None


def test_post_cancellation_spend_is_a_separate_finding():
    agreement = contract(cancelled_at=NOW - timedelta(days=2))
    link = correlate_contract_spend([agreement], [spend(contract_ref="ctr_1")],
                                    eval_time=NOW)[0]
    assert SpendFinding.SPEND_AFTER_CANCELLATION in link.findings
    assert not link.counts_toward_spend


def test_currencies_are_never_converted_or_summed():
    link = correlate_contract_spend([contract()], [spend(currency="EUR", contract_ref="ctr_1")],
                                    eval_time=NOW)[0]
    summary = summarize_contract_spend([contract()], [link], spend_coverage_ready=True)[0]
    assert SpendFinding.CURRENCY_MISMATCH in link.findings
    assert link.currency == "EUR" and summary.currency == "USD"
    assert summary.spent_minor_units == 0


def test_unresolved_vendor_produces_no_link_even_with_reference():
    assert correlate_contract_spend([contract()],
                                    [spend(vendor_node_id=None, contract_ref="ctr_1")],
                                    eval_time=NOW) == ()


def test_overlapping_contracts_are_unattributed_not_guessed():
    other = contract(contract_id="ctr_2")
    link = correlate_contract_spend([contract(), other], [spend()], eval_time=NOW)[0]
    assert link.attribution is SpendAttribution.UNATTRIBUTED
    assert link.candidate_contract_ids == ("ctr_1", "ctr_2")
    assert SpendFinding.AMBIGUOUS_CONTRACT in link.findings


def test_bad_explicit_reference_never_falls_back_to_a_different_contract():
    wrong_vendor = contract(contract_id="ctr_wrong", vendor_node_id="vendor_2")
    link = correlate_contract_spend(
        [contract(), wrong_vendor], [spend(contract_ref="ctr_wrong")], eval_time=NOW)[0]
    assert link.attribution is SpendAttribution.UNATTRIBUTED
    assert link.contract_id is None
    assert link.candidate_contract_ids == ("ctr_wrong",)
