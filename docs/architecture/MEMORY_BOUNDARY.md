# GeniOS Memory Boundary — architecture contract

> **Status:** Active contract · **Source:** Rohit_Updates/new-updates/Update 2 · **Owner:** engine
> This is the explicit architecture contract Update 2 §18 asks for: GeniOS stores *bounded* context,
> it is **not** the memory layer. Each rule below maps to where it already lives in the code, or is
> flagged as a gap.

## 1. The boundary (frozen)

> Source tools and dedicated memory systems own **durable source history and general recall**.
> GeniOS owns the **minimum evidence-linked context and decision state** needed to understand the
> current situation, decide safely, explain the decision, deliver it once, and measure the outcome.

- Memory answers *what happened / what can be recalled*.
- The GeniOS **Context Graph** answers *what is currently true, related, relevant, evidenced*.
- GeniOS **intelligence** answers *what should happen next, why, under which conditions, with what authority*.

Goal is **not** "remember everything" — it is **"know enough, prove enough, retain enough to decide correctly."**
Storage is a capability; "memory layer" is a responsibility. Having a database does not make GeniOS the memory layer.

## 2. Storage admission test (apply before persisting any new data class)

Persist only if the data is necessary to do at least one of: (1) resolve an entity/relationship;
(2) establish the current situation; (3) prove a load-bearing claim; (4) apply expertise/policy/reasoning;
(5) explain/replay a decision; (6) prevent duplicate/conflicting delivery; (7) verify completion / measure outcome;
(8) satisfy an explicit audit/security/legal obligation. Even then: **minimum representation, narrowest
visibility, shortest sufficient retention.**

## 3. What GeniOS stores — and where it already lives

| Class | Requirement (Update 2) | In code today |
|---|---|---|
| Connector/sync state | cursors, source IDs, hashes, last-sync, scope, tombstones, idempotency | `capture/connectors/*` (watermark/cursor), `capture/payload_store.py`, event dedup key |
| Resolved identity | canonical id, type, provider ids, verified names/domains, **resolution_status** (verified/probable/address_only/conflicted), per-claim confidence, merge/split history | `graph_nodes` (canonical_key, node_type, display_name, identity_strength); **gap:** explicit resolution_status enum surfaced to cards |
| Typed current facts | subject, path, value, source ref, evidence span, method/version, observed/synced time, valid_from/to, confidence, authority, **state** (current/stale/superseded/deleted), visibility | `graph_facts`: status, valid_from/to, freshness_policy_id, visibility_scope, created_by_event_id, authority_rank, confidence, occurred_at, created_at ✅ · **gap:** explicit `deleted_at`/tombstone + `source_updated_at`≠`synced_at` split |
| Relationships/edges | typed edges w/ provenance, temporal validity, visibility, confidence | `graph_edges` (edge_type, confidence, provenance) ✅ |
| Commitments/open loops | promised outcome, owner, recipient, source, due-date **basis**, state, completion criteria, blockers, renegotiation, completion evidence — else `incomplete_context` | commitment nodes + `commitment.action` (promised outcome), `commitment.due_at`; **Update 1** fails closed when the outcome is missing ✅ · **gap:** explicit due_date_basis + completion_criteria capture (needs source bodies = Level 2) |
| Evidence/provenance | prefer references; claim→source mapping; span hash; extractor version; separate evidence confidence | `graph_facts.created_by_event_id` + card `why[]` (field→value→source) ✅ · **Update 1** separates evidence/identity/situation/recommendation confidence ✅ |
| Bounded situation snapshots | immutable per-decision case file; retained for replay/audit | `reasoning_context_snapshots`, `reasoning_runs`, `config_snapshot_id` ✅ |
| Intelligence/decision records | decision id, snapshot ref, versions, findings, missing-context, alternatives, selected/suppressed, separate confidences, why-now, consequence, expiry | `signals` + `reasoning_run_outputs` + `cards.config_snapshot_id`/`template_version` + `signal_suppression_log` ✅ |
| Delivery/outcome | surface, delivered-to, dedup key, state (viewed/claimed/…/completed), actor+authority, handoff ref, verified completion, feedback | `cards.state`, `card_events`, `agent_claims`, `card_feedback_*` ✅ · **Update 1** CTA effects: claim ≠ complete ✅ |

## 4. Store only temporarily (short TTL, then delete/refresh)

Raw email bodies, full document text, transient payloads, parsed/OCR text, embeddings, LLM extraction
intermediates, candidate-match tables. → `capture/payload_store.py` + `/retention/purge` (raw-payload TTL).
If an excerpt becomes load-bearing evidence, retain only the **minimum span** under the evidence policy;
the full source stays in the source system, fetched on demand.

## 5. Never store by default

Complete mailbox/Slack history, all documents/drives, indefinite transcripts, generic personal memory,
unlimited cross-session recall, every payload just because the connector can read it, ungrounded model
summaries as facts, **any inferred identity/relationship/commitment/deadline/consequence as established
truth**, source content after revocation/deletion, cross-tenant facts/embeddings/learning.

## 6. Temporal semantics (every source-derived fact)

Distinguish: `source_updated_at` (provider change) · `observed_at` (business event) · `synced_at` (GeniOS
capture) · `valid_from`/`valid_to` · `expires_at`/TTL · `deleted_at`/tombstone. **Cron lag is real: never
describe the graph as real-time when it is 1–2h behind.** Before time-sensitive delivery/handoff,
revalidate critical facts whose freshness window elapsed.
- Today: `graph_facts` has `occurred_at` (≈observed), `created_at` (≈synced), `valid_from/to`, `freshness_policy_id`.
- **Gap being closed:** the intelligence card now surfaces an honest **freshness / "as of"** so it never implies real-time (see `_card_intelligence` freshness block).

## 7. Retention classes (durations are tenant/region-configurable)

Ephemeral processing (delete after extraction) · Refreshable context projection (keep while valid;
supersede, honour deletion) · Minimal evidence (keep to explain/replay) · Immutable decision record
(audit window; sensitive bytes may expire before metadata) · Delivery/outcome state (dedup, accountability)
· Aggregated learning (privacy-safe, tenant-scoped only). **Deletion must propagate**: revoked/deleted
source → no longer active evidence; dependent recommendations revalidated/suppressed; raw content purged;
honest tombstone kept.

## 8. Net-new work this contract triggers

1. **This document** — the explicit boundary contract (§18). ✅ done here.
2. **Card freshness honesty** — surface `freshness`/as-of on the intelligence card so it is never implied
   real-time. ✅ implemented in `_card_intelligence`.
3. **Deferred (bigger, lower urgency):** explicit `deleted_at`/tombstone column distinct from supersession;
   `source_updated_at`≠`synced_at` split; `resolution_status` enum on nodes; `due_date_basis` +
   `completion_criteria` capture (blocked on source-body capture = Level 2). Tracked, not silently dropped.

## 9. What Update 2 does NOT require us to build

The intelligence-safety half (card can't recommend an unknown commitment, missing→review_source,
separately-named confidences) is already delivered by **Update 1**. The storage half (provenance,
lifecycle, snapshots, TTL, cursors, visibility) already exists in the schema above. Update 2 is mostly
this **contract + freshness honesty**, not a rebuild.
