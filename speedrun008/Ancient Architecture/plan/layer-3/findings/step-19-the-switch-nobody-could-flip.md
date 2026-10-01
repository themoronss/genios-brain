# L3-19 findings · the cutover switch could not be flipped

**2026-09-25** · +11 tests · 8/8 mutations caught · 0 regressions · **no migration**

---

## 1 · The defect

`deliver/card_source.py` held the activation name as a **literal**:

```python
FEATURE = "cards_from_situations"
```

`platform/l4_activation.L4_FEATURES` — the closed set `require_feature` validates against — was:

```
roster_v2 · ranking_v2 · bundle · critique · brief · situation_reasoner
```

**`cards_from_situations` is not there.** So:

- `require_feature("cards_from_situations")` **raised `ValueError`** → no tenant could ever hold an
  activation row for it;
- `deliver/pipeline._situation_lane` was therefore `False` on every pass, for every tenant, forever;
- `out["cards_lane"]` read `"signal"` permanently, whatever an operator did.

⛔ **This is the mirror image of the typo `require_feature` exists to catch.** Its docstring guards
against *"a row written under `bundel` that reads as an activated tenant and narrates nothing"* — a
**writer** using a name the set refuses. The undetected case is a **reader** gating on a name the
writer refuses, and it is invisible in exactly the same way, **because `False` is a legal answer.**

### 1.1 ⛔ The blast radius, stated precisely — because overclaiming it would be its own defect

My first draft of this file said the entire L2-7 cutover "ran zero times". **That is too strong and
I corrected it before publishing.**

- `tally_source` runs the collapse measurement on **every** sweep regardless of the flag, so
  `cards_from_situation` / `cards_uninterpreted` / `cards_from_signal` were always being counted.
- Card **routing** is deliberately still per-signal — L2-7's criterion 5 requires both paths counted
  on one sweep before either is retired.

**What was unreachable was the SWITCH.** The routing step — the next one — would have hit the
`ValueError` under deadline instead of now.

---

## 2 · A second copy that had already drifted

`platform/intelligence_onboarding.py`:

```python
#: Layer 4's features in wave order (`l4_activation.PRECONDITIONS`): each one's
#: prerequisites are switched on before it.
L4_DEFAULT_FEATURES = ("roster_v2", "ranking_v2", "bundle", "critique", "brief")
```

The comment **claims a derivation that did not exist**, and the list had already fallen behind:
`situation_reasoner` joined `L4_FEATURES` and `PRECONDITIONS` and **never joined this list**, so
`make_tenant_live` silently never switched on the Context Reasoner.

⛔ A second copy of a vocabulary does not announce that it has fallen behind.

---

## 3 · What was built

| change | note |
|---|---|
| `FEATURE_CARDS_FROM_SITUATIONS` in `l4_activation` | registered in `L4_FEATURES`, `FEATURE_WAVES` (`L2-7`), `PRECONDITIONS`, `EFFECTS` |
| `CROSS_LAYER_PRECONDITIONS[…] = ("l3_domain",)` | ⛔ **measured in L3-13**: only the compiled lane writes `signals.situation_id`, and it needs a live L3 domain. Switch the lane on without one and every card reads UNINTERPRETED while the console says `live` — the same "both true, together misleading" shape `ranking_v2` is annotated with |
| `card_source.FEATURE` imports the constant | **one spelling.** Two spellings of one name is how this happened |
| `L4_DEFAULT_FEATURES` derived from `L4_FEATURES` | minus `NOT_DEFAULT_ON`, which carries a **reason per exclusion** |

### 3.1 ⛔ Provisioning behaviour is byte-identical

`L4_FEATURES` minus `{situation_reasoner, cards_from_situations}` is
`("roster_v2","ranking_v2","bundle","critique","brief")` — **exactly the old literal, same order.**
The drift is removed with **zero** behaviour change. Pinned by
`test_provisioning_behaviour_is_unchanged_by_the_derivation`.

The exclusions are declared, not accidental:

- **`situation_reasoner`** — it spends a model call per admitted situation. A default-on switch that
  costs money per row is a bill a tenant never agreed to.
- **`cards_from_situations`** — it is a **cutover, not a feature.** Switching it on at provisioning
  would mean no tenant ever runs the comparison `COMPARISON_KEYS` exists for.

---

## 4 · ⛔ The guard that would have caught it

`test_every_feature_constant_in_the_engine_is_in_the_closed_set` — every module-level `FEATURE*`
string constant in `genios_engine`, read from the **AST at module scope**, must be in `L4_FEATURES`.
And the reverse: every registered name must be defined as a constant somewhere.

**`deliver/card_source.FEATURE` was the only such constant outside `platform/`.** One direction was
checked; the other was not. A closed set checked in one direction is half a guard.

---

## 5 · ⛔ The existing pin caught my change, which is the system working

`tests/test_l4_pilot_activation.py::test_the_five_features_are_the_plans_five_in_wave_order` went
red on the full-suite run. **That is not a regression — it is the guard doing its job.** Its own
docstring records that it *"refused `situation_reasoner` until it also had a wave, an effect and a
precondition row."* It refused mine on the same terms.

It was **extended, never loosened** — the tail stays exact
(`== ("situation_reasoner", "cards_from_situations")`) so an eighth feature cannot arrive quietly.

---

## 6 · Technique 3 — 8/8

| # | mutation | result |
|---|---|---|
| 1 | the feature leaves the closed set | ✅ RED |
| 2 | `card_source` spells it as a literal again | ✅ RED |
| 3 | the wave entry disappears | ✅ RED |
| 4 | the effect sentence disappears | ✅ RED |
| 5 | the cross-layer precondition disappears | ✅ RED |
| 6 | the onboarding defaults go back to a literal | ✅ RED |
| 7 | an exclusion loses its reason | ✅ RED |
| 8 | `require_feature` stops refusing | ✅ RED |

⛔ **And one blunt-grep in my own test, caught during the build.** The first spelling check counted
`"cards_from_situations"` anywhere in `card_source.py` and went red on correct code — `__all__`
exports a **function** with that name. Replaced with a structural assertion: `FEATURE`'s binding
must be an `ast.Name`, never an `ast.Constant`. Tenth occurrence of that family.
