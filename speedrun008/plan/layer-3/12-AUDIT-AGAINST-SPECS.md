# Layer 3 — audited against the four specifications

**2026-09-25** · measured from the code, against:
Context Lifecycle Management · Eight-Group HCC Catalogue · Business Situation L2 Deep Spec ·
Cross-Correlation Coding Spec

---

## 0. What the four specs actually say Layer 3 is

They describe it as six groups, and **all six are the new Layer 3**, because the last one's output
is the `BusinessSituationObject`:

```
QualifiedEnterpriseSignal
   ↓
L2.1 Context Graph  ↔  L2.2 Graph Engines        (8 views · 8 engines)
   ↓
L2.3 Cross-Correlation                            (8 correlators)
   ↓
L2.4 Context Quality                              (8 components)
   ↓
L2.5 Situation Candidate Generator
   ↓
L2.6 Business Situation Engine
   ↓
BusinessSituationObject
```

**32 named components.** Here is what is actually there.

---

## 1 · L2.2 GRAPH ENGINES — **7 of 8 built**

| engine | code | state |
|---|---|---|
| Graph Builder | `find_or_create_node` | ✅ identity by `canonical_key`, alias collision → merge proposal |
| Graph Updater | `write_fact` → `fact_write_action` | ✅ **5 branches**, staleness checked before authority |
| Graph Validator | typed endpoints + authority | ✅ 26 files |
| Graph Deduplicator | `merge.py` + `graph_aliases` | ✅ 33 files, reversible |
| **Freshness Manager** | — | ⛔ **SEE BELOW** |
| Lifecycle Manager | `active / dormant / resolved / archived` | ✅ |
| Version Manager | `graph_versions` + `/graph/as-of` | ✅ half-open `[valid_from, valid_to)` |
| Consistency Checker | `discrepancies` table | ✅ held vs challenger preserved |

### ⛔ 1.1 · The Freshness Manager is a column nobody writes

```sql
graph_facts.freshness_policy_id text     -- migration 0004
```

**Zero writers. Zero readers. Anywhere.** This is the project's own doctrine caught again —
*"a column no writer names is null forever."*

The specs demand it four separate times: LCX-08 (*"review TTL ends"*), LCX-12 / GE-HCS-05
(*"a forwarded old email refreshes authority"*), CL-05, CL-12, CQ-HCS-02 and LCW-03
(*"freshness decay treated as truth decay"*).

⛔ **And `noop`-as-corroboration makes this urgent.** The Evidence Graph raises confidence
**60 → 85 → 100** on a repeated value. **A forwarded copy of a six-month-old delegation currently
counts as corroboration** — exactly GE-HCS-05's forbidden result — because nothing distinguishes
*new evidence* from *copied text*.

---

## 2 · L2.3 CROSS-CORRELATION — **7 of 8, and the shape is different**

| spec correlator | code | |
|---|---|---|
| **Cross Tool** | — | ⛔ **NO MODULE** |
| Cross Resource | `correlation_resource.py` | ✅ |
| Cross User | `correlation_people.py` | ✅ (renamed) |
| Cross Timeline | `correlation_timeline.py` | ✅ |
| Cross Conversation | `correlation_conversation.py` | ✅ |
| Cross Domain | `correlation_domain.py` | ✅ |
| Cross Organization | `correlation_organization.py` | ✅ |
| Dependency | `correlation_dependency.py` | ✅ |
| *(extra)* | `correlation_history.py`, `correlation_membership.py` | ✅ |

### ⛔ 2.1 · The missing one is the one a two-connector pilot needs most

**Cross Tool is the Gmail ↔ Calendar ↔ Drive join.** With only two connectors live, **it is the
only correlator whose inputs both exist.**

It owns 12 spec cases on its own — CT-01…CT-12 — plus CC-01…CC-06, and every one of them is a
pilot-shaped failure: *"an audit email and a calendar event with a different title"*,
*"Gmail current, Calendar unavailable"*, *"draft reported as sent"*, *"one email mirrored into a
task and a calendar description counted as three confirmations."*

### ⛔ 2.2 · Correlation groups; the specs want it to TYPE

`correlation.py`'s own first line: *"Do these signals belong to the same thing?"* — anchored on
`(counterparty entity, domain)`. **One question, one answer: together or apart.**

The specs want a **typed relation with a direction**. Measured:

| present | absent |
|---|---|
| `approved_by` · `supersedes` · `contradicts` · `requires` · `blocks` | ⛔ `same_entity_as` · `responds_to` · `assigned_to` · `requested_from` · `scheduled_for` · `fulfills` · `satisfies_condition` |

**5 of 12.** And the seven missing ones carry the product's meaning:
`fulfills` is *"did the document satisfy the requirement"*; `responds_to` is *"did they reply"*;
`satisfies_condition` is the entire dormant-opportunity feature (APP-53, TL-03, E2E-06).

⛔ *"`related_to` must not silently become `blocks`"* — today there is no `related_to` **and** no
`blocks` edge written by a correlator, so the distinction cannot be made either way.

### ⛔ 2.3 · There is no correlation decision record

The spec's `correlation_record` wants `accepted_evidence_ids`, `rejected_candidates_with_reasons`,
`unresolved_candidates`, `disposition: accept | reject | hold`, `reason_codes`,
`next_evaluation_at`.

**Grep finds reason codes in exactly two modules: `proposal_gate.py` and `interpretation_store.py`
— both built in L2-5 and L2-6 last week.** The correlator itself records nothing.

> *"A candidate rejected for wrong audit period and a candidate not retrieved at all are different
> failures."*

**Today they are the same failure: silence.** A missed correlation cannot be explained, which makes
every correlation bug unfixable by inspection.

---

## 3 · ⛔ THE ABSENCE CONTRACT — **3 of 8 ingredients, and this is the biggest hole**

This is the single most-repeated requirement across all four documents. It appears as
**LCX-13 · LCX-15 · CG-06 · CL-04 · BS-03 · CC-02 · CC-30 · CQ-HCS-05 · FX-07 · FX-08 · FX-12 ·
BW-04 · A8 · §9.3**.

| ingredient | state |
|---|---|
| coverage | ✅ 138 files |
| watermark | ✅ 25 files |
| backfill bounds | ✅ 62 files |
| **`pagination_complete`** | ⛔ **absent** |
| **`sync_health`** | ⛔ **absent** |
| **`known_gaps`** | ⛔ **absent** |
| **`observation_interval`** | ⛔ **absent** |
| **a `scoped_absence()` gate** | ⛔ **absent** |

⛔ **The consequence, stated by FX-08 exactly:** *"Rate limit produces an empty adapter result
instead of an error."* Without `sync_health` and `pagination_complete`, **an empty query and a
broken connector are indistinguishable** — so *"no meeting scheduled"* can be produced by an
outage.

**This is the failure mode that destroys trust fastest**, and it is one contract away.

---

## 4 · ⛔ THE EIGHT CLOCKS — **5 of 8, and the three missing ones are the expensive ones**

| clock | files | |
|---|---|---|
| `occurred_at` | 157 | ✅ |
| `valid_from` / `valid_until` | 37 / 16 | ✅ half-open, tested |
| `evaluated_at` | 21 | ✅ |
| `retain_until` | 5 | ✅ |
| **`recorded_at`** | **1** | ⚠️ **knowledge time exists in ONE file** |
| **`source_updated_at`** | 0 | ⛔ absent — no provider revision ordering |
| **`next_evaluation_at`** | 0 | ⛔ **absent — §5 below** |
| **`review_due_at`** | 0 | ⛔ absent |

### 4.1 · `recorded_at` in one file means as-of replay is half-built

`/graph/as-of` reads `valid_from`/`valid_to`, which is **effective** time. LCX-02 and CL-02 want
*"what did GeniOS know on 3 September"* — that is **knowledge** time, and it is recorded in one
place. **Today a late correction can make the system look like it knew something earlier than it
did.**

---

## 5 · ⛔ THE BIGGEST FUNCTIONAL GAP — nothing evaluates when nothing arrives

> ## ⛔ CORRECTED — 2026-09-25, during L3-06
>
> **This claim is false and was the loudest in the plan.** Elapsed time is evaluated at FOUR live
> levels: `platform/scheduler`'s **heavy tick runs L1 → L2/L3/L5 for every org every 6 hours**
> whether or not a message arrived; `reason/runner` applies per-rule cooldowns; `executions.
> next_check_at` **is** a registered due instant with a real due query; and
> `age_uncorrelated_situations` retires quiet situations on time alone. **The heavy tick was already
> pinned** by `test_the_heavy_sweep_still_reasons_for_every_org`.
>
> `due_evaluation` and `next_evaluation` do return zero — **they are not the names this system
> uses.** A grep for two invented words found none of a scheduler thread, a cadence in hours, a
> per-rule cooldown and a column called `next_check_at`. See
> [`findings/step-06-the-timer.md`](findings/step-06-the-timer.md).

```
due_evaluation   0 files      next_evaluation   0 files

> ## ⛔ CORRECTED — 2026-09-25, during L3-06
>
> **This claim is false and was the loudest in the plan.** Elapsed time is evaluated at FOUR live
> levels: `platform/scheduler`'s **heavy tick runs L1 → L2/L3/L5 for every org every 6 hours**
> whether or not a message arrived; `reason/runner` applies per-rule cooldowns; `executions.
> next_check_at` **is** a registered due instant with a real due query; and
> `age_uncorrelated_situations` retires quiet situations on time alone. **The heavy tick was already
> pinned** by `test_the_heavy_sweep_still_reasons_for_every_org`.
>
> `due_evaluation` and `next_evaluation` do return zero — **they are not the names this system
> uses.** A grep for two invented words found none of a scheduler thread, a cadence in hours, a
> per-rule cooldown and a column called `next_check_at`. See
> [`findings/step-06-the-timer.md`](findings/step-06-the-timer.md).
```

**Five of the supplied documents name this independently**: LCX-14, CL-03, TL-01, BW-14, LCW-04 —

> ## ⛔ CORRECTED — 2026-09-25, during L3-06
>
> **This claim is false and was the loudest in the plan.** Elapsed time is evaluated at FOUR live
> levels: `platform/scheduler`'s **heavy tick runs L1 → L2/L3/L5 for every org every 6 hours**
> whether or not a message arrived; `reason/runner` applies per-rule cooldowns; `executions.
> next_check_at` **is** a registered due instant with a real due query; and
> `age_uncorrelated_situations` retires quiet situations on time alone. **The heavy tick was already
> pinned** by `test_the_heavy_sweep_still_reasons_for_every_org`.
>
> `due_evaluation` and `next_evaluation` do return zero — **they are not the names this system
> uses.** A grep for two invented words found none of a scheduler thread, a cadence in hours, a
> per-rule cooldown and a column called `next_check_at`. See
> [`findings/step-06-the-timer.md`](findings/step-06-the-timer.md).
plus CC-23 and §5.4.

> *"A response window elapses with no incoming events. GeniOS never detects a material stalled
> commitment."*

The sweep is **event-driven**. A promise due Thursday, with no new mail on Friday, **produces
nothing** — and the product's entire value proposition is noticing exactly that.

`context/periodic.py` exists and is the natural home. **What is missing is the registration: a
predicate, a due instant, and a durable trigger.**

⛔ **And this compounds §3.** The safe conclusion the specs demand —
*"No reply observed in connected email through Friday 09:00"* — needs **both** the timer (§5) and
the coverage contract (§3). Neither exists. **Today the only honest output is silence.**

---

## 6 · L2.4 CONTEXT QUALITY — the pieces exist, the gate does not

All eight concepts appear in the code (confidence 47 files, conflict 41, missing-context 70,
completeness 39, validation 39, noise 20, freshness 16, evidence 84) — **but as scattered reads,
not as eight named components returning one verdict with reasons.**

The spec is precise about what that costs:

| spec rule | today |
|---|---|
| *"Unknown must never silently become false"* | ⛔ no three-valued `true/false/unknown` predicate type |
| *"Do not let an integer score authorize an unsupported conclusion"* | ⚠️ the 5-part vector exists and is `MIN` not average — ✅ this half is right |
| *"Confidence Calculation must be deterministic; an LLM-generated score is forbidden"* | ✅ **already enforced** — model may DESCRIBE never SCORE |
| *"Dependent copies must not inflate corroboration"* (CQ-HCS-01) | ⛔ `noop` corroboration has **no lineage check** |

### ⛔ 6.1 · CQ-HCS-01 is a live defect, not a design question

> *"Ten copies of one claim and one genuine independent validator result… duplicating copies cannot
> raise independent-support count."*

The Evidence Graph's ladder is **one:60 / two:85 / three+:100**, driven by `src_count`, deduped
**per event**. ⛔ **Ten forwards of one original are ten different events.** So ten copies of one
claim read as ten independent sources today.

`graph_source_refs.independence_group` **is the column meant to stop this, and it is unwritten** —
the same defect as `freshness_policy_id`.

---

## 7 · The score

| group | built | missing |
|---|---|---|
| **L2.1 Graph views** | 4 of 8 have presence | temporal · communication · resource · knowledge |
| **L2.2 Graph Engines** | **7 of 8** | Freshness Manager (a column with no writer) |
| **L2.3 Correlators** | **7 of 8** | ⛔ **Cross Tool** — the two-connector join |
| **typed relations** | 5 of 12 | `fulfills` · `responds_to` · `satisfies_condition` … |
| **correlation diagnostics** | 0 | accept/reject/hold + reason codes |
| **absence contract** | 3 of 8 | `sync_health` · `pagination_complete` · the gate |
| **the clocks** | 5 of 8 | `recorded_at` (×1) · `source_updated_at` · `next_evaluation_at` |
| **time-triggered eval** | ⛔ **0** | the whole thing |
| **L2.4 Quality gate** | pieces yes, gate no | three-valued predicates · lineage dedupe |
| **Intelligence Graph** | 4 tables, 0 edges | nodes · edges · write-back · the read |

⛔ **The engine room is built. What is missing is at the seams: what we could see, when to look
again, what kind of link this is, and what we already concluded.**
