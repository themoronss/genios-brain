# P2 · Notebook (Context Graph, L3) · 01 · What's exactly there

**The part:** GeniOS's memory of the company. It holds two things:
- **evidence:** what every source said (mail, calendar, Screen, other tools, executions, the founder's own actions);
- **conclusions:** what GeniOS concluded (who we are, who is who, the business situations, their questions and promises, what we told people, links, goals).

Each conclusion is versioned and backed by evidence. The **code check** that runs before anything is kept also belongs here, and so does each item's lifecycle (live, dormant, done, history). The Notebook decides nothing itself; P4 decides and the Notebook keeps.

**In the architecture's words:** L3 is the Evidence Graph (what the sources said) plus the Intelligence Graph (what GeniOS concluded). "L3 only remembers what L2 concluded."

---

## 1 · In the product: the archive exists, the notebook does not

**Measured on the copy of the design partner's org (28 Oct). The queries are in [06](../06-MEASUREMENTS.md).**

| What | Where | What's in it |
|---|---|---|
| Raw events | `source_events` | Gmail 3,381, Screen sessions 1,249 (22–28 Oct only), calendar 154 |
| Mail kept for reasoning | capture gate (L1) | 1,829 unique mails: 1,193 went on to reasoning, 636 were archived without text, 547 attachments were not read. Nothing older than 180 days is captured |
| **Evidence Graph** | `graph_nodes`, `graph_facts` | **16,792 facts, 2,352 relations**, timestamped. `authority_rank` holds two different scales in one column |
| Notes code writes per rule | graph facts | Promises: **87, all still open** (83 past their date). Questions: **208 of 212 open**. "Conflicts": **40 of 44** are about dates |
| Files | `context/workstreams.files_for` | **Computed on the fly, per counterparty, never stored** ("a file is one counterparty's correlations") |
| Situations | `context_situations` | **1,528**, formed by rules from a fixed list of types. **667** are support-desk "first response overdue" although Support is off for this org. They go dormant after a 45-day default |
| **Intelligence Graph** | admission of L2 results | **In shadow** ("SHADOW: nothing here touches the situations"). 30 interpretations were written and nothing reads them. **0 of the 16,792 facts came from the brain** |
| Goals | `company_goals` (migration 0254) | **7 proposed** (4 by the weekly drafter, 3 by the brain), **0 approved** |
| The approval door | `company_brief_lines` | 29 proposed lines, **0 accepted** |
| Goal links | `goal_situation_links` (0255) | **0 rows** |
| Goals on cards | `cards.goal_refs` (0256) | **0 of 111** cards |
| The founder's actions | `card_events` 211, `card_feedback_verdicts` 3, `moment_feedback` 133, `decisions` **0** | Stored. No reasoning step reads them back |
| Executions | `executions` 105, `execution_actions` 308, `execution_outcomes` 55, `situation_outcomes` 526 | Stored. Not joined to a business situation's page |
| Screen | `screen_thread_summaries` 141, `screen_thread_verdicts` 413, `screen_session_deltas` 3,167 | Stored. Not joined to situations |

## 2 · In the notebook: the Intelligence Graph, built locally

**Schema:** `notebook.*` (`nb/schema.sql`). Conclusions are keyed by **build** (one instant, one model); evidence is shared across builds. Rows are never deleted: a new start means a new build id.

### Evidence (Phase A, `nb/evidence.py` + `nb/recover.py`)

| Table | Rows | Notes |
|---|---|---|
| `notebook.mail` | 1,829 | Subject, full body, and the new text above quoted history. Direction, recipients, bounce (real delivery failures only: 7), calendar invite, attachment kinds. **635 of the 636 archived mails have their text recovered** from the stored encrypted payload (`text_source = 'recovered'`) |
| `notebook.meetings` | 142 | Each has `known_at`, the first time the copy recorded it. A build sees a future meeting only if it was known by its instant |
| `notebook.claim_candidates` | 89 | Amounts the capture pipeline read in our own sent mail |

### Conclusions (build `b2`, as of 23 Oct 01:40 UTC)

| Table | Rows | What it holds |
|---|---|---|
| `company` | 1 version | Who we are: names, founders, addresses, what we do, 15 pursuits, 15 numbers we told people (each found word for word in a cited mail), key relationships |
| `parties` | 667 | Who is who: each address and organisation, its kind (investor, accelerator, connector, candidate …) and one line on what it is **to us** |
| `works` | 423 | **The business situations.** Title, kind, status, stage, whose move and since when, next expected (what, from whom, by when, what if missed), importance, goal links, the latest verdict (summary, frame, evidence ids, unknowns), card, version |
| `work_versions` | 824 | Every saved page version, with the full admitted change |
| `members` | 2,540 | Which thread, mail or meeting belongs to which situation. 106 were moved out by the judge (`left_at`); a thread moved out of every situation gets one of its own |
| `loops` | 432 | Questions, asks and promises: who owes them, opening mail, due date, status (open 264, broken 51, moot 47, superseded 31, kept 24, answered 10, released 5), and the mail that settled them |
| `claims` | 114 | What **we** told people about ourselves: metric (MRR 33, pilots 17, design partners 16, ARR 10 …), the value as written, to whom, when |
| `links` | 138 | Between situations: part of, evidence for, contradicts, duplicate |
| `goals` | 15 | Statement, category, why, the situations that serve it (`work_ids`), evidence. **No target, plan, progress, status or next move** |
| `held` | 115 | Every change the code refused, **as the model proposed it**, with the reason |
| `cards` | 63 open | One per situation (P5) |
| `runs`, `state` | | Every model call and its cost; per-build state (instant, model, noise threads, unplaced meetings, notes on the whole picture) |

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
5. Every open card sits on a live situation and its quotes are real.
6. Goals and links point at things that exist.
7. Spend is under the cap.

**Size:** the whole `notebook` schema, across every build and test build, is 54 MB. One build's conclusions are a few MB.
