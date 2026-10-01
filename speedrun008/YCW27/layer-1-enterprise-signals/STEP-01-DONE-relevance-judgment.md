# Step 1 — DONE · relevance judgment · owner: us

> **Status:** DONE — no defect found · a probe was built · **four hypotheses disproved**
> **Written:** 2026-09-30 from read-only production measurement
> **Evidence:** [`findings/step-01-relevance.md`](findings/step-01-relevance.md)
> **Artifact:** `scripts/l1_relevance_state.py`

---

## 1 · What was expected

`no_model_wired = 251` (later 632) was reported as *"Layer 1's relevance judgment is not running in
production"*. The expectation was a wiring defect, fixable in code.

## 2 · What the code actually does

| Hypothesis | Verdict | Why |
|---|---|---|
| no model wired | ❌ wrong | `wiring.py:793` builds `RelevancePage(llm=llm, …)` correctly |
| a one-line fix in `wiring.py` | ❌ wrong | `wiring.py` needs no change |
| the activation switch was never turned on | ❌ wrong | **LIVE since 2026-09-18**, by `system:onboarding` |
| a regression on 19–20 Sep | ❌ wrong | the three commits there are a memory trim and a cost-ledger widening |

## 3 · What was actually true

**The rule histogram had never been split by source.** Split, it resolves completely:

| Source | Rows | Judged by model | `no_model_wired` | Verdict |
|---|---|---|---|---|
| `gmail` | 141 | 65 | **0** | ✅ working |
| `gcal` | 55 | 0 | **0** | ✅ rules decide it; the model is never needed |
| `screen_session` | 632 | 0 | **632** | ✅ **by design** |

⛔ Every unjudged row is a screen session. `platform/screen_promoter.py:183`:

```python
# K3: S4's relevance page never re-asks a model what S2's one call (or the verdict)
# already answered for this screen object — at most ONE AI call per object.
semantic=None if instant else screen_semantic_lane(R._semantic_lane_for(org_id), gate),
```

The screen instant lane makes **one** AI call, at S2, inside a **3.5-second hard timeout**. It
deliberately does not build the S4 lane so it cannot buy a second call. Reaching S4 with no client
and failing open at authority 3000 is the designed outcome.

## 4 · Scenario → expected result

| Scenario | Expected | Observed |
|---|---|---|
| A Gmail message arrives, ambiguous to the rules | the model judges it; rule is `llm5_business` or `llm5_not_business` | ✅ 65 of 106 |
| A calendar event arrives | rules settle it; no model call | ✅ 55 of 55 |
| A screen page arrives on the instant lane | ONE model call at S2; S4 files `no_model_wired` and **keeps** the event at 3000 | ✅ 632 of 632 |
| The model is unreachable | the event is **kept**, never dropped | ✅ fail-open holds |

## 5 · What we built

`scripts/l1_relevance_state.py` — read-only, runs against any org.

- splits the histogram **by source**, because *"a bare rule histogram shows `no_model_wired` at 76%
  and reads as 'Layer 1's judgment is broken'. Split by source it reads as what it is."*
- carries `_MODEL_FREE_BY_DESIGN = {"screen_session"}` with the reason and the file reference, so a
  future reader cannot mistake the screen lane's budget guarantee for a defect and "fix" it
- separates `llm5_unavailable` (theirs) from `no_model_wired` (by design) in the verdict
- `--assert-judged` passes when every source is judged **or** model-free by design

```
.venv/bin/python scripts/l1_relevance_state.py --org <org>
.venv/bin/python scripts/l1_relevance_state.py --assert-judged
```

## 6 · What we did NOT do, and why

| Not done | Why |
|---|---|
| change `wiring.py` | it is correct |
| write an activation row | it exists and is live |
| "fix" `no_model_wired` on screen | it is a budget guarantee, not a defect. Changing it buys a second AI call inside a 3.5 s timeout |

## 7 · The lesson

> ⛔ **A rule count without its dimension is not a measurement.** `no_model_wired = 632` and
> `no_model_wired = 632, all of them screen_session` are the same number and opposite findings.

Four confident explanations, all wrong, and each would have produced a code change to a file that
was already correct.
