"""Shared proactive pipeline — load facts, run rules, dedupe, deliver.

Single entry point used by THREE callers:

  1. The bus subscriber in `event_subscriber.py` — debounced per org, fires
     ~5s after the last MemoryItem of a burst (the natural "I just uploaded a
     CSV, do your thing" trigger).
  2. The Celery beat tick — periodic safety net for slow-burn rules that
     don't fire on a single fact change (e.g. `client_late_count_90d` crosses
     a threshold purely because today's date moved).
  3. The `/v1/scan` endpoint — manual escape hatch for the dashboard
     "Scan now" button. Same code path so a manual scan can't behave
     differently from an automatic one.

The 24-hour idempotency lives here — every emitted Insight has a stable
`signature_hash` (rule_id + invoice_id + org_id) and we suppress any
candidate whose signature already appeared inside `SUPPRESS_WINDOW_HOURS`.
That's how a customer re-uploading the same CSV doesn't get 15 fresh
emails for the same overdue invoices.

Plan alignment: g-i-4 (proactive emit) + g-i-7 (delivery). Dedupe module
already implements the 24h signature window per MD §1.1.1; this pipeline
just wires it to the live ForwardChainer + the registered webhooks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid as _uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.foundations.telemetry import get_logger
from core.proactive.store import InsightRow

log = get_logger(__name__)
_legacy_log = logging.getLogger(__name__)


SUPPRESS_WINDOW_HOURS = 24


# ─────────────────────────────────────────────────────────────────────────────
# Rule metadata (priority + headline title)
# ─────────────────────────────────────────────────────────────────────────────
# Lifted from app/api/routes/proactive.py to keep all rule-meta in one place.
# When a customer plugs in a custom module these will move into module
# manifest.json; for now AR ships hardcoded.

_RULE_PRIORITY: dict[str, str] = {
    "ar_gentle_first_nudge": "low",
    "ar_firm_second_reminder": "medium",
    "ar_phone_call_escalation": "high",
    "ar_large_invoice_preemptive": "medium",
    "ar_repeat_late_payer_flag": "high",
}

_RULE_TITLE: dict[str, str] = {
    "ar_gentle_first_nudge": "Polite reminder due",
    "ar_firm_second_reminder": "Firm reminder needed",
    "ar_phone_call_escalation": "Escalate — phone call needed",
    "ar_large_invoice_preemptive": "Large invoice due soon — courtesy check",
    "ar_repeat_late_payer_flag": "Client paid late repeatedly — review terms",
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — fact coercion, module load, signature, webhook signing
# ─────────────────────────────────────────────────────────────────────────────


def _coerce_fact_value(predicate: str, raw: str) -> Any:
    """Cast a facts.object string back to the type rules expect."""
    if predicate in (
        "days_past_due",
        "amount_inr",
        "last_reminder_age_days",
        "client_late_count_90d",
    ):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0
    if predicate == "is_vip_client":
        return str(raw).lower() in ("true", "1", "yes")
    return raw


def _load_module_chainer(module_id: str):
    """Locate the module folder and return a loaded ForwardChainer.

    Resolves from repo root → modules/<id>. Raises ValueError if missing —
    callers translate that to a 404 on the HTTP path.
    """
    from core.modules_framework.loader import load_module_package
    from core.reasoning.rule_engine import ForwardChainer

    repo_root = Path(__file__).resolve().parents[2]  # genios-brain root
    module_path = repo_root / "modules" / module_id
    if not module_path.exists():
        raise ValueError(f"Module {module_id} not installed at {module_path}")
    pkg = load_module_package(module_path)
    return ForwardChainer(pkg.ruleset)


def _signature_hash(*, module_id: str, rule_id: str, subject: str) -> str:
    """Deterministic 32-char hash for the 24h dedupe window.

    Subject is the invoice id (or whatever the rule's primary entity is)
    so re-firing the SAME rule on the SAME invoice within 24h is the
    "already told you" case we want to suppress. Different rules on the
    same invoice are independent (founder needs to know about both a
    firm-reminder AND a repeat-late flag for the same compound case).
    """
    raw = f"{module_id}|{rule_id}|{subject}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _sign_and_post(hook: dict, payload: dict) -> dict[str, Any]:
    """Sign + POST a webhook payload with the multi-format header set."""
    body = json.dumps(payload, default=str)
    secret = hook.get("secret", "")
    digest_hex = hmac.new(
        secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Genios-Signature": "sha256=" + digest_hex,
        "X-Genios-Event": "insight",
        "X-GitHub-Event": "insight",
        "X-Hub-Signature-256": "sha256=" + digest_hex,
        "X-Webhook-Signature": digest_hex,
    }
    try:
        resp = requests.post(hook["url"], data=body, headers=headers, timeout=10)
        return {
            "webhook_id": hook["id"],
            "status_code": resp.status_code,
            "ok": 200 <= resp.status_code < 300,
            "response_snippet": resp.text[:200],
        }
    except requests.RequestException as e:
        return {
            "webhook_id": hook["id"],
            "status_code": 0,
            "ok": False,
            "response_snippet": f"network: {str(e)[:200]}",
        }


def _load_active_webhooks(session: Session, org_id: str) -> list[dict]:
    """Read registered webhooks. Mirrors `app.api.routes.proactive._read_hooks`.

    Storage is Redis (`webhooks:<org_id>` key) — the plan doc says JSONB on
    `orgs.metadata` but the live implementation never moved off the Redis
    KV. Keeping the pipeline aligned with what the registration endpoint
    actually writes — until the migration to JSONB lands.
    """
    try:
        from app.redis_client import redis_client as _r

        raw = _r.get(f"webhooks:{org_id}")
        if not raw:
            return []
        hooks = json.loads(raw)
    except Exception as e:
        log.warning("proactive_pipeline_webhook_load_failed", org_id=org_id, error=str(e))
        return []
    return [h for h in hooks if h.get("is_active", True)]


def _client_name_for_invoice(session: Session, org_id: str, invoice_id: str) -> str:
    """One-row join to surface the Client.canonical_name for the human-readable
    payload. Cached by callers if they care about latency."""
    row = session.execute(
        text(
            """
            SELECT n.canonical_name
            FROM graph_nodes n
            JOIN graph_edges e ON e.to_node = n.id
            JOIN graph_nodes i ON i.id = e.from_node
            WHERE i.org_id = :org
              AND i.canonical_name = :inv
              AND n.type = 'client'
            LIMIT 1
            """
        ),
        {"org": org_id, "inv": invoice_id},
    ).fetchone()
    return row[0] if row else "Unknown client"


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def run_for_org(
    session: Session,
    *,
    org_id: str,
    module_id: str = "ar_collection",
    source: str = "manual",
) -> dict[str, Any]:
    """Load facts, run rules, dedupe vs 24h history, deliver to webhooks.

    Args:
        session: caller-owned SQLAlchemy session — the pipeline does NOT commit
            (caller decides transaction boundaries).
        org_id: per-org scoping.
        module_id: which module's ruleset to evaluate. Today only `ar_collection`.
        source: where this run came from. Used in audit + log tags only.
            One of "event" | "manual" | "cron".

    Returns:
        {
          "module_id": str,
          "source": str,
          "invoices_evaluated": int,
          "candidates": int,              # raw rule firings
          "suppressed_dedupe": int,       # squelched by 24h window
          "insights_fired": int,          # actually emitted + delivered
          "webhooks_called": int,
          "webhook_success": int,
          "firings": list[dict],          # per-insight summary (audit-friendly)
          "webhook_responses": list[dict],
        }
    """
    try:
        chainer = _load_module_chainer(module_id)
    except ValueError as e:
        log.warning("proactive_pipeline_module_missing", org_id=org_id, error=str(e))
        return {
            "module_id": module_id,
            "source": source,
            "invoices_evaluated": 0,
            "candidates": 0,
            "suppressed_dedupe": 0,
            "insights_fired": 0,
            "webhooks_called": 0,
            "webhook_success": 0,
            "firings": [],
            "webhook_responses": [],
            "error": str(e),
        }

    # 1) Load facts grouped by subject (invoice_id) — coerce types so the
    # rule engine's numeric comparisons work against DB strings.
    rows = session.execute(
        text(
            """
            SELECT subject, predicate, object
            FROM facts
            WHERE org_id = :org
              AND source_item_id LIKE 'upload:%'
            ORDER BY subject, predicate
            """
        ),
        {"org": org_id},
    ).fetchall()

    invoices: dict[str, dict[str, Any]] = {}
    for r in rows:
        invoices.setdefault(r.subject, {})[r.predicate] = _coerce_fact_value(
            r.predicate, r.object
        )

    if not invoices:
        return {
            "module_id": module_id,
            "source": source,
            "invoices_evaluated": 0,
            "candidates": 0,
            "suppressed_dedupe": 0,
            "insights_fired": 0,
            "webhooks_called": 0,
            "webhook_success": 0,
            "firings": [],
            "webhook_responses": [],
            "note": "No facts uploaded yet — drop a CSV in Resources first.",
        }

    # 2) Cheap upfront read of existing signatures within the window —
    # one query instead of one-per-firing.
    cutoff = datetime.now(UTC) - timedelta(hours=SUPPRESS_WINDOW_HOURS)
    seen_signatures: set[str] = {
        row[0]
        for row in session.execute(
            text(
                """
                SELECT signature_hash
                FROM proactive_insights
                WHERE org_id = :org
                  AND created_at >= :cutoff
                """
            ),
            {"org": org_id, "cutoff": cutoff},
        ).fetchall()
    }

    # 3) Per-invoice fact dict → rules → candidates. Drop anything whose
    # signature is in seen_signatures (24h suppression).
    client_name_cache: dict[str, str] = {}
    candidates_total = 0
    suppressed = 0
    new_insights: list[dict[str, Any]] = []  # for delivery

    for invoice_id, facts in invoices.items():
        result = chainer.run(facts)
        if not result.proof.steps:
            continue
        client_name = client_name_cache.get(invoice_id) or _client_name_for_invoice(
            session, org_id, invoice_id
        )
        client_name_cache[invoice_id] = client_name

        for step in result.proof.steps:
            candidates_total += 1
            sig_hash = _signature_hash(
                module_id=module_id, rule_id=step.rule_id, subject=invoice_id
            )
            if sig_hash in seen_signatures:
                suppressed += 1
                continue

            priority = _RULE_PRIORITY.get(step.rule_id, "medium")
            title = _RULE_TITLE.get(
                step.rule_id, step.conclusion.replace("_", " ").title()
            )
            memory_view = (
                f"Invoice {invoice_id} for {client_name}: "
                f"₹{facts.get('amount_inr', 0):,} · "
                f"{facts.get('days_past_due', 'n/a')} days past due · "
                f"status={facts.get('payment_status', 'n/a')} · "
                f"reminder_age={facts.get('last_reminder_age_days', -1)} · "
                f"client_late_count_90d={facts.get('client_late_count_90d', 0)} · "
                f"vip={facts.get('is_vip_client', False)}"
            )
            genios_view = step.reason or step.conclusion

            new_insights.append(
                {
                    "signature_hash": sig_hash,
                    "rule_id": step.rule_id,
                    "conclusion": step.conclusion,
                    "invoice_id": invoice_id,
                    "client_name": client_name,
                    "priority": priority,
                    "title": title,
                    "memory_view": memory_view,
                    "genios_view": genios_view,
                    "derivation_chain": [
                        {
                            "rule_id": s.rule_id,
                            "rule_module": getattr(s, "rule_module", module_id),
                            "rule_priority": getattr(s, "rule_priority", 0),
                            "conclusion": s.conclusion,
                            "matched_facts": getattr(s, "matched_facts", {}),
                            "reason": s.reason,
                            "hard": getattr(s, "hard", False),
                        }
                        for s in result.proof.steps
                    ],
                }
            )
            # Add the just-emitted signature to the in-process seen-set so a
            # rule that fires for the SAME (rule, invoice) twice within this
            # single run (shouldn't happen, but defensive) doesn't double-emit.
            seen_signatures.add(sig_hash)

    # 4) Persist + deliver every kept insight. Webhooks loaded once.
    active_hooks = _load_active_webhooks(session, org_id)
    webhook_calls: list[dict[str, Any]] = []
    fired_summary: list[dict[str, Any]] = []

    for ins in new_insights:
        # Persist the proactive_insights row first — gives us a stable id
        # for the webhook payload AND populates the 24h cache for future runs.
        #
        # scores_jsonb carries the human-readable headline + the rule lineage
        # the dashboard needs to render a useful list. Keeping these on the
        # row means the /insights endpoint doesn't have to re-join the
        # graph at read time.
        insight_id = str(_uuid.uuid4())
        session.add(
            InsightRow(
                id=insight_id,
                org_id=org_id,
                type="risk",  # AR rules all map to RISK in InsightType taxonomy
                primary_entity=ins["invoice_id"],
                root_cause_edge="",  # symbolic-only rules — no graph edge
                derivation_chain_jsonb=ins["derivation_chain"],
                foresight_jsonb=None,
                scores_jsonb={
                    "rule_id": ins["rule_id"],
                    "priority": ins["priority"],          # low | medium | high
                    "title": ins["title"],                # "Firm reminder needed"
                    "category": ins["conclusion"],        # "invoice_needs_firm_reminder"
                    "client_name": ins["client_name"],    # "Mehta Imports"
                    "memory_view": ins["memory_view"],    # one-line fact summary
                    "genios_view": ins["genios_view"],    # rule reason
                },
                grounding_refs_jsonb=[],
                signature_hash=ins["signature_hash"],
                delivery_route="notify",
            )
        )

        payload = {
            "event": "insight",
            "insight_id": insight_id,
            "org_id": org_id,
            "type": "ar_collection",
            "rule_id": ins["rule_id"],
            "invoice_id": ins["invoice_id"],
            "priority": ins["priority"],
            "category": ins["conclusion"],
            "title": ins["title"],
            "contact_name": ins["client_name"],
            "contact_id": None,
            "memory_view": ins["memory_view"],
            "genios_view": ins["genios_view"],
            "fact": ins["memory_view"],
            "analysis": ins["genios_view"],
            "generated_at": datetime.now(UTC).isoformat(),
        }
        for hook in active_hooks:
            webhook_calls.append(_sign_and_post(hook, payload))
        fired_summary.append(
            {
                "invoice_id": ins["invoice_id"],
                "client_name": ins["client_name"],
                "rule_id": ins["rule_id"],
                "priority": ins["priority"],
                "title": ins["title"],
                "signature_hash": ins["signature_hash"],
            }
        )

    # Caller flushes/commits — we leave the session as-is.
    session.flush()
    log.info(
        "proactive_pipeline_run",
        org_id=org_id,
        module_id=module_id,
        source=source,
        invoices=len(invoices),
        candidates=candidates_total,
        suppressed=suppressed,
        emitted=len(new_insights),
        webhooks=len(webhook_calls),
        webhook_ok=sum(1 for w in webhook_calls if w.get("ok")),
    )

    return {
        "module_id": module_id,
        "source": source,
        "invoices_evaluated": len(invoices),
        "candidates": candidates_total,
        "suppressed_dedupe": suppressed,
        "insights_fired": len(new_insights),
        "webhooks_called": len(webhook_calls),
        "webhook_success": sum(1 for w in webhook_calls if w.get("ok")),
        "firings": fired_summary,
        "webhook_responses": webhook_calls,
    }
