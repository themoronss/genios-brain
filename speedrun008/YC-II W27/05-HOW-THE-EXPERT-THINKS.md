# 05 · How the expert thinks — patterns, history, analytics, scenarios

**Written for:** Rohit first, then Harsh and the coding agent. This is the design at the centre
of the plan. Everything in `02-PLAN.md` exists to feed it, run it, check it or show it.

> **The direction, in your words (2026-10-05):** *"Ek company formula and rules pe nahi chalti,
> vo chalti hai patterns and analytics pe. LLM aise use karo ki GeniOS ek full-time 30 saal ka
> expert banke context reasoning kare."* · *"Context reasoning rule-based nahi hota — patterns,
> history, analytics and scenarios based hota hai."*

---

## 1 · The idea in one paragraph

A 30-year chief of staff does not run rules over your inbox. She **remembers everything**, knows
**what the company is trying to do**, keeps **a file for every piece of work in motion** —
each investor, each application, each intro, each hire — and when something moves in a file she
**thinks**: *what is really happening here, what does the history say, what usually happens in
cases like this, what happens if we do nothing, and what is the best move today?* Then she tells
you **only what needs you**, with the draft ready. GeniOS will work exactly like that. The model
is her judgment. The code is her memory, her calculator and her fact-checker.

---

## 2 · Why today's GeniOS does not think like this

The model **is** used — about 2,000 calls a day. It is just used in the three places where
judgment helps least:

| Where the model is today | What it is asked | What it is never given | Result |
|---|---|---|---|
| **The gate** (`relevance_gate`) | *"Is this ONE email junk?"* — with a prompt that lists what to drop | who you are, what you are doing, who this sender is to you | Startup India, Boardy, investors, incubators — called junk |
| **The reader** (`l1_extract`) | *"Extract the commitments, dates and questions in this ONE email"* — then code fits the result into one of 16 boxes | the work this email belongs to | an investor pitch became `contract_renewal`; a meeting became a `deadline`; 118 things that fit no box sit unreviewed |
| **The decider** (`l4_llm_decision`) | *"DECISION or DEFER, and give a score"* — every 15 minutes, on the same ~30 situations | history, patterns, numbers, the company's goals; and no memory of its own last answer | 57% DEFER; the same rule flips 113 / 118; cards appear and vanish |

Nowhere is the model given the whole file and asked what an expert would ask. **That is the
missing piece — not "more rules" and not "a formula".**

---

## 3 · The four things the expert reasons from

### History — *what has happened in this file*

Every touch, in both directions, across mail, calendar and screen, in order, with who did what.

> *Boardy intro to Pankaj, 3 Sep → Boardy nudge 4 Sep → nudge 7 Sep → nothing from Pankaj →
> nothing from you.*

**Comes from:** memory (`STEP-05`) arranged per workstream (`STEP-09`). **Who builds it:** code —
exact, complete, with a source for every line. The model never reconstructs history from its own
recall.

### Patterns — *what usually happens in cases like this*

Two kinds, always labelled with where they came from:

| | Example | Where from |
|---|---|---|
| **Your own patterns** | *"4 of Boardy's 7 contacts replied — two within hours, two within a week."* · *"You answer an investor who wrote first in ___ days; you have not once followed up an investor who did not reply."* | measured from your history (`STEP-10`) — and shown as *sparse* when there are too few cases to mean anything |
| **The profession's patterns** | *"A double opt-in intro left unanswered for a week usually dies."* · *"One follow-up with a new milestone, 7–10 days after a pitch, is the standard move; a third unprompted follow-up hurts."* | the reviewed playbooks of Plane D (`STEP-11`), written once, reviewed by you, versioned |

### Analytics — *the numbers*

Days waiting. Whose move it is. How many follow-ups were sent. The reply rate of the 11 Aug wave.
Your normal reply time. Days to the deadline or the meeting. Which mails bounced. **Which mailbox
was read and over what window** — so *"no reply"* is only said when it can be proven.

**Comes from:** deterministic calculators (`STEP-10`). ⛔ **No number on a card ever comes from
model text** — the model reasons *about* the numbers, it does not make them up.

### Scenarios — *what happens next, under each choice*

For every file that needs judgment, the expert writes out:

| Scenario | Example (Pankaj) |
|---|---|
| **If nothing is done** | the intro lapses; Boardy closes it; a possible investor never hears from you |
| **If you act now** | a three-line note referencing Boardy's intro and one recent milestone |
| **Best case / worst case** | a call this week / silence — then stop after one note |
| **Signals to watch** | Pankaj replies · Boardy writes again · you learn saka.vc is not a fund (then it drops) |

---

## 4 · The loop, step by step — and who does each step

This is the Design Atlas's own managerial loop (Part I.1), run per workstream.

| Step | Question | Who | Pankaj example |
|---|---|---|---|
| **Notice** | what changed, what is missing? | code finds the change or the silence; the model reads the new item | *"32 days since the intro, nobody has written"* |
| **Orient** | goals, people, timeline | code assembles the file; the company brief comes from the model and you | *"you are raising; saka.vc may be a fund"* |
| **Frame** | what situation is this? | **model** | *"a warm investor intro going cold"* |
| **Rival frames** | what else could it be? | **model** | *"or: Pankaj is not an investor at all"* |
| **Test** | evidence for and against | model proposes, code checks every quote against the source | *"Boardy's mail names him as ___"* — quote verified |
| **Compare patterns** | what does history say? | code computes, **model interprets** | *"4 of 7 replied — two within hours, two within a week"* |
| **Unknowns** | what fact would change the answer? | **model** names it; code turns it into a question for you or a fetch | *"Is saka.vc a fund?"* |
| **Project** | if nothing changes, then what? | **model** writes the scenarios; code attaches a base rate when one exists | §3 above |
| **Appraise** | stakes, urgency, reversibility | **model**, with reasons; code checks them against hard facts (dates, roles) | *"high — investor, active raise; fully reversible"* |
| **Intervene?** | which lane | code maps the appraisal plus the evidence state to one of five lanes (Atlas A.3) | Decision, or Investigation if the fund question is open |
| **Next move** | best move, alternative, when to stop, the draft | **model** | the note; *"ask Boardy to re-nudge"*; *"stop if no reply in 7 days"* |
| **Validate** | is every sentence true? | code | every claim cites a source or is marked an inference |
| **Remember** | so it does not flip | code | the judgment is stored with a receipt and reused until something in the file changes |

**The model does the thinking. The code makes sure the thinking stands on true facts, real
numbers and complete history — and never changes its mind without a reason.**

---

## 5 · When it thinks — and why it stops flip-flopping

The expert reviews a file **only when something in it changed**:

- a new mail, meeting or chat lands in the file;
- a date comes close — a deadline, a meeting, a promised reply;
- an expected reply does not arrive, judged against the file's own pattern;
- a number crosses what is normal for this file;
- you ask about it.

Each file carries a **fingerprint**: its evidence, the version of the brief, the version of the
playbook, its stage. Same fingerprint, same judgment — **zero model calls**. That one rule
replaces ~1,400 calls a day and ends the cards that appear and vanish. (`STEP-02`)

---

## 6 · Four worked examples from your own mailbox

The metadata is real. Where a mail's content matters, it is shown as `___` because I could not
read the text; the real system reads it. Lines marked **playbook** show the *kind* of
professional knowledge `STEP-11` writes for your review — none of it is in the corpus today, and
none of it may be used as authority until you accept it.

### A · Pankaj (saka.vc) — the intro nobody finished

| | |
|---|---|
| **Trigger** | silence: 32 days since Boardy's intro of 3 Sep, two Boardy nudges, nothing from either side |
| **The file** | Networking → Boardy → Pankaj · stage *offered → (no reply)* |
| **History** | intro 3 Sep · nudge 4 Sep · nudge 7 Sep · nothing since |
| **Patterns** | yours: 4 of Boardy's 7 contacts replied — two within hours, two within a week; you answered none of them in this mailbox. Playbook: an intro unanswered for a week usually dies; one short note from the person who asked for the intro is the standard revival |
| **Analytics** | 32 days · 2 nudges · fundraising active (brief) · fund status of saka.vc **unknown** |
| **Expert's frame** | *a warm investor intro decaying* — rival: *not an investor* |
| **Unknown** | *is saka.vc a fund?* → one question to you, or read from Boardy's intro text |
| **Lane** | Investigation until the unknown is answered, then Decision |
| **The card** | *"Pankaj (saka.vc) — Boardy introduced you on 3 Sep; nobody has written since (32 days, two nudges). If Saka is a fund, this is a warm investor lead going cold. Recommended: send the note below today. Alternative: ask Boardy to re-nudge. Stop: if no reply in 7 days, close it. Done when: Pankaj replies or a call is booked."* |

### B · Insight Partners — the call on 8 Oct

| | |
|---|---|
| **Trigger** | a meeting with insightpartners.com in 3 days, linked to Neel Jain's mail of 27 Sep |
| **The file** | Fundraising → Insight Partners · stage *first contact → call booked* |
| **History** | Neel's mail, 27 Sep (`___`) → invite → call 8 Oct. Your last mail to any investor: 26 Aug (Theresa, Antler); to the 11 Aug wave, nothing since |
| **Patterns** | playbook: a first investor call at your stage goes to traction, team, why now and round size; sending a short pre-read a day before helps. Yours: no investor has heard from you in 40 days |
| **Analytics** | 3 days to the call · open investor asks elsewhere: Manik's, since 8 Aug (`___`) |
| **Scenarios** | prepared — a pre-read the day before, crisp answers · unprepared — the call spends itself on basics |
| **Lane** | Decision |
| **The card** | *"Insight Partners, 8 Oct. What Neel wrote: ___. Send before the call: ___. Likely questions, with your best current answers taken from your own mails: ___. Do not claim: anything not yet verified. After the call I will ask what was agreed."* |

### C · Startup India — the update of 30 Sep

| | |
|---|---|
| **Trigger** | a new mail in Compliance → Startup India (DPIIT) |
| **History** | DigiLocker 23 Sep · DPIIT 24 Sep · DPIIT 29 Sep · DPIIT 30 Sep, twice |
| **Patterns** | playbook: application → possible clarification request (with a reply deadline) → recognition certificate → what it unlocks: the 80-IAC tax exemption application, the angel-tax exemption, self-certification |
| **Analytics** | three portal mails in one week — the case is moving |
| **Scenarios** | *if it is a clarification request:* doing nothing risks rejection — high stakes, a hard date. *If it is the certificate:* nothing is at risk, but a benefit is now available |
| **Lane** | Decision (clarification) or Monitor plus one line in the morning brief (certificate) |
| **The card** | *"Startup India — your DPIIT application has an update (30 Sep). Stage: ___. Next: ___ by ___."* — and the **same card updates** with each later mail |

### D · The 11 Aug investor wave

| | |
|---|---|
| **Trigger** | the wave's silence passed the playbook's follow-up window |
| **History** | ~11 investors written to on 11 Aug · five bounce reports between 11 and 14 Aug (whether they belong to this wave is read from the reports themselves — each names the failed address) · 0 replies in 55 days · 0 follow-ups |
| **Patterns** | playbook: one follow-up with a new milestone at 7–10 days is standard; past ~6 weeks, follow up only the best fits, with real news |
| **Analytics** | per investor — sent, bounced or not, replied or not, last touch. Which addresses bounced comes from the bounce reports themselves |
| **Unknowns** | your newest milestone worth sending — if none is on record, you are asked |
| **Lane** | Decision |
| **The card** | *"The 11 Aug wave: 0 of 11 after 8 weeks; ___ of the addresses bounced (fix them first). Follow up the five best fits — named, one draft each, built around ___. Close the other six."* |

**And one thing it must not do** — the NSRCEL cohort sessions (~54 founders each): no *"send a
recap"* card, ever. A cohort session is not an obligation. What it surfaces instead is the
session's assignment deadline, two days ahead (Atlas golden replay 05).

---

## 7 · What stays a rule — and why these are not "reasoning rules"

These are **guarantees**, not judgment. A 30-year expert follows them too; they are what make
her trustworthy.

| Guarantee | Why |
|---|---|
| Nothing captured is ever deleted by the gate — only given less attention | judgment cannot reason over what was thrown away |
| Nothing is sent, scheduled or promised without your approval | the expert advises; you act |
| You, and your own addresses, are never the person to chase | *"Send Mr Rohit Swerashi your traction metrics"* must be impossible |
| A connector is never the target — the introduced person is | Boardy is how you met Pankaj, not who you owe |
| Every sentence on a card has a source, or is marked as an inference | a fluent wrong card ends trust |
| Every number comes from calculation, never from model text | *"52 days"* must be exactly true |
| Something shared privately never crosses to another person's card | visibility |
| No new evidence, no new decision | stability |
| When the knowledge is missing, the expert says so and asks | no invented playbooks |

---

## 8 · What it costs

| | Today | With the expert |
|---|---|---|
| Model calls per day | ~2,000, 70% re-deciding | ~250–300: read each new item once, think once per changed file (10–30 judgments), one morning brief; screen and housekeeping as today |
| Model used for judgment | Haiku, 15-minute loop | the strongest model, because it now runs tens of times a day, not thousands |
| Spend per day, this org (list prices, see `04` §2.9) | ~$7 | ~$2–3 *(estimate — measured in `STEP-12`)* |

---

## 9 · How this fits the Design Atlas

The Atlas already designed this, and production never built it:

- **One bounded judgment pass inside L2** — frames, hypotheses, counterexamples, consequences,
  next move (Atlas II.2, L2 Fig. L2.1). Today: zero model calls on that path.
- **Plane R, Groups 1–3** — evidence and baselines (*analytics*), relationship history and prior
  situations (*history*), pattern match, counter-pattern and base rate (*patterns*), scenario set
  — do nothing, best, worst, signals to watch (*scenarios*). Built as contracts; never run
  through a model.
- **The material-change gate and fingerprint** (Atlas L2·O steps 2 and 12). Not built.
- **Five output lanes** (Atlas A.3). The column exists (`output_lane`); nothing chooses it from a
  real judgment.

What production runs instead — a model that scores every situation every 15 minutes — is the one
thing the Atlas forbids (*"the model may never score importance, priority or confidence"*).

**So this plan builds what the Atlas designed, removes what the Atlas forbids, and asks you for
one amendment** (`06-DECISIONS.md` D1): the expert's appraisal of stakes and urgency — with its
reasons — becomes an input to the lane, because *"what matters"* is exactly the judgment you are
asking for. Numbers, permissions and recipients still never come from the model.
