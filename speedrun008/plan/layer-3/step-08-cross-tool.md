# L3-08 · Cross Tool — and a draft is not a reply

**Needs Harsh:** none (⛔ **behaviour change, handoff §3.4**) · **Model:** none · **Migration:** none

> ## ✅ COMPLETE — 2026-09-25 · [findings](findings/step-08-cross-tool.md)
>
> +8 tests · 13,224 passed · 0 regressions.
>
> ⛔ **Sixth premise wrong.** *"Cross Tool is the only correlator with no module"* — there is no
> module because **the join does not need one**. Calendar attendees and email participants resolve
> to the **same person nodes by address**, and correlation anchors on the entity. That is stronger
> than the correlator the spec asks for: CT-01's test is that renaming the event keeps the
> association, and an identity join cannot break on a title.
>
> ⛔ **But CT-10 was live:** `direction_of` returned `outbound` for a draft, so **an unsent message
> counted as a reply** — `ball_in_court` flipped, waiting relationships read as answered, and the
> benchmark's *"zero emails in 28 days"* would have read *"you sent two"*.

## Done criteria

- [x] a draft no longer counts as our reply
- [x] a real send still does — the refusal is not a wall
- [x] ⛔ `None` (connector said nothing) behaves exactly as before
- [x] ⛔ drafts are **kept, not filtered** — a test pins `DRAFT` out of the junk labels
- [x] the label check is case-insensitive and refuses a bare string
- [x] technique 3: **five** mutations, all red, restore green
- [x] full suite: **13,224 passed · 14 pre-existing · 0 regressions**
