# Coverage and Missing

*Layer 2 · [context/situations.py:165–175](../../../genios_engine/context/situations.py) + [context/domain_spec.py](../../../genios_engine/context/domain_spec.py)*

> **How complete is this picture, what exactly is missing from it — and why does knowing
> less never make what we do know less true?**

| | |
|---|---|
| **Files** | [context/situations.py](../../../genios_engine/context/situations.py) — `coverage_score`, and the field-gathering inside `refresh_situations` |
| | [context/domain_spec.py](../../../genios_engine/context/domain_spec.py) — 176 lines, the registry of what each domain expects to know |
| **Owns** | `coverage_score` · `DomainSpec.fields_for` · `generic_spec` · `spec_version` |
| **Persisted to** | `context_situations.coverage` (int) and `.missing` (jsonb array of strings) |
| **Never touches** | `confidence_overall`. That is the entire point of this document |
| **Tests** | `test_missing_information_never_lowers_confidence` · `test_the_gaps_are_named_in_plain_language` · `test_a_type_with_no_expectations_is_fully_covered` · `test_coverage_looks_at_the_whole_situation_not_just_the_anchor` |

---

## 1 · The distinction this file exists to protect

**Correctness** and **completeness** are different questions, and folding them together
produces a number that means neither.

> Not knowing a deal's close date does not make the stage we DO know less true.

That sentence appears four times in the codebase — in the `situations.py` module docstring,
in the `coverage_score` docstring, in migration
[`0038_l2_situations.sql`](../../../migrations/0038_l2_situations.sql), and in the `_shape`
helper of [api/situation_routes.py](../../../genios_engine/api/situation_routes.py). It is
repeated because the mistake it prevents is so easy to make.

If coverage were folded into `overall`, then a deal where we know the stage, the amount and
the next step but **not** the close date would be reported as *less trustworthy* than one
where we know all four. It is not less trustworthy. It is less complete. A reader who
conflates the two will chase the wrong fix: they will go looking for corroborating evidence
when what they actually need is a CRM field filled in.

The rule generalises to a principle the whole codebase keeps:

> **Absence is never negative evidence.**

Layer 1 keeps it with its readiness predicates (*"no calendar connected"* must never read as
*"no meeting was booked"*). `health.py` keeps it with `_ratio_score` returning
`(100, False)` for an empty graph. `node_lifecycle` keeps it by returning `active` for an
entity with no dated evidence. `freshness_score` keeps it with its `known` flag. And this
file keeps it by putting coverage **outside** `overall`.

---

## 2 · `coverage_score` — the whole function

```python
# situations.py:165
def coverage_score(*, present_fields: set[str],
                   expected: dict[str, str]) -> tuple[int, list[str]]:
    """How complete the picture is, and the plain-language names of what is missing.

    Reported beside confidence, never inside it: not knowing a close date does not make
    the stage we do know less true.
    """
    if not expected:
        return 100, []
    missing = [label for f, label in sorted(expected.items()) if f not in present_fields]
    known = len(expected) - len(missing)
    return int(round(100 * known / len(expected))), missing
```

Four lines, three decisions.

### Decision 1 — no expectations means 100%, never 0%

```python
if not expected:
    return 100, []
```

*"We expect nothing, so nothing is missing"* — **not** *"we know nothing"*. This is the
guard that keeps a brand-new domain from looking broken on the day it is added.
[domain_spec.py](../../../genios_engine/context/domain_spec.py) calls it out as the trap:

> A registry that returns "no expectations" as "nothing known" would report every situation
> in a new domain as completely uncovered — absence read as negative evidence… It would make
> every new domain look broken on the day it was added.

```python
# tests/test_situations.py:158
def test_a_type_with_no_expectations_is_fully_covered() -> None:
    score, missing = coverage_score(present_fields=set(), expected={})
    assert (score, missing) == (100, [])
```

Note the shortcut also avoids `ZeroDivisionError` on `100 * known / 0` — but that is a
side-effect, not the reason. The reason is semantic.

### Decision 2 — the output is a list of **labels**, not field names

`expected` is `{fact_field: plain-language label}`. The returned `missing` list carries the
**labels**, so a caller never has to know that "whose turn it is" is spelled
`thread.ball_in_court`:

```python
# tests/test_situations.py:150
def test_the_gaps_are_named_in_plain_language() -> None:
    _, missing = coverage_score(present_fields={"deal.stage"},
                                expected={"deal.stage": "pipeline stage",
                                          "deal.close_date": "expected close date"})
    assert missing == ["expected close date"]
```

That list is persisted verbatim into `context_situations.missing` and handed straight to the
API consumer. It is the only human-facing string this quality engine produces.

### Decision 3 — ordering is by field key, not by label

`sorted(expected.items())` sorts on the **field name**, then emits the label. So the
`missing` list for a `deal` reads in field order, which is not alphabetical by label:

| sort position | field (sorted) | label emitted |
|---:|---|---|
| 1 | `commitment.due_at` | agreed next step |
| 2 | `deal.amount` | deal value |
| 3 | `deal.close_date` | expected close date |
| 4 | `deal.stage` | pipeline stage |

The ordering is **stable and deterministic**, which is what matters — the same inputs always
produce the same `missing` array, so the persisted jsonb does not churn between refreshes.
It is simply not sorted the way a reader might expect. Sorting by label instead would be a
one-word change with no other consequence.

### The rounding, and its one surprise

`int(round(100 * known / len(expected)))` uses Python 3's **banker's rounding** — exact `.5`
goes to the nearest *even* integer, not always up.

| known / expected | exact | stored |
|---|---:|---:|
| 1 / 4 | 25.0 | 25 |
| 1 / 3 | 33.33… | 33 |
| 2 / 3 | 66.67… | 67 |
| **1 / 8** | **12.5** | **12** ← rounds *down* |
| **3 / 8** | **37.5** | **38** ← rounds *up* |
| **5 / 8** | **62.5** | **62** ← rounds *down* |

No registered spec has 8 expected fields today (the largest is `deal`, with 4), so the case
is unreachable in practice. It is documented because a future domain with 8 fields would
produce a coverage number that looks off by one and has no other explanation.

---

## 3 · Where `expected` comes from — the domain registry

```python
# situations.py:355
stype    = situation_type(corr.anchor_type, corr.domain)
expected = spec_for(corr.domain).fields_for(stype)
```

Two lookups, both through [domain_spec.py](../../../genios_engine/context/domain_spec.py),
neither of which can raise:

```python
# domain_spec.py:57
def type_for(self, anchor_type: str) -> str:
    return self.situation_types.get(anchor_type) or f"{self.domain}_{anchor_type}"

def fields_for(self, situation_type: str) -> dict[str, str]:
    return self.expected_fields.get(situation_type, {})
```

```python
# domain_spec.py:94
def spec_for(domain: str | None) -> DomainSpec:
    """NEVER raises and never returns None — an unknown domain is an ordinary case."""
    name = (domain or "").strip().lower() or "general"
    return _SPECS.get(name) or generic_spec(name)
```

### The four registered specs, in full

These are the shipped placeholders. They are **data, not logic**, and they exist so that
behaviour was unchanged the day `domain_spec.py` landed.

| domain | anchor type → situation type | situation type | expected field | label |
|---|---|---|---|---|
| **sales** | `deal` → `deal` | `deal` | `deal.stage` | pipeline stage |
| | `company` → `opportunity` | | `deal.amount` | deal value |
| | `person` → `prospect_relationship` | | `deal.close_date` | expected close date |
| | | | `commitment.due_at` | agreed next step |
| | | `opportunity` | `thread.ball_in_court` | whose turn it is |
| | | | `commitment.due_at` | agreed next step |
| | | `prospect_relationship` | `thread.ball_in_court` | whose turn it is |
| **support** | `company` → `support_case` | `support_case` | `thread.ball_in_court` | whose turn it is |
| | `person` → `support_contact` | `support_contact` | `thread.ball_in_court` | whose turn it is |
| **admin** | `company` → `account_admin` | `account_admin` | `subscription.current_period_end` | renewal date |
| **general** | `company` → `relationship` | `relationship` | `thread.ball_in_court` | whose turn it is |
| | `person` → `relationship` | | | |

**Only four distinct fact fields are ever checked** across all four domains:
`deal.stage`, `deal.amount`, `deal.close_date`, `commitment.due_at`,
`thread.ball_in_court`, `subscription.current_period_end` — six, and the constraint on the
list is stated in the dataclass:

> Only fields something in the system actually produces belong here; checking for fields
> nothing writes yields a report that is always right and never useful.

That constraint is why `deal.close_date` is worth a second look: nothing in
`genios_engine/context/` writes it today except the structured CRM lane. On a tenant with no
CRM connected, every `deal` situation reports "expected close date" missing forever — which
is *correct*, and is exactly the honest answer coverage exists to give. The failure mode the
constraint warns about is a field **no code path anywhere** can produce; that is a different
thing.

### An unregistered domain is not an error

```python
# domain_spec.py:64
def generic_spec(domain: str) -> DomainSpec:
    """The spec for a domain nobody has described yet. Fully functional, not degraded."""
    return DomainSpec(domain=domain, display_name=domain.replace("_", " ").title())
```

A `generic_spec` has **no** `situation_types` and **no** `expected_fields`. Consequences:

| Derived value | For `domain="engineering"`, `anchor_type="company"` |
|---|---|
| `situation_type` | `"engineering_company"` — visibly unmapped, never mislabelled |
| `expected` | `{}` |
| `coverage` | **100** |
| `missing` | `[]` |

```python
# tests/test_situations.py:50
def test_an_unmapped_combination_stays_visibly_unmapped() -> None:
    assert situation_type("company", "engineering") == "engineering_company"
```

The test's own docstring says why the fallback is not a generic bucket: *"Falling back to a
generic bucket would file a situation as something it is not, and the missing-information
report would then check the wrong fields."* An `engineering_company` filed as an
`opportunity` would be measured against `thread.ball_in_court` and `commitment.due_at` — a
completeness report about the wrong domain.

---

## 4 · `present_fields` — the bug that made this detector useless

This is the most instructive part of the file, and it is bug **#7** in
[`Rohit_Updates/Layer 2.md`](../../../Rohit_Updates/Layer%202.md):

> **Missing-info was always right, never useful.** Checked facts on the anchor entity — but
> *"whose turn it is"* lives on **people**, so every company situation reported it missing
> forever.

### What was wrong

A situation is anchored on **one node**. For `("company", "sales")` the anchor is the
company. The obvious implementation reads that node's active facts and asks which expected
fields are present:

```python
node_facts = facts_by_node.get(corr.anchor_node_id, {})   # only the anchor
present_fields = set(node_facts)                          # ← the bug
```

But `thread.ball_in_court` and `commitment.due_at` are **written to person nodes**, not to
companies — see [pipeline.py:540–575](../../../genios_engine/context/pipeline.py), where the
commitment dual-write attaches `commitment.due_at` to a person (and now also to a commitment
node). A company-anchored `opportunity` expects exactly those two fields and can never hold
either.

**Result:** every opportunity in every tenant reported `coverage = 0` and
`missing = ["agreed next step", "whose turn it is"]`, permanently, no matter how complete the
picture actually was. A detector that is always right and never informative — which the
module docstring names as the exact failure it warns about.

### The fix — coverage asks what the SITUATION knows

`refresh_situations` runs a second query that gathers every field established by **any event
in this correlation**, wherever the fact landed:

```sql
-- situations.py:323
select distinct m.correlation_id, f.field
from context_correlation_members m
join graph_facts f on f.org_id = m.org_id
  and f.created_by_event_id = m.event_id
where m.org_id = :o and f.valid_to is null and f.status = 'active'
```

and unions it with the anchor's own facts:

```python
# situations.py:365
present_fields=set(node_facts) | fields_by_correlation.get(corr.correlation_id, set()),
```

The comment in the code states the principle:

> Coverage asks what **THIS SITUATION** knows, not what one node holds.

Both halves are needed and neither is redundant:

| Source | Catches |
|---|---|
| `set(node_facts)` — the anchor's active facts | Facts on the anchor that were written by an event **outside** this correlation (a structured CRM sync that landed before the correlation opened) |
| `fields_by_correlation` — facts created by this correlation's events | Facts this situation's own evidence established **on other nodes** — the person's `thread.ball_in_court`, the commitment's `due_at` |

The join key is `graph_facts.created_by_event_id = context_correlation_members.event_id`.

> **⚠️ The index this join needs does not exist.** Bug **#15** in `Layer 2.md`, verified
> against every migration: *"No index on `graph_facts.created_by_event_id` — it exists in no
> migration. Fine when the join ran once per drain; not fine now it runs per API request."*
> `refresh_situations` runs this as one org-wide bulk query per drain, so the cost is one
> sequential scan of `graph_facts` per refresh, not one per situation. Acceptable today,
> and the first thing to fix when a tenant gets large.

The test is a source-text assertion, because there is no database in the test suite:

```python
# tests/test_situations.py:313
def test_coverage_looks_at_the_whole_situation_not_just_the_anchor() -> None:
    source = inspect.getsource(refresh_situations)
    assert "fields_by_correlation" in source
    assert "set(node_facts) | fields_by_correlation" in source
```

It pins the prose rather than the behaviour. That weakness is systemic in Layer 2 and is
[`Layer 2.md` Part 5 item 2](../../../Rohit_Updates/Layer%202.md): a test Postgres in CI would
convert ~40 assertions like this one into real behavioural tests.

---

## 5 · Worked example — an Acme opportunity, before and after

**Setup.** A `("company", "sales")` correlation → `situation_type = "opportunity"`.
`expected = {"thread.ball_in_court": "whose turn it is", "commitment.due_at": "agreed next step"}`.

The correlation has four member events. One of them — an email from John at Acme — produced
`thread.ball_in_court = "us"` **on John's person node**, not on the Acme company node.

### With the old anchor-only logic

| Step | Value |
|---|---|
| `node_facts` (Acme company) | `{"company.domain": "acme.io", "company.size": "200"}` |
| `present_fields` | `{"company.domain", "company.size"}` |
| `missing` | `["agreed next step", "whose turn it is"]` |
| `known` | `2 − 2 = 0` |
| **`coverage`** | `round(100 × 0 / 2)` = **0** |

Reported: *"We know nothing about this opportunity."* We knew whose turn it was.

### With the shipped logic

| Step | Value |
|---|---|
| `node_facts` (Acme company) | `{"company.domain", "company.size"}` |
| `fields_by_correlation["corr_…"]` | `{"thread.ball_in_court", "email.subject", "person.title"}` |
| `present_fields` (union) | `{"company.domain", "company.size", "thread.ball_in_court", "email.subject", "person.title"}` |
| `sorted(expected.items())` | `commitment.due_at` → present? **no** · `thread.ball_in_court` → present? **yes** |
| `missing` | `["agreed next step"]` |
| `known` | `2 − 1 = 1` |
| **`coverage`** | `round(100 × 1 / 2)` = **50** |

Reported: *"Half the picture. What is missing is an agreed next step."* That is a sentence
someone can act on.

### And the confidence, unchanged in both cases

```python
# tests/test_situations.py:138
def test_missing_information_never_lowers_confidence() -> None:
    complete = _score(present_fields={"deal.stage", "deal.amount"},
                      expected_fields={"deal.stage": "stage", "deal.amount": "value"})
    sparse   = _score(present_fields=set(),
                      expected_fields={"deal.stage": "stage", "deal.amount": "value"})
    assert sparse.coverage < complete.coverage      # 0   vs 100
    assert sparse.overall  == complete.overall      # 90  ==  90
```

`_score`'s defaults are `event_count=5, source_count=2, last_seen_at=1 day ago`, so both
situations score `evidence=90, freshness=100, consistency=100, identity=100` →
`overall = 90`. **Coverage moved 100 points and `overall` moved zero.** That is the invariant
this whole document is about, and it is one assertion.

---

## 6 · `spec_version` — why coverage carries a registry fingerprint

`situation_type`, `coverage` and `missing` are all **derived from the registry and then
persisted**. Change a spec and the next refresh silently rewrites stored values, with nothing
in the row recording that *the definition* moved rather than *the world*.

```python
# domain_spec.py:102
def spec_version() -> str:
    from genios_engine.platform.canonical import stable_id
    return stable_id("dspec", {name: asdict(spec)
                               for name, spec in sorted(_SPECS.items())})
```

A content hash of the entire registry, stamped into every situation's `inputs` as
`domain_spec_version`. Two consequences:

1. A change in `missing` or `coverage` between two refreshes is **attributable**. If
   `domain_spec_version` also changed, the definition moved; if it did not, the data moved.
2. `sorted(_SPECS.items())` makes the hash independent of import order — which matters
   because `register()` is a mutable module-level dict and Layer 3 is expected to call it at
   import time. Without the sort, *"two workers with different import order could write
   different types for the same situation"* (the docstring's own words).

### The `register()` seam

```python
# domain_spec.py:74
def register(spec: DomainSpec, *, replace_existing: bool = True) -> DomainSpec:
    """Layer 3 calls this. Overwriting is allowed and is the point: the built-in specs
    below are placeholders that real domain expertise should replace, and a registry that
    refused would force Layer 2 to be edited to remove them first."""
```

Adding "engineering" is a `register()` call from Layer 3. **Zero changes to Layer 2.**
Until that call exists, an engineering situation is typed `engineering_company` and reports
100% coverage — visibly unmapped, working, and honest.

---

## 7 · The persisted shape and the read surface

```sql
-- 0038_l2_situations.sql
coverage       int,
missing        jsonb not null default '[]',   -- plain-language names of the gaps
```

```python
# api/situation_routes.py:60
# Completeness, reported apart from confidence on purpose: not knowing a close
# date does not make the stage we DO know less true.
"coverage": row["coverage"],
"missing": row["missing"] or [],
```

Note the sibling position in the JSON body — `coverage` and `missing` are **not** inside the
`confidence` object:

```json
{
  "situation_id": "sit_…",
  "type": "opportunity",
  "confidence": { "overall": 90, "evidence": 90, "freshness": 100,
                  "consistency": 100, "identity": 100 },
  "coverage": 50,
  "missing": ["agreed next step"]
}
```

The shape of the response is itself the argument. A consumer that wanted to average them
would have to reach across two keys to do it.

---

## 8 · Edge cases

| Case | Behaviour |
|---|---|
| Unregistered domain | `coverage = 100`, `missing = []`, type is `<domain>_<anchor>` |
| Registered domain, unmapped anchor type (`("meeting", "sales")`) | type is `sales_meeting`; `fields_for("sales_meeting")` → `{}` → `coverage = 100` |
| `domain` is `None` or empty | `spec_for` falls back to `"general"`, which **is** registered — so a nameless domain gets `relationship` and one expected field |
| All expected fields present | `coverage = 100`, `missing = []` — identical output to "nothing expected". The two are indistinguishable in the persisted row; only `inputs["domain_spec_version"]` and the situation type tell them apart |
| A fact exists but is `superseded` or has `valid_to` set | Not counted — both queries filter `valid_to is null and status = 'active'`. A field whose only value was overwritten by a *historical* write still counts, because the held active row remains |
| A fact exists on a node that was later merged away | `merge.py` repoints `context_situations.anchor_node_id` (`_NODE_REFERENCES` includes it) and the facts move with the survivor, so coverage follows the surviving entity |

---

## 9 · See also

* [01 · The Confidence Vector](01-Confidence-Vector.md) — the four dimensions coverage is deliberately not one of
* [04 · Graph Health Metrics](04-Graph-Health-Metrics.md) — the same "nothing measured ≠ zero" rule at graph scale
* [`Rohit_Updates/Layer 2.md`](../../../Rohit_Updates/Layer%202.md) — bugs #7 (anchor-only coverage), #13 (domain knowledge inside Layer 2), #15 (the missing index)
