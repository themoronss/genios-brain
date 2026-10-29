# P2 · Notebook · 03 · What's expected, and what's happening

**Expected**, from Rohit's own words:
- **the film:**
  - "the current status of your company, how your company is evolving, which right now is only in your head";
  - the tools fanning into "facts, not raw data";
  - "every Done teaches";
  - "your data stays with you only";
- **Rohit's 29 Oct loops:** the Notebook updates with new data. Correlate, analyse and lifecycle (improve, decay, ignore, prioritise) run over it;
- **the architecture (Atlas v2):** "L3 only remembers what L2 concluded".

**Happening** is measured ([01](01-WHATS-EXACTLY-THERE.md)): the product on the design partner's first week, and the notebook on build `b2`.

| # | Expected | Product today | Notebook today |
|---|---|---|---|
| 1 | **Facts, not raw data:** the company's state, kept | A rich archive (16,792 facts), none of them a conclusion | ✅ One page per business situation, versioned (824 versions over 423 situations) |
| 2 | **The unit is the business situation:** one application, one conversation, one introduction | Files by counterparty, computed and thrown away; 1,528 situations made by rules | ✅ Mostly right: each introduction is its own situation, and all 17 in-copy ideal items were found |
| 3 | **About this company, not a template** | 63% of the active situations are a support desk the company doesn't have | ✅ Situations come from the company's own mail |
| 4 | **Where each thing stands now** | Notes contradict and never close (87 of 87 promises open) | ✅ Questions and promises settle only with the right side's later mail. 264 open, 168 settled or ended, each with its evidence |
| 5 | **Goals are where the work is organised** | 7 proposed, 0 approved, 0 linked | ❌ 15 goals, each only a sentence. Two link sets disagree. 21 live situations have no goal |
| 6 | **Evolves with new data**, reading it through what is already known | Re-reads whole files | ✅ Re-reads from the saved page plus only the new mail. The way forward in time (`update.py`) is stale |
| 7 | **Every Done teaches** | Actions, executions and outcomes are stored, never read back. 40 questions asked, 0 answered | ❌ Not represented |
| 8 | **Lifecycle:** improve, decay, ignore, prioritise | A 45-day dormancy that puts quiet work to sleep; card expiry | ❌ Nothing decays. 63 cards, many from stale dates |
| 9 | **Every tool** (the film shows mail, calendar, chat, docs, tasks, drive) | Mail, calendar and Screen captured | ❌ Mail and calendar only |
| 10 | **Nothing invented** | The checker held whole results over one line (66 of 86) | ✅ Checked change by change; a refused change is held with its reason (115 in `b2`) |
| 11 | **Every fact travels** to the situations and goals it matters to | Not applicable (no conclusions) | ❌ The incubator's milestone never reached the accelerator (`i1`) |
| 12 | **As of any day:** an honest replay | Fingerprints and the change gate | ✅ Every build is one instant. A future meeting is visible only if it was known by then |
| 13 | **It remembers**: a long fundraise or a revived conversation still has its history | Clean text is deleted 180 days after capture, whatever the work | Not applicable (it reads the copy) |
| 14 | **Your data stays with you** | A per-tenant cloud database; archived words kept away from models by choice | A local copy on the founder's machine; archived text recovered locally |
| 15 | **More customers fit** | One tenant is over the database's ceiling (570 MB of 472) | A few MB of conclusions per build |
| 16 | **A team's private mail stays private** | Every mail carries its visibility | ❌ Ignored: every mail is treated as the founder's |
| 17 | **Four brains, kept apart** (the ideal's Brain page): Organization changed only by the founder, Behavior counted from mail, Adaptive always expiring, Persona confirmed by the person | Tables exist (`learned_brain_entries`, `learning_objects`), 0 entries | ❌ The company page only; no counted patterns, leases or preferences |
| 18 | **Four kinds of "nothing found"** (verified absence, partial coverage, unknown, conflicted), never "didn't happen" | `situation_absences` holds absence types with a coverage licence | ❌ Free-text unknowns; no coverage per situation |
| 19 | **Coverage you can see**, per source and per thread | Per domain (`source_coverage`) | ❌ Not stored |
| 20 | **A conflict is yours to decide**: sides kept, GeniOS never picks; your answer becomes the company's figure | `discrepancies` exists | 🟡 One "one number" situation, made once, never grown on later runs |
| 21 | **The Atlas lifecycle** (awaiting evidence, decision-ready, verifying, resolved only on outcome evidence, reopened) | A 45-day default and a few states | ❌ Five words, none of them Atlas's |
| 22 | **Every fact with its three times**: when it happened, when GeniOS learned it, when it stopped being true | The columns exist; derived writers stamp "now" every sweep | 🟡 One instant per build |
| 23 | **What must be decided, by whom, by when** (the DecisionObject) | Does not exist | ❌ Not represented |
| 24 | **Every number and date counted by code**, with its inputs | Partly, in tools | 🟡 The model can still write a count in a summary |
| 25 | **Every card traceable** to its page version, evidence and raw event, under one trace id | Receipts per pass | 🟡 Cards overwrite; no trace id |
| 26 | **Who is who, across tools and over time**: roles, affiliations, doubt kept, merges reversible, relationship going cold | Aliases, merges, an unwired doubt resolver | 🟡 Kind and one line per party |

## What the notebook proved

Items 1, 2, 3, 4, 6, 10 and 12 work locally. These are missing:
- the goal object (5);
- the founder's actions, answers and other tools as evidence (7, 9);
- lifecycle (8, 21);
- facts travelling between situations (11);
- visibility for teams (16);
- the brains (17);
- absence and coverage (18, 19);
- conflicts decided by the founder (20);
- the three times on every fact (22);
- the DecisionObject (23);
- numbers counted by code (24);
- traceable cards (25);
- identity over time (26).

These are the steps in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md), specified in [07](07-THE-NOTEBOOK-SPEC.md).

## What "done" means for P2

| Measure | Today | Target |
|---|---|---|
| In-copy ideal items whose situation is found (members, kind, status) | 17 of 17 found (`b2`); fields not scored | 17 of 17, with status and whose move right on at least 15 |
| Goals with target, plan, progress (or "unknown, why"), status and next move | 0 of 15 | every goal |
| Live situations linked to a goal, or listed as "not linked" | two link sets disagreeing on 53 | one link set; every live situation in one list or the other |
| Disagreements between link sets | 53 | 0 |
| Cards standing on a dormant, done or history situation | not checked | 0 |
| The incubator's milestone in the accelerator's dossier (`i1`) | missing | present, dated, with its source |
| A founder action or an execution outcome cited in a judgment | never | yes |
| Database invariants | 7 of 7 | all, including the new goal, link and lifecycle ones |
| Conclusions per tenant | a few MB | under 50 MB for a founder after a year |
| A team member's private mail on a page another person sees | not checked | never (a test) |
| The 309 requirements of the four references (trace in [08](08-REQUIREMENTS-TRACE.md)) | 14 covered by the old plan | every one built and tested, or explicitly owned by another part |
| Invariants of 07 §15 | 7 exist | all 21, after every build, Evolve day and replay day |
| Admission laws of 07 §11.2 | the notebook's six checks | all 25, each with a positive and a negative fixture |
| A day with nothing new | not measured | 0 model calls; a handful of indexed reads |
| Snapshot read, p95 | not measured | under 2 s |
