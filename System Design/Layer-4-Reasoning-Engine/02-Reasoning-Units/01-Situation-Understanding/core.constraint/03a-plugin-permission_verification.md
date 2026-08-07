# 03a · Plugin `permission_verification`

**Class:** `genios_engine/reason/reasoners/constraint.py:PermissionVerificationPlugin`
**`plugin_id`:** `permission_verification` · **`kind`:** `constraint.permission` · **`stage`:** `permission`
**Slots owned:** `_SLOT_HUMAN_APPROVAL = 1`, `_SLOT_RECIPIENT = 3`
**Tests:** `test_permission_plugin_accepts_both_approval_spellings_and_rejects_silence`,
`test_permission_plugin_only_counts_an_equality_guard_on_a_true_value`,
`test_missing_recipient_effect_declaration_still_fails_closed_in_both`

---

## 1 · The claim it makes

*Who is allowed to be affected by this play, and who had to say yes first.*

Two policies, both about **reach** rather than about scope, and both failing closed on an **omission**
rather than on an assertion:

| Policy | Row asks | Pass code | Fail code |
|---|---|---|---|
| `human_approval_required` | does the play declare a human approval boundary? | `human_approval_boundary_pass` | `human_approval_boundary_missing` |
| `no_unverified_recipient` | if the play reaches an external party, is that reach guarded by a verified-recipient precondition? | `verified_recipient_guard_pass` | `verified_recipient_guard_missing` |

From the class docstring:

> *"a play that simply never mentions approval or recipient verification is eliminated, because the
> absence of a declaration is exactly the state this gate exists to catch."*

---

## 2 · When it stays silent

| Condition | Rows emitted |
|---|---|
| Neither policy in `capability.policies` | **none** — `checks()` returns `()`, `contribute()` returns `()` |
| Only `human_approval_required` declared | one row per play, slot 1 |
| Only `no_unverified_recipient` declared | one row per play, slot 3 |
| Both declared | two rows per play, slots 1 and 3 |
| A play the capability declares | always gets a row for each declared policy — there is no per-play exemption |

`test_a_plugin_with_nothing_to_say_contributes_no_observation` asserts the empty case:
`PermissionVerificationPlugin().contribute(view) == ()` for a capability with `policies=()`.

There is no config key. This plugin cannot be tuned per deployment; the only lever is whether the
capability declares the policy at all.

---

## 3 · The full arithmetic

There is no arithmetic — this plugin computes two booleans. Both are stated below exactly as coded.

### 3.1 · `human_approval_required`

```python
@staticmethod
def _approval_declared(play: PlayDefinition) -> tuple[bool, Any]:
    boundary = play.metadata.get("execution_boundary")
    return (boundary == "human_approval_required" or "human_approval" in play.tags), boundary
```

```text
approval_declared = (metadata["execution_boundary"] == "human_approval_required")
                    OR ("human_approval" in play.tags)

detail = { "execution_boundary": <the raw metadata value, or None>,
           "human_approval_tag": <bool: is the tag present> }
```

Two spellings are accepted. The docstring's reason is historical, not aesthetic: *"both predate the
policy and both are load-bearing in shipped packs."* `sales.deal_cooling` and `sales.deal_health`
carry both on every play, so both would have to be removed to break a shipped run — but a new pack
author who reaches for only one is still correct.

`metadata` is read with `.get()` here, unlike the recipient policy. An `execution_boundary` that is
absent is a legitimate state — the play may be declaring approval via its tag — so absence must not
raise.

### 3.2 · `no_unverified_recipient`

```python
@staticmethod
def _verification_guards(play: PlayDefinition) -> tuple[Mapping[str, Any], ...]:
    return tuple(condition for condition in play.preconditions
                 if str(condition.get("field") or "").endswith(_RECIPIENT_GUARD_SUFFIXES)
                 and condition.get("value") is True
                 and str(condition.get("op") or "") in _EQUALITY_OPERATORS)
```

```text
recipient_required = play.metadata["external_recipient_required"]      # INDEXED, not .get()
guards             = [ c in play.preconditions
                       where str(c["field"]).endswith(_RECIPIENT_GUARD_SUFFIXES)
                         and c["value"] is True                        # identity, not equality
                         and str(c["op"]) in {"=", "==", "eq"} ]
guarded            = (not recipient_required) or (len(guards) > 0)

detail = { "external_recipient_required": recipient_required,
           "guard_count": len(guards) }
```

Three predicates, each with a stated reason.

**The field suffix set is open by design.**

```python
_RECIPIENT_GUARD_SUFFIXES = (".verified_recipient", ".recipient_verified",
                             ".stakeholder_verified", "_stakeholder_verified")
```

> *"Authors name the fact differently per CRM; what matters is that the play refuses to run unless
> somebody verified the counterparty."*

Note the fourth entry has no dot. `account.alternate_stakeholder_verified` matches
`_stakeholder_verified` and not `.stakeholder_verified` — which is precisely why the fourth entry
exists, since `sales.deal_cooling`'s `multithread_account` play uses that spelling.
`str.endswith(tuple)` matches if *any* suffix matches.

**`value` is compared with `is True`, not `==`.** `1 == True` in Python; `1 is True` is `False`. A
condition asserting `value: 1` is not a verification guard, and
`test_permission_plugin_only_counts_an_equality_guard_on_a_true_value` builds exactly that case and
asserts `ELIMINATE`.

**The operator must be equality.**

```python
_EQUALITY_OPERATORS = frozenset({"=", "==", "eq"})
```

> *"A guard must assert the verification is true; `>=` on a boolean is not a guard, it is an
> accident."*

**The metadata is indexed, not `.get()`-ed.**

> *"capability validation already requires the typed effect declaration, so a malformed object
> crossing that boundary should fail loudly here rather than be read as 'no external reach'."*

`CapabilityManifest.__post_init__` enforces the same thing at construction:

```python
if "no_unverified_recipient" in policies:
    for play in self.plays:
        if ("external_recipient_required" not in play.metadata
                or not isinstance(play.metadata["external_recipient_required"], bool)):
            raise ValueError(
                "no_unverified_recipient requires every play to declare the boolean "
                f"external_recipient_required effect: {play.play_id}")
```

So the `KeyError` is unreachable through a legally constructed manifest.
`test_missing_recipient_effect_declaration_still_fails_closed_in_both` reaches it by mutating a frozen
manifest with `object.__setattr__` and asserts `pytest.raises(KeyError)` — deliberately proving that
the second, redundant check has teeth if the first is ever bypassed.

---

## 4 · Worked example 1 — the four approval spellings

Capability declares `policies=("human_approval_required",)` and four plays. Actual rows, printed from
the plugin:

| key | `play_id` | declaration | outcome | `reason_code` | `detail` |
|---|---|---|---|---|---|
| `(0,0,1,0)` | `by_metadata` | `metadata={"execution_boundary": "human_approval_required"}` | `pass` | `human_approval_boundary_pass` | `{"execution_boundary": "human_approval_required", "human_approval_tag": False}` |
| `(0,1,1,0)` | `by_tag` | `tags=("human_approval",)` | `pass` | `human_approval_boundary_pass` | `{"execution_boundary": None, "human_approval_tag": True}` |
| `(0,2,1,0)` | `undeclared` | `metadata={"execution_boundary": "autonomous"}` | **`eliminate`** | `human_approval_boundary_missing` | `{"execution_boundary": "autonomous", "human_approval_tag": False}` |
| `(0,3,1,0)` | `no_metadata` | nothing | **`eliminate`** | `human_approval_boundary_missing` | `{"execution_boundary": None, "human_approval_tag": False}` |

Two things to read off that table. The `detail` distinguishes *"declared something else"*
(`"autonomous"`) from *"declared nothing"* (`None`) even though both eliminate with the same code —
an auditor can tell an author who chose autonomy from an author who forgot. And the sort key's third
component is `1` on every row: this plugin never emits into slot 0 or 2, which belong to
`policy_enforcement`.

`Observation` for this run: `{"checks_emitted": 4, "eliminated": 2}`.

---

## 5 · Worked example 2 — the six recipient-guard shapes

Capability declares `policies=("no_unverified_recipient",)`. Snapshot supplies
`facts={"account.alternate_stakeholder_verified": True}` and
`neighbor_facts={"contact.verified_recipient": True}` — **neither of which this plugin reads.**

| key | `play_id` | `external_recipient_required` | authored guard condition | `guard_count` | outcome |
|---|---|---|---|---|---|
| `(0,0,3,0)` | `internal` | `False` | — | 0 | `pass` |
| `(0,1,3,0)` | `guarded` | `True` | `{field: contact.verified_recipient, neighbor: True, op: "=", value: True}` | 1 | `pass` |
| `(0,2,3,0)` | `unguarded` | `True` | — | 0 | **`eliminate`** |
| `(0,3,3,0)` | `weak_operator` | `True` | same field, `op: ">="` | 0 | **`eliminate`** |
| `(0,4,3,0)` | `weak_value` | `True` | same field, `value: "yes"` | 0 | **`eliminate`** |
| `(0,5,3,0)` | `suffix_variant` | `True` | `{field: account.alternate_stakeholder_verified, op: "eq", value: True}` | 1 | `pass` |

`Observation`: `{"checks_emitted": 6, "eliminated": 3}`.

Row 0 is the trivial pass — a play that reaches nobody external needs no guard, and `guarded` is
`not recipient_required or ...`, which short-circuits before `_verification_guards` matters. Rows 3
and 4 are the two ways to write something that *looks* like a guard: the operator is wrong in one and
the value type is wrong in the other, and in both cases `guard_count` drops to 0 and the play is
removed. Row 5 proves the suffix set is doing real work: a differently-named CRM field with the
`eq` spelling and no `neighbor` flag still counts.

---

## 6 · The subtlety worth writing down

**`verified_recipient_guard_pass` proves the play *declares* a guard. It does not prove the guard
*holds*.**

This plugin never reads the snapshot. `_verification_guards` inspects the authored condition and stops
there. Whether `contact.verified_recipient` is actually `True` in this situation is
`PreconditionPlugin`'s question, answered on a different row, in a different slot, with a different
stage.

Observed on `sales.deal_cooling` with `neighbor_facts = {"contact.verified_recipient": False}`:

```text
restore_momentum  permission    pass       verified_recipient_guard_pass
                                           {"external_recipient_required": True, "guard_count": 1}
restore_momentum  precondition  eliminate  precondition_failed
                                           {"index": 1, "field": "contact.verified_recipient",
                                            "neighbor": True, "operator": "=",
                                            "expected": True, "actual": False}
```

The play *is* eliminated — the ELIMINATE arrives from slot 4, not slot 3 — so the safety property
holds. But the split has two consequences a reader should carry:

1. **The permission `Observation` under-reports.** On that run
   `permission_verification` reports `eliminated: 0` while the recipient is demonstrably unverified.
   The counts describe *this plugin's* rows, not the situation.
2. **`store.py` proves the wrong-sounding thing, correctly.** Its requirement for
   `no_unverified_recipient` is one passing `verified_recipient_guard_pass` row on the selected play
   — i.e. *the selected play declared a guard*. It relies on the precondition row to have eliminated
   the play if the guard did not hold, which `decision_maker.evaluate_candidates` enforces before
   selection ever happens. The two-row design is sound; the pass code simply reads stronger in
   isolation than it is.

The split is defensible on its own terms: *declaring* a guard is a property of the play, checkable
without a snapshot and stable across every situation, while *satisfying* it is a property of the
situation. Conflating them would make a play's compliance depend on the data, which is not what
"this play is authored safely" means.

---

## 7 · Edge cases

| Input | Behaviour |
|---|---|
| `metadata["execution_boundary"]` is a non-string, e.g. `1` | `1 == "human_approval_required"` is `False`; falls through to the tag test. `detail` carries the raw value |
| `tags` contains `human_approval` **and** `execution_boundary` is `"autonomous"` | passes — the disjunction is inclusive. The `detail` records both so the contradiction is visible |
| `metadata["external_recipient_required"]` absent while the policy is declared | `KeyError`, `_evaluate` converts to `FAILED`. Blocked at manifest construction in practice |
| `metadata["external_recipient_required"]` is `1` rather than `True` | `not 1` is `False`, so it behaves as `True` and a guard is required. Blocked at manifest construction by the `isinstance(..., bool)` test |
| A precondition with `field: None` | `str(None or "")` is `""`, which ends with no suffix; not a guard |
| A precondition with no `op` key | `str(condition.get("op") or "")` is `""`, not in `_EQUALITY_OPERATORS`; not a guard. Note `PreconditionPlugin` defaults a missing `op` to `exists`, this plugin does not |
| Multiple guards on one play | all counted; `guard_count` can exceed 1. Any one is enough to pass |
| `capability.plays` is empty | impossible — `CapabilityManifest` requires at least one play |
