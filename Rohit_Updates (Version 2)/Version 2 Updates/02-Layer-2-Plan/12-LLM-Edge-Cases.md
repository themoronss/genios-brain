# L2 — LLM Edge Cases

> The nine LLM sites in Layer 2 each have a way of being wrong. This document names them
> and states the mitigation for each. **A site whose failure mode is not written down here
> is not ready to ship.**

---

## The asymmetry that governs every threshold

**In Layer 2 the two directions of error do not cost the same:**

| Error | Cost |
|---|---|
| **Missing** something (no resolution detected, no merge, no correlation) | one unnecessary nudge, or a slightly noisier queue |
| **Inventing** something (false resolution, wrong merge, false correlation) | **the founder loses a live thread and never learns it happened** |

Globe puts it exactly: *"A cancelled nudge costs nothing. A wrong one costs trust, and
trust is the only thing this product actually sells."*

**Therefore every confidence threshold at every site leans toward doing less.** Where this
document has to choose, it chooses the miss.

---

# M-4 · Resolution detection — the most dangerous site

A false positive here **closes a live thread**. Nothing else in Layer 2 can do that.

| # | Case | What goes wrong | Mitigation |
|---|---|---|---|
| **1** | *"we should wrap this up"* | intent read as completion → **premature close** | verdict requires a **completion statement**, not an intention. Forward-looking modals (`should`, `will`, `let's`) are a hard negative signal |
| **2** | 3 of 5 commitments done | whole situation closes, 2 obligations vanish | **`PARTIALLY_RESOLVED`** is a distinct state. Scope is per-obligation, never per-situation |
| **3** | Vendor writes *"all done on our side"*, org disagrees | wrong close on a counterparty's claim | **speaker-authority weighting**: owner 1.0 · internal 0.8 · external 0.6 · service account **ignored** |
| **4** | *"well that's sorted then 🙄"* | sarcasm read literally | never auto-close on a **single short message**; low confidence → human review queue |
| **5** | Thread: *"done"* … later *"actually not yet"* | stale close persists | **latest statement wins**; a `CONTRADICTED` verdict reopens, like `RESOLVED_BY_FACT` does |
| **6** | **Hinglish**: *"ho gaya"*, *"kal kar denge"*, *"done kar diya"* | missed entirely, or *"kal kar denge"* (future) read as done | the codebase is **already multilingual** — `triage.py` carries `jaldi\|turant\|kal\|parso`. The prompt must accept mixed script, and the **golden set must include Hinglish resolutions and Hinglish future-tense near-misses** |
| **7** | Auto-reply: *"Your ticket has been resolved"* | a bot closes a real situation | service accounts ignored at the gate, before any call |
| **8** | Resolution of a *different* thing in the same thread | one obligation's close applied to another | scope must name the obligation; an unscoped verdict is rejected |
| **9** | Budget exhausted | silent miss | **falls back to `terminal_by_fact`** and **logs** |

**The structural guard behind all nine:** `RESOLVED_BY_STATEMENT` is **reversible by
design** — re-derived every pass, and it un-resolves itself when contradicted. So even a
wrong close is recoverable on the next drain, which is the same property
`RESOLVED_BY_FACT` already has and for the same stated reason.

---

# M-6 / M-7 · Situation framing and timeline

| # | Case | What goes wrong | Mitigation |
|---|---|---|---|
| **10** | Model asserts a fact not in the members | a confident card with a fabricated detail | **span-constrained**: every noun must trace to a supplied fact. Unsupported → validation fails → **deterministic template headline** |
| **11** | Framing contradicts the matched pattern conditions | the card says something the evidence does not | **pattern conditions are authoritative.** Framing describes them; it cannot override them |
| **12** | A number drifts in the prose (\$84K → \$84,000,000) | wrong money on a card | **numbers are templated in, never generated.** The model picks the sentence; the values are substituted |
| **13** | Timeline omits the decisive event | the story reads wrong | selection is the model's; **the full chronology stays available** and the card can expand to it |
| **14** | Framing leaks a fact from outside the situation's visibility | **cross-audience leak** | framing input is filtered by `narrowest()` visibility **before** the call — the model never sees what the recipient may not |

**Case 14 is the one to build the test for first.** It is the only edge case in this
document with a data-leak consequence rather than a trust consequence.

---

# M-1 · Entity linking

| # | Case | Mitigation |
|---|---|---|
| **15** | Model says "same", deterministic said "different" | **deterministic wins.** M-1 fires *only* on inconclusive cases — never to overturn a decided one |
| **16** | Model proposes a wrong merge | goes to `merge_proposals` → **human review**. Never auto-applied |
| **17** | Two people genuinely share a name | the model must cite distinguishing evidence; without a citable reason the proposal is not created |
| **18** | Model output is a similarity score | **rejected by contract.** `identity.py`'s law holds: no unexplainable similarity. The output must be a reason, not a number |

**Case 18 is why this site does not violate the identity law.** The law forbids
*unexplainable similarity*, not the LLM. A model that must cite evidence into a
human-reviewed proposal satisfies it; a cosine score never can.

---

# M-3 · Conversation matching · M-5 · Condition parsing · M-8 · Clustering

| # | Case | Site | Mitigation |
|---|---|---|---|
| **19** | Two threads about the same customer but different deals get merged | M-3 | subject **and** entity must both align; a shared account alone is not enough |
| **20** | Condition parsed into a predicate that is subtly wrong | M-5 | predicate is stored **with the original text**; a satisfied condition shows both, so a human can see the translation |
| **21** | Rhetorical condition (*"call me when you're serious"*) parsed and fired | M-5 | only `is_conditional` commitments with a **checkable** predicate auto-fire; the rest are review-only |
| **22** | Clustering merges two unrelated realities | M-8 | **under-merge is the safe direction.** Three cards about one thing is noise; one card about three things is wrong |
| **23** | Clustering churns — merge, split, merge | M-8 | a merge decision is **sticky** for 7 days unless contradicted by a fact |

---

# M-9 · Cohort predicate authoring

| # | Case | Mitigation |
|---|---|---|
| **24** | Predicate matches 2,000 accounts | **population preview before approval** |
| **25** | Predicate excludes the named reference account | if the founder said *"like Acme"* and Acme is not in the result, the predicate misunderstood — **surface it, do not store it** |
| **26** | References an unregistered fact | raises at **definition** time, not silently at evaluation |
| **27** | Founder approves without reading | preview shows the count **and five named sample members** |
| **28** | Predicate encodes a protected attribute | rejected — the same governance the learning layer applies (Globe Rule 09) |

**Case 28 matters more than it looks.** A cohort is a segment, and a segment predicate is
exactly where a protected attribute would silently enter the product's decision-making.
Reject it at authoring time, where it is visible, rather than discovering it in a review.

---

# Cross-cutting rules

Applying to all nine sites, enforced in review:

1. **No `_bp` output, ever.** No LLM at L2 produces a number that feeds ranking.
2. **No visibility decisions.** The model never widens an audience; input is
   visibility-filtered before the call.
3. **Deterministic first, always.** If a rule can settle it, the model does not see it.
4. **Every site has a logged fallback**, and every fallback degrades toward doing less.
5. **Span-constrained wherever a claim is made.** Reuse L1's `ALG-08` validator; do not
   write a second one.
6. **Multilingual by default.** The corpus is Hinglish-bearing. Every golden set includes
   mixed-script fixtures.
7. **Confidence floor → human review queue**, never a card.

---

## Golden-set requirements

Each site ships with hand-labelled fixtures before it activates for any tenant:

| Site | Minimum fixtures | Must include |
|---|---|---|
| **M-4** | **40** | all 9 cases above, **≥8 Hinglish**, ≥5 sarcasm/negation, ≥5 partial resolutions |
| M-6 | 25 | cases 10–14, ≥3 with a visibility boundary |
| M-1 | 20 | cases 15–18, ≥3 same-name-different-person |
| M-3 | 15 | cases 19, plus near-miss thread pairs |
| M-5 | 15 | cases 20–21, ≥5 unparseable |
| M-8 | 15 | cases 22–23 |
| M-9 | 10 | cases 24–28, including one protected-attribute attempt |

**Hard gates for every site:**
- **0 fabricated facts** — any claim not traceable to source is a hard fail
- **0 visibility leaks** — a hard fail
- **False-positive rate below the site's declared ceiling** (M-4: **2%**, the strictest,
  because its false positive closes a live thread)
