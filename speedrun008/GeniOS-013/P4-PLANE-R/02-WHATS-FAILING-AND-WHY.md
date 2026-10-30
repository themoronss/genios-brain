# P4 · Plane R · 02 · What's failing, and why

"Us" means the AI sessions that built the product and the notebook; "mine" means this notebook's own code. None of these is a misunderstanding by Rohit.

Every number is from [01](01-WHATS-EXACTLY-THERE.md): the product at `a729b968`, the local copy's first production week (22–28 Oct), and the notebook build `b2`. The failures keep their 29 Oct numbers (F1–F9; other parts cite them) and add F10–F19.

---

## F1 · Ways of thinking live in prompt text, in many copies

- **Evidence:**
  - the expert prompt: a 10-step checklist and 15 rules;
  - the L2 judge's prompt, built on it: 24 rules (2 of its own block rules, 14 of the expert's, 8 more) and a 20-step checklist;
  - the notebook's judge prompt: a 9-step order and 5 "chief of staff" rules;
  - and more: the test-mode decision maker's hedge and stance rules, the R-1 prompts, the brief drafter, the Screen insight rulebook and the narrator.

  They disagree. The product says "the playbook is **a prior** about this kind of work, not a fact about this file"; the notebook said "the playbook, when printed, is **more specific**". A rule in prompt text cannot be tested on its own, reviewed, cited, or measured, and it drifts.
- **Cause:** every step wrote the rules it needed into its own prompt. The Atlas's reasoning library (the `reasoning/` pack: versioned units in six groups, compiled into prompt fragments) was never built. The one authored hook, `domain.yaml` `reasoning:`, is used by no domain.
- **Whose:** us (product), and **mine** (notebook).

## F2 · The notebook told the model the playbook wins, and cut the playbook's conditions

- **Evidence:** the prompt's only precedence line says "the playbook, when printed, is more specific". The investor playbook's first-call note was then cut to 260 characters before printing, losing its own condition ("after one that named a step and a date, it is the firm's process until that date passes"), and the model blended two stages' notes. So two investor conversations were judged "their move, soft no": the follow-up we owed after a call (`i3`) and the question we had not really answered (`i2`). `i1` failed the same way: the generic "declined: re-apply at the next intake" stage beat the accelerator's written offer to reconsider.
- **Cause:** I wrote a precedence I had not thought through, and a renderer that cut what a rule needs. The product's own rule was the right one.
- **Whose:** **mine**.

## F3 · No calculators in the notebook; the product's prints UTC only

- **Evidence:**
  - **the notebook** shows the model no calculator at all. It reads UTC timestamps with no weekday and works out time, turns and gaps itself. At 07:10 company time (01:40 UTC), with a calendar row at 05:00 UTC (10:30 IST) and a mail slot at 11:30, the page was right twice and then, on a re-judge that leaned on its own earlier line ("essentially concurrent with this read-through"), asked "did you attend?" (`f1`). It misread who owed the next move on a stalled introduction, under a date labelled "stated" that no mail holds (`b3`);
  - **the product's** six tools are hours between instants, L1's ball-in-court, the nearest due date, unanswered inbound, days quiet and money. Every instant is printed in UTC; the company's time zone (`orgs.timezone`) is never read in `reason/l2` or `reason/expert`; 30 minutes past a due time prints "1 hours ago". Whose turn is L1's per-signal guess, not computed from the open loops. There are no lead times, working days, baselines or decision windows.
- **Cause:** the notebook was built without porting the tools; the product's gateway was built without the clock.
- **Whose:** **mine** (notebook); us (product).

## F4 · The 23 units decide nothing, and a model outside the register decides for them

- **Evidence:**
  - the units sit behind **77 of 111 cards** (36 from the compiled lane, 41 from the legacy pack lane);
  - their scores decide none of them: the **test-mode LLM decision maker** (Haiku, outside the register, no dollar cap, an in-process limit of 400 calls a day that saw 723 on 22 Oct) decided every compiled and legacy candidate, 242 of 242, shown only the units' reason codes;
  - many unit outputs are constants: impact empty on 43 of 43 runs, recommendation "0 supported plays" on 43 of 43, validation 4,000 bp on 43 of 43, confidence 6,250 bp on 36 of 43;
  - risk is still half-blind: relationship unmeasured on 43 of 43 risk results;
  - the model paths barely touch them: the expert path imports one unit and runs it after the model; the L2 judge imports none.
- **Cause:** when cards moved to the model (18 Oct), the units stayed as the compiled lane's scorers, and a test-mode model decider was put on top of them. GeniOS-008's "their arithmetic as evidence, their scores not" (L2-H1) is unfinished.
- **Whose:** us (architecture).

## F5 · No reasoning across situations, and none about goals as goals

- **Evidence:**
  - the accelerator page never learned that the incubator's final review was that day: the film's own example (`i1`) became the opposite call. In the notebook, relate made 3 "evidence for" links among 296 pieces of work, none of them this one;
  - the live judge writes a per-file goal impact (14 of 86 results) and at most one goal proposal (6 of 86), but no goal is judged as a goal: no target, plan, progress, status or next move. That is how `f3` was missed (a promised referral silent for 24 days, inside a pile of 30 threads);
  - nothing reasons across pages: the notebook raised 16 separate "follow up" cards and never said "you rarely follow up after calls".
- **Cause:** both designs judge one situation at a time; links come from one relate call; the goal object has no page (P2 N1).
- **Whose:** us, and **mine** (design).

## F6 · Coverage is the model's word, not code's

- **Evidence:** the absence rule is already coverage-aware in both prompts ("Never say something did not happen unless block F says that source was read for that window"; "Say that nobody replied only where WHAT WAS CHECKED says it may be said"). The blanket line "never say something is absent" is printed only when the snapshot was capped. What fails is the measurement: the model wrote coverage "low" in **73 of 86** results, and no code measures coverage at all. The 41 "find out" results of the first week were 39 of 63 under the first L2 prompt and 2 of 23 under the next (after the "find out only what the capture layer can fetch" rule).
- **Cause:** the confidence dimensions were made the model's own levels (F10), and the coverage receipt never reached the judge as a computed value.
- **Whose:** us (design).

## F7 · Company patterns are built, and produce nothing a run can use

- **Evidence:**
  - behaviour distillation, adaptive leases and organisation discovery run weekly and produced **0 learned entries**: 140 trend facts, none rising or falling; 3 card verdicts in the week; no rule-bearing document uploaded;
  - neither model path prints a learned brain; "yours" in the dossier (from `kind_numbers`) appears in 0 of 50 dossiers, because no file had a kind and so no stage;
  - the notebook has no company patterns at all; the prompt's "that person's usual pace" has no data behind it.
- **Cause:** the patterns are computed from slow metrics, not from the pages' own reply times, stage durations and outcomes; and no step over many pages exists (Maintain does not exist; P1 F5).
- **Whose:** unfinished.

## F8 · The model reads wrongly even when everything is there

- **Evidence:**
  - **partner calls marked done** (`b2`): with the follow-up rule, the page opened the follow-up loop we owe and set the move to us, but kept the status "done" and the founder "not needed". The rule moved two fields and not the other two, and nothing checks that they agree (31 pieces of work hold a loop we owe under a closed status; 53 done or dropped pages say the move is ours);
  - **an answer that was not an answer** (`i2`): "a projection is not the current number" was in the prompt; the loop still closed as answered, because admission checks only the direction and order of the reply, not whether it answers.
- **Correction to the 29 Oct text:** `c2` was not "the prompt said so and the model ignored it". Its saved page came from a run made two minutes before the renewal rule existed, and it was never judged again because the judge skips pages whose status is "noise", even when forced.
- **Cause:** a rule competing with a hundred other prompt lines, with no citation and no check; fields that should be derived by code (status, whose move) written by the model; a sticky status.
- **Whose:** the model, made likely by F1 and P2's page shape; mine (the sticky noise).

## F9 · The answer has to fit the API, and mostly does not

- **Evidence:** the notebook's full page returned "The compiled grammar is too large" on 12 of 12 calls; confidence, links and per-loop reasons were cut. In the product, 30 of the judge's calls failed validation (27 malformed after the one repair) and 6 were cut at the 12,000-token ceiling: the answer is the expert's schema and L2's merged, and every field is asked at every depth.
- **Whose:** an API limit (found by test), and us (one schema for every run).

## F10 · Confidence is asserted by the model, and the card uses a different one

- **Evidence:** the six dimensions are levels the model writes; code checks only their form. The card's own confidence is a count of cited mails (6,000 bp for one, 4,000 for none). The card's lane comes from the old `output_lane.route`, not from L2's `lane_for`; the two agree on 16 of 33 cards. L2's conflict lane is exactly the model's "open conflict" flag (23 of 23).
- **Cause:** GeniOS-008 deliberately made confidence "levels, never a score", written by the model; the Atlas's "computed by units" was not built.
- **Whose:** us.

## F11 · The plan does not plan

- **Evidence:** depth changes one prompt note and the repair mode; `max_calls` is never read; every field is asked at every depth, with the same model, tokens and timeout. 0 of 138 runs were shallow; 69 of 71 deep runs were deep only because L1 saw a conflict. The model asked for more depth in 49 of 86 results, and that reached only the next run. There are no units to select, no exclusions, and no dependency-complete plan (the compiled lane's planner only drops units; nothing pulls a unit's inputs in).
- **Cause:** GeniOS-008 built the depth plan as a prompt note first, before any unit library existed.
- **Whose:** us.

## F12 · Good answers are held, and the founder sees the checker's words

- **Evidence:** the claim check held **66 of 86** results (57 of 63 under the first prompt; 9 of 23 under v7). **52 of the 66** were "cites something the file does not show": the model cited block letters and section names (`F`, `C`, `D`, "WHAT WAS CHECKED") instead of printed ids. A held result becomes a founder question: 31 of 40 read "What is the next step with … ? We held the one we found: …", and 24 of the judge's 33 cards are question cards.
- **Cause:** the answer contract lets an id be any string; the check is right to hold it; the held path turns into a question to the founder.
- **Whose:** us.

## F13 · A third of the judge's money buys nothing, and the cap starves the rest

- **Evidence:** its $2.00 a day bound on every day (95 judgments skipped); **39% of its spend ($5.28 of $13.55) bought no stored result** (30 failed validation, 6 truncated); 31 runs were refused before any call because their dossiers were 245,000–280,000 characters; a retry resends the whole dossier.
- **Cause:** the dossier is the whole file rather than the page plus what is new (P2); one repair repays everything; truncation is not answered by the budget. P1's relief R5 covers the first fix.
- **Whose:** us.

## F14 · The judge reasons without knowledge, and does not abstain

- **Evidence:** 0 of 138 runs had a package; 50 of 50 dossiers say "No playbook for this file"; a thread with no file is judged from the company brief alone. The Atlas's "no package, no domain judgment: abstain instead" is not applied, so a recommendation can stand on no knowledge.
- **Cause:** P3 F8 (the compiler never meets the model); and no rule in Plane R limits what a run may conclude when the knowledge is missing.
- **Whose:** us.

## F15 · Questions are asked, and never answered

- **Evidence:** 115 evidence needs were raised in the week, all open, none met. The fetchers are off unless `GENIOS_NEED_FETCHERS` is on, and the stored-event fetcher (U13-20) does not exist. So the one bounded re-entry has run 0 times.
- **Cause:** fetchers kept off on purpose until verified; the fetch from our own database was never built.
- **Whose:** us.

## F16 · Nothing the judge concludes becomes the page

- **Evidence:** L2 admission runs in shadow: 33 admission rows and 30 interpretations, no applier for merges or links, no compare-and-set, and `admitted()` has no reader. A conclusion reaches a card only through the file's review row. 54 proposed changes were dropped for naming no printed situation. The result names none of the Atlas's fourteen outcomes.
- **Cause:** the door is P2's (P2 F-list); Plane R's part is a result that maps cleanly to it.
- **Whose:** us.

## F17 · Learning never reaches reasoning

- **Evidence:** no prediction is stored; calibration runs in shadow and cannot see the judge's cards (their rule ids are in no manifest); attribution maps 11 reasons to six old layers and changes nothing; 0 cards were resolved in the week; 3 verdicts.
- **Cause:** learning was built for the rule lanes; the judge's lane has no prediction, no outcome loop and no per-unit measure.
- **Whose:** unfinished.

## F18 · Model calls that decide sit outside the register, and cannot be replayed

- **Evidence:** about 16 call families bypass the register (`reason/bundle/sites.py`). Three of them decide things: the test-mode decision maker and its R-1 (3,695 Haiku calls, about $12 in the week, with no dollar cap), and `context/lifecycle/resolution.py` inside L3 (1,961 calls). A test-mode decision is not replayable: its cache lives in the process, and a replay calls the model again.
- **Cause:** test modes left on; GeniOS-008's L2-12 ("move resolution into L2") and L2-H2 ("retire the decision maker") not done.
- **Whose:** us.

## F19 · Every run says "bundle"

- **Evidence:** all 138 L2 runs carry trigger `bundle`. "Deadline crossed" and "expected reply absent" are derived from the expert's trigger words by a substring test, and none came through; `owner_change`, `outcome` and `human_ask` have no producer. So the clock's wake-ups never reach the judge as what they are.
- **Cause:** the clock is P1's and does not exist yet; the trigger list was defined before its producers.
- **Whose:** us.

---

## Summary

| Failure | Whose | Kind |
|---|---|---|
| F1 ways of thinking in prompt copies | us, mine | architecture, process |
| F2 the playbook wins; conditions cut | mine | prompt, renderer |
| F3 no calculators; UTC only | mine, us | not ported; no clock |
| F4 units decide nothing; a decider outside the register | us | architecture, unfinished |
| F5 nothing across situations; goals not judged | us, mine | design |
| F6 coverage is the model's word | us | design |
| F7 company patterns produce nothing | unfinished | not built from pages |
| F8 misreads and self-contradicting pages | model, mine | made likely by F1 and the page shape |
| F9 the answer does not fit | API, us | one schema for every run |
| F10 confidence asserted by the model | us | contract |
| F11 the plan does not plan | us | unfinished |
| F12 good answers held; the checker's words shown | us | contract, delivery |
| F13 a third of the money buys nothing | us | budget, dossier size |
| F14 no knowledge, no abstain | us | P3, plus no rule here |
| F15 questions never answered | us | fetchers off |
| F16 conclusions never become the page | us | P2's door, Plane R's result |
| F17 learning never reaches reasoning | unfinished | not built for the judge |
| F18 deciding calls outside the register | us | test modes left on |
| F19 every run says "bundle" | us | no clock yet (P1) |
