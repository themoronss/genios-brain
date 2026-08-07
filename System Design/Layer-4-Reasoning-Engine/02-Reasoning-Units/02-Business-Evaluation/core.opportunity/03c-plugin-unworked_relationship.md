# Plugin · `unworked_relationship`

**Class:** `opportunity.py:UnworkedRelationshipPlugin` (lines 89–103)
**`plugin_id`:** `unworked_relationship` — **third** in execution order
**`Observation.kind`:** `opportunity.unowned` ← **does not match the plugin id**
**Reason code:** `no_owner_assigned`
**Metrics emitted:** `strength_bp`
**Config keys:** `unowned_strength_bp` (default `4_000`)
**Depends on:** no prior unit

---

## 1 · The claim

> *"A live relationship with no one currently working it."*

The shortest claim in the unit and the one that needs the most care, because it is the only plugin
in `core.opportunity` that treats **absence of data as the assertion**. The other two say nothing
when their input is missing. This one says *"there is 4,000bp of headroom here"*.

The business reading is sound: an account with nobody assigned to it is untouched upside by
definition — no one is going to work it, so the whole of whatever is there is unclaimed. The
implementation reading is the problem, and §5 is where the two diverge.

---

## 2 · The code, in full

```python
class UnworkedRelationshipPlugin:
    """A live relationship with no one currently working it."""

    plugin_id = "unworked_relationship"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        owner = fact_value(view.request, "deal.owner")
        if owner:
            return ()
        return (Observation(
            plugin_id=self.plugin_id,
            kind="opportunity.unowned",
            metrics={"strength_bp": _config_bp(view, "unowned_strength_bp", 4_000)},
            reason_codes=("no_owner_assigned",),
        ),)
```

Ten lines. One guard. No arithmetic.

### 2.1 · The guard is Python truthiness, not a null check

`if owner:` — not `if owner is not None:`. Every falsy value takes the firing branch. Verified
against the live plugin, holding `deal.status = "closed_won"` so only this plugin can speak:

| `deal.owner` | Truthy? | `opportunity_bp` | `opportunity_count` |
|---|---|---|---|
| `"rohit"` | yes | 0 | 0 |
| `"unassigned"` | **yes** | 0 | 0 |
| `""` | no | **4,000** | 1 |
| `0` | no | **4,000** | 1 |
| `False` | no | **4,000** | 1 |
| `[]` | no | **4,000** | 1 |
| `None` | no | **4,000** | 1 |
| *field absent entirely* | no | **4,000** | 1 |

Two rows are worth pausing on. `deal.owner = 0` fires — a CRM that stores owner ids as integers and
uses `0` for the unassigned sentinel gets the right answer by accident. `deal.owner = "unassigned"`
does **not** fire — the same CRM using a string sentinel gets the wrong answer, silently, and there
is no config key to teach the plugin the sentinel.

### 2.2 · The one config key

```python
_config_bp(view, "unowned_strength_bp", 4_000)
```

| Key | Type | Default | Validator | Read when |
|---|---|---|---|---|
| `unowned_strength_bp` | int, 0–10,000 | `4_000` | `opportunity.py:_config_bp` | only on runs where the unowned branch fires |

The 4,000bp default is a judgement, unfitted to any data: an unowned deal is worth *less* than a
fully-decayed one (`stalled_but_open` at 10,000bp) and *less* than a day-old unanswered message
(`unanswered_inbound` at 10,000bp), but more than nothing. It sits just above the default
`opportunity_threshold_bp` of 3,000 and above the shipped 2,500 — so **on its own it is always
enough to make the unit report `matched=True`.** That is not incidental; it is the numeric fact
that produces defect 2 in the [README](README.md#6--known-defects-and-compromises).

Validation is lazy. `_config_bp` sits inside the firing branch, so a malformed value is only caught
on a run where the branch is reached. Verified:

```text
config = {"unowned_strength_bp": -1}
  deal.owner = "rohit"  → return () before _config_bp → COMPLETES, opportunity_bp 0
  deal.owner absent     → _config_bp raises ValueError:
                          "unowned_strength_bp must be integer basis points"
                        → orchestrator._evaluate catches → ResultStatus.FAILED
                          reason_codes ("reasoner_failure",)
                          diagnostics {"exception_type": "ValueError", "message": …}
```

Because the shipped capability marks `core.opportunity` `OPTIONAL`, that `FAILED` does not stop the
run — it appends `optional_failed:core.opportunity` to `uncertainty` and every consumer falls back
to its own default.

### 2.3 · The name mismatch

Three different names describe this one plugin:

| Field | Value | Set at |
|---|---|---|
| `plugin_id` | `unworked_relationship` | line 92 |
| `Observation.kind` | `opportunity.unowned` | line 100 |
| `Finding.finding_id` | `opportunity.unworked_relationship` | line 136, `f"opportunity.{item.plugin_id}"` |

The other two plugins keep kind and id aligned (`opportunity.stalled_but_open`,
`opportunity.unanswered_inbound`). This one does not. Nothing outside `opportunity.py` reads any
`Observation.kind` this unit emits — `calculate` reads `metrics`, `evaluate_meaning` reads
`plugin_id` — so it is inert. It is still a trap: grepping for `opportunity.unworked_relationship`
finds the finding but not the plugin, and grepping for `opportunity.unowned` finds the reverse.

---

## 3 · The arithmetic

There is none.

```text
strength_bp = _config_bp(view, "unowned_strength_bp", 4_000)
```

A constant lookup. No `clamp_bp` call is needed because `_config_bp` already rejects anything
outside 0–10,000 — and unlike `stalled_but_open`, which clamps defensively, this plugin does not
bother, correctly.

That makes `unworked_relationship` the only plugin in the unit whose strength does not vary with
the situation. Every unowned deal in an org contributes exactly the same number. It is a **flag
expressed in the score's units**, which is the compromise the whole unit makes to keep one metric
rather than a metric plus a set of booleans.

---

## 4 · Worked examples

### 4.1 · The shipped capability — where this plugin does real damage

`sales.deal_cooling_full` v2 against its fixture. The snapshot's facts are `deal.status`,
`deal.value`, `derived.engagement`, `thread.last_inbound`, `relationship.verified_stakeholder_count`.
There is no `deal.owner`, because nothing in `genios_engine/` writes that field and
`native.py:_selected_fields` would not carry it if something did.

```text
owner = fact_value(request, "deal.owner") = None
if None: → falsy → FIRE

_config_bp(view, "unowned_strength_bp", 4_000)
   view.config = {"opportunity_threshold_bp": 2500}   ← key absent → default
   → 4,000

Observation(plugin_id="unworked_relationship",
            kind="opportunity.unowned",
            metrics={"strength_bp": 4000},
            reason_codes=("no_owner_assigned",))

calculate  strengths [6000, 4000]        6000 from stalled_but_open
           lift = half_up(4000, 4) = (4,000 + 2) // 4 = 1,000
           opportunity_bp = 7,000        ← 1,000 of those 7,000 come from this plugin
           opportunity_count = 2

evaluate   7,000 >= 2,500 → matched True
           finding opportunity.unworked_relationship  {"strength_bp": 4000}
           reason code no_owner_assigned surfaces in ReasonerResult.reason_codes
```

Verified against the live orchestrator. The deal in that fixture is a real deal at a real company
with, presumably, a real account executive. The engine states in its audit trail that nobody is
assigned to it, because a field it has never been given was not there.

### 4.2 · The plugin alone, on an otherwise empty snapshot

```text
facts = {}, prior = {}

stalled_but_open       deal.status absent → "" ∉ open set        → ()
unanswered_inbound     deal.last_inbound absent                  → ()
unworked_relationship  deal.owner absent → falsy                 → FIRES  4,000

calculate  strengths [4000] → lift = half_up(0, 4) = 0 → opportunity_bp 4,000
           opportunity_count 1
evaluate   4,000 >= 3,000 (default) → matched True
           reason_codes ("no_owner_assigned",)
```

Verified. **A completely empty context produces a positive, matched opportunity claim.** That is
the sharpest statement of the problem: the unit's floor is not zero, it is 4,000bp, and it is
reached by knowing nothing at all.

### 4.3 · Silence — the deal is owned

```text
facts = {"deal.owner": "rohit", "deal.status": "closed_won"}

owner = "rohit" → truthy → return ()
_config_bp never called; a malformed unowned_strength_bp would not be detected

calculate  strengths [] → {"opportunity_bp": 0, "opportunity_count": 0}
evaluate   0 >= 3,000 is False → matched False, findings (), reason_codes ()
```

Verified.

### 4.4 · An authored strength

```text
config = {"unowned_strength_bp": 9_000}
facts  = {"deal.status": "closed_won"}       (no owner)

strength_bp = 9,000
opportunity_bp = 9,000, count 1, matched True
```

Verified. A capability that considers unowned accounts its primary opportunity source can raise the
key to make this plugin dominate the blend; one that considers ownership a bookkeeping detail can
set it to `0`, in which case the plugin still fires and still increments `opportunity_count` but
contributes nothing to the score.

---

## 5 · Silence semantics — and why this plugin inverts the unit's rule

| Condition | Contributes? |
|---|---|
| `deal.owner` truthy | silent |
| `deal.owner` falsy — `""`, `0`, `False`, `[]`, `None` | **fires** at `unowned_strength_bp` |
| `deal.owner` absent from the snapshot | **fires** at `unowned_strength_bp` |
| `deal.owner` present but not selected by the capability | **fires** at `unowned_strength_bp` |

The last two rows are the problem. `core.impact`'s module docstring states the rule the rest of
Layer 4 follows:

> *"An unmeasured dimension has no value, and treating it as zero would report a small stake for a
> large deal whose account tier simply was not synced."*

`unworked_relationship` does the opposite: it treats an unmeasured field as a **measured negative**,
and a measured negative is a claim. There is no branch anywhere in the plugin that distinguishes
*"the CRM says this deal is unassigned"* from *"nobody asked the CRM"*.

The information needed to make that distinction is sitting in the request. `ContextSnapshot` carries
`missing_fields` — Layer 2's explicit statement of what it looked for and could not find — and
`guards.py:required_missing` already uses it for exactly this purpose:

> *"A field counts as missing when it is absent **or** when Layer 2 explicitly published it as
> missing — an unknown fact and a known-absent fact must both stop reasoning rather than be
> silently treated as a default value."*

A three-line change would fix it:

```python
if "deal.owner" not in view.request.context.facts:
    return ()                # nobody asked; that is not the same as nobody assigned
```

The design intent is defensible without that guard **only** if the capability guarantees the field
is always selected — which is what `required_fields` exists to declare, and which
`core.opportunity` declares nothing in. The unit would get its evidence citations at the same time
([02 · Retriever](02-Retriever.md) §3.2). One manifest line closes both.

---

## 6 · Defects and compromises

| # | What | Severity |
|---|---|---|
| 1 | **Absence is read as a claim.** §5. In production `deal.owner` is written by nothing in `genios_engine/` and is not in `sales.deal_cooling_full` v2's selected field set, so this plugin fires on **every deal the capability ever evaluates** — and at 4,000bp against a 2,500bp threshold, it alone makes the unit `matched=True` every time. Verified on the shipped fixture. | **high** |
| 2 | **A string sentinel defeats the check.** `deal.owner = "unassigned"` is truthy, so the plugin goes silent on a deal that genuinely has no owner. No config key exists for the sentinel vocabulary. | medium |
| 3 | **No config key for the field path.** `"deal.owner"` is a literal. A capability rooted on `account` or `company` cannot point it at `account.owner`. | medium |
| 4 | **No evidence.** The `Observation` carries no `evidence_ids`. Here that is arguably honest — the claim is about a field that is *absent*, and there is no `EvidenceRef` for an absence — but it means a matched `core.opportunity` whose only firing plugin is this one produces `result.evidence_ids = ()` and is counted ungrounded by `core.validation`. Verified: `claimant:core.opportunity` in the shipped run. | **high** |
| 5 | **`kind` does not match `plugin_id`.** §2.3. Inert today, confusing forever. | cosmetic |
| 6 | **The 4,000bp default is unfitted**, and its relationship to `opportunity_threshold_bp` (3,000 default, 2,500 shipped) is what makes this plugin decisive rather than contributory. Neither number has been validated against outcomes. | acknowledged |
| 7 | **Unpinned.** No test asserts the truthiness table, the default, the lazy config validation, or the firing-on-absence behaviour. | process |

---

## 7 · Related

- [03 · Analyzer](03-Analyzer.md) — how this plugin's silence rule differs from the other two
- [04 · Calculator](04-Calculator.md) — where a constant 4,000bp lands in the blend
- [05 · Evaluator](05-Evaluator.md) — the threshold this default sits above
- [README](README.md) — defect 2, stated with its production consequence
- `genios_engine/reason/guards.py:required_missing` — the known-absent mechanism this plugin does not use
