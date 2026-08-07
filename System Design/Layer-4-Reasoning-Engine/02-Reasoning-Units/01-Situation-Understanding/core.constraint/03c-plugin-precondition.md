# 03c · Plugin `precondition`

**Class:** `genios_engine/reason/reasoners/constraint.py:PreconditionPlugin`
**`plugin_id`:** `precondition` · **`kind`:** `constraint.precondition` · **`stage`:** `precondition`
**Slot owned:** `_SLOT_PRECONDITION = 4` — the only slot whose fourth key component varies
**Helpers:** `constraint.py:_compare`, `common.py:fact_value`, `common.py:decimal`
**Tests:** `test_precondition_plugin_distinguishes_absent_from_smaller`,
`test_precondition_plugin_reads_the_neighbour_space_when_asked`,
`test_precondition_plugin_records_the_authored_index_on_every_row`,
`test_unsupported_operator_still_raises_in_both_implementations`, and the `every_operator`
differential scenario

---

## 1 · The claim it makes

*What the play author said must already be true before this play is eligible.*

This is the only part of the gate that is **authored per play** rather than per capability, and the
only part that **reads the snapshot**. It is also the only part with no policy behind it: preconditions
are evaluated whether or not the capability declares any policy at all.

One row per authored condition per play. A play with three conditions produces three independently
attributable rows:

> *"so a play with three conditions produces three independently attributable rows rather than one
> aggregate verdict."*

| Outcome | `reason_code` |
|---|---|
| condition holds | `precondition_pass` |
| condition does not hold | `precondition_failed` |

---

## 2 · When it stays silent

| Condition | Rows emitted |
|---|---|
| No play declares any precondition | **none** — `checks()` returns `()`, `contribute()` returns `()` |
| Some plays have conditions, others do not | rows only for the plays that have them |
| A condition names a field the snapshot does not carry | **a row is still emitted** — `ELIMINATE`, with `actual: None` |
| The capability declares no policies at all | irrelevant; this plugin does not read `capability.policies` |

There is no config key. Nothing about this plugin is tunable per deployment — the conditions come from
Layer 3 play authoring and are versioned with the capability snapshot.

`test_a_plugin_with_nothing_to_say_contributes_no_observation` asserts the empty case.

---

## 3 · The full arithmetic

### 3.1 · Resolving one condition

```python
@staticmethod
def evaluate_condition(request, condition) -> tuple[bool, str, bool, str, Any, Any]:
    field    = str(condition.get("field") or "")
    neighbor = bool(condition.get("neighbor", False))
    exists   = field in (request.context.neighbor_facts if neighbor else request.context.facts)
    operator = str(condition.get("op") or "exists")
    expected = condition.get("value")
    if operator == "exists":
        passed = exists
        actual = fact_value(request, field, neighbor=neighbor) if exists else None
    elif operator == "absent":
        passed = not exists
        actual = fact_value(request, field, neighbor=neighbor) if exists else None
    elif not exists:
        passed, actual = False, None
    else:
        actual = fact_value(request, field, neighbor=neighbor)
        passed = _compare(actual, operator, expected)
    return passed, field, neighbor, operator, expected, actual
```

Four defaults are worth naming because each one turns a malformed condition into a defined outcome
rather than a crash:

| Authored omission | Resolved to |
|---|---|
| no `field` key, or `field: None` | `""` — which is in no fact space, so `exists` is `False` |
| no `neighbor` key | `False` — the root fact space |
| no `op` key, or `op: None` | `"exists"` |
| no `value` key | `None` — meaningful for `=`/`!=`, ignored by `exists`/`absent` |

**Absence is resolved before comparison, never inside it.** The `elif not exists` branch short-circuits
every operator except `exists` and `absent`:

> *"'the field is missing' and 'the field is present and smaller' are different facts and an auditor
> needs to tell them apart from the `detail` alone."*

`test_precondition_plugin_distinguishes_absent_from_smaller` is exactly this: two conditions,
both `>= 100_000`, one against `deal.value = 50_000` and one against an absent field. Both eliminate;
`detail["actual"]` is `50_000` on the first and `None` on the second.

`common.py:fact_value` unwraps a fact record: if the stored value is a `Mapping` carrying a `"value"`
key it returns that, otherwise it returns the record itself. So
`{"deal.status": {"value": "open", "confidence_bp": 9_000}}` compares as `"open"`
(`wrapped_fact_record` scenario).

### 3.2 · The operator table

```python
def _compare(actual, operator: str, expected) -> bool:
    if operator in {"=", "==", "eq"}:   return actual == expected
    if operator in {"!=", "ne"}:        return actual != expected
    if operator == "in":
        return actual in expected if isinstance(expected, (tuple, list, set, frozenset)) else False
    if operator in {">", ">=", "<", "<="}:
        try:
            left, right = decimal(actual, "precondition actual"), decimal(expected, "precondition expected")
        except ValueError:
            return False
        return {">": left > right, ">=": left >= right,
                "<": left < right, "<=": left <= right}[operator]
    raise ValueError(f"unsupported precondition operator: {operator}")
```

| Operator spellings | Semantics | On a missing field |
|---|---|---|
| `exists` (also the default) | field is present in the chosen space | `False` |
| `absent` | field is **not** present | `True` |
| `=`, `==`, `eq` | Python `==` on the raw values | `False`, short-circuited before `_compare` |
| `!=`, `ne` | Python `!=` | `False`, short-circuited |
| `in` | membership; **`False` if `expected` is not a `tuple`/`list`/`set`/`frozenset`** | `False`, short-circuited |
| `>`, `>=`, `<`, `<=` | `Decimal` comparison; `False` if either side will not parse | `False`, short-circuited |
| anything else | **raises `ValueError: unsupported precondition operator: <op>`** | raises |

**Numeric comparison goes through `Decimal`, never float.** `common.py:decimal` builds
`Decimal(str(value))`, rejects `bool` outright, and rejects non-finite values:

> *"Numeric comparison goes through `Decimal` rather than float so that 'value >= 50000' resolves
> identically on every machine and in replay."*

**An unparseable value fails the comparison rather than raising**, because *"an unparseable fact is
not a satisfied precondition."* Both sides are parsed, so `deal.value > "not-a-number"` fails on the
*expected* side and `deal.label > 1` fails on the *actual* side; both produce a plain `ELIMINATE`.

**An unsupported operator raises**, and that asymmetry is argued explicitly:

> *"that is an authoring fault in Layer 3 and silently treating it as a failure would hide a broken
> play behind a plausible-looking elimination."*

### 3.3 · Building the rows

```python
for play_index, play in enumerate(request.capability.plays):
    for index, condition in enumerate(play.preconditions):
        passed, field, neighbor, operator, expected, actual = self.evaluate_condition(request, condition)
        key    = (_GROUP_PLAY=0, play_index, _SLOT_PRECONDITION=4, index)
        detail = {"index": index, "field": field, "neighbor": neighbor,
                  "operator": operator, "expected": expected, "actual": actual}
```

Six fields in the detail, and every one is a *resolved* value rather than the raw authored one:
`field` has been coerced to a string, `neighbor` to a boolean, `operator` has had its `exists` default
applied. An auditor reading the persisted row sees what the unit actually evaluated, not what the
author typed.

`index` is also carried in the sort key, so three conditions on one play emit in authored order —
`test_precondition_plugin_records_the_authored_index_on_every_row` asserts
`[0, 1, 2]`.

---

## 4 · Worked example 1 — every operator, on one play

One play, twenty authored conditions, `policies=()`. Snapshot:

```text
facts          = { deal.value: 250000, deal.stage: "negotiation",
                   deal.owner: "rohit", deal.label: "flagship" }
neighbor_facts = { contact.title: "VP" }
```

All twenty rows, printed from the plugin:

| `index` | `field` | `neighbor` | `operator` | `expected` | `actual` | outcome | why |
|---|---|---|---|---|---|---|---|
| 0 | `deal.value` | false | `>` | `100000` | `250000` | `pass` | `Decimal("250000") > Decimal("100000")` |
| 1 | `deal.value` | false | `>=` | `250000` | `250000` | `pass` | equal satisfies `>=` |
| 2 | `deal.value` | false | `<` | `100000` | `250000` | `eliminate` | |
| 3 | `deal.value` | false | `<=` | `250000` | `250000` | `pass` | |
| 4 | `deal.stage` | false | `in` | `("discovery","negotiation")` | `"negotiation"` | `pass` | tuple, membership holds |
| 5 | `deal.stage` | false | `in` | `"negotiation"` | `"negotiation"` | **`eliminate`** | expected is a `str`, not a collection → `False` without testing membership |
| 6 | `deal.stage` | false | `!=` | `"closed"` | `"negotiation"` | `pass` | |
| 7 | `deal.stage` | false | `ne` | `"negotiation"` | `"negotiation"` | `eliminate` | |
| 8 | `deal.stage` | false | `==` | `None` | `"negotiation"` | `eliminate` | no `value` key → compared against `None` |
| 9 | `deal.owner` | false | `exists` | `None` | `"rohit"` | `pass` | `actual` is populated on a passing `exists` |
| 10 | `deal.owner` | false | `absent` | `None` | `"rohit"` | `eliminate` | `actual` populated on a *failing* `absent`, which is the useful direction |
| 11 | `deal.next_step` | false | `exists` | `None` | `None` | `eliminate` | |
| 12 | `deal.next_step` | false | `absent` | `None` | `None` | `pass` | |
| 13 | `deal.next_step` | false | `>` | `1` | `None` | `eliminate` | short-circuited by `not exists`; `_compare` never runs |
| 14 | `deal.label` | false | `>` | `1` | `"flagship"` | `eliminate` | `Decimal("flagship")` raises → caught → `False` |
| 15 | `deal.value` | false | `>` | `"not-a-number"` | `250000` | `eliminate` | the *expected* side fails to parse |
| 16 | `contact.title` | **true** | `=` | `"VP"` | `"VP"` | `pass` | neighbour space |
| 17 | `contact.title` | false | `=` | `"VP"` | `None` | `eliminate` | same field, root space, not found |
| 18 | `""` | false | `exists` | `None` | `None` | `eliminate` | no `field` key at all |
| 19 | `deal.owner` | false | `exists` | `None` | `"rohit"` | `pass` | no `op` key → defaults to `exists` |

`Observation`: `{"checks_emitted": 20, "eliminated": 11}`.

Rows 16 and 17 together are the neighbour-space proof, and `test_precondition_plugin_reads_the_neighbour_space_when_asked`
runs the mirror of it: the same condition with `neighbor: true` against a snapshot that puts the fact
in the *root* space eliminates, because the two spaces are disjoint lookups with no fallback.

Row 5 is the one most likely to bite an author. `{"op": "in", "value": "negotiation"}` looks like it
should work — Python's `in` on strings is substring containment — and the guard against
`isinstance(expected, (tuple, list, set, frozenset))` exists precisely to stop
`"negotiation" in "negotiation_stage"` from silently passing. The condition fails closed, which is
right, but it fails silently: there is no reason code that says *"your `in` value should have been a
list"*.

---

## 5 · Worked example 2 — `sales.deal_cooling`, an open deal and a closed one

Three plays, two authored conditions each, all six rows in slot 4.

**Open deal**, `facts = {deal.status: "open"}`, `neighbor_facts = {contact.verified_recipient: True,
account.alternate_stakeholder_verified: True}`, no `deal.next_step`:

| key | play | `index` | condition | `actual` | outcome |
|---|---|---|---|---|---|
| `(0,0,4,0)` | `restore_momentum` | 0 | `deal.status = "open"` | `"open"` | `pass` |
| `(0,0,4,1)` | `restore_momentum` | 1 | `contact.verified_recipient = True` *(neighbor)* | `True` | `pass` |
| `(0,1,4,0)` | `multithread_account` | 0 | `deal.status = "open"` | `"open"` | `pass` |
| `(0,1,4,1)` | `multithread_account` | 1 | `account.alternate_stakeholder_verified = True` *(neighbor)* | `True` | `pass` |
| `(0,2,4,0)` | `clarify_next_step` | 0 | `deal.status = "open"` | `"open"` | `pass` |
| `(0,2,4,1)` | `clarify_next_step` | 1 | `deal.next_step absent` | `None` | `pass` |

`Observation`: `{"checks_emitted": 6, "eliminated": 0}`.

**Closed deal with an unverified contact**, `facts = {deal.status: "closed"}`,
`neighbor_facts = {contact.verified_recipient: False, account.alternate_stakeholder_verified: True}`:

| key | play | `index` | `expected` | `actual` | outcome |
|---|---|---|---|---|---|
| `(0,0,4,0)` | `restore_momentum` | 0 | `"open"` | `"closed"` | **`eliminate`** |
| `(0,0,4,1)` | `restore_momentum` | 1 | `True` | `False` | **`eliminate`** |
| `(0,1,4,0)` | `multithread_account` | 0 | `"open"` | `"closed"` | **`eliminate`** |
| `(0,1,4,1)` | `multithread_account` | 1 | `True` | `True` | `pass` |
| `(0,2,4,0)` | `clarify_next_step` | 0 | `"open"` | `"closed"` | **`eliminate`** |
| `(0,2,4,1)` | `clarify_next_step` | 1 | — | `None` | `pass` |

`Observation`: `{"checks_emitted": 6, "eliminated": 4}`.

The last row is the counter-intuitive one and it is correct: `clarify_next_step`'s second condition is
`{"field": "deal.next_step", "op": "absent"}`, so the *absence* of a next step is what makes the play
eligible. The play exists to create the missing next step. A precondition that passes on absence is
the reason `absent` had to be a first-class operator rather than a `!= None` comparison — an absent
field has no value to compare against.

---

## 6 · Interaction with `permission_verification`

Both plugins read `play.preconditions`, and they ask different questions of it:

```text
permission_verification._verification_guards(play)
    → does a condition of the guard SHAPE exist?
      (suffix match, value is True, op in {=, ==, eq})
      → slot 3, stage "permission"

PreconditionPlugin.evaluate_condition(request, condition)
    → does the condition HOLD against this snapshot?
      → slot 4, stage "precondition", one row per condition
```

`sales.deal_cooling`'s `restore_momentum` therefore produces two rows about condition index 1, and on
an unverified-contact run they disagree — `verified_recipient_guard_pass` at slot 3,
`precondition_failed` at slot 4. Both are true statements. See
[03a](03a-plugin-permission_verification.md) §6.

---

## 7 · The gap: one bad operator fails the whole capability

```python
raise ValueError(f"unsupported precondition operator: {operator}")
```

`orchestrator.py:_evaluate` catches it and produces `ResultStatus.FAILED` with the message in
`diagnostics`. Because `core.constraint` is `FailurePolicy.REQUIRED` in every shipped capability, the
whole run then produces no advice — not for the play with the typo, for every play.

`test_unsupported_operator_still_raises_in_both_implementations` pins the raise (using `op: "~="`) in
both the migrated unit and the frozen legacy reference, so this is shipped behaviour, not an
oversight.

The argument for it is sound and stated in the code: an authoring fault must not disguise itself as
an elimination, because an elimination looks like the system working. The cost is that the blast
radius is the capability rather than the play, and there is nothing upstream that validates authored
operators — `PlayDefinition.__post_init__` validates that each precondition is a mapping and stops
there. A Layer 3 manifest-time check against the known operator set would move the failure from
"runtime, every run, no advice" to "deployment, once, with the play id in the message". It is not
built.

---

## 8 · Edge cases

| Input | Behaviour |
|---|---|
| `field` present in both `facts` and `neighbor_facts` | only the space `neighbor` selects is consulted; no merge, no fallback |
| `actual` is a `bool` and the operator is `>`/`>=`/`<`/`<=` | `common.py:decimal` rejects `bool` with `ValueError` → caught → `False` |
| `actual` is a `Decimal` | used directly by `decimal()`, no string round-trip |
| `expected` is a `set` and the operator is `in` | supported — `set` and `frozenset` are both in the accepted collection types |
| `value` key present but the operator is `exists`/`absent` | ignored for the decision, still recorded in `detail["expected"]` |
| A precondition mapping that is empty, `{}` | `field=""`, `op="exists"`, `expected=None` → `ELIMINATE` with an empty field name. Row 18 above |
| Two identical conditions on one play | two rows with different `index`; both persisted, neither deduplicated |
| `preconditions` on a play the tenant has blocked | still evaluated and still emitted — the block is a separate group-1 row, not a skip |
