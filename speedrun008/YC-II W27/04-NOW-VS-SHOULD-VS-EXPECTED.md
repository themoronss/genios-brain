# 04 · What you see now, what you should see, what you will see

**Written for:** Rohit. **Measured:** 2026-10-05, 16:33 IST, on production, org Homians
(`org_e97e86f858ad48b2bbf64b8a`), read-only.

This is the page to read first if you only read one. Every number on it comes from a query against
production; the queries are listed in `01-CROSSCHECK.md` §7 so anyone can re-run them.

---

## 0 · How this was measured — and what could not be

| | |
|---|---|
| **Read** | sender, recipients, dates, every gate decision (`event_trace`), signal types, graph node names, situations, card headlines, calendar attendee domains, screen follow-up counts, every model call (`llm_costs`) |
| **Not read** | email **text**. The session's safety classifier blocked it, even after you asked me to read everything. So this page can say *that* the 30 Sep Startup India mail was junked — not *what* it said |
| **Already gone** | the 258 mails dropped at the first gate have **no content stored at all** — GeniOS deleted it. Only sender, date and recipients survive. Those mails come back only through a mailbox re-sync (`STEP-08`) |
| **Your mailbox** | `mrrohitswerashi@gmail.com` — its Gmail and its Calendar are the org's two connections, and everything below is read from them. *"You did not reply"* means no reply exists in that mailbox; a reply made by phone or chat is not visible to GeniOS |

---

## 1 · The whole picture in one table

Inbound mail, 4 Aug → 5 Oct, **365 mails** (your own sent mail excluded). The grouping is mine, by
sender domain — GeniOS has no such grouping today, which is part of the problem.

| Workstream | Mails | Deleted at gate 1 | Called junk by the AI filter | Read, but no "signal" | **Reached reasoning** |
|---|---:|---:|---:|---:|---:|
| Investors | 15 | 4 | 6 | 4 | **1** |
| Programs, incubators, grants | 168 | 112 | 38 | 11 | **3** |
| Government — Startup India, DigiLocker, MSME | 8 | 7 | 1 | 0 | **0** |
| Networking — Boardy | 35 | 31 | 1 | 0 | **1** |
| Partners, peers, intros | 41 | 19 | 9 | 3 | **10** |
| Jobs, learning | 5 | 3 | 2 | 0 | **0** |
| Bounces — your own mail that failed | 5 | 0 | 5 | 0 | **0** |
| Vendors, newsletters, accounts | 87 | 81 | 5 | 0 | **0** |

And beyond mail:

| | Today |
|---|---|
| Calendar | 34 events → **2 meetings** in memory |
| Screen (WhatsApp + desktop) | 102 follow-ups detected, 93 still open → **0 shown** (65 reminders built, all hidden) |
| Cards | **22** in total, all since the 3 Oct re-capture |

⛔ Not every one of the 168 program mails deserves a card — many are newsletters. The point is
that **3 of 168 even reached the stage where GeniOS can think**. The rest were deleted or junked
before anything that knows who you are ever saw them.

---

## 2 · Case by case

### 2.1 Startup India (DPIIT) — *you named this one*

| | |
|---|---|
| **What arrived** | 24 Sep DPIIT · 29 Sep DPIIT · 30 Sep DPIIT, twice — plus 23 Sep DigiLocker (whether it belongs to the same application cannot be told without the text) and 9 Aug an MSME mail from the same government sender |
| **What GeniOS did** | 24 and 29 Sep: dropped, because Gmail had filed them under Promotions (`N-06`). 23 Sep, 30 Sep 12:33 and 9 Aug: dropped as "no-reply sender" (`N-03`). 30 Sep 11:39: passed the rules, then the AI filter called it junk. Five of the six have no content left. **No node, no card.** |
| **Why** | The rules ask *"is a human writing to you?"* A government portal is a machine, so it fails. The AI filter's prompt says *drop automated, self-service messages*. **Nothing told either of them that you have a live DPIIT application.** |
| **What you should have seen** | On 24 Sep, the same day: *"Startup India — your DPIIT application has an update. Stage: ___. Next: ___ by ___."* On 30 Sep the **same card updates** — it does not multiply |
| **What you will see after the plan** | The mail is kept (`STEP-03`). The company brief knows *"DPIIT recognition: in progress"* (`STEP-07`). The reader files it to the Startup India workstream and reads the new stage (`STEP-09`). The expert decides whether it needs you today (`STEP-12`). A card, or a line in the morning brief, the same day (`STEP-14`, `STEP-15`) |

### 2.2 Boardy — *"networking ko bola, process complete nahi hua"*

Boardy made **seven introductions**. Reconstructed from the To/Cc lines alone, because the text is
gone:

| Intro | Boardy's intro | Did they reply? | Did you reply (this mailbox)? | In GeniOS memory? | Card |
|---|---|---|---|---|---|
| Silas — eclipta.one | 4 Aug (nudged 7 Aug) | no | no | **no** | none |
| Maria Exconde — Alyst Ventures | 6 Aug (nudged 7 and 11 Aug) | **yes, 11 Aug** | no | yes | 3 Oct, 52 days late — and a second, useless one: *"Which is right? Maria Exconde: party.role"* |
| Ori — tryeverguide.com | 6 Aug | no | no | **no** | none |
| Sal Stabler — Nexlayer | 6 Aug | **yes, same day** | no | **no** | none |
| Nitesh Pant — DevDash Labs | 6 Aug | **yes, 9 Aug** | no | yes | 3 Oct, 54 days late |
| Lalitha A R | 12 Aug | **yes, 12 and 13 Aug** — and a call on 13 Aug | no | yes | 3 Oct, 51 days late |
| Pankaj — saka.vc | 3 Sep (nudged 4 and 7 Sep) | no | no | **no** | none |

Boardy also sent you **16 one-to-one mails** (new offers or updates — I cannot tell which without
the text). You answered two: 12 Aug and 29 Sep. **On 29 Sep Boardy answered you 38 seconds later,
that answer was dropped, and nothing has happened since.**

| | |
|---|---|
| **What GeniOS did** | 31 of Boardy's 35 mails were deleted at gate 1 — 28 because Boardy's mail carries an unsubscribe header (`N-02`, "bulk campaign"), 3 because Gmail filed them under Promotions. The one that reached the AI filter was marked "junk, not sure" — its prompt tells it to drop *"automated matchmaking"* |
| **Why** | Boardy is an **AI agent that works for you**. To a rule it looks exactly like a mailing list. Only context tells the two apart: you wrote to Boardy, Boardy introduces you to named people, those people reply |
| **What you should have seen** | One file per introduced contact — Boardy is the **connector**, the contact is the **person** (the Atlas's own golden replay 02). A networking board: *"7 intros: 4 replied and are waiting on you, 3 silent."* For each waiting contact, a card with a draft, within a day or two of their reply. Pankaj first if saka.vc is a fund, because you are raising |
| **What you will see after the plan** | Boardy is recognised as your connector (`STEP-03`, `STEP-07`). Each intro becomes its own file with its own stage: *offered → accepted → intro sent → they replied → call booked → met → follow-up* (`STEP-09`). The expert knows the pattern: an intro answered within 48 hours converts; one left for weeks dies (`STEP-10`, `STEP-11`). A card per waiting contact, with the draft (`STEP-14`) |

### 2.3 Investors

| What happened | What GeniOS did |
|---|---|
| **11 Aug — you wrote to ~11 investors in one wave:** Afore (5 people), Peak XV (2), 3one4, Neon, Together, Z Fellows, IIMA, Titan (Manik had written first, 8 Aug), Surge, two angels | Typed most of them as **`contract_renewal`** — the closest of its 16 boxes. 55 days, 0 replies in this mailbox, **no follow-up reminder ever** |
| **Khushi Agarwal, 247VC, 18 Sep** (plus two attachments) | AI filter: junk. Attachments parked |
| **Troy Kirwin, a16z, 15 Sep** | AI filter: junk |
| **Neel Jain, Insight Partners, 27 Sep** | Read — but no box fitted, so it never entered memory. ⛔ **There is a call with insightpartners.com on 8 Oct, and GeniOS has nothing to prepare you with** |
| **Theresa Hoffmann, Antler** — you wrote to her 4 times between 6 and 26 Aug; she last wrote 7 Aug | One card, 3 Oct |
| **Manik, Titan, 8 Aug** — asked you something | The card reads *"Send **Mr Rohit Swerashi** your current traction metrics"* — it pinned his ask on you |

**What you should have seen:** a fundraising board, one line per investor — stage, last touch,
whose move, next step. *"Khushi wrote 18 Sep; 17 days without a reply; draft attached."*
*"Insight call 8 Oct — here is what Neel wrote, what you have shipped since, what to send before
the call."* *"The 11 Aug wave: 0 of 11 after 8 weeks. One follow-up with your newest milestone to
the five best fits (named), close the rest."* *"Theresa: she asked for updates when there is real
news — send only on a material milestone."*

### 2.4 Programs, incubators, grants

| Program | What arrived | What GeniOS did |
|---|---|---|
| **NSRCEL** (your program) | Deepthi wrote 24 times, plus 22 attachments; 14 cohort sessions on the calendar (~54 founders each) | 10 of her mails junked by the AI filter; 22 attachments parked. Cards: *"Phase-1 Review presentation"*, *"nsrcel — a dated payment obligation is open"* (⛔ false — there is no payment), *"Share review meeting details"* (expired) |
| **IIITD-IC** | four people wrote to you — Navin Gaur (7 Sep), Rajni Rani (7 Sep), Naresh Sood (8 Sep), Esha B (24 Sep) | none reached memory |
| **Hub71** | you replied 26 Aug; Hub71 wrote again 1 Oct | 1 Oct: junk |
| **iHub Gujarat** (investments@) | 1 Oct | junk |
| **FITT IIT Delhi** | Saket Raj, 13 Sep | junk |
| **IIM Lucknow EIC** | 16 and 21 Sep | junk |
| **GUSEC grants** | 7 Sep | junk |
| **StartinUP** | 5, 15, 25 Sep, 5 Oct | junk / no-reply |
| **Entrepreneurs First** | 24 Aug → 5 Oct | junk / bulk |
| **SINE IIT Bombay** | 13 mails | **all deleted at gate 1** |
| **Sankalp / Intellecap** | 12 mails | **all deleted at gate 1** |

**What you should have seen:** an applications board — per program: stage, next deadline, what
they need from you. NSRCEL: the week's session, the assignment due, the Phase-1 review and its
prep. A program newsletter goes to the archive, but surfaces if it carries a deadline for
something you applied to.

### 2.5 Meetings

| | |
|---|---|
| **What arrived** | 34 calendar events. External 1:1s or small calls: Engramme (4 Aug, 26 Sep), Antler (5 Aug), Reticle (5 and 10 Aug), actual.ai (5 Aug), Boardy / Lalitha (13 Aug), Evokoa (30 Sep), Supymem (5 Oct, twice). **Coming: Noveum (8 Oct), Insight Partners (8 Oct), Tryclean (9 Oct).** Plus 14 cohort sessions |
| **What GeniOS did** | Stored each meeting as a **"deadline"**. When the time passed the deadline "expired" and the meeting vanished — 18 of 20. Memory holds **2 meetings** |
| **What you should have seen** | Before each external meeting, a prep card tied to its workstream. After it, a question rather than an assumption: *"Did the Lalitha call happen? Was anything promised?"* (Atlas golden replay 05). Cohort sessions: no recap card — only the assignment deadlines |

### 2.6 Screen — WhatsApp and desktop

102 follow-ups detected, **93 still open**: 41 next steps, 21 promises others made to you, 13
promises **you** made, 8 risks, 7 open asks, 3 deadlines. 65 reminders and pieces of advice were
built — **every one hidden** (`suppressed_reason = 'shadow'`).

**Should:** they join the same files — a WhatsApp promise to an investor goes into that
investor's file — and they appear in the morning brief.

### 2.7 Hiring

The Founding AI Engineer offer to Khushi (`ydvkhushi721@gmail.com`, 5 Aug) became **six separate
cards** — ESOP allocation, board approval, fundraising completion, Khushi's acceptance, the
engagement documents, the formal offer — and one of them lists `ceo@thegenios.com` and you as the
people *"waiting longest"*.

**Should:** one file. *"Khushi — offer sent 5 Aug. Waiting on: her acceptance and the signed
documents. Blocked on: the ESOP board approval, which is yours."* One card.

### 2.8 Bounces

5 "Mail Delivery Subsystem" mails, 11–14 Aug — in the days right after the investor wave — all
called junk by the AI filter; 8 more parked. Each bounce report names the address that failed, so
whether these were investor mails is a fact GeniOS could have read; I could not. **Should:**
*"Your mail to ___ bounced on ___. Fix the address and resend."* The Design Atlas names this exact
case (Part I.2: *"three pitch emails the founder believed were delivered — they had bounced"*).

### 2.9 The model calls behind all of this

Last 3 days, per day:

| What the model is doing | Calls / day | Share |
|---|---:|---:|
| Re-deciding the same ~30 situations every 15 minutes (`l4_llm_decision`, `l4_llm_r1`) | ~1,400 | **70%** |
| Junk filter, one mail at a time, knowing nothing about you (`relevance_gate`) | ~250 | 13% |
| Screen memory and insight | ~100 | 5% |
| **Actually reading mail** (`l1_extract`) | **~70** | **3.5%** |
| Relevance, resolution, card text, deep narrator | ~170 | 8% |

≈ **2,000 calls a day**, ≈ **$7 a day** for this one org at list prices (assumed: Haiku 4.5 at
$1 / $5 per million input / output tokens, Sonnet-class at $3 / $15) — and **58% of that money
re-decides things nothing has changed about.**

### 2.10 The context an expert would need — all empty

| Table | Rows |
|---|---:|
| `seat_objectives` — your goals | 0 |
| `org_mission_critical_entities` — what matters to the company | 0 |
| `user_models` — how you work | 0 |
| `learned_brain_entries` — what GeniOS has learned | 0 |
| `card_feedback_verdicts` — your feedback | 0 |
| `unclassified_observations` — the reader's own *"this fits no box"* notes: investment thesis, rejection reasons, program selection, traction, relocation, application timelines | **118, 0 reviewed** |

---

## 3 · What "expected" means — the scoreboard

Every step in this plan moves one or more of these numbers, and none is called done until the
number moved on production.

| Measure | Today | Expected after the plan |
|---|---|---|
| Mail with its content deleted at the gate | 258 of 395 | **0** |
| Kept items in memory | ~27 of 395 mails · 2 of 34 meetings | **≥ 95%** |
| Boardy intros tracked per contact | 3 of 7, 50+ days late | **7 of 7, within 2 days of a reply** |
| Startup India updates surfaced | 0 of 5 | **the same day** |
| Investor mails in memory | 1 of 15 | **15 of 15** |
| External meetings with a prep card, when tied to a workstream | 0 | **≥ 90%** |
| Cards with you as the subject | ≥ 3 | **0** |
| A situation re-decided with no new evidence | every 15 minutes | **never** |
| Model calls per day | ~2,000, 70% re-deciding | **~250–300**, of which **10–30 are expert judgments** — the rest is reading, screen and housekeeping that run today too *(estimate — measured in `STEP-12`)* |
| Model spend per day, this org | ~$7 | **~$2–3** *(estimate)*, and spent on reading and thinking instead of re-deciding |
| Golden-set score (`STEP-01`) | measured in `STEP-01` | **must-detect ≥ 90%, forbidden outputs 0** |
