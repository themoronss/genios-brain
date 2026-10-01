# S1 — resolved. There was no relevance bug.

Measured 30 Sep 2026 with `scripts/l1_relevance_state.py` (unit **U-S1-01**), read-only, against
the pilot.

---

## The alarm

`no_model_wired = 251` (now 632) was read as *"Layer 1's relevance judgment is not running"*. Four
explanations were proposed and **every one of them was wrong**:

| # | Hypothesis | Why it was wrong |
|---|---|---|
| 1 | no model is wired in production | `wiring.py` builds `RelevancePage(llm=llm, …)` correctly |
| 2 | a one-line fix in `wiring.py` | `wiring.py` needs no change at all |
| 3 | the `l1_semantic_activation` switch was never turned on | it has been **LIVE since 18 Sep**, by `system:onboarding` |
| 4 | a regression introduced on 19–20 Sep | the three commits in that window are a memory trim and a cost-ledger widening; neither touches the decision |

## What it actually is

**The rule histogram was never broken down by source. Split by source it resolves completely:**

| Source | Rows | Judged by model | `no_model_wired` | Verdict |
|---|---|---|---|---|
| `gmail` | 141 | 65 | **0** | ✅ working, judged as recently as 30 Sep 03:39 |
| `gcal` | 55 | 0 | **0** | ✅ decided by rules alone — `structured_source`, `known_counterparty`. The model was never needed |
| `screen_session` | 632 | 0 | **632** | ✅ **by design** |

⛔ **Every single `no_model_wired` row is a screen session, and that is deliberate.**
`platform/screen_promoter.py:183`:

```python
# K3: S4's relevance page never re-asks a model what S2's one call (or the verdict)
# already answered for this screen object — at most ONE AI call per object.
semantic=None if instant else screen_semantic_lane(R._semantic_lane_for(org_id), gate),
```

The screen instant lane makes **one** AI call, at S2, inside a 3.5-second hard timeout. It
deliberately does not build the S4 semantic lane, so S4 cannot buy a second call. Reaching S4 with
no client and failing open at authority 3000 is the **designed** outcome.

**The apparent "it worked on 19 Sep then stopped" pattern was an artefact of the mix**: 19 Sep
carried a large Gmail backfill, and the traffic since has been mostly screen sessions.

## The one real defect this uncovered

```
gmail   llm5_unavailable   41
```

**41 of 106 Gmail model calls — 39% — were made and did not come back.** That is not a wiring
problem and activation will not fix it. `llm5_unavailable` means a client was present, the call was
issued, and it failed.

It fails open at authority 3000, so **nothing was lost**; 41 Gmail events reached Layer 2 unjudged.

## What was built

`scripts/l1_relevance_state.py` — the probe, corrected so it cannot raise this alarm again:

- breaks the histogram down **by source**, because *"a bare rule histogram shows `no_model_wired` at
  76% and reads as 'Layer 1's judgment is broken'. Split by source it reads as what it is."*
- carries `_MODEL_FREE_BY_DESIGN = {"screen_session"}` with the reason and the file reference, so a
  future reader cannot mistake the screen lane's budget guarantee for a defect and "fix" it
- separates `llm5_unavailable` from `no_model_wired` in the verdict, because they are different
  failures with different owners
- `--assert-judged` passes when every source is either judged or model-free by design

## What this does to the plan

| Unit | Status |
|---|---|
| `U-S1-01` the probe | ✅ **done.** It disproved four hypotheses, including two of its own author's |
| `U-S1-02` pin the fail-open | ✅ **still needed, and now clearly right** — 632 screen events depend on that fail-open every day |
| `U-S1-03` write the activation row | ❌ **withdrawn** — the row is live |
| `U-S1-04` assert the histogram moved | ❌ **withdrawn as written** — replaced by the per-source verdict, which is already in the probe |
| **new · `U-S1-05`** | **investigate `llm5_unavailable` at 39% on Gmail** — the only real defect here |

**S1 shrinks from four units to two**, and the section's premise changes from *"turn the judgment
on"* to *"Layer 1's judgment is on and correct; one call site is unreliable."*

## The lesson worth keeping

Four plausible explanations, each one confident, each one wrong — and all four would have produced
a code change to a file that was already correct. The measurement cost one script and twenty
minutes.

> ⛔ **A rule count without its dimension is not a measurement.** `no_model_wired = 632` and
> `no_model_wired = 632, all of them screen_session` are the same number and opposite findings.
