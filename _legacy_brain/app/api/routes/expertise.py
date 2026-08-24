"""Expertise (domain modules) API — read-only surface for the dashboard.

GET  /v1/expertise/domains   — catalog of domain modules + per-org active flag
GET  /v1/expertise/learned   — per-org learned rule-threshold overrides (read-only)
POST /v1/expertise/request   — capture a "please add this domain" request

Locked boundary (MASTER §15 / g-i-5): customers REQUEST domains, they never
AUTHOR them. Modules are static authored knowledge bundled at deploy time; this
surface only READS the catalog + the org's activations and RECORDS requests.
There is deliberately no provisioning / "build your own module" path here.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from core.foundations import audit
from core.modules_framework.bootstrap import MODULES_DIR
from core.modules_framework.registry import Registry

logger = logging.getLogger(__name__)
router = APIRouter()

# Friendly display names for bundled modules. Unknown ids titleize the id.
_FRIENDLY = {
    "sales": "Sales",
    "csm_health": "Customer Success",
    "ar_collection": "AR / Collections",
    "hr_pipeline": "HR / Recruiting",
}


def _humanize(module_id: str) -> str:
    return _FRIENDLY.get(module_id, module_id.replace("_", " ").title())


def _golden_count(module_dir: Path) -> int:
    """Count labeled golden cases (one JSON object per line). Best-effort."""
    f = module_dir / "golden" / "labeled_cases.jsonl"
    if not f.exists():
        return 0
    try:
        return sum(1 for line in f.read_text().splitlines() if line.strip())
    except Exception:
        return 0


def _read_catalog() -> list[dict]:
    """Scan modules/ on disk and return each module's display metadata.

    Disk is the source of truth for module *content* (rules, version, maturity);
    the DB only tracks per-org activation. Reading manifests here keeps the
    endpoint working even before the catalog table is seeded.
    """
    catalog: list[dict] = []
    if not MODULES_DIR.exists():
        return catalog
    for entry in sorted(MODULES_DIR.iterdir()):
        manifest = entry / "manifest.json"
        if not entry.is_dir() or entry.name.startswith("__") or not manifest.exists():
            continue
        try:
            m = json.loads(manifest.read_text())
        except Exception:
            logger.warning("expertise: bad manifest in %s", entry.name)
            continue
        provides = m.get("provides") or {}
        rules = provides.get("rules") or []
        mid = m.get("id", entry.name)
        catalog.append(
            {
                "id": mid,
                "name": _humanize(mid),
                "version": m.get("version", "0.0.0"),
                "maturity": m.get("maturity", "preview"),
                "rule_count": len(rules) if isinstance(rules, list) else 0,
                "golden_cases": _golden_count(entry),
                "covers": rules if isinstance(rules, list) else [],
                "artifacts": provides.get("artifacts") or [],
                "scopes": m.get("requiredScopes") or [],
            }
        )
    return catalog


@router.get("/v1/expertise/domains")
def list_domains(
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Domain modules available to GeniOS + which are active for THIS org.

    `active` precedence:
      1. If the org has explicit activations (org_modules rows), honor them.
      2. Otherwise default GA modules to active, the rest to "available" — this
         matches the product narrative (Sales live; CSM/AR/HR available) without
         requiring per-org seeding.
    """
    catalog = _read_catalog()

    activated_ids: set[str] = set()
    try:
        activated_ids = {a.module_id for a in Registry(db).list_for_org(org_id)}
    except Exception as e:  # table missing / pre-seed — fall back to maturity
        logger.warning("expertise: activation lookup failed (%s)", e)

    domains = []
    for c in catalog:
        active = (c["id"] in activated_ids) if activated_ids else (c["maturity"] == "ga")
        domains.append({**c, "active": active, "status": "active" if active else "available"})

    return {
        "domains": domains,
        "active_count": sum(1 for d in domains if d["active"]),
        "available_count": sum(1 for d in domains if not d["active"]),
    }


@router.get("/v1/expertise/learned")
def learned_patterns(
    module_id: Optional[str] = None,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Per-org learned rule-threshold overrides — the brain's private L2 layer.

    Read-only. Sourced from `org_rule_overrides` (the calibration tuner's
    output). Degrades to an empty list if the table isn't present yet.
    """
    try:
        params: dict = {"oid": org_id}
        sql = """
            SELECT module_id, rule_id, fact_predicate, op, threshold_value,
                   status, source, justification, sample_size,
                   precision_before, precision_after, applied_at
            FROM org_rule_overrides
            WHERE org_id = :oid
        """
        if module_id:
            sql += " AND module_id = :mid"
            params["mid"] = module_id
        sql += " ORDER BY created_at DESC LIMIT 200"
        rows = db.execute(text(sql), params).fetchall()
    except Exception as e:
        logger.warning("expertise: learned-patterns query failed (%s)", e)
        return {"patterns": [], "count": 0}

    patterns = [
        {
            "module_id": r.module_id,
            "rule_id": r.rule_id,
            "predicate": r.fact_predicate,
            "op": r.op,
            "threshold": float(r.threshold_value) if r.threshold_value is not None else None,
            "status": r.status,
            "source": r.source,
            "justification": r.justification,
            "sample_size": r.sample_size,
            "precision_before": r.precision_before,
            "precision_after": r.precision_after,
            "applied_at": r.applied_at.isoformat() if r.applied_at else None,
        }
        for r in rows
    ]
    return {"patterns": patterns, "count": len(patterns)}


class DomainRequest(BaseModel):
    domain: str = Field(min_length=2, max_length=80)
    note: str = Field(default="", max_length=500)


@router.post("/v1/expertise/request")
def request_domain(
    body: DomainRequest,
    org_id: str = Depends(verify_api_key),
):
    """Capture a 'please add this domain' request. Customers request, never author.

    Durable via the immutable audit log (audit.record never raises). GeniOS
    authors the requested domain offline and activates it per-org.
    """
    domain = body.domain.strip()
    audit.record(
        org_id=org_id,
        actor_type="user",
        actor_id=org_id,
        action="domain_requested",
        target_type="module",
        target_id=domain,
        metadata={"note": body.note.strip()},
    )
    return {
        "ok": True,
        "domain": domain,
        "status": "received",
        "message": (
            f"Request for a '{domain}' domain received. GeniOS authors domains — "
            "we'll be in touch."
        ),
    }
