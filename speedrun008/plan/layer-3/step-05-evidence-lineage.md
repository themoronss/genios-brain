# L3-05 · Copies do not corroborate

**Needs Harsh:** none · **Model:** none · **Migration:** none

> ## ✅ COMPLETE — 2026-09-25 · [findings](findings/step-05-evidence-lineage.md)
>
> +6 tests · 13,204 passed · 0 regressions. ⛔ **Wave 1 complete.**
>
> ⛔ **THE PLAN'S HEADLINE CLAIM WAS FALSE.** *"Ten copies of one claim read as ten independent
> sources today"* — `src_count` is `count(distinct sr.source)`. Ten Gmail forwards are one system.
> The ladder was never fooled, and `evidence_score` had already fought the same argument, got it
> wrong once, fixed it, and pinned it.
>
> ⛔ **What was actually wrong was one word, duplicated and untested.** The `distinct` sat in two
> hand-written copies of one subquery that no test drove — every test supplies `src_count` as a
> literal — so deleting it would have pushed every fact to the top rung **with nothing failing.**

## Done criteria

- [x] the subquery has **one home**, referenced by both readers
- [x] `distinct` pinned; `count(sr.source)` refused
- [x] counted over `fact_id`, so corroboration survives a supersede
- [x] the three rungs pinned, and the authority path pinned as deliberate
- [x] ⛔ the cross-channel hole **declared** with a reason and a mover, not built
- [x] technique 3: **five** mutations, all red, restore green
- [x] full suite: **13,204 passed · 14 pre-existing · 0 regressions**
