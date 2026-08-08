[Overview](00-Overview.md) · [The Four Brains](01-The-Four-Brains.md) · [Gaps](06-Gaps.md)

# Domain Compiler / Orchestrator

The `DomainCompiler` is the Layer 3 orchestrator. "Orchestrator" describes its coordination role;
"compiler" describes its contract: source expertise plus a pinned situation becomes one immutable
runtime artifact. A second decision-making orchestrator is unnecessary inside this layer.

## Public operation

```python
package = compiler.compile(business_situation, context_slice)
```

The context slice is optional only for compatibility when the BSO metadata already contains every
required fact. Production callers should pass the separately typed slice. No graph client, LLM
client, or reasoning engine is injected.

## The eight units

### 1. Capability Resolver

Starts with the domain registry's reverse index for `BusinessSituationObject.type`, evaluates the
authored situation predicates, then produces a bounded `RoutePlan` of domains, situations,
capabilities, required objects, optional objects, and never-load objects.

Unknown predicate inputs are not false. They are reported as incomplete situation context. Explicit
stubs are skipped and recorded. A stale generated registry, absent routed capability, empty required
object set, or excessive route fan-out is an authoring failure.

### 2. Object Resolver

Resolves global object ids from the selected domain catalogs. Required objects fail closed. Missing
optional objects are returned as typed degradation data. Domain ownership must match the selected
route, so an identically named concept cannot be pulled from an unrelated domain.

### 3. Brain Resolver

Builds two immutable snapshots:

- Expert slice: capabilities, objects, selected artifacts and explicit model/offering variants;
- runtime slice: relevant Organization, Behavior, and Adaptive entry versions.

It combines their content identities into `brain_snapshot_id`. It never mutates a source brain.

### 4. Knowledge Retriever

Loads each selected capability's authored knowledge manifest. It resolves playbooks, rules,
heuristics, mental models, and decision frameworks by id. It also loads only model and offering
overlays named explicitly by the BSO.

Missing references remain visible. The resolver never replaces a missing artifact with semantically
similar prose or an LLM-generated substitute.

### 5. Context Adapter

Evaluates the small authored predicate grammar against BSO data plus the supplied root/neighbor
facts and observations. It supports exact existence/comparison, edge count, and bounded
time/baseline operations while keeping unknown values explicit.

It also binds object definitions to matching BSO entity ids. Tenant identity, fact conflicts, and
context visibility are checked before routing. It adapts the boundary inputs; it does not bypass
Layer 2 to fetch more context.

### 6. Evidence Aggregator

Produces sorted source receipts for selected authoring documents and runtime brain rows. Receipts
include source id/version, content hash, brain, confidence, visibility, and trace lineage.

This makes both successful inclusion and important exclusion conditions reviewable without putting
reasoning results into Layer 3.

### 7. Expertise Builder

Constructs `ExpertisePackage` with:

```text
capabilities
objects + entity bindings
expert_rules
organization_rules
behavior_patterns
adaptive_preferences
confidence_bp
evidence
metadata
```

Package confidence never exceeds situation confidence. Missing optional knowledge lowers coverage;
runtime knowledge can add specificity but cannot inflate source certainty. Stable ordering and
canonical serialization produce the content-addressed id.

The builder does not deep-merge arbitrary mappings. Runtime claims participate in precedence only
when they declare the same `conflict_key`. On the preference axis Adaptive wins over Organization,
and Organization over Behavior. Permission categories are Organization-only. A same-rank tie fails
closed; selected and shadowed entry ids are both recorded and enter the runtime snapshot identity.

### 8. Expertise Publisher

Persists the immutable package. Publication is idempotent on `(org_id, expertise_id)`: the same
bytes return the stored object; different bytes under the same id fail. PostgreSQL projects and
checks the common envelope, stores both BSO and brain hashes, rejects update, and permits deletion
only for explicit tenant lifecycle operations.

## State machine

```text
received (BSO + context slice)
  -> routed
  -> objects_resolved
  -> knowledge_retrieved
  -> brains_snapshotted
  -> evidence_aggregated
  -> built
  -> published
```

There is no partial published state. Any fail-closed condition aborts before publication. A caller
may retry the complete compile because all selection and identity operations are deterministic.

## Edge-case matrix

| Scenario | Behavior |
|---|---|
| BSO names multiple domains | each domain is independently routed; only matched domains enter the plan |
| Context slice belongs to another org | reject before routing |
| Context visibility is narrower than the BSO | reject instead of widening graph evidence |
| Inline BSO fact conflicts with context slice | reject instead of selecting an implicit winner |
| No domain hint | registered domains are searched deterministically |
| Unknown domain hint | reject; do not silently widen search |
| Same situation type, predicate false | candidate excluded |
| Same situation type, predicate input absent | fail as incomplete context if no complete route remains |
| Capability is marked stub | skip and record; fail if all matches are stubs |
| Object in both required and optional sets | required wins |
| Object also in `never_load` | never-load wins |
| Optional object missing | continue, lower confidence, record id |
| Entity does not bind to an object | retain object knowledge with empty bindings |
| Runtime entry from another org | exclude before package construction |
| Private entry for org-visible BSO | exclude and record |
| Behavior/Adaptive publishes policy | reject the compile |
| Explicit preference conflict across brains | select Adaptive, then Organization, then Behavior |
| Explicit conflict ties at one rank | reject as ambiguous governance |
| Package publish is retried | return identical stored package |
| Existing id has different bytes | reject as an integrity conflict |

## Production composition

`genios_engine/packs/domain_wiring.py` owns process-level catalog reuse and constructs a compiler
from a caller-owned database connection. This keeps transaction lifetime and tenant context with the
application composition root. The filesystem catalog is immutable after load; runtime brains are
read fresh for each compilation.

The intended activation sequence is:

1. deploy schema and read/write code dark;
2. shadow-compile real BSOs and compare route/package goldens;
3. measure latency, package size, misses, exclusions, and conflicts;
4. dual-run legacy and package-fed Layer 4 with decisions disabled on the new path;
5. require replay and decision parity for an agreed window;
6. cut over per tenant behind a rollbackable flag;
7. retire legacy manifests only after rollback rehearsal.

## Verification surfaces

The focused test suite covers contract determinism, common envelope preservation, real-corpus
compilation, entity bindings, tenant and visibility isolation, permission-axis enforcement,
missing-context failure, required/optional knowledge behavior, and migration immutability. The full
repository suite remains the regression gate.
