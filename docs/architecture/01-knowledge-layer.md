> **Created:** 2026-08-07 · **Status:** Reference — frozen target vision
> **Source:** `GeniOS Theory II.pdf` — "Layer 1: Knowledge Layer"

# Layer 1 — Knowledge Layer

**One responsibility:** read enterprise reality and normalize it. **Zero reasoning.
Zero business logic.** Only reading and normalization.

**Current code:** `genios_engine/capture/` — connectors, acquire, connections,
coverage, documents, events_store, gate, intake, internal_knowledge, landing,
parked, payload_store, preprocess, source_families, source_registry, structured,
trace_store, triage.

## Purpose

"Reality enters GeniOS." Layer 1 collects raw enterprise signals from every source
and turns unstructured input into normalized, structured **events** — nothing more.
It does not decide, score, prioritize, or interpret.

## Scope — Raw Enterprise Signals only

The author explicitly narrows Layer 1 to raw signals and moves everything derived up:

- **Systems · People · Documents · Communications · Events · External World.**

> **Memory is NOT a source.** Memory is a *derived artifact* — it is produced from
> many sources by the Context Engine and therefore belongs to **Layer 2**, not here.

## Enterprise sources (the full catalogue the layer must be able to read)

1. **Internal Sources** — company memory, employee profiles, org structure, policies,
   SOPs, internal wiki, product info, pricing, company goals, KPIs, projects, tasks, assets.
2. **External Sources** — company/customer websites, LinkedIn, X, news, market
   research, competitor data, industry reports, public docs, SEC filings, gov data, APIs.
3. **Human Inputs** — text, voice, images, videos, files, notes, manual updates,
   feedback, approvals, decisions, commands.
4. **AI-Generated Sources** — AI notes/summaries/reports/suggestions/plans/emails/
   drafts/analysis/decisions.
5. **Enterprise Systems** — CRM (HubSpot/Salesforce/Pipedrive), ERP, HRMS, ATS,
   Finance, Payroll, Ticketing, PM, BI tools, custom systems.
6. **Communication** — Gmail, Outlook, Slack, Teams, WhatsApp, Telegram, Discord,
   meetings, calendar, call recordings, SMS.
7. **Knowledge** — Notion, Google Docs, Confluence, PDFs, Word, Excel, PPT, Figma,
   GitHub wiki, internal documentation.
8. **Operational** — GitHub, GitLab, Jira, Linear, Asana, ClickUp, Trello, CI/CD,
   deployments, logs, monitoring.
9. **Live Event Sources** — new email, calendar update, CRM update, new meeting, new
   lead, new customer, closed deal, ticket raised, PR created, deployment, invoice, payment.
10. **Intelligence Sources** — historical decisions, previous recommendations, human
    feedback, agent feedback, success/failure history, learned preferences/behaviors,
    adaptive patterns, executive decisions. *(These are inputs to learning, produced elsewhere.)*

## Everything becomes an Enterprise Event

Each source item is normalized into a single **Enterprise Signal / Event** shape (a
Slack message, an email, a calendar invite, a CRM update all become one event type).
This is what Layer 2 consumes.

## LLM usage in Layer 1

**Allowed, but only for unstructured → structured conversion:** entity extraction,
normalization, relationship extraction, chunking, embeddings, OCR, speech-to-text.
Everything that can be deterministic, is deterministic.

## Deployment / runtime characteristics

- Independent microservice.
- **Heavy work happens at ingestion**, not at request time. Never parse the entire
  company on every request.
- Async; feeds the event pipeline that drives Loop 1 (Enterprise Understanding).

## Frozen decisions

- Layer 1 is read + normalize only — **no reasoning, no business logic ever.**
- Memory belongs to Layer 2, not here.
- The output contract is the normalized Enterprise Event / Signal consumed by Context.
