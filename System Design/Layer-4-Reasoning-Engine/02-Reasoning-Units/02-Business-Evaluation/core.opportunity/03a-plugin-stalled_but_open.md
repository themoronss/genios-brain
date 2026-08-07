# Plugin · `stalled_but_open`

**Class:** `opportunity.py:StalledButOpenPlugin` (lines 69–86)
**`plugin_id`:** `stalled_but_open` — **first** in execution order
**`Observation.kind`:** `opportunity.stalled_but_open`
**Reason code:** `open_deal_without_momentum`
**Metrics emitted:** `strength_bp`
**Config keys:** none
**Depends on:** `core.temporal` publishing `drop_bp`

---

## 1 · The claim

> *"The deal is still winnable and nothing is happening to win it."*

That is the entire class docstring, and it is a two-part claim held in one sentence. Both halves
must be true for the plugin to speak:

| Half | Evidence | Why it is necessary |
|---|---|---|
| *still winnable* | `deal.status` is in an open-ended state | A closed-won deal has no headroom left to take; a closed-lost one has no headroom to take *here*. Reporting opportunity on either would put a card in front of a human about work that cannot be done |
| *nothing is happening* | `core.temporal` measured engagement decay | A deal that is open and actively progressing is not an opportunity, it is a deal. The gap only exists where momentum has gone |

Neither half is this plugin's own measurement. The status comes from the CRM through Layer 2; the
decay comes from `core.temporal`. What the plugin contributes is the **conjunction** — the
observation that the two are true simultaneously, which is the thing neither upstream source can
state on its own.

---

## 2 · The code, in full

```python
class StalledButOpenPlugin:
    """The deal is still winnable and nothing is happening to win it."""

    plugin_id = "stalled_but_open"

    def contribute(self, view: UnitView) -> tuple[Observation, ...]:
        status = str(fact_value(view.request, "deal.status") or "").lower()
        if status not in {"open", "active", "in_progress", "negotiation"}:
            return ()
        quiet_bp = view.prior_metric("core.temporal", "drop_bp", 0)
        if quiet_bp <= 0:
            return ()
        return (Observation(
            plugin_id=self.plugin_id,
            kind="opportunity.stalled_but_open",
            metrics={"strength_bp": clamp_bp(quiet_bp)},
            reason_codes=("open_deal_without_momentum",),
        ),)
```

Thirteen lines, two guards, no arithmetic of its own.

### 2.1 · Everything is hardcoded

| What | Value | Config key |
|---|---|---|
| Status fact path | `"deal.status"` | **none** |
| Open-state vocabulary | `{"open", "active", "in_progress", "negotiation"}` | **none** |
| Momentum source unit | `"core.temporal"` | **none** |
| Momentum metric name | `"drop_bp"` | **none** |
| Minimum firing decay | `> 0` | **none** |

Its siblings do not work this way. `impact_unit.py:AccountImportancePlugin` exposes
`relationship_reasoner` so a capability can point it at a different prior unit;
`tradeoff_unit.py:RiskVersusRewardPlugin` exposes `reward_source` for the same reason;
`relationship.py` exposes `neighbor_status_field` precisely so a capability can rename the status
fact. This plugin exposes nothing. A capability whose CRM stage vocabulary is `"qualified"` /
`"proposal"` / `"commit"` gets silence, with no diagnostic and no manifest-level remedy.

That matters less than it sounds today, because of what actually writes `deal.status`.

### 2.2 · What `deal.status` contains in production

Nothing in the CRM lane writes `deal.status`. `capture/structured/registry.py:65` maps HubSpot's
`dealstage` to **`deal.stage`**, and `reason/signals_derived.py:deal_facts` derives the status from
it at evaluation time:

```python
_STAGE_WON  = ("won", "closedwon", "closed_won")
_STAGE_LOST = ("lost", "closedlost", "closed_lost")

s = str(stage_f.get("value") or "").strip().strip('"').lower()
status = ("won"  if any(w in s for w in _STAGE_WON)
     else "lost" if any(w in s for w in _STAGE_LOST) else "open")
```

Three possible values: `"won"`, `"lost"`, `"open"`. **`"open"` is the catch-all** — every stage
that is not recognisably a close maps to it. So of the four vocabulary entries this plugin accepts,
exactly one is ever produced, and the other three (`"active"`, `"in_progress"`, `"negotiation"`)
are defensive width for a source that does not exist yet. Conversely the catch-all means the gate
is generous: a deal at `"appointmentscheduled"` reads as open.

`deal_facts` only fills `deal.status` when it is **absent**, so a CRM- or human-set value wins. The
plugin's `.lower()` handles casing from that path; it does **not** `.strip()`, so a value of
`"Open "` fails the set membership test. Verified: `"OPEN"` matches, `"Open "` does not.

### 2.3 · Where `drop_bp` comes from

`temporal.py:TemporalReasoner.evaluate`:

```python
engagement_bp = ratio_bp(value, engagement_field)      # derived.engagement, 0..10000
drop_bp = clamp_bp(10_000 - engagement_bp)
```

So `drop_bp` is *"how far engagement has fallen from perfect"*, already in basis points, already
clamped. `clamp_bp(quiet_bp)` on line 84 is therefore a provable no-op — `contracts/reasoning.py`
would have rejected a `drop_bp` outside 0..10,000 before it ever reached `prior_metric`. It is
belt-and-braces, and it also guards the case where a capability points `core.temporal` at a
different config and a future version widens the range.

`view.prior_metric` (`unit.py:128-134`) returns the default when the dependency did not run, did
not complete, or published a non-integer:

```python
result = self.prior.get(reasoner_id)
if result is None or result.status != ResultStatus.COMPLETED:
    return default
value = result.metrics.get(name, default)
return default if isinstance(value, bool) or not isinstance(value, int) else value
```

With `default = 0`, every one of those failure modes lands on the `quiet_bp <= 0` guard and the
plugin goes silent. It cannot mistake a missing dependency for healthy engagement, because both
produce the same silence — which is the correct conflation here, but see §5.

---

## 3 · The arithmetic

There is none. `strength_bp` **is** `drop_bp`, passed through:

```text
strength_bp = clamp_bp(prior_metric("core.temporal", "drop_bp", 0))
              where the branch is only taken when that value is > 0
              and clamp_bp is a no-op on any value the contracts already accepted
```

The design decision worth naming is that the plugin **borrows a number rather than deriving one**.
It would have been easy to compute a second, independent measure of momentum from `deal.status` and
some timestamp — and it would have been wrong, for the reason `cost_unit.py` states about the same
metric: *"the Opportunity Unit already priced it, so read it rather than re-deriving a second,
disagreeing estimate of the same thing."* Two units publishing two different numbers for one
concept is exactly what `validation_unit.py:ContradictionPlugin` exists to catch.

The cost of borrowing is that `stalled_but_open` reports its strength on `core.temporal`'s scale,
which is engagement decay, not opportunity size. A deal with engagement at 4,000bp yields 6,000bp
of "opportunity" whether it is a $5,000 deal or a $5,000,000 one. The magnitude of the stake is
`core.impact`'s job and is deliberately not folded in here.

---

## 4 · Worked examples

### 4.1 · The shipped capability — the only live plugin in production

`sales.deal_cooling_full` v2 against its fixture: a $500,000 deal, status open, engagement halved.

```text
snapshot   deal.status        = {"value": "open"}
           derived.engagement = {"value_bp": 4000}
prior      core.temporal COMPLETED

core.temporal
   engagement_bp = ratio_bp(4000) = 4000
   drop_bp       = clamp_bp(10000 - 4000) = 6000

stalled_but_open
   status = str("open" or "").lower() = "open"        ∈ the open set   → continue
   quiet_bp = prior_metric("core.temporal", "drop_bp", 0) = 6000
   6000 > 0                                                            → fire

   Observation(plugin_id="stalled_but_open",
               kind="opportunity.stalled_but_open",
               metrics={"strength_bp": 6000},
               reason_codes=("open_deal_without_momentum",))
```

That 6,000bp is the leader in `calculate`, and after the 1,000bp lift from
`unworked_relationship` it becomes the published `opportunity_bp = 7,000`. Verified against the
live orchestrator.

### 4.2 · Engagement collapsed — the end-to-end fixture

`tests/test_l4_end_to_end.py`: an open $250k deal with `derived.engagement_bp = 1,800`.

```text
core.temporal    drop_bp = clamp_bp(10000 - 1800) = 8200
stalled_but_open status "open" ∈ set, 8200 > 0 → strength_bp 8200
```

Combined with an inbound 216 hours old at 6,308bp:

```text
strengths sorted desc = [8200, 6308]
lift = half_up(6308 / 4) = (6308 + 2) // 4 = 6310 // 4 = 1577
opportunity_bp = clamp_bp(8200 + 1577) = 9777
```

Verified — which is what satisfies `test_the_units_actually_feed_each_other`'s assertion
`opportunity_bp > 8_000`.

### 4.3 · The two silence paths

```text
A · closed deal, decay present
    deal.status = "closed_won"      → "closed_won" ∉ the open set → return ()
    core.temporal drop_bp = 8200    → never read
    contribution: nothing. A won deal has no headroom to take.

B · open deal, engagement healthy
    deal.status = "open"            → passes
    core.temporal drop_bp = 0       → 0 <= 0 → return ()
    contribution: nothing. Momentum exists; there is no gap.
```

Both verified. Path B is the boundary: `drop_bp = 1` fires and produces
`opportunity_bp = 1, opportunity_count = 1` — technically an observation, arithmetically
meaningless, and correctly below any sane threshold.

### 4.4 · The dependency was never declared

```text
capability declares core.opportunity with dependencies = ()
   orchestrator passes prior = {}
   prior_metric("core.temporal", "drop_bp", 0) → 0
   → return ()

result: opportunity_bp 0, opportunity_count 0, matched False
        semantic_hash identical to a run where core.temporal FAILED,
        and identical to a run where the deal was closed
```

Verified across all three. There is no reason code, no `missing_fields` entry and no diagnostic
distinguishing *"the deal is fine"* from *"you forgot to wire up `core.temporal`."*

---

## 5 · Silence semantics

**Silent whenever either half of the claim is unproven.** Specifically:

| Condition | Silent? | Distinguishable downstream? |
|---|---|---|
| `deal.status` absent from the snapshot | yes — `str(None or "").lower()` is `""` | no |
| `deal.status` present but not in the vocabulary | yes | no |
| `deal.status = "Open "` — trailing whitespace | yes | no |
| `core.temporal` not declared as a dependency | yes | no |
| `core.temporal` ran but `status != COMPLETED` | yes | no |
| `core.temporal` published no `drop_bp` | yes | no |
| `drop_bp = 0` — engagement perfect | yes | no |
| `drop_bp > 0` on an open deal | **fires** | — |

Every silence path collapses to the same `()`. This is the conservative choice — the plugin never
claims an opportunity it cannot substantiate — but it means a wiring fault and a healthy deal are
indistinguishable from the outside. `core.impact` faces the identical problem with its
`core.relationship` dependency and solves it no better; the category README records it as a
recurring shape rather than a one-off.

The plugin never emits a zero-strength observation. A `drop_bp` of `0` produces `()`, not
`strength_bp: 0`, so it never inflates `opportunity_count`.

---

## 6 · Defects and compromises

| # | What | Severity |
|---|---|---|
| 1 | **No config key for anything.** The status path, the open-state vocabulary and the momentum source are all literals. A capability outside sales cannot use this plugin without editing Python. | medium |
| 2 | **`.lower()` without `.strip()`.** `"Open "` silently fails the membership test. CRM exports routinely carry padding. Compare `impact_unit.py`, which does `.strip().lower()` on both sides of its tier comparison. | low, and undiagnosable from the outside |
| 3 | **Three of four accepted status values are unreachable today.** `signals_derived.py:deal_facts` emits only `"won"`, `"lost"`, `"open"`. `"active"`, `"in_progress"` and `"negotiation"` are dead vocabulary unless a CRM writes `deal.status` directly. Harmless, but it makes the set look like a tuned list when it is a guess at a future source. | cosmetic |
| 4 | **The claim is correlated with `unanswered_inbound` and nothing accounts for it.** A deal is usually quiet *because* nobody replied, so the two plugins often fire off one underlying fact. The ÷4 lift in `calculate` bounds the double-count; it does not model it. See [03 · Analyzer](03-Analyzer.md) §4.4. | design note |
| 5 | **No evidence.** The `Observation` is built with no `evidence_ids`, so the `open_deal_without_momentum` finding cites nothing — not the `deal.status` fact it read, not the engagement fact behind `drop_bp`. `common.py:evidence_ids(view.request, "deal.status")` would supply the first in one line. | high — see [02 · Retriever](02-Retriever.md) §4 |
| 6 | **Unpinned.** No test asserts the vocabulary, either guard, or the pass-through. The only coverage is `opportunity_bp > 0` and `> 8_000` assertions two layers up. | process |

---

## 7 · Related

- [03 · Analyzer](03-Analyzer.md) — how this plugin composes with the other two
- [03b · `unanswered_inbound`](03b-plugin-unanswered_inbound.md) — the correlated sibling
- [04 · Calculator](04-Calculator.md) — where `strength_bp` goes
- `genios_engine/reason/reasoners/temporal.py` — the source of `drop_bp`
- `genios_engine/reason/signals_derived.py:deal_facts` — the source of `deal.status`
