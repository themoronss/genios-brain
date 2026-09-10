"""L2.3.5 · deterministic contract-to-spend correlation.

Money remains integer minor units and currency-partitioned.  The module never converts, allocates
or guesses: an ambiguous/out-of-term item is explicitly UNATTRIBUTED, and missing spend coverage
produces UNKNOWN rather than a measured zero.
"""

from __future__ import annotations

from pathlib import Path

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Sequence

from sqlalchemy import text

from genios_engine.context.analytic.publish import publish_derived_fact
from genios_engine.platform.canonical import semantic_hash, stable_id


class SpendAttribution(str, Enum):
    EXACT = "exact"
    STRONG = "strong"
    UNATTRIBUTED = "unattributed"


class SpendFinding(str, Enum):
    SPEND_PAST_TERM = "spend_past_term"
    SPEND_AFTER_CANCELLATION = "spend_after_cancellation"
    CURRENCY_MISMATCH = "currency_mismatch"
    AMBIGUOUS_CONTRACT = "ambiguous_contract"


class SpendCoverage(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ContractResource:
    contract_id: str
    vendor_node_id: str | None
    starts_at: datetime
    ends_at: datetime | None
    committed_minor_units: int
    currency: str
    cancelled_at: datetime | None = None

    def __post_init__(self) -> None:
        _money(self.committed_minor_units)
        _aware(self.starts_at, "starts_at")
        if self.ends_at is not None:
            _aware(self.ends_at, "ends_at")
            if self.ends_at < self.starts_at:
                raise ValueError("contract ends_at precedes starts_at")
        if self.cancelled_at is not None:
            _aware(self.cancelled_at, "cancelled_at")
        _currency(self.currency)

    @property
    def effective_end(self) -> datetime | None:
        if self.cancelled_at is None:
            return self.ends_at
        if self.ends_at is None:
            return self.cancelled_at
        return min(self.ends_at, self.cancelled_at)

    def contains(self, at: datetime) -> bool:
        end = self.effective_end
        return at >= self.starts_at and (end is None or at <= end)


@dataclass(frozen=True, slots=True)
class SpendEvent:
    spend_id: str
    vendor_node_id: str | None
    occurred_at: datetime
    minor_units: int
    currency: str
    contract_ref: str | None = None

    def __post_init__(self) -> None:
        _money(self.minor_units)
        _aware(self.occurred_at, "occurred_at")
        _currency(self.currency)


@dataclass(frozen=True, slots=True)
class ContractSpendLink:
    spend_id: str
    contract_id: str | None
    attribution: SpendAttribution
    minor_units: int
    currency: str
    occurred_at: datetime
    within_term: bool
    counts_toward_spend: bool
    findings: tuple[SpendFinding, ...] = ()
    candidate_contract_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ContractSpendSummary:
    contract_id: str
    currency: str
    coverage: SpendCoverage
    committed_minor_units: int
    spent_minor_units: int | None
    unattributed_minor_units: int | None
    link_ids: tuple[str, ...] = ()
    finding_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResourceCorrelationSweep:
    contracts: int = 0
    spend_events: int = 0
    exact: int = 0
    strong: int = 0
    unattributed: int = 0
    links_written: int = 0
    summaries_written: int = 0
    coverage: SpendCoverage = SpendCoverage.UNKNOWN

    def as_record(self) -> dict[str, int | str]:
        return {
            "contracts": self.contracts, "spend_events": self.spend_events,
            "exact": self.exact, "strong": self.strong,
            "unattributed": self.unattributed, "links_written": self.links_written,
            "summaries_written": self.summaries_written, "coverage": self.coverage.value,
        }


def _money(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TypeError("money must be a non-negative integer in minor units")
    return value


def _aware(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value


def _currency(value: str) -> str:
    if not isinstance(value, str) or len(value) != 3 or value != value.upper():
        raise ValueError("currency must be an uppercase ISO-4217 code")
    return value


def _past_findings(contract: ContractResource, spend: SpendEvent) -> tuple[SpendFinding, ...]:
    findings: list[SpendFinding] = []
    if contract.cancelled_at is not None and spend.occurred_at > contract.cancelled_at:
        findings.append(SpendFinding.SPEND_AFTER_CANCELLATION)
    elif contract.ends_at is not None and spend.occurred_at > contract.ends_at:
        findings.append(SpendFinding.SPEND_PAST_TERM)
    if spend.currency != contract.currency:
        findings.append(SpendFinding.CURRENCY_MISMATCH)
    return tuple(findings)


def correlate_contract_spend(
    contracts: Sequence[ContractResource],
    spend_events: Sequence[SpendEvent],
    *,
    eval_time: datetime,
) -> tuple[ContractSpendLink, ...]:
    """Rank exact reference, then unique vendor+term; never guess an unresolved/ambiguous side."""
    _aware(eval_time, "eval_time")
    by_id = {contract.contract_id: contract for contract in contracts}
    links: list[ContractSpendLink] = []
    for spend in sorted(spend_events, key=lambda item: (item.occurred_at, item.spend_id)):
        if spend.occurred_at > eval_time or not spend.vendor_node_id:
            continue

        explicit = by_id.get(spend.contract_ref or "")
        if explicit is not None and explicit.vendor_node_id \
                and explicit.vendor_node_id == spend.vendor_node_id:
            findings = _past_findings(explicit, spend)
            within = explicit.contains(spend.occurred_at)
            currency_matches = spend.currency == explicit.currency
            links.append(ContractSpendLink(
                spend_id=spend.spend_id, contract_id=explicit.contract_id,
                attribution=SpendAttribution.EXACT, minor_units=spend.minor_units,
                currency=spend.currency, occurred_at=spend.occurred_at, within_term=within,
                counts_toward_spend=within and currency_matches, findings=findings))
            continue

        # A supplied reference is an assertion about identity.  If it cannot be resolved to the
        # same vendor, silently falling back to a different vendor/term match would turn a bad
        # reference into a confident link.  Preserve it as unattributed for review instead.
        if spend.contract_ref:
            candidates = (explicit.contract_id,) if explicit is not None else ()
            links.append(ContractSpendLink(
                spend_id=spend.spend_id, contract_id=None,
                attribution=SpendAttribution.UNATTRIBUTED, minor_units=spend.minor_units,
                currency=spend.currency, occurred_at=spend.occurred_at, within_term=False,
                counts_toward_spend=False,
                findings=((SpendFinding.AMBIGUOUS_CONTRACT,) if explicit is not None else ()),
                candidate_contract_ids=candidates))
            continue

        vendor_contracts = [contract for contract in contracts
                            if contract.vendor_node_id
                            and contract.vendor_node_id == spend.vendor_node_id]
        in_term = [contract for contract in vendor_contracts
                   if contract.contains(spend.occurred_at)
                   and contract.currency == spend.currency]
        if len(in_term) == 1:
            contract = in_term[0]
            links.append(ContractSpendLink(
                spend_id=spend.spend_id, contract_id=contract.contract_id,
                attribution=SpendAttribution.STRONG, minor_units=spend.minor_units,
                currency=spend.currency, occurred_at=spend.occurred_at, within_term=True,
                counts_toward_spend=True))
            continue

        candidates = tuple(sorted(contract.contract_id for contract in
                                  (in_term if in_term else vendor_contracts)))
        findings: list[SpendFinding] = []
        if len(in_term) > 1:
            findings.append(SpendFinding.AMBIGUOUS_CONTRACT)
        elif vendor_contracts:
            # Keep cancellation/end findings visible while refusing attribution.
            for contract in vendor_contracts:
                findings.extend(_past_findings(contract, spend))
        links.append(ContractSpendLink(
            spend_id=spend.spend_id, contract_id=None,
            attribution=SpendAttribution.UNATTRIBUTED, minor_units=spend.minor_units,
            currency=spend.currency, occurred_at=spend.occurred_at, within_term=False,
            counts_toward_spend=False, findings=tuple(sorted(set(findings), key=str)),
            candidate_contract_ids=candidates))
    return tuple(links)


def summarize_contract_spend(
    contracts: Sequence[ContractResource],
    links: Sequence[ContractSpendLink],
    *,
    spend_coverage_ready: bool | None,
) -> tuple[ContractSpendSummary, ...]:
    """Per-contract, per-currency totals; UNKNOWN coverage carries no fabricated zero."""
    out: list[ContractSpendSummary] = []
    for contract in sorted(contracts, key=lambda value: value.contract_id):
        attributed = [link for link in links if link.contract_id == contract.contract_id
                      and link.counts_toward_spend and link.currency == contract.currency]
        related_unattributed = [link for link in links
                                if contract.contract_id in link.candidate_contract_ids
                                and link.currency == contract.currency]
        known = spend_coverage_ready is True
        out.append(ContractSpendSummary(
            contract_id=contract.contract_id, currency=contract.currency,
            coverage=SpendCoverage.KNOWN if known else SpendCoverage.UNKNOWN,
            committed_minor_units=contract.committed_minor_units,
            spent_minor_units=(sum(link.minor_units for link in attributed) if known else None),
            unattributed_minor_units=(sum(link.minor_units for link in related_unattributed)
                                      if known else None),
            link_ids=tuple(link.spend_id for link in attributed),
            finding_ids=tuple(sorted({link.spend_id for link in links
                                      if link.contract_id == contract.contract_id
                                      and link.findings}))))
    return tuple(out)


_RESOURCE_FACTS = text(
    "select n.node_id, n.node_type, f.fact_version_id, f.field, f.value, f.occurred_at "
    "from graph_nodes n join graph_facts f "
    "  on f.org_id=n.org_id and f.subject_node_id=n.node_id "
    " and f.valid_to is null and f.status='active' "
    "where n.org_id=:o and n.valid_to is null "
    "  and n.node_type = any(cast(:types as text[])) "
    "order by n.node_id, f.field, f.fact_version_id")

#: THE SHIPPED PAIR: what a COMMITMENT looks like, and what a DRAW against one looks like.
#:
#: They were the only two answers, and they are a procurement vocabulary. The same reading —
#: *we committed to X and have drawn Y against it, and Z is unattributed* — is what a clinic
#: asks of a `care_plan` against `visits`, a firm of a `retainer` against `time_entries`, a
#: school of a `budget_line` against `requisitions`, an exporter of an `L/C` against
#: `shipments`. Every one of those was a Python edit, and until it happened the whole correlator
#: read a tenant's world as empty rather than as unmodelled.
#:
#: WHAT IS NOT AUTHORABLE, and must not become so: the three-tier EXACT / STRONG / UNATTRIBUTED
#: discipline and the refusal to guess through an unresolved reference. Those are what make an
#: attribution honest, and a tenant who could relax them would get a tidier report about a
#: world that had not changed. Only WHICH NODE TYPES carry the two roles moves.
_CONTRACT_TYPES = ("contract", "subscription")
_SPEND_TYPES = ("invoice", "payment", "spend")

#: Where an authored pair lives. One file, because a commitment type and a draw type only mean
#: anything together — a directory of halves would let somebody declare one and wonder why
#: nothing attributed.
RESOURCE_KINDS_FILE = Path(__file__).resolve().parent.joinpath(
    "observations", "resource_kinds.yaml")


def resource_kinds(path: "Path | None" = None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """`(commitment types, draw types)` — the shipped pair plus whatever a business declared.

        commitment_types: [retainer]
        draw_types: [time_entry]

    ADDED, NEVER REPLACED. A tenant that models retainers usually still has invoices, and a
    declaration that silently stopped reading `contract` would empty a working correlator on
    the day somebody added a line. Removing a shipped type is a code change precisely because
    it is the destructive direction.
    """
    import yaml

    target = path or RESOURCE_KINDS_FILE
    commitments, draws = list(_CONTRACT_TYPES), list(_SPEND_TYPES)
    try:
        if not target.is_file():
            return tuple(commitments), tuple(draws)
        data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        for key, sink in (("commitment_types", commitments), ("draw_types", draws)):
            for name in (data.get(key) or []):
                cleaned = str(name).strip()
                # A TYPE MAY NOT BE BOTH. A node that is its own draw would attribute against
                # itself and report a contract as fully spent the moment it existed.
                if cleaned and cleaned not in commitments and cleaned not in draws:
                    sink.append(cleaned)
    except Exception:      # noqa: BLE001 — an unreadable file leaves the shipped pair standing
        return _CONTRACT_TYPES, _SPEND_TYPES
    return tuple(commitments), tuple(draws)


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _moment(value: Any) -> datetime | None:
    value = _json_value(value)
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return result.astimezone(timezone.utc) if result.tzinfo is not None else None


def _text_value(value: Any) -> str | None:
    value = _json_value(value)
    if isinstance(value, Mapping):
        value = value.get("id") or value.get("node_id") or value.get("value")
    return str(value).strip() if value not in (None, "") else None


def _money_value(value: Any, currency_value: Any = None) -> tuple[int, str] | None:
    value = _json_value(value)
    currency = _text_value(currency_value)
    amount: Any = value
    if isinstance(value, Mapping):
        amount = next((value[key] for key in (
            "minor_units", "amount_minor_units", "amount_minor", "amount_cents", "amount")
                       if key in value), None)
        currency = _text_value(value.get("currency")) or currency
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0 or not currency:
        return None
    currency = currency.upper()
    try:
        return _money(amount), _currency(currency)
    except (TypeError, ValueError):
        return None


def _pick(facts: Mapping[str, tuple[Any, str, datetime | None]], *names: str) -> Any:
    for name in names:
        if name in facts:
            return facts[name][0]
    return None


def _resource_inputs(conn, org_id: str) -> tuple[
        tuple[ContractResource, ...], tuple[SpendEvent, ...], dict[str, tuple[str, ...]]]:
    commitment_types, draw_types = resource_kinds()
    rows = conn.execute(
        _RESOURCE_FACTS, {"o": org_id, "types": [*commitment_types, *draw_types]}
    ).mappings().all()
    grouped: dict[str, dict[str, tuple[Any, str, datetime | None]]] = {}
    types: dict[str, str] = {}
    for row in rows:
        node_id = str(row["node_id"])
        types[node_id] = str(row["node_type"])
        grouped.setdefault(node_id, {})[str(row["field"])] = (
            _json_value(row["value"]), str(row["fact_version_id"]), row["occurred_at"])

    contracts: list[ContractResource] = []
    spends: list[SpendEvent] = []
    provenance: dict[str, tuple[str, ...]] = {}
    for node_id, facts in grouped.items():
        node_type = types[node_id]
        provenance[node_id] = tuple(sorted({record[1] for record in facts.values()}))
        if node_type in commitment_types:
            prefix = node_type
            starts = _moment(_pick(facts, f"{prefix}.starts_at", "contract.start_date"))
            amount = _money_value(
                _pick(facts, f"{prefix}.value", f"{prefix}.amount", "contract.value"),
                _pick(facts, f"{prefix}.currency", "contract.currency"))
            if starts is None or amount is None:
                continue
            contracts.append(ContractResource(
                contract_id=node_id,
                vendor_node_id=_text_value(_pick(
                    facts, f"{prefix}.vendor_node_id", "contract.vendor_node_id")),
                starts_at=starts,
                ends_at=_moment(_pick(
                    facts, f"{prefix}.ends_at", f"{prefix}.current_period_end",
                    "contract.end_date")),
                committed_minor_units=amount[0], currency=amount[1],
                cancelled_at=_moment(_pick(
                    facts, f"{prefix}.cancelled_at", "contract.cancelled_at"))))
            continue

        amount_field = next((name for name in (
            f"{node_type}.total", f"{node_type}.amount", "spend.amount") if name in facts), None)
        amount = _money_value(
            facts[amount_field][0] if amount_field else None,
            _pick(facts, f"{node_type}.currency", "spend.currency"))
        occurred = _moment(_pick(
            facts, f"{node_type}.occurred_at", f"{node_type}.paid_at", "spend.occurred_at"))
        if occurred is None and amount_field is not None:
            occurred = facts[amount_field][2]
            if occurred is not None and occurred.tzinfo is not None:
                occurred = occurred.astimezone(timezone.utc)
        if amount is None or occurred is None:
            continue
        spends.append(SpendEvent(
            spend_id=node_id,
            vendor_node_id=_text_value(_pick(
                facts, f"{node_type}.vendor_node_id", "spend.vendor_node_id")),
            occurred_at=occurred, minor_units=amount[0], currency=amount[1],
            contract_ref=_text_value(_pick(
                facts, f"{node_type}.contract_ref", "spend.contract_ref"))))
    return tuple(contracts), tuple(spends), provenance


def _spend_coverage(conn, org_id: str) -> bool | None:
    rows = conn.execute(text(
        "select domain, coverage_ready, freshness from source_coverage where org_id=:o"),
        {"o": org_id}).mappings().all()
    explicit: list[bool] = []
    for row in rows:
        domain = str(row["domain"]).lower()
        if domain in {"finance", "spend", "procurement"}:
            explicit.append(bool(row["coverage_ready"]))
        freshness = row["freshness"] if isinstance(row["freshness"], Mapping) else {}
        if any(str(status) == "fresh" and any(
                token in str(capability).lower()
                for token in ("invoice", "payment", "spend", "finance"))
               for capability, status in freshness.items()):
            explicit.append(True)
    return all(explicit) if explicit else None


def _link_payload(link: ContractSpendLink, inputs: tuple[str, ...]) -> dict[str, Any]:
    return {
        "spend_id": link.spend_id, "contract_id": link.contract_id,
        "attribution": link.attribution.value, "minor_units": link.minor_units,
        "currency": link.currency, "occurred_at": link.occurred_at.isoformat(),
        "within_term": link.within_term, "counts_toward_spend": link.counts_toward_spend,
        "findings": [finding.value for finding in link.findings],
        "candidate_contract_ids": list(link.candidate_contract_ids),
        "input_fact_version_ids": list(inputs), "formula_version": "resource-correlation.v1",
    }


def _persist_links(conn, org_id: str, links: Sequence[ContractSpendLink],
                   provenance: Mapping[str, tuple[str, ...]], eval_time: datetime) -> int:
    keep: list[str] = []
    written = 0
    for link in links:
        related = tuple(sorted(set(provenance.get(link.spend_id, ())) | {
            fact_id for contract_id in ([link.contract_id] if link.contract_id else
                                       link.candidate_contract_ids)
            for fact_id in provenance.get(contract_id, ())}))
        payload = _link_payload(link, related)
        content_hash = semantic_hash(payload)
        link_id = stable_id("csl", {"org_id": org_id, "payload": payload})
        keep.append(link_id)
        count = conn.execute(text(
            "insert into contract_spend_attributions "
            "(link_id, org_id, spend_node_id, contract_node_id, attribution, amount_minor_units, "
            " currency, occurred_at, counts_toward_spend, findings, candidate_contract_ids, "
            " input_fact_version_ids, formula_version, content_hash, valid_from) values "
            "(:id,:o,:sp,:ct,:a,:amount,:cur,:at,:counts,cast(:findings as jsonb),"
            " cast(:candidates as jsonb),cast(:inputs as jsonb),:formula,:hash,:now) "
            "on conflict (link_id) do nothing"), {
                "id": link_id, "o": org_id, "sp": link.spend_id, "ct": link.contract_id,
                "a": link.attribution.value, "amount": link.minor_units,
                "cur": link.currency, "at": link.occurred_at,
                "counts": link.counts_toward_spend,
                "findings": json.dumps([finding.value for finding in link.findings]),
                "candidates": json.dumps(list(link.candidate_contract_ids)),
                "inputs": json.dumps(list(related)), "formula": "resource-correlation.v1",
                "hash": content_hash, "now": eval_time,
            }).rowcount or 0
        written += int(count)
        conn.execute(text(
            "update contract_spend_attributions set valid_to=null, status='active' "
            "where org_id=:o and link_id=:id"), {"o": org_id, "id": link_id})
    conn.execute(text(
        "update contract_spend_attributions set valid_to=:now, status='superseded' "
        "where org_id=:o and valid_to is null "
        "and not (link_id = any(cast(:keep as text[])))"),
        {"o": org_id, "now": eval_time, "keep": keep})
    return written


def refresh_contract_spend(store, org_id: str, *, eval_time: datetime,
                           spend_coverage_ready: bool | None = None) -> ResourceCorrelationSweep:
    """Production cross-resource pass.  Reads current graph state once and publishes deterministically."""
    _aware(eval_time, "eval_time")
    with store.engine.begin() as conn:
        contracts, spends, provenance = _resource_inputs(conn, org_id)
        coverage_ready = (_spend_coverage(conn, org_id) if spend_coverage_ready is None
                          else spend_coverage_ready)
        links = correlate_contract_spend(contracts, spends, eval_time=eval_time)
        summaries = summarize_contract_spend(
            contracts, links, spend_coverage_ready=coverage_ready)
        links_written = _persist_links(conn, org_id, links, provenance, eval_time)
        summaries_written = 0
        for summary in summaries:
            inputs = tuple(sorted(set(provenance.get(summary.contract_id, ())) | {
                fact_id for spend_id in (*summary.link_ids, *summary.finding_ids)
                for fact_id in provenance.get(spend_id, ())}))
            published = publish_derived_fact(
                conn, org_id=org_id, subject_node_id=summary.contract_id,
                field="derived.contract_spend.summary",
                value={
                    "currency": summary.currency, "coverage": summary.coverage.value,
                    "committed_minor_units": summary.committed_minor_units,
                    "spent_minor_units": summary.spent_minor_units,
                    "unattributed_minor_units": summary.unattributed_minor_units,
                    "link_ids": list(summary.link_ids), "finding_ids": list(summary.finding_ids),
                    "input_fact_version_ids": list(inputs),
                    "formula_version": "resource-correlation.v1",
                }, eval_time=eval_time, value_type="contract_spend_summary",
                visibility_scope="org", version_prefix="fv_resource:")
            summaries_written += int(published.wrote)
    return ResourceCorrelationSweep(
        contracts=len(contracts), spend_events=len(spends),
        exact=sum(link.attribution is SpendAttribution.EXACT for link in links),
        strong=sum(link.attribution is SpendAttribution.STRONG for link in links),
        unattributed=sum(link.attribution is SpendAttribution.UNATTRIBUTED for link in links),
        links_written=links_written, summaries_written=summaries_written,
        coverage=(SpendCoverage.KNOWN if coverage_ready is True else SpendCoverage.UNKNOWN))


__all__ = ["ContractResource", "ContractSpendLink", "ContractSpendSummary",
           "ResourceCorrelationSweep", "SpendAttribution", "SpendCoverage", "SpendEvent",
           "SpendFinding", "correlate_contract_spend", "refresh_contract_spend",
           "summarize_contract_spend"]
