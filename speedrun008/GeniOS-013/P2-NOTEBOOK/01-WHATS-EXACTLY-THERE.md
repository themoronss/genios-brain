# P2 · Notebook (Context Graph, L3) · 01 · What's exactly there

**The part:** GeniOS's memory of the company. It holds two things:
- **evidence:** what every source said (mail, calendar, Screen, other tools, executions, the founder's own actions);
- **conclusions:** what GeniOS concluded (who we are, who is who, the business situations, their questions and promises, what we told people, links, goals).

Each conclusion is versioned and backed by evidence. The **code check** that runs before anything is kept also belongs here, and so does each item's lifecycle (live, dormant, done, history). The Notebook decides nothing itself; P4 decides and the Notebook keeps.

**In the architecture's words:** L3 is the Evidence Graph (what the sources said) plus the Intelligence Graph (what GeniOS concluded). "L3 only remembers what L2 concluded."

**Measured on:**
- **the product:** the local copy of the design partner's org, cut on 28 Oct at 12:45 UTC. Its production data was started from empty on 21 Oct, so this is one tenant's first week ([P1 01](../P1-ORCHESTRATOR/01-WHATS-EXACTLY-THERE.md));
- **the notebook:** build `b2`, as of 23 Oct 01:40 UTC.

The queries are in [06](../06-MEASUREMENTS.md) and in this part's log line in [08](../08-LOG.md).

**Status key:** ✅ works · 🟡 partly works · ❌ doesn't work · ⬜ not built.

---

## 1 · Every function of the Notebook, and whether it works

### 1.1 · Keeping the evidence

| Function | Product | Notebook |
|---|---|---|
| Keep every captured item, with where it came from | ✅ 4,784 events, each with its encrypted raw copy and 105,066 provenance links | ✅ 1,829 mails, 142 meetings |
| Keep the words long enough to remember the work | 🟡 Clean text is kept **180 days after capture**, and the encrypted raw mail 180 days (365 for parked items). The clock starts at capture, not at the mail's date, and ignores whether live work still cites it | — It reads the copy |
| Read an archived mail when it matters | ❌ by design. 636 of 1,829 mails were archived **with no clean text**; only the encrypted raw copy remains | ✅ 635 of 636 recovered from the raw copy |
| Join meetings to the work | 🟡 142 meeting nodes; rule situations of type "meeting follow-through" | ✅ Meetings matched to situations. Each has `known_at`, so a build sees a future meeting only if it was known by then |
| Screen, the founder's actions, executions, other tools | ❌ Stored, never joined to the work: 1,249 Screen events, 141 Screen thread summaries, 211 card events, 105 executions | ⬜ Mail and calendar only |
| The founder's answers and corrections | ❌ **40 questions asked, 0 answered** (22 open, 18 retired). 0 decisions, 0 corrections | ⬜ |

### 1.2 · Who we are, who is who

| Function | Product | Notebook |
|---|---|---|
| Who we are | 🟡 Computed on each read from seats, the signup address, connections and a declaration table, which has 0 rows. The company brief: 29 lines proposed, **0 accepted** | ✅ One company page: names, founders, our addresses, what we do, 15 pursuits, 15 numbers we told people (each found word for word) |
| Who is who | 🟡 365 people and 163 companies. Upkeep passes fix their names. A role is rarely stored | ✅ 667 parties, each with its kind (investor, accelerator, connector, candidate …) and one line on what it is **to us** |
| The company's time zone | ✅ `orgs.timezone` is set | 🟡 Known from the copy, but never printed to the judge (P1 F6) |

### 1.3 · The business situations

| Function | Product | Notebook |
|---|---|---|
| The business situation is the unit | ❌ Two units, neither of them the situation: **264 "files"** (one per counterparty, computed on each read and thrown away), and **1,528 rule situations** of fixed types. **730 of the 1,164 active ones are support-desk types** although Support is off | ✅ **423 situations.** Each introduction is its own; the intro platform's housekeeping is one more. All 17 in-copy ideal items were found |
| Where each one stands: status, stage, whose move and since when, what is expected next, from whom, by when | ⬜ Not stored anywhere | ✅ On every page |
| Questions and promises close only with proof | ❌ **208 of 212** questions open; **87 of 87** promises open (83 past their date) | ✅ 432 loops: 264 open and 168 settled or ended, each with the mail that settled it. 58 closures were refused for lack of proof |
| What we told people | ❌ Amounts are stored as plain numbers and never compared (`p1`) | ✅ 114 claims, word for word, from our own sent text: metric, value, to whom, when |
| Links between situations | 🟡 264 correlations, by counterparty | 🟡 138 links: 130 made by code ("part of"), 8 by the relate call. Facts don't travel between situations (`i1`) |
| Versions: what changed and why | ⬜ The brain's results stay in shadow | 🟡 824 page versions, with the full admitted change but no one-line "what changed and why" |
| Lifecycle: live, waiting, dormant, done | 🟡 A 45-day default puts quiet work to sleep: 282 dormant, 80 resolved | ❌ Nothing decays |

### 1.4 · Goals

| Function | Product | Notebook |
|---|---|---|
| Goals proposed | 🟡 7 proposed on days 5–6, by the weekly drafter and the brain | 🟡 15 goals, at the wrong grain (N3) |
| The goal object: target, plan, progress, status, next move | 🟡 The columns exist in `company_goals` (metric, target, deadline, parent) and are empty | ❌ A sentence, a category, a why, linked situations |
| Confirmed by the founder | ❌ 0 approved: the door is "accept a brief line", and 0 of 29 are accepted | ⬜ |
| One set of links from situations to goals | ❌ 0 rows in `goal_situation_links`; 0 of 111 cards carry a goal | ❌ Two link sets that disagree on 53 of 233 situations |

### 1.5 · The check before anything is kept

| Function | Product | Notebook |
|---|---|---|
| Check change by change, keep the rest | ❌ Two admissions, neither applied. The old situation admission (985 decisions: 526 admitted, 459 held). The L2 admission, in shadow (34: 24 admitted, 8 held, 2 rejected; nothing written). The claim check held 66 of 86 whole results over single lines | ✅ 115 changes held, each with its reason, and their pages kept. Among them: 58 closures without proof, 27 ids the model was not shown, 15 claims not in our own new text, 11 mails moved out that the page itself cites, 3 quotes not word for word |
| Invariants the database must always satisfy | ⬜ | ✅ 7 of 7 pass |

### 1.6 · Size, isolation, erasure

| Function | Product | Notebook |
|---|---|---|
| Fit in its database | ❌ **570 MB against a 472 MB ceiling** on 27 Oct (§4) | ✅ A few MB per build; 54 MB for every build and test build together |
| Keep tenants apart | ✅ An org id on every row; every read filters by it | — One org |
| Erase a tenant | ✅ An erasure path for every table it lists | — |

## 2 · In the product: an archive with no notebook

| What | Where | What's in it |
|---|---|---|
| Raw events | `source_events` | Gmail 3,381 rows, Screen 1,249 (22–28 Oct only), calendar 154. Every mail's visibility is "participants" |
| Mail kept for reasoning | the capture gate (L1) | 1,829 unique mails: 1,193 went on to reasoning, 636 were archived without clean text, 547 attachments were parked unread |
| **Evidence Graph** | `graph_nodes`, `graph_facts`, `graph_edges` | **16,792 facts:** 10,644 computed by code and 6,148 read from events, **none from the brain**. 2,268 nodes: 1,070 threads, 365 people, 163 companies, 142 meetings, 87 commitments. 2,352 relations. `authority_rank` holds two different scales in one column |
| The support desk, for a tenant without Support | `context_situations`, `graph_facts` | 718 "first response overdue" situations (667 active), 63 "ticket ageing", and **3,590 facts** (21% of all) tracking first responses |
| One-line objective per thread | `graph_facts` `thread.objective` | 603 threads. A good input for onboarding (GeniOS-013 U13-28) |
| Files | `context/workstreams.files_for` | **264, computed on each read, per counterparty, never stored** ("a file is one counterparty's correlations") |
| Rule situations | `context_situations` | **1,528**, from a fixed list of types: 1,164 active, 282 dormant (a 45-day default), 80 resolved |
| Promises and questions | facts and `open_loops` | Promises: **87, all still open** (83 past their date). Questions: **208 of 212 open**. "Conflicts": **40 of 44** are about dates |
| **Intelligence Graph** | the L2 admission | **In shadow** ("SHADOW: nothing here touches the situations"). 30 interpretations were written and nothing reads them |
| Goals | `company_goals` (migration 0254) | **7 proposed** (4 by the weekly drafter, 3 by the brain), **0 approved** |
| The approval door | `company_brief_lines` | 29 proposed lines, **0 accepted** |
| Goal links | `goal_situation_links` (0255) | **0 rows** |
| Goals on cards | `cards.goal_refs` (0256) | **0 of 111** cards |
| The founder's side | `card_events` 211, `card_feedback_verdicts` 3, `moment_feedback` 133, `founder_questions` 40 (0 answered), `decisions` 0, `founder_corrections` 0 | Stored. No reasoning step reads them back |
| Executions | `executions` 105, `execution_actions` 308, `execution_outcomes` 55, `situation_outcomes` 526 | Stored. Not joined to a situation's page |
| Screen | `screen_thread_summaries` 141, `screen_thread_verdicts` 413, `screen_session_deltas` 3,167 | Stored. Not joined to situations |

## 3 · In the notebook: the Intelligence Graph, built locally

**Schema:** `notebook.*` (`nb/schema.sql`). Conclusions are keyed by **build** (one instant, one model); evidence is shared across builds. Rows are never deleted: a new start means a new build id.

### Evidence (Phase A, `nb/evidence.py` and `nb/recover.py`)

| Table | Rows | Notes |
|---|---|---|
| `notebook.mail` | 1,829 | Subject, full body, and the new text above the quoted history. Also: direction, recipients, bounce (real delivery failures only: 7), calendar invite, attachment kinds. **635 of the 636 archived mails have their text recovered** from the stored encrypted payload (`text_source = 'recovered'`) |
| `notebook.meetings` | 142 | Each has `known_at`, the first time the copy recorded it |
| `notebook.claim_candidates` | 89 | Amounts the capture pipeline read in our own sent mail |

### Conclusions (build `b2`)

| Table | Rows | What it holds |
|---|---|---|
| `company` | 1 version | Who we are (§1.2) |
| `parties` | 667 | Who is who (§1.2) |
| `works` | 423 | **The business situations:** title, kind, status, stage, whose move and since when, next expected (what, from whom, by when, what if missed), importance, goal links, the latest verdict (summary, frame, evidence ids, unknowns), card, version |
| `work_versions` | 824 | Every saved page version, with the full admitted change |
| `members` | 2,540 | Which thread, mail or meeting belongs to which situation. The judge moved 106 out (`left_at`); a thread moved out of every situation gets one of its own |
| `loops` | 432 | Questions, asks and promises: who owes them, the opening mail, the due date, the status (open 264, broken 51, moot 47, superseded 31, kept 24, answered 10, released 5), and the mail that settled them |
| `claims` | 114 | What **we** told people about ourselves: metric (MRR 33, pilots 17, design partners 16, ARR 10 …), the value as written, to whom, when |
| `links` | 138 | Between situations: part of, evidence for, contradicts, duplicate |
| `goals` | 15 | Statement, category, why, the situations that serve it (`work_ids`), evidence. **No target, plan, progress, status or next move** |
| `held` | 115 | Every change the code refused, **as the model proposed it**, with the reason |
| `cards` | 63 open | One per situation (P5) |
| `runs`, `state` | | Every model call and its cost. Per-build state: the instant, the model, noise threads, unplaced meetings, notes on the whole picture |

**What each phase cost on `b2`:**
- company page: $0.10;
- parties: $0.66;
- situations (grouping, 107 calls, 2.7 min): $1.11;
- judging 378 situations: $6.37;
- relate: $0.17.

### The code check before anything is kept (`nb/checks.py`)

A change is held, on its own and with its reason, when it:
- cites an id the model was not shown;
- quotes words that are not in the cited mail (case, quote marks, links, list markers and invisible characters are folded first);
- claims something as ours that isn't in the **new** text of our own outbound mail;
- closes a question or promise without a **later** mail from the side that owed it, or with a bounce, an unreadable mail or a meeting;
- gives a date that isn't real, or a "since" date in the future;
- moves out a mail the same page cites.

One bad line never holds the whole page. The live product held 66 of 86 pages that way.

### What always holds (7 database invariants, `tests/test_invariants_db.py`, all passing on `b2`)

1. Every member mail exists.
2. Every thread is in a situation or marked noise.
3. Every settled question or promise was settled by the right side's later member mail.
4. Every claim is word for word and ours.
5. Every open card sits on a live situation, and its quotes are real.
6. Goals and links point at things that exist.
7. Spend is under the cap.

## 4 · Where the space goes (the product, one tenant)

The local copy holds only this org's rows, loaded fresh. Its `public` schema takes about **280 MB**; production reported **570 MB** for the same database on 27 Oct. Production's own table sizes were not read. The gap is most likely dead rows from rewriting the whole company on every chain (P1 F9), waiting for the database to reclaim them.

| Table | Size in the copy | Rows | What it is |
|---|---|---|---|
| `graph_source_refs` | 49 MB | 105,066 | Provenance: which event backs which fact |
| `screen_session_deltas` | 45 MB | 3,167 | Encrypted Screen captures, **one week's worth** |
| `raw_payloads` | 30 MB | 4,784 | Encrypted raw copies of every event |
| `graph_facts` | 18 MB | 16,792 | The Evidence Graph's facts |
| `situation_admission_decisions` | 13 MB | 985 | The old situation admission |
| `event_trace` | 12 MB | 32,942 | Pipeline trace lines |
| `expertise_packages` | 10 MB | 100 | Compiled expertise (purged to the newest each sweep) |
| `prepared_content` | 7.7 MB | 3,801 | Clean text |

The whole notebook, with every build and test build, is 54 MB. One build's conclusions are a few MB.

## 5 · How long evidence is kept (the product)

Measured from the rows' own expiry dates:

| What | Kept after capture |
|---|---|
| Clean text of a mail, an event or a Screen session | 180 days |
| Encrypted raw mail (emitted or archived) | 180 days |
| Encrypted raw parked items | 365 days |
| Encrypted raw Screen sessions | about 270 days |

Two things follow:
- An onboarding that captures 365 days loses the clean text of all of it **180 days later**, whatever the mail's own date.
- A situation that lives longer than that loses the words behind its earlier pages, unless the page kept them.
