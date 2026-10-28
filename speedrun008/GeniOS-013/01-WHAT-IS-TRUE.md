# 01 · What is true today, measured

**Written for:** Harsh and the coding agents.
**Source:** a local copy of the design partner's org, cut from production at 2026-10-28 12:45 UTC in one read-only `REPEATABLE READ` transaction. It holds all 204 public tables, but only this org's rows. Code is at `harsh/mvp` `7d2c3615`.
**Rule of this file:** every number comes with the query that produced it, so it can be re-run on production read-only. `:org` stands for the org id. No names appear.

---

## §0 · How to reproduce

- **On a local copy.** The copy is a Postgres 17 container with the production schema (migration head 0256) and the org's rows. Point `GENIOS_TARGET_DATABASE_URL` at it.
- **On production.** Wrap each query in `begin transaction read only; … rollback;`.
- **Running the engine on a copy.** The engine itself can run against the copy (`GENIOS_DATABASE_URL` → the copy). Harsh's 23 Oct "local run with production's models" is the method. The model and Gmail APIs stay live, so cards are written to the copy and nothing is sent.

## §1 · The baseline score

```
GENIOS_TARGET_DATABASE_URL=<copy> .venv/bin/python scripts/ideal_card_gap.py \
  --from-dashboard <private path>/02-data.js --org <org> --self <founder address>
→ cards found 8/20 · fields filled 28/220 · product cards 65
```

- `found` matches on the **counterparty**. So a "We held…" card counts as found.
- The stricter trace (the stage at which each ideal item was lost, judged by the right recommendation) gives **0 the same, 9 partial or wrong, 11 missing**.
- Harsh's local run on 23 Oct reached 9/20 and 37/220.

## §2 · The facts in one table

| # | Fact | Number | § |
|---|---|---|---|
| 1 | Mails in the window: emitted / archived | 1,829: 1,193 / 636 | §3 |
| 2 | Attachments not read (their mails were read) | 547 | §3 |
| 3 | Graph facts: from sources / computed by code / **from L2** | 6,148 / 10,644 / **0** | §4 |
| 4 | Relations, by type | 2,352, in 6 people-to-people types only | §4 |
| 5 | Question loops still open | 208 of 212 | §4 |
| 6 | Promises still open | 87 of 87 (83 past due) | §4 |
| 7 | L2 runs triggered by new mail | 138 of 138 | §6 |
| 8 | L2 results held by the claim check | 66 of 86 | §6 |
| 9 | Dossiers saying "No company brief is accepted" | 138 of 138 | §6 |
| 10 | Re-judgments with no new mail in between | 16 of 20 | §6 |
| 11 | L2 conclusions that changed a situation | 0 (admission is shadow) | §7 |
| 12 | Live cards from the old rule lanes | 71 of 103 | §8 |
| 13 | Live goals / cards with a goal | 0 / 0 of 103 | §9 |
| 14 | Old-flow model input since 21 Oct, against R-9's | 10.75M against 2.33M tokens | §10 |

## §3 · Layer 1 input (corrected)

| What | Count |
|---|---|
| Unique mails (`email_message`), 25 Apr → 28 Oct | 1,829 |
| — emitted to the chain | 1,193 (65%) |
| — archived by the gate | 636 (35%): Promotions tab 241, bulk/unsubscribe 200, no-reply sender 167, bulk precedence 24, other 4 |
| Attachment stubs parked (`email_attachment`) | 547: unsupported 421 (417 of them calendar invites), download failed 125 (66 image, 58 PDF, 1 other), OCR unavailable 1 |
| Parent mail of a parked attachment that was emitted | **547 of 547** |
| Calendar events | 142 unique |

```sql
select object_type, outcome, count(distinct source_object_id) from source_events
 where org_id = :org and source = 'gmail' group by 1, 2;
select attention_reason, count(*) from source_events
 where org_id = :org and object_type = 'email_message' and outcome = 'archived' group by 1;
```

**Lost at this layer.** Two kinds of ideal item:
- An application's "still incomplete" reminders: 5 of 5 were archived as bulk or no-reply. This is `f2`.
- Mail older than the window: `i6`, `s1` and `s2`.

## §4 · What the context graph holds

**Facts by origin.** 6,148 come from source events and 10,644 are `deterministic_derived`. No other derivation type exists. **0 facts were written from L2's reasoning.**

Of the 16,792 facts, 7,065 are engine counters and metrics: reply clocks, backlog, anomaly, trend and cohort readings, history counters. 4,244 of those are support-desk timers, although Support is not activated for this org.

```sql
select coalesce(derivation_type, '(null)'), count(*) from graph_facts where org_id = :org group by 1;
```

**Relations.** There are 2,352 edges, of six types:

| Type | Count |
|---|---|
| `corresponded_with` | 1,410 |
| `concerns` | 315 |
| `works_at` | 279 |
| `attended` | 259 |
| `owns` | 88 |
| `involves` | 1 |

None of them relates two pieces of meaning: nothing like *answers*, *fulfils*, *replaces*, *contradicts*, *is part of*, *is new evidence for* or *serves goal*.

```sql
select edge_type, count(*) from graph_edges where org_id = :org group by 1 order by 2 desc;
```

**Loops and promises.**
- `open_loops` has 212 question loops. Only 4 have ever closed, all with basis `replied`. Closing is deterministic, with no model involved (`context/open_loops.py`, docstring).
- There are 87 commitment nodes. All 87 have `commitment.status = open`, and 83 are past their due date.

```sql
select kind, status, coalesce(closed_basis, '-'), count(*) from open_loops where org_id = :org group by 1, 2, 3;
```

**Conflicts.** L1 raised 44 conflicts and resolved none (`unresolved_surface_both`). 40 of them are on `date.value`: mostly rescheduled meetings and dates quoted from older mail. The other 4 are on `amount.value`.

**The founder's own claims.**
- 80 `financial.amount` facts about MRR or ARR came from the founder's own sent mail.
- All of them sit on the founder's *person* node as generic amounts, so nothing compares them.
- 33 of them ("contracted ARR") look like quoted text from someone else.

## §5 · One piece of work in today's graph (`i1`)

Here is everything the graph holds about the accelerator application. It is rich: facts, notes, notes of notes, relations and timestamps are all there. The trouble is that the pieces are spread across more than ten nodes, each written by a different reader, and four of them contradict each other while all being "current":

| Node (written by) | What it says now | True? |
|---|---|---|
| outreach (code) | waiting on the evaluator's reply: 62 days, 2 follow-ups | ✅ |
| thread (L1) | the ball is in their court | ✅ |
| commitment (L1) | the founder promised to share updated details by 13 Aug: **open** | ❌ the updates went out on 11, 13 and 26 Aug |
| stated_dependency (code) | their decision is **waiting on the founder** to share details | ❌ for the same reason |
| condition (code) | their conditional offer, with the quote | ✅ |
| situations (rules) | `investor_relationship` dormant · `account_admin` dormant | ❌ it is a live programme application |

The old rule lane turned the open commitment into a card: "you are 71 days late". L2's reading was right, but it was held, and no part of that reading is stored.

## §6 · What Layer 2 does

**Runs.** 138 runs:

| Outcome | Count |
|---|---|
| result | 86 |
| over budget | 38 |
| failed | 7 |
| truncated | 6 |
| refused | 1 |

- **Trigger:** `bundle` (new mail) for all 138. `deadline_crossed` and `expected_reply_absent` exist in `contracts/reasoning_result.py`, but 0 runs carry them.
- **Files judged:** 80 of 264 files were ever judged.
- **Lanes of the 86 results:** investigation 45, conflict 23, decision 7, suppress 6, monitor 5.
- **Modes:** find_out 41, act 32, wait 7, nothing 6.
- **The conflict lane** is mostly about which meeting time was the confirmed one.

**The claim check.**
- Check v4 (22–27 Oct) held 57 of 63 results.
- Check v8 (from 27 Oct) held 9 of 23.
- Line-level drop reasons, all versions: `unknown_evidence` 538, `unsupported` (a name it could not find) 156, `ungrounded` 119, `wrong_number` (often only a different date format) 117.
- 15 lines were dropped because the company's own product name was "unsupported": the org's company field holds the legal name.

**Dossiers.**

| Measure | Value |
|---|---|
| Average size | 70,143 characters |
| Largest | 279,755 characters |
| "No company brief is accepted" | 138 of 138 |
| "No playbook for this file" | 105 of 138 (38 of 38 under prompt v7) |
| Context read capped ("never say something is absent because it is not here") | 113 of 138 |
| An item "L1 could not settle" | 114 of 138 |

```sql
select prompt_version, count(*), round(avg(length(dossier->>'text'))),
       count(*) filter (where dossier->>'text' like '%No company brief is accepted%'),
       count(*) filter (where dossier->>'text' like '%No playbook for this file%')
  from reasoning_results where org_id = :org and dossier ? 'text' group by 1;
```

**Why "No playbook".** A file gets a playbook only when an accepted brief line names its kind of work (`packs/compiler/playbook_reader.py`, `NO_KIND`). The brief has 29 lines, all `proposed` and none accepted. So the Founder Office expertise never reaches the judgment.

**Re-judgments.**
- 20 runs re-judged a file that had been judged before. 16 of those had no new mail in between, and spent 308,903 input tokens.
- `i1` was judged twice with no mail since 26 Aug. Each run read about 17.5k tokens and wrote about 7.4k.
- What the next dossier shows of its own earlier judgment is one line: "review … valid, mode act".

**The intro platform's file.**
- One anchor node holds 10 correlations across 4 domains: 500 events, 322 threads and 61 other people.
- L2 hit the per-decision ceiling 31 times with 0 input tokens, so the file was never judged.
- That loses `f3` (a scout's referral), `b1` (two new introductions) and `b3` (a stalled introduction).

## §7 · Where L2's conclusions go

**Admission is shadow.**
- `context/l2_admission.py` decides ADMIT, HOLD or REJECT. Its own docstring says: *"⛔ SHADOW: nothing here touches `context_situations`"*.
- `merge` and `link` are HOLD, "no applier for either yet".
- Since 22 Oct, 34 admission rows have been written.

**Interpretations are write-only.**
- `record_interpretations` wrote 30 `situation_interpretations` rows. Each averages 2,713 characters, about 4% of a dossier.
- Nothing in `reason/` or `deliver/` reads them.

**Example: a government registration portal file.**
- On 28 Oct, L2 concluded: "a portal correction for a startup registration, not an investor relationship". Admission recorded it as `admit / update`.
- The situation still reads `investor_relationship / fundraising / active`.
- The weekly drafter's goal still counts that file as an investor thread.

```sql
select a.decision, a.op, s.situation_type, s.domain, s.status
  from l2_admissions a join context_situations s using (situation_id)
 where a.org_id = :org and a.reason like '%portal correction%';
```

## §8 · Cards

**Where the 103 live cards (31 surfaced + 72 queued) come from:**

| Path | Cards |
|---|---|
| Old signal path, no capability | 38 |
| Corpus-situation (compiled) lane | 33 |
| L2 file review (22 of them investigation) | 31 |
| `verify.situation` | 1 |

**Duplicates by subject:**
- 5 "deals walkthrough";
- 5 "calendar invites";
- 9 "Needs a decision — <intro platform>".
- 21 cards are about the intro platform.

**Other problems:**
- About 13 headlines show the check's internal reason.
- 6 name the founder in the third person.
- 0 carry a goal.

```sql
select case when capability_key is null then 'old signal path' when capability_key like 'expert.%' then 'L2'
            when capability_key like 'expertise.%' then 'compiled' else capability_key end, count(*)
  from cards where org_id = :org and state in ('surfaced', 'queued') group by 1;
```

## §9 · Goals and the brief

- **Goals.** 7 goals in 11 revisions, all `proposed` and `inferred`. 4 came from the weekly drafter, 3 from L2. `goal_situation_links` is empty.
- **The brief.** 29 lines: company, connectors, goals, in-motion, people, preferences and watchlist. All are proposed.
- **Misfiling.** The in-motion lines file the government portal and an incubator as "investor". Those same lines would set the kind of work, and so the playbook.
- **Identity.** `org_self_identities` is empty.

## §10 · Spend since 21 Oct

**R-9, the L2 judgment** (`OWN_BUDGETS[SITE_REASON] = ("2.00", "0.25")`):
- It hit its daily cap every day: $1.88 to $1.96 a day.
- 95 calls were skipped for budget.
- 30 calls were paid and then failed validation ($4.20).
- 6 calls were truncated.

**The old flow's model calls, against R-9's:**

| Site | Calls | Input tokens |
|---|---|---|
| `l4_llm_decision` (old LLM decision maker) | 2,045 | 6.65M |
| `l2:resolution` (old resolution pass in `context/`) | 1,961 | 3.04M |
| `l4_llm_r1` (R-1) | 1,650 | 1.06M |
| **old flow, total** | **5,656** | **10.75M** |
| R-9 | 221 | 2.33M |

## §11 · How the nine symptoms follow from the trunk

| # | Symptom | Why it follows from "conclusions are not kept" |
|---|---|---|
| 1 | The unit is the counterparty, not the work | L2 cannot create, join or split a piece of work (no applier), so only the rules' sender files exist |
| 2 | Goals, brief and kind are stuck | They are conclusions too; they wait for approval before anything uses them |
| 3 | Silence is invisible | No "expected by" is stored, so the clock has nothing to compare against |
| 4 | Loops never close | "This promise was kept" is a conclusion; L2 saw it and nothing stored it |
| 5 | Dossiers are huge and noisy | No stored understanding, so all raw evidence is re-sent every time |
| 6 | The check blocks good answers | With no trusted state, it matches words against raw evidence strings |
| 7 | The budget is tiny | Reasoning from zero is expensive, so it is capped at about 12 judgments a day |
| 8 | Three card engines | The rules own the situations, so their lanes keep making cards |
| 9 | No measurement | Which is why none of this was visible |

## §12 · Measured and not true

Two things were checked and do not hold. Do not build on them.
- **"Most L1 signals come from quoted history."** Not true. Only 41 of 1,474 signals have no quote in new text: 8 come only from quoted history and 33 only from the subject line.
- **"Whole mails are parked for an attachment."** Not true. 547 of 547 parked items are attachment stubs, and their mails were emitted.
