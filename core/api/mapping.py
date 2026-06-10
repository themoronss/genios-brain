"""Custom-source mapping routes — propose + confirm + freeze.

POST /v1/mapping/introspect       given sample records → introspection
POST /v1/mapping/propose          run inspector → templates → LLM → proposal
POST /v1/mapping/confirm          apply human edits + freeze
GET  /v1/mapping/active           load the currently active mapping for a connection

The frontend flow (custom integration confirm UI):
    1. Customer admin uploads/syncs sample records via the connection.
    2. Dashboard calls /propose with the samples to get a proposal view.
    3. Admin edits dropdowns + submits to /confirm.
    4. Mapping is frozen + drift_check runs nightly thereafter.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.api.deps import db_session, require_org
from core.foundations.telemetry import get_logger
from core.memory.adapters.custom.confirmer import (
    ConfirmationError,
    HumanEdit,
    apply_human_edits,
    to_confirmation_view,
)
from core.memory.adapters.custom.freezer import freeze, load_active
from core.memory.adapters.custom.inspector import introspect_samples, introspect_sql_schema
from core.memory.adapters.custom.proposer import ProposerError, propose

router = APIRouter(prefix="/v1/mapping", tags=["mapping"])
log = get_logger(__name__)


class IntrospectRequest(BaseModel):
    source_type: str = Field(..., min_length=1)
    samples: list[dict[str, Any]] = Field(default_factory=list)
    sql_schema_rows: list[dict[str, Any]] | None = None


class ProposeRequest(BaseModel):
    source_type: str = Field(..., min_length=1)
    samples: list[dict[str, Any]] = Field(default_factory=list)
    sql_schema_rows: list[dict[str, Any]] | None = None


class ConfirmEdit(BaseModel):
    canonical_field: str
    source_field: str | None = None
    transform: str | None = None
    confidence_override: float | None = None


class ConfirmRequest(BaseModel):
    connection_id: str = Field(..., min_length=1)
    source_type: str = Field(..., min_length=1)
    confirmed_by: str = Field(..., min_length=1)
    samples: list[dict[str, Any]] = Field(default_factory=list)
    sql_schema_rows: list[dict[str, Any]] | None = None
    edits: list[ConfirmEdit]


@router.post("/introspect")
def introspect(
    body: IntrospectRequest,
    _org_id: str = Depends(require_org),
) -> dict[str, Any]:
    introspection = (
        introspect_sql_schema(body.source_type, body.sql_schema_rows)
        if body.sql_schema_rows
        else introspect_samples(body.source_type, body.samples)
    )
    return introspection.model_dump(mode="json")


@router.post("/propose")
def propose_mapping(
    body: ProposeRequest,
    org_id: str = Depends(require_org),
) -> dict[str, Any]:
    introspection = (
        introspect_sql_schema(body.source_type, body.sql_schema_rows)
        if body.sql_schema_rows
        else introspect_samples(body.source_type, body.samples)
    )

    # Billing: only the LLM path pays. The template path (a hardcoded
    # known mapping like 'gmail') costs us nothing and shouldn't charge
    # the customer. The Sonnet path (genuinely unknown schema) is the
    # priciest call we make routinely — 5 cr captures it without
    # surprising the customer since they only hit this on first connect.
    from core.memory.adapters.custom.proposer import guess_from_introspection
    template_hit = guess_from_introspection(introspection) is not None

    if not template_hit:
        import hashlib as _h
        from sqlalchemy import text as _text

        from app.database import SessionLocal
        from core.foundations import audit
        from core.resources.billing import deduct_or_raise

        # Idempotency: hash of (source_type + field names) so a double-
        # click or browser retry on the same form submission does not
        # double-charge.
        fields_sig = ",".join(sorted(f.name for f in introspection.fields))
        sample_fp = _h.sha256(
            f"{body.source_type}:{fields_sig}".encode()
        ).hexdigest()[:16]

        # Trial-tier grace: the first custom mapping is FREE. Customer
        # gets to test "bring your own data source" without a 3-credit
        # toll just to discover whether mapping even works for their
        # shape. Detected by:
        #   plan == 'trial' AND no prior ledger row for this reason.
        # Free path still writes an audit row so the grace is observable
        # for support + future analytics.
        granted_free = False
        _db = SessionLocal()
        try:
            plan_row = _db.execute(
                _text("SELECT subscription_tier FROM orgs WHERE id = :o"),
                {"o": org_id},
            ).fetchone()
            tier = (plan_row.subscription_tier if plan_row else "").lower()
            if tier == "trial":
                prior = _db.execute(
                    _text(
                        "SELECT 1 FROM credit_ledger "
                        "WHERE org_id = :o AND reason = 'custom_adapter:mapping' "
                        "LIMIT 1"
                    ),
                    {"o": org_id},
                ).fetchone()
                if prior is None:
                    granted_free = True
        finally:
            _db.close()

        if granted_free:
            # Write a 0-amount ledger row tagged with the grace metadata.
            # MUST land in credit_ledger (not just audit) — the "prior
            # mapping?" check above keys off ledger rows; without this
            # row the next call would qualify for the grace again and
            # the customer would get unlimited free mappings.
            _ldb = SessionLocal()
            try:
                _ldb.execute(
                    _text(
                        """
                        INSERT INTO credit_ledger
                          (org_id, bucket, kind, amount, balance_after,
                           reason, related_kind, related_id,
                           idempotency_key, metadata)
                        VALUES
                          (:org, 'context', 'grant', 0,
                           (SELECT COALESCE(credits,0)+COALESCE(topup_credits,0)
                            FROM orgs WHERE id = :org),
                           'custom_adapter:mapping', 'custom_mapping', :rid,
                           :key, CAST(:meta AS JSONB))
                        ON CONFLICT (org_id, idempotency_key)
                          WHERE idempotency_key IS NOT NULL
                        DO NOTHING
                        """
                    ),
                    {
                        "org": org_id, "rid": sample_fp,
                        "key": f"custom_mapping_grace:{org_id}:{sample_fp}",
                        "meta": __import__("json").dumps({
                            "grace": "trial_first_custom_mapping",
                            "would_have_billed": 3,
                            "fingerprint": sample_fp,
                        }),
                    },
                )
                _ldb.commit()
            except Exception as _e:
                _ldb.rollback()
                # If the grace row fails we'd rather under-charge than
                # block the user — but log it loud so ops can clean up.
                __import__("logging").getLogger(__name__).warning(
                    "trial_grace_ledger_write_failed", extra={"err": str(_e)},
                )
            finally:
                _ldb.close()
            audit.record(
                org_id=org_id,
                actor_type="user",
                actor_id="system",
                action="permission_changed",
                target_type="credit_ledger",
                target_id=sample_fp,
                metadata={
                    "reason": "custom_adapter:mapping",
                    "units": 0,
                    "grace": "trial_first_custom_mapping",
                    "would_have_billed": 3,
                },
            )
        else:
            deduct_or_raise(
                org_id=org_id,
                reason="custom_adapter:mapping",
                idempotency_key=f"custom_mapping:{org_id}:{sample_fp}",
                related_kind="custom_mapping",
                related_id=sample_fp,
            )

    try:
        proposal = propose(introspection, org_id=org_id)
    except ProposerError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e

    view = to_confirmation_view(proposal, introspection)
    return {
        "source_type": body.source_type,
        "introspection": introspection.model_dump(mode="json"),
        "rows": [
            {
                "canonical_field": r.canonical_field,
                "proposed_source_field": r.proposed_source_field,
                "proposed_transform": r.proposed_transform,
                "proposed_confidence": r.proposed_confidence,
                "available_source_fields": r.available_source_fields,
                "is_required": r.is_required,
            }
            for r in view
        ],
    }


@router.post("/confirm", status_code=status.HTTP_201_CREATED)
def confirm_mapping(
    body: ConfirmRequest,
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    introspection = (
        introspect_sql_schema(body.source_type, body.sql_schema_rows)
        if body.sql_schema_rows
        else introspect_samples(body.source_type, body.samples)
    )
    human_edits = [
        HumanEdit(
            canonical_field=e.canonical_field,
            source_field=e.source_field,
            transform=e.transform,
            confidence_override=e.confidence_override,
        )
        for e in body.edits
    ]
    try:
        field_map = apply_human_edits(human_edits, introspection)
    except ConfirmationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e

    # Production guard: confirm-mapping requires a real Connection row first.
    # Without it the freeze() FK insert into source_mappings raises a 500.
    # Return a clean 400 so the UI can prompt "Create a connection first".
    from core.memory.store import Connection
    exists = session.get(Connection, body.connection_id)
    if exists is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "connection_not_found",
                "connection_id": body.connection_id,
                "message": "No connection exists with this ID. Create the connection (e.g. via OAuth or POST /v1/connections) before freezing a mapping.",
            },
        )

    frozen = freeze(
        session,
        connection_id=body.connection_id,
        org_id=org_id,
        source_type=body.source_type,
        field_map=field_map,
        confirmed_by=body.confirmed_by,
    )
    session.commit()
    return frozen.model_dump(mode="json")


@router.get("/active")
def get_active_mapping(
    connection_id: str,
    source_type: str,
    _org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    mapping = load_active(session, connection_id, source_type)
    if mapping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no frozen mapping for this connection",
        )
    return mapping.model_dump(mode="json")


@router.get("/list")
def list_org_mappings(
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    """List all active frozen mappings for an org + their owning connections.

    Powers the custom integration page UI so the user can see what they've
    configured without poking the DB.
    """
    from core.memory.store import Connection, SourceMappingRow

    rows = session.execute(
        select(
            SourceMappingRow.connection_id,
            SourceMappingRow.version,
            SourceMappingRow.mapping_json,
            SourceMappingRow.confirmed_at,
            SourceMappingRow.confirmed_by,
            Connection.source_id,
            Connection.source_type,
        )
        .join(Connection, Connection.id == SourceMappingRow.connection_id)
        .where(SourceMappingRow.org_id == org_id)
        .where(Connection.source_type.notin_(_INTERNAL_SOURCE_TYPES))
        .order_by(SourceMappingRow.confirmed_at.desc())
    ).fetchall()

    mappings = []
    for r in rows:
        mapping_json = r.mapping_json if isinstance(r.mapping_json, dict) else {}
        field_map = mapping_json.get("field_map") or mapping_json
        if not isinstance(field_map, dict):
            field_map = {}
        avg_conf = (
            sum(float((v or {}).get("confidence") or 0) for v in field_map.values())
            / max(1, len(field_map))
        )
        mappings.append({
            "connection_id":   r.connection_id,
            "source_type":     mapping_json.get("source_type", r.source_type),
            "version":         r.version,
            "connection_label": f"{r.source_type} · {r.source_id}",
            "fields":          list(field_map.keys()),
            "avg_confidence":  round(avg_conf, 2),
            "confirmed_at":    r.confirmed_at.isoformat() if r.confirmed_at else None,
            "confirmed_by":    r.confirmed_by,
        })
    return {"mappings": mappings, "count": len(mappings)}


# System / bootstrap source types that exist for internal plumbing and
# should NEVER appear in customer-facing dropdowns.
_INTERNAL_SOURCE_TYPES = {"admin_console", "system", "internal", "self"}


@router.get("/connections")
def list_connections_for_mapping(
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    """Return the active Connection rows for this org so the custom-integration
    page can offer a dropdown (no need to look up UUIDs in the DB).

    System/admin connections (admin_console, internal, system, self) are
    hidden so the customer sees only their real data sources.
    """
    from core.memory.store import Connection

    rows = session.execute(
        select(Connection.id, Connection.source_type, Connection.source_id, Connection.status)
        .where(Connection.org_id == org_id)
        .where(Connection.source_type.notin_(_INTERNAL_SOURCE_TYPES))
        .order_by(Connection.created_at.desc())
    ).fetchall()
    return {
        "connections": [
            {
                "id": r.id,
                "source_type": r.source_type,
                "source_id": r.source_id,
                "status": r.status,
                "label": f"{r.source_type} · {r.source_id}",
            }
            for r in rows
        ],
    }
