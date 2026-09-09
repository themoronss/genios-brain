# Readiness against the 50 Admin Intelligence applications

Measured on `y-combinator-w27` @ `9ddf1f52`. Every number below was computed from the source
tree, not estimated. The method for each is stated so it can be re-run.

**Headline: the engine is real and the Admin domain is nearly empty.** L1 can classify what the
spec needs. L2 produces three Admin readings out of fifteen categories. L3 has zero authored Admin
capabilities. L4's action vocabulary is sales-shaped and cannot express managerial restraint.

---

## 0. The funnel report — not run

`scripts/pipeline_funnel_report.py` refuses without an explicit target:

> refusing to run … without an explicit database target. Pass `--database-url <url>` or export
> `GENIOS_TARGET_DATABASE_URL`. These scripts deliberately do not fall back to the configured
> `database_url`, because on a machine with a `.env` that is the production tenant database.

That guard is correct and this session has no database — no `.env`, no local server. **The claim
that this branch flipped the feed is therefore still unproven.** To close it:

```bash
export GENIOS_TARGET_DATABASE_URL='postgresql://…'
python scripts/pipeline_funnel_report.py --org <pilot_org_id>
```

Run it once on `23d47640` and once on `9ddf1f52` and compare. Nothing else settles the question.

---

## 1. The 10-part card structure

Your structure, against what the system can actually emit today.

| # | Part | State | Evidence |
|---|---|---|---|
| 1 | What should be happening | **Missing for Admin** | 3 authored capabilities exist: `deal_cooling`, `deal_cooling_v2`, `deal_health`. All sales. Zero Admin. |
| 2 | What is actually observed | **Works** | 43 of 58 declared fact paths have writers |
| 3 | The meaningful gap | **Works for 3 readings** | `awaiting_response`, `commitment_overdue`, `cohort_outreach_gap` |
| 4 | Why it matters now | **Works** | `do_nothing_consequence` on the execution contract; elapsed/countdown urgency |
| 5 | Who is accountable — confirmed / inferred / unknown | **Half** | This branch added `commitment.owner` and keeps absent absent. But there is **no ownership basis field** — grep for `ownership_basis\|owner_confidence\|declared_owner\|inferred_owner` returns **0**. The system cannot say *how* it knows. |
| 6 | Best next action | **Works, wrong vocabulary** | 9 plays, all sales/comms: `advance_deal`, `defend_position`, `deliver_commitment`, `follow_up`, `handle_objection`, `multi_thread`, `re_engage`, `reply`, `send_recap` |
| 7 | What should NOT be done | **Absent** | No field anywhere carries restraint. `do_nothing_consequence` is part 4, not part 7 — "what happens if you ignore this" is the opposite of "do not chase the four completed owners". |
| 8 | When to escalate | **Half** | L5 escalation machinery exists, but `escalation.accepted_at` and `escalation.receiver_node_id` have **no writer**. The system can escalate and cannot observe acceptance. |
| 9 | Closure evidence | **Absent where it matters** | `commitment.delivered_at` has **no writer** — and the registry says so plainly: *"no source system reports that a promise was kept."* Your example 8 ("someone says done, completion unverified") is unbuildable as specified. |
| 10 | Uncertainty from coverage | **Works** | `coverage_ready`, `missing`, and the `not observed` discipline are real and enforced |

**Four of ten are present. Three are half. Three are absent.** The three absent ones — restraint,
closure proof, ownership basis — are precisely what separates your spec from a status feed.

---

## 2. The 15 categories

Method: `context/domain_spec.py` maps an anchor to a situation type; a producer declares that
anchor as `ANCHOR_X = "x"`. Counting producers rather than type strings, because the readers route
by anchor.

**10 of 27 situation types have a producer. Only 3 of those are Admin.**

| Producer | Type | Domain |
|---|---|---|
| `outreach_situations.py` | `awaiting_response` | **Admin** |
| `outreach_situations.py` | `commitment_overdue` | **Admin** |
| `outreach_situations.py` | `cohort_outreach_gap` | **Admin** |
| `support_situations.py` | `escalation_requested`, `first_response_overdue`, `knowledge_gap`, `queue_overloaded`, `repeat_contact`, `ticket_aging`, `workaround_only` | Support |

Against your fifteen:

| # | Category | Producer? |
|---|---|---|
| 1 | Commitment | **Yes** — `commitment_overdue` |
| 2 | Follow-up & Relationship | **Yes** — `awaiting_response`, `cohort_outreach_gap` |
| 3 | Deadline | No |
| 4 | Scheduling & Meeting | No — `meeting_follow_through` declared, nothing writes it |
| 5 | Decision | No — no situation type exists at all |
| 6 | Ownership | No |
| 7 | Founder Bottleneck | No |
| 8 | Coordination | No |
| 9 | Process | No |
| 10 | Document & Information Integrity | No — `document_under_control` declared, nothing writes it |
| 11 | Vendor & Contract | No |
| 12 | Financial & Admin Obligations | No |
| 13 | Goal & Progress | No |
| 14 | Opportunity | No — `opportunity` declared, nothing writes it |
| 15 | Risk | No |

**2 of 15.** And both of those can only fill 7 of your 10 card parts.

---

## 3. The 50 applications

Roughly **6 are reachable today**, all inside categories 1 and 2, and each is missing at least one
part of your structure.

| App | Reachable | Blocker |
|---|---|---|
| 1 External deliverable promised, not produced | Partly | No "do not" clause |
| 2 Internal commitment blocking a launch | Partly | Blocked-work chain is not computed |
| 3 Fulfilment cannot be verified | **No** | `commitment.delivered_at` has no writer, by design |
| 4 Two commitments cannot both be honoured | No | No resource-contention model |
| 5 Important inbound request waiting | Yes | — |
| 6 Historical investor condition now satisfied | **No** | See §4 |
| 7 Strategic relationship going cold | Yes | — |
| 8 Promised recurring update skipped | Partly | Cadence commitments are not stored |
| 9–12 Deadline | No | No producer |
| 13–16 Scheduling | No | No producer |
| 17–20 Decision | No | No situation type |
| 21–23 Ownership | No | No producer; no authority model |
| 24–26 Founder bottleneck | No | No producer |
| 27–29 Coordination | No | No producer + needs Slack/Jira |
| 30–32 Process | No | No producer + no authored process |
| 33–35 Document integrity | No | No producer |
| 36–38 Vendor & contract | No | No situation type |
| 39–41 Financial | No | No situation type + no finance connector |
| 42–44 Goal & progress | No | No situation type |
| 45–47 Opportunity | **No** | See §4 |
| 48–50 Risk | No | No situation type |

---

## 4. The single most important finding

Your marquee examples — 6, 20, 45, 46, 47 — all share one shape:

> *"They said come back when X. X has now happened."*

**The system cannot do this, and the reason is written in the code.** `capture/esqe/detector.py`
says of the opportunity predicate:

> *"the only form of 'satisfied' the extraction can express — there is **no `condition_met` flag**"*

`OPPORTUNITY_SIGNAL` fires only when a **single message** both states a condition and shows it
satisfied. There is no stored dormant condition that later, unrelated evidence can wake.

That is not a tuning gap. It is a missing primitive: **a condition, stored against a counterparty,
with a satisfaction predicate the graph re-evaluates as new facts arrive.** Without it, the
category the Globe itself calls *"the pattern a human almost never catches"* cannot exist.

---

## 5. Layer by layer

### L1 — Knowledge · **the strongest layer**

The taxonomy already covers what your spec needs: `COMMITMENT_MADE`, `COMMITMENT_DUE`,
`DEADLINE_STATED`, `DECISION_PENDING`, `DECISION_MADE`, `APPROVAL_REQUESTED`, `CONTRACT_RENEWAL`,
`FINANCIAL_OBLIGATION`, `RISK_FLAGGED`, `OPPORTUNITY_SIGNAL`, `RELATIONSHIP_CHANGE`,
`INFORMATION_CONFLICT`, `ESCALATION`, `ANOMALY` — 14 types.

**L1 is already classifying things nothing downstream consumes.** `DECISION_PENDING` is detected
and there is no decision situation. `CONTRACT_RENEWAL` is detected and there is no vendor
situation. `RISK_FLAGGED` is detected and there is no risk situation.

Gap: no stored conditional trigger (§4).

### L2 — Context · **the bottleneck**

3 Admin producers. 15 declared fact paths with no writer, and the missing ones are exactly the
ones your spec leans on: `commitment.delivered_at`, `escalation.accepted_at`,
`escalation.receiver_node_id`, `document.approved_at`, `response.first_reply_at`,
`meeting.recap_sent`, `mailbox.owner`.

This is where the work is. Every category from 3 to 15 needs a producer here, and the producers
are not hard — `outreach_situations.py` is ~450 lines and yields three readings.

### L3 — Expertise · **empty for Admin**

Three authored capabilities, all sales. The four-brain merge is structurally present
(`expertise_builder.py` merges expert / organization / behavior / adaptive), so the machinery
works — it has nothing Admin to merge.

Your spec's part 1 ("what *should* be happening") lives here and does not exist. Worse, your
examples 3, 4, 21, 23 need something the Organization Brain has never held: **a responsibility
matrix with authorized backups.** Grep for `responsibility_matrix|authorized_backup|delegate_to`
returns **0**.

Without it, example 3 ("hand off to the Compliance Lead") is not a card the system can honestly
produce, and example 4's correct refusal — *"GeniOS cannot safely reassign this responsibility"* —
is the only honest output for every ownership case today.

### L4 — Reasoning · **right shape, wrong vocabulary**

The 17-unit structure and single Decision Maker are real. The problem is the action vocabulary:
nine plays, all conversational. None of them expresses:

- hand off to an authorized backup
- request a management decision on ownership
- block external submission of unapproved material
- return a document with named deficiencies
- designate an authoritative version and retire the other
- consolidate duplicated follow-ups into one authoritative request
- **do nothing, deliberately, and say why**

That last one is the whole difference between your spec and a reminder app.

---

## 6. What to build, in order

1. **The condition primitive** (§4). Unlocks categories 5, 14 and your best examples. Nothing else
   unlocks as much.
2. **Ownership basis + responsibility matrix** in the Organization Brain — `confirmed` /
   `inferred` / `unknown`, plus authorized backups. Unlocks category 6 and makes 1, 3, 7 honest.
3. **A restraint field and a closure field** on the decision contract. Cheap, and they are two of
   your three absent card parts.
4. **Producers for categories 3, 5, 6, 10** — deadline, decision, ownership, document integrity.
   All four are Gmail-reachable and all four have L1 signal types already firing into nothing.
5. **Admin capabilities in the Expert Brain.** Without these every card above is a fact with no
   interpretation.

Categories 8, 9, 11, 12 need connectors or authored process and should not be attempted first.

---

## 7. The honest summary

The pipeline is sound and this branch removed the four defects that made its output actively
wrong. But **the distance between what it emits today and the twenty manager examples is not a
tuning distance.** It is roughly: one missing primitive, one missing authority model, two missing
contract fields, four missing producers, and an Admin corpus that has never been written.

L1 is ready. L2 is a third built. L3 is empty. L4 is structurally ready and speaks the wrong
language.
