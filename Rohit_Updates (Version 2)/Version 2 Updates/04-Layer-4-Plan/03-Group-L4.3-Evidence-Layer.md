# Group L4.3 — The Evidence Layer (3 components)

> **What this group owns:** the record of *what was observed*, so that a decision made
> today can be re-justified a year from now. The Store is the strongest code in L4. The
> shape around it is inverted against the spec.

---

## The inversion, stated plainly

| | Globe's model | Code today |
|---|---|---|
| Who mints evidence | **units**, as they observe | **adapters**, before any unit runs |
| What it carries | `unit_ref` · `claim` · `value` · `source` | source + payload; **no `unit_ref`, no `value_bp`** |
| How many builders | one | **three, with three id seeds** |
| Lifetime | as long as the decision | payload TTL **720h**, then gone |

Evidence is currently an **input to** reasoning rather than an **output of** it. That is
why a `Finding` cannot be traced to the observation that produced it, and why the same
fact carries different identities on different lanes.

---

# S1 · Evidence Schema — canonize `Finding` as the per-unit emission

**WHAT** — `Finding` already carries the claim, the reason code and the metrics. It is
the object units already emit. v2 declares it *the* evidence emission and adds the one
field it lacks.

```python
class Finding:
    ...                          # unchanged
    value_bp: int | None = None  # the observed magnitude, when there is one
    # unit_ref derives from the emitting reasoner_id — no new field, no new object
```

**WHY NOT A NEW TYPE** — a second evidence object would need a second builder, a second
store path and a second validator, and the L1 lesson (268 invented field names) says the
cheapest correct move is to *name what already exists* rather than to add beside it.

**WHERE** — `contracts/reasoning.py` (the type) · every unit's `calculate` (already
returns Findings) · the aggregator (reads `unit_ref` for Rule 11 grouping).

**ACCEPTANCE** — every Finding on a pilot run carries a resolvable `unit_ref`; a Finding
with a magnitude carries `value_bp`; nothing else changed shape.

---

# S2 · Evidence Builder — one helper, one seed (DLG-11)

**VERIFIED PROBLEM** — three builder sites compute evidence ids from different seeds, so
**the same fact gets a different identity per lane**. Cross-lane deduplication, Rule 11's
independence grouping and "have we already said this?" suppression are all impossible.

**FIX**
```
build_evidence_ref(org_id, entity_ref, field, source_ref, observed_at_key) -> EvidenceRef
    id = content_hash of the tuple above     # one seed, one shape, everywhere
```
All three sites call it. A migration maps historic ids forward; historic decisions replay
against the mapping table, never against a silently different id.

**WHY IT IS LOAD-BEARING** — Rule 11 (doc 04 E2) raises confidence only on evidence from
a *different independence group*. Groups are derived from source identity. With three id
seeds, two records of the same fact can look independent — which would let confidence
rise on a duplicate. **The builder fix is a correctness precondition for Rule 11**, not
a tidiness exercise.

**ACCEPTANCE** — one fixture fact routed through all three lanes yields **one** evidence
id; the migration maps every historic id; no decision replay breaks.

---

# S3 · Evidence Store — preserve, plus a digest that outlives the TTL

**CURRENT STATE — verified excellent.** Content-addressed, atomic, hash-verified on
replay, and it **fails closed** when a payload does not match its hash rather than
serving a silently altered value. Nothing about this changes.

**THE ONE GAP** — payloads live in a 720h-TTL table. After purge, a decision can still
prove *which* evidence it used but no longer *what that evidence said* — so a
year-old card cannot be re-justified, which is the entire point of the layer.

**FIX — a permanent digest beside the ref:**
```
{ evidence_id, value_digest, unit_ref, rendered_text[:120], observed_at_key }   # forever
{ full payload }                                                               # 720h TTL
```
Replay after purge **degrades to digest verification and says so** in the trace, instead
of failing closed on a decision that was perfectly sound.

**WHY 120 CHARACTERS** — enough to re-read the claim in a card ("renewal date moved to
March 3"), short enough that the permanent table stays small and carries no bulk PII.

**FAILURE MODES** — digest mismatch on replay (fail closed, as today — this path is not
weakened) · a digest written for a payload that never persisted (write both in one
transaction) · storage growth (bounded: one short row per evidence id).

**ACCEPTANCE** — a post-TTL replay verifies digests and **labels itself digest-verified**;
a tampered payload still fails closed; the permanent table's row size is bounded in test.

---

## Group acceptance gate — G-L4.3

```
pytest tests/reason/test_evidence_shape.py tests/reason/test_store_replay.py -q
```

| Metric | Gate |
|---|---|
| evidence id identical across all three lanes for one fact | exact |
| Findings carrying a resolvable `unit_ref` | 100% |
| post-TTL replay | digest-verified and labelled, never a false failure |
| tampered payload | still fails closed |
| historic id migration | complete, replay-tested |
