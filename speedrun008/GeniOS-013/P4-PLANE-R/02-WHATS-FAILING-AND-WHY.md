# P4 · Plane R · 02 · What's failing, and why

"Us" means the AI sessions that built the product and the notebook; "mine" means this notebook's own code. None of these is a misunderstanding by Rohit.

---

## F1 · Reasoning rules live in prompt text, three different copies

- **Evidence:**
  - the expert prompt's rules and checklist;
  - the L2 prompt, built on it;
  - the notebook's hand-written judge prompt.

  They disagree. The product says "the playbook is **a prior** about this kind of work, not a fact about this file". The notebook said "the playbook, when printed, is **more specific**". A rule in prompt text can't be tested by itself, can't be reviewed, and drifts.
- **Cause:** every step wrote the rules it needed into its own prompt. Plane R never got a written library of reasoning patterns like Plane D's rules of thumb.
- **Whose:** us (product), and **mine** (notebook).

## F2 · The notebook told the model the playbook wins

- **Evidence:** the notebook's prompt said "apply it; the playbook, when printed, is more specific". With the playbook's "after a first call, silence is usually a soft no" shown without its condition (P3 F2), the model judged two investor conversations as "their move, soft no". Those were the follow-up we owed after a call (`i3`) and the question we hadn't really answered (`i2`).
- **Cause:** I wrote a precedence I had not thought through. The product's own rule was the right one.
- **Whose:** **mine**.

## F3 · The notebook has no calculators, so the model does arithmetic and reads the clock itself

- **Evidence:**
  - **The clock:** at 07:10 company time (01:40 UTC) the model read an 11:30 panel as happening now (`f1`).
  - **Whose turn:** it misread who owed the next move on a stalled introduction (`b3`). It said we owed new times, when the last asks were to them.

  The product's L2 tool gateway computes exactly these: whose turn, time since, nearest due and passed, how many of their messages are waiting.
- **Cause:** the notebook was built without porting the tools.
- **Whose:** **mine**.

## F4 · The 23 units are outside the model paths

- **Evidence:** the expert pass uses one unit (constraint). The L2 pass uses none, although its tool gateway was built to carry their useful arithmetic.
- **Cause:** when cards moved to the model (the expert pass, 18 Oct), the units stayed where they were: scoring for the compiled lane.
- **Whose:** us (architecture). The direction already chosen (L2-H1: "their arithmetic as evidence, their scores not") is right, and unfinished.

## F5 · No reasoning across situations, and none about goals

- **Evidence:**
  - the accelerator page never learned that the incubator's final review was that day. The film's own example (`i1`) became the opposite call;
  - no goal is reasoned about as a goal, so no goal says what is missing. That is how `f3` was missed (a referral silent for 24 days);
  - the product has no goal reasoning at all.
- **Cause:** both designs judge one situation at a time; links come from one relate call.
- **Whose:** us, and **mine** (design).

## F6 · Absence is forbidden in the product's dossier

- **Evidence:** the L2 dossier tells the model the read was cut short, so it must "never say something is absent". The founder's best intelligence is absence: a reply that never came, a follow-up never sent. When unsure, the brain chose "find out" in 41 of 86 results.
- **Cause:** a reasonable caution about partial reads, turned into a blanket rule.
- **Whose:** us (design). The notebook replaced it with "an absence is a finding when the source was fully read".

## F7 · A model can't see "multidimensional patterns" one situation at a time

- **Evidence:**
  - the notebook raised about 15 separate "send a follow-up after the call" cards. The pattern ("you rarely follow up after calls") was never said once;
  - the numbers conflict was found by code (claims), not by reasoning;
  - the product has company patterns (behaviour, adaptive leases, the founder's own stage durations), and the notebook has none.
- **Cause:** no correlate or analyse step over many pages (Maintain doesn't exist; P1 F5).
- **Whose:** unfinished.

## F8 · The model reads wrongly even when everything is there

- **Evidence:**
  - a renewal was filed as noise although the prompt said a renewal within 7 days is a decision (`c2`);
  - partner calls were marked "done" although the prompt said the follow-up after a call is ours (`b2`).
- **Cause:** a rule competing with a hundred other lines of prompt, with no citation and no check. Plus missing expertise (P3 F1, F4).
- **Whose:** the model, made likely by F1 and P3. Fixed by selection, citation and checks (P4-5), not by more prompt lines.

## F9 · The answer had to shrink to fit the API

- **Evidence:** the full page returned "The compiled grammar is too large". The six confidence words, links and per-loop reasons were dropped.
- **Whose:** an API limit, found by test.

---

## Summary

| Failure | Whose | Kind |
|---|---|---|
| F1 rules in three prompts | us, mine | architecture, process |
| F2 the playbook wins | mine | prompt |
| F3 no calculators, UTC | mine | not ported |
| F4 units outside the model paths | us | architecture, unfinished |
| F5 no cross-situation or goal reasoning | us, mine | design |
| F6 absence forbidden | us | design |
| F7 no patterns across pages | unfinished | not built |
| F8 misreads | model | made likely by F1 and P3 |
| F9 grammar limit | API | found by test |
