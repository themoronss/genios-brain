# 01 · What the local session did, and what the product must do the same way

**Written for:** Harsh and every coding agent. Read this first: it defines the target that every other file in this folder measures against.

> ⚠ This repository is public. Nothing from Rohit's real mail is written here. Cards are named by their ids on `brain.thegenios.com/preview` (`p1`, `f1`…`l1`), never by the people in them. The real content stays in the owner-only preview and in `GeniOS-Ideal-Dashboard/` on Rohit's machine.

---

## 1 · What happened on 23 Oct

1. Rohit asked: *"if the reasoning plane worked ideally, which goals, which cards and which details would GeniOS produce?"* He wanted it shown in a clone of the dashboard, each item in its proper section, for his product pitch and product video.
2. A Claude session (Opus 5.5, 1M context) did the job **by hand**:
   - it read his Gmail and Google Calendar through the claude.ai connectors (the same mailbox production is connected to);
   - it searched by topic, not by thread: investors, accelerators, programmes, the incubator, government registration, intros, customers and design partners, hiring, vendors and renewals, bounces;
   - it opened every thread it found and read it whole, going back to **November 2025** (about 11 months);
   - it read the calendar for past and coming meetings and matched each one to the mail around it;
   - it read Rohit's **sent** mail as carefully as his inbox.
3. It then wrote, by itself:
   - **10 goals**, one per piece of work Rohit is actually pursuing, each with a category, a progress basis and the cards that move it;
   - **2 goal proposals**, which Rohit approves or rejects;
   - **20 cards**, each with the full card contract (§3) and a trace that names the threads and dates it used.
4. The result was built into `GeniOS-Ideal-Dashboard/index.html`. It went live as `brain.thegenios.com/preview`, owner-only, from dashboard `main` `ff13896`.
5. Rohit then asked: *"jab itna aa sakta hai locally toh website pe kya dikkat hai?"* This folder is the full answer, and the build order that closes the gap.

---

## 2 · The target, in numbers

| What | Count | Where it shows on `/preview` |
|---|---|---|
| Goals | 10 | Goals page, grouped by category, each with progress and its cards |
| Goal proposals | 2 | Goals page, "proposed", approve in one click |
| Cards | 20 | Cards page, in lanes (conflict, decide, answer, waiting), filterable by category |
| Categories | 8 | investment, funding, business, sales, projects, progress, process, hiring |
| Domain | 1 | Admin only; the other domains are shown locked |
| Months of history used | ~11 | back to Nov 2025 |
| Cards whose key mail is older than 60 days on 23 Oct | 9 of 20 | `i1`, `i2`, `i4`, `i6`, `s1`, `s2`, `h1`, `b3`, `l1` (dates in [07 §2](../GeniOS-011/07-IDEAL-PREVIEW-LIVE.md)) |
| Cards that needed two or more sources or threads | 13 of 20 | `p1`, `f1`, `f2`, `i1`, `i2`, `i3`, `i4`, `i5`, `s2`, `b1`, `b2`, `c1`, `c2` |
| Cards that needed the calendar | 5 | `p1`, `f1`, `i1`, `i3`, `b2` |
| Cards that rest on the founder's own sent mail | 6 | `p1`, `i2`, `i4`, `i5` (the bounces of sent mail), `i6`, `s2` |

These three rows were counted from each card's `trace.l1` in `GeniOS-Ideal-Dashboard/src/02-data.js`, on Rohit's machine, on 23 Oct.

The card-by-card table (what situation each card is, and which steps make it appear) is in [07-IDEAL-PREVIEW-LIVE §2](../GeniOS-011/07-IDEAL-PREVIEW-LIVE.md). This folder does not repeat it. It goes one level deeper: the code that drops each card today, and the unit that fixes it.

---

## 3 · The card contract the local session met (and the live card does not)

Every one of the 20 cards carries all 15 fields. `scripts/ideal_card_gap.py` (S44.U1, merged) scores a product card against them field by field.

| # | Field | What it is | Who should produce it in the product | Live today |
|---|---|---|---|---|
| 1 | **subject** | one line, starts with a verb, names the person, never cut | L5 card writer (`deliver/card_copy.py`, S34.U3) | ❌ the expert's move cut to 60 chars, with a "Needs a decision —" prefix ([08 §2](08-L5-CARDS-AND-DASHBOARD.md)) |
| 2 | **summary** | two lines: what is happening and why it matters | L5 card writer from the L2 judgment | ⚠ `situation` text, generic |
| 3 | **how** | how GeniOS knows (which threads, which dates) | L5 from the judgment's sources | ⚠ `why` rows, often a hub node's facts |
| 4 | **who / for whom / by when** | the actor, the counterparty, the deadline | L2 judgment (`gold.recommended`) | ✅ on expert cards (`recommended.*`) |
| 5 | **steps** | 2–5 concrete steps | L2 judgment | ❌ the steps tuple is the headline repeated (`reason/expert/decide.py` `_play`) |
| 6 | **avoid** | what not to do | L2 judgment | ⚠ only on the card.v2 projection |
| 7 | **done when** | the evidence that closes it | L2 judgment (`success_signal`) | ⚠ present when the pack has one |
| 8 | **if not** | what happens if nothing is done | L2 (`scenarios.do_nothing`) | ✅ via `do_nothing_consequence` |
| 9 | **alternative** | the second-best move | L2 (`gold.alternative`) | ✅ on expert cards |
| 10 | **draft** | a ready message, 5 lines | L2 judgment (`draft`) | ❌ stored in `cards.artifact`, never rendered by the dashboard |
| 11 | **the goal it moves** | goal id and one line | Goals (G6) + L5 | ❌ no goal object; the dashboard hard-codes "Not linked to a goal yet" |
| 12 | **verbatim quotes** | the counterparty's own words, from up to 3 threads | L3 memory + L5 | ⚠ inside `why` rows, often a bare name |
| 13 | **one cross-thread fact** | something from another thread or the calendar that changes the move | L2 dossier (other files, calendar, goals) | ❌ the dossier reads one file only |
| 14 | **category** | one of the 8 | Plane D map + L5 (N2) | ❌ no category anywhere in the brain |
| 15 | **result** | what doing it gets you | L2 (`scenarios.act`) | ❌ `scenarios.act` never reaches the card |

---

## 4 · Why the local session got it right: seven things it did that the product does not

Each line names what the session did, the layer that must do it in the product (Atlas v2 vocabulary: L1 Signals · L2 Qualification = Plane D + Plane R · L3 Context Graph · L4 Executive · L5 Delivery · L6 Learning), and the file of this folder that covers the gap.

| # | The session… | The product today… | Layer | Gap covered in |
|---|---|---|---|---|
| 1 | **ran at all.** Nothing stopped it. | skips Rohit's whole org on every scheduled sweep if his plan has expired; only Sync now still runs | before L1 (run gate) | [03](03-RUN-GATE-AND-SWITCHES.md) |
| 2 | **read 11 months**, including newsletters-looking mail from Boardy, programme portals and the government portal, the founder's own sent mail, the calendar, and bounce notices | reads 60 days; archives Boardy (N-02 List-Unsubscribe), portals (N-03/N-06); has no word for an intro, a meeting, an application; never writes numbers from sent mail; never turns a bounce into anything visible | L1 | [04](04-L1-SIGNALS.md) |
| 3 | **filed by piece of work**: one investor relationship across many threads; one update sent to 12 people as one subject; one claim stated four ways as one conflict | files by counterparty node, but splits each file into one situation per keyword domain × 45-day generation, mints random ids, never groups a wave as a subject, overwrites an equal-rank conflicting number silently | L3 | [05](05-L3-CONTEXT-GRAPH.md) |
| 4 | **judged like a founder's chief of staff**, with investor and programme know-how, and looked again at quiet files | runs the expert only if switched on; Founder Office knowledge is unreviewed and refused by the compiled lane; a quiet file with no reply pattern is never looked at again; a reply closes the ask even when it doesn't answer it; most real-model answers are held | L2 (Plane D + R) | [06](06-L2-PLANE-D-AND-R.md) |
| 5 | **saw across threads**: the panel today changes what to write to the investor | judges one file at a time, with no other file, no calendar outside the file, no goals | L2 dossier | [06](06-L2-PLANE-D-AND-R.md) |
| 6 | **had goals in mind first** and tied every card to one | has no goal object; goals are accepted brief lines (free text) | Goals (L3 object, L2 proposes) | [07](07-GOALS.md) |
| 7 | **wrote the card for a human**: subject, steps, draft, goal, category | cuts the model's move to 60 characters, drops steps/result/draft, shows no goal or category | L5 + dashboard | [08](08-L5-CARDS-AND-DASHBOARD.md) |

---

## 5 · What the product must NOT copy from the local session

The local session had no budget, no check and no other customer. The product must keep three things the session skipped:

1. **Every claim checked against the mail.** The claim check (`contracts/claim_check.py`) stays. What changes is that a held card is *repaired once*, then written in the founder's words, never as an engineer sentence (S20).
2. **A cost ceiling.** The session read ~470 threads with one large model. The product must do this with a bounded number of calls: rules and code first, the model only where meaning is needed (Atlas v2 §6: 0–3 calls per reasoning run). Every paid pass starts with a 1–2 call probe, and Rohit says yes to the spend.
3. **The same machinery for every customer.** Nothing in the fix may name Rohit's investors, programmes or counterparties in code. What is specific to a company lives in that company's **brief** (accepted lines), its **org data** and its **mail**, never in the engine. Test cases use synthetic analogues (`REAL_NAMES` rule).

---

## 6 · Is there a shortcut? (The "direct LLM" question)

Rohit asked on 23 Oct whether the website could bypass the reasoning plane and run the LLM directly. It can, as a **bridge, not the product**:

- **What it would be:** a brain route, `POST /v1/direct/run`, that reads the connected Gmail and Calendar through the brain's own connectors, sends a bounded digest to one large-model call, and stores the same JSON the preview shows (goals, proposals, cards). `GET /v1/direct/latest` serves it, and the dashboard's real pages read it. The dashboard route `/api/direct` already falls back to it, and is written on a local branch (`rohit/direct-intel`, uncommitted).
- **What it skips:** L3 admission, claim checking, situation identity, the 7-a-day budget, L6 learning. So it cannot be the product's card source for customers, and it would compete with the real cards.
- **Status:** not built. Rohit stopped that work on 23 Oct and asked for this folder instead. If it is ever built, it must be owner-only, behind a switch, capped per day, and labelled "draft from your mail" on every card.

The rest of this folder is the real fix: the pipeline doing what the session did.
