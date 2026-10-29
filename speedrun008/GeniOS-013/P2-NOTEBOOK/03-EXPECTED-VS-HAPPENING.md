# P2 · Notebook · 03 · What's expected, and what's happening

**Expected**, from Rohit's own words:
- **the film:**
  - "the current status of your company, how your company is evolving, which right now is only in your head";
  - the tools fanning into "facts, not raw data";
  - "every Done teaches";
  - "your data stays with you only";
- **Rohit's 29 Oct loops:** the Notebook updates with new data. Correlate, analyse, and lifecycle (improve, decay, ignore, prioritise) run over it;
- **the architecture (Atlas v2):** "L3 only remembers what L2 concluded".

| # | Expected | Product today | Notebook today |
|---|---|---|---|
| 1 | **Facts, not raw data:** the company's state, kept | A rich archive (16,792 facts), but no conclusions | ✅ One page per business situation, versioned (824 versions over 423 situations) |
| 2 | **The unit is the business situation:** one application, one conversation, one introduction | Files by sender, computed and thrown away; situations made by rules | ✅ Mostly right: each introduction is its own situation; the intro platform's own housekeeping is one |
| 3 | **Where each thing stands now** | Notes contradict and never close (87 of 87 promises open) | ✅ Questions and promises settle only with the right side's later mail. 264 open, 168 settled or ended, each with its evidence |
| 4 | **Goals are where the work is organised** | 7 proposed, 0 approved, 0 linked | ❌ 15 goals, each only a sentence. Two link sets disagree. 21 live situations have no goal |
| 5 | **Evolves with new data**, reading it through what is already known | Re-reads whole files | ✅ Re-reads from the saved page plus only the new mail. The way forward in time (`update.py`) is stale |
| 6 | **Every Done teaches** | Actions, executions and outcomes stored, never read back | ❌ Not represented |
| 7 | **Lifecycle:** improve, decay, ignore, prioritise | A 45-day dormancy that puts quiet work to sleep; card expiry | ❌ Nothing decays. 63 cards, many from stale dates |
| 8 | **Every tool** (the film shows mail, calendar, chat, docs, tasks, drive) | Mail, calendar, Screen captured | ❌ Mail and calendar only |
| 9 | **Nothing invented** | The checker holds the whole result over one line (66 of 86 held) | ✅ Checked change by change; a refused change is held with its reason (115 in `b2`) |
| 10 | **Every fact travels** to the situations and goals it matters to | Not applicable (no conclusions) | ❌ The incubator's milestone never reached the accelerator (`i1`) |
| 11 | **As of any day:** an honest replay | Fingerprints and change gate | ✅ Every build is one instant. A future meeting is visible only if it was known by then |
| 12 | **Your data stays with you** | A per-tenant cloud database; archived words kept away from models by choice | Local copy on the founder's machine; archived text recovered locally |

## What the notebook proved

Items 1, 2, 3, 5, 9 and 11 work locally. Four things are missing:
- the goal object (4);
- the founder's actions and other tools as evidence (6, 8);
- lifecycle (7);
- facts travelling between situations (10).

These are the steps in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md).
