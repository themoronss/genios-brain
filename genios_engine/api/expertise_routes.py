"""Expertise (domain modules) API — the dashboard's Expertise page. Read-only over the L4 pack
system + L6 learned tuning. A "domain" is a pack (sales today); "learned patterns" are the L6
calibration nudges + auto-mutes this tenant has accrued. Customers REQUEST domains, never author
them. These endpoints existed only in the old genios-brain; wiring them onto the new engine's pack
registry so the page shows real data instead of dead calls.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.packs.wiring import BUILTIN_PACKS
from genios_engine.platform.auth import get_current_org
from genios_engine.platform.ids import new_id
from genios_engine.platform.logging import get_logger
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_log = get_logger("genios.expertise")
_graph = make_graph_store()

# The authored Layer-3 Domain Expertise corpus (the NEW system) — three human-authored domains
# (Sales / Admin / Customer Support) with their real capability areas. This replaces the legacy
# BUILTIN_PACKS view for the Expertise page so it shows the actual authored domains + detail.
_CORPUS_ROOT = Path(__file__).resolve().parents[2] / "Domain Expertise"
_ARTIFACT_DIRS = frozenset({"playbooks", "heuristics", "mental-models", "decision-frameworks"})


@lru_cache(maxsize=1)
def _corpus_domains() -> list[dict]:
    """Read the 3 authored domains straight from the corpus YAML (domain.yaml + capability.yaml).
    Read-only, cached once. A malformed file is skipped, never a 500."""
    out: list[dict] = []
    if not _CORPUS_ROOT.is_dir():
        return out
    for droot in sorted(_CORPUS_ROOT.iterdir()):
        dpath = droot / "domain.yaml"
        if not droot.is_dir() or droot.name.startswith("_") or not dpath.is_file():
            continue
        try:
            data = yaml.safe_load(dpath.read_text(encoding="utf-8")) or {}
        except Exception as e:      # noqa: BLE001 — one bad domain must not break the page
            _log.warning("corpus domain %s unreadable: %s", droot.name, e)
            continue
        ident = data.get("identity", {}) if isinstance(data, dict) else {}
        subs = [s for s in (data.get("subdomains") or []) if isinstance(s, dict)]
        cap_files = list(droot.rglob("capability.yaml"))
        artifacts = sum(1 for p in droot.rglob("*.yaml")
                        if _ARTIFACT_DIRS & set(p.relative_to(droot).parts))
        out.append({
            "id": ident.get("id") or droot.name,
            "name": ident.get("name") or droot.name.replace(" Expertise", ""),
            "version": str(ident.get("version") or "0.1.0"),
            "status": ident.get("status") or "draft",
            "description": " ".join((data.get("description") or "").split()),
            "question": data.get("question") or "",
            "subdomain_count": len(subs),
            "capability_count": len(cap_files),
            "artifact_count": artifacts,
            "subdomains": [{
                "id": s.get("id"),
                "name": s.get("name"),
                "question": s.get("question") or "",
                "note": " ".join((s.get("note") or "").split())[:280],
                "capabilities": [str(x) for x in (s.get("capabilities") or [])],
            } for s in subs],
            "active": True,             # authored + present in the corpus
        })
    return out

# per-pack display metadata the manifest doesn't carry (kept small + explicit, not guessed).
_MATURITY = {"sales": "ga", "general": "ga"}
_DISPLAY = {"sales": "Sales", "general": "General"}
# rule_id → pack_id, built from the registry's own manifests — so learned patterns (below)
# attribute a nudge/mute to the pack that actually owns the rule, not a hardcoded guess.
_RULE_PACK = {r["id"]: p["id"] for p in BUILTIN_PACKS for r in p.get("rules", [])}


def _require_graph():
    if _graph is None:
        raise HTTPException(400, "graph store not configured (needs DATABASE_URL)")


def _domain_from_pack(pack: dict, active: bool) -> dict:
    rules = pack.get("rules", [])
    plays = pack.get("plays", {})
    scopes = sorted({r.get("scope") for r in rules if r.get("scope")})
    covers = pack.get("schema", {}).get("signal_vocab", []) or [r["reason_code"] for r in rules]
    artifacts = sorted({p.get("artifact", "") for p in plays.values() if p.get("artifact")})
    pid = pack["id"]
    return {
        "id": pid,
        "name": _DISPLAY.get(pid, pid.replace("_", " ").title()),
        "version": pack.get("version", "1.0.0"),
        "maturity": _MATURITY.get(pid, "preview"),
        "rule_count": len(rules),
        "golden_cases": 0,                       # not tracked in the engine yet — honest zero
        "covers": covers,
        "artifacts": artifacts,
        "scopes": scopes,
        "active": active,
        "status": "active" if active else "available",
    }


@router.get("/v1/expertise/domains")
def expertise_domains(org_id: str = Depends(get_current_org)) -> dict:
    """The authored Layer-3 Domain Expertise (Sales / Admin / Customer Support) with real detail —
    reads the corpus, NOT the legacy BUILTIN_PACKS."""
    domains = _corpus_domains()
    return {"domains": domains,
            "active_count": sum(1 for d in domains if d["active"]),
            "available_count": sum(1 for d in domains if not d["active"])}


@router.get("/v1/expertise/learned")
def expertise_learned(module_id: str | None = None,
                      org_id: str = Depends(get_current_org)) -> dict:
    """L6 learned tuning for this tenant: gate nudges (calibration_nudges) + auto-mutes (rule_mutes).
    These ARE the per-org rule overrides the brain has learned — never author-written."""
    _require_graph()
    patterns: list[dict] = []
    with _graph.engine.connect() as c:
        for r in c.execute(text(
                "select rule_id, param, before_val, after_val, direction, precision, impressions, "
                "created_at from calibration_nudges where org_id=:o order by created_at desc limit 100"),
                {"o": org_id}):
            patterns.append({
                "module_id": _RULE_PACK.get(r.rule_id, "sales"), "rule_id": r.rule_id,
                "predicate": r.param,
                "op": r.direction, "threshold": float(r.after_val) if r.after_val is not None else None,
                "status": "active", "source": "tuner",
                "justification": f"{r.direction} — precision {r.precision} over {r.impressions} impressions",
                "sample_size": int(r.impressions) if r.impressions is not None else None,
                "precision_before": None,
                "precision_after": float(r.precision) if r.precision is not None else None,
                "applied_at": r.created_at.isoformat() if r.created_at else None})
        for r in c.execute(text(
                "select rule_id, reason, precision, impressions, muted_at from rule_mutes "
                "where org_id=:o and active order by muted_at desc"), {"o": org_id}):
            patterns.append({
                "module_id": _RULE_PACK.get(r.rule_id, "sales"), "rule_id": r.rule_id,
                "predicate": "gate.mute",
                "op": "mute", "threshold": None, "status": "reverted", "source": "tuner",
                "justification": f"auto-muted ({r.reason}) — precision {r.precision} over {r.impressions}",
                "sample_size": int(r.impressions) if r.impressions is not None else None,
                "precision_before": float(r.precision) if r.precision is not None else None,
                "precision_after": None,
                "applied_at": r.muted_at.isoformat() if r.muted_at else None})
    if module_id:
        patterns = [p for p in patterns if p["module_id"] == module_id]
    return {"patterns": patterns, "count": len(patterns)}


class DomainRequest(BaseModel):
    domain: str
    note: str = ""


@router.post("/v1/expertise/request")
def expertise_request(body: DomainRequest, org_id: str = Depends(get_current_org)) -> dict:
    """Record a customer's request for a new domain pack (they can't author one). Persisted so the
    team sees demand; returns an honest 'received' — no fake ETA."""
    _require_graph()
    with _graph.engine.begin() as c:
        c.execute(text(
            "insert into domain_requests (id, org_id, domain, note, status) "
            "values (:id,:o,:d,:n,'received')"),
            {"id": new_id("dreq"), "o": org_id, "d": body.domain.strip()[:80],
             "n": (body.note or "").strip()[:500]})
    return {"ok": True, "domain": body.domain.strip(), "status": "received",
            "message": "Request received — our team reviews new-domain requests before enabling them."}
