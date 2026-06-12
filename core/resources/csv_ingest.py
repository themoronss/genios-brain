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
# Column-name synonym dictionary
# ─────────────────────────────────────────────────────────────────────────────
#
# Maps normalized (snake_case lowercase) CSV column names to the canonical
# predicates module rules look up. Add synonyms here as real customer CSVs
# surface variants — single source of truth so the LLM-fallback path doesn't
# need its own list.

# `entity_name` is special: that column's value becomes the Client entity's
# canonical_name. `entity_id` is the Invoice's stable ID. Everything else is
# emitted as a FactRow under the Invoice subject.
COLUMN_SYNONYMS: dict[str, str] = {
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


def infer_column_mapping(columns: list[str]) -> tuple[dict[str, str], list[str]]:
    """Map CSV columns → canonical predicates via the synonym table.

    Returns (mapping, unmapped). `mapping` keys are the original column names;
    values are canonical predicates (or one of the special "entity_id" /
    "entity_name" / "client_*" sentinels). `unmapped` lists columns that
    didn't match — surfaced back to the customer so they can rename.
    """
    mapping: dict[str, str] = {}
    unmapped: list[str] = []
    for col in columns:
        norm = normalize_column_name(col)
        canonical = COLUMN_SYNONYMS.get(norm)
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
) -> list[StructuredRow]:
    """Apply mapping + compute derived facts. Drops rows missing the basics.

    Derived facts the rules require:
      - days_past_due           = today - due_date (in days)
      - last_reminder_age_days  = today - last_reminder_sent, -1 if blank
      - client_late_count_90d   = (computed cross-row below)
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
        # Direct passthroughs (string-valued)
        for k in ("payment_status", "payment_terms", "project_name", "notes"):
            if mapped.get(k):
                facts[k] = mapped[k].lower() if k == "payment_status" else mapped[k]

        # Typed fields
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
        facts["last_reminder_age_days"] = (today - last_d).days if last_d else -1

        if mapped.get("is_vip_client"):
            facts["is_vip_client"] = _parse_bool_loose(mapped["is_vip_client"])

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
) -> dict[str, int]:
    """Emit one MemoryItem per CSV row, each carrying a `structured_facts`
    hint so the g-i-3 ingest subscriber persists deterministically (no LLM).

    This is the structured counterpart to the unstructured upload path —
    same bus, same subscriber, just a different metadata flag. Preserves
    the g-i-1 invariant that *all* facts flow through `emit -> subscriber`.

    Returns counts derived from emission outcome.
    """
    from core.memory.emit import emit as emit_memory_item
    from core.memory.types import (
        MemoryItem,
        MemoryItemMetadata,
        StructuredFactsHint,
    )

    emitted = 0
    uploaded_at = datetime.now(UTC)

    for r in rows:
        # Compose the human-readable content too — useful for the audit log
        # and for any downstream subscriber that wants to peek at the row
        # (search index, dashboard previews) without re-parsing facts.
        content = (
            f"Invoice {r.invoice_id} issued to {r.client_name}. "
            + ", ".join(f"{k}={v}" for k, v in r.facts.items() if v is not None)
        )
        hint = StructuredFactsHint(
            entity_name=r.client_name,
            entity_type="client",
            secondary_entity_id=r.invoice_id,
            secondary_entity_type="invoice",
            entity_attributes={
                k: v for k, v in (("email", r.client_email), ("phone", r.client_phone)) if v
            },
            facts=r.facts,
            edge_predicate="issued_to",
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
