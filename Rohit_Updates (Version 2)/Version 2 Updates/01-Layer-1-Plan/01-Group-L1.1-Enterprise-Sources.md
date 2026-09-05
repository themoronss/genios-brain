# L1.1 — Enterprise Sources

**Group responsibility:** the company's existing surfaces. GeniOS never replaces these;
it reads them.

**Group law:** *A source that cannot be read is a stated boundary, never a silent gap.*
An unconnectable source must produce a coverage flag, not an absence that looks like a
negative fact.

---

## Current state vs the 16 spec'd categories

| # | Category | Status | Notes |
|---|---|---|---|
| 1 | Gmail / Outlook | ⚠️ partial | Gmail built; **Outlook missing** |
| 2 | Calendar | ✅ built | Google Calendar |
| 3 | Slack / Teams | ❌ missing | registry descriptor, `buildable=False` |
| 4 | Notion / Docs | ✅ built | |
| 5 | Google Drive | ✅ built | |
| 6 | CRM / ERP | ⚠️ partial | **HubSpot deals only, 4 properties** |
| 7 | GitHub / Jira | ❌ missing | |
| 8 | Finance / QuickBooks | ❌ missing | |
| 9 | HRIS | ❌ missing | |
| 10 | Contracts | ⚠️ partial | via mail attachments only |
| 11 | Expense reports | ❌ missing | |
| 12 | Uploads | ✅ built | |
| 13 | Voice / transcripts | ❌ missing | no audio path at all |
| 14 | Browser extension | ❌ missing | |
| 15 | Databases | ✅ built | one table per connection |
| 16 | Webhooks / APIs | ✅ built | |

**6 built · 3 partial · 7 missing.**

Note: the code is **ahead** of the Globe V1 scope here, which specified Gmail + Calendar
only. This group is not the weakest part of Layer 1 — L1.6 is.

---

## Connector priority — ordered by what intelligence each unlocks

Do not order this backlog by integration difficulty. Order it by which customer
behaviour becomes possible.

| Priority | Connector | Unlocks | Blocked behaviour today |
|---|---|---|---|
| **P0** | **HubSpot expansion** (contacts, companies, owners, pipeline history, notes) | account context, owner resolution, stage history | the account is already connected — the connector simply never asks for these objects. **Cheapest unlock on the list.** |
| **P1** | **Billing** (Stripe) | subscription state, MRR, renewal, payment failure, dunning | churn detection, revenue attribution, LTV. A `stripe.subscription.v1` structured mapping is **already registered** for a source that cannot be built |
| **P2** | **Product usage** (Mixpanel / PostHog / generic event webhook) | usage decline, feature adoption, activation | every "cohort shows early churn signals + usage pattern" claim |
| **P3** | **Support desk** (Zendesk / Intercom) | ticket volume, sentiment, escalation, SLA | 30-day-early at-risk flags |
| **P4** | **Slack** | decision debt, coordination, vendor strategy chatter | most decisions are discussed in Slack, not email |
| **P5** | Voice / transcripts | meeting commitments that never touch email | L1.3.4-U3 depends on this |
| **P6** | Outlook | parity for non-Google tenants | whole market segment |
| **P7** | GitHub / Jira | ownership, cycle time, process | |

### The P0 case, precisely

`capture/connectors/hubspot.py:39` fetches deals with exactly four properties:
`dealname`, `dealstage`, `amount`, `closedate`. Contacts are read only opportunistically
when already present on the deal. Companies, owners, pipeline history and notes are
never requested.

The OAuth grant, the connector class, the sync loop and the cursor store **all already
exist and work**. This is an API-surface expansion, not an integration project. It is
the highest ratio of unlocked intelligence to engineering hours available anywhere in
Layer 1.

---

## L1.1-U1 · Coverage declaration — the group law, implemented

**WHAT** — Every org has a machine-readable statement of what GeniOS can and cannot see.

**WHY** — This is the difference between *"this customer has no support tickets"* and
*"we have no source that could carry a support ticket."* Without it every absence-based
inference is either unsafe or permanently hedged.

Today `capture/coverage/model.py` computes the real answer and **throws it away**:
`coverage_fn` is passed by no production caller, so `coverage_ready` is `None` on every
event, and the `source_coverage` table created in migration `0002` is referenced only by
the account-deletion cascade. Nothing writes it; nothing reads it.

**HOW**
1. Compute per-org capability coverage on every sweep from the set of active connections.
2. Write `source_coverage`.
3. Pass `coverage_fn` from `sync_runner` so every event carries `coverage_ready`.
4. Surface the coverage map to L2 so a situation can carry **"unknowable from connected
   sources"** as a state distinct from **"absent"**.

**ACCEPTANCE**
```
pytest tests/capture/coverage/test_coverage_wiring.py -q
# every event emitted by a sweep has coverage_ready set (True or False, never None)
# source_coverage has rows for the pilot org
# an org with no support connector reports coverage_ready=False for support capabilities
```

**REVERSE PROMPT**
```
TASK: Wire the coverage model that already exists but is never called.

THE BUG: capture/pipeline.py accepts a coverage_fn parameter. Grep shows it is passed by
NO production caller — only referenced inside pipeline.py itself. So GatedEvent.coverage_ready
is None on every event ever produced, while capture/coverage/model.py computes the real
answer and discards it. Separately, the source_coverage table from migration 0002 is
written by nothing and read only by the account-deletion cascade.

The contract's own docstring says it best: "A dead field on a contract is worse than a
missing one: it invites a consumer to trust a seam that carries nothing, and None reads
as 'unknown' exactly where a caller most wants a yes."

CHANGES:
1. sync_runner: compute the org's coverage map once per sweep from active connections.
2. Persist it to source_coverage (org_id, capability, covered, computed_at).
3. Pass coverage_fn into capture_event from every production call site — the sweep AND
   the webhook path AND the upload path AND the internal-knowledge path.
4. Assert in the publication validator (L1.6.10) that coverage_ready is not None.

This is a WIRING task. Do not rewrite coverage/model.py — it is correct. Find its
callers and connect them.

TEST tests/capture/coverage/test_coverage_wiring.py — the three assertions in doc 01
L1.1-U1 ACCEPTANCE, plus: an event from the webhook path also carries coverage_ready.
```

---

## L1.1-U2 · Registry honesty

**GAP** — the dashboard slug maps in `api/routes.py:850-856` and `:921-923` list Slack,
Jira, Sheets and Docs, but both connect endpoints hard-refuse any source outside
`IMPLEMENTED_SOURCE_TYPES`. A founder can see a tile they cannot click.

**FIX** — the UI reads `BUILDABLE_SOURCES` directly. Unbuildable sources render as
"coming soon" with a waitlist action, never as an available tile that errors.

**ACCEPTANCE** — no source appears as connectable that the connect endpoint would refuse.
