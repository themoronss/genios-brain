# Plugin · `strategic_linkage`

**Class:** `impact_unit.py:StrategicLinkagePlugin` (lines 187–241)
**`plugin_id`:** `strategic_linkage` — **third** in execution order
**`Observation.kind`:** `impact.strategic_linkage`
**Publishes into:** `strategic_bp` (via `_DIMENSIONS`), default weight **2,000** — the tie-breaker

---

## 1 · The claim

*Whether this entity is attached to something the business has declared it is trying to do.*

> *"Work that advances a declared goal is worth more than equally-sized work that does not."*

The design constraint that shapes every line of this plugin:

> *"Strategic weight is not inferable from the entity itself — it is a statement of intent that
> lives in the capability."*

There is no way to look at a deal and know whether it matters strategically. That is a fact about
the company's plans, not about the deal. So the plugin reads a fact the **capability** names (a list
of initiative or goal ids the entity is tagged with) and scores it against a weight table the
**capability** authors. Without both halves it contributes nothing — *"rather than guessing that
untagged work is unimportant."*

One id gets special treatment. Linkage to the capability's **own** declared goal is strategic by
definition — the capability exists to move that goal — so it carries a configured default even when
the author never listed the goal in the weight table.

---

## 2 · The code

```python
class StrategicLinkagePlugin:
    plugin_id = "strategic_linkage"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        field = str(view.config.get("strategic_link_field") or "").strip()
        if not field:
            return ()
        raw = fact_value(view.request, field)
        if raw is None:
            return ()
        items = raw if isinstance(raw, (tuple, list)) else (raw,)
        links = tuple(sorted({str(item).strip() for item in items if str(item).strip()}))
        if not links:
            return ()
        weights = _mapping_config(view, "strategic_goal_bp")
        table = {str(key).strip(): weights[key] for key in sorted(weights)}
        goal_id = view.request.capability.goal.goal_id
        scores: list[int] = []
        codes: list[str] = []
        for link in links:                  # links are sorted, so the scan is order-independent
            if link == goal_id:
                strength = _config_bp(view, "goal_alignment_bp", 6_000) if link not in table \
                    else clamp_bp(_delta_bp(table[link], f"strategic_goal_bp.{link}"))
                codes.append("linked_to_capability_goal")
            elif link in table:
                strength = clamp_bp(_delta_bp(table[link], f"strategic_goal_bp.{link}"))
                codes.append("linked_to_strategic_initiative")
            else:
                continue                    # an untagged initiative is unweighted, not zero-weight
            scores.append(strength)
        if not scores:
            return ()
        return (Observation(
            plugin_id=self.plugin_id,
            kind="impact.strategic_linkage",
            metrics={"strength_bp": max(scores), "linked_goal_count": len(scores)},
            evidence_ids=evidence_ids(view.request, field),
            reason_codes=tuple(codes),
        ),)
```

### 2.1 · Config keys

| Key | Type | Default | Validated by | Effect |
|---|---|---|---|---|
| `strategic_link_field` | str | `""` | `str(... or "").strip()` | which fact holds the tags. **Empty ⇒ the plugin is entirely off** — this is the only one of the three plugins with a hard off switch |
| `strategic_goal_bp` | mapping id → int | `{}` | `_mapping_config`, then `_delta_bp` per matched key | the price of each initiative |
| `goal_alignment_bp` | bp 0–10,000 | `6_000` | `_config_bp` | the price of the capability's **own** goal when it is not in the table |

Unlike `account_importance`, the two mapping keys are **not** both required: with
`strategic_link_field` set and `strategic_goal_bp` empty, the plugin can still fire — but only on
the capability's own `goal_id`, priced at `goal_alignment_bp`.

### 2.2 · Normalisation, and where it differs from the tier plugin

```python
links = tuple(sorted({str(item).strip() for item in items if str(item).strip()}))
table = {str(key).strip(): weights[key] for key in sorted(weights)}
```

Both sides are `.strip()`ed and **not** `.lower()`ed. Initiative ids are machine identifiers, not
human labels — `expand_enterprise` — so casing is meaningful and folding it would merge two distinct
initiatives. Tier labels are the opposite case, which is why
[`account_importance`](03a-plugin-account_importance.md) lowercases and this one does not. The
asymmetry is deliberate and undocumented in the source; it is worth knowing before someone
"harmonises" them.

Three determinism devices in those two lines:

- **`set` then `sorted`** on the links: duplicate tags collapse, and the scan order is
  alphabetical rather than whatever order the CRM emitted.
- **`sorted(weights)`** on the table build: a post-`strip()` key collision resolves the same way on
  every machine (last sorted key wins).
- **Order-independent result** as a consequence: `max(scores)` and `len(scores)` do not depend on
  the scan order at all, but `codes` does — and `Observation.__post_init__` sorts and dedups it.

---

## 3 · The arithmetic

```text
per link:  goal_id match, not in table  →  strength = goal_alignment_bp        (0..10,000)
           goal_id match, in table      →  strength = clamp_bp(table[link])
           in table only                →  strength = clamp_bp(table[link])
           neither                      →  skipped entirely — no score, no code, no count

strength_bp       = max(scores)
linked_goal_count = len(scores)
```

**The strongest single linkage sets the level.** Not the sum, not the mean:

> *"A deal attached to five minor initiatives is not more strategic than one attached to the
> company's stated priority; summing would say otherwise."*

Summing would let five 2,000bp tags manufacture a maximal strategic claim out of five minor ones.
Averaging would let a `logo_refresh` tag drag down a deal that is genuinely attached to the
company's stated priority. Max says: *the strongest declared linkage is the linkage.*

`linked_goal_count` is the corroboration signal that max throws away. It counts **priced** links
only — an unpriced tag is skipped before `scores.append` — so it answers *"how many of this
entity's tags did the capability actually have an opinion about?"*, which is a statement about the
completeness of the weight table as much as about the deal.

`clamp_bp` after `_delta_bp` is where the two validators disagree and the clamp resolves it:
`_delta_bp` permits −10,000..10,000, and `clamp_bp` folds anything negative to **0**. So unlike the
tier path — which discards a negative weight and falls back — a negative `strategic_goal_bp` weight
becomes a scored **0** that still counts. Verified: `{"cost_cutting": -2000}` on a matching tag gives
`{'strength_bp': 0, 'linked_goal_count': 1}` with `reason_codes = ("linked_to_strategic_initiative",)`.
Two plugins in the same module treat a negative authored weight two different ways, and neither
tells the author.

---

## 4 · Exactly when it stays silent

| # | Condition | Source rationale |
|---|---|---|
| 1 | `strategic_link_field` unauthored, empty, or whitespace | *"Untagged work is unclassified, not unimportant, so an unconfigured unit says nothing"* — pinned by `test_strategic_linkage_stays_silent_until_the_capability_names_the_field` |
| 2 | the named field is absent, or present with value `None` | nothing was tagged |
| 3 | every item is empty or whitespace after `strip()` | `links` is empty |
| 4 | **no** link is either the capability goal or a key of `strategic_goal_bp` | *"an untagged initiative is unweighted, not zero-weight"* — `scores` is empty, so `()` |

Condition 4 is the interesting one. A deal tagged with three initiatives the author never priced
produces **no observation at all** — not a zero. The plugin refuses to convert *"I have no opinion
about these initiatives"* into *"these initiatives are worth nothing"*, which is exactly the
distinction the unit's whole silence rule is built on.

---

## 5 · Worked examples

### 5.1 · The strongest linkage wins, and unpriced tags do not count

```text
config  strategic_link_field = "deal.initiatives"
        strategic_goal_bp    = {"expand_enterprise": 8000, "logo_refresh": 1000}
facts   deal.initiatives     = ("logo_refresh", "expand_enterprise", "unpriced_pilot")
goal_id grow_enterprise_arr

links = sorted({"logo_refresh", "expand_enterprise", "unpriced_pilot"})
      = ("expand_enterprise", "logo_refresh", "unpriced_pilot")

scan
  "expand_enterprise"  != goal_id, in table  → 8000, code linked_to_strategic_initiative
  "logo_refresh"       != goal_id, in table  → 1000, code linked_to_strategic_initiative
  "unpriced_pilot"     != goal_id, not in table → continue   (no score, no code, no count)

scores = [8000, 1000]
strength_bp       = max(scores) = 8000
linked_goal_count = len(scores) = 2          # NOT 3 — the unpriced one is invisible
reason_codes      = ("linked_to_strategic_initiative",)   # deduped by Observation.__post_init__
```

Pinned by `test_the_strongest_linkage_sets_the_level_rather_than_the_sum` — *"Five minor initiatives
do not outweigh one company priority."* The test asserts `linked_goal_count == 2` explicitly, with
the comment *"the unpriced one is not counted"*.

### 5.2 · The capability's own goal, unlisted

```text
config  strategic_link_field = "deal.initiatives"
        goal_alignment_bp    = 7000
        (no strategic_goal_bp at all)
facts   deal.initiatives     = ("grow_enterprise_arr",)
goal_id grow_enterprise_arr

table = {}                                  # _mapping_config returns {} for a missing key
scan
  "grow_enterprise_arr" == goal_id, and NOT in table
    → strength = _config_bp(view, "goal_alignment_bp", 6000) = 7000
    → code linked_to_capability_goal

strength_bp 7000 · linked_goal_count 1 · reason_codes ("linked_to_capability_goal",)
```

Pinned by `test_linkage_to_the_capabilitys_own_goal_counts_without_being_listed` — *"The capability
exists to move that goal, so work attached to it is strategic already."* With the key unauthored the
strength would be the **6,000bp default**.

Note the branch order: if the author *does* list the goal in `strategic_goal_bp`, the table wins and
`goal_alignment_bp` is never read. Verified: `strategic_goal_bp = {"grow_enterprise_arr": 3000}`
gives `strength_bp = 3000` with code `linked_to_capability_goal`. An author can price their own goal
*below* the default, and the reason code still says the linkage is to the capability goal.

### 5.3 · Goal and initiative together — both codes, one level

```text
config  strategic_link_field = "deal.initiatives"
        strategic_goal_bp    = {"expand_enterprise": 8000}
facts   deal.initiatives     = ("grow_enterprise_arr", "expand_enterprise")

links = ("expand_enterprise", "grow_enterprise_arr")     # sorted
scan
  "expand_enterprise"   in table  → 8000, linked_to_strategic_initiative
  "grow_enterprise_arr" == goal_id, not in table → 6000 (default), linked_to_capability_goal

scores = [8000, 6000]
strength_bp       = 8000
linked_goal_count = 2
reason_codes      = ("linked_to_capability_goal", "linked_to_strategic_initiative")   # sorted
```

Verified against the live plugin. Both codes reach the `Finding` and the result's `reason_codes`
union, so an auditor can see that the deal was attached to the capability's goal *and* to a separate
priced initiative, even though only one of them set the level.

### 5.4 · Scalar and list read identically

```text
facts   deal.initiatives = "expand_enterprise"       # a bare string
items   = ("expand_enterprise",)                     # wrapped by the isinstance guard
→ identical metrics to  deal.initiatives = ("expand_enterprise",)
```

Pinned by `test_a_single_string_link_is_read_the_same_as_a_one_item_list` — *"Layer 2 emits scalars
and lists for the same field; the reading must not depend on shape."* Without the
`isinstance(raw, (tuple, list))` guard, a bare string would iterate character by character and
produce a set of one-letter "links", none of which would match anything.

### 5.5 · Whitespace and duplicates collapse

```text
facts   deal.initiatives = ("  expand_enterprise ", "expand_enterprise", "  ", "")
config  strategic_goal_bp = {"expand_enterprise": 8000}

set comprehension: strip each, drop the falsy ones, dedup
links = ("expand_enterprise",)
strength_bp 8000 · linked_goal_count 1
```

Verified. Four tag entries become one link. `linked_goal_count` reports **1**, not 4 — it counts
distinct priced links, not rows.

---

## 6 · Edge cases

| Input | Result | Note |
|---|---|---|
| `strategic_goal_bp = {"cost_cutting": -2000}`, tag matches | `strength_bp 0`, **counted**, code emitted | `clamp_bp` folds the negative to 0. Diverges from the tier plugin, which discards a negative and falls back |
| `strategic_goal_bp = {"x": 20000}`, tag `x` | `ValueError: strategic_goal_bp.x must be an integer between -10000 and 10000` → `FAILED` | raised only when that specific tag is present — an unpriced-in-practice bad weight lies dormant |
| `goal_alignment_bp = 11000` | `ValueError: goal_alignment_bp must be integer basis points` | only reached when the goal id is actually tagged and not in the table |
| `strategic_goal_bp` is a list | `ValueError: strategic_goal_bp must be a mapping` | from `_mapping_config` |
| `strategic_goal_bp = {"  expand_enterprise  ": 8000}` | key is stripped at table build; matches the stripped link | |
| `strategic_goal_bp = {"a": 1, "A": 2}` | **no** collision — keys are not lowercased | unlike `account_tier_bp` |
| Tag list contains a non-string, e.g. `42` | `str(42)` → `"42"`; matches only if the table has key `"42"` | no type error |
| Tag list contains a nested list | `str(["a"])` → `"['a']"` — will not match; effectively skipped | Layer 2 does not emit nested tags |
| `raw` is a `Mapping` | not `tuple`/`list`, so wrapped as one item and `str()`ed — junk, will not match | `fact_value` already unwrapped any `{"value": ...}` shell |
| `raw` is a `set` | impossible — `ContextSnapshot.__post_init__` runs `facts` through `contracts/reasoning.py:_freeze`, which converts a `set`/`frozenset` to a tuple ordered by each item's `semantic_hash` | the ordering is stable but not alphabetical; it does not matter here, because this plugin re-sorts the links itself |
| Field configured, tags present and priced, but no `EvidenceRef` on the field | observation fires with `evidence_ids = ()` | the reading is real; the citation is missing |

---

| ← | → |
|---|---|
| [03b · revenue_exposure](03b-plugin-revenue_exposure.md) | [04 · Calculator](04-Calculator.md) |
