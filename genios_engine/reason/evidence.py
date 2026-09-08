"""Layer 4 · Group L4.3 — the evidence layer: one identity, one emission, one digest.

Doc 03 states the inversion this module closes:

    | | Globe's model | Code today |
    | Who mints evidence | units, as they observe | adapters, before any unit runs |
    | What it carries | unit_ref, claim, value | source + payload; no unit_ref, no value_bp |
    | How many builders | one | THREE, with three id seeds |
    | Lifetime | as long as the decision | payload TTL 720h, then gone |

S1 and S2 both live here. S3 (the store) extends `reason/store.py`, which is preserve-hard.

WHY THE THREE SEEDS WERE A CORRECTNESS BUG, NOT UNTIDINESS
----------------------------------------------------------
Before this module the same observed fact carried a different `evidence_id` depending on
which lane produced it:

    composer.py          {org_id, deal_id, signal_id, reasoning_run_id}
    adapters/legacy_*    {org_id, node_id, field, value_hash, occurred_at, source_ref_id,
                          fact_version_id}
    adapters/native.py   {org_id, node_id, partition, field, value_hash, source_ref_id,
                          fact_version_id, occurred_at}

Rule 11 (doc 04 E2) raises confidence ONLY on evidence drawn from a different independence
group, and independence groups are derived from source identity. Two rows describing one
fact under two ids look independent — so the same observation, seen twice, could RAISE
confidence. That is the failure mode Law 4 exists to prevent, reached through the id seed
rather than through the composition. The single seed below is a precondition for Rule 11.

THE SEED IS THE FIVE-TUPLE DOC 03 PRINTS, AND NOTHING ELSE
----------------------------------------------------------
    id = content_hash(org_id, entity_ref, field, source_ref, observed_at_key)

`value_hash` is deliberately NOT in it. An id that changes when the value changes is not an
identity, it is a version — and it makes "have we already said this?" unanswerable, because
the second reading of a fact that moved gets a fresh id and reads as a brand new
observation. `fact_version_id` and `reasoning_run_id` are dropped for the same reason: they
are lineage, they are still carried ON the ref, and they are exactly what made the three
lanes disagree.

`context_scope` is not in the seed either, and it does not need to be: a neighbour-scoped
reading is a statement about a DIFFERENT ENTITY (the 1-hop neighbourhood), so the caller
passes a different `entity_ref` for it — see `neighborhood_ref()`. The distinction survives
in the place the doc puts it, rather than as a sixth seed component nobody outside this file
would know to reproduce.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from genios_engine.contracts.reasoning import EvidenceRef, Finding, ReasonerResult, unit_ref
from genios_engine.platform.canonical import canonical_dumps, semantic_hash, stable_id

#: Stamped into the seed so a v2 id can never be mistaken for, or collide with, one of the three
#: historic ids it replaces. `reasoning_evidence_id_map` maps old to new; a shared hash space
#: would make that table ambiguous in exactly the cases it exists to disambiguate.
EVIDENCE_SEED_VERSION = "evidence_seed@2"

#: What an unobserved fact's `observed_at_key` is. NOT the empty string and NOT the epoch: an
#: absent observation time is a different claim from "observed at midnight 1970", and typed
#: absence is the rule L2 already follows.
UNOBSERVED = "unobserved"

#: Doc 03: "enough to re-read the claim in a card, short enough that the permanent table stays
#: small and carries no bulk PII."
RENDERED_TEXT_CAP = 120

#: The suffix that turns a root entity ref into the ref for its 1-hop neighbourhood.
NEIGHBORHOOD_SUFFIX = "#neighbor"


def observed_at_key(value: Any) -> str:
    """The seed's fifth component: one canonical spelling of *when this was observed*.

    Two lanes reading the same source record must agree on this string, so a naive datetime is
    read as UTC (which is what every writer in the tree means by one) and an ISO string is
    parsed rather than embedded verbatim — `2026-01-01T00:00:00Z` and `2026-01-01T00:00:00+00:00`
    are the same instant and must not be two identities.
    """
    if value is None:
        return UNOBSERVED
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return UNOBSERVED
        try:
            value = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text
    if not isinstance(value, datetime):
        raise TypeError("observed_at must be a datetime, an ISO-8601 string, or None")
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def neighborhood_ref(entity_ref: str) -> str:
    """The entity ref for the 1-hop neighbourhood of `entity_ref`.

    A borrowed fact is asserted by a neighbour, not by the anchor. Giving it its own entity ref
    keeps root and neighbour readings of the SAME field distinct without adding `context_scope`
    to the seed — and it keeps the collapse honest: the two readings really are about two
    different things.
    """
    ref = str(entity_ref).strip()
    if not ref:
        raise ValueError("entity_ref is required")
    return ref if ref.endswith(NEIGHBORHOOD_SUFFIX) else f"{ref}{NEIGHBORHOOD_SUFFIX}"


def evidence_id(*, org_id: str, entity_ref: str, field: str,
                source_ref: str | None, observed_at: Any = None,
                observed_key: str | None = None) -> str:
    """DLG-11 · THE evidence identity. One seed, one shape, all three lanes.

    `observed_key` exists for the backfill, which reads an already-normalized key off a stored
    payload and must not re-derive it; live callers pass `observed_at` and let this normalize.
    """
    org = str(org_id).strip()
    entity = str(entity_ref).strip()
    name = str(field).strip()
    if not org or not entity or not name:
        raise ValueError("evidence id requires org_id, entity_ref and field")
    source = str(source_ref).strip() if source_ref is not None else ""
    key = observed_key if observed_key is not None else observed_at_key(observed_at)
    return stable_id("evidence", {
        "seed_version": EVIDENCE_SEED_VERSION,
        "org_id": org,
        "entity_ref": entity,
        "field": name,
        "source_ref": source,
        "observed_at_key": key,
    })


def build_evidence_ref(*, org_id: str, entity_ref: str, field: str, value: Any,
                       source_ref: str | None = None, observed_at: Any = None,
                       context_scope: str = "root", fact_version_id: str | None = None,
                       confidence_bp: int = 5_000, authority_rank: int = 1,
                       independence_group: str | None = None) -> EvidenceRef:
    """The ONE builder (DLG-11). Every lane that mints evidence calls this and nothing else.

    Everything after `value` is provenance carried ON the ref and deliberately absent from the
    seed. `independence_group` in particular: Rule 11 groups by it, and a group derived from a
    lane-specific id would re-open the bug this builder closes.
    """
    scope = str(context_scope).strip() or "root"
    if scope not in {"root", "neighbor"}:
        raise ValueError("evidence context_scope must be root or neighbor")
    seed_entity = neighborhood_ref(entity_ref) if scope == "neighbor" else str(entity_ref).strip()
    normalized_at = observed_at
    if normalized_at is not None and not isinstance(normalized_at, datetime):
        key = observed_at_key(normalized_at)
        try:
            normalized_at = datetime.fromisoformat(key)
        except ValueError:
            normalized_at = None
    return EvidenceRef(
        evidence_id=evidence_id(org_id=org_id, entity_ref=seed_entity, field=field,
                                source_ref=source_ref, observed_at=observed_at),
        field=field,
        value=value,
        context_scope=scope,
        source_ref_id=str(source_ref) if source_ref is not None else None,
        fact_version_id=str(fact_version_id) if fact_version_id is not None else None,
        occurred_at=normalized_at,
        confidence_bp=confidence_bp,
        authority_rank=authority_rank,
        independence_group=(str(independence_group)
                            if independence_group is not None else None),
    )


def canonical_evidence_id_for(*, org_id: str, root_entity_id: str,
                              ref: Mapping[str, Any] | EvidenceRef) -> str:
    """The canonical id a STORED evidence ref would have. The backfill's whole engine.

    Every seed component is recoverable from a persisted payload — which is why the historic
    migration can be complete rather than best-effort: `entity_ref` is the snapshot's root
    (plus the neighbourhood suffix when the ref says `neighbor`), and `field`, `source_ref_id`
    and `occurred_at` are on the ref itself.
    """
    data = ref if isinstance(ref, Mapping) else {
        "field": ref.field, "context_scope": ref.context_scope,
        "source_ref_id": ref.source_ref_id, "occurred_at": ref.occurred_at}
    scope = str(data.get("context_scope") or "root")
    entity = (neighborhood_ref(root_entity_id) if scope == "neighbor"
              else str(root_entity_id).strip())
    source = data.get("source_ref_id")
    return evidence_id(org_id=org_id, entity_ref=entity, field=str(data.get("field") or ""),
                       source_ref=(str(source) if source is not None else None),
                       observed_at=data.get("occurred_at"))


# ── S3's permanent half: the digest that outlives the payload ─────────────────────────────

def value_digest(value: Any) -> str:
    """The content address of an evidence value. Survives the 720h payload TTL forever."""
    return semantic_hash(value)


def rendered_text(field: str, value: Any) -> str:
    """A <=120 character human re-reading of one fact, for a card justified a year later.

    Bounded in this function and again by a CHECK constraint, because doc 03's size argument is
    also its PII argument: the permanent table is small precisely so that it is not a second,
    un-expiring copy of the payload.
    """
    if isinstance(value, str):
        body = value.strip()
    elif isinstance(value, (int, float, bool)) or value is None:
        body = str(value)
    else:
        body = canonical_dumps(value)
        if isinstance(body, bytes):
            body = body.decode("utf-8", "replace")
    text = f"{field}={body}".replace("\n", " ").replace("\r", " ").strip()
    if len(text) <= RENDERED_TEXT_CAP:
        return text
    return text[:RENDERED_TEXT_CAP - 1] + "…"


def digest_row(ref: Mapping[str, Any] | EvidenceRef) -> dict[str, Any]:
    """The permanent row for one evidence ref: doc 03's five fields plus its provenance keys.

    `unit_ref` is NOT here. It is stamped later, from the run's hash-verified reasoner results
    (see `unit_refs_by_evidence`), because a snapshot is written BEFORE any unit has observed
    anything — a unit_ref written at snapshot time would be a guess about the future.
    """
    data = ref if isinstance(ref, Mapping) else {
        "evidence_id": ref.evidence_id, "field": ref.field, "value": ref.value,
        "context_scope": ref.context_scope, "source_ref_id": ref.source_ref_id,
        "occurred_at": ref.occurred_at, "independence_group": ref.independence_group}
    field = str(data.get("field") or "")
    if not field:
        raise ValueError("evidence digest requires a field")
    identifier = str(data.get("evidence_id") or "")
    if not identifier:
        raise ValueError("evidence digest requires an evidence_id")
    value = data.get("value")
    body = {
        "evidence_id": identifier,
        "field": field,
        "context_scope": str(data.get("context_scope") or "root"),
        "value_digest": value_digest(value),
        "rendered_text": rendered_text(field, value),
        "observed_at_key": observed_at_key(data.get("occurred_at")),
        "source_ref_id": (str(data["source_ref_id"])
                          if data.get("source_ref_id") is not None else None),
        "independence_group": (str(data["independence_group"])
                               if data.get("independence_group") is not None else None),
    }
    body["digest_hash"] = semantic_hash(body)
    return body


def digest_set_hash(*, payload_hash: str, rows: Sequence[Mapping[str, Any]]) -> str:
    """The content address of a whole digest SET, bound to the payload it was minted from.

    Binding `payload_hash` is what stops a verified-looking digest set being transplanted onto
    another snapshot: `payload_hash` is inside `context_hash`, which is inside the snapshot id,
    so the anchor reaches all the way back to an id the store already proves.
    """
    ordered = sorted((str(row["evidence_id"]), str(row["digest_hash"])) for row in rows)
    return semantic_hash({"payload_hash": str(payload_hash),
                          "seed_version": EVIDENCE_SEED_VERSION,
                          "digests": [list(item) for item in ordered]})


def digests_for_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every permanent digest row for one stored context payload, ordered by evidence id."""
    refs = payload.get("evidence") or ()
    rows = [digest_row(item) for item in refs]
    rows.sort(key=lambda row: row["evidence_id"])
    seen = {row["evidence_id"] for row in rows}
    if len(seen) != len(rows):
        raise ValueError("context payload carries a duplicate evidence_id")
    return rows


# ── S1's half: Finding as THE per-unit emission ───────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class EvidenceEmission:
    """Globe's evidence schema — `unit_ref`, `claim`, `value` — as one read-only view.

    It stores nothing new. `unit_ref` is DERIVED (and membership-checked) via
    `contracts.reasoning.unit_ref`, `claim` is the finding's kind, `value` is `value_bp`. A
    second stored evidence object would need a second builder, a second store path and a second
    validator — the exact mistake doc 03 names.
    """

    unit_ref: str
    finding_id: str
    claim: str
    value_bp: int | None
    matched: bool | None
    evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def to_semantic_dict(self) -> dict[str, Any]:
        return {"unit_ref": self.unit_ref, "finding_id": self.finding_id, "claim": self.claim,
                "value_bp": self.value_bp, "matched": self.matched,
                "evidence_ids": self.evidence_ids, "reason_codes": self.reason_codes}


def emission(result: ReasonerResult, finding: Finding) -> EvidenceEmission:
    """One finding, read as evidence. Raises if the finding did not come from this result."""
    return EvidenceEmission(
        unit_ref=unit_ref(result, finding),
        finding_id=finding.finding_id,
        claim=finding.kind,
        value_bp=finding.value_bp,
        matched=finding.matched,
        evidence_ids=tuple(finding.evidence_ids),
        reason_codes=tuple(finding.reason_codes),
    )


def emissions(results: Iterable[ReasonerResult]) -> tuple[EvidenceEmission, ...]:
    """Every finding on a run, canonized as evidence, in a deterministic order.

    Ordered by (unit_ref, finding_id) rather than by execution order on purpose: this feeds a
    content-addressed digest stamp, and a hash that moved because a unit ran in a different
    position would be a false tamper alarm.
    """
    out = [emission(result, finding)
           for result in results for finding in result.findings]
    out.sort(key=lambda item: (item.unit_ref, item.finding_id))
    return tuple(out)


def unit_refs_by_evidence(results: Iterable[ReasonerResult]) -> dict[str, tuple[str, ...]]:
    """Which units observed each evidence id — the `unit_ref` column of the permanent digest.

    Built from `emissions()` so that the membership check runs on every finding on the run:
    that check IS the K2 row "Finding.unit_ref resolvable on 100%", enforced rather than
    sampled. A result's own top-level `evidence_ids` count too — a unit that consumed a fact
    without emitting a finding about it still observed it.
    """
    ordered = list(results)
    mapping: dict[str, set[str]] = {}
    for item in emissions(ordered):
        for identifier in item.evidence_ids:
            mapping.setdefault(identifier, set()).add(item.unit_ref)
    for result in ordered:
        for identifier in result.evidence_ids:
            mapping.setdefault(identifier, set()).add(result.reasoner_id)
        for adjustment in result.adjustments:
            for identifier in adjustment.evidence_ids:
                mapping.setdefault(identifier, set()).add(result.reasoner_id)
    return {key: tuple(sorted(value)) for key, value in sorted(mapping.items())}


__all__ = ["EVIDENCE_SEED_VERSION", "EvidenceEmission", "NEIGHBORHOOD_SUFFIX",
           "RENDERED_TEXT_CAP", "UNOBSERVED", "build_evidence_ref",
           "canonical_evidence_id_for", "digest_row", "digest_set_hash", "digests_for_payload",
           "emission", "emissions", "evidence_id", "neighborhood_ref", "observed_at_key",
           "rendered_text", "unit_refs_by_evidence", "value_digest"]
