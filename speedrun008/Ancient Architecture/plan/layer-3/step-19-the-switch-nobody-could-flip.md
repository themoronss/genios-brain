# L3-19 · Turn it on — ⛔ the switch could not be flipped

**Needs Harsh:** ⛔ **one activation call when the comparison is done** · **Model:** none · **Migration:** none

> ## ✅ COMPLETE — 2026-09-25 · [findings](findings/step-19-the-switch-nobody-could-flip.md)
>
> +11 tests · 8/8 mutations · 0 regressions.
>
> ⛔ **`deliver/card_source.FEATURE = "cards_from_situations"` was a literal, and
> `platform/l4_activation.L4_FEATURES` did not contain it.** So `require_feature` **raised** on the
> name, no tenant could ever hold an activation row, and `_situation_lane` was `False` on every
> pass in production.
>
> ⛔ **The mirror image of the typo that function exists to catch** — a *reader* gating on a name the
> *writer* refuses. Invisible for the same reason: **`False` is a legal answer.**
>
> ⛔ **And a second copy had already drifted.** `intelligence_onboarding.L4_DEFAULT_FEATURES` was
> five literal strings whose comment claimed to follow `PRECONDITIONS`; `situation_reasoner` had
> joined the closed set and never joined that list, so `make_tenant_live` **silently never switched
> on the Context Reasoner.**
>
> ⛔ **Honest blast radius:** the lane **label**, not lost cards. `tally_source` counts the collapse
> ratio every sweep regardless of the flag, and routing is deliberately still per-signal until the
> criterion-5 comparison runs. What was unreachable was the switch itself.

## Done criteria

- [x] the feature registered with a wave, preconditions, a cross-layer precondition and an effect
- [x] ⛔ `CROSS_LAYER_PRECONDITIONS = ("l3_domain",)` — measured, not assumed: only the compiled
      lane writes `situation_id`
- [x] **one spelling** — `card_source.FEATURE` imports the constant
- [x] `L4_DEFAULT_FEATURES` derived; ⛔ **provisioning behaviour byte-identical**, pinned
- [x] every exclusion carries a reason, enforced
- [x] ⛔ the guard that would have caught it: every `FEATURE*` constant ⟷ the closed set
- [x] registration is **total** across all four tables, both directions
- [x] ⛔ the existing L2-5 pin caught the change and was **extended, never loosened**
- [x] ⛔ a blunt-grep in my own test found and replaced with a structural AST assertion
- [x] technique 3: **eight** mutations, all red
- [x] full suite: **0 regressions**

## ⛔ What Harsh must do, and when

**Nothing yet.** When the criterion-5 comparison has run for a pilot tenant, one call turns the lane
on for that tenant:

```python
activate(engine, org_id, feature="cards_from_situations", by="<name>")
```

⛔ **Check `missing_cross_layer_preconditions` first.** Without a live L3 domain nothing writes
`signals.situation_id`, so every card groups into the NULL bucket, reads UNINTERPRETED, and the
console still says `live`.
