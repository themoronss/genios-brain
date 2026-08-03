"""Per-input billing for Resources tab (manual + uploads).

One small function that the manual + upload paths both call before they
emit anything. Centralises:
  - the deduct call against the v1 credit ledger (single source of truth)
  - InsufficientCredits → HTTPException(402) translation so the route
    layer doesn't have to know about ledger internals
  - an audit log on every charge attempt (success and 402) so the founder
    has a trail when a customer complains "you charged me wrong"

Why a thin module instead of inlining: the same 5-line block was about to
land in manual.py, uploads.py, and the Gmail attachment hook. Drift on
reasons/idempotency keys across three sites is exactly the bug class
that turns a "credits are wrong" report into a 3-day debug.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from core.foundations import audit
from core.foundations.telemetry import get_logger

log = get_logger(__name__)


def deduct_or_raise(
    *,
    org_id: str,
    reason: str,
    idempotency_key: str,
    related_kind: str,
    related_id: str,
    agent_uuid: str | None = None,
    actor_email: str | None = None,
    units: int = 1,
) -> dict[str, Any] | None:
    """Charge the customer once for one Resources input.

    Returns the DeductResult dict on success (caller can ignore). Raises
    HTTPException(402) when the org is out of credits — the FastAPI
    exception bubble keeps any partial state from being committed
    because the route has not yet flushed/committed.

    Best-effort wrapper around app.credits.ledger.deduct — failures other
    than InsufficientCredits (e.g. ledger module missing in dev) are
    logged and swallowed so a dev-only environment is not blocked by
    plumbing, but production WILL see them in stderr.
    """
    try:
        from app.credits.ledger import InsufficientCredits, deduct
        from app.database import SessionLocal
    except Exception as e:
        log.warning("billing_ledger_import_failed", error=str(e), reason=reason)
        return None

    ldb = SessionLocal()
    try:
        result = deduct(
            ldb,
            org_id=org_id,
            bucket="context",
            reason=reason,
            units=units,
            idempotency_key=idempotency_key,
            related_kind=related_kind,
            related_id=related_id,
            agent_uuid=agent_uuid,
        )
        ldb.commit()
        audit.record(
            org_id=org_id,
            actor_type="user" if actor_email else "system",
            actor_id=actor_email or "system",
            action="data_accessed",
            target_type="credit_ledger",
            target_id=related_id,
            metadata={"reason": reason, "units": units, "kind": "deduct"},
        )
        return {
            "ledger_id": result.ledger_id,
            "balance_after": result.balance_after,
            "amount": result.amount,
            "idempotent_hit": result.idempotent_hit,
        }
    except InsufficientCredits as e:
        ldb.rollback()
        audit.record(
            org_id=org_id,
            actor_type="user" if actor_email else "system",
            actor_id=actor_email or "system",
            action="data_accessed",
            target_type="credit_ledger",
            target_id=related_id,
            metadata={"reason": reason, "units": units, "kind": "insufficient",
                      "requested": e.requested, "available": e.available},
        )
        raise HTTPException(
            status_code=402,
            detail={
                "error": "insufficient_credits",
                "bucket": "context",
                "requested": e.requested,
                "available": e.available,
                "message": "Out of credits — top up or upgrade plan to continue.",
                "reason": reason,
            },
        ) from e
    except HTTPException:
        ldb.rollback()
        raise
    except Exception as e:
        # Ledger transient / DB blip — log loud and continue. We prefer
        # to extract-and-not-bill once over locking the customer out for
        # a transient outage. Founder sees the warning in stderr.
        ldb.rollback()
        log.warning(
            "billing_deduct_failed",
            org_id=org_id, reason=reason, related_id=related_id, error=str(e),
        )
        return None
    finally:
        ldb.close()
