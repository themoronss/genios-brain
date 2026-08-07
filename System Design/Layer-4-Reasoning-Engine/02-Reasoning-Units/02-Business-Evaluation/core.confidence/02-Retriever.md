# 02 · Retriever

**Stage 3:** `unit.py:ReasoningUnit.retrieve` (line 190) — **not overridden**. This unit uses the
base implementation unchanged.

---

## 1 · What it is for

The Retriever answers *which slice of the frozen snapshot is this unit allowed to look at?* Its
product is a `UnitView` — the bounded window that lets a reviewer answer "what could this unit
possibly have seen" without reading the unit's body.

The framework is explicit that this stage does not fetch anything:

> *Units are forbidden to touch a database, network, or clock — that is what makes a decision
> replayable months later. Retrieval already happened when Layer 2 froze the ContextSnapshot. So
> "Retriever" here means select and shape from that frozen input.*

For this unit the stage is inherited whole. It is also, uniquely in the roster, **inherited and then
ignored**.

---

## 2 · What the base implementation does

```python
# unit.py:190
def retrieve(self, request, spec, prior) -> UnitView:
    wanted = tuple(field for field in spec.required_fields
                   if not field.startswith("neighbor:"))
    facts = {name: request.context.facts[name]
             for name in wanted if name in request.context.facts}
    evidence = tuple(sorted(item.evidence_id for item in request.context.evidence
                            if item.field in facts))
    return UnitView(request=request, spec=spec, prior=prior,
                    facts=MappingProxyType(facts), evidence_ids=evidence)
```

Three selections and one wrapper.

| Field of `UnitView` | Contents for this unit | Read by this unit? |
|---|---|---|
| `request` | the whole `ReasoningRequest` | **yes** — this is what it actually uses |
| `spec` | the capability's `ReasonerSpec` for `core.confidence` | **yes** — `required_fields` and `config` |
| `prior` | declared dependencies only | **yes** — the bridge lookup |
| `facts` | `spec.required_fields ∩ context.facts`, as a read-only mapping | **no** |
| `evidence_ids` | ids of evidence items whose `field` is in `facts` | **no** |
| `config` (property) | `spec.config` | **yes** — `source_reasoner` |

### 2.1 · What that produces on the shipped capability

Taking `sales.deal_cooling`, whose spec declares four required fields, with three of them present:

```python
spec.required_fields = ("deal.status", "deal.value", "derived.engagement", "thread.last_inbound")
context.facts        = {"deal.status": {...}, "deal.value": {...}, "derived.engagement": 42}
context.evidence     = (EvidenceRef("ev_crm",  field="deal.status",        group="crm"),
                        EvidenceRef("ev_mail", field="derived.engagement", group="mailbox"))
```

```
view.facts        → {"deal.status", "deal.value", "derived.engagement"}
view.evidence_ids → ("ev_crm", "ev_mail")
```

Both were verified by calling `retrieve` directly. And both are then **discarded**: the run's
`ReasonerResult.evidence_ids` is `()`.

---

## 3 · Why the unit reads around its own window

Nothing in `confidence.py` mentions `view.facts` or `view.evidence_ids`. Every read goes through
`view.request`:

| Accessor | Line | Reaches for |
|---|---|---|
| `_present_fields` | 113 | `view.request.context.facts` |
| `FactSourceQualityPlugin.contribute` | 162 | `common.py:fact_record(view.request, field)` → `request.context.facts` |
| `CoverageCompletenessPlugin.contribute` | 211 | `view.request.context.evidence` |

This is not an oversight in either direction. Both bypasses are **required** by what the unit
measures.

### 3.1 · The facts bypass is required by the completeness fallback

`_declared_fields` falls back to the *capability's* `required_fields` when the spec declares none:

```python
# confidence.py:108
return tuple(view.spec.required_fields or view.request.capability.required_fields)
```

The base retriever only ever selects `spec.required_fields`. So when the fallback engages,
`view.facts` is **empty** while the unit still has work to do. Demonstrated:

```
spec.required_fields       = ()
capability.required_fields = ("a.one", "a.two", "a.three")
context.facts              = {"a.one": 1}

view.facts        → {}                    ← the retriever selected nothing
_declared_fields  → ("a.one", "a.two", "a.three")
_present_fields   → ("a.one",)            ← read straight from request.context.facts
completeness_bp   = half_up(1 × 10,000, 3) = 3,333
confidence_bp     = half_up(5,000×40 + 3,333×30 + 5,000×20 + 0×10, 100)
                  = half_up(200,000 + 99,990 + 100,000 + 0, 100)
                  = half_up(399,990, 100)  = 4,000
```

A unit that respected `view.facts` here would report `completeness_bp = 10,000` — "nothing was
asked for, so everything arrived" — which is the opposite of the truth. Pinned by
`test_the_capabilitys_own_required_fields_are_used_when_the_unit_declares_none`.

### 3.2 · The evidence bypass is required by what coverage means

`view.evidence_ids` holds only the ids of evidence backing *this unit's declared fields*. The
coverage axis is a claim about the snapshot as a whole:

> *It counts every evidence item in the frozen context rather than only the items backing this
> unit's fields, because independence is a property of where the picture came from, not of which
> field is being read right now.* — `confidence.py:196`

So `CoverageCompletenessPlugin` iterates `view.request.context.evidence` with **no filter at all**:
not by field, not by `context_scope`. Neighbour-scoped evidence counts toward the group total, as
does evidence for root fields this unit never declared. That is deliberate, and it is why a
capability whose *other* units pull in a second data source raises this unit's confidence even
though this unit reads none of those fields.

### 3.3 · The cost

The retriever builds a dictionary and a sorted tuple on every run, and nothing consumes either. The
`build` override then goes further and explicitly refuses the evidence ids it was handed
(see [06](06-Builder-and-Metrics.md) §4). The cost is a few microseconds and one piece of misleading
scaffolding: a reviewer reading `UnitView` for this unit will find a populated `facts` mapping that
has no bearing on the output.

**Cheapest honest fix:** override `retrieve` to return an empty view, as `core.priority` and
`core.risk` do, and let the emptiness state the truth — this unit reasons about the request and the
snapshot in aggregate, not from a selected slice. It is a behaviour-preserving change *only* because
`build` already discards the evidence ids; do it without that guarantee and every decision hash
would move.

---

## 4 · What the frozen snapshot guarantees before the unit sees it

`ContextSnapshot.__post_init__` (`contracts/reasoning.py:194`) enforces four invariants that this
unit silently depends on:

| Invariant | Line | What it means here |
|---|---|---|
| `evidence` is sorted by `evidence_id` | 202 | iteration order over evidence is total, so the group set is built deterministically |
| `evidence_id` values are unique | 207 | no evidence item can be counted twice |
| Every evidence item's `field` exists in its scope's fact map | 210 | coverage can never count evidence for a field that did not arrive |
| The evidence value semantically matches the fact's value | 216 | an evidence item is a citation of the fact, not an independent assertion |

The third one is the load-bearing one for this unit. `evidence_coverage_bp` counts independence
groups without checking whether the underlying facts arrived, and it is only safe to do so because
the contract has already made an evidence item without its fact impossible to construct.

`ReasonerSpec.__post_init__` and `CapabilityManifest.__post_init__` add a fifth: both
`required_fields` tuples are `tuple(sorted(set(...)))`. That is what makes `_declared_fields`
deterministic and what `test_fact_insertion_order_cannot_change_the_result` pins — two spellings of
the same declaration produce the same `semantic_hash`.

---

## 5 · What lands in `prior`

`prior` is the third `UnitView` field and the one the bridge depends on. The orchestrator builds it
per step:

```python
# orchestrator.py:158
dependencies = {item: prior[item] for item in spec.dependencies if item in prior}
```

**Only declared dependencies.** A capability that names `source_reasoner: legacy.rule` but forgets
`dependencies=("legacy.rule",)` gets `view.prior == {}`, the bridge stays silent, and the unit
computes a number the capability author never asked for — with no error anywhere. All four shipped
specs declare their source correctly:

| Capability | `dependencies` on this spec | `source_reasoner` | Declared consistently? |
|---|---|---|---|
| `sales.deal_cooling` | `("core.risk",)` | — | n/a, computed branch |
| `sales.deal_cooling_full` | inherited: `("core.risk",)` | — | n/a, computed branch |
| `sales.deal_health` | `("core.signal_composition",)` | `core.signal_composition` | yes |
| legacy pack, per rule | `("legacy.rule",)` | `legacy.rule` | yes |

`sales.deal_cooling` declaring `core.risk` as a dependency is itself worth noting: **the unit never
reads it.** Nothing in `confidence.py` touches `prior` except through `_bridged_confidence_bp`, and
that only looks up `config["source_reasoner"]`, which v1 leaves empty. The dependency exists to
order the DAG — confidence runs after risk — not to pass data. It is a scheduling edge wearing a
data edge's clothes, and it costs nothing except the reader's time.

---

## 6 · Edge cases

| Situation | `view.facts` | `view.evidence_ids` | Effect on the result |
|---|---|---|---|
| Spec declares 4 fields, 3 present | those 3 | ids of evidence on those 3 | none — both unused |
| Spec declares nothing, capability declares 3 | `{}` | `()` | none — completeness still measured from the capability's 3 |
| Spec declares `neighbor:contact.title` | filtered out of `wanted` by the base retriever | — | the field still counts in `_declared_fields`' denominator and can never be present, so completeness is permanently capped. No shipped capability does this |
| Evidence exists for a field the unit never declared | not in `facts`, so its id is not selected | `()` for that item | **still counted** toward `independent_evidence_groups` |
| Neighbour-scoped evidence | never selected — its field is in `neighbor_facts` | not selected | **still counted** toward `independent_evidence_groups` |
| `prior` empty | — | — | bridge silent, computed branch runs |

The last three rows are the ones a reader is most likely to get wrong. The `UnitView`'s emptiness
says nothing about what the coverage axis counted.

---

## Related

- [01 · Input and Validator](01-Input-and-Validator.md) — where `required_fields` comes from and what refuses a run
- [03a · `coverage_completeness`](03a-plugin-coverage_completeness.md) — the unfiltered evidence scan in full
- [03c · `legacy_bridge`](03c-plugin-legacy_bridge.md) — what `prior` is used for
- [06 · Builder and Metrics](06-Builder-and-Metrics.md) — why the selected evidence ids are thrown away
- [Unit Framework §3.1](../../README.md) — the Retriever's departure from the spec, and the `neighbor:` inconsistency
