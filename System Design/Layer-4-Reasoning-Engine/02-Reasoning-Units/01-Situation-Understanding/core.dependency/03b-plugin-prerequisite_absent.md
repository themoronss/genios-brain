# 03b · Plugin `prerequisite_absent`

**Class:** `dependency_unit.py:PrerequisiteAbsencePlugin`
**`plugin_id`:** `prerequisite_absent` — runs **second** in `plugin_id` order

---

## 1 · The claim

*The capability declared it needs a fact to do this work, and the fact is not there.*

> *"A missing prerequisite is a dependency on **retrieval**, not on a person: nobody has refused
> anything, the information simply is not in hand yet. It is reported at direct depth because this
> workflow can go and get it, which is what makes it a materially different blocker from an approver
> who has gone quiet."*

That distinction is the plugin's entire reason for existing separately from `approval_gate`. A
missing signatory email and a stalled legal review both stop the work, but one is an errand and the
other is a negotiation.

---

## 2 · What exists

### 2.1 Where the prerequisite list comes from

```python
declared = _config_fields(view, "prerequisite_fields",
                          tuple(view.request.capability.required_fields))
if not declared:
    return ()
```

Two sources, in priority order:

| Priority | Source | Set by |
|---|---|---|
| 1 | `spec.config["prerequisite_fields"]` | Layer 3, per capability, for this unit |
| 2 | `request.capability.required_fields` | Layer 3, the capability's context requirements |

The fallback rationale: *"Prerequisites come from Layer 3 — either named explicitly for this unit or,
failing that, the capability's own declared `required_fields`. If neither exists the plugin says
nothing: a capability that never stated what it needs has not given us grounds to call anything
missing."*

`_config_fields` dedupes, strips, drops blanks and **sorts**, so the emission order of prerequisite
findings is alphabetical by field name and cannot depend on how the manifest was typed.

### 2.2 Config keys

| Key | Default | Effect |
|---|---|---|
| `prerequisite_fields` | `capability.required_fields` | which fields count as prerequisites |
| `prerequisite_severity_bp` | `5,000` | severity of each absent prerequisite |

Both are read **after** the `if not declared: return ()` guard, so a malformed
`prerequisite_severity_bp` in a capability that declares no prerequisites raises nothing. Verified:
`prerequisite_severity_bp: -5` with an empty declaration returns `()` cleanly.

### 2.3 The two outputs

| `kind` | blocked | inspected | depth | severity_bp | hard | evidence | reason codes |
|---|---|---|---|---|---|---|---|
| `dependency.prerequisite_absent` | 1 | 1 | 1 | config, 5,000 | 0 | **none, ever** | `prerequisite_not_available`, `blocker:<field>` |
| `dependency.prerequisites_met` | 0 | count satisfied | — | — | — | none | `prerequisites_met` |

---

## 3 · How it works

### 3.1 The presence test

```python
for field in declared:
    if field in facts and not _is_absent(fact_value(view.request, field)):
        satisfied += 1
        continue
    observations.append(... dependency.prerequisite_absent ...)
```

Two conditions, both required: the key must exist in `context.facts`, **and** the unwrapped value
must not be an emptiness placeholder.

```python
def _is_absent(value: Any) -> bool:
    """A fact written as null or blank is not a fact. L2 records placeholders; treat them as absent."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (tuple, list, Mapping)) and not isinstance(value, str):
        return len(value) == 0
    return False
```

| Value | `_is_absent` | Result |
|---|---|---|
| key not in `facts` | — | **blocker** |
| `None` | `True` | **blocker** |
| `""`, `"   "` | `True` | **blocker** |
| `()`, `[]`, `{}` | `True` | **blocker** |
| `0` | `False` | satisfied |
| `False` | `False` | satisfied |
| `"2026-09-30"` | `False` | satisfied |
| `{"value": None}` | unwraps to `None` → `True` | **blocker** |
| `{"source": "crm"}` (no `value` key) | `len == 1` → `False` | satisfied |

The last row is a small hole: a fact record that carries provenance but no value satisfies the
prerequisite. `fact_value` only unwraps records containing a literal `"value"` key, so anything else
is treated as the value itself. No shipped Layer 2 writer produces that shape; it is worth knowing
before one does.

`0` and `False` counting as present is correct and deliberate: zero is a value, and the plugin's
question is *do we have the fact*, not *is the fact interesting*.

### 3.2 Depth is always 1

There is no branch. Every absent prerequisite is `DIRECT_DEPTH`, because retrieving a fact is
something this workflow does: query the CRM again, ask the rep, run the enrichment. Nobody outside
has to change their mind first. A prerequisite that genuinely requires an external party to supply
it would be modelled as `blocked_by`, not as an absent field.

### 3.3 Why the satisfied count is aggregated

One `prerequisites_met` row carrying `inspected: N`, not N rows. Same reasoning as the cleared-gates
row: a satisfied prerequisite has no identity worth carrying downstream, only a count, and the count
is what stops `unblocked_bp = 10,000` from being unreadable.

---

## 4 · Worked examples

### 4.1 One declared, one satisfied, one absent

```python
facts = {"deal.renewal_date": "2026-09-30"}
capability.required_fields = ("deal.renewal_date", "deal.signatory_email")
```

```text
declared sorted → ("deal.renewal_date", "deal.signatory_email")

deal.renewal_date    in facts, "2026-09-30" not absent → satisfied = 1
deal.signatory_email not in facts                      → blocker, severity 5,000, depth 1, hard 0

observations:
  dependency.prerequisite_absent  blocked 1 inspected 1 depth 1 severity_bp 5,000 hard 0
                                  evidence_ids ()
                                  codes (blocker:deal.signatory_email, prerequisite_not_available)
  dependency.prerequisites_met    blocked 0 inspected 1
```

Whole-unit result, verified by execution:

```text
severities = [5,000]     depth 1     penalty 0
free       = 10,000 − 5,000 − divide_half_up(0, 4) − 0 = 5,000

matched  True
metrics  blocked_count 1 · blocking_depth 1 · unblocked_bp 5,000
         hard_blocked_count 0 · blocker_severity_bp 5,000 · inspected_count 2
codes    ("prerequisite_not_available",)
finding  dependency.prerequisite_absent.deal.signatory_email
evidence ()                                    ← the unit cites nothing on this run
```

`test_a_declared_prerequisite_that_is_missing_blocks_and_a_present_one_does_not` pins the depth and
the `inspected == 1` on the satisfied row.

### 4.2 Layer 3 naming its own prerequisites

```python
facts  = {"deal.renewal_date": "2026-09-30"}
config = {"prerequisite_fields": ["contract.countersigned_at"]}
capability.required_fields = ("deal.renewal_date",)
```

```text
declared = ("contract.countersigned_at",)      ← config REPLACES the capability list
contract.countersigned_at not in facts          → blocker
deal.renewal_date is no longer inspected at all → satisfied = 0, no prerequisites_met row

observations: exactly 1
  dependency.prerequisite_absent
  codes (blocker:contract.countersigned_at, prerequisite_not_available)
```

`test_layer_three_may_name_the_prerequisites_itself` asserts `len(observations) == 1`. The override
is **wholesale**, like `gate_fields`: naming one field switches off inspection of everything the
capability declared. The docstring's case for the override: *"A capability whose real preconditions
differ from its context requirements can say so."* A capability may require `deal.status` to reason
at all while the *work* actually needs a countersigned contract; those are different lists.

### 4.3 A null placeholder

```python
facts = {"deal.signatory_email": None}
capability.required_fields = ("deal.signatory_email",)
→ dependency.prerequisite_absent
```

`test_a_null_placeholder_is_treated_as_an_absent_prerequisite`, whose docstring names the source of
the shape: *"L2 writes nulls for fields it tried and failed to resolve; a present key is not a
value."* Layer 2's `context/structured.py` records an attempted-and-failed resolution as a key with
a null, which is exactly the case a naive `field in facts` check would call satisfied.

### 4.4 Nothing declared

```python
facts = {"deal.status": "open"}
capability.required_fields = ()
config has no prerequisite_fields
→ PrerequisiteAbsencePlugin().contribute(view) == ()
```

`test_a_capability_that_declared_no_prerequisites_gets_none_invented`: *"Nothing was stated as
needed, so nothing can honestly be called missing."* No inspection row either — there was nothing to
inspect, and claiming an inspection would inflate `inspected_count` with work that never happened.

---

## 5 · Two findings that matter more than the arithmetic

### 5.1 On the default source, this plugin can never report a blocker in production

This is the sharpest thing in the folder, and it is invisible from inside the module.

The orchestrator's first act is:

```python
initial_missing = required_missing(request, request.capability.required_fields)
...
if initial_missing:
    terminal = DecisionOutcome.INSUFFICIENT_CONTEXT
```

and every planned step then takes the `if terminal is not None` branch and is **skipped**. So if a
capability-level required field is absent, `core.dependency` is never called at all.

Verified end to end through `ReasoningOrchestrator.execute`:

```text
capability.required_fields = ("deal.renewal_date", "deal.signatory_email")
facts = {"deal.renewal_date": ..., "legal.review_status": "in_review"}    # signatory absent

core.dependency  status=skipped  metrics={}  reason_codes=("skipped_after_insufficient_context",)
decision outcome insufficient_context   uncertainty ('deal.signatory_email',)
```

And with the field supplied:

```text
facts = {deal.renewal_date, deal.signatory_email, legal.review_status: in_review}
core.dependency  status=completed
                 blocked_count 1 · inspected_count 3 · unblocked_bp 4,000
                 reason_codes ("gate_awaiting_decision",)
```

`inspected_count 3` = 1 gate + 2 satisfied prerequisites. The `prerequisite_absent` branch is
unreachable.

**So in the orchestrated path, `dependency.prerequisite_absent` fires only when
`prerequisite_fields` is configured to name a field that is *not* in `capability.required_fields`.**
No shipped capability does that — `sales.deal_cooling_full` inherits
`required_fields = ("deal.status", "deal.value", "derived.engagement", "thread.last_inbound")` from
v1 and sets no `prerequisite_fields`, so the plugin will always emit exactly
`dependency.prerequisites_met` with `inspected: 4` and nothing else.

The plugin is correct in isolation and correct under direct call — which is how all four of its
tests exercise it. It is simply switched off by a layer above. The fix, if the claim is wanted, is
one config key in the manifest naming the fields whose absence should *report* rather than *abort*.
That is a Layer 3 authoring change, and it is the highest-value one available for this unit.

### 5.2 This plugin cites no evidence, and that has a downstream consequence

Neither observation carries `evidence_ids`. For the absent case that is unavoidable — an absent fact
has no `EvidenceRef` by definition. For the satisfied case it is a choice: the plugin knows the field
name and could call `evidence_ids(view.request, field)` exactly as the other two plugins do, but it
does not.

The consequence appears in `core.validation`. `EvidenceSufficiencyPlugin` flags any result where
`_asserts_a_claim(result)` is true and `_cited(result, producible)` is empty:

```python
def _asserts_a_claim(result) -> bool:
    if result.matched is True:
        return True
    return any(finding.matched is not False for finding in result.findings)
```

Every `core.dependency` finding carries `matched=True`. So a run whose **only** blocker is an absent
prerequisite produces `matched=True` with `evidence_ids == ()` and `core.validation` emits:

```text
validation.ungrounded_claim   reason_codes ("claim_without_evidence", "claimant:core.dependency")
```

lowering `evidence_sufficiency_bp` for the run. The claim is true, deterministic and correct — it
just cannot be traced to a row, so the integrity unit reports it as untraceable. Given §5.1 this is
currently unreachable in production too, but the moment `prerequisite_fields` is configured, both
behaviours switch on together.

The Category README records the same gap at §3.6, alongside `core.timeline`'s `TrendDirectionPlugin`.
Adding `evidence_ids(view.request, field)` to the `prerequisites_met` row would ground the plugin on
every run where anything is satisfied, at a cost of one line.
