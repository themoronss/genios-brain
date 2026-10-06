# 09 · What Rohit expects, and what STEP-00 to STEP-18 actually build

**Asked 2026-10-06** by Rohit, with five documents: *"Will the results I expect come this time? Are we
building properly for this level of intelligent cards, or are things still being missed?"*

| Document | Path (Rohit's machine) | What it sets |
|---|---|---|
| GeniOS vs LLM benchmark | `~/Downloads/Artifacts/genios-vs-llm-benchmark.html` | five prompts P1–P5 on this mailbox; the bar GeniOS must clear (six checks) |
| Design Atlas v2 | `~/Downloads/Artifacts/genios-design-atlas-v2.md` | the architecture; the fix list P0·1–P2·17 (V.2); the measures (V.4) |
| Sole Mate, Admin Domain Intelligence | `~/Downloads/Artifacts/GeniOS-Admin-Domain-Intelligence-SoleMate.html` | a manager (Anisha) preparing six documents for an audit; ten pass conditions |
| Admin Possibility Atlas | `~/Downloads/GeniOS Admin Possibility Atlas.html` | 98 possibilities; the V1 wedge; the 30-day pilot and its scorecard |
| Design Atlas v2 (HTML) | — | same content as the `.md` |

Every row below was checked against the plan files in this folder and, where it names code, against
`speedrun008` @ `f0ee8225`. Production was not read.

---

## 1 · The short answer

1. **Not after STEP-04.** STEP-00 to STEP-04 stop the engine from deleting mail, re-deciding every
   sweep, and pinning cards on the founder. They are the floor. They produce no new intelligence.
   The measured board is still the before-score (`03-FINDINGS` §F.1): must-detect **4 / 30**,
   must-abstain **5 / 10**, Atlas replays **0 / 80**.
2. **The documents' level of card first becomes possible at STEP-12 to STEP-14.** That needs:
   - the data in memory (STEP-05, STEP-08);
   - the files (STEP-09), their history and numbers (STEP-10), and the playbooks (STEP-11);
   - then one judgment per file (STEP-12), every claim checked (STEP-13), and the gold-shape card
     (STEP-14).

   The morning brief is STEP-15. Learning from Rohit is STEP-16.
3. **Even with all eighteen steps built as written, eight things the documents expect are missing**
   (§3):
   - five are small additions to existing steps;
   - one is a decision (how far back);
   - one is a new step (the benchmark re-run);
   - one is a separate block (Sole Mate: a team, its documents, more connectors). It is not
     reachable on Gmail + Calendar for a one-person company.
4. **"Perfect" will be a number, not a feeling.** The golden board says whether the engine catches
   what was labelled. The benchmark re-run (§3, G2) says whether it beats Claude with plain
   connectors. Neither number exists until those steps run.

---

## 2 · Where each expectation is built

### 2.1 · The benchmark — "the bar GeniOS now has to clear"

| The bar | Where the plan builds it | Covered? |
|---|---|---|
| Catch the bounces (Afore ×2, Surge) | STEP-03: the bounce report is kept, not deleted. STEP-04: it was our mail. STEP-10 §3.5: DSN → `DELIVERY_FAILURE` on the investor's file. Golden case F16 | ✅ planned, guarded |
| Catch the Radhesh miss — the founder's reply went only to the introducer | STEP-09 §3.2, §3.4, §3.5: an intro is split per contact; roles checked against headers; the intro stages | ⚠️ the design can catch it. **No golden case has this shape** (G1) |
| Answer P3 (6 months) and P4 (12 months) at full scope | STEP-08 resync, D5 = 180 days | ❌ P4 needs 12 months, P5 is all-time (G3). There is no surface that answers a question (G2) |
| State indexed vs total for every answer | STEP-10 §3.10: a coverage receipt per workstream. STEP-06: an end state for every item | ✅ for cards; ❌ for answers (G2) |
| Resolve the 3one4 contradiction with the verbatim quote | STEP-13 §3.1: every fact cites evidence. STEP-14 §3.5: a quote claim needs the quote | ⚠️ the mail is from **2 Apr 2026**, 187 days before today. **D5 = 180 loses it** (G3) |
| Stay in the window the user set | — | ❌ only meaningful once questions can be asked (G2) |

**The five findings it says to act on:**

| Finding | Where the plan builds it |
|---|---|
| Afore and Surge never received the pitch | as above (F16) |
| 28 days of zero outbound while fundraising, people waiting 46–77 days | STEP-09 open loops; STEP-10 §3.2 latencies and §3.3 silence; STEP-15 brief. **No case: a founder-level silence is a brief item, not a file** (G1) |
| The 11 Aug template killed live threads | STEP-10 §3.4 the wave as one object (F15). STEP-13 §3.4 an ask closes only on a matching answer. **No case: a template reply to a specific question** (G1) |
| The founder never wrote to Radhesh | as above |
| Follow-through collapsed after six rejections | STEP-10 §3.8 history; STEP-16 §3.4 behaviour patterns, observe-only. Brief-level at best; the benchmark itself calls it founder behaviour |

### 2.2 · The Design Atlas fix list (V.2)

| Atlas item | Plan | Covered? |
|---|---|---|
| P0·1 activate Admin, org data; **exit: one situation signal → card → approval → execution → verified outcome** | Admin is switched on for every tenant: `activation.default_on: true` (`Domain Expertise/Admin Expertise/domain.yaml:50`, read by `platform/intelligence_onboarding.py:119-138`). STEP-16 §3.3: outcomes close loops | ⚠️ no case runs the whole chain to a *verified* close (G6) |
| P0·2 five pipeline counters | STEP-06 §3.2 `situation_outcomes`; M17 B17 (zero decisions recorded) | ✅ |
| P0·3 lanes, not a scalar floor | STEP-13 §3.5 | ✅ |
| P0·4 temporal and relationship before risk | STEP-12: the dossier gives the expert the timeline and the numbers before it judges | ✅ by construction, not by re-ordering Plane R units |
| P0·5 claim-level validation | STEP-13 §3.1–3.3, STEP-14 §3.5 | ✅ |
| P1·6 coverage receipts, absence signals | STEP-06, STEP-10 §3.3, §3.10 | ✅ |
| P1·7 EvidenceNeed — an investigation resolves itself | STEP-13 §3.6 | ✅ |
| P1·8 six object types | commitment (exists), condition (STEP-11 01), open question (STEP-09 §3.6), delivery status (STEP-10 §3.5), meeting follow-up link (STEP-05 §3.4 + STEP-11 06), thread terminal state (STEP-09 stages) | ✅ spread across steps |
| P1·9 organisation and behaviour brains | behaviour: STEP-10 + STEP-16 §3.4. Organisation: STEP-07's brief is the founder's version | ⚠️ no owners, approval limits or backups (G7) |
| P1·10 corpus hygiene (Admin's `document.*`) | — | ❌ not in YC-II W27 (G7) |
| P1·11 the orchestrator loop | STEP-02 (gate, fingerprint), STEP-12 (one pass, cached on the fingerprint) | ✅ |
| P2·12 attribution, "Wrong because…" | STEP-16 §3.1–3.2 | ⚠️ reasons are kept; the layer that failed is not named |
| P2·13 bounded bitemporal read | STEP-12 §3.1 uses `context/bounded_read.py` | ✅ |
| P2·14 re-home 59 capabilities | — | not in scope (Admin-only, founder first) |
| P2·15 Screen into the graph | STEP-05 §3.7, STEP-09 §3.2, STEP-14 §3.6 | ✅ |
| P2·17 reach beyond 60 days, **exit: P3 and P4 answered** | STEP-08, D5 = 180 | ⚠️ P3 yes, P4 no (G3) |
| V.4 benchmark re-run, P1–P5 + Recall@10 | — | ❌ (G2) |

### 2.3 · Sole Mate — the ten pass conditions

| Pass condition | Plan | Covered? |
|---|---|---|
| Identifies the business situation | STEP-09 + STEP-12 (frames, rival frames) | ✅ |
| Avoids unsupported assumptions | STEP-13 | ✅ |
| Missing vs not visible in sources | STEP-10 §3.10 coverage; STEP-13 unknowns | ⚠️ said for replies; documents are not tracked (G7) |
| Declared vs inferred ownership | — | ❌ no owner model beyond "us" (G7) |
| Recognises work that is genuinely complete | STEP-13 §3.4, STEP-16 §3.3 | ✅ |
| Refuses to mark complete without evidence | STEP-16 §3.3 (outcome recorded) | ⚠️ no case (G6) |
| Owner absence and valid backups | — | ❌ (G7) |
| Communicates uncertainty | STEP-12 unknowns, STEP-13 lanes, STEP-14 confidence vector | ✅ |
| Actionable without noise | STEP-02, STEP-14 §3.1 one file one card, STEP-15 | ✅ |
| Stops raising after verified completion | STEP-06, STEP-13 §3.4, STEP-16 §3.3 | ⚠️ no case (G6) |

Its method — run the scenario, find the first layer that broke, fix, replay — is the golden set's
method (STEP-01). The golden board already says where each case was lost (gate, before memory, in
reasoning).

### 2.4 · The Possibility Atlas — the V1 wedge and the pilot

| Promise | Plan | Covered? |
|---|---|---|
| Commitments and follow-ups | STEP-09 open loops, STEP-15 "your promises due" | ✅ |
| Meetings to actions | STEP-05 §3.4, STEP-11 06, STEP-15 prep | ✅ |
| Decisions and approvals | — | not needed for a one-person company |
| **Vendor and subscription renewals** — its first example card is a login vendor renewing at +32% | workstream kinds are investor, program, intro, hire, partner, compliance, internal (STEP-09 §3.1); vendor receipts are archived (F33) | ❌ a renewal never becomes a file, so the expert never sees it (G5) |
| Weekly scorecard: usefulness, silence, coverage, outcomes | the data exists (STEP-06, STEP-10, STEP-16); no scorecard | ❌ (G6) |
| "At least one situation proven end to end" | — | ❌ (G6) |

---

## 3 · The gaps, and the fix for each

**G1 · The test bed does not contain the benchmark's best findings.**

*Why.* The golden labels cover **4 Aug → 5 Oct** (`golden-labels.md`), the old 60-day window. The
benchmark's highest-value items started before that:

| Person | What is open | Days (as of 23 Sep) |
|---|---|---|
| Keshav (RocketSDR) | "I will book it again" | 77 |
| Aditya (IIMA Ventures) | his slot proposal, never answered | 71 |
| Radhesh (Suvan) | the reply went only to the introducer | 69 |
| John (Actual.ai) | a booking never confirmed | 63 |
| Vatsa (Valiron) | "I will book directly" | 58 |
| Piyush (3one4) | "re-engage once … traction" | 2 Apr |
| Neon | four real exchanges in March, then silence | — |

So the engine could pass its own golden set at 90% and still miss them.

*Fix.* After STEP-08 brings that history back, add synthetic cases in the same method. Rohit
labels; ideal-reader cassettes; real names never appear in the cases.

- **must-detect:**
  - the founder replied only to the introducer;
  - the founder's own promise in a sent mail, not kept;
  - a specific question answered with a template;
  - a booking the founder never confirmed;
  - a deferral from months ago whose condition may now be met. The case carries the verbatim
    quote and its date. A traction number that is not in the evidence is a **forbidden** output
    (one model invented one in the benchmark).
- **brief only:**
  - a relationship that went cold after real exchanges;
  - an external event with no follow-up in 7 days (cohort sessions excluded, as F31);
  - weeks of zero outbound while people wait.

Owner: Claude. Size: one tree block, about nine cases. It lands as STEP-08's acceptance.

**G2 · No step re-runs the benchmark.**

*Why.* The Atlas calls it *"the only fair 'beats an LLM' claim"* (V.4). The Possibility Atlas lists
*"GeniOS beats ChatGPT"* among the numbers nobody may claim before it runs. The plan has no step
for it.

There is also no surface that answers a question. `POST /v1/intelligence/query`
(`api/intelligence_routes.py:343`) exists. It is the older graph-facts Q&A: module `sales` by
default, and it does not read workstreams or timelines.

*Fix — a new STEP-19, after STEP-10, small:*

- five ledgers as read views over the data STEP-09 and STEP-10 already build:
  - relationships and reciprocity;
  - commitments;
  - cold threads;
  - meeting × mail follow-up;
  - conditions;
- one model call that words the answer from a ledger, under STEP-13's checks. Every number is
  computed; every quote is verbatim; the window and the coverage line are stated;
- the same five prompts on the same mailbox, scored blind on the six-dimension rubric, with a
  planted answer key (Recall@10). The result is published with the rubric, win or lose (Atlas
  V.4, *"the number that would prove us wrong"*).

**G3 · How far back: D5 = 180 days is too short for P4 and P5.**

| Prompt | Horizon | What 180 days loses |
|---|---|---|
| P3 | 6 months | — |
| P4 | 12 months | half the window |
| P5 | all time | the 3one4 deferral (2 Apr 2026) and the Neon exchanges (March) |

- *Fix.* D5 = **365 days**. `06` D5 itself says more history *"costs little, because only
  high-attention mail is read by the model."*
- *Alternative.* 365 days for threads the founder wrote in, 180 for the rest.
- Rohit's decision (D16 below).

**G4 · The documents and the plan disagree on where the model sits.**

| Source | Where the model sits |
|---|---|
| Sole Mate | *"only layers 2 and 7 touch an LLM, both at temperature zero … every judgement in between is rules and math"* |
| Atlas RULE 02 | *"the model never scores, routes, permits or decides"* |
| Rohit, 2026-10-05 (`06` D1 = A) | the expert's appraisal decides what matters, with its evidence; code checks every claim, computes every number, chooses the recipient and never sends |

The plan follows D1. Anyone grading the build with Sole Mate's text would fail it by design.

*Fix.* Change two lines, in Atlas V.5 *Decided* and in Sole Mate's engine section. Owner: Rohit
(they are his documents). Claude can draft the wording.

**G5 · Renewals are not a workstream.**

*Fix.* In STEP-09:
- add the kind `vendor`: a renewal, a price change, a failed payment, a trial ending;
- add one must-detect case (a renewal with a price rise);
- keep F33: a plain receipt stays archived.

A domain or workspace renewal is real for a founder too. Size: small, inside STEP-09 and STEP-11.

**G6 · Done means done — no case proves it, and no scorecard shows it.**

*Fix.* In STEP-16:
- one end-to-end golden case. An ask arrives and a card is raised. The founder answers with the
  requested thing. The card resolves as **verified**, with the evidence id, and is never raised
  again. The runner already supports several sweeps (F15 has three);
- a receipt for the verified-outcome rate;
- the weekly scorecard the pilot promises: usefulness per lane, what was held back and why,
  coverage, outcomes. All four already exist as data.

**G7 · Sole Mate is a different product shape. It is not in YC-II W27.**

It needs:
- an organisation brain: owners declared vs inferred, a responsibility matrix, approval limits,
  backups, leave;
- document state: received, incomplete, outdated, verified, audit-ready. This needs reading
  attachments (fetch fixed in M17 B19) and Admin's `document.*` vocabulary (Atlas P1·10);
- the connectors it names: Slack, Notion, Jira, HubSpot.

One cheap source is already in Gmail. Out-of-office auto-replies say *who is away until when, and
who covers*. STEP-03 now keeps them; nothing reads them.

*Fix.* A separate block after YC-II W27, built on a team tenant, with a Sole Mate-shaped golden set.
Not before the founder path shows verified outcomes (the Possibility Atlas's own order: *"the other
thirteen areas grow only when these four produce verified outcomes"*).

**G8 · N = 1 mailbox.**

The benchmark warns that Rohit's outbound is small, which flatters general models. *Fix.* Before
any claim, run the golden method on a second, high-volume design-partner mailbox. Owner: Rohit (a
partner's consent).

---

## 4 · Decisions for Rohit

| # | Question | Default if he says nothing |
|---|---|---|
| D15 | Add the benchmark cases to the golden set (G1), as STEP-08's acceptance? | yes |
| D16 | D5 = 365 days instead of 180 (G3)? | **365** — 180 loses the 3one4 deferral |
| D17 | A new STEP-19, the benchmark re-run with five ledgers (G2)? | yes, after STEP-10 |
| D18 | `vendor` as a workstream kind (G5), and G6's case and scorecard in STEP-16? | yes |
| D19 | Sole Mate (G7) as the next block after YC-II W27, not inside it? | yes |
| — | Update Atlas V.5 and Sole Mate's engine section to D1 (G4) | Rohit's own edit; Claude drafts |

## 5 · What does not change

The order is right. Without STEP-03, the gate deleted 33 mail objects across the 40 golden cases (`baseline/yc2w27-s03-qa/`). Without
STEP-02, the decider re-decided ~1,400 times a day and flipped 113 of 118 situations. Without STEP-04,
the founder is the subject of his own cards. No expert can reason over data that was deleted, or
about a person it thinks is someone else.

The shape Rohit asked for on 2026-10-05 is the shape of STEP-07 → STEP-15:
- the model as the manager, not one prompt per mail;
- reading per item stays cheap;
- judgment is one pass per file, only when it changed (STEP-12), and one pass per day (STEP-15);
- every claim is checked by code (STEP-13).

None of the gaps above asks for a re-design. They are what the plan must add to be measured against
the documents.
