# 01 · Anchoring — what a situation is *about*

*One question: given the entities an event touched, which situations does it belong to?*

> **The key is `(counterparty entity, domain)`.** Everything else in this engine — generations,
> threads, both lanes — exists to make that key land on the right entity.

---

## §1 · What it is for

An event touches entities. An inbound email from `john@acme.io` touches John (a person), Acme (a
company built from the sender's domain), possibly a deal, possibly a project someone named in the
prose. **Anchoring picks which of those the situation is filed under.**

Get it wrong in one direction and every conversation is duplicated at two levels, and every count
in the product doubles. Get it wrong in the other and the entire company collapses into one
situation containing everything. Both of those were real, and both are now fixed by code you can
point at.

---

## §2 · What exists

| Symbol | File | Role |
|---|---|---|
| `ANCHOR_PRIORITY` | `correlation.py:81` | the tier order, strongest first |
| `_anchor_priority()` | `correlation.py:76` | builds it by importing Layer 1's vocabulary |
| `Anchor` | `correlation.py:87` | frozen dataclass — `(node_id, node_type, domain)` |
| `Anchor.base_key` | `correlation.py:95` | the situation's identity **across** generations |
| `resolve_domain()` | `correlation.py:103` | L1's hint list → one domain string |
| `choose_anchors()` | `correlation.py:118` | node types + domain → the list of anchors |
| `DEFAULT_DOMAIN = "general"` | `correlation.py:64` | the resting place for uncategorised text |

---

## §3 · How it works

### 3.1 · The priority list is imported, not restated

```python
def _anchor_priority() -> tuple[str, ...]:
    from genios_engine.capture.internal_knowledge import ANCHORING_KINDS
    return ("deal", *sorted(ANCHORING_KINDS), "company", "person")

ANCHOR_PRIORITY: tuple[str, ...] = _anchor_priority()
```

`capture/internal_knowledge.py:67` declares `ANCHORING_KINDS = frozenset({"project"})`, so the
value at runtime is exactly:

```python
('deal', 'project', 'company', 'person')
```

| Tier | Why it is where it is |
|---|---|
| `deal` | the business object **itself**. Nothing is more specific than the thing being sold |
| `project` | comes from Layer 1's canon vocabulary. A named project is more specific than the company it belongs to — *"the Phoenix migration"* must not be filed under *"Acme"* alongside the renewal |
| `company` | people change companies; a company outlives them |
| `person` | last resort. A freelancer or a personal Gmail address still deserves a situation |
| *anything else* | **cannot anchor.** A meeting, a document, a commitment **describes** a situation; it is not one |

Two properties fall out of the import:

* **Adding an anchoring kind is one edit in one file.** Layer 1 owns the canon vocabulary because
  Layer 1 owns provenance; L2 honours it. Importing L1 from L2 is the legal direction.
* **`sorted(ANCHORING_KINDS)` is not decoration.** A `frozenset` has no order, so without `sorted`
  the priority tuple would depend on Python's hash seed and the same email could anchor differently
  between two processes.

`ANCHORING_KINDS` holds only `project` out of Layer 1's twelve `INTERNAL_KINDS`. The line is not
importance — a pricing policy may matter more than any single project — it is **whether other
signals cluster around it.** A refund policy is true continuously; it is not something *happening*.
Letting every policy, price list and wiki page open its own situation would bury the handful that
need attention under a filing cabinet. `task` is deliberately excluded too: one situation per to-do
item would swamp the same list, and nothing downstream ranks at that granularity
(`internal_knowledge.py:56-67`).

### 3.2 · `resolve_domain` — the first hint wins

```python
for hint in domain_hints or []:
    domain = hint.get("domain") if isinstance(hint, dict) else getattr(hint, "domain", None)
    if domain:
        return str(domain)
return DEFAULT_DOMAIN
```

The hints are Layer 1's, computed at ingestion and persisted on `source_events.domain_hints`
(`capture/pipeline.py:186`). They are deterministic and there is **no model in the path**:

| Hint kind | Source | Value |
|---|---|---|
| source prior (`source="scope"`) | `capture/domain/hints.py:_SOURCE_PRIOR` | `hubspot`/`salesforce` → `sales`, `zendesk`/`intercom` → `support`, `stripe`/`razorpay` → `admin` |
| keyword (`source="keyword"`) | `capture/domain/hints.py:_KEYWORDS` | `sales`: deal, pricing, proposal, contract, quote, demo, budget, renewal · `support`: issue, error, broken, ticket, down, outage, bug, not working · `admin`: invoice, payment, overdue, gst, compliance, legal, tds, filing |

L1 appends the source prior **first**, then keyword matches in the dict's literal order
(`sales`, `support`, `admin`), so *"the first hint is the most trustworthy"* is a true statement
about the producer, not an assumption. Taking the first is what makes the choice deterministic
instead of alphabetical or dict-ordered — an email hitting two keywords must correlate the same way
on every replay (`test_the_strongest_hint_wins`).

`resolve_domain` accepts both dicts (how the hints come back out of JSON in `source_events`) and
objects (`contracts.gated_event.DomainHint`, how they exist in memory in Layer 1). Both shapes are
handled in one line because both shapes really occur.

**No hint is a bucket, not an error.** Most email lands in `general`, and that is fine: threads keep
real conversations together, so `general` is a resting place for the genuinely uncategorised rather
than a dumping ground for everything.

### 3.3 · `choose_anchors` — only the strongest available tier

```python
for node_type in ANCHOR_PRIORITY:
    at_tier = sorted(nid for nid, ntype in node_types.items() if ntype == node_type)
    if at_tier:
        return [Anchor(node_id=nid, node_type=node_type, domain=domain) for nid in at_tier]
return []          # nothing anchored — the event stands alone, which is a real answer
```

Three rules, all load-bearing:

1. **First non-empty tier wins, and the loop returns.** An email to a person *at* a company yields
   **one** company-anchored situation, not a company one *and* a person one. Anchoring at both
   tiers would duplicate every conversation and double every count
   (`test_only_the_strongest_tier_anchors`).
2. **Every node at that tier anchors.** An introduction email naming two companies genuinely
   belongs to two situations, and dropping one loses a real relationship
   (`test_an_intro_naming_two_companies_creates_two_situations`).
3. **`sorted(...)` makes it order-independent.** Dict iteration order must never decide which
   situation an event lands in (`test_anchoring_is_order_independent`).

Returning `[]` is a **first-class outcome**, not a failure. A newsletter, an automated alert, a note
about no one: inventing a group here would fill the graph with situations about nobody
(`test_nothing_anchored_is_a_real_answer`).

### 3.4 · `base_key` — the identity across generations

```python
@property
def base_key(self) -> str:
    return stable_id("corr", {"node": self.node_id, "domain": self.domain})
```

`platform/canonical.py:120` defines `stable_id(prefix, value) = f"{prefix}_{sha256(canonical_dumps(value))}"`,
and `canonical_dumps` sorts keys, drops whitespace and forbids NaN. So the hash input for
`node_7f3a` in `sales` is literally the string:

```
{"domain":"sales","node":"node_7f3a"}
```

and the real output is:

```
base_key = corr_0fcceab00bf16c1af963252a425473828b9b63871ee2f91bb43cc0062aff25cd
```

The generation number is **not** in `base_key` — `find_or_open` adds it separately when minting the
`correlation_id` (see [02 · Time Windows and Generations](02-Time-Windows-and-Generations.md)). That
is deliberate: a restarted conversation becomes a **sibling** of the old one rather than a stranger,
which is what keeps the history findable.

Worked pairs, computed from the real function:

| Node | Domain | `base_key` |
|---|---|---|
| `node_7f3a` | `sales` | `corr_0fcceab0…25cd` |
| `node_7f3a` | `support` | `corr_6b931678…eb9f` |
| `node_9c11` | `sales` | `corr_4c33eec2…13b6` |

Same node, different domain → different key. *Acme's renewal and Acme's outage are not one problem*
(`test_the_same_entity_in_two_domains_is_two_situations`). Same node and domain → identical key,
every time, on every replay (`test_the_same_entity_and_domain_is_one_situation`).

---

## §4 · Why our own company is excluded

**This was bug #1 of Layer 2, and it would have destroyed the feature silently.**

Sending mail creates a company entity from *your own* domain — `_works_at` in `pipeline.py:284`
derives a company node from every participant's email domain, including your own seats. Without an
exclusion, **every outbound email in the tenant would anchor on your own company**, filing the
entire business into one enormous situation containing everything. Correlation would appear to be
working — high reach, big groups — while telling you nothing.

The exclusion is built in **three different places, because there are three lanes**:

### Extraction lane — `pipeline.py:271-298`

```python
touched: dict[str, str] = {}
internal_nodes: set[str] = set()

def _person(email: str) -> str:
    ...
    touched[node] = "person"
    if key in internal_set:
        internal_nodes.add(node)

def _works_at(email: str, person_node: str) -> None:
    ...
    touched[company] = "company"
    # A company reached through one of OUR OWN seats is us, not a counterparty.
    if (_norm_email(email) or "") in internal_set:
        internal_nodes.add(company)
```

and at the call site (`pipeline.py:589`):

```python
node_types={n: t for n, t in touched.items() if n not in internal_nodes}
```

Note what is *not* excluded: the node, its facts, its edges and its observations are all still
written. **Only the grouping is skipped.** `internal_set` is the tenant's own seat emails, read once
per drain from `org_seats` (`runner.py:_internal_emails`), not once per event.

Pinned by `test_our_own_company_never_anchors_a_situation`, which asserts that
`process_event`'s source contains both `internal_nodes` and `if n not in internal_nodes`.

### Structured lane — `structured.py:81-89`

```python
internal = internal_emails or frozenset()
touched = {node: node_type}
for rel in (relations or []):
    key = (rel.get("canonical_key") or "").strip().lower()
    if rel["node_type"] == "person" and key in internal:
        continue
    ...
```

A calendar invite lists **us** as attendees. Anchoring on our own people would file every meeting in
the company into one enormous situation (`test_our_own_attendees_never_anchor_a_meeting`).

### Backfill lane — `backfill.py:120-122`

```python
if (row.canonical_key or "").lower() in internal:
    continue                       # our own people never anchor a situation
```

> **⚠️ The backfill's exclusion is weaker than the live path's, and it is a real gap.** `internal`
> here is a set of **seat email addresses**. A person node's `canonical_key` is an email, so people
> are excluded correctly. A **company** node's `canonical_key` is a bare domain (`kurral.com`) and
> can never equal an email address — so the company node built from your own domain is **not**
> filtered out during a backfill. It anchors for whichever historical events created it or wrote
> facts on it. Detailed, with scope, in [06 · Known Limitations](06-Known-Limitations.md).

---

## §5 · Worked examples

Real calls, real return values. `d = "sales"` in all rows.

| `node_types` | anchors returned | why |
|---|---|---|
| `{"n_person": "person", "n_company": "company"}` | `[n_company]` | strongest tier only |
| `{"n_deal": "deal", "n_company": "company", "n_person": "person"}` | `[n_deal]` | the deal *is* the business object |
| `{"n_person": "person"}` | `[n_person]` | a freelancer still deserves a situation |
| `{"n_a": "company", "n_b": "company"}` | `[n_a, n_b]` | an intro email is genuinely two relationships |
| `{"n_b": "company", "n_a": "company"}` | `[n_a, n_b]` | sorted — insertion order changes nothing |
| `{"n_doc": "document", "n_meeting": "meeting"}` | `[]` | neither describes *what the situation is about* |
| `{}` | `[]` | a newsletter, an alert, a note about no one |
| `{"node_sub": "subscription"}` | `[]` | **see the edge case below** |

Verified live against the module:

```python
>>> plan_correlation(thread_correlation_ids=[],
...     node_types={"n_person": "person", "n_company": "company", "n_doc": "document"},
...     domain_hints=[{"domain": "sales", "source": "scope"}, {"domain": "support"}])
CorrelationPlan(anchors=(Anchor(node_id='n_company', node_type='company', domain='sales'),),
                via='anchor', inherited_correlation_ids=())
```

---

## §6 · Edge cases worth knowing

**Node types the structured lane produces that can never anchor.** The mapping registry
(`capture/structured/registry.py`) declares four `node_type`s: `deal`, `subscription`, `meeting`,
`product_account`. Only `deal` is in `ANCHOR_PRIORITY`. `meeting` recovers because the calendar
mapping declares attendee relations, and those people lift to companies. **`subscription` (Stripe)
and `product_account` (the client's own database) declare no relations at all** — so `touched` is
`{node: "subscription"}`, `choose_anchors` returns `[]`, and those events correlate to **nothing,
ever**. This is a real coverage hole, recorded in [06](06-Known-Limitations.md).

**A canon node anchors only if its kind is anchoring.** `pipeline.py:323` writes
`touched[canon_node] = internal_kind` — the raw kind string, not a placeholder. So a `project`
document anchors (it is in `ANCHOR_PRIORITY`) and a `policy` document does not. The type is carried
through rather than invented precisely because correlation anchors on **type**: a placeholder here
would resolve the mention correctly and then anchor nothing — built, green, and silently inert
(`pipeline.py:431-433`).

**A company mention in prose reuses the existing node.** `pipeline.py:405-413`: when the extractor
names "Acme" and `resolve_company_mention` finds the node already built from `acme.io`, the mention
adds `touched[known] = "company"` and creates **no** new node. The anchor rule holds rather than
bends.

**Personal email domains never become companies.** `_company_domain` returns `None` for gmail.com,
outlook.com and the rest of `_PERSONAL_DOMAINS`, so a 1:1 with a personal address anchors on the
**person** — the correct answer, and the reason the `person` tier exists at all.

---

## §7 · The tests that hold this shape

| Test (`tests/test_correlation.py`) | Property |
|---|---|
| `test_the_strongest_hint_wins` | first hint, deterministic |
| `test_no_hint_is_a_bucket_not_an_error` | `[]` and `None` → `general` |
| `test_only_the_strongest_tier_anchors` | no double-filing |
| `test_a_deal_outranks_its_company` | two deals at one customer do not collapse |
| `test_a_person_anchors_when_there_is_no_company` | the last-resort tier works |
| `test_an_intro_naming_two_companies_creates_two_situations` | same-tier fan-out |
| `test_anchoring_is_order_independent` | `sorted` is load-bearing |
| `test_nothing_anchored_is_a_real_answer` | `[]` for docs/meetings/empty |
| `test_the_same_entity_in_two_domains_is_two_situations` | domain is part of the key |
| `test_the_same_entity_and_domain_is_one_situation` | key stability |
| `test_our_own_company_never_anchors_a_situation` | ⚠️ **source-text assertion** on `process_event` |
| `test_our_own_attendees_never_anchor_a_meeting` | ⚠️ **source-text assertion** on `commit_structured` |

The two marked tests assert on the *text* of the function, not its behaviour — a consequence of
there being no database in the test suite. They pin prose, and a refactor that preserved the
behaviour while renaming `internal_nodes` would fail them. That is a known weakness of the whole
Layer 2 suite, not of this rule.
