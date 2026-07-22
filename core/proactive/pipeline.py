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

from core.delivery.bands import to_band
from core.foundations.telemetry import get_logger
from core.proactive.store import InsightRow

log = get_logger(__name__)
_legacy_log = logging.getLogger(__name__)


SUPPRESS_WINDOW_HOURS = 24


# ─────────────────────────────────────────────────────────────────────────────
# Rule metadata — read from manifest.json (module-agnostic)
# ─────────────────────────────────────────────────────────────────────────────
# Each module's manifest.json carries a `rule_metadata` block:
#   {
#     "<rule_id>": {
#       "title": "<headline shown in dashboard + Hermes prompts>",
#       "priority": "low|medium|high",
#       "tunable_knobs": [
#         {"fact_predicate": "...", "op": "...", "default_threshold": N}
#       ]
#     }
#   }
# Loaded once per (module_id, process) and cached so adding a new module
# is purely a YAML+JSON change — no Python edits in this file.

_rule_metadata_cache: dict[str, dict[str, dict[str, Any]]] = {}


def _load_rule_metadata(module_id: str) -> dict[str, dict[str, Any]]:
    """Read manifest.json for a module and return its `rule_metadata` block.

    Returns {} (not raises) when the module exists but the manifest has no
    metadata block — that's the path for a brand-new module being scaffolded.
    """
    if module_id in _rule_metadata_cache:
        return _rule_metadata_cache[module_id]
    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = repo_root / "modules" / module_id / "manifest.json"
    if not manifest_path.exists():
        _rule_metadata_cache[module_id] = {}
        return {}
    try:
        with open(manifest_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning(
            "rule_metadata_load_failed", module_id=module_id, error=str(e)
        )
        _rule_metadata_cache[module_id] = {}
        return {}
    rm = data.get("rule_metadata") or {}
    _rule_metadata_cache[module_id] = rm
    return rm


def _rule_title(module_id: str, rule_id: str, conclusion: str) -> str:
    meta = _load_rule_metadata(module_id).get(rule_id) or {}
    return meta.get("title") or conclusion.replace("_", " ").title()


def _rule_priority(module_id: str, rule_id: str) -> str:
    meta = _load_rule_metadata(module_id).get(rule_id) or {}
    return meta.get("priority") or "medium"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — fact coercion, module load, signature, webhook signing
# ─────────────────────────────────────────────────────────────────────────────


_INT_PREDICATES = frozenset({
    # AR
    "days_past_due", "amount_inr", "last_reminder_age_days", "client_late_count_90d",
    # HR
    "days_in_stage", "total_pipeline_days", "offer_expiry_days",
    "interview_score", "days_since_last_contact",
    # CSM
    "mrr_usd", "days_to_renewal", "days_since_last_login", "nps_score",
    "open_tickets", "usage_drop_pct_30d",
    # Sales
    "deal_value", "days_in_current_stage", "contacts_engaged",
    "discount_pct", "gross_margin_pct", "days_to_close",
})

_BOOL_PREDICATES = frozenset({
    "is_vip_client", "active",
    # Sales
    "economic_buyer_engaged", "budget_confirmed", "next_step_scheduled",
    "competitor_poc_active",
})


# ─────────────────────────────────────────────────────────────────────────────
# Tool registry — minimum viable side-effect-class + blast-radius lookup
# ─────────────────────────────────────────────────────────────────────────────
#
# Per the CTO brief (g-i-7): every recommended action carries a side-effect
# class so the autonomy router can decide:
#   irreversible  → notify-first  (human approves before action fires)
#   financial     → flag          (always human-confirmed)
#   reversible    → autonomous-eligible if confidence is high
#   internal      → autonomous (low blast radius, no external party touched)
#
# Each rule's `recommend` field names an action; we map that action to its
# class here. Adding a new vertical means: append the new actions to this
# table. Later this moves into the module manifest; hardcoded for v1 so the
# brief's "no naked recommendations" invariant is honored today.

_TOOL_REGISTRY: dict[str, dict[str, str]] = {
    # AR
    "send_polite_reminder":           {"side_effect": "irreversible", "blast_radius": "small"},
    "send_firm_reminder":             {"side_effect": "irreversible", "blast_radius": "small"},
    "send_preemptive_courtesy_check": {"side_effect": "irreversible", "blast_radius": "small"},
    "escalate_to_phone_call":         {"side_effect": "irreversible", "blast_radius": "medium"},
    "review_client_payment_terms":    {"side_effect": "internal",     "blast_radius": "small"},
    # HR
    "call_candidate_today":           {"side_effect": "irreversible", "blast_radius": "medium"},
    "re_engage_personally":           {"side_effect": "irreversible", "blast_radius": "small"},
    "move_or_reject":                 {"side_effect": "internal",     "blast_radius": "small"},
    "review_fit_or_close":            {"side_effect": "internal",     "blast_radius": "small"},
    "triage_or_reject":               {"side_effect": "internal",     "blast_radius": "small"},
    # CSM
    "schedule_exec_call":             {"side_effect": "reversible",   "blast_radius": "small"},
    "save_call_with_csm":             {"side_effect": "irreversible", "blast_radius": "medium"},
    "escalate_to_support_lead":       {"side_effect": "internal",     "blast_radius": "small"},
    "discovery_call":                 {"side_effect": "reversible",   "blast_radius": "small"},
    "friendly_health_check":          {"side_effect": "reversible",   "blast_radius": "small"},
    # Sales
    "trigger_reengagement_sequence":               {"side_effect": "irreversible", "blast_radius": "medium"},
    "schedule_executive_check_in":                 {"side_effect": "irreversible", "blast_radius": "medium"},
    "get_meeting_with_economic_buyer":             {"side_effect": "irreversible", "blast_radius": "medium"},
    "multithread_to_second_stakeholder":           {"side_effect": "irreversible", "blast_radius": "medium"},
    "reengage_before_competitor_locks_in":         {"side_effect": "irreversible", "blast_radius": "medium"},
    "schedule_differentiation_call_with_champion": {"side_effect": "irreversible", "blast_radius": "medium"},
    "send_lightweight_check_in":                   {"side_effect": "irreversible", "blast_radius": "small"},
    "book_mutual_next_step_now":                   {"side_effect": "irreversible", "blast_radius": "small"},
    "trigger_adoption_outreach":                   {"side_effect": "irreversible", "blast_radius": "small"},
    "flag_to_rep_with_next_action":                {"side_effect": "internal",     "blast_radius": "small"},
    "schedule_pipeline_review":                    {"side_effect": "internal",     "blast_radius": "small"},
    "requalify_or_disqualify":                     {"side_effect": "internal",     "blast_radius": "small"},
    "confirm_budget_and_funding_source":           {"side_effect": "internal",     "blast_radius": "small"},
    "identify_new_champion_immediately":           {"side_effect": "internal",     "blast_radius": "small"},
    "escalate_to_executive_sponsor":               {"side_effect": "internal",     "blast_radius": "medium"},
    "exec_escalate_support_resolution":            {"side_effect": "internal",     "blast_radius": "medium"},
    "require_cfo_approval":                        {"side_effect": "internal",     "blast_radius": "medium"},
    "require_finance_approval":                    {"side_effect": "internal",     "blast_radius": "medium"},
    "require_sales_lead_approval":                 {"side_effect": "internal",     "blast_radius": "small"},
    "apply_standard_volume_terms":                 {"side_effect": "internal",     "blast_radius": "small"},
}


def _sales_memory_view(deal_name: str, facts: dict) -> str:
    """Deal-shaped one-line summary for a sales insight (replaces the AR invoice
    format). Only includes fields actually present, so it degrades cleanly."""
    parts: list[str] = [str(deal_name)]
    dv = facts.get("deal_value")
    if dv is not None:
        try:
            parts.append(f"₹{float(dv):,.0f} deal")
        except (TypeError, ValueError):
            pass
    if facts.get("stage"):
        parts.append(f"stage={facts['stage']}")
    if facts.get("days_in_current_stage") is not None:
        parts.append(f"{facts['days_in_current_stage']}d in stage")
    if facts.get("contacts_engaged") is not None:
        parts.append(f"{facts['contacts_engaged']} contact(s)")
    for key, lbl in (("momentum", "momentum"), ("buying_intent", "buying_intent"), ("sentiment", "sentiment")):
        v = facts.get(key)
        if v is not None:
            try:
                parts.append(f"{lbl}={round(float(v), 2)}")
            except (TypeError, ValueError):
                pass
    for key, lbl in (("objection", "objection"), ("commitment", "we-owe"), ("competitor", "competitor")):
        v = facts.get(key)
        if isinstance(v, str) and v.strip():
            parts.append(f'{lbl}="{v.strip()}"')
    return " · ".join(parts)


def _enrich_sales_facts_from_graph(session, org_id: str, deal_id: str, facts: dict) -> dict:
    """Structural join: a sales deal's facts are keyed by deal_id, but its derived
    signals (sentiment / buying_intent / momentum / importance / ball_in_court)
    live on the ACCOUNT entity. The deal node stores `client_node_id` (set at CSV
    ingest), so resolve deal -> account and merge the account's signals into the
    deal's flat facts. Best-effort; any failure returns facts unchanged."""
    try:
        from sqlalchemy import select as _sel

        from core.graph.store import NodeRow
        from core.signals.runtime import merge_signals_into_facts

        deal_node = (
            session.execute(
                _sel(NodeRow)
                .where(NodeRow.org_id == org_id, NodeRow.canonical_name == str(deal_id))
                .limit(1)
            )
            .scalars()
            .first()
        )
        attrs = getattr(deal_node, "attributes", None) if deal_node else None
        account_node_id = attrs.get("client_node_id") if isinstance(attrs, dict) else None
        if not account_node_id:
            return facts
        acct = session.get(NodeRow, account_node_id)
        account_name = acct.canonical_name if acct else None
        merged = merge_signals_into_facts(
            session,
            org_id=org_id,
            facts=facts,
            subject_node_id=account_node_id,
            subject_name=account_name,
        )
        # Bridge the neural `competitor` signal to the legacy boolean the
        # competition ruleset reads — un-deads `competitor_named_going_quiet`.
        if merged.get("competitor") and "competing_vendor_named" not in merged:
            merged["competing_vendor_named"] = True
        return merged
    except Exception:  # noqa: BLE001
        return facts


def _registry_for_action(action: str) -> dict[str, str]:
    """Returns side_effect + blast_radius for a recommend action. Unknown
    actions default to the safest classification — irreversible + medium —
    so a new module without a registry entry routes notify-first."""
    return _TOOL_REGISTRY.get(action) or {
        "side_effect": "irreversible",
        "blast_radius": "medium",
    }


def _route_for_side_effect(side_effect: str, confidence: float) -> str:
    """The 80/20 autonomy router per the brief.

    irreversible/financial → notify (always human-confirms first)
    reversible             → autonomous if confidence >= 0.75, else notify
    internal               → autonomous (low blast radius)
    """
    if side_effect in ("irreversible", "financial"):
        return "notify"
    if side_effect == "internal":
        return "autonomous"
    # reversible
    return "autonomous" if confidence >= 0.75 else "notify"


# ─────────────────────────────────────────────────────────────────────────────
# Confidence + uncertainty — the response-envelope contract
# ─────────────────────────────────────────────────────────────────────────────


def _confidence_and_uncertainty(
    *,
    facts: dict[str, Any],
    rule_id: str,
    has_active_override: bool,
    other_fires: int,
) -> tuple[float, list[str]]:
    """Compute a confidence in [0,1] + an uncertainty[] list for one firing.

    The symbolic path defaults to high confidence (0.92) because the rule
    only fired when every condition matched. We DEMOTE confidence when the
    facts the rule consumed are themselves weak — missing/stale/contradicted —
    and surface the specific reason in uncertainty[] so a downstream agent
    or human can decide whether to act.

    Honest math, not invented precision. Each demotion is a small fixed
    penalty (0.05–0.1) tied to a named cause. Capped at floor 0.55 so we
    never push a symbolic firing below the action threshold purely from
    uncertainty flags — those are SIGNALS, not vetoes.
    """
    conf = 0.92
    uncertainty: list[str] = []

    # Missing primary signal — the rule fired on a sparse fact set
    if facts.get("last_reminder_age_days") == -1:
        # AR-shape: no prior communication recorded
        uncertainty.append("no_prior_communication_recorded")
        conf -= 0.05
    if facts.get("days_since_last_contact", 0) > 30 and "hr_" in rule_id:
        uncertainty.append("contact_freshness_low")
        conf -= 0.05

    # Override active → threshold was learned, not given. Mark + small demotion.
    if has_active_override:
        uncertainty.append("threshold_tuned_from_limited_outcomes")
        conf -= 0.05

    # Multiple rules fire on the same subject → compound case, partial
    # priority ambiguity. Not a defect (the engine handles them), but the
    # agent should know.
    if other_fires > 0:
        uncertainty.append(f"compound_case_{other_fires}_other_rules_fired")
        conf -= 0.03

    # Stale fact: if days_past_due > 90, the customer signal is old.
    dpd = facts.get("days_past_due")
    if isinstance(dpd, int) and dpd > 90:
        uncertainty.append("fact_age_exceeds_90_days")
        conf -= 0.05

    # Floor — symbolic firings never drop below 0.55. If you don't trust the
    # rule that much, REMOVE the rule, don't keep firing it at low confidence.
    return max(0.55, round(conf, 3)), uncertainty


def _coerce_fact_value(predicate: str, raw: str) -> Any:
    """Cast a facts.object string back to the type rules expect.

    The integer + boolean predicate sets are the union across every module.
    Rule conditions written as `op: ">"` with a numeric `value:` literal
    require integers on the fact side; rules using `op: "=="` against a
    boolean need a real bool, not the string "True".
    """
    if predicate in _INT_PREDICATES:
        try:
            return int(raw)
        except (TypeError, ValueError):
            try:
                return int(float(raw))
            except (TypeError, ValueError):
                return 0
    if predicate in _BOOL_PREDICATES:
        return str(raw).lower() in ("true", "1", "yes")
    return raw


def _load_module_chainer(
    module_id: str,
    session: Session | None = None,
    org_id: str | None = None,
):
    """Locate the module folder and return a loaded ForwardChainer.

    When `session` + `org_id` are provided, applies any active per-org
    threshold overrides (Phase 4 calibration loop) before handing the
    ruleset to the chainer. The overrides are read from
    `org_rule_overrides` and replace the matching Condition.value in
    a CLONED ruleset — the original module RuleSet stays untouched so
    other orgs see the YAML defaults.

    Raises ValueError if the module folder is missing — callers
    translate that to a 404 on the HTTP path.
    """
    from core.modules_framework.loader import load_module_package
    from core.reasoning.rule_engine import ForwardChainer

    repo_root = Path(__file__).resolve().parents[2]  # genios-brain root
    module_path = repo_root / "modules" / module_id
    if not module_path.exists():
        raise ValueError(f"Module {module_id} not installed at {module_path}")
    pkg = load_module_package(module_path)
    ruleset = pkg.ruleset

    if session is not None and org_id is not None:
        ruleset = _apply_org_overrides(
            session, ruleset=ruleset, org_id=org_id, module_id=module_id
        )
    return ForwardChainer(ruleset)


def _apply_org_overrides(
    session: Session,
    *,
    ruleset,
    org_id: str,
    module_id: str,
):
    """Return a new RuleSet with per-org threshold overrides applied.

    Only rules referenced by an active override row are touched; everything
    else is left at its YAML default. The Pydantic models are frozen, so
    we build new instances via `.model_copy(update=...)`.
    """
    from core.foundations.threshold_tuner import get_active_override
    from core.reasoning.rule_loader import Condition, Rule, RuleSet, WhenClause

    new_rules = []
    overrides_applied = 0
    for rule in ruleset.rules:
        override = get_active_override(
            session, org_id=org_id, module_id=module_id, rule_id=rule.id
        )
        if not override:
            new_rules.append(rule)
            continue
        # Walk the rule's `when.all` conditions for the matching fact
        # predicate + operator and replace its `value`.
        if not rule.when.all:
            new_rules.append(rule)
            continue
        patched = False
        new_conds = []
        for cond in rule.when.all:
            if (
                cond.fact == override["fact_predicate"]
                and cond.op.value == override["op"]
            ):
                new_conds.append(cond.model_copy(update={"value": override["threshold_value"]}))
                patched = True
            else:
                new_conds.append(cond)
        if not patched:
            new_rules.append(rule)
            continue
        new_when = rule.when.model_copy(update={"all": new_conds})
        new_rules.append(rule.model_copy(update={"when": new_when}))
        overrides_applied += 1
        log.info(
            "proactive_pipeline_override_applied",
            org_id=org_id,
            rule_id=rule.id,
            predicate=override["fact_predicate"],
            new_value=override["threshold_value"],
        )

    if overrides_applied == 0:
        return ruleset
    return RuleSet(rules=new_rules)


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


def _record_action(
    session: Session,
    *,
    org_id: str,
    insight_id: str,
    webhook_id: str,
    webhook_url: str,
    payload: dict,
    response: dict,
) -> None:
    """Append an action_ledger row for one webhook delivery.

    Keeps the audit trail self-describing — every webhook the engine
    actually fired lives here with its full body + the receiver's
    HTTP response, so a customer can later see *exactly* what GeniOS
    did on their behalf. Failures DO write a row too (outcome=failed)
    so the dashboard's "actions taken" widget can surface delivery
    health, not just successes.

    Idempotency note: signature_hash on the parent proactive_insights
    row already guards against firing the same (rule, invoice) twice
    inside 24h, so per-(insight_id, webhook_id) duplication is bounded
    by that. We don't add a separate uniqueness check here — that
    would mask a legitimate retry surface.
    """
    from app.actions import ledger as _ledger

    ok = bool(response.get("ok"))
    detail = (
        f"http={response.get('status_code')} "
        f"hook={webhook_id} "
        f"snippet={(response.get('response_snippet') or '')[:200]}"
    )
    try:
        _ledger.record(
            session,
            org_id=org_id,
            agent_id="genios-proactive-engine",
            action_type="webhook_delivered",
            risk_tier="external_send",
            target_type="insight",
            target_ref=insight_id,
            payload={
                "webhook_id": webhook_id,
                "webhook_url": webhook_url,
                "insight_payload": payload,
            },
            outcome="success" if ok else "failed",
            outcome_detail=detail,
        )
    except Exception as e:
        log.warning(
            "proactive_action_ledger_failed",
            insight_id=insight_id,
            webhook_id=webhook_id,
            error=str(e),
        )


def _client_name_for_invoice(session: Session, org_id: str, invoice_id: str) -> str:
    """One-row join to surface the *primary* entity's canonical_name for the
    human-readable payload — works across modules (Client for AR, Candidate
    for HR, Account for CSM). Cached by callers if they care about latency.

    Lookup: find the secondary-entity node (by canonical_name = invoice_id),
    follow its outgoing edge to the primary, return that primary's name.
    """
    row = session.execute(
        text(
            """
            SELECT n.canonical_name
            FROM graph_nodes n
            JOIN graph_edges e ON e.to_node = n.id
            JOIN graph_nodes i ON i.id = e.from_node
            WHERE i.org_id = :org
              AND i.canonical_name = :inv
            LIMIT 1
            """
        ),
        {"org": org_id, "inv": invoice_id},
    ).fetchone()
    return row[0] if row else "Unknown"


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def installed_module_ids() -> list[str]:
    """Enumerate every module folder that has a manifest.json. Cached so
    list() is O(1) after the first call inside a process."""
    if not hasattr(installed_module_ids, "_cache"):
        repo_root = Path(__file__).resolve().parents[2]
        modules_dir = repo_root / "modules"
        ids: list[str] = []
        if modules_dir.exists():
            for entry in sorted(modules_dir.iterdir()):
                if not entry.is_dir() or entry.name.startswith("_"):
                    continue
                if (entry / "manifest.json").exists():
                    ids.append(entry.name)
        installed_module_ids._cache = ids  # type: ignore[attr-defined]
    return list(installed_module_ids._cache)  # type: ignore[attr-defined]


def run_all_for_org(
    session: Session,
    *,
    org_id: str,
    source: str = "manual",
) -> dict[str, Any]:
    """Run every installed module's pipeline for one org and aggregate.

    Used by the event subscriber, the hourly Celery beat, and the /v1/scan
    HTTP route — none of those callers know which module's data just
    landed. Each module's chainer fires only on facts that match its
    rule predicates, so AR rules silently no-op on HR facts and vice
    versa; the 24h signature dedupe still applies per (rule, subject).
    """
    aggregate: dict[str, Any] = {
        "source": source,
        "modules": [],
        "insights_fired_total": 0,
        "webhook_success_total": 0,
        "webhooks_called_total": 0,
        "suppressed_dedupe_total": 0,
    }
    for module_id in installed_module_ids():
        r = run_for_org(session, org_id=org_id, module_id=module_id, source=source)
        aggregate["modules"].append({"module_id": module_id, **r})
        aggregate["insights_fired_total"] += int(r.get("insights_fired") or 0)
        aggregate["webhook_success_total"] += int(r.get("webhook_success") or 0)
        aggregate["webhooks_called_total"] += int(r.get("webhooks_called") or 0)
        aggregate["suppressed_dedupe_total"] += int(r.get("suppressed_dedupe") or 0)

    # Timing detectors — the 3 v2-ported time-based signals (going_cold,
    # role_change, overdue_commitment). Module rulesets above key off `facts`
    # predicate changes; these fire on the passage of time instead, reading
    # `graph_nodes` / `facts` directly. Same `proactive_insights` sink, same
    # 24h signature dedupe, same transaction (no commit here). Isolated so a
    # detector-side failure can't sink the module scan that already succeeded.
    try:
        from core.proactive.timing_detectors import run_timing_detectors

        td = run_timing_detectors(session, org_id=org_id)
        aggregate["timing_detectors"] = td
        aggregate["insights_fired_total"] += int(td.get("insights_fired") or 0)
    except Exception as e:  # noqa: BLE001 — never let timing detectors break the scan
        log.warning("proactive_timing_detectors_failed", org_id=org_id, error=str(e))
        aggregate["timing_detectors"] = {"insights_fired": 0, "error": str(e)[:200]}

    # Signal Layer — recompute derived signals (importance / momentum /
    # engagement) from graph state on each scan. Same isolation as the timing
    # detectors: a signal-side failure must never sink the scan that succeeded.
    try:
        from core.signals.runtime import run_symbolic_detectors

        aggregate["signals_computed"] = run_symbolic_detectors(session, org_id=org_id)
    except Exception as e:  # noqa: BLE001 — never let signals break the scan
        log.warning("proactive_signals_failed", org_id=org_id, error=str(e))
        aggregate["signals_computed"] = 0

    # Graph-path — turn the fresh signals into 'important relationship cooling'
    # suggestions (proactive_insights + NBA). Isolated like the detectors above.
    try:
        from core.signals.insight_runner import run_relationship_detectors

        rel = run_relationship_detectors(session, org_id=org_id)
        aggregate["relationship_insights"] = rel
        aggregate["insights_fired_total"] += int(rel.get("insights_fired") or 0)
    except Exception as e:  # noqa: BLE001 — never let it break the scan
        log.warning("proactive_relationship_failed", org_id=org_id, error=str(e))
        aggregate["relationship_insights"] = {"insights_fired": 0, "error": str(e)[:200]}

    return aggregate


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
        chainer = _load_module_chainer(module_id, session=session, org_id=org_id)
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

    # Detect when an org override is active so the confidence helper can
    # surface it as an uncertainty signal.
    from core.foundations.threshold_tuner import get_active_override as _gao

    _override_cache: dict[str, bool] = {}

    def _has_override(rule_id: str) -> bool:
        if rule_id in _override_cache:
            return _override_cache[rule_id]
        present = _gao(session, org_id=org_id, module_id=module_id, rule_id=rule_id) is not None
        _override_cache[rule_id] = present
        return present

    for invoice_id, facts in invoices.items():
        # Signal Layer — enrich this subject's facts with its derived signals
        # (importance / momentum / ball_in_court / ...) so signal-aware rules can
        # fire. Additive + wrapped: caller (uploaded) facts win on conflict, and
        # a signal-read failure must never break the existing rule run.
        try:
            from core.signals.runtime import merge_signals_into_facts

            if module_id == "sales":
                # Deal facts are keyed by deal_id; signals live on the account.
                # Join deal -> account and merge the account's signals.
                facts = _enrich_sales_facts_from_graph(session, org_id, invoice_id, facts)
            else:
                facts = merge_signals_into_facts(
                    session, org_id=org_id, subject_name=invoice_id, facts=facts
                )
        except Exception:  # noqa: BLE001
            pass
        result = chainer.run(facts)
        if not result.proof.steps:
            continue
        client_name = client_name_cache.get(invoice_id) or _client_name_for_invoice(
            session, org_id, invoice_id
        )
        client_name_cache[invoice_id] = client_name

        steps_for_subject = len(result.proof.steps)
        # Best-in-class: one deal surfaces ONE decision, not N near-identical alerts.
        # For sales, emit only the highest-priority firing per deal — its
        # derivation_chain + confidence still reflect ALL the signals that fired.
        emit_steps = result.proof.steps
        if module_id == "sales" and len(emit_steps) > 1:
            emit_steps = [max(emit_steps, key=lambda st: _rule_priority(module_id, st.rule_id))]
        for step in emit_steps:
            candidates_total += 1
            sig_hash = _signature_hash(
                module_id=module_id, rule_id=step.rule_id, subject=invoice_id
            )
            if sig_hash in seen_signatures:
                suppressed += 1
                continue

            priority = _rule_priority(module_id, step.rule_id)
            title = _rule_title(module_id, step.rule_id, step.conclusion)

            # Response-envelope fields per the CTO brief — confidence + named
            # uncertainty[] + tool registry classification + the resulting
            # delivery_route. No naked recommendations from this point on.
            confidence, uncertainty = _confidence_and_uncertainty(
                facts=facts,
                rule_id=step.rule_id,
                has_active_override=_has_override(step.rule_id),
                other_fires=max(0, steps_for_subject - 1),
            )
            recommend_action = step.recommend or step.conclusion
            registry = _registry_for_action(recommend_action)
            delivery_route = _route_for_side_effect(registry["side_effect"], confidence)
            if module_id == "sales":
                # Deal-shaped rendering + a specific, situation-aware next-best-action
                # (names the action + deal + signals) instead of the AR invoice format
                # and a static YAML reason string.
                deal_name = client_name or invoice_id
                memory_view = _sales_memory_view(deal_name, facts)
                from core.actions.recommender import build_next_best_action

                _nba = build_next_best_action(
                    subject_name=deal_name,
                    recommend=recommend_action,
                    signals=facts,
                    reason=step.reason or step.conclusion,
                )
                genios_view = _nba.prescription
            else:
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
                    "confidence": confidence,
                    "uncertainty": uncertainty,
                    "recommend_action": recommend_action,
                    "side_effect_class": registry["side_effect"],
                    "blast_radius": registry["blast_radius"],
                    "delivery_route": delivery_route,
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
                    # Response-envelope fields (CTO brief g-i-7) — every
                    # consumer (Hermes, dashboard, audit) sees the same shape.
                    "confidence": ins["confidence"],
                    "uncertainty": ins["uncertainty"],
                    "recommend_action": ins["recommend_action"],
                    "side_effect_class": ins["side_effect_class"],
                    "blast_radius": ins["blast_radius"],
                },
                grounding_refs_jsonb=[],
                signature_hash=ins["signature_hash"],
                delivery_route=ins["delivery_route"],
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
            # ─── Response envelope per CTO brief (g-i-7) ───
            # No naked recommendations. Every downstream agent / Hermes /
            # dashboard sees the same self-describing shape.
            "envelope": {
                "recommendation": ins["recommend_action"],
                # Customer-facing: qualitative band, not a raw probability
                # (§5 Gate 1). The raw float stays internal in the
                # proactive_insights row's scores_jsonb above.
                "confidence": to_band(ins["confidence"]).value,
                "uncertainty": ins["uncertainty"],
                "side_effect_class": ins["side_effect_class"],
                "blast_radius": ins["blast_radius"],
                "route": ins["delivery_route"],
                "derivation_chain": ins["derivation_chain"],
            },
        }
        # Each webhook delivery is recorded in action_ledger so the dashboard
        # can render "GeniOS sent N reminders" with auditable evidence. The
        # row is also where customer/Hermes feedback gets persisted later
        # (paid / dismissed / escalated) via the /outcome endpoint.
        for hook in active_hooks:
            resp = _sign_and_post(hook, payload)
            webhook_calls.append(resp)
            _record_action(
                session,
                org_id=org_id,
                insight_id=insight_id,
                webhook_id=hook.get("id", ""),
                webhook_url=hook.get("url", ""),
                payload=payload,
                response=resp,
            )
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
