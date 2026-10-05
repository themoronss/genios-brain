# STEP-09 · TO BUILD · workstreams — a file for every piece of work in motion

**Owner:** Claude. **Depends on:** `STEP-05` (memory), `STEP-07` (the brief seeds the list); the
stage vocabularies come from `STEP-11` and start as *proposed* until you accept them. **Decision:**
`06` D2 (are these workstreams in scope). **Moves:** Boardy intros tracked per contact **3 of 7 →
7 of 7**; every investor, program, filing and hire in the brief has exactly one live file.

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
