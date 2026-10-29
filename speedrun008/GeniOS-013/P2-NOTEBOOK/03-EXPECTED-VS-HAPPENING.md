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

## What the notebook proved

Items 1, 2, 3, 4, 6, 10 and 12 work locally. These are missing:
- the goal object (5);
- the founder's actions, answers and other tools as evidence (7, 9);
- lifecycle (8);
- facts travelling between situations (11);
- visibility for teams (16).

These are the steps in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md).

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
