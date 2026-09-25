# L3-06 · The heartbeat that notices what did not happen

**Needs Harsh:** none · **Model:** none · **Migration:** none

> ## ✅ COMPLETE — 2026-09-25 · [findings](findings/step-06-the-timer.md)
>
> +4 tests · 13,208 passed · 0 regressions.
>
> ⛔ **THE LOUDEST CLAIM IN THIS PLAN WAS FALSE.** *"Nothing evaluates when nothing arrives"* was
> written in five documents and presented as the second of three highest-value items in Layer 3.
> **Elapsed time is evaluated at four live levels** — a 6-hourly heavy tick over every org, per-rule
> cooldowns, `executions.next_check_at` with a real due query, and situations aging to dormant on
> time — and **the first was already pinned by a test.**
>
> ⛔ **`due_evaluation` and `next_evaluation` do return zero. They are not the names this system
> uses.** A grep for two invented words found none of a scheduler thread, a cadence in hours, a
> cooldown and a column called `next_check_at`.

## Done criteria

- [x] ⛔ **no timer built** — four exist; a fifth would be the over-scaffolding refused at L3-01, 03 and 05
- [x] the heavy tick may not take the light tick's shortcut
- [x] the light tick must keep taking it — **both directions**
- [x] the heavy tick keeps the four other clocks that ride it
- [x] the heartbeat stays bounded (the 3-day silent freeze of 2026-08-18)
- [x] the claim corrected **in place** across five planning documents
- [x] technique 3: **four** mutations, all red, restore green
- [x] full suite: **13,208 passed · 14 pre-existing · 0 regressions**
