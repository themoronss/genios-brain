# L3-10 · The residue kinds are closed

**Needs Harsh:** none · **Model:** none · ⛔ **Migration: none — the plan was wrong**

> ## ✅ COMPLETE — 2026-09-25 · [findings](findings/step-10-correlation-record.md) · ⛔ **Wave 3 complete**
>
> +7 tests · 13,244 passed · 0 regressions.
>
> ⛔ **Eighth premise wrong, and the record's design is better than the spec's.**
> `context/residue.py` answers *"what did this layer fail to explain"* as **current state, not a
> log** — it deletes a row when a reading covers the subject, so it cannot grow unbounded and needs
> no retention policy. **The spec warns about exactly that problem in its own design.**
>
> ⛔ **What was missing:** the four kinds were bare constants with no collection and no guard — and
> for this table the failure is one-way: **a kind that stops being recorded makes the sweep look
> more complete than it is.**

## Done criteria

- [x] `RESIDUE_KINDS` closed, guarded both ways — declared ⟷ recorded
- [x] `first_seen_at` may never be refreshed — the age is what makes it a queue
- [x] a capped pass must still say it capped
- [x] ⛔ correlation's **stated limitation** pinned, so the chimera cannot be "fixed" in
- [x] ⛔ the docstring's *"no clock"* claim tested as a **property**, not repeated as a sentence
- [x] technique 3: **five** mutations, all red, restore green
- [x] full suite: **13,244 passed · 14 pre-existing · 0 regressions**
