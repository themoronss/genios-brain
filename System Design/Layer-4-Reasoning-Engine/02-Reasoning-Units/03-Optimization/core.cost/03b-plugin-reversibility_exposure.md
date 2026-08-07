# 03b · Plugin `reversibility_exposure`

**Class:** `genios_engine/reason/reasoners/cost_unit.py:ReversibilityPlugin` (lines 178–205)
**Helper:** `cost_unit.py:_play_exposure` (lines 84–99)
**`plugin_id`:** `reversibility_exposure` · **`kind`:** `cost.exposure` · **runs second**
**Tests:** `test_exposure_reports_the_worst_play_because_the_choice_is_not_made_yet` ·
`test_a_read_only_roster_carries_no_exposure` ·
`test_human_approval_relieves_exposure_because_a_person_reads_it_first`

---

## 1 · The claim it makes

*What acting exposes the org to if it turns out to be the wrong call, independent of how hard it is
to do.*

From the helper docstring:

> *"Two things dominate: whether the play can be taken back, and whether it puts something in front
> of someone outside the org. A read-only play that turns out to be a mistake costs an apology; an
> irreversible outbound one costs a relationship."*

This is the cost that no amount of effort accounting shows. A one-step play can be the most dangerous
thing in the roster, and `step_effort` would price it at 1,200bp.

**It reports the roster's ceiling, not its average.** From the class docstring:

> *"this unit does not know which play will be chosen, so the exposure the capability carries is the
> exposure of the most dangerous thing it is allowed to do. Averaging would let two harmless
> read-only plays hide one irreversible outbound one."*

That asymmetry is deliberate and it is the mirror image of `step_effort`'s floor. Together they mean
`cost_bp` blends the cheapest play's effort with the dearest play's exposure and may describe no play
that exists. [04](04-Calculator.md) §3.2 argues why that is the right trade for a capability-level
ledger.

---

## 2 · When it stays silent

```python
plays = _plays(view)
if not plays:
    return ()
```

**Never, through a legally constructed manifest.** `CapabilityManifest.__post_init__` raises
`capability requires at least one play`, so `_plays(view)` is never empty and the guard is
unreachable defensive code.

The plugin therefore always emits exactly one observation, and `exposure_bp: 0` is always an
**evidenced** zero — *"nothing here can be got wrong in a way that cannot be undone"* — never an
absence. That is the opposite of `delay_cost`'s design, and correctly so: the roster is a manifest
property that is always fully known, whereas the age of a silence is a snapshot property that may not
be.

There is no per-play exemption and no config key that can suppress the observation.

---

## 3 · The full arithmetic

### 3.1 · Per play

```python
def _play_exposure(view: UnitView, play: PlayDefinition) -> int:
    exposure = 0
    if not play.read_only:
        exposure += _config_bp(view, "irreversible_exposure_bp", 6_000)
    if play.metadata.get("external_recipient_required") is True:
        exposure += _config_bp(view, "external_recipient_exposure_bp", 2_000)
    if "human_approval_required" in view.request.capability.policies:
        exposure -= _config_bp(view, "approval_backstop_relief_bp", 3_000)
    return clamp_bp(exposure)
```

```text
exposure = 0
         + irreversible_exposure_bp        6,000   if play.read_only is False
         + external_recipient_exposure_bp  2,000   if metadata["external_recipient_required"] is True
         − approval_backstop_relief_bp     3,000   if "human_approval_required" in capability.policies
         → clamp_bp, i.e. min(10,000, max(0, ·))
```

Three independent terms, two additive and one subtractive. The clamp is what makes the subtraction
safe: a read-only play under an approval policy computes `0 − 3,000 = −3,000` and publishes `0`.

### 3.2 · Across the roster

```python
exposures   = tuple(_play_exposure(view, play) for play in plays)
irreversible = sum(1 for play in plays if not play.read_only)
external     = sum(1 for play in plays
                   if play.metadata.get("external_recipient_required") is True)
code         = "irreversible_action_available" if irreversible else "roster_is_reversible"

metrics = {"exposure_bp": max(exposures),
           "irreversible_play_count": irreversible,
           "external_recipient_play_count": external}
```

`max` over per-play exposures — not `max` of the components, which would be a different and larger
number if the worst irreversible play and the worst external play were different plays. Verified:
a roster of `{read_only=False, external=False}` and `{read_only=True, external=True}` reports
`exposure_bp: 6,000`, not `8,000`.

### 3.3 · The three policy terms, argued

**Irreversibility, 6,000bp — the largest single charge in the unit.** `PlayDefinition.read_only`
defaults to `True`, and Layer 3 must opt a play out of it explicitly. The charge is set above the
external-recipient charge because *"a read-only play that turns out to be a mistake costs an apology;
an irreversible outbound one costs a relationship"* — the apology is recoverable and the relationship
may not be.

**External reach, 2,000bp.** Read as `play.metadata.get("external_recipient_required") is True`.
Three properties of that expression matter:

- `.get()`, not indexing — an absent key is a legitimate state here, unlike in
  `core.constraint:PermissionVerificationPlugin`, which indexes the same key and raises on absence
  because a declared `no_unverified_recipient` policy makes the declaration mandatory.
- `is True`, not truthiness — `1 is True` is `False` in Python, so `metadata={"external_recipient_required": 1}`
  contributes **nothing**. Verified.
- The same test governs `external_recipient_play_count`, so metric and charge cannot drift apart.

**The approval backstop, −3,000bp.** From the docstring:

> *"The human-approval policy earns relief because a person reads the thing before it leaves — the
> exposure is real but it is caught."*

The relief is capability-wide: one string in `capability.policies` relieves **every** play in the
roster, including plays a human would never see. That is a coarse instrument, and it is the right
coarseness only because `CapabilityManifest.__post_init__` requires a `human_approval_required`
capability to carry a required `core.constraint`, which then emits a per-play
`human_approval_boundary_missing` ELIMINATE for any play that does not declare the boundary. The
relief here is safe because a harder gate elsewhere removes the plays it would wrongly relieve.

`3,000 < 6,000` is the load-bearing inequality. Approval reduces the exposure of an irreversible play
to `3,000bp`; it does not zero it. A human can approve the wrong thing.

### 3.4 · Config keys

| Key | Default | Sign | Notes |
|---|---|---|---|
| `irreversible_exposure_bp` | `6_000` | `+` | applies when `play.read_only is False` |
| `external_recipient_exposure_bp` | `2_000` | `+` | applies when `metadata["external_recipient_required"] is True` |
| `approval_backstop_relief_bp` | `3_000` | `−` | applies when `"human_approval_required" in capability.policies` |

All three go through `_config_bp` and must be integers in `0..10_000`.

**The validator cannot express a negative knob.** `approval_backstop_relief_bp` is a subtraction
whose magnitude is validated as a non-negative basis-point value, so a deployment can only ever
*reduce* exposure with it. That is correct for what the key means today, and it means `_config_bp`
could not be reused unchanged for a relief knob that ought to be able to go either way. Recorded
because the asymmetry between the key's sign in the formula and its validated range is not obvious
from either side alone.

---

## 4 · Worked example 1 — a mixed roster

`test_exposure_reports_the_worst_play_because_the_choice_is_not_made_yet`. Two plays, no policies:

```text
capability.policies = ()

log_note     read_only=True   external absent
             0 + 0 − 0                                   = 0
send_intro   read_only=False  external=True
             6,000 + 2,000 − 0                           = 8,000

exposure_bp                   = max(0, 8,000)            = 8,000
irreversible_play_count       = 1
external_recipient_play_count = 1
code                          = "irreversible_action_available"
```

```text
Observation(plugin_id='reversibility_exposure', kind='cost.exposure',
            metrics={'exposure_bp': 8000, 'irreversible_play_count': 1,
                     'external_recipient_play_count': 1},
            evidence_ids=(), reason_codes=('irreversible_action_available',))
```

`8,000bp` means 0.80. Two harmless plays did not dilute one dangerous one — which is the whole point
of the `max`.

## 5 · Worked example 2 — the approval backstop, in three shapes

`test_human_approval_relieves_exposure_because_a_person_reads_it_first` plus the shipped run.

**A. One irreversible play, approval declared.**

```text
capability.policies = ("human_approval_required",)
send_intro   read_only=False, external absent
             6,000 + 0 − 3,000                           = 3,000
exposure_bp                                              = 3,000
```

**B. The shipped `sales.deal_cooling_full` roster.**

```text
capability.policies = ('evidence_required', 'human_approval_required',
                       'no_unverified_recipient', 'read_only')

clarify_next_step     read_only=True, external=False
                      0 + 0 − 3,000 = −3,000 → clamp     = 0
multithread_account   read_only=True, external=True
                      0 + 2,000 − 3,000 = −1,000 → clamp = 0
restore_momentum      read_only=True, external=True
                      0 + 2,000 − 3,000 = −1,000 → clamp = 0

exposure_bp                   = max(0, 0, 0)             = 0
irreversible_play_count       = 0
external_recipient_play_count = 2
code                          = "roster_is_reversible"
```

Two of three shipped plays reach an outside party, and the capability's published exposure is zero.
The 3,000bp backstop more than covers the 2,000bp external charge, and the clamp discards the
remainder. See §6.1 for why the reason code makes that harder to read than it should be.

**C. The full grid, verified.**

| `read_only` | `external_recipient_required` | policies | `exposure_bp` |
|---|---|---|---|
| `True` | absent | none | 0 |
| `True` | `False` | none | 0 |
| `True` | `True` | none | 2,000 |
| `False` | absent | none | 6,000 |
| `False` | `False` | none | 6,000 |
| `False` | `True` | none | **8,000** — the maximum reachable on defaults |
| `True` | absent | `human_approval_required` | 0 |
| `True` | `True` | `human_approval_required` | 0 — clamped from −1,000 |
| `False` | absent | `human_approval_required` | 3,000 |
| `False` | `True` | `human_approval_required` | 5,000 |

`8,000bp` is the ceiling on default config. `10,000bp` is reachable only by tuning the two additive
knobs above their defaults.

---

## 6 · Edge cases and gaps

### 6.1 · `roster_is_reversible` can fire on a non-zero exposure

```python
code = "irreversible_action_available" if irreversible else "roster_is_reversible"
```

The code keys on `irreversible`, which counts only `read_only is False`. It says nothing about the
external-recipient charge. Verified:

```text
one play: read_only=True, external_recipient_required=True, no policies

exposure_bp                   = 2,000
external_recipient_play_count = 1
reason_codes                  = ('roster_is_reversible',)
```

A reader taking the code at face value reads "nothing here can be got wrong in a way that cannot be
undone" while the ledger carries 2,000bp of exposure for a play that puts something in front of an
outsider. The metrics are correct and the code is a partial description of them. A third code —
`roster_reaches_outside`, or making the existing one conditional on `exposure_bp == 0` — would close
it. Not built, and no test covers this combination.

The shipped roster is exactly in this shape: `roster_is_reversible` alongside
`external_recipient_play_count: 2`. It happens to be honest there only because the approval backstop
drove exposure to zero.

### 6.2 · The clamp hides the size of the relief

`clamp_bp` runs per play, so a play whose relief exceeds its charges reports `0` rather than a
negative. Two consequences:

- `−3,000` and `−1,000` are indistinguishable in the output. A reviewer cannot tell from
  `exposure_bp: 0` whether the play was harmless or whether the backstop absorbed a real charge.
- The relief cannot leak across plays. Because the clamp is inside `_play_exposure` and the roster
  reduction is `max` over the already-clamped values, a very safe play can never pull the roster
  figure below zero and mask a dangerous one.

The second property is the one that matters, and it depends on the clamp being where it is. Moving
`clamp_bp` outside the per-play helper would not change any shipped number today but would remove
that guarantee.

### 6.3 · Every metadata shape

Verified against `read_only=True`, no policies:

| `metadata["external_recipient_required"]` | Charge | `external_recipient_play_count` |
|---|---|---|
| `True` | 2,000 | 1 |
| `False` | 0 | 0 |
| `1` | **0** | **0** — `1 is True` is `False` |
| `"true"` | 0 | 0 |
| `None` | 0 | 0 |
| key absent | 0 | 0 |

`core.constraint` treats the same key more strictly: it indexes rather than `.get()`s, and
`CapabilityManifest.__post_init__` enforces `isinstance(..., bool)` on every play whenever the
capability declares `no_unverified_recipient`. So a manifest that declares that policy cannot reach
the `1` or `"true"` rows above. A manifest that does **not** declare it can, and this unit will
silently price a truthy-but-not-`True` declaration at zero exposure.

### 6.4 · The rest of the boundary table

| Input | Behaviour |
|---|---|
| One play | `exposure_bp` is that play's exposure; `max` over a single element |
| Empty roster | `()` — unreachable, `CapabilityManifest` requires at least one play |
| `capability.policies` contains a policy name this unit does not know | ignored; only `human_approval_required` is tested |
| `human_approval_required` declared but the capability has no `core.constraint` | unreachable — `CapabilityManifest.__post_init__` raises `capability policies and play preconditions require a required core.constraint` |
| `irreversible_exposure_bp` set to `0` | irreversibility becomes free; the plugin still emits `irreversible_action_available` because the code counts plays, not basis points |
| `approval_backstop_relief_bp` set to `10_000` | every play reports `0`; the roster's exposure disappears entirely |
| `play.metadata` is empty | `.get()` returns `None`, `None is True` is `False` — no charge, no raise |

---

## Related

| File | Covers |
|---|---|
| [03 · Analyzer](03-Analyzer.md) | Execution order, and why `_play_exposure` runs twice per play |
| [03c · `step_effort`](03c-plugin-step_effort.md) | The mirror asymmetry — the roster's floor rather than its ceiling |
| [04 · Calculator](04-Calculator.md) §3.2 | Why `exposure_bp` is blended with `effort_bp` rather than added to it |
| [05 · Evaluator](05-Evaluator.md) §3.3 | Where `_play_exposure` is recomputed per play for the `cost_benefit` check |
| [../../01-Situation-Understanding/core.constraint/03a-plugin-permission_verification.md](../../01-Situation-Understanding/core.constraint/03a-plugin-permission_verification.md) | The stricter reading of `external_recipient_required` and `human_approval_required` |
