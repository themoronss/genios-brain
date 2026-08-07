# 03b · Plugin `owner_availability` — `OwnerAvailabilityPlugin`

**Symbol:** `resource_unit.py:OwnerAvailabilityPlugin` (lines 86–145)
**`plugin_id`:** `owner_availability` — second in `plugin_id` order
**Emits:** `resource.owner_unassigned` **or** `resource.owner_availability` — 0 or 1 observation per run
**Sole publisher of:** `capacity_bp`

---

## 1 · The claim it makes

> *Is there a named human, and is that human actually available?*
>
> *Capacity in a services business is a person before it is a budget line. Two distinct claims live
> here because they are answered by different facts: nobody owns this — an assignment gap the
> organisation can close in seconds — and the owner is away, a gap only time closes.*

Two failures, one plugin, because they are the same question asked at two depths and they are
mutually exclusive: you cannot be unavailable if you do not exist. The plugin resolves the depth
first — is there anybody? — and only then asks how available that person is.

The distinction is not decorative. *Nobody owns this* is fixed by an assignment in a CRM; *the owner
is on leave* is fixed by waiting or by reassigning, which is a different conversation with different
stakes. Emitting them under one `kind` would collapse two different remedies into one number.

---

## 2 · When it stays silent

```python
owner_captured = "deal.owner" in request.context.facts
owner = str(fact_value(request, "deal.owner") or "").strip()
if owner_captured and not owner:
    return (Observation(kind="resource.owner_unassigned", metrics={"capacity_bp": 0}, ...),)
availability = self._declared_availability(view)
if availability is None:
    return ()                      # nothing was declared; do not invent an availability
return (Observation(kind="resource.owner_availability",
                    metrics={"capacity_bp": availability}, ...),)
```

| Situation | Emits | Why |
|---|---|---|
| `deal.owner` **key absent** from `context.facts`, no availability facts | `()` | *"An owner field that was never captured is silence, and silence stays silence."* |
| `deal.owner` **key present**, value empty or whitespace or `None` | `resource.owner_unassigned`, `capacity_bp: 0` | *"An empty owner field that Layer 2 did in fact capture is evidence of zero capacity — someone looked and there was no one."* |
| `deal.owner` names someone, no `owner.availability_bp`, no `owner.status` | `()` | an unmeasured owner is not an unavailable one |
| `owner.status` present but not in any of the three vocabularies | `()` | an unrecognised status means *we do not know*, never *available* |
| `owner.availability_bp` present but malformed or out of range | `()` | *"malformed capacity is unknown capacity, never full"* |

The captured-versus-absent distinction is the sharpest silence rule anywhere in the roster, and it
rests on a deliberate difference between two reads of the same field name:

```python
"deal.owner" in request.context.facts       # ← raw key presence: did Layer 2 look?
fact_value(request, "deal.owner")           # ← unwrapped value:   did it find anything?
```

Four tests pin the four silences: `test_an_unmeasured_owner_produces_no_availability_claim`,
`test_an_unrecognised_status_word_is_treated_as_unknown_not_available`,
`test_a_malformed_availability_figure_is_unknown_rather_than_full`, and
`test_an_empty_owner_field_that_was_captured_is_evidence_of_no_executor` for the case that is *not*
silence.

---

## 3 · The arithmetic

There is none. `capacity_bp` is either read directly or looked up in a table — the plugin resolves a
precedence, it does not compute.

```python
def _declared_availability(self, view: UnitView) -> int | None:
    raw = fact_value(view.request, "owner.availability_bp")
    if raw is not None:
        try:
            return basis_points(raw, "owner.availability_bp")
        except ValueError:
            return None
    status = str(fact_value(view.request, "owner.status") or "").strip().lower()
    if status in _AVAILABLE_STATUSES:
        return 10_000
    if status in _REDUCED_STATUSES:
        return _config_bp(view, "owner_reduced_availability_bp", 4_000)
    if status in _UNAVAILABLE_STATUSES:
        return 0
    return None
```

```text
capacity_bp = owner.availability_bp                              if present and 0 ≤ v ≤ 10,000
            = None                                               if present and malformed
            = 10,000                                             if status ∈ AVAILABLE
            = owner_reduced_availability_bp, default 4,000        if status ∈ REDUCED
            = 0                                                  if status ∈ UNAVAILABLE
            = None                                               otherwise
```

**Why the number outranks the label:**

> *A status is a coarse label a CRM applied; a number is what someone measured.*

And, importantly, the precedence is *presence*-based, not *validity*-based: if
`owner.availability_bp` is present but malformed the plugin returns `None` immediately rather than
falling back to the status word. A corrupt measurement must not be quietly replaced by a coarser
guess — the reader is told nothing rather than something derived from a source the system already
knows is broken.

### The three closed vocabularies

Module-level `frozenset`s, lines 44–47:

| Constant | Members | `capacity_bp` |
|---|---|---|
| `_AVAILABLE_STATUSES` | `available`, `active`, `working`, `online`, `in_office` | `10,000` |
| `_REDUCED_STATUSES` | `busy`, `limited`, `partial`, `overloaded`, `stretched` | `owner_reduced_availability_bp`, default **4,000** |
| `_UNAVAILABLE_STATUSES` | `out_of_office`, `ooo`, `on_leave`, `unavailable`, `inactive`, `departed`, `offboarded` | `0` |

> *Read as a closed vocabulary on purpose: an unrecognised status means "we do not know", not
> "available", because guessing availability upward is the failure mode that puts work on someone who
> is on parental leave.*

The default direction of an unknown is the whole safety argument. Every membership test in the chain
is an *opt-in*; the fall-through returns `None`, which the unit reports as *unmeasured* and which the
Evaluator then defaults to `10,000` — no strain — rather than to `0`. So an unknown status word
produces *no capacity claim at all*, and the play proceeds with a `resource_capacity_unknown` WARN
instead of a fabricated shortfall. Unknown fails toward *tell the human*, not toward *block* and not
toward *proceed silently*.

Matching is case-insensitive and whitespace-tolerant: `"  Out_Of_Office "` → `out_of_office` → `0`.
Verified.

---

## 4 · Configuration

| Key | Default | Validator | Effect |
|---|---|---|---|
| `owner_reduced_availability_bp` | **4,000** | `_config_bp` — integer, `0 ≤ v ≤ 10,000`, `bool` rejected | what a `_REDUCED_STATUSES` word is worth |

One key, and its existence is argued:

> *When only the label exists it is mapped conservatively — "busy" is a real reduction, not a rounding
> error, and the reduction is tunable per capability because a busy account manager and a busy surgeon
> are not equally busy.*

`test_a_busy_owner_is_reduced_not_erased_and_the_reduction_is_tunable` runs the same
`{"deal.owner": "dana_whitfield", "owner.status": "busy"}` twice: default → `4,000`, and with
`{"owner_reduced_availability_bp": 1_500}` → `1,500`.

Note what tuning it to `1,500` does downstream: against the default `capacity_floor_bp` of `3,000`,
`1,500 ≤ 3,000` fires `owner_capacity_below_floor`, while `4,000` does not. So this single key decides
whether *busy* is a warning or not, and the two thresholds — `owner_reduced_availability_bp` and
`capacity_floor_bp` — have to be authored together to mean anything coherent. Nothing enforces that
pairing; nothing documents it in the code either.

**It is validated lazily.** `_config_bp` runs only inside the `_REDUCED_STATUSES` branch, so a
manifest carrying `owner_reduced_availability_bp: 20_000` raises nothing until a CRM reports someone
as `busy`. Verified: with no status fact at all, that config produces no error.

The other two vocabularies are **not** tunable. `10,000` for available and `0` for unavailable are
hard-coded, which is defensible for the unavailable end — on leave is on leave — and arguable for the
available end, since a CRM saying `active` is a low-quality signal being read as full capacity.

---

## 5 · Worked examples

### 5.1 · A measured figure beats a label

```text
facts    deal.owner            = "dana_whitfield"
         owner.status          = "available"          ← would map to 10,000
         owner.availability_bp = 2,500                ← wins

_declared_availability
    raw = 2500, not None
    basis_points(2500) → 0 ≤ 2500 ≤ 10000 → 2,500
    status never consulted

Observation resource.owner_availability
            metrics       {capacity_bp: 2500}
            reason_codes  ("owner_availability_declared",)
            evidence_ids  ids for deal.owner, owner.availability_bp, owner.status
```

2,500bp — a quarter of a person. Against the default `capacity_floor_bp` of 3,000 this fires
`owner_capacity_below_floor`, so the same run that a status-only read would have called *fully
available* is instead flagged as thin. That inversion is the point of the precedence:
`test_a_measured_availability_outranks_a_status_label`.

### 5.2 · On leave — Northwind's Dana

```text
facts    deal.owner   = "dana_whitfield"
         owner.status = "out_of_office"

owner_captured  True, owner = "dana_whitfield" → non-empty, no early return
_declared_availability
    owner.availability_bp absent → raw is None
    status "out_of_office" ∈ _UNAVAILABLE_STATUSES → 0

Observation resource.owner_availability
            metrics       {capacity_bp: 0}
            reason_codes  ("owner_availability_declared",)
```

`0 ≤ 3,000` → `owner_capacity_below_floor`. Note the reason code is still
`owner_availability_declared`, not something like `owner_unavailable` — the observation reports *an
availability was declared*, and it is the Evaluator's threshold that decides the declaration is a
problem. `test_an_owner_on_leave_has_no_capacity_at_all` asserts both the metric and the code.

### 5.3 · Nobody assigned

```text
facts    deal.owner = ""

owner_captured  "deal.owner" in facts → True
owner           str("" or "").strip() → ""
→ early return

Observation resource.owner_unassigned
            metrics       {capacity_bp: 0}
            reason_codes  ("no_owner_to_execute",)
            evidence_ids  ids for deal.owner only
```

Same `capacity_bp` as the on-leave case, different `kind`, different reason code, narrower evidence.
The Calculator cannot tell them apart — both fold into `min(capacities)` as `0` — but the `Finding`
carries the `kind` verbatim as its `finding_id`, so a card explaining the shortfall can say *nobody
owns this* rather than *the owner is unavailable*.
`test_an_empty_owner_field_that_was_captured_is_evidence_of_no_executor`.

### 5.4 · Busy, twice

```text
facts    deal.owner = "dana_whitfield", owner.status = "busy"

default config                              → capacity_bp 4,000   → 4,000 > 3,000 → no strain
config owner_reduced_availability_bp: 1,500 → capacity_bp 1,500   → 1,500 ≤ 3,000 → strain
```

### 5.5 · An unrecognised status

```text
facts    deal.owner = "dana_whitfield", owner.status = "sabbatical_q3"

"sabbatical_q3" ∉ AVAILABLE ∪ REDUCED ∪ UNAVAILABLE → None
contribute → ()

unit metrics    capacity_bp absent
evaluate_meaning  metrics.get("capacity_bp", 10_000) = 10,000 → no strain
                  known = False (no capacity_bp, no headroom_bp)
                  → WARN resource_capacity_unknown
```

A person on sabbatical is reported as *unmeasured*, which produces a warning that reaches the human,
rather than as *available*, which would silently assign them work. The vocabulary is closed precisely
so that the unknown lands here. `test_an_unrecognised_status_word_is_treated_as_unknown_not_available`.

Worth stating plainly: this is the *safe* failure, not a *good* one. `sabbatical_q3` clearly means
unavailable to any reader, and the plugin cannot say so. Widening the vocabulary is a code change
with no configuration seam — there is no `unavailable_statuses` config key — so a tenant whose CRM
uses non-standard status words gets a permanently blind capacity reading.

---

## 6 · Edge cases, including one the docstring over-promises

### 6.1 · `capacity_bp` does not require a named human

**Verified.** With `{"owner.availability_bp": 9000}` and **no `deal.owner` at all**:

```text
owner_captured  False → no early return
_declared_availability → 9,000

Observation resource.owner_availability
            metrics      {capacity_bp: 9000}
            evidence_ids ()                       ← nothing to cite
```

The plugin's own docstring asks *"Is there a named human, and is that human actually available?"* and
the code answers only the second half. An availability figure floating free of an owner produces a
full capacity claim attributed to nobody. That is unlikely to arise from a real CRM — availability is
usually captured *about* a person — but nothing in the plugin enforces it, and the observation it
produces cites no evidence at all, which is the tell.

The reverse asymmetry is enforced: a captured-but-empty owner returns early, so
`{"deal.owner": "", "owner.availability_bp": 9000}` yields `resource.owner_unassigned` with
`capacity_bp: 0` and the 9,000 figure is discarded. **Verified.** That direction is right — an
availability reading for a vacancy is meaningless — and it makes the missing check on the other
direction look more like an oversight than a decision.

### 6.2 · Whitespace-only owner is unassigned

`{"deal.owner": "  "}` → `.strip()` → `""` → `resource.owner_unassigned`. **Verified.** A CRM field
containing a space is treated as empty, which is the right reading of a field somebody cleared badly.

### 6.3 · `deal.owner` present with value `None`

`fact_value` returns `None`, `str(None or "")` is `""`, `.strip()` is `""` → `owner_unassigned`. The
`or ""` guard is what makes this work; without it `str(None)` would be `"None"`, a four-character
owner name. A small guard doing real work.

### 6.4 · Non-string owner values

`{"deal.owner": 12345}` → `str(12345).strip()` → `"12345"` → non-empty → treated as a named owner, and
the plugin proceeds to `_declared_availability`. An owner id rather than a name is fine; the plugin
never uses the value for anything except emptiness.

### 6.5 · Boundary values on `owner.availability_bp`

| Input | `basis_points` | Result |
|---|---|---|
| `0` | accepted | `capacity_bp: 0` — a measured zero, distinct from unassigned by `kind` |
| `10000` | accepted | `capacity_bp: 10000` |
| `10001` | `must be between 0 and 10000` | `None` → silent |
| `-1` | rejected | `None` → silent |
| `"2500"` | accepted — `integer` parses a `Decimal`-convertible string | `2,500` |
| `2500.5` | rejected — not integral | `None` → silent |
| `True` | rejected — `integer` rejects `bool` explicitly | `None` → silent. **Verified** |

The `bool` rejection matters more than it looks: `isinstance(True, int)` is `True` in Python, so
without the explicit guard an `owner.availability_bp` of `True` would read as `1bp` — one
ten-thousandth of a person, a near-total shortfall manufactured from a boolean.

### 6.6 · The evidence cited is broader than the evidence used

`evidence_ids(request, "deal.owner", "owner.availability_bp", "owner.status")` is called for the
availability observation regardless of which of the three actually produced the number. A run that
resolved capacity from `owner.status` still cites an `owner.availability_bp` evidence row if one
exists. Over-citation rather than under-citation — the safe direction for an audit trail, but it means
an evidence id on this observation proves the field was captured, not that it was used.

---

## Related

| Document | Covers |
|---|---|
| [03-Analyzer.md](03-Analyzer.md) | How this plugin composes with the other two |
| [04-Calculator.md](04-Calculator.md) | The `min` over `capacity_bp` — with one contributor it is the identity |
| [05-Evaluator.md](05-Evaluator.md) | `capacity_floor_bp`, and why an absent `capacity_bp` defaults to 10,000 |
| [../README.md](../README.md) | Category 3 §4.2 — the three vocabularies as a summary table |
