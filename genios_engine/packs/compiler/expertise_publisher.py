"""Idempotent ExpertisePackage publication seams."""

from __future__ import annotations

import json
from typing import Protocol

from sqlalchemy import text

from genios_engine.contracts.domain_expertise import ExpertisePackage
from genios_engine.platform.canonical import canonical_dumps, canonicalize

from .errors import ExpertisePublicationConflict


class ExpertisePublisher(Protocol):
    def publish(self, package: ExpertisePackage) -> ExpertisePackage: ...


def _plain_canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


class InMemoryExpertisePublisher:
    def __init__(self) -> None:
        self.packages: dict[tuple[str, str], ExpertisePackage] = {}

    def publish(self, package: ExpertisePackage) -> ExpertisePackage:
        key = (package.org_id, package.id)
        previous = self.packages.get(key)
        if previous is not None and previous.semantic_hash != package.semantic_hash:
            raise ExpertisePublicationConflict(
                f"expertise id collision for {package.org_id}:{package.id}")
        self.packages[key] = previous or package
        return self.packages[key]


class PostgresExpertisePublisher:
    def __init__(self, connection) -> None:
        self.connection = connection

    def publish(self, package: ExpertisePackage) -> ExpertisePackage:
        canonical_payload = canonicalize(package.to_semantic_dict())
        payload = _plain_canonical(canonical_payload)
        visibility = _plain_canonical(canonicalize(package.visibility))
        self.connection.execute(text(
            "insert into expertise_packages (org_id,expertise_id,semantic_hash,schema_version,"
            "trace_id,situation_id,brain_snapshot_id,visibility,payload) values "
            "(:o,:id,:hash,:schema,:trace,:situation,:brain,cast(:visibility as jsonb),"
            "cast(:payload as jsonb)) on conflict (org_id,expertise_id) do nothing"), {
                "o": package.org_id,
                "id": package.id,
                "hash": package.semantic_hash,
                "schema": package.schema_version,
                "trace": package.trace_id,
                "situation": package.situation_id,
                "brain": package.brain_snapshot_id,
                "visibility": visibility,
                "payload": payload,
            })
        held = self.connection.execute(text(
            "select semantic_hash,payload from expertise_packages "
            "where org_id=:o and expertise_id=:id"),
            {"o": package.org_id, "id": package.id}).mappings().first()
        if held is None:
            raise ExpertisePublicationConflict("expertise package insert was not observable")
        stored_hash = held.get("semantic_hash")
        stored_payload = held.get("payload")
        if isinstance(stored_payload, str):
            stored_payload = json.loads(stored_payload)
        if stored_hash != package.semantic_hash \
                or _plain_canonical(stored_payload) != payload:
            raise ExpertisePublicationConflict(
                f"immutable expertise package mismatch for {package.org_id}:{package.id}")
        return package


def purge_superseded_expertise_packages(engine, *, keep: int = 3) -> int:
    """Keep the newest `keep` packages per (org, situation); delete the rest. Returns rows removed.

    Content-addressing stops a package being rewritten when NOTHING changed — that fix is in
    `contracts/domain_expertise.py` and it is the larger half. It cannot bound this table on its
    own, and the reason is worth stating plainly rather than discovering later:
    `SituationContextSlice.graph_version` is ORG-GLOBAL (`max(graph_version) from graph_versions`),
    so any write anywhere in the tenant advances the version carried by EVERY situation's slice,
    including anchors whose own facts did not move. A package therefore legitimately mints a new
    id on each sync that touched anything, and at ~238 kB a package with 73 live situations that
    is ~17 MB per sync for one tenant. Unbounded growth of the slow kind instead of the fast kind.

    Removing `graph_version` from the content address would bound it harder, and was deliberately
    NOT done: the version is what binds a compiled package to the exact graph it observed, it is
    the same value the reasoning snapshot's integrity guard compares, and quietly making two
    packages built from different graphs identical is a worse property to own than a table that
    needs sweeping. Superseding is honest — the old package really is superseded — and it is the
    same shape as `purge_expired_context_payloads` next door.

    `keep > 1` on purpose: the newest package is what the current card cites, and the ones behind
    it are what an audit of a card issued yesterday needs in order to replay. Three is a working
    window, not a guarantee — a replay of something older is expected to fail closed rather than
    read a package that was quietly swapped underneath it.
    """
    with engine.begin() as conn:
        result = conn.execute(text(
            "delete from expertise_packages p using ("
            "  select org_id, expertise_id, row_number() over ("
            "    partition by org_id, situation_id order by created_at desc, expertise_id desc"
            "  ) rn from expertise_packages"
            ") ranked "
            "where ranked.rn > :keep and p.org_id = ranked.org_id "
            "  and p.expertise_id = ranked.expertise_id"), {"keep": keep})
    return int(result.rowcount or 0)


__all__ = [
    "ExpertisePublisher",
    "InMemoryExpertisePublisher",
    "PostgresExpertisePublisher",
    "purge_superseded_expertise_packages",
]
