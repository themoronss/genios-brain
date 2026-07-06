"""Structured CSV ingestion — bypass LLM extraction for tabular data.

This sits next to uploads.py. The Resources upload endpoint detects `.csv`
and routes here instead of the chunk-and-LLM path. Why a separate path:

  * Tabular data has stable column → fact-predicate mapping. Letting the
    LLM re-discover it per chunk produces inconsistent predicate names
    ("amount" vs "amount_inr" vs "total") that break module rules.
  * Customers pay LLM token cost otherwise. 35-row CSV would burn ~35 × ₹0.29
    in Haiku extraction; here it's $0.
  * Derived facts the LLM CAN'T compute reliably (days_past_due,
    client_late_count_90d) get computed deterministically from the data.

UX contract:
  * Customer uploads any CSV; we auto-map common column-name synonyms to
    canonical predicates module rules consume.
  * Unmapped columns are surfaced back in the response so the customer
    knows what was kept and what was dropped — no silent loss.
  * No "connection_id" or "source_type" picker — we synthesize them
    from the filename. The Resources page stays the single entry point.

g-i-1 invariant (per GENIOS_V2_PLAN.md): every fact reaches the graph via
the MemoryItem bus. This module honors that by emitting one MemoryItem
per row carrying a `metadata.structured_facts` hint — the g-i-3 ingest
subscriber recognizes the hint and persists deterministically (no LLM
call). Single pipeline, two modes.
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from core.foundations.telemetry import get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Per-module column profiles
# ─────────────────────────────────────────────────────────────────────────────
#
# A profile owns the column→fact synonyms for ONE module + the entity-shape
# the structured-facts hint should emit. `signature_columns` are the
# canonical predicates whose presence in the CSV implies "this CSV belongs
# to this module" — used by `detect_module()` to auto-route a CSV upload to
# the right ruleset without making the customer pick from a dropdown.
#
# Add a new vertical module by adding a profile here. No other code in
# csv_ingest.py needs to change.

@dataclass(frozen=True)
class ModuleProfile:
    module_id: str
    primary_entity_type: str       # eg "client" (the Client node)
    secondary_entity_type: str     # eg "invoice" (the Invoice node)
    edge_predicate: str            # eg "issued_to"
    column_synonyms: dict[str, str]
    signature_columns: tuple[str, ...]  # canonical predicates that imply this module


# `entity_name` is special: that column's value becomes the primary entity's
# canonical_name. `entity_id` is the secondary entity's stable ID. Everything
# else is emitted as a FactRow under the secondary-entity subject.
_AR_SYNONYMS: dict[str, str] = {
    # ── Invoice ID (becomes Invoice entity stable id) ───────────────────────
    "invoice_id": "entity_id",
    "invoice_number": "entity_id",
    "invoice_no": "entity_id",
    "id": "entity_id",
    "ref": "entity_id",
    "reference": "entity_id",
    # ── Client entity name (becomes Client.canonical_name) ──────────────────
    "client_name": "entity_name",
    "customer_name": "entity_name",
    "vendor_name": "entity_name",
    "company": "entity_name",
    "account_name": "entity_name",
    "name": "entity_name",
    # ── Client contact attributes (stored on Client node) ───────────────────
    "client_email": "client_email",
    "customer_email": "client_email",
    "email": "client_email",
    "contact_email": "client_email",
    "client_phone": "client_phone",
    "customer_phone": "client_phone",
    "phone": "client_phone",
    "contact": "client_phone",
    "mobile": "client_phone",
    # ── Invoice facts (the module rules read these) ─────────────────────────
    "amount_inr": "amount_inr",
    "amount": "amount_inr",
    "total": "amount_inr",
    "value": "amount_inr",
    "price": "amount_inr",
    "invoice_amount": "amount_inr",
    "due_date": "due_date",
    "due": "due_date",
    "payment_due": "due_date",
    "pay_by": "due_date",
    "issue_date": "issue_date",
    "invoice_date": "issue_date",
    "created": "issue_date",
    "date": "issue_date",
    "payment_status": "payment_status",
    "status": "payment_status",
    "state": "payment_status",
    "last_reminder_sent": "last_reminder_sent",
    "last_followup": "last_reminder_sent",
    "last_contacted": "last_reminder_sent",
    "last_reminder": "last_reminder_sent",
    "is_vip_client": "is_vip_client",
    "is_vip": "is_vip_client",
    "vip": "is_vip_client",
    "important": "is_vip_client",
    "priority_client": "is_vip_client",
    "payment_terms": "payment_terms",
    "terms": "payment_terms",
    "net_days": "payment_terms",
    "project_name": "project_name",
    "project": "project_name",
    "description": "project_name",
    "work_done": "project_name",
    "service": "project_name",
    "notes": "notes",
    "comments": "notes",
    "remarks": "notes",
}


_HR_SYNONYMS: dict[str, str] = {
    # Candidate stable id (becomes Candidate.canonical_name)
    "candidate_id": "entity_id",
    "id": "entity_id",
    "ref": "entity_id",
    # Candidate display name (used as the primary entity, the role they're
    # interviewing for becomes a secondary entity)
    "candidate_name": "entity_name",
    "name": "entity_name",
    "applicant_name": "entity_name",
    # Role being interviewed for — becomes the secondary entity (the role
    # the candidate is in the pipeline for)
    "role": "secondary_entity",
    "role_name": "secondary_entity",
    "position": "secondary_entity",
    "title": "secondary_entity",
    "job": "secondary_entity",
    # Contact attrs
    "candidate_email": "candidate_email",
    "email": "candidate_email",
    "candidate_phone": "candidate_phone",
    "phone": "candidate_phone",
    # Facts the rules read
    "stage": "stage",
    "pipeline_stage": "stage",
    "status": "stage",
    "days_in_stage": "days_in_stage",
    "stage_age_days": "days_in_stage",
    "total_pipeline_days": "total_pipeline_days",
    "pipeline_days": "total_pipeline_days",
    "applied_days_ago": "total_pipeline_days",
    "offer_expiry_days": "offer_expiry_days",
    "offer_expires_in_days": "offer_expiry_days",
    "offer_expiry": "offer_expiry_days",
    "interview_score": "interview_score",
    "score": "interview_score",
    "rating": "interview_score",
    "days_since_last_contact": "days_since_last_contact",
    "last_contact_days": "days_since_last_contact",
    "last_touched_days": "days_since_last_contact",
    "active": "active",
    "is_active": "active",
    "notes": "notes",
    "comments": "notes",
}


_CSM_SYNONYMS: dict[str, str] = {
    # Account stable id (becomes Account.canonical_name) — also acts as the
    # primary entity because CSM tracks accounts directly (no secondary
    # "invoice"-style child).
    "account_id": "entity_id",
    "id": "entity_id",
    "ref": "entity_id",
    "account_name": "entity_name",
    "company": "entity_name",
    "customer_name": "entity_name",
    "name": "entity_name",
    # CSM owner — becomes secondary entity (the rep)
    "csm_owner": "secondary_entity",
    "owner": "secondary_entity",
    "rep": "secondary_entity",
    # Contact attrs
    "account_email": "account_email",
    "email": "account_email",
    # Facts the rules read
    "status": "status",
    "account_status": "status",
    "subscription_status": "status",
    "mrr_usd": "mrr_usd",
    "mrr": "mrr_usd",
    "monthly_revenue": "mrr_usd",
    "days_to_renewal": "days_to_renewal",
    "renewal_days": "days_to_renewal",
    "renewal_in_days": "days_to_renewal",
    "days_since_last_login": "days_since_last_login",
    "last_login_days": "days_since_last_login",
    "last_active_days": "days_since_last_login",
    "nps_score": "nps_score",
    "nps": "nps_score",
    "open_tickets": "open_tickets",
    "tickets_open": "open_tickets",
    "support_tickets": "open_tickets",
    "usage_drop_pct_30d": "usage_drop_pct_30d",
    "usage_drop_pct": "usage_drop_pct_30d",
    "usage_drop_30d": "usage_drop_pct_30d",
    "notes": "notes",
    "comments": "notes",
}


_SALES_SYNONYMS: dict[str, str] = {
    # Deal / opportunity identifier → the Deal (secondary entity) stable id.
    # Deal name is the reliable identifier across CRM exports (HubSpot,
    # Salesforce), so it doubles as the id when no explicit id column exists.
    "deal_id": "entity_id",
    "opportunity_id": "entity_id",
    "opp_id": "entity_id",
    "deal_name": "entity_id",
    "opportunity_name": "entity_id",
    "opportunity": "entity_id",
    "deal": "entity_id",
    "id": "entity_id",
    # Account / company → primary entity canonical_name.
    "account_name": "entity_name",
    "account": "entity_name",
    "company": "entity_name",
    "company_name": "entity_name",
    "customer_name": "entity_name",
    "customer": "entity_name",
    "client_name": "entity_name",
    "name": "entity_name",
    # Contact attrs on the account.
    "contact_email": "client_email",
    "email": "client_email",
    "contact_phone": "client_phone",
    "phone": "client_phone",
    "contact": "client_phone",
    # ── Deal facts the sales rules read ──────────────────────────────────
    "stage": "stage",
    "deal_stage": "stage",
    "sales_stage": "stage",
    "pipeline_stage": "stage",
    "status": "stage",
    "amount": "deal_value",
    "deal_value": "deal_value",
    "value": "deal_value",
    "deal_amount": "deal_value",
    "acv": "deal_value",
    "arr": "deal_value",
    "contract_value": "deal_value",
    "close_date": "close_date",
    "expected_close_date": "close_date",
    "expected_close": "close_date",
    "close": "close_date",
    "days_in_stage": "days_in_current_stage",
    "days_in_current_stage": "days_in_current_stage",
    "stage_age_days": "days_in_current_stage",
    "days_since_last_contact": "days_since_last_contact",
    "last_activity_days": "days_since_last_contact",
    "last_contact_days": "days_since_last_contact",
    "last_activity_date": "last_activity_date",
    "last_activity": "last_activity_date",
    "last_contacted": "last_activity_date",
    "contacts_engaged": "contacts_engaged",
    "num_contacts": "contacts_engaged",
    "number_of_contacts": "contacts_engaged",
    "associated_contacts": "contacts_engaged",
    "stakeholders": "contacts_engaged",
    "next_step": "next_step",
    "next_activity": "next_step",
    "next_activity_date": "next_step",
    "next_step_date": "next_step",
    "next_meeting": "next_step",
    "economic_buyer_engaged": "economic_buyer_engaged",
    "economic_buyer": "economic_buyer_engaged",
    "eb_engaged": "economic_buyer_engaged",
    "budget_confirmed": "budget_confirmed",
    "budget": "budget_confirmed",
    "discount_pct": "discount_pct",
    "discount": "discount_pct",
    "gross_margin_pct": "gross_margin_pct",
    "margin": "gross_margin_pct",
    "competitor_poc_active": "competitor_poc_active",
    "competitor_active": "competitor_poc_active",
    "competitor": "competitor_poc_active",
    "champion_status": "champion_status",
    "champion": "champion_status",
    "nps_score": "nps_score",
    "nps": "nps_score",
    "days_to_renewal": "days_to_renewal",
    "usage_drop_pct_30d": "usage_drop_pct_30d",
    "notes": "notes",
    "comments": "notes",
}


# Public registry — single source of truth keyed by module_id.
MODULE_PROFILES: dict[str, ModuleProfile] = {
    "ar_collection": ModuleProfile(
        module_id="ar_collection",
        primary_entity_type="client",
        secondary_entity_type="invoice",
        edge_predicate="issued_to",
        column_synonyms=_AR_SYNONYMS,
        # An AR CSV is one that ships amount + due_date + payment_status.
        signature_columns=("amount_inr", "due_date", "payment_status"),
    ),
    "hr_pipeline": ModuleProfile(
        module_id="hr_pipeline",
        primary_entity_type="candidate",
        secondary_entity_type="role",
        edge_predicate="applied_for",
        column_synonyms=_HR_SYNONYMS,
        signature_columns=("stage", "days_in_stage", "interview_score"),
    ),
    "csm_health": ModuleProfile(
        module_id="csm_health",
        primary_entity_type="account",
        secondary_entity_type="owner",
        edge_predicate="owned_by",
        column_synonyms=_CSM_SYNONYMS,
        signature_columns=("mrr_usd", "days_to_renewal", "nps_score"),
    ),
    "sales": ModuleProfile(
        module_id="sales",
        primary_entity_type="account",
        secondary_entity_type="deal",
        edge_predicate="deal_with",
        column_synonyms=_SALES_SYNONYMS,
        # A deals/pipeline CSV ships a stage + a deal value + a close date.
        # ("stage" alone is shared with HR; deal_value + close_date disambiguate.)
        signature_columns=("stage", "deal_value", "close_date"),
    ),
}


# Back-compat — older call sites use the AR-only flat dict. Kept as a view
# over the ar_collection profile so they don't break.
COLUMN_SYNONYMS = _AR_SYNONYMS


def detect_module(columns: list[str]) -> str | None:
    """Pick the best-fit module for an uploaded CSV by counting how many
    of each profile's `signature_columns` map cleanly via that profile's
    synonyms. Returns None when no profile catches >=2 signature columns
    -- caller falls back to manual selection / LLM-extract path.
    """
    scores: list[tuple[str, int]] = []
    normalized = [normalize_column_name(c) for c in columns]
    for module_id, profile in MODULE_PROFILES.items():
        hits = 0
        for sig in profile.signature_columns:
            for norm in normalized:
                canonical = profile.column_synonyms.get(norm)
                if canonical == sig:
                    hits += 1
                    break
        scores.append((module_id, hits))
    scores.sort(key=lambda x: x[1], reverse=True)
    best_id, best_score = scores[0]
    if best_score < 2:
        return None
    return best_id


# ─────────────────────────────────────────────────────────────────────────────
# Parsing + normalization
# ─────────────────────────────────────────────────────────────────────────────


def normalize_column_name(col: str) -> str:
    """Lowercase, strip, and snake_case a column name for synonym lookup."""
    s = col.strip().lower()
    s = re.sub(r"[\s\-/]+", "_", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def parse_csv_bytes(raw: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Parse CSV bytes → (header_columns, rows).

    Raises ValueError if the file isn't a parseable CSV with at least one
    data row.
    """
    text_body = raw.decode("utf-8-sig", errors="replace")  # strip BOM if present
    reader = csv.DictReader(io.StringIO(text_body))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")
    rows = [r for r in reader]
    if not rows:
        raise ValueError("CSV has a header but zero data rows")
    return list(reader.fieldnames), rows


def infer_column_mapping(
    columns: list[str], module_id: str | None = None
) -> tuple[dict[str, str], list[str]]:
    """Map CSV columns → canonical predicates via the module's synonym table.

    When `module_id` is None, the AR profile is used for back-compat with
    older call sites. New code passes the module_id (typically the result
    of `detect_module(columns)`).

    Returns (mapping, unmapped). `mapping` keys are the original column names;
    values are canonical predicates. `unmapped` lists columns that didn't
    match — surfaced back to the customer so they can rename.
    """
    profile = MODULE_PROFILES.get(module_id or "ar_collection") or MODULE_PROFILES["ar_collection"]
    synonyms = profile.column_synonyms
    mapping: dict[str, str] = {}
    unmapped: list[str] = []
    for col in columns:
        norm = normalize_column_name(col)
        canonical = synonyms.get(norm)
        if canonical:
            mapping[col] = canonical
        else:
            unmapped.append(col)
    return mapping, unmapped


# ─────────────────────────────────────────────────────────────────────────────
# Derived facts
# ─────────────────────────────────────────────────────────────────────────────


def _parse_date_loose(s: str) -> date | None:
    """Accept ISO (2026-06-12), slash (2026/06/12), or dd-mm-yyyy."""
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_int_loose(s: str) -> int | None:
    """Strip currency symbols + commas, parse int."""
    if s is None:
        return None
    cleaned = re.sub(r"[^\d.-]", "", str(s))
    if not cleaned or cleaned in ("-", "."):
        return None
    try:
        return int(float(cleaned))
    except (TypeError, ValueError):
        return None


def _parse_bool_loose(s: str) -> bool:
    return str(s).strip().lower() in ("true", "yes", "1", "vip", "y", "t")


@dataclass
class StructuredRow:
    """One CSV row after mapping + derivation. Pure data — no DB types."""

    invoice_id: str
    client_name: str
    client_email: str | None = None
    client_phone: str | None = None
    facts: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, str] = field(default_factory=dict)


def process_rows(
    rows: list[dict[str, str]],
    mapping: dict[str, str],
    *,
    today: date | None = None,
    module_id: str = "ar_collection",
) -> list[StructuredRow]:
    """Apply mapping + compute derived facts. Drops rows missing the basics.

    For the AR module, derived facts the rules require:
      - days_past_due           = today - due_date (in days)
      - last_reminder_age_days  = today - last_reminder_sent, -1 if blank
      - client_late_count_90d   = (computed cross-row below)

    For HR / CSM modules, the customer's CSV is expected to ship those
    integers directly (days_in_stage, days_to_renewal, etc.) — the
    date-derivation branches are no-ops for them.
    """
    if today is None:
        today = datetime.now(UTC).date()

    # First pass — extract per-row structured fields.
    structured: list[StructuredRow] = []
    for raw in rows:
        # Re-keyed by canonical name so downstream code doesn't care about
        # the original column ordering / casing.
        mapped: dict[str, str] = {}
        for src_col, canonical in mapping.items():
            val = (raw.get(src_col) or "").strip()
            if val == "":
                continue
            mapped[canonical] = val

        invoice_id = mapped.get("entity_id", "").strip()
        client_name = mapped.get("entity_name", "").strip()
        if not invoice_id or not client_name:
            # Row useless without these two — skip silently. Stats surface
            # how many got dropped so the customer can audit their CSV.
            continue

        facts: dict[str, Any] = {}
        # Direct passthroughs (string-valued). The profile-specific lists
        # carry whichever fields the module's rules expect from a CSV; the
        # union covers every field across modules so the mapper code itself
        # stays profile-blind.
        for k in (
            # AR-shape passthroughs
            "payment_status", "payment_terms", "project_name", "notes",
            # HR-shape passthroughs
            "stage", "role", "secondary_entity",
            # CSM-shape passthroughs
            "status",
        ):
            if mapped.get(k):
                facts[k] = mapped[k].lower() if k in ("payment_status", "status", "stage") else mapped[k]

        # ── AR-shape typed fields ────────────────────────────────────────
        if "amount_inr" in mapped:
            amt = _parse_int_loose(mapped["amount_inr"])
            if amt is not None:
                facts["amount_inr"] = amt

        due_d = _parse_date_loose(mapped.get("due_date", ""))
        if due_d is not None:
            facts["due_date"] = due_d.isoformat()
            facts["days_past_due"] = (today - due_d).days

        issue_d = _parse_date_loose(mapped.get("issue_date", ""))
        if issue_d is not None:
            facts["issue_date"] = issue_d.isoformat()

        last_d = _parse_date_loose(mapped.get("last_reminder_sent", ""))
        if last_d or "last_reminder_sent" in mapped:
            facts["last_reminder_age_days"] = (today - last_d).days if last_d else -1

        if mapped.get("is_vip_client"):
            facts["is_vip_client"] = _parse_bool_loose(mapped["is_vip_client"])

        # ── HR-shape typed fields ───────────────────────────────────────
        for k in (
            "days_in_stage", "total_pipeline_days", "offer_expiry_days",
            "interview_score", "days_since_last_contact",
        ):
            if k in mapped:
                v = _parse_int_loose(mapped[k])
                if v is not None:
                    facts[k] = v
        if "active" in mapped:
            facts["active"] = _parse_bool_loose(mapped["active"])
        elif module_id == "hr_pipeline":
            # The "active" boolean is essential for HR rules — default true
            # unless the CSV says otherwise.
            facts["active"] = True

        # ── CSM-shape typed fields ──────────────────────────────────────
        for k in (
            "mrr_usd", "days_to_renewal", "days_since_last_login",
            "nps_score", "open_tickets", "usage_drop_pct_30d",
        ):
            if k in mapped:
                v = _parse_int_loose(mapped[k])
                if v is not None:
                    facts[k] = v

        # ── Sales-shape typed fields ────────────────────────────────────
        if "deal_value" in mapped:
            v = _parse_int_loose(mapped["deal_value"])
            if v is not None:
                facts["deal_value"] = v
        for k in ("days_in_current_stage", "contacts_engaged",
                  "discount_pct", "gross_margin_pct"):
            if k in mapped:
                v = _parse_int_loose(mapped[k])
                if v is not None:
                    facts[k] = v
        for k in ("economic_buyer_engaged", "budget_confirmed",
                  "competitor_poc_active"):
            if k in mapped:
                facts[k] = _parse_bool_loose(mapped[k])
        if mapped.get("champion_status"):
            facts["champion_status"] = mapped["champion_status"].lower()
        # A non-empty "next step / next activity" cell ⇒ a next step IS
        # scheduled (the #1 anti-stall rule reads this); a sales CSV with no
        # such column ⇒ none scheduled.
        if "next_step" in mapped:
            facts["next_step_scheduled"] = bool(str(mapped["next_step"]).strip())
        elif module_id == "sales":
            facts["next_step_scheduled"] = False
        # days_since_last_contact: direct int handled in the HR loop above; if
        # only a last-activity DATE is present, derive the day count.
        if "days_since_last_contact" not in facts:
            la = _parse_date_loose(mapped.get("last_activity_date", ""))
            if la is not None:
                facts["days_since_last_contact"] = (today - la).days
        # close_date passthrough + days-to-close derivation.
        close_d = _parse_date_loose(mapped.get("close_date", ""))
        if close_d is not None:
            facts["close_date"] = close_d.isoformat()
            facts["days_to_close"] = (close_d - today).days

        structured.append(
            StructuredRow(
                invoice_id=invoice_id,
                client_name=client_name,
                client_email=mapped.get("client_email"),
                client_phone=mapped.get("client_phone"),
                facts=facts,
                raw=raw,
            )
        )

    # Second pass — compute client_late_count_90d across rows.
    # A "late payment" = paid row whose last_reminder_sent is AFTER due_date.
    # This needs the full set of rows for the same client, so it runs after
    # the per-row extraction above.
    ninety_ago = (today - _days_delta(90))
    late_per_client: dict[str, int] = defaultdict(int)
    for r in structured:
        if r.facts.get("payment_status") == "paid":
            due_d = _parse_date_loose(r.raw.get(_origin_col(mapping, "due_date"), ""))
            last_d = _parse_date_loose(r.raw.get(_origin_col(mapping, "last_reminder_sent"), ""))
            if due_d and last_d and last_d > due_d and last_d >= ninety_ago:
                late_per_client[r.client_name] += 1

    for r in structured:
        r.facts["client_late_count_90d"] = late_per_client.get(r.client_name, 0)

    return structured


def _origin_col(mapping: dict[str, str], canonical: str) -> str:
    """Reverse-lookup: which original CSV column maps to this canonical?"""
    for src, can in mapping.items():
        if can == canonical:
            return src
    return ""


def _days_delta(n: int):
    from datetime import timedelta
    return timedelta(days=n)


# ─────────────────────────────────────────────────────────────────────────────
# Emit through the memory bus (single ingestion pipeline per g-i-1)
# ─────────────────────────────────────────────────────────────────────────────


def emit_rows_to_bus(
    *,
    org_id: str,
    rows: list[StructuredRow],
    file_id: str,
    source_id: str,
    module_id: str = "ar_collection",
) -> dict[str, int]:
    """Emit one MemoryItem per CSV row, each carrying a `structured_facts`
    hint so the g-i-3 ingest subscriber persists deterministically (no LLM).

    Per-module entity shape comes from MODULE_PROFILES so AR rows produce
    Client+Invoice nodes, HR rows produce Candidate+Role nodes, CSM rows
    produce Account+Owner nodes — all through the same bus, all with the
    same subscriber, just with different hint shape.

    Preserves the g-i-1 invariant that *all* facts flow through
    `emit -> subscriber`.
    """
    from core.memory.emit import emit as emit_memory_item
    from core.memory.types import (
        MemoryItem,
        MemoryItemMetadata,
        StructuredFactsHint,
    )

    profile = MODULE_PROFILES.get(module_id) or MODULE_PROFILES["ar_collection"]
    emitted = 0
    uploaded_at = datetime.now(UTC)

    for r in rows:
        # Compose the human-readable content too — useful for the audit log
        # and for any downstream subscriber that wants to peek at the row
        # (search index, dashboard previews) without re-parsing facts.
        content = (
            f"{profile.secondary_entity_type.title()} {r.invoice_id} "
            f"{profile.edge_predicate} {r.client_name}. "
            + ", ".join(f"{k}={v}" for k, v in r.facts.items() if v is not None)
        )
        hint = StructuredFactsHint(
            entity_name=r.client_name,
            entity_type=profile.primary_entity_type,
            secondary_entity_id=r.invoice_id,
            secondary_entity_type=profile.secondary_entity_type,
            entity_attributes={
                k: v for k, v in (("email", r.client_email), ("phone", r.client_phone)) if v
            },
            facts=r.facts,
            edge_predicate=profile.edge_predicate,
        )
        # The g-i-3 subscriber prepends source_type to form the stored
        # `source_item_id` ("upload:{item_id}"). Keep item_id raw to avoid a
        # double-prefix like "upload:upload:..." downstream.
        item = MemoryItem(
            item_id=f"{file_id}:{r.invoice_id}",
            source_id=source_id,
            source_type="upload",
            content=content,
            metadata=MemoryItemMetadata(
                timestamp=uploaded_at,
                source_confidence=1.0,
                tags=["csv", "structured"],
                structured_facts=hint,
            ),
        )
        emit_memory_item(item, org_id=org_id)
        emitted += 1

    # Bus subscribers persist asynchronously inside their own DB sessions —
    # the count here is "rows emitted to the bus", not "rows persisted".
    # The caller pairs this with a post-flush SELECT to roll up real counts
    # for the resource_uploads row.
    return {"rows_emitted": emitted}
