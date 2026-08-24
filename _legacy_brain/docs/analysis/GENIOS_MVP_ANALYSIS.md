# Genios MVP — Expectation vs Reality

> Living document. Sections marked `<!-- auto -->` are refreshed by
> `scripts/audit.py`. Everything else is hand-curated — update it as your
> strategy evolves, not as code changes.

<!-- auto:last_updated_start -->
**Last auto-refresh:** 2026-04-15T05:49:40+00:00
**Brain tested:** `http://localhost:8000`
**Reality signals captured:** 10
<!-- auto:last_updated_end -->

---

## 1. The Promise — what Genios claims to deliver

> *"A personal memory layer for AI agents — the context you have about
> every relationship, ready for any LLM to use, without retraining."*

The agent-facing contract (`/v1/context`) promises:

- **Relationship truth** — stage, sentiment trend, last interaction, history
- **Behavioral memory** — what works for this person, what to avoid, style
- **Commitments** — what you or they owe each other
- **Topics** — what they actually care about
- **Scoring** — confidence, freshness, coverage — so the agent knows when to
  trust the bundle
- **Situation awareness** — auto-classifies the situation (deal_stuck,
  discovery, follow_up, etc.) and surfaces targeted signals

**Core value claim:** drafts, replies, and decisions grounded in real memory
— no reintroducing, no forgotten commitments, no tone mismatches — from any
MCP-speaking LLM client (Claude Desktop, Claude Code, Cursor, custom agents).

---

## 2. The Reality — live snapshot

<!-- auto:reality_start -->
- **Brain:** `http://localhost:8000`
- **Probes run:** 10
- **Met:** 0 · **Missed:** 0 · **Buggy:** 0 · **Unknown:** 10
- **Overall health:** 0% (0/10 capabilities met)
- **Average probe latency:** 1 ms
<!-- auto:reality_end -->

---

## 3. Expectation vs Reality Matrix

Hand-curated list of buyer expectations. Status column auto-refreshes.

<!-- auto:matrix_start -->
| # | Capability | Expected | Status | Notes |
|---|---|---|---|---|
| 1 | /v1/context returns a usable bundle for a known contact | HTTP 200 with entity + context_for_agent | ? | request failed: HTTPConnectionPool(host='localhost', port=8000): Max retries exc |
| 2 | Situation auto-classified from free text | situation_type set to a non-null string | ? | request failed: HTTPConnectionPool(host='localhost', port=8000): Max retries exc |
| 3 | Contact search / autocomplete | endpoint exists, returns list | ? | request failed: HTTPConnectionPool(host='localhost', port=8000): Max retries exc |
| 4 | `communication_style` populated when style data exists | non-empty string when what_works is populated (or honest null) | ? | request failed: HTTPConnectionPool(host='localhost', port=8000): Max retries exc |
| 5 | `what_works` / `what_to_avoid` populated | at least one populated | ? | request failed: HTTPConnectionPool(host='localhost', port=8000): Max retries exc |
| 6 | No duplicate commitments | each commitment text unique | ? | request failed: HTTPConnectionPool(host='localhost', port=8000): Max retries exc |
| 7 | Topics extracted from meetings | topics_of_interest non-empty for contact with meetings | ? | request failed: HTTPConnectionPool(host='localhost', port=8000): Max retries exc |
| 8 | `agent_behavior` and `action_recommendation` agree | block/proceed signals don't contradict | ? | request failed: HTTPConnectionPool(host='localhost', port=8000): Max retries exc |
| 9 | Promo/no-reply senders filtered from graph | marked as broadcast OR not returned as WARM | ? | request failed: HTTPConnectionPool(host='localhost', port=8000): Max retries exc |
| 10 | Latency acceptable for interactive use | < 2000 ms on a fresh build | ? | request failed: HTTPConnectionPool(host='localhost', port=8000): Max retries exc |
<!-- auto:matrix_end -->

Status legend: ✅ met · ⚠️ partial · ❌ missing · 🐛 buggy · ? unknown

---

## 4. Findings — bugs + gaps with fix/defer recommendation

Each finding has four parts so a reader can decide without re-running anything:

- **Expectation** — what should happen
- **Reality** — what actually happens (evidence)
- **Impact** — why it matters for a buyer
- **Recommendation** — fix now / fix later / defer / won't-fix, with reasoning

---

### F1 · Contradictory agent signal on low-confidence contacts — **FIXED 2026-04-14**

- **Expectation:** one unambiguous instruction to the agent — proceed or block.
- **Reality (before fix):** `/v1/context` returned `agent_behavior: "block"`
  **and** `action_recommendation: "proceed"` simultaneously on contacts with
  `confidence < 0.1` (observed on `atin@example.com`, `pro14888@adobe.com`).
- **Impact:** LLMs would pick the permissive signal by default (they
  optimize for helpfulness). Outbound to a flagged-as-block contact
  would go through → potential embarrassment in a real buyer demo.
- **Fix applied:** `bundle_builder.py:927` — after both functions run, if
  `agent_behavior == "block"` the `action_recommendation` is coerced to
  `"block"` as well. `escalate_to_human`/`needs_confirmation` downgrade
  `proceed` → `warn`. Single coherent contract. Re-audit to confirm.

### F2 · `communication_style` reports "Unknown" even when style data exists — **FIXED 2026-04-14**

- **Expectation:** string like `"concise, formal, metric-driven"` or
  `"casual with emojis"`.
- **Reality:** `"Unknown"` across 100% of probed contacts, even when
  `what_works` and `what_to_avoid` are populated (observed on
  `tripathihk2014@gmail.com`).
- **Impact:** LLMs see "Unknown" → default to generic polite tone → core
  personalization promise fails. This is *exactly* what differentiates
  Genios from vanilla Gemini/Claude.
- **Recommendation:** **Fix now (P1, ~10 min).** Derive `communication_style`
  from `what_works` when populated. If neither field has data, omit both
  rather than returning a misleading "Unknown".

### F3 · Duplicate commitments — **FIXED 2026-04-15**

- **Expectation:** one commitment row per distinct obligation.
- **Reality:** Harsh Tripathi has `"send raw Q3 retention cohort data"`
  twice, created 6 seconds apart. `open_commitments: 2` inflated.
- **Impact:** LLM mentions the same ask twice in drafts. Cosmetic but
  screams "buggy" in a buyer demo. Also breaks trust in the commitment
  count metric.
- **Recommendation:** **Fix later (P2, 30-60 min).** Add dedupe in the
  commitment extractor: normalize text (lowercase + stripped) and drop
  dupes within a 1-hour window. Low risk, medium impact.

### F4 · Topics empty for meeting-heavy contacts — **FIXED 2026-04-15**

- **Expectation:** meeting titles and descriptions feed the topic extractor.
- **Reality:** `pro14888@adobe.com` has a meeting
  `"Adobe Interview- Harsh Tripathi"` → `topics_of_interest: []`.
  `atin@example.com` has a `"Q1 roadmap and hiring plans"` meeting →
  `topics_of_interest: []`.
- **Impact:** Agents lose the richest signal. "Roadmap", "hiring",
  "interview process" — all invisible. Drafts stay generic.
- **Recommendation:** **Fix later (P2, ~1-2 hours).** Extend the topic
  extractor to include calendar event titles + descriptions. Medium
  effort, high impact on eval scores.

### F5 · Bulk / promotional senders classified as real contacts — **PARTIAL FIX 2026-04-15**

Added `is_broadcast` computed field on every context bundle, and
`exclude_broadcast=true` default on `/v1/contacts`. Full ingestion-level
fix (never storing them in the first place) still pending — but for agent
consumers this is already solved.

---

### F5 (original) · Bulk / promotional senders classified as real contacts

- **Expectation:** `information@hdfcbank.net`, `noreply@*`, marketing
  senders filtered from the contact graph OR tagged `is_broadcast`.
- **Reality:** HDFC Bank (marketing broadcasts) stored as `WARM` contact
  with `context_score: 0.60`. 4 inbound one-way messages, 0 replies,
  `is_bidirectional: false` — signal exists, classifier not using it.
- **Impact:** Pollutes every "who should I re-engage" query. Risk of
  drafting replies to no-reply addresses. Bad UX in dashboard too.
- **Recommendation:** **Fix later (P2, ~2-3 hours).** Simple first pass:
  filter email patterns (`noreply`, `no-reply`, `information@`, `promo@`,
  `mailer@`, subdomain `marketing.*`, etc.) AND require
  `is_bidirectional: true` OR `interaction_count > 2` before promoting
  to the graph. Ingestion-level change, affects all connectors.

### F8 · "Agent loop detection" blocked normal agent use — **FIXED 2026-04-15**

- **Expectation:** an agent (Claude, GPT, Cursor) can call `/v1/context` 5-10
  times in quick succession while reasoning — e.g. "summarize my 5 hottest
  leads" triggers 5 lookups.
- **Reality (before fix):** `llm_guard.py` hard-capped at **3 context calls
  per agent per 60 seconds** under the label `AGENT_LOOP_DETECTED`,
  regardless of whether the calls were for the same entity or different
  ones. Every audit run was getting 429 after 3-5 unique contacts.
- **Impact (before fix):** A buyer wiring Genios into Claude Desktop
  would hit this within their first multi-contact prompt.
- **Fix applied:** rewrote `check_agent_loop` in
  [llm_guard.py](genios-brain/app/llm_guard.py) to key on **entity** — a
  true loop is the same agent asking for the same person repeatedly.
  Different entities fan out freely. Cap raised to 8 per-entity per 60s
  and made configurable via `GENIOS_ENTITY_REPEAT_CAP` env. Error renamed
  to `ENTITY_REPEAT_LIMIT` with a useful message.

### F9 · Rate limit burden pushed onto client (audit tooling had to de-dupe)

- **Expectation:** clients can call the API naively; server handles pacing.
- **Reality:** to make the audit script reliable, I had to add per-contact
  response caching so 10 probes produce only 5 network calls. Any
  real-world client doing analytics on multiple contacts must do the
  same — undocumented burden.
- **Impact:** Every client implementer writes the same caching wrapper.
  Error-prone. Increases integration friction.
- **Recommendation:** **Defer.** Fixing F8 largely removes the need. If
  F8 is fixed generously, F9 resolves itself.

### F6 · Cold-build latency ~4.5s per `/v1/context` call

- **Expectation:** < 2s for interactive agent use.
- **Reality:** `latency_ms: 4300–4900` consistently across 4 probes on
  localhost with warm DB. Cache hits are fast; first builds are slow.
- **Impact:** In an agent loop (Claude calls the tool mid-reasoning), 5s
  is perceptible lag. At scale, connection pool pressure goes up.
- **Recommendation:** **Profile first, then fix (P3, TBD).** Add timing
  spans in `build_context_bundle` to find the 4s spender. Likely
  candidates: LLM-backed enrichment, `company_contacts` N+1 query,
  or precedent search re-running on every call. Don't optimize blind.

---

## 5. What already works well — do not regress

- **Entity resolution** — 6-tier pipeline (exact email → fuzzy company) is
  robust. Hit rate: 100% on probed contacts with exact email.
- **Situation classification** — `_classify_situation` correctly detected
  `follow_up` from "follow up on our recent chat" and "follow up after the
  Adobe interview". Free-text → typed signal works.
- **Open commitment tracking** — Harsh's retention data ask was captured
  from conversation text, surfaced with owner + status + created_at.
- **Coverage score** — 0.86 for data-rich Harsh, 0.43 for sparse Atin.
  Honest signal, maps to intuition.
- **Scoring stack** — 5-score system (freshness, confidence, consistency,
  signal, authority) is a proper differentiator — few memory layers expose
  this much metadata.
- **MCP integration** — Claude Code loaded the server on first try. Tool
  descriptions fired auto-invocations correctly once bugs were out.

---

## 6. Strategic gaps — capabilities a buyer would expect

Not bugs — missing endpoints/features. Ranked by demo impact.

### G1 · Contact search endpoint (`GET /v1/contacts?q=...`) — **SHIPPED 2026-04-15**

Right now Claude has to *guess* emails. Membase and competitors let the LLM
search by partial input ("Ashish at HDFC"). Without this, every prompt has
to include the exact email — huge UX penalty.

**Shipped:** `GET /v1/contacts` now supports `?q=`, `?stage=`,
`?needs_attention=true`, `?limit=`. Ranking: exact email > exact name >
fuzzy match > recent interaction. Exposed as MCP tool
`genios_search_contacts` in [genios-mcp/server.py](genios-mcp/server.py).
Claude will auto-call this before context lookups whenever the user says
"Alice at Acme" or "Ashish from HDFC" instead of a full email.

### G2 · "Who should I follow up with?" query — **SHIPPED 2026-04-15**

`GET /v1/contacts` now supports `needs_attention`, `recent_days`,
`silent_days`, `overdue`, `exclude_broadcast`. Exposed via
`genios_search_contacts` MCP tool. Claude can answer:
- "Who needs attention?" → `needs_attention=true`
- "Who have I been ignoring for 2 weeks?" → `silent_days=14`
- "What's overdue this week?" → `overdue=true`
- "Active contacts this month?" → `recent_days=30`

### G3 · Temporal queries

"Contacts I haven't replied to in 2 weeks", "overdue commitments this month".
Exists partially inside `overdue_commitments` count, but not queryable
from an agent.

**Effort:** medium. Useful for enterprise.

### G4 · Cross-entity summaries

"Summarize everything about Acme Corp across all contacts there".
`company_contacts` exists inside a bundle but there's no
`/v1/company/{name}` endpoint.

**Effort:** small if building on existing pieces. Medium demo value.

### G5 · Write-back / capture API

"Claude drafted a reply — log this as an outbound interaction." Currently
Genios is read-only to agents. Agents can't *update* memory.

**Effort:** medium. Critical once agents are in production use.

---

## 7. Priority stack — ranked recommendation

| # | Item | Type | Effort | Impact | Decision |
|---|---|---|---|---|---|
| ✓ | F1 — collapse `agent_behavior`/`action_recommendation` | Bug | 15m | High | **DONE 2026-04-14** |
| ✓ | F2 — populate `communication_style` from what_works | Bug | 10m | High | **DONE 2026-04-14** |
| ✓ | F3 — commitment dedupe | Bug | 30m | Medium | **DONE 2026-04-15** |
| ✓ | F4 — topics from meetings | Bug | 1-2h | High (eval) | **DONE 2026-04-15** |
| ✓ | F5 (light) — `is_broadcast` + query-level filter | Bug | 30m | Medium | **DONE 2026-04-15** |
| ✓ | F8 — "agent loop" cap blocks multi-contact use | Bug | 30m | Critical | **DONE 2026-04-15** |
| ✓ | G1 — contact search endpoint + MCP tool | Gap | 2h | High (UX) | **DONE 2026-04-15** |
| ✓ | G2 — "who needs attention" + temporal filters | Gap | 1h | Highest (demo) | **DONE 2026-04-15** |
| 1 | F5 (full) — broadcast filter at ingestion | Bug | 2-3h | Medium (cleanliness) | **Fix next sprint** |
| 2 | F6 — latency profile + fix | Perf | TBD | Medium (scale) | **Profile first** |
| 3 | G3, G4, G5 | Gap | various | Medium | **Roadmap** |

## How to re-run the reality check

```bash
cd ~/Desktop/genios
python3 scripts/audit.py
```

The script will:
1. Call each probe against your running brain (localhost:8000)
2. Update section 2 with a live snapshot
3. Update section 3 matrix with current status per capability
4. Preserve hand-curated sections (1, 4, 5, 6, 7) untouched
5. Append any new drift findings to a diff log: `scripts/audit_history.jsonl`
