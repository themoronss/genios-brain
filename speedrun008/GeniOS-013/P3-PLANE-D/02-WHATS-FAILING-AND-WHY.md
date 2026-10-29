# P3 · Plane D · 02 · What's failing, and why

The knowledge in Plane D is mostly **right**. What fails is:
- how it reaches the model;
- what was never written;
- what was never reviewed, or reviewed and never switched on;
- what it cannot yet say: its conditions as checks, where and until when it holds, and the company's own numbers.

"Us" means the AI sessions that built the product and the notebook; "mine" means this notebook's own code. None of these is a misunderstanding by Rohit. The numbers are from [01](01-WHATS-EXACTLY-THERE.md).

---

## F1 · Approved knowledge exists but never reaches the model

- **Evidence:** Admin's approved items cover several of the cards that were missed:
  - renewal management (`c2`: the tool subscription renewal was filed as noise);
  - follow-up coordination, with its situation "meeting without follow-through" (`b2`: the partner calls marked "done"; `i3`: the follow-up after an investor call);
  - statutory filing and licence and registration (`c1`).

  The product's L2 and expert paths and the notebook all choose knowledge **by the kind of work, from Founder Office only** (vendor is the one exception, and it reads nothing, F10). None of them ever shows Admin's items to the model. Admin's knowledge does reach the compiled lane, but only as templates (F8).
- **Cause:** the bridge has one key (the kind of work) and one domain. It was built for the expert pass of STEP-12, when the founder's domain was new and the plan was to author everything there.
- **Whose:** us (design of the bridge).

## F2 · A rule's conditions are lost on the way

- **Evidence:** the reader (`packs/compiler/playbook_reader.py`) carries a rule's statement and its "why", but not its "applies when", "breaks down when" or "failure modes".
  - "Silence reads by stage" reached the model as "after a first call that named no next step, silence is usually a soft no".
  - Its condition did not reach it: "applies when … **the turn is theirs**", "failure mode: using it to excuse our own silence; **it reads their quiet, never ours**".
  - In the notebook, the model applied "soft no" to a call **we** had not followed up (`i3`), and to `i2`.
- **Cause:** the reader was written to show stages and moves. The rules were shown as single sentences, and their guard lines were left in the YAML.
- **Whose:** us (product reader code). The notebook inherited it.

## F3 · The notebook showed only the first step of each playbook move

- **Evidence:** `nb/common.playbook_text` prints `steps[0]` of each move. "Before an investor call", **step 6 of 6**, "write the same day: thank them, confirm the next step and its date in writing", never reached the notebook's model. The product's expert dossier prints all steps.
- **Cause:** to save space, I cut each move to its first step and never checked which steps carried the rules that mattered.
- **Whose:** **mine**.

## F4 · Coverage stops at two of the founder's six kinds of work

- **Evidence:**
  - Founder Office authors investor relations and programme applications only. Introductions, meetings, hiring and registrations are stubs. Partner has no home, and vendor reads Admin's capability, which has no staged playbook.
  - In `b2`, **300 of 421 situations (71%) had no expertise behind them**.
  - That is exactly where the model guessed wrong: partner calls marked done (`b2`), a renewal filed as noise (`c2`), who owes the move on an introduction (`b3`).
- **Cause:** authoring stopped after the first two capabilities. The rest were planned as STEP-11 M31.
- **Whose:** unfinished work.

## F5 · Nothing the founder's work leans on was reviewed by the founder

- **Evidence:**
  - All 29 Founder Office units (10 rules, 11 playbooks, 2 situations, 6 objects) and its 6 capabilities are `draft`, `unreviewed` and written by AI. Its rules say "practitioner judgement — unverified; for the founder's review".
  - So **the compiler drops all 6 Founder Office capabilities** ("unreadable"). If the model's path used the compiler today, the founder's own knowledge would disappear from it (F8).
  - Corpus-wide, 22 situations are still `draft`, so their cards are downgraded to observations.
- **Cause:** the design says "reviewed by that founder line by line" (`06` D45), but no review session was ever scheduled.
- **Whose:** process.

## F6 · Some older Admin items are wrong, not just unread

- **Evidence** (the 4 Oct diagnosis of the live cards):
  - `money-owed-either-way` fires on **any** dated commitment. It produced a false "a dated payment obligation is open" card about an incubator. Its package still carries the headline "{entity} — a dated payment obligation is open".
  - `dependency-stated` made a card without the quote that was its whole value. It is still the most frequent card source: 13 of the 36 compiled-lane cards in the first week.
- **Cause:** a rule's gate written too wide, and a renderer that dropped the evidence.
- **Whose:** us (authoring, AI-written, approved without a test case).

## F7 · One kind of work, one playbook, but a situation needs several kinds of knowledge

- **Evidence:** an investor call needs investor relations **and** meeting follow-through. A programme's fee renewal needs programme applications **and** renewal management. The bridge picks one playbook by kind. The compiler already returns several capabilities per situation (2.96 on average), but only for the compiled lane.
- **Whose:** us (design of the bridge).

## F8 · The compiler and the model never meet

- **Evidence:**
  - The Atlas's Domain Compiler is built (eight components in `packs/compiler/`). It made **100 packages** in the first week, each with 2 to 8 capabilities, their rules, objects and evidence, and pinned snapshots.
  - Those packages feed only the compiled lane, which renders them through templates (`render_hint`, a fallback headline). No model reads them.
  - The two paths where the model judges (`reason/l2/`, `reason/expert/`) import none of the compiler. They have their own dossier and the playbook reader.
  - **So the lane with the knowledge has no model, and the lane with the model has no knowledge.**
  - The package contract also refuses a package with no capability or object, so "nothing applies" cannot be recorded as a package.
- **Cause:** the compiler was built for the rule-born situations of the earlier lane. When L2 became the primary path, it got its own dossier, and the two were never joined.
- **Whose:** us (wiring).

## F9 · Choosing knowledge waits on the founder accepting a brief line

- **Evidence:** all **138** L2 dossiers say "No company brief is accepted". The kind of work comes only from an accepted brief line, and 0 of 29 were accepted. With no kind, there is no playbook: **105** dossiers say "No playbook for this file" and the other **33** "No file holds this subject". All **50** expert reviews say "No playbook for this file".
- **Cause:** the rule "only a confirmed kind is a fact" (GeniOS-013 [07](../07-DECISIONS.md) D1) was also applied to choosing knowledge. L2's own reading of the kind is a fine key for knowledge, as long as it is labelled as L2's reading. U13-26 plans exactly that.
- **Whose:** us (design).

## F10 · The reader accepts only a playbook with stages

- **Evidence:** `playbook_for` needs **exactly one** playbook with stages per capability. Only 2 of 238 playbooks declare stages, both Founder Office's. Admin's 58 playbooks have none, so a vendor file gets "no playbook declares stages", even though Admin's renewal knowledge is approved.
- **Cause:** the reader was built around the two staged Founder Office playbooks.
- **Whose:** us (reader code).

## F11 · Review is performed on two of eight kinds of unit, and its second step is never taken

- **Evidence:**
  - **Capabilities** need a named reviewer's accepted content hash. **Situations** are flagged when `draft`, and their cards become observations.
  - **Rules of thumb, playbooks and objects** are only reported, never gated, and carry no hash. The code says so: "IT REPORTS. IT DOES NOT GATE".
  - **165 units were approved by a named reviewer and never switched to `stable`:** 80 rules of thumb, 80 playbooks and 5 situations. Admin alone has 44 rules and 44 playbooks in that state. Wherever they are shown, they are labelled "not yet reviewed".
  - Models (88), mental models (61) and decision frameworks (59) have never been reviewed at all, and the retriever reads them.
- **Cause:** approving and switching on are two separate steps, and nobody owns the second one. Content hashes were added for capabilities only.
- **Whose:** process, and us (the gate stops at two kinds).

## F12 · The units cannot yet say what the Atlas asks of them

- **Evidence:** the Atlas's D-Unit has fields the corpus does not:
  - **conditions code can check.** Most are prose. Only 50 of 291 rules and 78 of 238 playbooks carry checkable ones (`when_to_use.conditions`, such as `has_obs: meeting_scheduled`), and nothing evaluates them when knowledge is chosen;
  - **`facts_required`,** the fact paths a unit needs. **68 of the 141 fact paths** in the vocabulary are named by no unit;
  - **`evidence_requirements`,** what counts as proof and what never does;
  - **`authority_boundary`,** what GeniOS may do and what only a human may do;
  - **`evaluation_cases`,** where the unit must speak and where it must stay silent;
  - **where and until when it holds.** Programme and registration rules for India cite their sources (startup recognition, the seed fund), but no unit carries a jurisdiction, a valid-from date or a review-by date. A rule that changed would still read as current.
- **Cause:** the corpus schema predates Atlas v2's D-Unit anatomy, and was never migrated.
- **Whose:** us (schema).

## F13 · Part of the knowledge the ideal stands on was never written

- **Evidence** ([01 §7](01-WHATS-EXACTLY-THERE.md)):
  - **5 of the 14 situations the ideal names do not exist:** application deadline, conditional deferral, wave gone silent, information conflict, delivery failure. Two of them exist only as playbooks.
  - **4 of the rules its cards cite do not exist:** one number, everywhere; investors compare updates; prepare one number, one story, one ask; a dormant thread reopens with news.
  - **4 more exist only inside another unit,** where nothing can select or cite them on their own: a warm intro beats a cold application; answer the question that was asked; an update must carry a new fact; startup recognition gates the seed fund and the tax holiday.
  - `obligation_falls_due` (the ideal's `c1`, `c2`) is in the half-state.
- **Cause:** the ideal was written after the corpus, from the founder's real work, and was never carried back into it.
- **Whose:** unfinished work.

## F14 · The company's brains are empty, so the knowledge stays generic

- **Evidence:** every one of the 100 packages carries **0 organisation rules, 0 behaviour patterns and 0 adaptive preferences**. `learned_brain_entries` has **0 rows**. Nothing tells a rule this company's numbers: how fast this investor usually replies, which approvals this company needs, what matters this quarter.
- **Consequence:** without them, GeniOS gives consulting advice: correct, and generic.
- **Cause:** the readers exist (`runtime_brains.py`), but nothing writes the brains. Layer 6 has published no entry, and the company page (P2 §3.4) is not yet the Organisation brain's source.
- **Whose:** us (unbuilt writers). Shared with P2 (§8 there) and L6.

## F15 · The tests check routing, not knowledge

- **Evidence:** all 40 evaluation cases ask one question: does a kind of work reach the right playbook, or none? None asks whether a rule is **cited** where it must be, **not** cited where it must not be, or whether following it gave the outcome it promises. The two wrong Admin items (F6) had no case that would have caught them. The Atlas's six tests of proper expertise are not shown for any capability.
- **Whose:** us.

## F16 · Nobody can see whether a unit earns its place

- **Evidence:** no count exists of how often a unit was selected, cited, contradicted, cut by a budget or followed by a good outcome. The packages list the rule ids they carried, and nothing adds them up. The review queue orders situations by how permissive they are, not by how often they are used or how much harm a wrong one did.
- **Whose:** unbuilt.

## F17 · Some situations exist, but as authored cannot describe the ideal's case

- **Evidence** ([01 §7](01-WHATS-EXACTLY-THERE.md)):
  - `reply_owed` needs them to have written last; `i2` is our reply that missed the question;
  - `meeting_without_follow_through` fires only 20 to 240 hours after a meeting; `i3` and `b2` are 15 to 64 days old;
  - `promise_past_its_date` is our own promise; `f3` is a third party's;
  - `decision_waiting_on_a_person` is the ball in their court; `b1` is the founder's decision;
  - "the wave gone silent" excludes updates to existing investors, which is `i4`, while Admin's `campaign_going_quiet` already covers a silent run of outreach;
  - `obligation_falls_due` routes nothing: its L2 type is pending, waiting for facts nothing writes.
- **Cause:** each was written for the rule lane's detection, before the ideal's cases existed. No case tied a situation to the cards it should cover.
- **Whose:** us (authoring without cases).

## Already fixed: investor relations was in Sales

Under "Admin only", a fundraising founder's most valuable cards couldn't exist. It moved to Founder Office on 9 Oct (STEP-11).

---

## Summary

| Failure | Whose | Kind |
|---|---|---|
| F1 approved knowledge unreachable | us | design of the bridge |
| F2 conditions dropped | us | reader code |
| F3 first step only | mine | notebook code |
| F4 coverage | unfinished | authoring |
| F5 never reviewed by the founder | process | review never scheduled |
| F6 wrong older items | us | authoring without test cases |
| F7 one key | us | design |
| F8 compiler and model never meet | us | wiring |
| F9 selection waits on an accepted brief line | us | design |
| F10 only a staged playbook is read | us | reader code |
| F11 review stops at two kinds; 165 approved, never switched on | process, us | review workflow, gate |
| F12 no checkable conditions, no facts, proof, authority, cases, jurisdiction | us | schema |
| F13 the ideal's knowledge partly missing | unfinished | authoring |
| F14 brains empty | us (with P2, L6) | unbuilt writers |
| F15 tests check routing only | us | tests |
| F16 no measurement per unit | unbuilt | measurement |
| F17 situations that cannot describe the ideal's case | us | authoring without cases |
