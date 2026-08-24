# Penetration test — scope of work

Hand this document to the vendor (HackerOne Professional / Cure53 / local).

## 1. System under test

**GeniOS** — multi-tenant SaaS that ingests Google Workspace / Slack /
Jira / Notion / HubSpot activity for each tenant's organization, builds
a knowledge graph, and exposes it via API + SDK to operator-side agents.

Production URL: `https://api.genios.ai`
Test URL: `https://api.staging.genios.ai` (credentials provided separately)

Stack:
- Python 3.12 / FastAPI (genios-brain)
- Postgres 15 on Supabase (multi-tenant with Row-Level Security)
- Redis (Upstash) — caching, event bus, Celery broker
- Celery — scheduled tasks + event router
- LLM providers: Groq (primary), Gemini (embeddings + fallback)
- Deployed on DigitalOcean App Platform

## 2. In-scope surfaces

### API endpoints
- `POST /v1/context` (Pull API)
- `POST /v1/feedback` + `POST /v1/outcome` (deprecated alias)
- `GET  /v1/stream/recommendations` (SSE)
- `POST /v1/agent` (agent registration)
- `POST /v1/admin/delete` (GDPR cascade)
- `GET  /v1/admin/aar*` (beta metrics)
- `POST /v1/webhooks/*` (inbound Gmail / Calendar receivers)
- OAuth callbacks: `/auth/{gmail,calendar,drive,slack,jira,notion,hubspot}/callback`
- `POST /v1/billing/webhook` (Razorpay webhook — if enabled during test)

### Data plane
- Postgres RLS policies — verify cross-tenant isolation on every table
  holding tenant data (contacts, interactions, contact_facts, insights,
  recommendations, delivery_attempts, llm_usage, calibration_models, etc.)
- Redis keys — tenant scoping in key prefixes
- Outbound webhook delivery — HMAC-SHA256 signature

### SDK
- Python: `genios>=1.0.0rc1` (pip)
- TypeScript: `@genios/sdk>=1.0.0-rc.1` (npm)

## 3. Out of scope

- Supabase (infrastructure provider — they have their own audits)
- Upstash Redis (same)
- DigitalOcean App Platform
- Groq / Gemini / Anthropic LLM providers
- Customer-side integrations (customers' own Gmail / Slack / etc.)

## 4. Priority threat classes (highest-first)

1. **Cross-tenant data leak via RLS bypass**
   The most damaging failure mode. Try to:
   - Forge `app.tenant_id` session var
   - Hit endpoints that query without proper auth
   - Exploit SQL-injection to read across `org_id`
   - Find tables without RLS enabled

2. **OAuth flow attacks**
   - Token theft via CSRF on callback
   - Replay of authorization codes
   - Scope escalation
   - Our OAuth app's refresh token disclosure

3. **Webhook replay / forgery**
   - Replay of signed webhooks (no timestamp check currently — flag as finding)
   - HMAC timing-attack windows
   - Inbound webhook receivers (Gmail Pub/Sub) accepting spoofed notifications

4. **API key attacks**
   - Key forgery (prefix guessing)
   - Missing rate limiting per key
   - Key scope leakage

5. **Prompt injection against LLM extractors**
   - Craft email body that hijacks `extract_email_intelligence`
   - Attempt to make it emit different tenant's data
   - Cost amplification (burn LLM budget)

6. **Admin endpoint abuse**
   - `POST /v1/admin/delete` cross-tenant attempt
   - AAR CSV extraction of another tenant

7. **Standard web app vulns** (OWASP Top 10)
   - XSS on dashboard (delegate to genios-dashboard if in scope)
   - CSRF on state-changing endpoints
   - SSRF via webhook URL validation
   - IDOR on any resource-id-bearing endpoint

## 5. Methodology

- Authenticated pen test — we'll provide 2 tenants' API keys for cross-tenant testing
- Grey-box access — vendor sees code and schema on request (signed NDA)
- Production-equivalent staging — no prod testing without prior written go-ahead

## 6. Deliverables expected

- Executive summary (≤ 2 pages)
- Findings report with severity (CVSS v3.1), reproduction steps, remediation guidance
- Retest of remediations after 30 days

## 7. Timeline

- Kick-off: week 0
- Testing window: 2 weeks
- Report delivery: 1 week after testing ends
- Retest: 4 weeks after our remediation PRs merge

## 8. Contact

- Technical: [eng-lead]
- Security incident during testing: [email + PGP]
- Contracts / NDA: [legal / founder]

## 9. Non-destructive clause

No DoS, no mass data exfiltration, no customer-visible disruption. Findings
that require destructive proof must be demonstrated in a throw-away tenant
we'll spin up for the engagement.
