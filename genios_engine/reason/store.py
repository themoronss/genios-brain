"""Transactional persistence for deterministic Layer 4 reasoning.

The reasoners themselves stay pure and database-free.  An orchestrator computes a
complete bundle in memory, then this store commits the run, all intermediate
results, every candidate/check and the final decision in one transaction.  A
repeated idempotency key returns the already-committed bundle; it can never create
a second authoritative decision.

The public methods deliberately accept mappings (and dataclass/Pydantic objects)
instead of importing the concrete reasoning contracts.  That keeps persistence a
leaf dependency while still using the shared canonical encoder for all hashes.
"""

from __future__ import annotations

import hashlib
import heapq
import json
from contextlib import nullcontext
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from genios_engine.packs.snapshot import snapshot_id as effective_config_snapshot_id
from genios_engine.platform.db import get_engine


class ReasoningStoreError(RuntimeError):
    """Base class for a persistence-contract violation."""


class IdempotencyConflict(ReasoningStoreError):
    """The same tenant idempotency key was reused for different semantic input."""


class ContextSnapshotMismatch(ReasoningStoreError):
    """A run attempted to bind context that does not match its immutable snapshot."""


class ConfigSnapshotMismatch(ReasoningStoreError):
    """A run attempted to bind a capability to another pack's effective config."""


class ContextPayloadExpired(ReasoningStoreError):
    """Snapshot metadata remains, but the retention-controlled payload is gone."""


class ReplayIntegrityError(ReasoningStoreError):
    """A persisted replay artifact no longer matches its declared semantic hash."""


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        # dataclasses.asdict() deep-copies every value.  Immutable reasoning
        # contracts deliberately contain MappingProxyType, which cannot be
        # pickled/deep-copied.  Read fields directly and let canonicalize()
        # recursively serialize the frozen values.
        return {item.name: getattr(value, item.name) for item in fields(value)}
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dict(dump(mode="python"))
    raise TypeError(f"{label} must be a mapping, dataclass, or Pydantic model")


def _sequence(value: Any, label: str) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise TypeError(f"{label} must be a sequence")
    return list(value)


def _required_text(data: Mapping[str, Any], key: str) -> str:
    value = str(data.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    out = str(value).strip()
    return out or None


def _enum_value(value: Any) -> Any:
    return value.value if isinstance(value, Enum) else value


def _aware_datetime(value: Any, label: str) -> datetime:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{label} must be an ISO-8601 datetime") from exc
    if not isinstance(value, datetime):
        raise TypeError(f"{label} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _canonical_dumps(value: Any) -> str:
    # Lazy import avoids a runtime dependency cycle: contracts/protocols may use
    # this store, while the canonical encoder remains the single hashing law.
    from genios_engine.reason.canonical import canonical_dumps

    encoded = canonical_dumps(value)
    return encoded.decode("utf-8") if isinstance(encoded, bytes) else encoded


def _semantic_hash(value: Any) -> str:
    from genios_engine.reason.canonical import semantic_hash

    return semantic_hash(value)


def _stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{_semantic_hash(value)}"


def _json_param(value: Any) -> str:
    return _canonical_dumps(value)


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value
    return value


def _encoded_semantic_hash(value: Any) -> str:
    """Hash JSON that is already in canonical tagged form after a database round-trip."""
    encoded = json.dumps(_json_value(value), ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _decanonicalize(value: Any) -> Any:
    """Restore scalar tags from canonical JSON loaded back from PostgreSQL.

    The persistence store normally hashes Python contract values before writing
    canonical tagged JSON.  Replay integrity checks run in the opposite
    direction, so they must restore those tagged scalars before applying the
    canonical hashing law again.  Keeping this small decoder local avoids a
    store -> replay -> store import cycle.
    """
    if isinstance(value, Mapping):
        if set(value) == {"$datetime"}:
            return datetime.fromisoformat(str(value["$datetime"]).replace("Z", "+00:00"))
        if set(value) == {"$date"}:
            return date.fromisoformat(str(value["$date"]))
        if set(value) == {"$decimal"}:
            return Decimal(str(value["$decimal"]))
        if set(value) == {"$uuid"}:
            return UUID(str(value["$uuid"]))
        return {str(key): _decanonicalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_decanonicalize(item) for item in value]
    return value


def _integrity_equal(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise ReplayIntegrityError(f"{label} integrity mismatch")


_POLICY_CHECK_REQUIREMENTS: dict[str, tuple[str, str]] = {
    "read_only": ("policy", "read_only_policy_pass"),
    "human_approval_required": ("permission", "human_approval_boundary_pass"),
    "evidence_required": ("policy", "evidence_policy_pass"),
    "no_unverified_recipient": ("permission", "verified_recipient_guard_pass"),
}


def _contract_check(value: Any, *, play_id: str | None = None) -> dict[str, Any]:
    """Normalize one check to the exact semantic shape emitted by a reasoner.

    Persisted checks replace ``play_id`` with a run-local candidate id.  Reconstituting the
    contract shape lets the store compare those rows with the immutable checks embedded in the
    reasoner result instead of trusting two caller-controlled representations independently.
    """
    data = _mapping(value, "candidate check")
    effective_play = play_id or _optional_text(data.get("play_id"))
    if effective_play is None:
        raise ValueError("candidate check play_id is required")
    return {
        "play_id": effective_play,
        "stage": _required_text(data, "stage"),
        "outcome": str(_enum_value(data.get("outcome") or "")),
        "reason_code": _required_text(data, "reason_code"),
        "evaluator_id": _required_text(data, "evaluator_id"),
        "evaluator_version": _required_text(data, "evaluator_version"),
        "detail": _mapping(data.get("detail") or {}, "candidate check detail"),
        "score_before_bp": data.get("score_before_bp"),
        "score_after_bp": data.get("score_after_bp"),
    }


def _typed_reasoner_result(value: Mapping[str, Any]):
    """Rebuild the public result contract from one prepared persistence row."""
    from genios_engine.contracts.reasoning import (
        CandidateAdjustment,
        CandidateCheck,
        Finding,
        ReasonerResult,
    )

    output = _decanonicalize(_mapping(value.get("output") or {}, "reasoner output"))
    return ReasonerResult(
        reasoner_id=_required_text(value, "reasoner_id"),
        reasoner_version=_required_text(value, "reasoner_version"),
        status=_required_text(value, "status"),
        matched=output.get("matched"),
        metrics=_mapping(output.get("metrics") or {}, "reasoner metrics"),
        findings=tuple(Finding(**_mapping(item, "finding")) for item in
                       _sequence(output.get("findings"), "reasoner findings")),
        adjustments=tuple(CandidateAdjustment(**_mapping(item, "candidate adjustment"))
                          for item in _sequence(output.get("adjustments"),
                                               "reasoner adjustments")),
        checks=tuple(CandidateCheck(**_mapping(item, "candidate check")) for item in
                     _sequence(output.get("checks"), "reasoner checks")),
        evidence_ids=tuple(_sequence(value.get("evidence_refs"), "reasoner evidence refs")),
        missing_fields=tuple(_sequence(output.get("missing_fields"), "reasoner missing fields")),
        reason_codes=tuple(_sequence(output.get("reason_codes"), "reasoner reason codes")),
        diagnostics=_mapping(value.get("diagnostics") or {}, "reasoner diagnostics"),
    )


def _topological_spec_ids(specs: Sequence[Mapping[str, Any]]) -> list[str]:
    """Mirror the registry's lexical Kahn ordering from persisted spec bytes."""
    by_id = {_required_text(spec, "reasoner_id"): spec for spec in specs}
    if len(by_id) != len(specs):
        raise ReplayIntegrityError("duplicate capability reasoner identity")
    indegree = {reasoner_id: 0 for reasoner_id in by_id}
    children = {reasoner_id: set() for reasoner_id in by_id}
    for reasoner_id, spec in by_id.items():
        for dependency in spec.get("dependencies") or []:
            dependency = str(dependency)
            if dependency not in by_id or dependency == reasoner_id:
                raise ReplayIntegrityError("invalid persisted reasoner dependency graph")
            if reasoner_id not in children[dependency]:
                children[dependency].add(reasoner_id)
                indegree[reasoner_id] += 1
    ready = [reasoner_id for reasoner_id, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    ordered: list[str] = []
    while ready:
        reasoner_id = heapq.heappop(ready)
        ordered.append(reasoner_id)
        for child in sorted(children[reasoner_id]):
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(ready, child)
    if len(ordered) != len(by_id):
        raise ReplayIntegrityError("cyclic persisted reasoner dependency graph")
    return ordered


def _validate_supplied_hash(data: Mapping[str, Any], key: str, actual: str) -> None:
    supplied = _optional_text(data.get(key))
    if supplied is not None and supplied != actual:
        raise ValueError(f"{key} does not match canonical content")


def _bp(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer basis-point value")
    if value < 0 or value > 10_000:
        raise ValueError(f"{label} must be between 0 and 10000")
    return value


def _integer(value: Any, label: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} must be at least {minimum}")
    return value


class ReasoningStore:
    """Tenant-scoped, content-addressed Layer 4 persistence."""

    def __init__(self, database_url: str | None = None, *, engine: Engine | None = None) -> None:
        if engine is None and not database_url:
            raise ValueError("database_url or engine is required")
        self._engine = engine or get_engine(str(database_url))

    @property
    def engine(self) -> Engine:
        return self._engine

    def _write_scope(self, conn=None):
        return nullcontext(conn) if conn is not None else self._engine.begin()

    def _read_scope(self, conn=None):
        return nullcontext(conn) if conn is not None else self._engine.connect()

    def put_capability_snapshot(self, *, org_id: str, capability: Any,
                                _conn=None) -> dict[str, Any]:
        """Persist immutable capability bytes before a context or run can reference them."""
        org_id = str(org_id).strip()
        if not org_id:
            raise ValueError("org_id is required")
        manifest = _mapping(capability, "capability")
        capability_id = _required_text(manifest, "capability_id")
        capability_version = _required_text(manifest, "version")
        manifest_hash = _semantic_hash(manifest)
        supplied_id = _optional_text(getattr(capability, "capability_snapshot_id", None))
        capability_snapshot_id = supplied_id or _stable_id("cap", manifest)
        if supplied_id is not None and supplied_id != _stable_id("cap", manifest):
            raise ValueError("capability_snapshot_id does not match manifest content")

        with self._write_scope(_conn) as conn:
            conn.execute(text(
                "insert into reasoning_capability_snapshots "
                "(org_id,capability_snapshot_id,capability_id,capability_version,manifest,"
                "manifest_hash) values (:o,:id,:cap,:v,cast(:m as jsonb),:h) "
                "on conflict do nothing"),
                {"o": org_id, "id": capability_snapshot_id, "cap": capability_id,
                 "v": capability_version, "m": _json_param(manifest), "h": manifest_hash})
            held = conn.execute(text(
                "select capability_snapshot_id, manifest, manifest_hash "
                "from reasoning_capability_snapshots "
                "where org_id=:o and capability_id=:cap and capability_version=:v"),
                {"o": org_id, "cap": capability_id, "v": capability_version}).first()
            if held is None:
                raise ReasoningStoreError("capability snapshot conflict could not be resolved")
            if (held.capability_snapshot_id != capability_snapshot_id
                    or held.manifest_hash != manifest_hash
                    or _encoded_semantic_hash(held.manifest) != manifest_hash):
                raise ReasoningStoreError(
                    f"immutable capability version mismatch: {capability_id}@{capability_version}")
        return {"org_id": org_id, "capability_snapshot_id": capability_snapshot_id,
                "capability_id": capability_id, "capability_version": capability_version,
                "manifest_hash": manifest_hash}

    def load_capability_snapshot(self, *, org_id: str,
                                 capability_snapshot_id: str) -> dict[str, Any] | None:
        if not org_id or not capability_snapshot_id:
            raise ValueError("org_id and capability_snapshot_id are required")
        with self._engine.connect() as conn:
            row = conn.execute(text(
                "select * from reasoning_capability_snapshots "
                "where org_id=:o and capability_snapshot_id=:id"),
                {"o": org_id, "id": capability_snapshot_id}).mappings().first()
        return self._decoded_row(row) if row is not None else None

    def put_context_snapshot(
        self,
        *,
        org_id: str,
        capability_id: str,
        capability_version: str,
        capability_snapshot_id: str,
        graph_version: int,
        evaluation_time: datetime | str,
        selector_version: str,
        selector: Mapping[str, Any] | Any,
        payload: Mapping[str, Any] | Any,
        root_node_id: str | None = None,
        root_node_type: str | None = None,
        source_manifest: Sequence[Any] | None = None,
        expires_at: datetime | str | None = None,
        schema_version: int = 2,
        item_count: int | None = None,
        _conn=None,
    ) -> dict[str, Any]:
        """Persist or recover one immutable bounded context snapshot.

        ``payload`` must be self-contained for replay; the graph is never queried
        during replay.  Its row can later be purged by retention without deleting
        the snapshot's non-content hash/provenance metadata.
        """
        org_id = str(org_id).strip()
        capability_id = str(capability_id).strip()
        capability_version = str(capability_version).strip()
        capability_snapshot_id = str(capability_snapshot_id).strip()
        selector_version = str(selector_version).strip()
        if not all((org_id, capability_id, capability_version,
                    capability_snapshot_id, selector_version)):
            raise ValueError("org/capability/snapshot/selector identifiers are required")
        graph_version = _integer(graph_version, "graph_version", minimum=0)
        schema_version = _integer(schema_version, "schema_version", minimum=1)
        if schema_version not in {1, 2}:
            raise ValueError("unsupported context snapshot schema version")

        eval_time = _aware_datetime(evaluation_time, "evaluation_time")
        expiry = _aware_datetime(expires_at, "expires_at") if expires_at is not None else None
        selector_obj = _mapping(selector, "selector")
        payload_obj = _mapping(payload, "payload")
        sources = _sequence(source_manifest, "source_manifest")
        root_node_id = _optional_text(root_node_id)
        root_node_type = _optional_text(root_node_type) or _optional_text(
            payload_obj.get("root_entity_type"))
        if root_node_id is None or root_node_type is None:
            raise ContextSnapshotMismatch(
                "context snapshot requires a bound root entity id and type")

        # The replay payload is authority-bearing input, not an opaque JSON attachment.  Prove
        # every duplicated identity field before hashing or storing it so a caller cannot bind
        # another tenant/root/graph epoch to otherwise plausible row metadata.
        if _optional_text(payload_obj.get("org_id")) != org_id:
            raise ContextSnapshotMismatch("context payload tenant differs from row metadata")
        if _integer(payload_obj.get("graph_version"), "payload graph_version", minimum=0) \
                != graph_version:
            raise ContextSnapshotMismatch("context payload graph version differs from row metadata")
        if _optional_text(payload_obj.get("root_entity_id")) != root_node_id:
            raise ContextSnapshotMismatch("context payload root id differs from row metadata")
        if _optional_text(payload_obj.get("root_entity_type")) != root_node_type:
            raise ContextSnapshotMismatch("context payload root type differs from row metadata")
        if _aware_datetime(payload_obj.get("evaluation_time"), "payload evaluation_time") \
                != eval_time:
            raise ContextSnapshotMismatch("context payload evaluation time differs from row metadata")
        if _optional_text(payload_obj.get("selector_version")) != selector_version:
            raise ContextSnapshotMismatch(
                "context payload selector version differs from row metadata")
        if item_count is None:
            items = payload_obj.get("items")
            count = len(items) if isinstance(items, list) else 0
        else:
            count = _integer(item_count, "item_count", minimum=0)

        selector_hash = _semantic_hash(selector_obj)
        payload_hash = _semantic_hash(payload_obj)
        context_material = {
            "schema_version": schema_version,
            "org_id": org_id,
            "capability_id": capability_id,
            "capability_version": capability_version,
            "capability_snapshot_id": capability_snapshot_id,
            "root_node_id": root_node_id,
            "graph_version": graph_version,
            "evaluation_time": eval_time,
            "selector_version": selector_version,
            "selector_hash": selector_hash,
            "payload_hash": payload_hash,
            "source_manifest": sources,
        }
        if schema_version >= 2:
            context_material["root_node_type"] = root_node_type
        context_hash = _semantic_hash(context_material)
        snapshot_id = _stable_id("ctx", {"org_id": org_id, "context_hash": context_hash})

        with self._write_scope(_conn) as conn:
            inserted = conn.execute(text(
                "insert into reasoning_context_snapshots ("
                "org_id, context_snapshot_id, capability_id, capability_version, "
                "capability_snapshot_id, root_node_id, root_node_type, graph_version, evaluation_time, "
                "selector_version, selector, selector_hash, payload_hash, context_hash, "
                "source_manifest, "
                "item_count, schema_version) values ("
                ":o,:id,:cap,:cv,:cs,:root,:root_type,:gv,:et,:sv,cast(:selector as jsonb),:sh,:ph,:ch,"
                "cast(:sm as jsonb),:ic,:schema) "
                "on conflict (org_id, context_hash) do nothing returning context_snapshot_id"),
                {"o": org_id, "id": snapshot_id, "cap": capability_id, "cv": capability_version,
                 "cs": capability_snapshot_id, "root": root_node_id,
                 "root_type": root_node_type, "gv": graph_version,
                 "et": eval_time, "sv": selector_version,
                 "selector": _json_param(selector_obj), "sh": selector_hash,
                 "ph": payload_hash, "ch": context_hash, "sm": _json_param(sources),
                 "ic": count, "schema": schema_version}).first()
            if inserted is None:
                held = conn.execute(text(
                    "select context_snapshot_id, payload_hash, selector, selector_hash, capability_id, "
                    "capability_version, capability_snapshot_id, root_node_id, root_node_type, "
                    "graph_version, evaluation_time "
                    "from reasoning_context_snapshots where org_id=:o and context_hash=:h"),
                    {"o": org_id, "h": context_hash}).first()
                if held is None:
                    raise ReasoningStoreError("context snapshot conflict could not be resolved")
                held_selector = held.selector
                if held_selector is None:
                    # Upgrade an older pre-selector-byte snapshot only when the
                    # incoming bytes prove the already-held selector hash.
                    filled = conn.execute(text(
                        "update reasoning_context_snapshots set selector=cast(:selector as jsonb) "
                        "where org_id=:o and context_snapshot_id=:id and selector is null "
                        "and selector_hash=:sh returning selector"),
                        {"o": org_id, "id": snapshot_id, "sh": selector_hash,
                         "selector": _json_param(selector_obj)}).first()
                    if filled is None:
                        raise ContextSnapshotMismatch(
                            "historical context selector could not be restored")
                    held_selector = filled.selector
                snapshot_id = held.context_snapshot_id
                if (held.payload_hash != payload_hash or held.selector_hash != selector_hash
                        or _encoded_semantic_hash(held_selector) != selector_hash
                        or held.capability_id != capability_id
                        or held.capability_version != capability_version
                        or held.capability_snapshot_id != capability_snapshot_id
                        or held.root_node_id != root_node_id
                        or held.root_node_type != root_node_type
                        or int(held.graph_version) != graph_version
                        or held.evaluation_time.astimezone(timezone.utc) != eval_time):
                    raise ContextSnapshotMismatch("context hash resolved to different metadata")

            conn.execute(text(
                "insert into reasoning_context_payloads "
                "(org_id, context_snapshot_id, payload, expires_at) "
                "values (:o,:id,cast(:p as jsonb),:exp) "
                "on conflict (org_id, context_snapshot_id) do nothing"),
                {"o": org_id, "id": snapshot_id, "p": _json_param(payload_obj), "exp": expiry})
            held_payload = conn.execute(text(
                "select payload from reasoning_context_payloads "
                "where org_id=:o and context_snapshot_id=:id"),
                {"o": org_id, "id": snapshot_id}).first()
            if (held_payload is None
                    or _encoded_semantic_hash(held_payload.payload) != payload_hash):
                raise ContextSnapshotMismatch("stored context payload does not match payload_hash")

        return {
            "org_id": org_id,
            "context_snapshot_id": snapshot_id,
            "context_hash": context_hash,
            "payload_hash": payload_hash,
            "selector_hash": selector_hash,
            "graph_version": graph_version,
            "evaluation_time": eval_time,
        }

    def persist_complete(
        self,
        *,
        org_id: str,
        run: Mapping[str, Any] | Any,
        reasoner_results: Sequence[Any],
        candidates: Sequence[Any],
        candidate_checks: Sequence[Any],
        output: Mapping[str, Any] | Any,
        _conn=None,
    ) -> dict[str, Any]:
        """Atomically persist one complete authoritative reasoning bundle.

        The method performs semantic validation before opening the transaction.
        If another worker already committed the same ``idempotency_key``, its
        bundle is returned only when the canonical input and output hashes agree.
        """
        org_id = str(org_id).strip()
        if not org_id:
            raise ValueError("org_id is required")
        run_obj = _mapping(run, "run")
        result_objs = [_mapping(v, "reasoner_result") for v in
                       _sequence(reasoner_results, "reasoner_results")]
        candidate_objs = []
        for candidate in _sequence(candidates, "candidates"):
            item = _mapping(candidate, "candidate")
            # DecisionCandidate exposes candidate_id as a deterministic
            # property, not a dataclass field.  Preserve it so a
            # ReasoningDecision can reference the same persistence handle.
            contract_id = getattr(candidate, "candidate_id", None)
            if contract_id is not None:
                item.setdefault("candidate_id", contract_id)
            candidate_objs.append(item)
        check_objs = [_mapping(v, "candidate_check") for v in
                      _sequence(candidate_checks, "candidate_checks")]
        output_obj = _mapping(output, "output")

        idempotency_key = _required_text(run_obj, "idempotency_key")
        capability_id = _required_text(run_obj, "capability_id")
        capability_version = _required_text(run_obj, "capability_version")
        capability_snapshot_id = _required_text(run_obj, "capability_snapshot_id")
        context_snapshot_id = _required_text(run_obj, "context_snapshot_id")
        trigger_kind = _required_text(run_obj, "trigger_kind")
        mode = str(_enum_value(run_obj.get("mode") or "live"))
        evaluation_time = _aware_datetime(run_obj.get("evaluation_time"), "evaluation_time")
        input_manifest = _mapping(run_obj.get("input_manifest") or {}, "input_manifest")
        reasoner_plan = _sequence(run_obj.get("reasoner_plan"), "reasoner_plan")
        orchestrator_version = _required_text(run_obj, "orchestrator_version")
        engine_build = _required_text(run_obj, "engine_build")
        config_snapshot_id = _optional_text(run_obj.get("config_snapshot_id"))
        policy_snapshot_id = _optional_text(run_obj.get("policy_snapshot_id"))
        replay_of_run_id = _optional_text(run_obj.get("replay_of_run_id"))
        supersedes_run_id = _optional_text(run_obj.get("supersedes_run_id"))
        root_node_id = _optional_text(run_obj.get("root_node_id"))

        if trigger_kind not in {"event", "query", "schedule", "manual", "replay"}:
            raise ValueError("invalid trigger_kind")
        if mode not in {"live", "shadow", "simulation", "replay"}:
            raise ValueError("invalid reasoning mode")
        if mode == "replay" and not replay_of_run_id:
            raise ValueError("replay mode requires replay_of_run_id")

        reasoner_plan_hash = _semantic_hash(reasoner_plan)
        trigger_ref = _optional_text(run_obj.get("trigger_ref"))
        input_hash = _semantic_hash({
            "org_id": org_id,
            "context_snapshot_id": context_snapshot_id,
            "capability_snapshot_id": capability_snapshot_id,
            "config_snapshot_id": config_snapshot_id,
            "policy_snapshot_id": policy_snapshot_id,
            "root_node_id": root_node_id,
            "evaluation_time": evaluation_time,
            "trigger_kind": trigger_kind,
            "trigger_ref": trigger_ref,
            "mode": mode,
            "replay_of_run_id": replay_of_run_id,
            "supersedes_run_id": supersedes_run_id,
            "input_manifest": input_manifest,
            "reasoner_plan_hash": reasoner_plan_hash,
            "orchestrator_version": orchestrator_version,
            "engine_build": engine_build,
        })
        _validate_supplied_hash(run_obj, "input_hash", input_hash)
        _validate_supplied_hash(run_obj, "reasoner_plan_hash", reasoner_plan_hash)
        run_id = _optional_text(run_obj.get("run_id")) or _stable_id(
            "rrun", {"org_id": org_id, "idempotency_key": idempotency_key})

        results = self._prepare_results(run_id, input_hash, result_objs)
        prepared_candidates = self._prepare_candidates(run_id, candidate_objs)
        prepared_checks = self._prepare_checks(run_id, check_objs, prepared_candidates)
        prepared_output = self._prepare_output(run_id, output_obj,
                                               prepared_candidates, prepared_checks)
        output_hash = _semantic_hash({
            "reasoner_results": [r["output_hash"] for r in sorted(results, key=lambda x: x["ordinal"])],
            "candidates": [c["candidate_hash"] for c in
                           sorted(prepared_candidates, key=lambda x: x["candidate_id"])],
            "checks": [c["check_hash"] for c in
                       sorted(prepared_checks, key=lambda x: (x["candidate_id"], x["ordinal"]))],
            "decision_hash": prepared_output["decision_hash"],
        })
        _validate_supplied_hash(run_obj, "output_hash", output_hash)

        inserted_run = False
        with self._write_scope(_conn) as conn:
            preexisting = conn.execute(text(
                "select run_id, input_hash, output_hash from reasoning_runs "
                "where org_id=:o and idempotency_key=:k for share"),
                {"o": org_id, "k": idempotency_key}).first()
            if (preexisting is not None
                    and (preexisting.input_hash != input_hash
                         or preexisting.output_hash != output_hash)):
                raise IdempotencyConflict(
                    "idempotency_key already belongs to different reasoning content")
            context = conn.execute(text(
                "select capability_id, capability_version, capability_snapshot_id, root_node_id, "
                "root_node_type, "
                "evaluation_time, context_hash from reasoning_context_snapshots "
                "where org_id=:o and context_snapshot_id=:id"),
                {"o": org_id, "id": context_snapshot_id}).first()
            if context is None:
                raise ContextSnapshotMismatch("context snapshot does not belong to this tenant")
            if (context.capability_id != capability_id
                    or context.capability_version != capability_version
                    or context.capability_snapshot_id != capability_snapshot_id
                    or context.evaluation_time.astimezone(timezone.utc) != evaluation_time
                    or (root_node_id is not None and context.root_node_id != root_node_id)):
                raise ContextSnapshotMismatch("run metadata differs from its context snapshot")
            payload_row = conn.execute(text(
                "select payload from reasoning_context_payloads "
                "where org_id=:o and context_snapshot_id=:id"),
                {"o": org_id, "id": context_snapshot_id}).first()
            if payload_row is None:
                raise ContextPayloadExpired(context_snapshot_id)
            capability_row = conn.execute(text(
                "select manifest from reasoning_capability_snapshots "
                "where org_id=:o and capability_snapshot_id=:id"),
                {"o": org_id, "id": capability_snapshot_id}).first()
            if capability_row is None:
                raise ContextSnapshotMismatch(
                    "capability snapshot does not belong to this tenant")
            manifest = _decanonicalize(_json_value(capability_row.manifest))
            if not isinstance(manifest, Mapping):
                raise ContextSnapshotMismatch("capability manifest bytes are invalid")
            if (_required_text(manifest, "capability_id") != capability_id
                    or _required_text(manifest, "version") != capability_version
                    or _required_text(manifest, "root_entity_type") != context.root_node_type):
                raise ContextSnapshotMismatch(
                    "capability manifest identity/root type differs from run context")
            expected_policy_snapshot_id = _stable_id("policy", {
                "capability_id": capability_id,
                "capability_version": capability_version,
                "policies": manifest.get("policies") or [],
            })
            if policy_snapshot_id != expected_policy_snapshot_id:
                raise ReasoningStoreError(
                    "policy_snapshot_id does not match immutable capability policy bytes")
            manifest_specs = [_decanonicalize(_mapping(item, "reasoner spec")) for item in
                              _sequence(manifest.get("reasoners"), "capability reasoners")]
            expected_plan = _topological_spec_ids(manifest_specs)
            if reasoner_plan != expected_plan:
                raise ReasoningStoreError("reasoner plan differs from capability DAG")
            ordered_results = sorted(results, key=lambda item: item["ordinal"])
            if len(ordered_results) != len(manifest_specs):
                raise ReasoningStoreError("reasoner results do not cover the capability DAG")
            spec_by_id = {_required_text(item, "reasoner_id"): item for item in manifest_specs}
            if len(spec_by_id) != len(manifest_specs):
                raise ReasoningStoreError("capability DAG contains duplicate reasoner identity")
            request_hash = _required_text(input_manifest, "request_hash")
            contract_results: dict[str, dict[str, Any]] = {}
            for ordinal, result in enumerate(ordered_results):
                reasoner_id = result["reasoner_id"]
                spec = spec_by_id.get(reasoner_id)
                if (result["ordinal"] != ordinal or spec is None
                        or expected_plan[ordinal] != reasoner_id
                        or result["reasoner_version"] != spec.get("version")):
                    raise ReasoningStoreError(
                        "reasoner result order/identity/version differs from capability DAG")
                output = result["output"]
                contract_result = {
                    "reasoner_id": reasoner_id,
                    "reasoner_version": result["reasoner_version"],
                    "status": result["status"],
                    "matched": output.get("matched"),
                    "metrics": output.get("metrics") or {},
                    "findings": output.get("findings") or [],
                    "adjustments": output.get("adjustments") or [],
                    "checks": output.get("checks") or [],
                    "evidence_ids": result["evidence_refs"],
                    "missing_fields": output.get("missing_fields") or [],
                    "reason_codes": output.get("reason_codes") or [],
                }
                dependencies = {
                    dependency_id: contract_results[dependency_id]
                    for dependency_id in spec.get("dependencies") or []
                    if dependency_id in contract_results
                }
                expected_result_input_hash = _semantic_hash({
                    "request_hash": request_hash,
                    "spec": spec,
                    "dependencies": dependencies,
                })
                if result["input_hash"] != expected_result_input_hash:
                    raise ReasoningStoreError(
                        "reasoner result input hash differs from declared DAG dependencies")
                if (prepared_output["outcome_kind"] == "decision"
                        and str(spec.get("failure_policy") or "required") == "required"
                        and result["status"] != "completed"):
                    raise ReasoningStoreError(
                        "a required reasoner did not complete for a live decision")
                if (prepared_output["outcome_kind"] == "decision" and spec.get("gating") is True
                        and (result["status"] != "completed" or output.get("matched") is not True)):
                    raise ReasoningStoreError(
                        "a live decision cannot bypass a non-matching gating reasoner")
                if result["status"] != "completed" and output.get("checks"):
                    raise ReasoningStoreError(
                        "a non-completed reasoner cannot contribute candidate checks")
                contract_results[reasoner_id] = contract_result

            declared_plays = {
                (_required_text(item, "play_id"), _required_text(item, "version")): item
                for item in (_decanonicalize(_mapping(play, "declared play")) for play in
                             _sequence(manifest.get("plays"), "capability plays"))
            }
            for candidate in prepared_candidates:
                declared = declared_plays.get((candidate["play_id"], candidate["play_version"]))
                if declared is None:
                    raise ReasoningStoreError("candidate play is absent from capability manifest")
                if candidate["parameters"].get("read_only") is not declared.get("read_only"):
                    raise ReasoningStoreError(
                        "candidate read_only effect differs from its declared play")
            if prepared_output["outcome_kind"] in {"decision", "blocked"}:
                candidate_plays = {(item["play_id"], item["play_version"])
                                   for item in prepared_candidates}
                if (candidate_plays != set(declared_plays)
                        or len(prepared_candidates) != len(declared_plays)):
                    raise ReasoningStoreError(
                        "reasoning candidates must cover every declared play exactly once")

            # Candidate-check rows are an index over the immutable reasoner outputs.  Require exact
            # multiset equality so callers cannot forge a pass, hide an elimination, or duplicate a
            # generic check to satisfy several policies.
            embedded_checks = [
                _contract_check(check)
                for result in ordered_results
                for check in _sequence(result["output"].get("checks"), "reasoner checks")
            ]
            candidate_by_id = {item["candidate_id"]: item for item in prepared_candidates}
            persisted_checks = [
                _contract_check(
                    check, play_id=candidate_by_id[check["candidate_id"]]["play_id"])
                for check in prepared_checks
            ]
            if (sorted(_semantic_hash(item) for item in embedded_checks)
                    != sorted(_semantic_hash(item) for item in persisted_checks)):
                raise ReasoningStoreError(
                    "candidate checks differ from immutable reasoner result effects")

            if prepared_output["outcome_kind"] in {"decision", "blocked"}:
                # Recompute the deterministic candidate/rank projection from the immutable
                # manifest, context and reasoner effects.  Child rows cannot independently assert
                # a 10,000 utility winner when the reasoners produced a gate miss, elimination or
                # lower score.
                from types import SimpleNamespace

                from genios_engine.reason.decision_maker import build_candidates
                from genios_engine.reason.guards import (
                    required_missing,
                    validate_candidate_effects,
                    validate_evidence_references,
                )
                from genios_engine.reason.replay import (
                    capability_from_manifest,
                    context_from_payload,
                )

                typed_capability = capability_from_manifest(manifest)
                typed_context = context_from_payload(_decanonicalize(
                    _mapping(_json_value(payload_row.payload), "context payload")))
                request_view = SimpleNamespace(
                    capability=typed_capability, context=typed_context)
                if required_missing(request_view, typed_capability.required_fields):
                    raise ReasoningStoreError(
                        "a decision/blocked outcome cannot bypass required context")
                typed_results = [_typed_reasoner_result(item) for item in ordered_results]
                for typed_result in typed_results:
                    validate_candidate_effects(
                        typed_result, {play.play_id for play in typed_capability.plays})
                    validate_evidence_references(typed_result, request_view)
                degraded = any(
                    str(spec_by_id[item.reasoner_id].get("failure_policy") or "required")
                    == "optional" and item.status.value in {"failed", "insufficient_context"}
                    for item in typed_results
                )
                derived_candidates, derived_confidence = build_candidates(
                    request_view, typed_results, degraded)
                expected_outcome = ("decision" if any(
                    item.disposition.value == "eligible" for item in derived_candidates)
                                    else "blocked")
                if prepared_output["outcome_kind"] != expected_outcome:
                    raise ReasoningStoreError(
                        "persisted outcome differs from deterministic reasoner effects")

                checks_by_candidate: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
                for check in prepared_checks:
                    checks_by_candidate[check["candidate_id"]].append(check)
                prepared_contract_candidates: list[dict[str, Any]] = []
                for candidate in prepared_candidates:
                    if (candidate["initial_utility_bp"] != candidate["final_utility_bp"]):
                        raise ReasoningStoreError(
                            "candidate utility cannot diverge from its deterministic projection")
                    contract_checks = [
                        _contract_check(check, play_id=candidate["play_id"])
                        for check in sorted(checks_by_candidate[candidate["candidate_id"]],
                                            key=lambda item: item["ordinal"])
                    ]
                    prepared_contract_candidates.append({
                        "play_id": candidate["play_id"],
                        "play_version": candidate["play_version"],
                        "disposition": candidate["disposition"],
                        "utility_bp": candidate["final_utility_bp"],
                        "confidence_bp": candidate["confidence_bp"],
                        "score_components": candidate["score_components"],
                        "rank_position": candidate["rank_position"],
                        "checks": contract_checks,
                        "evidence_ids": candidate["evidence_refs"],
                        "parameters": candidate["parameters"],
                    })
                if ([_semantic_hash(item) for item in prepared_contract_candidates]
                        != [item.semantic_hash for item in derived_candidates]):
                    raise ReasoningStoreError(
                        "candidate values/ranks differ from deterministic reasoner effects")
                if prepared_output["confidence_bp"] != derived_confidence:
                    raise ReasoningStoreError(
                        "decision confidence differs from deterministic reasoner effects")
                derived_selected_index = next((index for index, item in
                                               enumerate(derived_candidates)
                                               if item.rank_position == 1), None)
                expected_selected_id = (prepared_candidates[derived_selected_index]["candidate_id"]
                                        if derived_selected_index is not None else None)
                if prepared_output["selected_candidate_id"] != expected_selected_id:
                    raise ReasoningStoreError(
                        "selected candidate differs from deterministic rank one")

            if prepared_output["outcome_kind"] == "decision":
                selected_id = prepared_output["selected_candidate_id"]
                policies = _sequence(manifest.get("policies"), "capability policies")
                constraint_spec = spec_by_id.get("core.constraint")
                if policies and constraint_spec is None:
                    raise ReasoningStoreError("capability policies require core.constraint")
                for policy in policies:
                    requirement = _POLICY_CHECK_REQUIREMENTS.get(str(policy))
                    if requirement is None:
                        raise ReasoningStoreError(f"unsupported persisted policy: {policy}")
                    stage, reason_code = requirement
                    matches = [
                        check for check in prepared_checks
                        if check["candidate_id"] == selected_id
                        and check["stage"] == stage
                        and check["reason_code"] == reason_code
                        and check["evaluator_id"] == "core.constraint"
                        and check["evaluator_version"] == constraint_spec.get("version")
                        and check["outcome"] == "pass"
                    ]
                    if len(matches) != 1:
                        raise ReasoningStoreError(
                            f"selected play lacks one exact passing check for policy {policy}")
            if config_snapshot_id is not None:
                config = conn.execute(text(
                    "select snapshot_id,pack_id,effective from config_snapshots "
                    "where org_id=:o and snapshot_id=:id"),
                    {"o": org_id, "id": config_snapshot_id}).first()
                if config is None:
                    raise ConfigSnapshotMismatch(
                        "config/capability snapshot does not belong to this tenant")
                effective = _json_value(config.effective)
                if not isinstance(effective, Mapping) or not isinstance(manifest, Mapping):
                    raise ConfigSnapshotMismatch("config/capability snapshot bytes are invalid")
                config_pack = str(config.pack_id or "")
                effective_pack = str(effective.get("pack_id") or "")
                capability_pack = str(manifest.get("domain") or "")
                metadata = manifest.get("metadata") or {}
                legacy_pack = (str(metadata.get("pack_id") or "")
                               if isinstance(metadata, Mapping) else "")
                legacy_version = (str(metadata.get("pack_version") or "")
                                  if isinstance(metadata, Mapping) else "")
                legacy_config = (str(metadata.get("config_snapshot_id") or "")
                                 if isinstance(metadata, Mapping) else "")
                recomputed_config_id = effective_config_snapshot_id(
                    _decanonicalize(dict(effective)))
                if (config.snapshot_id != recomputed_config_id
                        or config_snapshot_id != recomputed_config_id
                        or not config_pack or config_pack != effective_pack
                        or config_pack != capability_pack
                        or (str(capability_id).startswith("legacy.")
                            and (legacy_pack != config_pack
                                 or legacy_version != str(effective.get("version") or "")
                                 or legacy_config != config_snapshot_id))):
                    raise ConfigSnapshotMismatch(
                        "capability domain does not match the effective config pack")

            row = conn.execute(text(
                "insert into reasoning_runs (org_id, run_id, idempotency_key, capability_id, "
                "capability_version, capability_snapshot_id, context_snapshot_id, "
                "config_snapshot_id, policy_snapshot_id, trigger_kind, trigger_ref, root_node_id, "
                "mode, status, evaluation_time, input_manifest, input_hash, reasoner_plan, "
                "reasoner_plan_hash, orchestrator_version, engine_build, output_hash, "
                "replay_of_run_id, supersedes_run_id) values ("
                ":o,:id,:ik,:cap,:cv,:cs,:ctx,:cfg,:policy,:tk,:tr,:root,:mode,'completed',:et,"
                "cast(:im as jsonb),:ih,cast(:rp as jsonb),:rph,:ov,:eb,:oh,:replay,:supersedes) "
                "on conflict (org_id, idempotency_key) do nothing returning run_id"),
                {"o": org_id, "id": run_id, "ik": idempotency_key, "cap": capability_id,
                 "cv": capability_version, "cs": capability_snapshot_id, "ctx": context_snapshot_id,
                 "cfg": config_snapshot_id, "policy": policy_snapshot_id, "tk": trigger_kind,
                 "tr": trigger_ref, "root": root_node_id,
                 "mode": mode, "et": evaluation_time, "im": _json_param(input_manifest),
                 "ih": input_hash, "rp": _json_param(reasoner_plan), "rph": reasoner_plan_hash,
                 "ov": orchestrator_version, "eb": engine_build, "oh": output_hash,
                 "replay": replay_of_run_id, "supersedes": supersedes_run_id}).first()
            if row is None:
                held = conn.execute(text(
                    "select run_id, input_hash, output_hash from reasoning_runs "
                    "where org_id=:o and idempotency_key=:k"),
                    {"o": org_id, "k": idempotency_key}).first()
                if held is None:
                    raise ReasoningStoreError("idempotent run conflict could not be resolved")
                if held.input_hash != input_hash or held.output_hash != output_hash:
                    raise IdempotencyConflict(
                        "idempotency_key already belongs to different reasoning content")
                run_id = held.run_id
            else:
                inserted_run = True
                self._insert_results(conn, org_id, run_id, results)
                self._insert_candidates(conn, org_id, run_id, prepared_candidates)
                self._insert_checks(conn, org_id, run_id, prepared_checks)
                self._insert_output(conn, org_id, run_id, prepared_output)

        bundle = self.load_bundle(org_id=org_id, run_id=run_id, _conn=_conn)
        if bundle is None:
            raise ReasoningStoreError("completed bundle could not be loaded")
        bundle["idempotent_reuse"] = not inserted_run
        return bundle

    def _prepare_results(self, run_id: str, run_input_hash: str,
                         values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen_ordinals: set[int] = set()
        seen_invocations: set[tuple[str, str]] = set()
        for index, value in enumerate(values):
            ordinal = _integer(value.get("ordinal", index), "reasoner ordinal", minimum=0)
            reasoner_id = _required_text(value, "reasoner_id")
            reasoner_version = _required_text(value, "reasoner_version")
            invocation_key = str(value.get("invocation_key") or "default")
            status = str(_enum_value(value.get("status") or "completed"))
            skip_reason_code = _optional_text(value.get("skip_reason_code"))
            if ordinal in seen_ordinals:
                raise ValueError("reasoner result ordinals must be unique and non-negative")
            if (reasoner_id, invocation_key) in seen_invocations:
                raise ValueError("duplicate reasoner invocation")
            if status not in {"completed", "skipped", "failed", "insufficient_context"}:
                raise ValueError("invalid reasoner result status")
            seen_ordinals.add(ordinal)
            seen_invocations.add((reasoner_id, invocation_key))
            if "output" in value:
                output = _mapping(value.get("output") or {}, "reasoner output")
            else:
                # Native ReasonerResult keeps its semantic output as typed
                # fields rather than under an `output` key.
                output = {key: value[key] for key in (
                    "matched", "metrics", "findings", "adjustments", "checks",
                    "missing_fields", "reason_codes") if key in value}
            evidence_refs = _sequence(
                value.get("evidence_refs", value.get("evidence_ids")), "evidence_refs")
            diagnostics = _mapping(value.get("diagnostics") or {}, "diagnostics")
            input_hash = _optional_text(value.get("input_hash")) or _semantic_hash({
                "run_input_hash": run_input_hash,
                "reasoner_id": reasoner_id,
                "reasoner_version": reasoner_version,
                "invocation_key": invocation_key,
            })
            material = {
                "ordinal": ordinal,
                "reasoner_id": reasoner_id,
                "reasoner_version": reasoner_version,
                "invocation_key": invocation_key,
                "status": status,
                "input_hash": input_hash,
                "output": output,
                "evidence_refs": evidence_refs,
                "skip_reason_code": skip_reason_code,
                "error_code": _optional_text(value.get("error_code")),
            }
            output_hash = _semantic_hash(material)
            _validate_supplied_hash(value, "output_hash", output_hash)
            out.append({**material, "diagnostics": diagnostics, "output_hash": output_hash,
                        "result_id": _optional_text(value.get("result_id")) or
                                     _stable_id("rres", {"run_id": run_id,
                                                         "output_hash": output_hash})})
        return out

    def _prepare_candidates(self, run_id: str,
                            values: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        ids: set[str] = set()
        hashes: set[str] = set()
        ranks: set[int] = set()
        for value in values:
            play_id = _required_text(value, "play_id")
            play_version = _required_text(value, "play_version")
            parameters = _mapping(value.get("parameters") or {}, "candidate parameters")
            score_components = _mapping(value.get("score_components") or {}, "score_components")
            score_components = {
                key: _bp(component, f"score_components.{key}")
                for key, component in score_components.items()
            }
            disposition = str(_enum_value(value.get("disposition") or "eligible"))
            if disposition not in {"eligible", "eliminated"}:
                raise ValueError("candidate disposition must be eligible or eliminated")
            rank_position = value.get("rank_position")
            if rank_position is not None:
                rank_position = _integer(rank_position, "candidate rank", minimum=1)
                if rank_position in ranks:
                    raise ValueError("candidate ranks must be positive and unique")
                ranks.add(rank_position)
            confidence_bp = _bp(value.get("confidence_bp"), "candidate confidence_bp")
            evidence_refs = _sequence(
                value.get("evidence_refs", value.get("evidence_ids")),
                "candidate evidence_refs")
            initial_utility = value.get("initial_utility_bp")
            if initial_utility is None:
                initial_utility = value.get("utility_bp")
            final_utility = value.get("final_utility_bp")
            if final_utility is None:
                final_utility = value.get("utility_bp")
            material = {
                "play_id": play_id,
                "play_version": play_version,
                "parameters": parameters,
                "score_components": score_components,
                "initial_utility_bp": _bp(initial_utility, "candidate initial_utility_bp"),
                "final_utility_bp": (_bp(final_utility, "candidate final_utility_bp")
                                     if final_utility is not None else None),
                "confidence_bp": confidence_bp,
                "disposition": disposition,
                "rank_position": rank_position,
                "evidence_refs": evidence_refs,
            }
            candidate_hash = _semantic_hash(material)
            _validate_supplied_hash(value, "candidate_hash", candidate_hash)
            # Contract candidate IDs are semantic and therefore repeat across a
            # replay.  The DB primary key is tenant-wide, so persistence IDs must
            # also include the run.  Preserve the contract/caller ID as an alias
            # for checks and decision selection.
            external_candidate_id = _optional_text(value.get("candidate_id"))
            candidate_id = _stable_id(
                "cand", {"run_id": run_id, "candidate_hash": candidate_hash})
            if candidate_id in ids or candidate_hash in hashes:
                raise ValueError("duplicate reasoning candidate")
            ids.add(candidate_id)
            hashes.add(candidate_hash)
            out.append({**material, "candidate_hash": candidate_hash,
                        "candidate_id": candidate_id,
                        "external_candidate_id": external_candidate_id})
        return out

    def _prepare_checks(self, run_id: str, values: list[dict[str, Any]],
                        candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        candidate_by_id = {c["candidate_id"]: c for c in candidates}
        candidate_aliases = dict(candidate_by_id)
        for candidate in candidates:
            alias = candidate.get("external_candidate_id")
            if alias:
                if alias in candidate_aliases and candidate_aliases[alias] is not candidate:
                    raise ValueError("duplicate external candidate_id")
                candidate_aliases[alias] = candidate
        candidates_by_play: defaultdict[str, list[str]] = defaultdict(list)
        for candidate in candidates:
            candidates_by_play[candidate["play_id"]].append(candidate["candidate_id"])
        next_ordinal: defaultdict[str, int] = defaultdict(int)
        seen: set[tuple[str, int]] = set()
        out: list[dict[str, Any]] = []
        eliminated: set[str] = set()
        for value in values:
            candidate_id = _optional_text(value.get("candidate_id"))
            if candidate_id is not None:
                candidate = candidate_aliases.get(candidate_id)
                candidate_id = candidate["candidate_id"] if candidate is not None else candidate_id
            if candidate_id is None:
                play_id = _optional_text(value.get("play_id"))
                matches = candidates_by_play.get(play_id or "", [])
                if len(matches) != 1:
                    raise ValueError(
                        "candidate check requires candidate_id when play_id is not unique")
                candidate_id = matches[0]
            if candidate_id not in candidate_by_id:
                raise ValueError("candidate check references an unknown candidate")
            ordinal = _integer(value.get("ordinal", next_ordinal[candidate_id]),
                               "candidate-check ordinal", minimum=0)
            next_ordinal[candidate_id] = max(next_ordinal[candidate_id], ordinal + 1)
            if (candidate_id, ordinal) in seen:
                raise ValueError("candidate check ordinals must be unique and non-negative")
            seen.add((candidate_id, ordinal))
            stage = _required_text(value, "stage")
            outcome = str(_enum_value(value.get("outcome") or ""))
            if not outcome:
                raise ValueError("outcome is required")
            if stage not in {"precondition", "constraint", "policy", "permission",
                             "safety", "cost_benefit", "ranking"}:
                raise ValueError("invalid candidate-check stage")
            if outcome not in {"pass", "warn", "eliminate", "adjust"}:
                raise ValueError("invalid candidate-check outcome")
            if outcome == "eliminate":
                eliminated.add(candidate_id)
            detail = _mapping(value.get("detail") or {}, "candidate-check detail")
            material = {
                # IDs are persistence handles and may differ in a replay run.  The
                # check hash follows the candidate's semantic hash instead.
                "candidate_hash": candidate_by_id[candidate_id]["candidate_hash"],
                "ordinal": ordinal,
                "stage": stage,
                "evaluator_id": _required_text(value, "evaluator_id"),
                "evaluator_version": _required_text(value, "evaluator_version"),
                "outcome": outcome,
                "reason_code": _required_text(value, "reason_code"),
                "score_before_bp": (_bp(value["score_before_bp"], "score_before_bp")
                                    if value.get("score_before_bp") is not None else None),
                "score_after_bp": (_bp(value["score_after_bp"], "score_after_bp")
                                   if value.get("score_after_bp") is not None else None),
                "detail": detail,
            }
            check_hash = _semantic_hash(material)
            _validate_supplied_hash(value, "check_hash", check_hash)
            out.append({**material, "candidate_id": candidate_id, "check_hash": check_hash,
                        "check_id": _optional_text(value.get("check_id")) or
                                    _stable_id("rchk", {"run_id": run_id,
                                                       "check_hash": check_hash})})

        for candidate in candidates:
            was_eliminated = candidate["candidate_id"] in eliminated
            if candidate["disposition"] == "eliminated" and not was_eliminated:
                raise ValueError("eliminated candidate requires an eliminate check")
            if candidate["disposition"] == "eligible" and was_eliminated:
                raise ValueError("eligible candidate cannot have an eliminate check")
        return out

    def _prepare_output(self, run_id: str, value: dict[str, Any],
                        candidates: list[dict[str, Any]], checks: list[dict[str, Any]]) -> dict[str, Any]:
        del checks  # Their hashes enter run.output_hash; decision_core stays compact.
        outcome_kind = str(_enum_value(value.get("outcome_kind", value.get("outcome")) or ""))
        if not outcome_kind:
            raise ValueError("outcome_kind is required")
        if outcome_kind not in {"decision", "no_action", "defer", "insufficient_context",
                                "blocked", "failed"}:
            raise ValueError("invalid reasoning outcome_kind")
        selected = _optional_text(value.get("selected_candidate_id"))
        candidate_by_id = {c["candidate_id"]: c for c in candidates}
        candidate_aliases = dict(candidate_by_id)
        for candidate in candidates:
            alias = candidate.get("external_candidate_id")
            if alias:
                candidate_aliases[alias] = candidate
        if selected is not None and selected in candidate_aliases:
            selected = candidate_aliases[selected]["candidate_id"]
        if outcome_kind == "decision":
            if selected is None or selected not in candidate_by_id:
                raise ValueError("decision outcome requires a known selected_candidate_id")
            if candidate_by_id[selected]["disposition"] != "eligible":
                raise ValueError("selected candidate must be eligible")
        elif selected is not None:
            raise ValueError("non-decision outcome cannot select a candidate")
        if (outcome_kind in {"no_action", "insufficient_context", "failed"}
                and candidates):
            raise ValueError(f"{outcome_kind} outcome cannot contain candidates")
        ranked = _sequence(value.get("ranked_candidate_ids"), "ranked_candidate_ids")
        ranked = [candidate_aliases[cid]["candidate_id"] if cid in candidate_aliases else cid
                  for cid in ranked]
        if not ranked:
            ranked = [c["candidate_id"] for c in sorted(
                (candidate for candidate in candidates if candidate["rank_position"] is not None),
                key=lambda candidate: candidate["rank_position"])]
        if len(set(ranked)) != len(ranked) or any(cid not in candidate_by_id for cid in ranked):
            raise ValueError("ranked_candidate_ids must be unique known candidate IDs")
        if any(candidate_by_id[cid]["disposition"] != "eligible" for cid in ranked):
            raise ValueError("ranked_candidate_ids cannot contain eliminated candidates")
        if selected is not None and (not ranked or ranked[0] != selected):
            raise ValueError("selected candidate must be first in deterministic ranking")
        decision_core = _mapping(value.get("decision_core") or value, "decision_core")
        missing_data = _sequence(
            value.get("missing_data", value.get("uncertainty")), "missing_data")
        confidence_bp = _bp(value.get("confidence_bp"), "output confidence_bp")
        material = {
            "outcome_kind": outcome_kind,
            # Decision hashes must survive replay under a new run_id, so bind
            # semantic candidate hashes rather than run-local persistence IDs.
            "selected_candidate_hash": (candidate_by_id[selected]["candidate_hash"]
                                        if selected is not None else None),
            "ranked_candidate_hashes": [candidate_by_id[cid]["candidate_hash"] for cid in ranked],
            "decision_core": decision_core,
            "confidence_bp": confidence_bp,
            "missing_data": missing_data,
        }
        decision_hash = _semantic_hash(material)
        _validate_supplied_hash(value, "decision_hash", decision_hash)
        return {
            "outcome_kind": outcome_kind,
            "selected_candidate_id": selected,
            "ranked_candidate_ids": ranked,
            "decision_core": decision_core,
            "confidence_bp": confidence_bp,
            "missing_data": missing_data,
            "decision_hash": decision_hash,
            "run_id": run_id,
        }

    @staticmethod
    def _insert_results(conn, org_id: str, run_id: str, values: list[dict[str, Any]]) -> None:
        sql = text(
            "insert into reasoning_reasoner_results (org_id,result_id,run_id,ordinal,reasoner_id,"
            "reasoner_version,invocation_key,status,input_hash,output,output_hash,evidence_refs,"
            "diagnostics,skip_reason_code,error_code) values ("
            ":o,:id,:run,:ord,:rid,:rv,:ik,:st,:ih,cast(:out as jsonb),:oh,cast(:ev as jsonb),"
            "cast(:diag as jsonb),:skip,:err)")
        for value in values:
            conn.execute(sql, {"o": org_id, "id": value["result_id"], "run": run_id,
                               "ord": value["ordinal"], "rid": value["reasoner_id"],
                               "rv": value["reasoner_version"], "ik": value["invocation_key"],
                               "st": value["status"], "ih": value["input_hash"],
                               "out": _json_param(value["output"]), "oh": value["output_hash"],
                               "ev": _json_param(value["evidence_refs"]),
                               "diag": _json_param(value["diagnostics"]),
                               "skip": value["skip_reason_code"], "err": value["error_code"]})

    @staticmethod
    def _insert_candidates(conn, org_id: str, run_id: str,
                           values: list[dict[str, Any]]) -> None:
        sql = text(
            "insert into reasoning_candidates (org_id,candidate_id,run_id,play_id,play_version,"
            "parameters,score_components,initial_utility_bp,final_utility_bp,confidence_bp,"
            "disposition,rank_position,evidence_refs,candidate_hash) values ("
            ":o,:id,:run,:play,:pv,cast(:params as jsonb),cast(:scores as jsonb),:iu,:fu,:conf,"
            ":disp,:rank,cast(:ev as jsonb),:hash)")
        for value in values:
            conn.execute(sql, {"o": org_id, "id": value["candidate_id"], "run": run_id,
                               "play": value["play_id"], "pv": value["play_version"],
                               "params": _json_param(value["parameters"]),
                               "scores": _json_param(value["score_components"]),
                               "iu": value["initial_utility_bp"], "fu": value["final_utility_bp"],
                               "conf": value["confidence_bp"], "disp": value["disposition"],
                               "rank": value["rank_position"],
                               "ev": _json_param(value["evidence_refs"]),
                               "hash": value["candidate_hash"]})

    @staticmethod
    def _insert_checks(conn, org_id: str, run_id: str,
                       values: list[dict[str, Any]]) -> None:
        sql = text(
            "insert into reasoning_candidate_checks (org_id,check_id,run_id,candidate_id,ordinal,"
            "stage,evaluator_id,evaluator_version,outcome,reason_code,score_before_bp,score_after_bp,"
            "detail,check_hash) values ("
            ":o,:id,:run,:cid,:ord,:stage,:eid,:ev,:out,:reason,:before,:after,"
            "cast(:detail as jsonb),:hash)")
        for value in values:
            conn.execute(sql, {"o": org_id, "id": value["check_id"], "run": run_id,
                               "cid": value["candidate_id"], "ord": value["ordinal"],
                               "stage": value["stage"], "eid": value["evaluator_id"],
                               "ev": value["evaluator_version"], "out": value["outcome"],
                               "reason": value["reason_code"], "before": value["score_before_bp"],
                               "after": value["score_after_bp"],
                               "detail": _json_param(value["detail"]), "hash": value["check_hash"]})

    @staticmethod
    def _insert_output(conn, org_id: str, run_id: str, value: dict[str, Any]) -> None:
        conn.execute(text(
            "insert into reasoning_run_outputs (org_id,run_id,outcome_kind,selected_candidate_id,"
            "ranked_candidate_ids,decision_core,decision_hash,confidence_bp,missing_data) values ("
            ":o,:run,:kind,:selected,cast(:ranked as jsonb),cast(:core as jsonb),:hash,:conf,"
            "cast(:missing as jsonb))"),
            {"o": org_id, "run": run_id, "kind": value["outcome_kind"],
             "selected": value["selected_candidate_id"],
             "ranked": _json_param(value["ranked_candidate_ids"]),
             "core": _json_param(value["decision_core"]), "hash": value["decision_hash"],
             "conf": value["confidence_bp"], "missing": _json_param(value["missing_data"])})

    def load_bundle(self, *, org_id: str, run_id: str, _conn=None) -> dict[str, Any] | None:
        """Load a complete trace.  Both identifiers are mandatory tenant boundaries."""
        if not org_id or not run_id:
            raise ValueError("org_id and run_id are required")
        with self._read_scope(_conn) as conn:
            run = conn.execute(text(
                "select * from reasoning_runs where org_id=:o and run_id=:r"),
                {"o": org_id, "r": run_id}).mappings().first()
            if run is None:
                return None
            context = conn.execute(text(
                "select cs.*, cp.payload, cp.expires_at as payload_expires_at "
                "from reasoning_context_snapshots cs left join reasoning_context_payloads cp "
                "on cp.org_id=cs.org_id and cp.context_snapshot_id=cs.context_snapshot_id "
                "where cs.org_id=:o and cs.context_snapshot_id=:id"),
                {"o": org_id, "id": run["context_snapshot_id"]}).mappings().first()
            config = None
            if run.get("config_snapshot_id") is not None:
                config = conn.execute(text(
                    "select * from config_snapshots "
                    "where org_id=:o and snapshot_id=:id"),
                    {"o": org_id, "id": run["config_snapshot_id"]}).mappings().first()
            results = conn.execute(text(
                "select * from reasoning_reasoner_results where org_id=:o and run_id=:r "
                "order by ordinal asc"), {"o": org_id, "r": run_id}).mappings().all()
            candidates = conn.execute(text(
                "select * from reasoning_candidates where org_id=:o and run_id=:r "
                "order by rank_position asc nulls last, candidate_id asc"),
                {"o": org_id, "r": run_id}).mappings().all()
            checks = conn.execute(text(
                "select * from reasoning_candidate_checks where org_id=:o and run_id=:r "
                "order by candidate_id asc, ordinal asc"),
                {"o": org_id, "r": run_id}).mappings().all()
            output = conn.execute(text(
                "select * from reasoning_run_outputs where org_id=:o and run_id=:r"),
                {"o": org_id, "r": run_id}).mappings().first()
        return {
            "run": self._decoded_row(run),
            "context_snapshot": self._decoded_row(context) if context else None,
            "config_snapshot": self._decoded_row(config) if config else None,
            "reasoner_results": [self._decoded_row(row) for row in results],
            "candidates": [self._decoded_row(row) for row in candidates],
            "candidate_checks": [self._decoded_row(row) for row in checks],
            "output": self._decoded_row(output) if output else None,
        }

    def verify_replay_bundle(self, bundle: Mapping[str, Any], *,
                             org_id: str | None = None) -> None:
        """Verify every immutable semantic artifact before replay may consume it.

        Replay is an audit operation, not a best-effort deserialize.  This
        verifier works from the persisted rows only: it recomputes capability,
        selector, context, run-input, reasoner-result, candidate, check,
        decision, and aggregate run-output hashes.  It also rebuilds the
        contract-level request/result/candidate/decision hashes embedded in the
        audit envelope, so a self-consistent-looking but tampered child row is
        rejected before any reasoner executes.
        """
        try:
            self._verify_replay_bundle(bundle, org_id=org_id)
        except ReplayIntegrityError:
            raise
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ReplayIntegrityError(f"invalid replay bundle: {exc}") from exc

    @staticmethod
    def _verify_replay_bundle(bundle: Mapping[str, Any], *,
                              org_id: str | None = None) -> None:
        run = _mapping(bundle.get("run"), "run")
        context = _mapping(bundle.get("context_snapshot"), "context_snapshot")
        capability = _mapping(bundle.get("capability_snapshot"), "capability_snapshot")
        output_row = _mapping(bundle.get("output"), "output")
        results = [_mapping(item, "reasoner_result") for item in
                   _sequence(bundle.get("reasoner_results"), "reasoner_results")]
        candidates = [_mapping(item, "candidate") for item in
                      _sequence(bundle.get("candidates"), "candidates")]
        checks = [_mapping(item, "candidate_check") for item in
                  _sequence(bundle.get("candidate_checks"), "candidate_checks")]

        run_org = _required_text(run, "org_id")
        run_id = _required_text(run, "run_id")
        run_config_snapshot_id = _optional_text(run.get("config_snapshot_id"))
        config = (_mapping(bundle.get("config_snapshot"), "config_snapshot")
                  if run_config_snapshot_id is not None else None)
        expected_org = str(org_id).strip() if org_id is not None else run_org
        _integrity_equal("run tenant", run_org, expected_org)
        for label, row in (("context", context), ("capability", capability),
                           ("output", output_row)):
            _integrity_equal(f"{label} tenant", _required_text(row, "org_id"), expected_org)
        if config is not None:
            _integrity_equal("config tenant", _required_text(config, "org_id"), expected_org)
        for label, rows in (("reasoner result", results), ("candidate", candidates),
                            ("candidate check", checks)):
            for row in rows:
                _integrity_equal(f"{label} tenant", _required_text(row, "org_id"), expected_org)
                _integrity_equal(f"{label} run", _required_text(row, "run_id"), run_id)
        _integrity_equal("output run", _required_text(output_row, "run_id"), run_id)

        # Capability bytes and their content-addressed identity.
        manifest = _decanonicalize(_mapping(capability.get("manifest"), "capability manifest"))
        manifest_hash = _semantic_hash(manifest)
        _integrity_equal("capability manifest hash", capability.get("manifest_hash"), manifest_hash)
        _integrity_equal(
            "capability snapshot id",
            capability.get("capability_snapshot_id"),
            f"cap_{manifest_hash}",
        )
        capability_id = _required_text(manifest, "capability_id")
        capability_version = _required_text(manifest, "version")
        expected_policy_snapshot_id = _stable_id("policy", {
            "capability_id": capability_id,
            "capability_version": capability_version,
            "policies": manifest.get("policies") or [],
        })
        _integrity_equal("capability policy snapshot", run.get("policy_snapshot_id"),
                         expected_policy_snapshot_id)
        for label, row in (("capability row", capability), ("context", context), ("run", run)):
            _integrity_equal(f"{label} capability_id", row.get("capability_id"), capability_id)
            _integrity_equal(
                f"{label} capability_version", row.get("capability_version"), capability_version)
        capability_snapshot_id = _required_text(capability, "capability_snapshot_id")
        _integrity_equal("context capability snapshot", context.get("capability_snapshot_id"),
                         capability_snapshot_id)
        _integrity_equal("run capability snapshot", run.get("capability_snapshot_id"),
                         capability_snapshot_id)

        # Effective pack bytes use the pack registry's canonical config hash, not the generic
        # reasoning semantic hash. A tenant-scoped FK proves row ownership; this recomputation
        # proves that the row's bytes actually deserve the identifier stamped on the run.
        if config is not None:
            effective = _decanonicalize(_mapping(config.get("effective"), "effective config"))
            expected_config_snapshot_id = effective_config_snapshot_id(effective)
            _integrity_equal("config snapshot id", config.get("snapshot_id"),
                             expected_config_snapshot_id)
            _integrity_equal("run config snapshot", run_config_snapshot_id,
                             expected_config_snapshot_id)
            config_pack = _required_text(config, "pack_id")
            effective_pack = _required_text(effective, "pack_id")
            capability_pack = _required_text(manifest, "domain")
            _integrity_equal("config row/effective pack", config_pack, effective_pack)
            _integrity_equal("capability/config pack", capability_pack, config_pack)
            if capability_id.startswith("legacy."):
                metadata = _mapping(manifest.get("metadata") or {}, "capability metadata")
                _integrity_equal(
                    "legacy capability/config pack",
                    _required_text(metadata, "pack_id"),
                    config_pack,
                )
                _integrity_equal(
                    "legacy capability/config version",
                    _required_text(metadata, "pack_version"),
                    _required_text(effective, "version"),
                )
                _integrity_equal(
                    "legacy capability/config snapshot",
                    _required_text(metadata, "config_snapshot_id"),
                    expected_config_snapshot_id,
                )

        # Bounded context bytes.  Selector bytes are retained separately because
        # a selector hash without the selector cannot be independently audited.
        if context.get("selector") is None:
            raise ReplayIntegrityError("context selector bytes are unavailable for replay")
        if context.get("payload") is None:
            raise ContextPayloadExpired(context.get("context_snapshot_id") or run.get("run_id"))
        payload_expires_at = context.get("payload_expires_at")
        if (payload_expires_at is not None
                and _aware_datetime(payload_expires_at, "payload_expires_at")
                <= datetime.now(timezone.utc)):
            raise ContextPayloadExpired(context.get("context_snapshot_id") or run.get("run_id"))
        selector = _decanonicalize(_mapping(context.get("selector"), "context selector"))
        payload = _decanonicalize(_mapping(context.get("payload"), "context payload"))
        source_manifest = _decanonicalize(
            _sequence(context.get("source_manifest"), "context source_manifest"))
        selector_hash = _semantic_hash(selector)
        payload_hash = _semantic_hash(payload)
        _integrity_equal("context selector hash", context.get("selector_hash"), selector_hash)
        _integrity_equal("context payload hash", context.get("payload_hash"), payload_hash)
        evaluation_time = _aware_datetime(context.get("evaluation_time"),
                                          "context evaluation_time")
        schema_version = int(context.get("schema_version"))
        if schema_version not in {1, 2}:
            raise ReplayIntegrityError("unsupported context snapshot schema version")
        context_material = {
            "schema_version": schema_version,
            "org_id": expected_org,
            "capability_id": capability_id,
            "capability_version": capability_version,
            "capability_snapshot_id": capability_snapshot_id,
            "root_node_id": context.get("root_node_id"),
            "graph_version": int(context.get("graph_version")),
            "evaluation_time": evaluation_time,
            "selector_version": _required_text(context, "selector_version"),
            "selector_hash": selector_hash,
            "payload_hash": payload_hash,
            "source_manifest": source_manifest,
        }
        if schema_version >= 2:
            context_material["root_node_type"] = _required_text(context, "root_node_type")
        context_hash = _semantic_hash(context_material)
        _integrity_equal("context hash", context.get("context_hash"), context_hash)
        context_snapshot_id = _stable_id(
            "ctx", {"org_id": expected_org, "context_hash": context_hash})
        _integrity_equal("context snapshot id", context.get("context_snapshot_id"),
                         context_snapshot_id)
        _integrity_equal("run context snapshot", run.get("context_snapshot_id"),
                         context_snapshot_id)

        # Snapshot metadata must describe the payload it claims to bind.
        _integrity_equal("payload tenant", payload.get("org_id"), expected_org)
        _integrity_equal("payload graph version", payload.get("graph_version"),
                         int(context.get("graph_version")))
        _integrity_equal("payload root node", payload.get("root_entity_id"),
                         context.get("root_node_id"))
        _integrity_equal("payload root type", payload.get("root_entity_type"),
                         context.get("root_node_type"))
        _integrity_equal("capability/context root type", context.get("root_node_type"),
                         _required_text(manifest, "root_entity_type"))
        _integrity_equal("payload selector version", payload.get("selector_version"),
                         context.get("selector_version"))
        _integrity_equal(
            "payload evaluation time",
            _aware_datetime(payload.get("evaluation_time"), "payload evaluation_time"),
            evaluation_time,
        )

        # Run input provenance, including every field that can alter authority or
        # replay lineage.  An explicit idempotency key can no longer alias these.
        reasoner_plan = _decanonicalize(
            _sequence(run.get("reasoner_plan"), "reasoner_plan"))
        reasoner_plan_hash = _semantic_hash(reasoner_plan)
        _integrity_equal("reasoner plan hash", run.get("reasoner_plan_hash"),
                         reasoner_plan_hash)
        input_manifest = _decanonicalize(
            _mapping(run.get("input_manifest"), "input_manifest"))
        run_evaluation_time = _aware_datetime(run.get("evaluation_time"),
                                              "run evaluation_time")
        _integrity_equal("run evaluation time", run_evaluation_time, evaluation_time)
        _integrity_equal("run root node", run.get("root_node_id"), context.get("root_node_id"))
        mode = _required_text(run, "mode")
        trigger_kind = _required_text(run, "trigger_kind")
        trigger_ref = _optional_text(run.get("trigger_ref"))
        replay_of_run_id = _optional_text(run.get("replay_of_run_id"))
        supersedes_run_id = _optional_text(run.get("supersedes_run_id"))
        run_input_hash = _semantic_hash({
            "org_id": expected_org,
            "context_snapshot_id": context_snapshot_id,
            "capability_snapshot_id": capability_snapshot_id,
            "config_snapshot_id": _optional_text(run.get("config_snapshot_id")),
            "policy_snapshot_id": _optional_text(run.get("policy_snapshot_id")),
            "root_node_id": _optional_text(run.get("root_node_id")),
            "evaluation_time": run_evaluation_time,
            "trigger_kind": trigger_kind,
            "trigger_ref": trigger_ref,
            "mode": mode,
            "replay_of_run_id": replay_of_run_id,
            "supersedes_run_id": supersedes_run_id,
            "input_manifest": input_manifest,
            "reasoner_plan_hash": reasoner_plan_hash,
            "orchestrator_version": _required_text(run, "orchestrator_version"),
            "engine_build": _required_text(run, "engine_build"),
        })
        _integrity_equal("run input hash", run.get("input_hash"), run_input_hash)

        contract_context_hash = _semantic_hash(payload)
        contract_context_id = f"ctx_{contract_context_hash}"
        _integrity_equal("contract context hash",
                         input_manifest.get("contract_context_hash"), contract_context_hash)
        _integrity_equal("contract context snapshot id",
                         input_manifest.get("contract_context_snapshot_id"), contract_context_id)
        _integrity_equal("run source manifest", input_manifest.get("source_manifest"),
                         source_manifest)
        request_hash = _semantic_hash({
            "org_id": expected_org,
            "capability_snapshot_id": capability_snapshot_id,
            "context_snapshot_id": contract_context_id,
            "evaluation_time": run_evaluation_time,
            "trigger_kind": _required_text(input_manifest, "original_trigger_kind"),
            "trigger_ref": trigger_ref,
            "mode": mode,
            "config_snapshot_id": _optional_text(run.get("config_snapshot_id")),
            "policy_snapshot_id": _optional_text(run.get("policy_snapshot_id")),
        })
        _integrity_equal("contract request hash", input_manifest.get("request_hash"), request_hash)
        expected_trace_id = _stable_id("run", {
            "request_hash": request_hash,
            "orchestrator_version": run.get("orchestrator_version"),
            "reasoner_plan": reasoner_plan,
        })
        _integrity_equal("trace run id", input_manifest.get("trace_run_id"), expected_trace_id)

        # Reasoner rows: verify persistence hashes, contract hashes, DAG input
        # hashes, declared identity, order, and dependency visibility.
        manifest_specs = [_decanonicalize(_mapping(item, "reasoner spec")) for item in
                          _sequence(manifest.get("reasoners"), "capability reasoners")]
        spec_by_id = {_required_text(item, "reasoner_id"): item for item in manifest_specs}
        if len(spec_by_id) != len(manifest_specs):
            raise ReplayIntegrityError("duplicate capability reasoner identity")
        _integrity_equal("reasoner plan", reasoner_plan,
                         _topological_spec_ids(manifest_specs))
        ordered_results = sorted(results, key=lambda item: int(item.get("ordinal")))
        _integrity_equal("reasoner result count", len(ordered_results), len(reasoner_plan))
        contract_results: dict[str, dict[str, Any]] = {}
        contract_result_hashes: list[list[str]] = []
        persistence_result_hashes: list[str] = []
        for ordinal, row in enumerate(ordered_results):
            _integrity_equal("reasoner result ordinal", int(row.get("ordinal")), ordinal)
            reasoner_id = _required_text(row, "reasoner_id")
            _integrity_equal("reasoner result plan position", reasoner_id,
                             reasoner_plan[ordinal])
            spec = spec_by_id.get(reasoner_id)
            if spec is None:
                raise ReplayIntegrityError("reasoner result is absent from capability manifest")
            _integrity_equal("reasoner result version", row.get("reasoner_version"),
                             spec.get("version"))
            result_output = _decanonicalize(
                _mapping(row.get("output") or {}, "reasoner output"))
            evidence_refs = _decanonicalize(
                _sequence(row.get("evidence_refs"), "reasoner evidence_refs"))
            result_material = {
                "ordinal": ordinal,
                "reasoner_id": reasoner_id,
                "reasoner_version": _required_text(row, "reasoner_version"),
                "invocation_key": _required_text(row, "invocation_key"),
                "status": _required_text(row, "status"),
                "input_hash": _required_text(row, "input_hash"),
                "output": result_output,
                "evidence_refs": evidence_refs,
                "skip_reason_code": _optional_text(row.get("skip_reason_code")),
                "error_code": _optional_text(row.get("error_code")),
            }
            result_output_hash = _semantic_hash(result_material)
            _integrity_equal("reasoner output hash", row.get("output_hash"), result_output_hash)
            persistence_result_hashes.append(result_output_hash)
            contract_result = {
                "reasoner_id": reasoner_id,
                "reasoner_version": row.get("reasoner_version"),
                "status": row.get("status"),
                "matched": result_output.get("matched"),
                "metrics": result_output.get("metrics") or {},
                "findings": result_output.get("findings") or [],
                "adjustments": result_output.get("adjustments") or [],
                "checks": result_output.get("checks") or [],
                "evidence_ids": evidence_refs,
                "missing_fields": result_output.get("missing_fields") or [],
                "reason_codes": result_output.get("reason_codes") or [],
            }
            dependencies = {
                dependency_id: contract_results[dependency_id]
                for dependency_id in spec.get("dependencies") or []
                if dependency_id in contract_results
            }
            expected_result_input_hash = _semantic_hash({
                "request_hash": request_hash,
                "spec": spec,
                "dependencies": dependencies,
            })
            _integrity_equal("reasoner input hash", row.get("input_hash"),
                             expected_result_input_hash)
            contract_results[reasoner_id] = contract_result
            contract_result_hashes.append([reasoner_id, _semantic_hash(contract_result)])

        # Candidate and check hashes.  Persistence IDs remain run-local, while
        # contract hashes are reconstructed for deterministic replay comparison.
        candidate_by_id: dict[str, dict[str, Any]] = {}
        for row in candidates:
            candidate_id = _required_text(row, "candidate_id")
            if candidate_id in candidate_by_id:
                raise ReplayIntegrityError("duplicate persisted candidate id")
            candidate_by_id[candidate_id] = row
        checks_by_candidate: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        persistence_check_hashes: list[tuple[str, int, str]] = []
        for row in checks:
            candidate_id = _required_text(row, "candidate_id")
            candidate = candidate_by_id.get(candidate_id)
            if candidate is None:
                raise ReplayIntegrityError("candidate check references an unknown candidate")
            ordinal = int(row.get("ordinal"))
            check_contract = {
                "play_id": candidate.get("play_id"),
                "stage": _required_text(row, "stage"),
                "outcome": _required_text(row, "outcome"),
                "reason_code": _required_text(row, "reason_code"),
                "evaluator_id": _required_text(row, "evaluator_id"),
                "evaluator_version": _required_text(row, "evaluator_version"),
                "detail": _decanonicalize(_mapping(row.get("detail") or {}, "check detail")),
                "score_before_bp": row.get("score_before_bp"),
                "score_after_bp": row.get("score_after_bp"),
            }
            check_material = {
                "candidate_hash": candidate.get("candidate_hash"),
                "ordinal": ordinal,
                "stage": check_contract["stage"],
                "evaluator_id": check_contract["evaluator_id"],
                "evaluator_version": check_contract["evaluator_version"],
                "outcome": check_contract["outcome"],
                "reason_code": check_contract["reason_code"],
                "score_before_bp": check_contract["score_before_bp"],
                "score_after_bp": check_contract["score_after_bp"],
                "detail": check_contract["detail"],
            }
            check_hash = _semantic_hash(check_material)
            _integrity_equal("candidate check hash", row.get("check_hash"), check_hash)
            persistence_check_hashes.append((candidate_id, ordinal, check_hash))
            checks_by_candidate[candidate_id].append({"ordinal": ordinal,
                                                       "contract": check_contract})

        contract_candidate_by_hash: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        persistence_candidate_hashes: list[tuple[str, str]] = []
        for candidate_id, row in candidate_by_id.items():
            parameters = _decanonicalize(
                _mapping(row.get("parameters") or {}, "candidate parameters"))
            score_components = _decanonicalize(
                _mapping(row.get("score_components") or {}, "candidate score_components"))
            evidence_refs = _decanonicalize(
                _sequence(row.get("evidence_refs"), "candidate evidence_refs"))
            candidate_material = {
                "play_id": _required_text(row, "play_id"),
                "play_version": _required_text(row, "play_version"),
                "parameters": parameters,
                "score_components": score_components,
                "initial_utility_bp": int(row.get("initial_utility_bp")),
                "final_utility_bp": (int(row["final_utility_bp"])
                                     if row.get("final_utility_bp") is not None else None),
                "confidence_bp": int(row.get("confidence_bp")),
                "disposition": _required_text(row, "disposition"),
                "rank_position": (int(row["rank_position"])
                                  if row.get("rank_position") is not None else None),
                "evidence_refs": evidence_refs,
            }
            candidate_hash = _semantic_hash(candidate_material)
            _integrity_equal("candidate hash", row.get("candidate_hash"), candidate_hash)
            persistence_candidate_hashes.append((candidate_id, candidate_hash))
            candidate_checks = [item["contract"] for item in sorted(
                checks_by_candidate.get(candidate_id, []), key=lambda item: item["ordinal"])]
            contract_candidate = {
                "play_id": candidate_material["play_id"],
                "play_version": candidate_material["play_version"],
                "disposition": candidate_material["disposition"],
                "utility_bp": (candidate_material["final_utility_bp"]
                               if candidate_material["final_utility_bp"] is not None
                               else candidate_material["initial_utility_bp"]),
                "confidence_bp": candidate_material["confidence_bp"],
                "score_components": score_components,
                "rank_position": candidate_material["rank_position"],
                "checks": candidate_checks,
                "evidence_ids": evidence_refs,
                "parameters": parameters,
            }
            contract_candidate_hash = _semantic_hash(contract_candidate)
            if contract_candidate_hash in contract_candidate_by_hash:
                raise ReplayIntegrityError("duplicate contract candidate hash")
            contract_candidate_by_hash[contract_candidate_hash] = (row, contract_candidate)

        embedded_check_hashes = sorted(
            _semantic_hash(_contract_check(check))
            for result in contract_results.values()
            for check in _sequence(result.get("checks"), "reasoner checks")
        )
        indexed_check_hashes = sorted(
            _semantic_hash(item["contract"])
            for values in checks_by_candidate.values()
            for item in values
        )
        _integrity_equal("reasoner/candidate check effects",
                         indexed_check_hashes, embedded_check_hashes)

        # Persistence output hash and contract decision envelope.
        ranked_ids = _decanonicalize(
            _sequence(output_row.get("ranked_candidate_ids"), "ranked_candidate_ids"))
        if any(candidate_id not in candidate_by_id for candidate_id in ranked_ids):
            raise ReplayIntegrityError("ranked output references an unknown candidate")
        selected_id = _optional_text(output_row.get("selected_candidate_id"))
        if selected_id is not None and selected_id not in candidate_by_id:
            raise ReplayIntegrityError("selected output references an unknown candidate")
        decision_core = _decanonicalize(
            _mapping(output_row.get("decision_core"), "decision_core"))
        missing_data = _decanonicalize(
            _sequence(output_row.get("missing_data"), "missing_data"))
        decision_material = {
            "outcome_kind": _required_text(output_row, "outcome_kind"),
            "selected_candidate_hash": (candidate_by_id[selected_id]["candidate_hash"]
                                        if selected_id is not None else None),
            "ranked_candidate_hashes": [candidate_by_id[item]["candidate_hash"]
                                        for item in ranked_ids],
            "decision_core": decision_core,
            "confidence_bp": int(output_row.get("confidence_bp")),
            "missing_data": missing_data,
        }
        if decision_material["outcome_kind"] == "decision":
            for spec in manifest_specs:
                reasoner_id = _required_text(spec, "reasoner_id")
                result = contract_results.get(reasoner_id)
                if (str(spec.get("failure_policy") or "required") == "required"
                        and (result is None or result.get("status") != "completed")):
                    raise ReplayIntegrityError(
                        "decision contains an incomplete required reasoner")
                if (spec.get("gating") is True
                        and (result is None or result.get("status") != "completed"
                             or result.get("matched") is not True)):
                    raise ReplayIntegrityError("decision bypasses a gating reasoner")
            if selected_id is None:
                raise ReplayIntegrityError("decision has no selected candidate")
            constraint_spec = spec_by_id.get("core.constraint")
            selected_checks = [item["contract"] for item in
                               checks_by_candidate.get(selected_id, [])]
            for policy in _sequence(manifest.get("policies"), "capability policies"):
                requirement = _POLICY_CHECK_REQUIREMENTS.get(str(policy))
                if requirement is None or constraint_spec is None:
                    raise ReplayIntegrityError("decision has an unsupported policy proof")
                stage, reason_code = requirement
                matches = [check for check in selected_checks
                           if check["stage"] == stage
                           and check["reason_code"] == reason_code
                           and check["evaluator_id"] == "core.constraint"
                           and check["evaluator_version"] == constraint_spec.get("version")
                           and check["outcome"] == "pass"]
                if len(matches) != 1:
                    raise ReplayIntegrityError(
                        f"decision lacks one exact passing check for policy {policy}")
        decision_hash = _semantic_hash(decision_material)
        _integrity_equal("decision output hash", output_row.get("decision_hash"), decision_hash)
        declared_result_hashes = _decanonicalize(
            _sequence(decision_core.get("reasoner_result_hashes"),
                      "decision reasoner_result_hashes"))
        _integrity_equal("contract reasoner result hashes", declared_result_hashes,
                         contract_result_hashes)
        declared_candidate_hashes = _decanonicalize(
            _sequence(decision_core.get("candidate_hashes"), "decision candidate_hashes"))
        _integrity_equal("contract candidate count", len(declared_candidate_hashes),
                         len(contract_candidate_by_hash))
        if len(set(declared_candidate_hashes)) != len(declared_candidate_hashes):
            raise ReplayIntegrityError("duplicate declared contract candidate hash")
        try:
            ordered_contract_candidates = [contract_candidate_by_hash[item]
                                           for item in declared_candidate_hashes]
        except KeyError as exc:
            raise ReplayIntegrityError("contract candidate hash integrity mismatch") from exc
        selected_contract_id = None
        if selected_id is not None:
            selected_contract_hash = next(
                item for item, (row, _) in contract_candidate_by_hash.items()
                if row["candidate_id"] == selected_id)
            selected_contract_id = f"cand_{selected_contract_hash}"
        contract_decision = {
            "outcome": output_row.get("outcome_kind"),
            "capability_id": capability_id,
            "capability_version": capability_version,
            "context_snapshot_id": contract_context_id,
            "candidates": [item[1] for item in ordered_contract_candidates],
            "selected_candidate_id": selected_contract_id,
            "confidence_bp": int(output_row.get("confidence_bp")),
            "uncertainty": decision_core.get("uncertainty") or [],
            "do_nothing_consequence": decision_core.get("do_nothing_consequence"),
            "expires_at": decision_core.get("expires_at"),
            "outcome_window_days": decision_core.get("outcome_window_days"),
        }
        contract_decision_hash = _semantic_hash(contract_decision)
        _integrity_equal("contract decision hash",
                         decision_core.get("contract_decision_hash"), contract_decision_hash)
        _integrity_equal("contract decision id", decision_core.get("contract_decision_id"),
                         f"decision_{contract_decision_hash}")
        _integrity_equal("decision capability_id", decision_core.get("capability_id"),
                         capability_id)
        _integrity_equal("decision capability_version",
                         decision_core.get("capability_version"), capability_version)
        _integrity_equal("decision context snapshot",
                         decision_core.get("context_snapshot_id"), contract_context_id)
        _integrity_equal("decision uncertainty", missing_data,
                         decision_core.get("uncertainty") or [])

        aggregate_output_hash = _semantic_hash({
            "reasoner_results": persistence_result_hashes,
            "candidates": [item[1] for item in sorted(persistence_candidate_hashes)],
            "checks": [item[2] for item in sorted(
                persistence_check_hashes, key=lambda item: (item[0], item[1]))],
            "decision_hash": decision_hash,
        })
        _integrity_equal("run output hash", run.get("output_hash"), aggregate_output_hash)

    def load_replay_bundle(self, *, org_id: str, run_id: str) -> dict[str, Any]:
        bundle = self.load_bundle(org_id=org_id, run_id=run_id)
        if bundle is None:
            raise ReasoningStoreError("reasoning run not found")
        context = bundle.get("context_snapshot") or {}
        if context.get("payload") is None:
            raise ContextPayloadExpired(context.get("context_snapshot_id") or run_id)
        payload_expires_at = context.get("payload_expires_at")
        if (payload_expires_at is not None
                and _aware_datetime(payload_expires_at, "payload_expires_at")
                <= datetime.now(timezone.utc)):
            raise ContextPayloadExpired(context.get("context_snapshot_id") or run_id)
        run_config_snapshot_id = _optional_text(bundle["run"].get("config_snapshot_id"))
        if run_config_snapshot_id is not None and bundle.get("config_snapshot") is None:
            raise ReasoningStoreError("effective config snapshot is unavailable for replay")
        capability = self.load_capability_snapshot(
            org_id=org_id,
            capability_snapshot_id=bundle["run"]["capability_snapshot_id"],
        )
        if capability is None:
            raise ReasoningStoreError("capability snapshot is unavailable for replay")
        bundle["capability_snapshot"] = capability
        self.verify_replay_bundle(bundle, org_id=org_id)
        return bundle

    def load_by_idempotency(self, *, org_id: str,
                            idempotency_key: str) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            run_id = conn.execute(text(
                "select run_id from reasoning_runs where org_id=:o and idempotency_key=:k"),
                {"o": org_id, "k": idempotency_key}).scalar()
        return self.load_bundle(org_id=org_id, run_id=run_id) if run_id else None

    def purge_expired_context_payloads(self, *, eval_time: datetime | str) -> int:
        now = _aware_datetime(eval_time, "eval_time")
        with self._engine.begin() as conn:
            result = conn.execute(text(
                "delete from reasoning_context_payloads "
                "where expires_at is not null and expires_at < :now"), {"now": now})
        return int(result.rowcount or 0)

    @staticmethod
    def _decoded_row(row: Mapping[str, Any]) -> dict[str, Any]:
        decoded = dict(row)
        json_fields = {
            "source_manifest", "selector", "payload", "input_manifest", "reasoner_plan", "output",
            "evidence_refs", "diagnostics", "parameters", "score_components", "detail",
            "ranked_candidate_ids", "decision_core", "missing_data",
            "manifest", "effective",
        }
        for key in json_fields & decoded.keys():
            decoded[key] = _json_value(decoded[key])
        return decoded
