"""The ten source families of Layer 1 — taxonomy as DATA, one place.

Every SourceEvent carries a family so downstream layers can reason about the KIND of
reality an event came from without matching on source names. Adding a source = one
line here; the pipeline never branches on family (capture stays reasoning-free).

Families (the vision's Layer-1 top level):
  internal          company's own records (wiki, SOPs, KPIs) — not yet wired
  external          public world (websites, news, filings)   — not yet wired
  human_input       a person typed/uploaded/decided it
  ai_generated      an AI agent produced it
  enterprise_system CRM / ERP / client databases (structured systems of record)
  communication     mail, chat, meetings, calendar
  knowledge         docs, pages, files
  operational       GitHub/Jira/CI — not yet wired
  live_event        webhook-pushed happenings — not yet wired
  intelligence      GeniOS's own prior decisions/feedback fed back as source
"""
from __future__ import annotations

FAMILIES: frozenset[str] = frozenset({
    "internal", "external", "human_input", "ai_generated", "enterprise_system",
    "communication", "knowledge", "operational", "live_event", "intelligence",
    "unclassified",
})

SOURCE_FAMILY: dict[str, str] = {
    # communication — mail + calendar/meetings
    "gmail": "communication", "outlook": "communication", "imap": "communication",
    "inkbox": "communication", "slack": "communication", "teams": "communication",
    "whatsapp": "communication", "sms": "communication",
    "gcal": "communication", "calendar": "communication",
    "google_calendar": "communication",
    # knowledge — docs/pages/files
    "notion": "knowledge", "gdrive": "knowledge", "drive": "knowledge",
    "google_drive": "knowledge", "confluence": "knowledge", "upload": "knowledge",
    # enterprise systems — CRM/DB systems of record
    "hubspot": "enterprise_system", "salesforce": "enterprise_system",
    "pipedrive": "enterprise_system", "database": "enterprise_system",
    "postgres": "enterprise_system", "mysql": "enterprise_system",
    # human + AI intake
    "human": "human_input",
    "agent": "ai_generated",
    # operational
    "github": "operational", "gitlab": "operational", "jira": "operational",
    "linear": "operational",
    # GeniOS's own outputs re-entering as evidence
    "genios": "intelligence",
}

# Families whose events a HUMAN or an AGENT deliberately handed us. The noise gate's
# N-codes exist for inbox firehoses — deliberately-provided material bypasses them
# (it still lands, is traced, and is deduped like everything else).
DELIBERATE_FAMILIES: frozenset[str] = frozenset({"human_input", "ai_generated"})
DELIBERATE_SOURCES: frozenset[str] = frozenset({"human", "agent", "upload"})


def family_of(source: str) -> str:
    return SOURCE_FAMILY.get((source or "").lower(), "unclassified")
