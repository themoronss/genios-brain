# STEP-09 · PENDING — owner Rohit (push; the brief's connectors and watchlist; D35) and Harsh (deploy, no migration; re-file history if the health check names it) · workstreams — a file for every piece of work in motion

**Owner:** Claude. **Depends on:** `STEP-05` (memory), `STEP-07` (the brief seeds the list); the
stage vocabularies come from `STEP-11` and start as *proposed* until you accept them. **Decision:**
`06` D2 (are these workstreams in scope). **Moves:** Boardy intros tracked per contact **3 of 7 →
7 of 7**; every investor, program, filing and hire in the brief has exactly one live file.
**✅ Built and QA green 2026-10-07 — §9; what is left is the deploy and the brief (§9.6).**

---

## 1 · What is true now

| | Evidence |
|---|---|
| The nearest thing to a workstream already exists | `[CODE]` `context_correlations` keyed `(anchor, domain, generation)` — a counterparty × domain episode with per-event membership (`context/correlation.py:392-435`); `context_situations` unique on `(org_id, correlation_id)` (`context/situations.py:1164-1202`) |
| Domains come from regex hints | `[CODE]` `capture/domain/hints.py:23-60` — `fundraising` (which also swallows accelerator, incubator, cohort, programme and application status) is tested before `sales`; compliance and hiring fall under `admin` |
| The fundraising situations can never go live | `[CODE]` `reason/domain_shadow.py:512-526` maps `fundraising` and `general` to no live lane; `packs/compiler/capability_resolver.py:35-47` aliases `fundraising` to `sales` |
| Workstream-shaped facts exist and are live | `[CODE]` the state readings in `context/outreach_situations.py` (awaiting response, cohort, campaign, condition, stated dependency, analytic movement; nodes minted at `:1799-1802`); `context/waiting.py` (days waiting, follow-ups, their normal reply time); `context/meeting_lifecycle.py`; `reason/meetings/prep.py` |
| The reader already proposes the right words | `[CODE]` the live L1 business facts include `party.role`, `relationship.nature`, `thread.objective`, `campaign.objective` (`capture/semantic/extractor.py:783-794`; `contracts/extraction.py:437-438`); the legacy objective enum already has `fundraising`, `investor_update`, `hiring`, `partnership`, `intro_request`, `approval`… (`context/extract/prompt.py:52-62`) — but `thread.objective` falls back to free text (`context/pipeline.py:306`) |
| Intro roles exist, connector ≠ target is not enforced | `[CODE]` roles `introducer` / `introduced` (`context/pipeline.py:416-424`); relay detection (`capture/gate/rules.py:121-190`); `[ATLAS]` golden replay 02 is blocked on *"no counterparty role model"* and *"one anchor per situation"* (`context/situation_bso.py:69-166`) |
| Asks that never open a loop | `[CODE]` `contracts/open_loop.py:24` `ASK_KINDS` omits `intro_requested`, `information_requested`, `approval_requested`, `investor_update_sent` — which `observations/kinds.yaml` marks as asks; `awaited_from_node_id` is set only when there is exactly one external recipient (`context/pipeline.py:1621`) |
| The vocabulary has no word for this work | `[CODE]` `contracts/signal.py:210-299`; `[PROD]` investor pitches typed `contract_renewal`; 118 open-lane observations — investment thesis, program selection, rejection rationale, application timeline — 0 reviewed |

## 2 · Why

A chief of staff does not think in emails; she thinks in files. *"Where are we with Insight?"*,
*"what does Hub71 need from us?"*, *"which of Boardy's intros are still open?"* — each is one file
with a stage, an open ask, whose move it is, and a date.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | the workstream, on existing tables | `context_situations` + append-only `situation_interpretations` + `open_loops` | a workstream **is** a long-lived situation of type `workstream.<kind>`, kinds: `investor`, `program`, `intro`, `hire`, `partner`, `compliance`, `internal`. Its stage, open asks, roles, next step, owner and due date are typed fields on each new interpretation (never overwritten — the Atlas's *"represent them on the chain, do not grow a second graph"*, L3) |
| 3.2 | grouping, deterministic | new `context/workstreams.py` | thread → counterparty → organisation → correlation episode; meetings join by attendee and thread; screen items by person; the brief's *work in motion* seeds the list. **An intro is split per introduced contact**: Boardy is a `connector` edge, each contact is its own workstream (replay 02) |
| 3.3 | the reader proposes the meaning | `capture/semantic/extractor.py`; `contracts/extraction.py` | for each item the reader returns, with an evidence span: `workstream_kind`, `counterparty`, `stage_change` (from → to), `open_ask` (who asks whom for what), `due`, `roles` (requester, connector, target, owner). `thread.objective` gains `program_application` and `compliance_filing`, and stops falling back to free text |
| 3.4 | code verifies the proposal | new `context/workstream_verify.py` | the span must exist in the source; roles must agree with the headers (the connector is the `From`, the target is in `To`/`Cc`); target ≠ us (`STEP-04`); target ≠ connector. A proposal that fails stays a proposal and never moves a stage |
| 3.5 | stages | from `STEP-11`'s playbooks | e.g. **program:** *applied → acknowledged → under review → shortlisted → interview → decision → onboarding → active*; **intro:** *offered → accepted → introduced → they replied → call booked → met → follow-up*; **compliance:** *submitted → under review → clarification asked → answered → granted → benefits claimed*. Until you accept a vocabulary, its stages are stored and labelled *proposed* |
| 3.6 | asks open loops | `contracts/open_loop.py:24` | `ASK_KINDS` takes the four missing asks, so an intro request or an investor's information request opens a loop and can close as *answered* |
| 3.7 | the open lane becomes a source | weekly, `capture/semantic/open_lane.py` | recurring unclassified kinds (a DPIIT application, a program selection notice) are proposed as new stages or kinds for your review, instead of waiting for a manual `POST /admin/discovery/promote` |
| 3.8 | the read API | `api/workstream_routes.py` | `GET /workstreams` — per file: kind, counterparty, stage, open asks with who owes them, last touch, next date, evidence ids. The expert's dossier (`STEP-12`) reads the same |

## 4 · What will happen — your files, from the data already measured `[MODELLED]`

| File | Stage | Whose move | Evidence |
|---|---|---|---|
| Intro · Pankaj (saka.vc) via Boardy | introduced, no reply either side | yours | intro 3 Sep, nudges 4 and 7 Sep |
| Intro · Sal (Nexlayer) via Boardy | they replied | yours | 6 Aug |
| Intro · Lalitha via Boardy | met 13 Aug | yours — the follow-up | replies 12–13 Aug, call 13 Aug |
| Investor · Insight Partners (Neel) | call booked, 8 Oct | yours — prepare | mail 27 Sep, invite |
| Investor · 247VC (Khushi) | they wrote | yours | 18 Sep |
| Investor · Antler (Theresa) | deferred — *"send updates"* | conditional on a milestone | her 7 Aug mail; your four since |
| Program · Hub71 | ___ (read from the 1 Oct mail) | ___ | your 26 Aug reply; their 1 Oct mail |
| Program · NSRCEL | active cohort | yours — the assignment due | sessions; Deepthi's mails |
| Compliance · Startup India (DPIIT) | ___ (read from the 30 Sep mail) | ___ | five portal mails, 23–30 Sep |
| Hire · Khushi, Founding AI Engineer | offer sent | hers, and yours (ESOP approval) | 5 Aug |

## 5 · Expected

| Measure | Before | After |
|---|---|---|
| Boardy intros tracked per contact | 3 of 7 | **7 of 7** |
| Investors in the brief with a live file | — | **all** |
| One file per subject (no duplicates) | the offer to Khushi was 6 cards | **1** file |
| Golden replay 02 (Boardy) mutations passing | 0 of 10 | **≥ 8 of 10** |

## 6 · Verify

```
GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest tests/context/test_workstreams.py -q
#   three Boardy intros → three files, one connector edge, zero shared asks;
#   a reply from one contact closes only that contact's loop;
#   a proposal whose span is missing never moves a stage — each by mutation
.venv/bin/python -m pytest tests/replays -q          # replays 02, 03, 04, 06 move from xfail to pass
```

## 7 · Risks

| Risk | Guard |
|---|---|
| A wrong grouping merges two pieces of work | the split rule for intros; files are keyed on counterparty × kind, and a merge is a proposal you can undo |
| The reader's stage guess moves a file wrongly | stage moves need a verified span; an unaccepted vocabulary stays labelled *proposed* |

---

## 8 · The check of 2026-10-07 — what the 5 Oct plan got right, and wrong

Every claim above was re-read against `speedrun008` @ `c1cab2fc` (STEP-02 to STEP-07 built; STEP-08's
code, built beside this check, touches none of the modules cited) — by a read-only worker, and the
claims that decide the design again by hand. The plan was **measured on the golden set**: the 32 cases
this step is about, each replayed from its cassette through the real chain, its rows read before the
tenant was removed — 0 cassette misses, every verdict as `03` §F.1 records it, no spend
(`baseline/yc2w27-s09-check/`: `measure_workstreams.py`, `table.md`). Production was not read.

### 8.1 · Measured — the golden set (intros F03–F08, F37; investors F10–F15, F42, F44; programs F17–F24, F31; compliance F01, F02; hire F25; partners F26–F29)

| | Result |
|---|---|
| introductions tracked per introduced contact (8 contacts in F03–F08, F37) | **0 of 8 split by design.** 5 are in memory as a person — exactly the ones who replied; 3 have a correlation of their own, 2 by the order the drain happened to read the mails (F04, F37) and 1 from a calendar invite (F07); 2 own files hold the introduction itself. Rahul (F03), Simon and Omar (F08) — introduced, never replied — **are not in memory at all** |
| why the contact is missing | Introly's mail carries `List-Unsubscribe`, so `addressed_to_a_list` drops **every** To/Cc recipient (`context/pipeline.py:1243-1244`), and a person named in the text needs an address to become a node (`:1373`) |
| why the connector anchors the intro | the extraction's role `connector` is free text the graph never reads (`03` F80), and `choose_anchors` falls back to the connector when it is the only party at its tier (`context/correlation.py:249-252`); the contact's reply then joins the connector's file by thread (`:322-325`) — F05, F06, F07 |
| portals and programs that write from `updates@` / `no-reply@` / `support@` | become `service` nodes and **never correlate** (`context/pipeline.py:153-161, 1012-1014, 2131`): F01, F02, F23 have **no file at all**, though STEP-07 made their mail kept and read |
| which domain the work lands in | by the words of the mail, not the kind of work: investors in Admin (F12, F13, F42 — carded) or in `fundraising` (F10, F11, F14, F15, F44 — dark: no live lane, `reason/domain_shadow.py:525`); accelerators in `fundraising` (F17, F20, F24, F31), the incubator in Admin (F19); one partner split across Sales and Admin (F29). **15 situations in 11 of these cases sit in `fundraising`** and end `no_corpus` |
| what makes the cards today | 23 cards in these 32 cases: **15 from the legacy `unanswered_email` rule** (no situation behind them) — every passing intro card (F04, F05, F06, F37) among them — 4 `account_admin`, 3 `meeting_follow_through`, 1 `dependency_stated` |
| open loops | 28, all `question`, none closed; `awaited_from` set only on F15's five outbound asks |
| golden replay 02 (Boardy) | all 10 mutations `blocked_missing_capability`; only m04 is driven (on F09), a strict xfail; the other nine have no founder case to drive them. Across every driven Atlas mutation: 4 pass (03 m00, 03 m01, 04 m01, 06 m04), 3 xfail (01 m01, 02 m04, 03 m05) |

### 8.2 · The claims

| Claim (5 Oct) | Verdict (7 Oct) |
|---|---|
| correlations keyed `(anchor, domain, generation)`, situations unique on `(org, correlation)` | ✅ `migrations/0037_l2_correlation.sql:32`, `0038_l2_situations.sql:51`. ⚠️ Not in the plan: the **thread-first** join (`context/correlation.py:322-325`) and the **45-day** window (`:70`) with 45-day dormancy (`context/situations.py:87`) — F15's five fund situations are already `dormant` |
| domains from regex hints; `fundraising` swallows programs; compliance and hiring in Admin | ✅ `capture/domain/hints.py:22-67`, ranked `:134`; F01's portal "application" is hinted `fundraising` first |
| fundraising can never go live | ✅ `reason/domain_shadow.py:513-527`. ⚠️ The doctrine exists, in the Sales corpus: a `CANDIDATE_ROUTES` entry is declared and unarmed (`:482-497`) — one line from live, by decision, not by authoring |
| workstream-shaped facts exist and are live | ⚠️ partly. The outreach readings (`context/outreach_situations.py:1444-1482`) are Admin's and mostly **held** at admission on the golden set (awaiting_response ×6, condition_in_review ×3, analytic_movement ×10); `waiting.py` is live; `reason/meetings/prep.py` is a desktop moment, not the mail chain |
| the reader already proposes the right words; `thread.objective` falls back to free text | ⚠️ the fields exist (`contracts/extraction.py:436-439`), but the legacy objective list (`context/extract/prompt.py:52-62`) is **never sent in production** — L2 runs with no model (`context/runner.py:194-211`), so `objective` is always `{}` (`qes_adapter.py:187`) and `objective_of` always returns the free-text fact |
| intro roles exist; connector ≠ target is not enforced | ✅ `_COUNTERPARTY_ROLES` (`context/pipeline.py:417-425`); 0 `party.role` facts in F03–F09, F37. Relay detection (`capture/gate/rules.py:119-184`) is about a relayed REPLY, not an introduction |
| `ASK_KINDS` omits four asks `kinds.yaml` marks | ✅ but the two lists mean different things: `is_ask` is "we asked them" (`kinds.yaml:15-18`), `ASK_KINDS` "a counterparty waits on us" (`contracts/open_loop.py:21-23`). On the live path only `approval_requested` can occur, and adding it opens a WRONG loop on F25 (passing today: the approval awaited is the board's, not the candidate's) |
| §3.1: a workstream is a long-lived situation of type `workstream.<kind>`, its fields on append-only interpretations | ❌ **as written.** A correlation situation's type is re-derived every refresh from (anchor type, domain) (`context/situations.py:1126, 1195`); a dotted type breaks the corpus schema (`Domain Expertise/_schema/situation.schema.json`, `^[a-z0-9_]+$`); the producible types are pinned (`tests/test_l3_route_vocabulary_contract.py:52`). `situation_interpretations` keeps one row per (situation, slice digest), has one writer and no reader, and refuses any field the situation contract does not let a model write (`context/proposal_gate.py:144-147`) — `stage`, `open_asks`, `owner`, `due` would be refused |
| §3.3: the reader proposes `workstream_kind`, `counterparty`, `stage_change`, `open_ask`, `due`, `roles` | ⚠️ mostly there already — `questions` (asked_by / asked_of, with a span), `roles`, `commitments.due`, `decision_states`; new are only `workstream_kind` and `stage_change`. ⛔ **Cost:** two schema versions bumped by hand (`extractor.py:188`, `structured/mapper.py:143`), every extraction re-read, and **69 extraction answers in 38 of 44 cassettes** re-recorded — and if it lands after STEP-08 runs in production, the mailbox is re-read twice |
| §3.4: a new `workstream_verify.py` | ⚠️ `context/proposal_gate.py` already is the deterministic validator (span grading, schema, the contract) — a second one would be a second answer. STEP-13 §3.3 plans the same check |
| §3.5: stages from STEP-11 | ❌ not buildable now — STEP-11 is unbuilt, D2 and D3 unanswered |
| §3.7: the open lane becomes a weekly source | ⚠️ built as an on-demand, staff-only tool, and its own tests refuse what §3.7 asks: nothing under `reason/` or `packs/` may import it, and it is not periodic (`tests/capture/semantic/test_open_lane.py:479, 503`) |
| §3.8: `GET /workstreams` | ✅ nothing collides — "workstream" appears nowhere in `genios_engine/` |
| §5: replays 02, 03, 04, 06 move from xfail to pass | ⚠️ stale: three of the four already pass; replay 02's "≥ 8 of 10" needs at least seven founder cases that do not exist, plus STEP-12/14 |
| §5: Boardy intros 3 of 7 → 7 of 7 | ✅ the right measure — on the golden set it is **0 of 8 by design** (§8.1) |

### 8.3 · What changes in the design

1. **A file is a correlation the company brief can name — not a new situation type.** No
   `workstream.<kind>` types, no fields on interpretations, no second graph. The work in motion already
   groups by thread → person → company (`context/correlation.py`); what is missing is that the brief's
   connectors, portals and programs take part in it.
2. **An introduction is split per contact by the brief's connectors.** A sender the brief names as a
   connector is an `introducer` on its own mail (never the anchor — F80), and its To/Cc recipients
   become people, `introduced`, even under an unsubscribe header (only a connector's mail; a real
   mailing list stays skipped). The intro then anchors on each contact, and the contact's reply joins
   the contact's file by thread.
3. **A watchlist domain is a file.** Mail from a service address at a domain the brief watches
   correlates under that organisation — one file per program or portal, instead of none.
4. **The kind comes from the brief**, never guessed from the words: a connector's file is an *intro*,
   a watchlist domain's a *program* or *compliance* file, a counterparty an in-motion line names takes
   that line's kind (D31). A file with no brief line behind it is listed with no kind.
5. **The list is a read model, then an API** — `context/workstreams.py` (deterministic, no model, no
   table) and `GET /v1/workstreams`: per file the kind, the counterparty, the evidence, the last touch,
   the open asks and whose move it is. A health check says which named counterparty has mail and no file.
6. **Not now:** stages (STEP-11's vocabularies); a new extraction field (D32 — and if ever, before
   STEP-08 runs); `ASK_KINDS` (it would open wrong loops); a weekly open lane (its own rules forbid it);
   live cards for files in a dark domain — that is D2.
7. **The connector is never owed a reply** (`03` F81): the legacy `unanswered_email` rule skips a
   sender the brief names as a connector — it raises Introly in six cases today; the decider defers it.

### 8.4 · What will be built — tree block `yc2_w27_s09` (milestone M27), proposed

| Category | Units | What |
|---|---|---|
| C1 · the intro, per contact | 3 | `context/pipeline` — the brief's connector is `introducer`; its recipients become `introduced` people; `context/correlation` — the intro anchors on each contact, a contact's reply stays in the contact's file |
| C2 · a portal or program is a file | 1 | `context/pipeline` — a service sender at a watchlist domain correlates under that domain's organisation |
| C3 · the connector is never owed a reply | 1 | the legacy `unanswered_email` rule skips the brief's connectors (F81) |
| C4 · the files, readable | 3 | `context/workstreams.files_for`; `GET /v1/workstreams`; `pipeline_health` — *every counterparty the brief names that has mail has a file* |
| C5 · the golden set | 2 | the cassettes whose prompts move, re-recorded deliberately; the acceptance — 8 of 8 contacts in their own file with their introduction, F01/F02/F23 one file each, the board measured, every must-abstain held |

10 units, critical path 6 (`C1.U01` → `C1.U03` → `C4.U01` → `C4.U02` → the re-record → the
acceptance). **M28 — files go live** is drawn only when D2 is answered:
under A a Founder Office domain (with STEP-11's corpus), under B the founder's files routed into
Admin's account situations, under C nothing more.

### 8.5 · Decisions

| | Question | Recommended | Default |
|---|---|---|---|
| D2 | Are the founder's workstreams in scope beyond Admin? | **A, in two moves** — M27 now (it is domain-free: files exist, are listed and readable, in every domain); the Founder Office domain with STEP-11's playbooks for the cards. B (fold into Admin) only if you want cards on investor and program files before STEP-11 — measured on the golden set before it ships | C — M27 still builds; the files in `fundraising` stay listed, not carded |
| D30 | May a connector's introduction create the people it introduces? | **Yes, the brief's connectors only** — the contact is addressed in a mail to you, as any To/Cc recipient is; without it no introduction can be split | no — then intros stay merged under the connector |
| D31 | Does each in-motion line name its counterparty (a domain or an address) and its kind? | **Yes** — "every investor in the brief has a file" becomes measurable; the drafter proposes it, you accept it | no — kinds only for connectors and the watchlist |
| D32 | A new extraction field (`workstream_kind`, `stage_change`) now? | **Not now** — the brief gives the kind; if ever, before STEP-08 runs in production, or the mailbox is read twice | not now |
| D33 | How long a file may stay quiet before it is dormant? | **Per kind, as data, labelled proposed** — 90 days for investor, program and compliance, 45 for intro and partner — until STEP-11 authors them | 45 days for every file, as today |
| D34 | The legacy `unanswered_email` cards once files exist? | **Keep them until STEP-14** — they make 15 of today's 23 golden cards, every passing intro among them; measure the duplicates first | keep |

### 8.6 · Risks

| Risk | Guard |
|---|---|
| minting introduced contacts puts people in the org-wide graph | only the brief's connectors (D30); a mailing list stays skipped; no screen item creates a person (D22) |
| splitting an intro changes what the reasoning reads — must-abstain F37 ("the connector is never the person to reply to") | the acceptance holds every must-abstain case; F81's fix keeps the connector out of the reply rule |
| every intro, portal and program case's prompts move | re-recorded deliberately from the ideal reader (as STEP-07 did), each diff read before it is kept |
| a brief with no accepted line changes nothing — so nothing moves in production until Rohit accepts it | by design (D26 already orders STEP-08 after the brief); the health check names what has no file |

---

## 9 · Built — 2026-10-07 (`yc2_w27_s09`, 13 units green: 10 drawn + 3 found)

Rohit's go, 2026-10-07: *"to ab step 9 pe chalte hain, complete karte hain perfectly … lekin
perfection aur quality ke saath"*. Built bottom-up, each unit test-first, each test run against its own
mutations, the repo-wide guards before every commit; crosschecked, and the three findings it raised
fixed before QA. Nothing ran on production. Commits `2c1cfbeb` (C1–C3), `2dedfdd9`, `5a28449d` (C4),
`cebe28af`, `57a664f6` (C5), `567049fc` (the crosscheck's fixes).

### 9.1 · What was built

| | Where | What it does |
|---|---|---|
| who a connector introduced, by names (found) | `context/introductions.py` | `assign_names`: whose is each name an introduction used — a person's against the address's local part, an organisation's against its domain, the one leftover name for the one person introduced; a name that fits two people is nobody's, ours and the connector's are never a contact's; a personal mailbox names no organisation. `introductions_by`: who a connector introduced (the `introduced` edges), with their company and names. `named_in`: which of them a later mail names. `connector_roles`: every node the brief names a connector, as `introducer` — the one answer the drain and a rebuild read. Never a model |
| the connector is an introducer | `context/pipeline.process_event`, `context/runner`, `scripts/rebuild_graph.py` | the drain reads the brief once per pass, beside who is us, and hands it down every road. A connector the brief names is an introducer wherever it appears — on the mail, or only named in its prose — with a `party.role` fact on the brief's word; alone at its tier (its own ask) it still anchors. Its declared auto-reply is no file |
| the people it introduces | the same | its To/Cc recipients — ours and fellow connectors excepted — are people even under its unsubscribe header (D30): `party.role introduced` (by, thread, names), an `introduced` edge, named from the introduction. A real mailing list from anyone else still establishes nobody |
| one file per person | `context/correlation._the_parties_files` | an introduction anchors on each person it introduces; in a thread holding several files, a reply joins only the files of the parties in it — every one when it names none |
| a nudge joins their file (found) | `context/pipeline` | a connector's mail to us alone that names someone it introduced joins each named person's file, recorded on them (`connector_nudge`); naming nobody, it is the connector's own ask (golden F09); the next nudge in a thread already theirs follows it. Only mail read as correspondence — its newsletter never is (crosscheck X1) |
| a rebuild files as the drain did (found) | `context/backfill.backfill_correlations` | passes the brief's connector roles; and neither it nor the replay after every backfill drain files what the drain called noise (`03` F101 — it did, since L3-0A) |
| a watched portal is a file | `context/pipeline` | mail from a domain the brief watches, or a subdomain, is filed under that domain's organisation — the counterparty of every notice it sends, even beside another company the graph knows; `Auto-Submitted: auto-generated` is how a portal sends a notice, and is a file; its mailing (a list header, a bulk precedence) and an auto-reply are not, and are recorded as what they are |
| never a reply owed to the connector | `context/pipeline` (the turn) | an introduction's `thread.last_inbound` / `ball_in_court` are written on each person it introduces; a nudge writes none; the connector's own ask keeps its turn; a portal's machine address is never owed one; the thread is named after its one person introduced |
| the files, readable | `context/workstreams.files_for`, `api/workstream_routes.py` (`GET /v1/workstreams`) | one file per anchor (every domain, every generation): the brief's kind (`connector`, `watched`, `person`, `intro`, or none), the line behind it, who introduced it, its mail oldest first, first and last touch, days quiet, whose move (*ours* while anyone in it waits on us), its open asks and who owes them; every named counterparty with its mail, how much is filed, and its introductions filed under the connector (`misfiled`). An org-level reader: nothing a seat captured privately |
| the health check | `scripts/pipeline_health.check_every_named_counterparty_has_a_file` | reads the same answer; fails while a named counterparty's read mail is filed nowhere, or a connector's introductions sit in its own file — names each, and the cure (§9.6) |
| the acceptance | `tests/replays/test_every_piece_of_work_has_a_file.py` | §8.1's promises on the golden cases, through the real chain with the cassettes |

### 9.2 · Measured — the golden set

| | Before STEP-09 | After |
|---|---|---|
| people the connector introduced with a file of their own holding their introduction (F03–F08, F37) | **0 of 8**, by design (§8.1) | **8 of 8**, kind `intro`, introduced by Introly; F03's two nudges in Rahul's |
| the connector | anchored F03's introduction; *"unanswered email — Introly"* on six cases | anchors no introduction; owed no reply in any intro case; its own ask (F09) is its own file |
| portals and programs that wrote (F01, F02, F23) | no file at all | **one `watched` file each**, holding every notice |
| the board (`03` §F.1) | must-detect 11/32 · must-abstain 11/12 · forbidden 4 · Atlas 4/80 | must-detect **12/32** (F03 passes: one card, *"Take Rahul Menon's introduction forward"*) · 11/12 · 4 · 4/80 |
| the health check on every replayed case | — | 0 unfiled, 0 misfiled |

Nine cassettes missed and were re-recorded from the ideal reader (no spend); the other 35 replay
exactly. Each diff was read (`baseline/yc2w27-s09-build/cassette_diff.txt`): every answer removed is the
connector's reply situation or an R-1 reading merged with it; every answer added is a person
introduced, a portal's file, or the resolution site reading a notice. Four cases reached new
questions, answered from the prompt as written (F02, F03, F07, F08); six authored answers nobody asks
any more are retired. The acceptance kills a drain with no brief, a pipeline with no connector roles
and one that drops the connector's recipients. Mutations, each unit against its own test: 20/20
(names), 6/6 + 6/6 + 1/1 (the introducer, the runner, the rebuild script), 11/11 (the people), 4/5
(the thread's files — the survivor an equivalent short-circuit), 5/5 (the nudge), 6/6 (the rebuild),
11/11 + 11/11 (the portal), 11/12 (the turn — an equivalent short-circuit), 38/38 (the read model),
3/3 (the route), 7/7 (the health check).

### 9.3 · Decided while building

- **The connector's own ask is its own file; a nudge joins the person it names.** Drawn as "the
  connector never anchors"; golden F09 expects a card about Introly's own question, F03 forbids
  *"Reply to Introly"* — so a mail that names no one it introduced anchors on it (minted U04).
- **The reply rule moved into the pipeline's turn** (C3 redrawn): a skip in `reason/runner` would also
  have silenced the connector's own ask.
- **A watched portal is the counterparty, and a notice marked auto-generated is a file**: a portal's
  machine address carried its "machine" role to the portal, which lost its file the moment a notice
  named another company; and `addressed_to_a_list` reads any `Auto-Submitted` as a list.
- **Whose move is *ours* while anyone in the file waits on us** — answering one partner at a fund
  does not answer the other.
- **History filed the old way is named, not hidden**: `misfiled` counts a connector's introductions in
  its own file, so the health check fails until history is re-filed.

### 9.4 · Found while building

- **`03` F101 — the history replay filed what the drain called noise** (fixed, X2). Live before STEP-09,
  on every backfill drain since L3-0A; a read-only count says how much production holds (`08` §3.8).
- **`03` F96 — the founder's own company gets a file** when a watched notice names it and the company's
  domain is undeclared (F02's *"Recognition granted"*). A decision: **D35**.
- **`03` F97** — `company_brief.current(conn)` does not read through a connection (latent).
- **`03` F98** — a rebuild loses a company a mail named in prose (pre-existing).
- **`03` F99** — a watched portal's file reaches the decider with none of its notices' words: F02's
  7-day ask is deferred (`STEP-12`).
- **`03` F100** — the statement counter takes prose beginning with *"with"* for SQL.
- **Declared, fragile:** `GET /v1/workstreams` is unpaginated; a file whose anchor was merged away
  drops out of the list until the next correlation rebuild; a nudge matched by first name reaches
  every introduced person of that name.

### 9.5 · QA

Green on every tier, the first run, at `567049fc` (`baseline/yc2w27-s09-qa/qa_record.txt`; every
database check on a database created for it):

| Tier | Result |
|---|---|
| the tree and the 13 units' own verifies | 17 pass / 0 fail / 0 skip |
| the whole suite on Postgres | 18,528 passed, 4 skipped (the known four, re-listed with their reasons), 88 xfailed |
| the golden lane, `GENIOS_GOLDEN_REQUIRED=1` | 731 passed, 86 xfailed, **0 skipped** |
| the board against `03` §F.1 | matches — must-detect **12/32**, must-abstain 11/12, forbidden 4, Atlas 4/80 |
| the hermetic job | 16,561 passed, 1,612 skipped (1,608 need a database; tier 2 ran them), 72 xfailed |

### 9.6 · After the deploy — Rohit, then Harsh

1. **Nothing moves until the brief names a connector or a watched domain** — and the drain files only
   NEW mail the new way.
2. Deploy before STEP-08's re-sync: it carries F101's fix (`08` §3.7).
3. After Rohit accepts: the health check (`08` §4.7). If it names anything — mail read before the brief
   — re-file: `scripts/rebuild_graph.py --apply`, then `POST …/situations/backfill?rebuild=true`, then
   the check again (`08` §3.8).
4. Decisions waiting (`06`): **D2** (files beyond Admin reach cards — M28), **D31** (an in-motion line
   names its counterparty — gives a file its kind), **D33** (dormancy per kind), **D34** (the legacy
   cards), **D35** (declare the company's domain — F96).
