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


__all__ = [
    "ExpertisePublisher",
    "InMemoryExpertisePublisher",
    "PostgresExpertisePublisher",
]
