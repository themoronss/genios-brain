# Atlas alignment · Layer 6 Learning & Evolution

| Atlas hierarchy | Documentation location | Runtime mapping |
|---|---|---|
| Part A · seven-component Learning Orchestrator | `01-Learning-Orchestrator/` | `feedback/orchestrator.py`, `store.py`, `governance.py` |
| Part B · 11 Learning Units | `02-Learning-Units/` | ten analysis units in `feedback/units.py`; Unit 11 in governance |
| Part C · five Evolution Publishers | `03-Evolution-Publisher/` | guarded dispatch and stores in `feedback/store.py` |
| Promotion lifecycle | `04-Promotion-Lifecycle/` | contract state machine, validation/governance and locked transitions |
| `LearningObject` | `05-Contracts-and-Operations/01-LearningObject-Contract/` | `contracts/learning.py` v1 compatibility + v2 authority |
| Storage/API/tests/LLM policy | `05-Contracts-and-Operations/` | Layer 6 migrations 0045+0047 (after intervening Layer 5.2 migration 0046), learning routes and ratchets |

The Atlas and product architecture call this **Layer 6**. The package's internal import rank is 7;
that rank is not a product layer and there is no product Layer 7.

## Four brains, five publisher seams and two non-brain artifacts

The contract now makes the distinction explicit:

```text
BrainTarget    = organization | behavior | adaptive | runtime
LearningTarget = BrainTarget + metrics + knowledge_suggestion
```

The Atlas's five Evolution Publishers are Behavior, Adaptive, Organization, Runtime Memory and
Learning Metrics. Metrics is telemetry rather than a brain. Knowledge Evolution creates the other
non-brain target, a human-review suggestion; it never enters normal publisher dispatch. No enum,
API filter or writer can represent an Expert Brain target.

The planned dynamic-brain store boundary is also explicit: Layer 6 writes a governed, visibility-
preserving version; lower layers will consume only a reviewed typed snapshot. The producer half is
built. The four consumer contracts remain an integration item, so current code does not silently
make a generic JSON row affect a decision.

## `LearningObject` v2 alignment

| Atlas / Theory requirement | Current code truth |
|---|---|
| Tenant and schema identity | `org_id`, `schema_version='learning.v2'` |
| Unit, target, key and proposed change | closed enums, `subject_key`, canonical deep-frozen `value` |
| Repetition and time window | observations, independent refs, distinct days, first/last seen |
| Confidence and validation dimensions | integer confidence, noise, conflict, freshness and business value basis points |
| Evidence and lineage | source refs, source trace IDs, `trace_id`, `lineage_complete`, optional subject principal |
| Audience rule | explicit normalized `visibility {scope, principals, derived_from}` inherited at the narrowest boundary |
| Temporary/permanent/review promotion | lifecycle state plus projected promotion/governance fields |
| Supersession/rollback | proposal and entry lineage; safe predecessor restoration |
| Governance verdict | preflight plus pinned revisioned tenant policy; held Observed/Candidate may re-evaluate under a later claimed run |
| Reproducibility | content-derived ID/hash, verified rehydration, payload/projection constraints and append-only per-run policy/time evaluation ledger |
| Concurrency/erasure | tenant `orgs FOR SHARE` mutation root; policy before child/advisory locks; reset/delete owns tenant `FOR UPDATE` |

This closes the earlier v3.1 envelope gap: Layer 6 now carries both explicit visibility and a
trace ID. Migration 0047 propagates them through learned brains, Runtime memory, knowledge
suggestions and metrics, and rejects incomplete v2 projection shapes.

Personal preference is stricter than ordinary narrowest-ACL aggregation: user scope is always
projected to a private ACL containing exactly the resolved subject, and source exclusion or failed
resolution is rejected. Behavior/Adaptive derivations preserve that ceiling. Runtime is likewise a
closed lifecycle exception: it publishes as an expiring lease and API/database policy prevent a
human-review hold.

## Theory safety rules implemented

- Learning improves a later run; it never executes the current decision or delivery.
- Outcome evidence has more authority than interaction volume; neutral activity cannot become
  success.
- Terminal dashboard judgments version one canonical verdict. `wrong:bad_timing` remains canonical
  but is timing/neutral quality evidence; dashboard requeue and dashboard/extension snooze are
  lifecycle/timing audit facts, not verdict labels.
- A preference must be an explicit typed statement; a recurring pattern is not automatically a
  preference.
- Temporary memory has a lease, expires from PostgreSQL authority and cannot promote permanently.
- Delivery freshness comes from the latest lifecycle/receipt event, including non-receipt endings,
  rather than mutable row time or creation time alone.
- Only a `failed` delivery without an earlier `delivered_at` is transport-negative; a post-delivery
  ACCEPTED → FAILED transition remains transport-delivered and is evaluated as an execution/outcome.
- Promotion requires evidence, validation and governance; high confidence cannot bypass policy.
- Identical held evidence may be reconsidered only from Observed/Candidate under the later run's
  pinned current policy/time. Candidate never regresses and later lifecycle states never reopen.
- Knowledge evolution stops at a human-reviewed suggestion. Expert Brain remains human-controlled.
- An LLM may optionally structure/summarize a fact with provenance, but cannot score, validate,
  choose a target, promote, publish or roll back.
- PostgreSQL is source of truth. Redis, if added, is disposable acceleration only.
- Discovery reads never grant mutation authority: review and rollback recheck under canonical
  tenant → sorted policy → object/subject locks; feedback sources use tenant → graph → card.

## Honest alignment boundary

The internal Atlas structure is implemented and covered by local tests. Alignment is not a claim
that the product loop is already operating in production: typed lower-layer readers, real receipt/
event producers, populated-PostgreSQL 0046→0047 rehearsal, multi-replica proof, tenant policy
sign-off, observability and the human-owned suggestion-to-PR workflow remain external integration.
