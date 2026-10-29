# P3 · Plane D · 02 · What's failing, and why

The knowledge in Plane D is mostly **right**. What fails is how it reaches the model, what was never written, and what was never reviewed. "Us" means the AI sessions that built the product and the notebook; "mine" means this notebook's own code. None of these is a misunderstanding by Rohit.

---

## F1 · Approved knowledge exists but never reaches the model

- **Evidence:** Admin's `stable`, `approved` items cover three of the cards that were missed:
  - renewal management (`c2`: the tool subscription renewal was filed as noise);
  - follow-up coordination, with its situation "meeting without follow-through" (`b2`: the partner calls marked "done"; `i3`: the follow-up after an investor call);
  - licence and registration (`c1`).

  The product's expert path, its L2 path and the notebook all choose knowledge **by the kind of work, from Founder Office only**. None of them ever shows Admin's items to the model.
- **Cause:** the bridge has one key (the kind of work) and one domain. It was built for the expert pass of STEP-12, when the founder's domain was new and the plan was to author everything there.
- **Whose:** us (design of the bridge).

## F2 · A rule's conditions are lost on the way

- **Evidence:** the reader (`packs/compiler/playbook_reader.py`) carries a rule's statement and its "why", but not its "applies when", "breaks down when" or "failure modes".
  - "Silence reads by stage" reached the model as "after a first call that named no next step, silence is usually a soft no".
  - Its condition did not reach it: "applies when … **the turn is theirs**", "failure mode: using it to excuse our own silence; **it reads their quiet, never ours**".
  - In the notebook the model applied "soft no" to a call **we** had not followed up (`i3`), and to `i2`.
- **Cause:** the reader was written to show stages and moves. The rules were shown as single sentences, and their guard lines were left in the YAML.
- **Whose:** us (product reader code). The notebook inherited it.

## F3 · The notebook showed only the first step of each playbook move

- **Evidence:** `nb/common.playbook_text` prints `steps[0]` of each move. "Before an investor call", **step 6 of 6**, "write the same day: thank them, confirm the next step and its date in writing", never reached the notebook's model. The product's expert dossier prints all steps.
- **Cause:** to save space, I cut each move to its first step and never checked which steps carried the rules that mattered.
- **Whose:** **mine**.

## F4 · Coverage stops at two of the founder's six kinds of work

- **Evidence:**
  - Founder Office authors investor relations and programme applications only. Introductions, meetings, hiring and compliance are stubs. Partner and vendor have no home.
  - In `b2`, **300 of 421 situations (71%) had no expertise behind them**.
  - That is exactly where the model guessed wrong: partner calls marked done (`b2`), a renewal filed as noise (`c2`), who owes the move on an introduction (`b3`).
- **Cause:** authoring stopped after the first two capabilities. The rest were planned as STEP-11 M31.
- **Whose:** unfinished work.

## F5 · Nothing was ever reviewed by the founder

- **Evidence:**
  - Founder Office is `draft` and `unreviewed`, created by AI. Its rules are marked "practitioner judgement — unverified; for the founder's review".
  - Corpus-wide, 22 situations are still `draft`, so their cards are downgraded to observations.
  - All 6 Founder Office capabilities are unreadable to the compiler.
  - In 1 October's count of 23 drafts, five had been reviewed and approved, and nobody had flipped the word.
- **Cause:** the design says "reviewed by that founder line by line" (`06` D45), but no review session was ever scheduled, and only an author may flip a status.
- **Whose:** process.

## F6 · Some older Admin items are wrong, not just unread

- **Evidence** (the 4 Oct diagnosis of the live cards):
  - `money-owed-either-way` fires on **any** dated commitment. It produced a false "a dated payment obligation is open" card about the incubator.
  - `dependency-stated` made a card without the quote that was its whole value.
- **Cause:** a rule's gate written too wide, and a renderer that dropped the evidence.
- **Whose:** us (authoring, AI-written, approved without a test case).

## F7 · One kind of work, one playbook, but a situation needs several kinds of knowledge

- **Evidence:** an investor call needs investor relations **and** meeting follow-through. A programme's fee renewal needs programme applications **and** renewal management. The bridge picks one playbook by kind.
- **Whose:** us (design).

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
| F5 never reviewed | process | review never scheduled |
| F6 wrong older items | us | authoring without test cases |
| F7 one key | us | design |
