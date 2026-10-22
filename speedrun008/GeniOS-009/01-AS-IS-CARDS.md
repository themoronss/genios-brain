# 01 · The cards today — measured

**Written for:** Rohit, Harsh and every coding agent.

## How this was measured

- **Code:** `speedrun008` at `21b7ae10` (Harsh's `harsh/mvp`, fast-forwarded locally on 22 Oct).
- **Run:** all 67 golden founder cases, F01–F67 (`tests/replays/specs/founder/`), each through the **real chain** (connector mapping → `run_sync` → `_run_l2_chain` → cards). Each case ran twice:
  - **today's path:** the expert reviews each changed file;
  - **the L2 path** (`l2_cards`): the Layer 2 judgment reviews it and makes the card.
- **The model was the ideal reader**, a faithful answer to each prompt taken from the case's own expected reading. No API spend. So this measures **what the engine does with a right answer**: which card exists, its shape, its lane and its versions. It does not measure model quality.
- **Database:** scratch pg3 `zz_probe_1792225346`.
- **Data and scripts:** [`measurements/`](measurements/)
  - `golden-cards-2026-10-22.json`: every card, every field, both paths;
  - `card_dump.py` / `card_report.py`: re-run with `GENIOS_TEST_DATABASE_URL=… python measurements/card_dump.py <repo> out.json`.
- ⚠ **Production cards were not read.** Production reads need Rohit's permission (memory: production-reads-need-permission).

## 1 · The numbers

| | Today's path | L2 path (`l2_cards`) |
|---|---|---|
| cases passing / failing | **63 / 4** | **63 / 4** (the same four) |
| cards produced | 57 | 62 |
| cases with ≥ 1 card | 46 | 47 |
| cases silent (no card) | 21, of which **18 rightly silent** (newsletters, receipts, own mail, answered elsewhere, declined intro, …) and **3 wrongly silent** (F15, F18, F56) | 20 |
| lane: decision | 48 | 48 |
| lane: investigation (a question to you) | 8 | 13 |
| lane: monitor | 1 | 1 |
| lane: conflict / suppress | 0 / 0 | 0 / 0 |
| two cards about the same subject in one case | **0** | **0** |
| cards with more than one version (a living card that updated) | 15 | 15 |
| cards whose ending was recorded | 5: verified 1 (F57), called wrong 2 (F65, F67), cleared 2 (F66) | same |
| cards that name a goal | **0 as a field**; 1 in words (F02: *"…mark the brief's StartupSetu recognition goal as met"*) | same |

## 2 · What a card carries today (fill rate, today's path, 57 cards)

| Field | Filled | Note |
|---|---|---|
| headline, subject, why now | 57/57 | always |
| capability key | 56/57 | **all 56 are `expert.file_review`**: every card today is the STEP-12 expert's review of one file |
| recommended · alternative · wait-or-stop | 48/57 | every **decision** card has all three; investigation cards are a question by design |
| outcome window | 49/57 | |
| confidence | 49/57 | ⚠ the **old three keys `{C, I, U}`** (one card has `{C, I, R, U}`), not Atlas v2's six dimensions (evidence · frame · temporal · causal · authority · coverage). GeniOS-008 item L2-9 |
| what remains | 38/57 | missing on 18 decision cards (F03, F16, F25, F47–F51, F60×3, F61×2, F65, F66×2, F67×2) |
| relationship role | **25/57** | intro 16 · watched 7 · connector 2 · **missing 32**. The "who is this to us" line is absent on more than half |
| goal | — | no column |
| definition of done / check-in state | — | no column; only the card's ending (`file_outcomes`) |

## 3 · Findings

| # | Finding | Evidence | Where it goes |
|---|---|---|---|
| A1 | **The card core is healthy.** One card per subject, living versions, claim-checked words; 18 of 21 silences are correct | §1 | keep |
| A2 | **F15: today silent, the L2 path splits into 5 held cards.** Five funds, eight weeks without a reply. Today's path makes 0 cards; the L2 path makes 5 investigation cards (*"What is the next step with Cobalt Peak? We held the one we found: a fact your move rests on quotes nothing from the mail it cites."*). The case expects exactly 1. Both paths fail differently. The held wording is also an engineer's sentence on a founder's card. | dump F15 | G0 (L2 path), G6 copy |
| A3 | **F18: a state fund's open round is never triaged** | 0 lines about Sabarmati | open, both paths |
| A4 | **F56: a vendor renewal at +32% makes no card** | case `blocked_on` a vendor-renewal kind (Harsh `0d5939d1` note) | open |
| A5 | **F63: the investigation card asks the wrong question** (*"whether Ishaan will write first?"*) where the case wants the missing **address** named | dump F63 | open |
| A6 | **A monitor-lane card with an imperative headline and no capability key**: F55 *"Send Dev Malhotra the pricing sheet"* is lane `monitor` | dump F55 | G6: a monitor card must read as a wait, not a move |
| A7 | **Confidence is still three opaque keys**, not the six named dimensions | §2 | GeniOS-008 L2-9, shown on the card in G6 |
| A8 | **Relationship role missing on 32 of 57 cards** | §2 | G6 (role is read from the file's people; intro/connector/watched only today) |
| A9 | **No goal on any card**, though the brief has goals and the expert already writes about them in words | §1, F02 | G1–G6 |
| A10 | **Check-in is only the card's ending.** VERIFIED vs REPLIED exists per card (`context/file_outcomes.py`); nothing on the situation or a goal | §1, F57 | G7 |
| A11 | **Every card is the expert's file review**: no card comes from a situation formed by L2 and admitted by L3 as the owner of existence | capability key | GeniOS-008 L3-1 (G0.3) |

## 4 · Every case, every card (today's path; the L2 path is identical except F15)

| Case | What the case is | Verdict | Cards today | Lane · headline (today) | L2 path differs? |
|---|---|---|---|---|---|
| F01 | A government portal moves the founder's live application | pass | 1 | investigation · Can you tell us whether the examiner has already raised a query or asked for a document on | same |
| F02 | One application across four mails: the same card updates | pass | 1 | decision · Download the recognition certificate (v2) | same |
| F03 | A connector introduces an investor, then nudges twice | pass | 1 | decision · Write to Rahul Menon directly: thank him | same |
| F04 | The introduced contact replied the same day; the reply is owed | pass | 1 | decision · Reply to Sofia Brandt accepting a twenty-minute product demo | same |
| F05 | The introduced contact replied five days later; the reply is owed | pass | 1 | decision · Reply to Marco Ruiz with a short deck attached, a line (v2) | same |
| F06 | The introduced contact asks when to meet | pass | 1 | decision · Answer Nikhil Bose: confirm Thursday (v2) | same |
| F07 | After a call with an introduced contact: was anything promised? | pass | 1 | investigation · Can you tell us whether the call took place as booked? (v2) | same |
| F08 | Two introductions nobody answered | pass | 0 | — none (silent) | same |
| F09 | The connector answers the founder's reply with its own ask | pass | 1 | decision · Answer Introly's question in one line: the seed round | same |
| F10 | An investor follows up after a demo day and asks for the data room | pass | 1 | decision · Reply to Kiran with the data-room link | same |
| F11 | An investor reaches out and asks whether the founder is raising | pass | 1 | decision · Reply to Tom that you are raising your seed round now | same |
| F12 | An investor's question before a booked call — a prep card a day ahead | pass | 1 | decision · Send Neeraj retention for the first three pilot customers (v2) | same |
| F13 | An investor asks for traction metrics before his partners' meeting | pass | 1 | decision · Email Mohit a one-page summary of current traction | same |
| F14 | An investor who asked for real news only — the right move is to wait | pass | 0 | — none (silent) | same |
| F15 | The founder's outreach to five funds, eight weeks without a reply | fail | 0 | — none (silent) | 5 investigation cards, one per fund ("What is the next step with Cobalt Peak? We held …") |
| F16 | The founder's mail to a fund bounced | pass | 1 | decision · Find Lattice's correct address, a named partner if possible | same |
| F17 | An accelerator moves the founder's application to interview | pass | 1 | decision · Book a thirty-minute interview slot through Gulf Launchpad's | same |
| F18 | A state innovation fund opens a round — read and triaged | fail | 0 | — none (silent) | same |
| F19 | An incubation cell: three people, three asks | pass | 1 | decision · Answer the cell's three asks today (v2) | same |
| F20 | A foundation sends its newsletter and a meetup invite | pass | 0 | — none (silent) | same |
| F21 | A management school's enterprise centre writes twice | pass | 1 | investigation · Can you tell us whether an application to this programme went in, with a receipt? | same |
| F22 | A university startup cell announces a seed grant | pass | 1 | investigation · Can you tell us whether you are a startup incubated on the university's campus? | same |
| F23 | A state startup mission writes four times | pass | 0 | — none (silent) | same |
| F24 | An accelerator's assignment and review — each due date seen two days ahead | pass | 1 | decision · Upload the Phase-1 review deck to the cohort folder (v3) | same |
| F25 | One job offer: one file and one card, not six | pass | 1 | decision · Get the board's approval of the ESOP pool now (v2) | same |
| F26 | A partner proposes a call time, then confirms it | pass | 1 | decision · Reply to Neha to confirm Tuesday 30 Sep at 11 am IST (v2) | same |
| F27 | A partner's open question before a booked call | pass | 1 | decision · Check whether our agent can read Cleanwave's webhook events (v2) | same |
| F28 | A partner asks for the security questionnaire before a booked call | pass | 1 | decision · Send Ishita our security questionnaire answers (v2) | same |
| F29 | Two calls with a partner in one day: prep before, follow-up after | pass | 1 | decision · Send Aman the API pricing sheet now unless it reached him (v3) | same |
| F30 | The founder's own promises on WhatsApp belong in their files | pass | 0 | — none (silent) | same |
| F31 | A cohort session of fifty founders: no recap, only the assignment | pass | 1 | decision · Block time this week to write Assignment 4 | same |
| F32 | Program newsletters are archived, never a card | pass | 0 | — none (silent) | same |
| F33 | Vendor receipts and marketing are archived, never a card | pass | 0 | — none (silent) | same |
| F34 | Co-founder matching digests and a fellowship newsletter are archived | pass | 0 | — none (silent) | same |
| F35 | A review notice that says no fee applies is never a payment card | pass | 0 | — none (silent) | same |
| F36 | The founder's own sent mail is never 'awaiting reply' from him | pass | 0 | — none (silent) | same |
| F37 | The connector is never the person to reply to | pass | 1 | decision · Reply to Farah directly with the deck, before the twelfth. | same |
| F38 | A question answered on another channel is not owed again | pass | 0 | — none (silent) | same |
| F39 | The founder's own availability proposal is not a deliverable | pass | 0 | — none (silent) | same |
| F40 | A meeting nobody confirmed took place is never recapped | pass | 0 | — none (silent) | same |
| F41 | Your own company address is never someone you wait on | pass | 0 | — none (silent) | same |
| F42 | An investor's ask that names the founder is about the investor | pass | 1 | decision · Reply to Manav with a one-page summary of current traction | same |
| F43 | Your own pitch names the thread after the investor, never after you | pass | 0 | — none (silent) | same |
| F44 | An investor writing from Gmail is not one of us | pass | 1 | decision · Reply to Kavita with your deck and ask her to pick a time | same |
| F45 | The founder answers an investor's questions at several speeds | pass | 1 | decision · Introduce Meera Shah to the two pilot leads who agreed (v2) | same |
| F46 | An investor answers in the founder's other mailbox — both are read | pass | 1 | decision · Reply to Ravi Iyer with your deck, apologise for the wait | same |
| F47 | A pitch bounced, in the shape Gmail sends it | pass | 1 | decision · Find a working address for Ardent Ridge | same |
| F48 | An introduction the founder answered only to the introducer | pass | 1 | decision · Write to Tarun directly | same |
| F49 | The founder's own promise in a sent mail, not kept | pass | 1 | decision · Book a time on Kunal's calendar through the link he sent | same |
| F50 | An investor's two questions answered with the founder's template | pass | 1 | decision · Write back to Owen with the two numbers he asked (v2) | same |
| F51 | Two slots offered for a call, never confirmed | pass | 1 | decision · Take one of Sana's two times — Tuesday 4 Aug at 3pm | same |
| F52 | A fund's not-yet from April whose condition is now met | pass | 1 | investigation · Can you tell us how many paying customers you have today? | same |
| F53 | A fund gone cold after four real exchanges | pass | 0 | — none (silent) | same |
| F54 | A founders' mixer attended, and no follow-up in seven days | pass | 2 | investigation · …whether you went to the event and spoke with Kavya?<br>investigation · …spoke with Rhea? | same |
| F55 | Four weeks of no outbound while three people wait | pass | 3 | monitor · Send Dev Malhotra the pricing sheet<br>decision · Reply to Rhea with an apology for the delay and new times<br>decision · Reply to Kabir with a clear answer on the pilot | same |
| F56 | A login vendor's renewal notice at a 32% higher price | fail | 0 | — none (silent) | same |
| F57 | An ask answered with the signed document, and never raised again | pass | 1 | decision · Sign the mutual NDA and send it to Zoya. (ended: verified) | same |
| F58 | Your company domain is also the platform's: still you | pass | 0 | — none (silent) | same |
| F59 | Three introductions in three threads: three files, a card each | pass | 3 | decision · Send Tara Sethi your deck…<br>decision · Offer Dev Malhotra a 30-minute demo<br>decision · Answer Anaya Kulkarni by Monday… | same |
| F60 | Three introductions forwarded in one thread: split per contact | pass | 3 | decision · Offer Rhea Kapur a demo…<br>decision · Offer Vikram Nair a call…<br>decision · Send Kiran Bhat your deck | same |
| F61 | One introduced contact replied, two stayed silent | pass | 3 | decision · Confirm the call with Sana Qadri… (v2)<br>decision · Write to Omkar Joshi…<br>decision · Tell Tanvi Shah whether you will apply | same |
| F62 | One contact's call is booked, another's time only proposed | pass | 1 | decision · Accept Ira Menon's call on Tuesday 12 August at 11 am | same |
| F63 | The introduction leaves the contact's address out | fail | 1 | investigation · Can you tell us whether Ishaan will write first? | same |
| F64 | A declined introduction clears and never comes back | pass | 0 | — none (silent) | same |
| F65 | An investor asked for news only on real milestones | pass | 1 | decision · Send Leah a short note on the pilot teams (ended: called wrong) | same |
| F66 | A correction for a whole kind of work | pass | 2 | decision · Send Ines a short note…<br>decision · Send Marcus a short note… (both ended: cleared) | same |
| F67 | One click is never a pattern | pass | 2 | decision · Pick an interview slot<br>decision · Reply to Nadia that you would like to present (ended: called wrong) | same |

## 5 · What a real card says today, in full (F24, today's path)

```
Lane          decision · prescriptive · surfaced · 3 versions
Headline      Upload the Phase-1 review deck to the cohort folder
About         Divya Raman · watched (the programme)
Why now       Nothing in 13 days — longer than this file has gone quiet before (11.96 days)
What remains  Divya Raman asked a question — waiting on you since 1 Sep; … since 13 Sep
Recommended   Upload the Phase-1 review deck to the cohort folder by the twenty-eighth, and check the
              folder holds the unit economics sheet — if it does not, upload it and tell Divya.
Alternative   If the deck cannot be ready by the twenty-eighth, tell Divya before the date and ask what
              the programme allows.
Wait or stop  Nothing to wait for; the moves are ours, and they are done when both are in the folder
              before the review.
Window        2 days · capability expert.file_review · confidence {C 80, I 56, U 80}
```

[`06-CARDS-TARGET.md`](06-CARDS-TARGET.md) §2 shows this same card after GeniOS-009.
