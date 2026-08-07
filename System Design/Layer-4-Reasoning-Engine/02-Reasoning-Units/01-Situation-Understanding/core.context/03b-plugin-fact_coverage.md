# 03b · Plugin `fact_coverage`

**Class:** `context_unit.py:FactCoveragePlugin` · **`plugin_id`:** `fact_coverage`
**Observation kind:** `context.fact_coverage` · **Second** in execution order.
**Helper:** `context_unit.py:declared_fields` — exported, and the only helper in this unit with its
own test (`test_every_reasoners_declared_need_joins_the_denominator`).

---

## 1 · The claim it makes

> *Which of the declared facts are actually present, and which are known absences.*

Four integers: a share, and the three counts the share was computed from.

> *"This is the plainest claim the unit makes and the one most often skipped in practice: systems
> tend to reason from whatever arrived and never state what did not. Recording the absences by name
> is what lets a later human ask 'why did it not consider the owner?' and get an answer."*

Note the gap between the argument and the code: **the plugin publishes the absence *count*, not the
absent names.** `absent` is computed, used to derive `present` and `missing_field_count`, and then
discarded. The names survive only in `context.missing_fields` on the snapshot, which is a Layer 2
artifact and does not include fields that were simply never requested. A reader asking *"which
field was missing?"* has to reconstruct the answer by re-running `declared_fields` against the
snapshot. The three counts are in the trace; the names are not.

---

## 2 · The denominator — `declared_fields()`

Completeness is meaningless in the absolute:

> *"a snapshot with four facts is not 40% of anything unless something declared what the full set
> was. So the denominator is taken from the capability itself — its own `required_fields` plus
> every field its reasoners declared they need — rather than from a list this unit invents."*

```python
def declared_fields(view: UnitView) -> tuple[str, ...]:
    configured = view.config.get("context_fields")
    if configured is not None:
        if not isinstance(configured, (tuple, list)) or not all(
                isinstance(name, str) and name.strip() for name in configured):
            raise ValueError("context_fields must be a list of non-empty field names")
        return tuple(sorted({name.strip() for name in configured}))
    names: set[str] = set(view.request.capability.required_fields)
    for spec in view.request.capability.reasoners:
        names.update(spec.required_fields)
    names.update(view.request.context.missing_fields)
    return tuple(sorted(names))
```

### 2.1 · The three sources, when there is no override

| # | Source | Why it belongs |
|---|---|---|
| 1 | `capability.required_fields` | What the capability itself said it cannot work without |
| 2 | `spec.required_fields` for **every** reasoner in the manifest | *"A field only `core.temporal` asked for is still a fact this capability cares about."* (`test_every_reasoners_declared_need_joins_the_denominator`) |
| 3 | `context.missing_fields` | The fields Layer 2 *tried* to supply and could not |

The third is the interesting one:

> *"Those are the fields the selector tried to supply and could not; they are known absences, and
> leaving them out of the denominator would let a snapshot look complete precisely because
> retrieval failed."*

`test_fields_the_selector_failed_to_supply_still_count_against_completeness` calls that *"the worst
failure"* — and it is, because it is silent. A broken join in Layer 2 that drops two fields would,
without this line, raise completeness from 33% to 100% and make the outage look like a clean run.

The result is `tuple(sorted(set(...)))` — deduplicated and sorted, so the same manifest always
produces the same denominator regardless of declaration order.

### 2.2 · Worked denominator on the shipped manifest

`sales.deal_cooling_full`, computed by running `declared_fields` against the real manifest:

```text
capability.required_fields
    deal.status · deal.value · derived.engagement · thread.last_inbound

spec.required_fields, union over 20 reasoner specs
    core.temporal      derived.engagement · thread.last_inbound
    core.relationship  deal.status · relationship.verified_stakeholder_count
    core.confidence    deal.status · deal.value · derived.engagement · thread.last_inbound
    (the other 17 specs declare none)

context.missing_fields
    whatever Layer 2 could not supply on this run

declared_fields = 5 names
    deal.status
    deal.value
    derived.engagement
    relationship.verified_stakeholder_count       ← contributed only by core.relationship
    thread.last_inbound
```

**Each present field is worth exactly 2,000bp** on this capability. `core.relationship`'s
declaration is what makes it five rather than four — a fact worth knowing before someone tunes
`completeness_floor_bp`, because adding a unit to the roster silently moves the denominator and
therefore every completeness reading the capability has ever produced.

### 2.3 · The `context_fields` override

> *"A capability may override the whole set via `context_fields` when its reasoner declarations are
> not the right yardstick (e.g. a capability that reasons mostly on neighbour context)."*

**"The whole set" is literal.** When `context_fields` is present the function returns immediately;
`capability.required_fields`, the reasoner specs, *and* `context.missing_fields` are all ignored.
Verified:

```text
config={"context_fields": ["a.b"]}, facts={"a.b": 1}, missing_fields=("z.z",)
  → declared_fields = ('a.b',)              # z.z is NOT in the denominator
  → completeness_bp = 10,000                # a known absence made invisible

same snapshot, no override, capability.required_fields=("a.b",)
  → declared_fields = ('a.b', 'z.z')
  → completeness_bp = 5,000
```

That is the override doing what it was asked to do, and it is also the one way to reintroduce the
exact failure the `missing_fields` line exists to prevent. A capability that overrides the yardstick
takes responsibility for including its own known absences.

No shipped capability sets `context_fields`.

---

## 3 · When it stays silent

```python
declared = declared_fields(view)
if not declared:
    # Nothing declared what "complete" means here, so no share can be stated. Reporting
    # 100% because zero fields were missing would be the fabrication this unit exists to
    # prevent.
    return ()
```

**Silent when the denominator is empty.** Two ways to reach that:

| Situation | Reachable? |
|---|---|
| The capability declares no `required_fields`, no reasoner spec declares any, and Layer 2 reported no missing fields | yes — `test_a_capability_that_declares_nothing_gets_no_completeness_reading` |
| `context_fields` is set to an empty list | yes, verified: `config={"context_fields": []}` → `declared_fields = ()` → no observation, even with facts present |

*"100% of zero declared fields is not 'complete' — it is a question nobody asked."*

The empty-list case is worth flagging: it passes the `isinstance` and `all()` checks (`all()` over
an empty sequence is `True`), so it is accepted as valid configuration and silently disables the
coverage axis. There is no test for it and no comment about it.

---

## 4 · The arithmetic, in full

```python
declared = declared_fields(view)
if not declared:
    return ()
absent  = missing_fields(view.request, declared)
present = tuple(name for name in declared if name not in set(absent))
return (Observation(
    plugin_id=self.plugin_id,
    kind="context.fact_coverage",
    metrics={
        "completeness_bp": clamp_bp(divide_half_up(len(present) * 10_000, len(declared))),
        "declared_field_count": len(declared),
        "known_field_count": len(present),
        "missing_field_count": len(absent),
    },
    evidence_ids=evidence_ids(view.request, *present),
    reason_codes=("context_fields_absent",) if absent else ("context_fields_all_present",),
),)
```

```text
declared             = sorted, deduplicated names (§2)
absent               = common.py:missing_fields(request, declared)
present              = declared − absent, in declared (sorted) order
completeness_bp      = clamp_bp( divide_half_up( |present| × 10_000 , |declared| ) )
declared_field_count = |declared|          ≥ 1 by the silence guard
known_field_count    = |present|
missing_field_count  = |absent|            invariant: known + missing = declared
```

The clamp cannot bind: `present ⊆ declared`, so the ratio is in `[0, 1]` and the half-up division is
in `[0, 10_000]`. The denominator cannot be zero — the silence guard runs first, which is also what
keeps `divide_half_up` from raising `ValueError("denominator must be positive")`.

### 4.1 · Which absences `missing_fields` sees

```python
# reasoners/common.py
def missing_fields(request, fields):
    missing = []
    for field in fields:
        if field.startswith("neighbor:"):
            if field.split(":", 1)[1] not in request.context.neighbor_facts:
                missing.append(field)
        elif field not in request.context.facts:
            missing.append(field)
    return tuple(sorted(missing))
```

Presence in a mapping. Nothing else — not the value, not its age, not whether Layer 2 flagged it.
`neighbor:`-prefixed names are resolved against `context.neighbor_facts` with the prefix stripped,
which matters because `adapters/native.py` generates exactly that shape into
`context.missing_fields`:

```python
missing = tuple(sorted(
    [field for field in root_fields if field not in context.facts]
    + [f"neighbor:{field}" for field in neighbor_fields if field not in context.neighbor_facts]))
```

Verified end to end: a `neighbor:acct.tier` entry in `context.missing_fields` lands in the
denominator and is correctly counted as absent, because `neighbor_facts` does not contain
`acct.tier`.

### 4.2 · The reason code is binary and carries no magnitude

`context_fields_absent` if *anything* is missing, `context_fields_all_present` otherwise. One field
of a hundred missing produces the same code as ninety-nine of a hundred. The magnitude lives in
`completeness_bp`, and the threshold reading lives in `evaluate_meaning` — which is why this code
and `context_incomplete` are different strings saying different things:

| Code | Source | Means |
|---|---|---|
| `context_fields_absent` | the plugin | at least one declared field did not arrive |
| `context_incomplete` | the evaluator | `completeness_bp` fell below the capability's floor |

A run can carry `context_fields_absent` and `context_substantially_known` together — that is the
README §6 example, where four of five arrived: something is missing, and enough is here.

---

## 5 · What it cites

```python
evidence_ids=evidence_ids(view.request, *present)
```

```python
# reasoners/common.py
def evidence_ids(request, *fields):
    wanted = set(fields)
    return tuple(sorted(item.evidence_id for item in request.context.evidence
                        if item.field in wanted))
```

Every evidence row whose `field` is one of the present declared fields — the breadth of what the
coverage claim rests on. This is the widest citation set of the three plugins. On the README §6
example it is all five rows.

Two known holes.

**`neighbor:`-prefixed names never match.** The `wanted` set contains the prefixed name
(`neighbor:acct.tier`), while `EvidenceRef.field` carries the bare name (`acct.tier`). So a
neighbour fact that is present counts toward `known_field_count` and contributes **no citation**.
The mismatch is between two functions in the same module — `missing_fields` strips the prefix,
`evidence_ids` does not — and it is invisible until a capability declares a neighbour requirement.
None does today.

**`context_scope` is ignored.** A neighbour-scoped evidence row whose field name equals a present
root field would be cited as though the unit had observed it at the root. Harmless today because no
shipped capability has a colliding name; the same blindness exists in the base retriever
([02 · Retriever](02-Retriever.md) §4.3).

When `present` is empty, `evidence_ids(request)` is called with no fields, `wanted` is the empty
set, and the result is `()` — no citation, which is correct: a claim that nothing arrived cannot
cite the things that did not.

---

## 6 · Configuration

| Key | Type | Default | Validator | Failure mode |
|---|---|---|---|---|
| `context_fields` | list/tuple of non-empty strings | derived (§2.1) | inline in `declared_fields` | `ValueError("context_fields must be a list of non-empty field names")` |

**Validated eagerly** — `declared_fields` is the first call in `contribute`, before the silence
guard, so a malformed override raises on every run.
`test_a_malformed_coverage_override_is_a_deployment_fault` pins the whitespace case:
*"Silently ignoring bad config would make coverage mean something different per tenant."*

Verified behaviour of the accepted and rejected shapes:

```text
["deal.status"]            → ('deal.status',)
[" a.b ", "a.b", "c.d"]    → ('a.b', 'c.d')       stripped, deduplicated, sorted
[]                         → ()                    accepted → the plugin goes silent
["  "]                     → ValueError
"deal.status"              → ValueError            a bare string is not a list
[123]                      → ValueError
```

`ReasonerSpec.__post_init__` deep-freezes config through `contracts/reasoning.py:_freeze`, so a JSON
list arrives as a `tuple` and a set arrives as a hash-sorted tuple. The `isinstance(configured,
(tuple, list))` check accounts for that; a `dict` or a bare string is rejected.

---

## 7 · Worked examples

### 7.1 · Three of four declared

`test_completeness_is_measured_against_what_the_capability_declared_it_needs`.

```text
capability.required_fields = deal.status · deal.owner · deal.value_minor · deal.close_date
facts                      = deal.status · deal.owner · deal.value_minor

declared             = 4      (sorted: close_date, owner, status, value_minor)
absent               = ('deal.close_date',)
present              = 3
completeness_bp      = divide_half_up(3 × 10_000, 4) = (30,000 + 2) // 4 = 7,500
declared_field_count = 4 · known_field_count = 3 · missing_field_count = 1
reason_codes         = ('context_fields_absent',)
```

*"a share nobody can dispute later."*

### 7.2 · Retrieval failure folded into the denominator

`test_fields_the_selector_failed_to_supply_still_count_against_completeness`.

```text
capability.required_fields = ('deal.status',)
facts                      = {deal.status: open}
context.missing_fields     = ('deal.owner', 'deal.close_date')

declared        = 3       deal.close_date · deal.owner · deal.status
absent          = 2       (neither is in facts)
present         = 1
completeness_bp = divide_half_up(10_000, 3) = (10,000 + 1) // 3 = 3,333
```

Without the `missing_fields` line the denominator would be 1 and the reading would be **10,000bp** —
a broken selector reporting a perfect snapshot.

### 7.3 · The capability names its own yardstick

`test_a_capability_may_name_its_own_coverage_yardstick`.

```text
capability.required_fields = deal.status · deal.owner
facts                      = {deal.status: open}
config                     = {"context_fields": ["deal.status"]}

declared        = ('deal.status',)
present         = 1
completeness_bp = 10,000
reason_codes    = ('context_fields_all_present',)
```

The same snapshot reads 5,000bp without the override and 10,000bp with it. The override is a
capability saying *"deal.owner is not part of what I mean by complete"* — a legitimate statement,
and a loaded gun.

### 7.4 · The reference table

Every value computed from `divide_half_up(present × 10_000, declared)`:

| present / declared | `completeness_bp` | Against the 6,000bp default floor |
|---|---|---|
| 0 / 3 | 0 | incomplete |
| 1 / 6 | 1,667 | incomplete |
| 1 / 3 | 3,333 | incomplete |
| 2 / 5 | 4,000 | incomplete |
| 2 / 4 | 5,000 | incomplete |
| 4 / 7 | 5,714 | incomplete |
| **3 / 5** | **6,000** | **substantially known** — the boundary is `<`, not `≤` |
| 5 / 8 | 6,250 | substantially known |
| 2 / 3 | 6,667 | substantially known |
| 3 / 4 | 7,500 | substantially known |
| 4 / 5 | 8,000 | substantially known |
| 5 / 5 | 10,000 | substantially known |

On the shipped five-field manifest that means **three of five is enough and two of five is not.**

---

## 8 · Cross-unit note: two units compute `completeness_bp` and they disagree by design

`core.confidence` emits `completeness_bp` into its result too, deliberately undeclared:

> *"`completeness_bp` is already owned by `core.context`, and the roster invariant allows exactly
> one declared publisher per metric name. The value is preserved byte-for-byte because removing or
> renaming it would change every decision hash; the name collision is recorded here rather than
> fixed."* — `confidence.py:UNDECLARED_METRICS`

The two denominators are different:

| | `core.context:fact_coverage` | `core.confidence:coverage_completeness` |
|---|---|---|
| Denominator | `capability.required_fields` ∪ **all** `spec.required_fields` ∪ `context.missing_fields` | `spec.required_fields` **or** `capability.required_fields` — whichever is non-empty, never both |
| Known absences from Layer 2 | counted | **not counted** |
| Empty denominator | no observation | `completeness_bp = 10_000` — *"A capability that declared no required fields asked for nothing and got all of it."* |
| Override key | `context_fields` | none |

On `sales.deal_cooling_full` with `relationship.verified_stakeholder_count` absent:

```text
core.context     declared 5, present 4  → completeness_bp = 8,000
core.confidence  declared 4, present 4  → completeness_bp = 10,000
```

A 2,000bp gap on the same metric name in the same run. `core.validation:ContradictionPlugin` would
flag it as `units_disagree_on_metric` only above `contradiction_gap_bp` (default 5,000) *and* only
if both units were declared dependencies of `core.validation` — which they are not; in
`deal_cooling_v2` the validation unit depends on risk, opportunity, impact and confidence, not
context. So today the collision is invisible in every direction.

**A consumer reading `completeness_bp` off a result must check which result it came from.** The
opposite-direction disagreement is the dangerous one: `core.confidence` reads 10,000 in exactly the
case `core.context` was built to catch — a snapshot whose fields are missing because retrieval
failed.

---

## Related

| File | Covers |
|---|---|
| [03 · Analyzer](03-Analyzer.md) | Execution order and plugin independence |
| [03a · `evidence_freshness`](03a-plugin-evidence_freshness.md) | The first plugin |
| [03c · `source_corroboration`](03c-plugin-source_corroboration.md) | The third |
| [05 · Evaluator](05-Evaluator.md) | `completeness_floor_bp` and the `context_incomplete` code |
| [06 · Builder and Metrics](06-Builder-and-Metrics.md) | Where these four metrics land, and why nothing detects the collision |
