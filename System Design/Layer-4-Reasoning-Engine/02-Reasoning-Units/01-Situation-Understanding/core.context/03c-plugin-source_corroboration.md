# 03c · Plugin `source_corroboration`

**Class:** `context_unit.py:SourceCorroborationPlugin` · **`plugin_id`:** `source_corroboration`
**Observation kind:** `context.source_corroboration` · **Third** in execution order.
**Helper:** `context_unit.py:independence_key` — exported and directly tested.

This plugin publishes five of the unit's twelve metrics and carries the most reasoning per line. It
is also the one with the largest gap between what it can express and what the shipped system feeds
it — §6.

---

## 1 · The claim it makes

> *How many independent witnesses stand behind what we believe — and where they disagree.*

> *"One source saying something and three independent sources saying the same thing are different
> epistemic situations, and the difference is invisible unless somebody counts."*

Five integers: the witness count on the best-corroborated field, how many fields clear the
capability's bar, how many rest on a single source, how many fields carry any evidence at all, and
how many show disagreement.

### Conflict is reported, never resolved

> *"Where independent witnesses cite different values for the same field, this unit says so and
> stops; choosing which witness to believe is a judgement, and judgement belongs to the Decision
> Maker with the full picture in front of it."*

`test_disagreeing_independent_sources_are_reported_and_never_resolved` pins both halves: the count
goes up, both rows are cited, and no winner is named.

---

## 2 · Witnesses, not rows — `independence_key()`

```python
def independence_key(item: EvidenceRef) -> str:
    if item.independence_group:
        return f"group:{item.independence_group}"
    if item.source_ref_id:
        return f"source:{item.source_ref_id}"
    return f"evidence:{item.evidence_id}"
```

> *"Two rows are one witness when they came from the same place. A mailbox sync that ingests the
> same thread twice, or two CRM fields written by the same integration, is a single observer
> repeating itself; counting it as two would let the system manufacture corroboration out of
> duplication."*

| Precedence | Field on `EvidenceRef` | Key | Meaning |
|---|---|---|---|
| 1 | `independence_group` | `group:<name>` | Layer 2 stated the witness explicitly |
| 2 | `source_ref_id` | `source:<id>` | no group declared; the source reference is the next best proxy |
| 3 | — | `evidence:<evidence_id>` | *"an unattributed row can only ever speak for itself"* |

**The namespace prefixes are not decoration.**

> *"The namespace prefixes exist so that an `independence_group` named 'crm' and a `source_ref_id`
> named 'crm' are never accidentally treated as the same witness."*

`test_a_group_and_a_source_of_the_same_name_are_different_witnesses` asserts
`group:crm != source:crm`. A plain string key would collapse two real observers into one and
*understate* corroboration — the safe direction, but wrong.

The fallback chain is monotonically conservative: each step down attributes *less* independence, and
the last step attributes the minimum possible. There is no path by which a missing attribute
inflates a count.

---

## 3 · The arithmetic, in full

```python
def contribute(self, view: UnitView) -> tuple[Observation, ...]:
    minimum = _config_count(view, "min_corroboration", 2)
    witnesses: dict[str, dict[str, set[str]]] = {}
    citations: dict[str, list[str]] = {}
    # Sorted so neither the grouping nor the cited evidence depends on snapshot iteration order.
    for item in sorted(view.request.context.evidence, key=lambda ref: ref.evidence_id):
        field_witnesses = witnesses.setdefault(item.field, {})
        field_witnesses.setdefault(independence_key(item), set()).add(semantic_hash(item.value))
        citations.setdefault(item.field, []).append(item.evidence_id)
    if not witnesses:
        return ()
    best = min(witnesses, key=lambda name: (-len(witnesses[name]), name))
    conflicts = sum(1 for groups in witnesses.values()
                    if len(groups) > 1 and len({h for hs in groups.values() for h in hs}) > 1)
    corroborated = sum(1 for groups in witnesses.values() if len(groups) >= minimum)
    single = sum(1 for groups in witnesses.values() if len(groups) == 1)
    return (Observation(..., metrics={
        "corroboration_count":        len(witnesses[best]),
        "corroborated_field_count":   corroborated,
        "single_sourced_field_count": single,
        "evidenced_field_count":      len(witnesses),
        "conflict_count":             conflicts,
    }, evidence_ids=tuple(citations[best]),
       reason_codes=("context_sources_conflict",) if conflicts else ("context_sources_agree",)),)
```

### 3.1 · The data structure

```text
witnesses : field → ( independence_key → set of semantic_hash(value) )
citations : field → [ evidence_id, … ]        in evidence_id order

for each evidence row e, in evidence_id order:
    witnesses[e.field][independence_key(e)] ∪= { semantic_hash(e.value) }
    citations[e.field] += [ e.evidence_id ]
```

A two-level map. The outer level is the field; the inner level is the witness; the leaf is the set
of *distinct values that witness asserted for that field*. Values are compared by
`platform/canonical.py:semantic_hash`, which is `sha256(canonical_dumps(value))` — so `4500000` and
`"4500000"` are different values, `Decimal("1.0")` and `Decimal("1.00")` are the same (normalised),
and floats raise rather than compare.

### 3.2 · The five metrics

```text
corroboration_count        = |witnesses[best]|                              ≥ 1
corroborated_field_count   = |{ f : |witnesses[f]| ≥ min_corroboration }|
single_sourced_field_count = |{ f : |witnesses[f]| = 1 }|
evidenced_field_count      = |witnesses|                                    ≥ 1
conflict_count             = |{ f : |witnesses[f]| > 1
                                  ∧ |⋃ over witnesses of their value hashes| > 1 }|
```

`corroborated_field_count` and `single_sourced_field_count` do not partition the field set unless
`min_corroboration == 2`. At the default they do: a field has either one witness or two or more.
At `min_corroboration = 3` a two-witness field is in neither bucket, and at `min_corroboration = 1`
a single-witness field is in **both**. Verified:

```text
one field, one witness, min_corroboration = 1
  → corroborated_field_count = 1  AND  single_sourced_field_count = 1
```

Not a contradiction — they answer different questions — but a consumer computing
`evidenced − corroborated − single` will get a negative number.

### 3.3 · Picking the best field

```python
best = min(witnesses, key=lambda name: (-len(witnesses[name]), name))
```

> *"Deterministic pick: most witnesses first, field name as the tie-break — never dict order."*

Negating the length turns `min` into "most witnesses", and the field name breaks ties
lexicographically. Verified: two fields with one witness each, `a.f` and `z.f`, select `a.f` and
cite `ev_a`.

This matters because `corroboration_count` is a **single field's** count presented as the unit's
headline corroboration number, and because `citations[best]` is what the observation cites. Both
are properties of one arbitrarily-chosen-but-deterministically-chosen field. A snapshot where
`deal.status` has three witnesses and every other field has one reports
`corroboration_count: 3` — which reads as *"this situation is well corroborated"* when the honest
reading is *"one fact in this situation is well corroborated."* `single_sourced_field_count` is the
corrective, and it is published beside it for exactly that reason.

---

## 4 · When it stays silent

```python
if not witnesses:
    return ()
```

**Silent when `context.evidence` is empty.** Because every evidence row contributes a field key,
`witnesses` is empty if and only if the evidence tuple is.

> *"Zero witnesses is not 'one weak witness' — it is nothing to report."*
> (`test_a_snapshot_with_no_evidence_makes_no_corroboration_claim`)

Note what does **not** cause silence: undated rows, future-dated rows, neighbour-scoped rows. All of
them count here. This plugin cares about provenance, not time, so the exclusions
[`evidence_freshness`](03a-plugin-evidence_freshness.md) applies do not exist here. A snapshot whose
every row is dated in the future produces no freshness reading and a full corroboration reading.

`min_corroboration` is read **before** the silence check, so a malformed value raises even on a
snapshot with no evidence:

```text
config={"min_corroboration": 0}, evidence=()
  → ValueError: min_corroboration must be a positive integer
```

---

## 5 · What a conflict is, and the two ways the predicate is wrong

### 5.1 · The stated rule

```python
conflicts = sum(1 for groups in witnesses.values()
                if len(groups) > 1 and len({h for hs in groups.values() for h in hs}) > 1)
```

> *"A conflict needs two independent witnesses; one source citing two values for a list-valued fact
> is describing facets of the same fact, not contradicting itself."*

`test_one_source_citing_two_members_of_a_list_fact_is_not_a_conflict` pins the first clause:
`deal.contacts = ("ana@buyer.com", "raj@buyer.com")` with both rows in `independence_group="crm"`
gives `conflict_count = 0`, because `len(groups) == 1`.

### 5.2 · A conflict is only *representable* for collection-valued facts

This is not visible in the plugin at all — it comes from the snapshot contract.
`ContextSnapshot.__post_init__` validates every evidence row against the fact it points at:

```python
matches = semantic_hash(actual) == semantic_hash(item.value)
if not matches and isinstance(actual, (tuple, list)):
    matches = any(semantic_hash(member) == semantic_hash(item.value) for member in actual)
if not matches:
    raise ValueError(f"evidence {item.evidence_id} value does not match its context fact")
```

For a **scalar** fact, every evidence row's value must be semantically identical to the fact's
value. Two witnesses cannot cite different values for `deal.status` — the snapshot refuses to be
constructed. Verified:

```text
facts    = {deal.value: 4500000}
evidence = ev_a (crm,     value 4500000)
           ev_b (mailbox, value "4500000")
  → ValueError: evidence ev_b value does not match its context fact
```

So `conflict_count > 0` is reachable **only for a fact whose value is a tuple or list**, where two
witnesses cite different members. Every other kind of source disagreement — the CRM says `open` and
the mailbox says `closed_lost` — is resolved upstream, in Layer 2's fact merge, before a snapshot
exists. The unit's docstring describes a general capability; the contract permits one narrow case.

That is arguably fine: disagreement resolution *is* Layer 2's job, and the graph's authority ranking
exists to do it. But it means the `conflict_count` metric is far narrower than the module's prose,
and a reader should not expect it to surface source disagreement in general.

### 5.3 · The predicate produces a false positive on agreeing witnesses

The value hashes are flattened across **all** witnesses before being counted:

```python
len({h for hs in groups.values() for h in hs}) > 1
```

That asks *"did the witnesses collectively mention more than one value?"* — not *"do the witnesses
disagree?"*. Two witnesses that agree perfectly on a two-member list are reported as a conflict.
Verified:

```text
facts    = {deal.contacts: ("ana@b.com", "raj@b.com")}
evidence = ev_c1 crm     → ana
           ev_c2 crm     → raj
           ev_m1 mailbox → ana
           ev_m2 mailbox → raj

witnesses['deal.contacts'] = { group:crm     : {h(ana), h(raj)},
                               group:mailbox : {h(ana), h(raj)} }
len(groups) = 2 > 1 ✓
union of hashes = {h(ana), h(raj)}, size 2 > 1 ✓
  → conflict_count = 1
  → reason_codes = ('context_sources_conflict',)
```

Two integrations that independently confirm the same two contacts — the strongest corroboration the
model can express — are reported as a disagreement. The same four rows also correctly yield
`corroboration_count: 2` and `corroborated_field_count: 1`, so the observation simultaneously says
*"well corroborated"* and *"in conflict"*.

The tested conflict case (`ev_crm → ana`, `ev_mail → raj`) and this one are indistinguishable to the
predicate. A predicate that matched the prose would compare the witnesses' value sets to each other
— for example, flag a field when the witnesses' hash sets are not all equal, or when their
intersection is empty — rather than counting distinct values in their union. Nothing in the test
suite covers the agreeing-witnesses case, which is why it survived.

**Combined with §5.2 this is narrow in practice:** it requires a collection-valued fact, at least
two declared independence groups, and at least two members cited per group. No shipped snapshot
adapter can produce that shape (§6). It is recorded because it will become reachable the moment one
can.

---

## 6 · The finding that matters most: production feeds this plugin one witness

Both shipped snapshot adapters emit **exactly one `EvidenceRef` per field**.

```python
# reason/adapters/native.py:native_context_snapshot — the path a live capability run takes
evidence = tuple(
    [_evidence(org_id=…, field=field, record=context.facts[field], neighbor=False)
     for field in root_fields if field in context.facts]
    + [_evidence(org_id=…, field=field, record=context.neighbor_facts[field], neighbor=True)
       for field in neighbor_fields if field in context.neighbor_facts])
```

One comprehension, one row per field. `adapters/legacy_context.py` does the same over
`rule.evidence_fields`. Therefore, on every real run:

```text
|witnesses[f]| = 1  for every field f

corroboration_count        = 1
corroborated_field_count   = 0            (default min_corroboration = 2)
single_sourced_field_count = evidenced_field_count
conflict_count             = 0
reason_codes               = ('context_sources_agree',)
evaluator adds             = 'context_single_sourced'
```

**Four of this plugin's five metrics are constants in production, and the fifth is just the field
count.** The corroboration axis of the Context Unit cannot fire.

The information is not missing — it is somewhere else. `runner.py` loads each fact with two
provenance columns:

```sql
(select min(sr.source) from graph_source_refs sr
 where sr.fact_version_id = f.fact_version_id)                       as source_group,
(select count(distinct sr.source) from graph_source_refs sr
 join graph_facts fv on fv.fact_version_id = sr.fact_version_id
 where fv.fact_id = f.fact_id)                                       as src_count
```

`source_group` — a single string, `min()` of possibly several — becomes the one row's
`independence_group`. `src_count` — the real number of distinct sources behind the fact — is
carried in the fact record and read by `core.confidence:FactSourceQualityPlugin`:

```python
groups = integer(record.get("src_count", 1), f"{field}.src_count")
corroborations.append(_CORROBORATION_MANY_BP if groups >= 3
                      else (_CORROBORATION_PAIR_BP if groups == 2 else _CORROBORATION_SINGLE_BP))
```

So the system does know that three sources back a fact. `core.confidence` reads it off `src_count`;
`core.context` counts evidence rows and sees one. Two units measuring corroboration from two
different representations of the same truth, and only one of them is wired to the representation
that carries it.

### 6.1 · The `unattributed` default makes two branches of `independence_key` dead

Both adapters set:

```python
independence_group=(str(mapping["independence_group"])
                    if mapping.get("independence_group") else "unattributed")
```

`independence_group` is therefore **never `None`** on a row produced by either adapter, so
`independence_key` always takes branch 1 and returns `group:…`. The `source:` and `evidence:`
fallbacks are reachable only from hand-built `EvidenceRef`s — that is, from tests and replay
fixtures.

`runner.py` supplies `f"source:{r.source_group}"` when a source group exists, so a real key reads
`group:source:gmail`. The double prefix is harmless and slightly confusing in a trace.

The `"unattributed"` literal has a real effect: **all unattributed rows on one field collapse into a
single witness**, rather than each speaking for itself as `evidence:<id>` would. That is the
conservative direction — it cannot manufacture corroboration — and it is the opposite of what the
`independence_key` docstring describes for that case. The docstring describes the contract; the
adapters never exercise it.

### 6.2 · What would need to change

Nothing in this plugin. Either the adapter emits one `EvidenceRef` per `graph_source_refs` row —
which is the shape `independence_key` was written for — or the plugin learns to read `src_count`
off the fact record, which would duplicate `core.confidence`'s approach and lose the per-witness
value comparison that makes conflict detection possible at all. The first is the change the design
implies. It is not built, and no test asserts the current constant behaviour either, so the day the
adapter changes, these metrics start moving with nothing pinned to catch it.

---

## 7 · Configuration

| Key | Type | Default | Validator | Also read by |
|---|---|---|---|---|
| `min_corroboration` | positive integer | `2` | `_config_count` | `evaluate_meaning`, for the `context_corroborated` reason code |

**Validated eagerly** in the plugin (before the silence check), **lazily** in the evaluator (only
when a `corroboration_count` metric exists). Since the plugin runs first and always reads it, the
eager path wins in practice: a malformed value raises during `analyze`, before `evaluate_meaning` is
reached.

The default of 2 encodes *"a second independent witness is what turns an assertion into a fact"*.
Nothing in the module argues for 2 specifically over 3, and no capability has tuned it.

---

## 8 · What it cites

```python
evidence_ids=tuple(citations[best])
```

**Every row on the best-corroborated field** — including multiple rows from the same witness, since
`citations` is keyed on field rather than on witness. On the conflict test that is both rows:

```python
assert observation.evidence_ids == ("ev_crm", "ev_mail")
```

> *"It counts the disagreement and cites both rows; it never names a winner."*

Rows on every other field are not cited by this plugin. They may still reach the result through
`fact_coverage`'s wider citation, which is what happens on the README §6 example: corroboration
cites two of five rows, coverage cites all five, and the union is five.

`citations[best]` is built by appending in `evidence_id`-sorted iteration order, so it is already
sorted before `Observation.__post_init__` sorts and deduplicates it again.

---

## 9 · Worked examples

### 9.1 · Two independent sources corroborate a fact

`test_two_independent_sources_corroborate_a_fact`.

```text
facts    = {deal.status: open}
evidence = ev_crm  (deal.status, "open", independence_group="crm")
           ev_mail (deal.status, "open", independence_group="mailbox")

witnesses['deal.status'] = { group:crm     : {h("open")},
                             group:mailbox : {h("open")} }

corroboration_count        = 2
corroborated_field_count   = 1        (2 ≥ min_corroboration 2)
single_sourced_field_count = 0
evidenced_field_count      = 1
conflict_count             = 0        (union of hashes = {h("open")}, size 1)
reason_codes               = ('context_sources_agree',)
evidence_ids               = ('ev_crm', 'ev_mail')
```

### 9.2 · The same source reported twice is one witness

`test_the_same_source_reported_twice_is_one_witness`. *"A mailbox sync ingesting the same thread
twice must not manufacture agreement."*

```text
evidence = ev_a (deal.status, "open", independence_group="mailbox")
           ev_b (deal.status, "open", independence_group="mailbox")

witnesses['deal.status'] = { group:mailbox : {h("open")} }      # one key, two rows folded

corroboration_count        = 1
corroborated_field_count   = 0
single_sourced_field_count = 1
evidence_ids               = ('ev_a', 'ev_b')     # both rows cited; one witness counted
```

The citation set and the witness count deliberately differ. The trace shows both rows so a reviewer
can see the duplication; the metric refuses to be impressed by it.

### 9.3 · Independent witnesses citing different members of a list

`test_disagreeing_independent_sources_are_reported_and_never_resolved`.

```text
facts    = {deal.contacts: ("ana@buyer.com", "raj@buyer.com")}
evidence = ev_crm  (deal.contacts, "ana@buyer.com", group="crm")
           ev_mail (deal.contacts, "raj@buyer.com", group="mailbox")

witnesses['deal.contacts'] = { group:crm     : {h("ana@buyer.com")},
                               group:mailbox : {h("raj@buyer.com")} }
len(groups) = 2 > 1                     ✓
union of hashes size 2 > 1              ✓
  → conflict_count = 1
reason_codes = ('context_sources_conflict',)
evidence_ids = ('ev_crm', 'ev_mail')
```

Both rows cited, no winner named.

### 9.4 · The same shape from one witness

`test_one_source_citing_two_members_of_a_list_fact_is_not_a_conflict`.

```text
evidence = ev_a (deal.contacts, "ana@buyer.com", group="crm")
           ev_b (deal.contacts, "raj@buyer.com", group="crm")

witnesses['deal.contacts'] = { group:crm : {h("ana"), h("raj")} }
len(groups) = 1                          ✗ first clause fails
  → conflict_count = 0
```

*"A single observer describing two facets of one fact has not contradicted itself."* Compare with
§5.3, where adding a second witness that says exactly the same thing turns this into a conflict.

### 9.5 · Multiple fields, unequal corroboration

The README §6 snapshot:

```text
witnesses
    deal.status         { group:source:crm, group:source:gmail }    2 witnesses
    deal.value          { group:source:crm }                        1
    derived.engagement  { group:unattributed }                      1
    thread.last_inbound { group:source:gmail }                      1

best = 'deal.status'          (most witnesses; no tie)

corroboration_count        = 2
corroborated_field_count   = 1
single_sourced_field_count = 3
evidenced_field_count      = 4
conflict_count             = 0
evidence_ids               = ('ev_crm_status', 'ev_mail_status')
```

Read the three counts together: *one fact is confirmed twice, three rest on a single source.* That
sentence is the reason the plugin publishes all three rather than a single "corroboration score".

*(This snapshot is hand-built. A snapshot produced by `native.py` would report
`corroboration_count: 1, corroborated_field_count: 0, single_sourced_field_count: 4` — see §6.)*

---

## Related

| File | Covers |
|---|---|
| [03 · Analyzer](03-Analyzer.md) | Why `min_corroboration` being read twice cannot cause disagreement |
| [03a · `evidence_freshness`](03a-plugin-evidence_freshness.md) | The other plugin that reads `context.evidence`, for a different property |
| [03b · `fact_coverage`](03b-plugin-fact_coverage.md) | The wider citation set that usually subsumes this one |
| [05 · Evaluator](05-Evaluator.md) | `context_corroborated` / `context_single_sourced` |
| [06 · Builder and Metrics](06-Builder-and-Metrics.md) | The evidence union these citations feed, and why it is the unit's only live effect |
