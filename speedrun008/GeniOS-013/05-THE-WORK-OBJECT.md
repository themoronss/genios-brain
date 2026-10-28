# 05 · The piece of work: the situation as Atlas v2 means it

**Written for:** everyone. §1, §2 and §12 are written in plain words. The rest is the specification an agent builds from.
**Architecture source:** GeniOS-008 `00-ARCHITECTURE.md`. Two lines from it settle the design: L2 is the primary layer, and *"the situation is formed by reasoning over the bundle, the expertise and what the company already knows. L3 only remembers what L2 concluded."* L3's job is described as *"Intelligence Graph: situations → interpretations … It records what GeniOS concluded."*

---

## §1 · What it is, and what it is not

A **work item** is one piece of work the company is doing or waiting on, for example:
- one application;
- one raise conversation with one fund;
- one hire;
- one introduction;
- one vendor renewal;
- one compliance filing;
- one customer deal.

**It is the situation of Atlas v2, made real.**
- L2 proposes it.
- L3 checks it and keeps it.
- The clock watches it.
- Cards are views of it.

**It is not per counterparty.**
- One counterparty can hold many works. The intro platform is one "channel" work plus one work per introduction.
- One work can span many people, addresses and tools. An accelerator application includes the evaluator, the programme's no-reply address, the calendar meeting and the founder's updates.

**It is not a memory store.** It holds conclusions, a few KB per work. It points to evidence by id; the evidence stays where it already is (`source_events`, `prepared_content`, the graph).

**It is where everything meets.**
- A calendar event, a Drive document and a Mac-app screen moment join a work as **members**.
- A goal is linked to a work with a **relation**.
- An agent's task (L4 `ExecutionObject`) belongs to a work. The task's result is a member event, and it can close the work's loops.

This is what makes cross-tool, cross-domain, goal and agent correlation possible: they all share one key.

**Beside, not instead.** Today's `context_situations` (one row per correlation, written by rules) and today's files (`context/workstreams.WorkFile`, "one counterparty's correlations", never stored) stay as they are. They become **seeds** and **evidence** for works, exactly as `context/l2_admission.py` already treats them.

## §2 · The contract (`contracts/work_item.py`)

| Field | Type | Meaning | Written by |
|---|---|---|---|
| `work_id` | `wk_<hash>` | stable id; never re-minted on a rebuild | code |
| `title` | text ≤ 120 | the work in the founder's words ("Reconsideration of the accelerator application") | L2 · founder |
| `kind` | enum | `investor` · `program` · `compliance` · `hiring` · `intro` · `partner` · `vendor` · `customer` · `other` (the brief's `WORK_KINDS`, plus `customer` and `other`) | L2 · founder |
| `kind_basis` | enum | `l2` (unconfirmed) · `brief` (an accepted line) · `founder` | code |
| `status` | enum | `proposed` · `active` · `waiting_them` · `waiting_us` · `blocked` · `done` · `dropped` · `merged` (§7) | L2 · founder · code |
| `stage` | text | one of the playbook stages for `kind` (`packs/compiler/playbook_reader`) | L2 (code checks it is in the list) |
| `whose_move` | `us` · `them` · `none` | from the open loops (§4); L2 may override it with evidence | code · L2 |
| `next_expected` | object | what should happen next, from whom, by when, why that date, and what to do if it doesn't (§8) | L2 · founder |
| `goal_links` | list | `{goal_id, relation: advances / threatens / depends_on / unclear, confirmed: bool}` | L2 · founder |
| `parties` | list | `{node_id, role: decides / contact / introducer / us / other}` | L2 · code |
| `importance` | object | `{stakes, urgency}`: words (high, medium, low), never a score | L2 |
| `verdict` | object | summary (≤ 3 sentences), frame, the six confidence words, evidence ids, writer, time (§9) | L2 · founder |
| `parent_work_id` | id | e.g. an introduction under the intro-platform channel work | L2 |
| `merged_into` | id | set when two works become one | admission |
| `version` | int | compare-and-set on every write | code |
| `created_at`, `updated_at`, `closed_at` | time | | code |

## §3 · Members (`work_members`)

**A member** is anything that belongs to the work: a thread, an event, a meeting, a document, a correlation, a person or company node, or a screen moment.

**How something becomes a member:**
- **By continuation (code, 0 model calls).** A new event in a thread that is already a member joins automatically. A calendar event whose invite thread is a member joins automatically.
- **By L2.** A new thread, a new tool's item, or a move from one work to another needs L2. It cites the evidence (an id that was printed).
- **By the founder.** "This belongs to X."
- **Onboarding (Step 5) only.** Seed membership from today's correlations is allowed, labelled `joined_by = seed`. L2's first judgment confirms or moves it.

A thread may belong to two works (for example, one introduction mail that introduces two people). The membership row says so explicitly.

## §4 · Loops: what is owed, by whom, and whether it has been settled

`open_loops` exists already (212 question loops; only 4 ever closed). It is extended, not replaced.

| Field | Meaning |
|---|---|
| `kind` | `question` (someone asked something) · `ask` (a request for an action) · `promise` (someone committed to do something). The 87 commitment nodes migrate in as `promise` |
| `owed_by` | `us` · `them`, plus `awaited_from_node_id` when one person owes it |
| `text`, `due_at` | the words and the date, as the evidence printed them |
| `status` | `open` → `answered` · `kept` · `released` · `broken` · `superseded` · `moot` |
| `closed_by_event`, `closed_by_result` | the mail that settled it, and the L2 result that judged it settled |

**Who closes a loop.**
- L2 proposes the closure, citing the event.
- Code checks it (§10).
- Today's deterministic reply match stays as a hint ("a reply exists"). It no longer closes a loop on its own. It is the reason one reply used to close every ask.

## §5 · Meaning links (`intelligence_links`)

| Relation | From → to | Example |
|---|---|---|
| `answers` | event → question loop | the investor's question is *not* answered by the generic update (`i2`) |
| `fulfils` | event → promise loop | the 11 Aug update fulfils the promise made on 6 Aug (`i1`) |
| `replaces` | value → value | the meeting moved from Monday to Tuesday, so there is no conflict |
| `contradicts` | claim ↔ claim | four different traction numbers (`p1`) |
| `part_of` | work → work | an introduction is part of the intro-platform channel work |
| `evidence_for` | event → work | today's incubator review is a new fact for the accelerator update (`i1`) |
| `serves` | work → goal | the application serves "get into an accelerator" |

- **Kept apart from `graph_edges` on purpose.** Graph edges are evidence and carry their own authority scale. Putting conclusions into the same column would mix two scales, the same mistake recorded internally as "two authority scales in one column".
- **Every link carries** its writer (an L2 result fingerprint or the founder), its evidence ids, and `valid_from` / `valid_to`. It is bitemporal, like the graph.

## §6 · Company claims (`company_claims`)

**What it records.** What we have told whom about ourselves:

| Field | Meaning |
|---|---|
| `topic` | traction, customers, team, funding, product, or other |
| `metric` | e.g. MRR, ARR, count |
| `value` | the value, normalised to an amount with its currency and period |
| `said_in` | the event it was said in |
| `said_to` | the people it was said to |
| `said_at` | when it was said |
| `quoted` | true when the text was someone else's |

**Who writes it.**
- Code proposes a claim from an amount in **our own outbound mail**. Today's 80 `financial.amount` facts on the founder's person node are the backfill.
- L2 sets `topic`, and sets `quoted` when the amount came from someone else's text.

**How a conflict is found.** Code compares claims with the same topic and metric across recipients and time. A difference opens one "one number everywhere" work (`p1`). The founder picks the true number; GeniOS never does.

## §7 · Status

```
proposed ─► active ─► waiting_them ⇄ waiting_us ─► done
                 │          │             │       └► dropped
                 └──────────┴──── blocked ┘
any ─► merged   (admission only, when two works become one)
```

- **Allowed transitions** are a table in the contract. Admission refuses any other (§10).
- **`done` and `dropped`** need evidence (an outcome mail, a decision) or the founder.
- **`waiting_*` follows the loops.** Code sets it from `whose_move`; L2 may override with evidence.

## §8 · Next expected: the field the clock reads

`next_expected = {what, from, by, basis, if_missed, set_at}`

| `basis` | Where `by` comes from |
|---|---|
| `stated` | a date in the evidence ("the review is on the 23rd") |
| `playbook` | the stage prior for the kind (`playbook_reader` stage priors) |
| `cadence` | this counterparty's measured reply time, with a multiple |
| `founder` | the founder said so |

`if_missed` is one of: `nudge`, `close`, `ask_founder`, `escalate`.

**Bounds, checked by code:**
- `by` is in the future when it is set.
- `by` is no later than the playbook's maximum for the stage, unless the basis is `stated` or `founder`.
- The clock (Step 4) needs nothing but this field and the members' latest event time. It makes 0 model calls.

## §9 · Verdict and versions

**The verdict.**
- `summary`: what is true now, in ≤ 3 sentences, written for the founder.
- `frame`: the reading the verdict rests on.
- `confidence`: the six Atlas dimensions, each as a word.
- `evidence`: printed ids.
- `writer` and `at`.

**Versions.**
- Every change writes a row to `work_item_versions`: version, time, writer, a diff and evidence. It is append-only.
- `work_items` holds the current version.
- A write applies only if the version it read is still current (compare-and-set). This is Orchestrator step 11.

**Founder corrections win.** A founder's correction is a version with writer `founder`. The fields it set are **locked against L2**: L2 may propose a change, admission holds it, and it becomes a question to the founder.

## §10 · Admission: what code checks before L2's change is kept (`context/work_admission.py`)

| Check | On failure |
|---|---|
| Every id the change cites was printed in the dossier (the catalogue) | REJECT that change |
| A loop closes only on an event that (a) is a member of the same work, (b) is after the loop opened, and (c) comes from the side that owed it: our outbound for our promise or their question; their inbound for our question | HOLD and raise an EvidenceNeed |
| A status transition is in the allowed table (§7) | REJECT |
| `stage` is in the playbook's list for the kind | HOLD (stage unknown) |
| `next_expected.by` is within the bounds in §8 | clamp to the bound and note it |
| `merge` and `split` name only works the dossier printed | REJECT |
| A field the founder locked is not overwritten | HOLD and ask the founder |
| The version read is still current | retry on the next pass |

Each change is admitted or refused on its own, so one bad line no longer holds the whole judgment. That was the defect behind 66 of 86 held results. Everything admitted is written in **one transaction**: the work, its version row, members, loops, links and claims. Nothing here calls a model.

## §11 · Tables (migrations 0257, 0258; erased with the org like 0256)

```sql
create table work_items (
  org_id text not null, work_id text not null, version int not null,
  title text not null, kind text, kind_basis text not null,
  status text not null, stage text, stage_since timestamptz,
  whose_move text, whose_move_since timestamptz,
  next_expected jsonb, importance jsonb, verdict jsonb,
  goal_links jsonb not null default '[]', parties jsonb not null default '[]',
  parent_work_id text, merged_into text,
  created_at timestamptz not null, updated_at timestamptz not null, closed_at timestamptz,
  primary key (org_id, work_id));
create table work_item_versions (
  org_id text not null, work_id text not null, version int not null, at timestamptz not null,
  writer text not null, writer_ref text, diff jsonb not null, evidence jsonb not null default '[]',
  primary key (org_id, work_id, version));
create table work_members (
  org_id text not null, work_id text not null, member_kind text not null, member_ref text not null,
  joined_at timestamptz not null, joined_by text not null, writer_ref text,
  evidence jsonb not null default '[]', left_at timestamptz,
  primary key (org_id, work_id, member_kind, member_ref));
create table intelligence_links (
  org_id text not null, link_id text not null, relation text not null,
  from_ref text not null, to_ref text not null, writer text not null, writer_ref text,
  evidence jsonb not null default '[]', valid_from timestamptz not null, valid_to timestamptz,
  primary key (org_id, link_id));
create table company_claims (
  org_id text not null, claim_id text not null, topic text, metric text, value_text text not null,
  amount_minor bigint, currency text, period text, said_in_event text not null,
  said_to jsonb not null default '[]', said_at timestamptz not null, quoted boolean not null default false,
  work_id text, writer text not null,
  primary key (org_id, claim_id));
-- 0258: open_loops gains kind 'ask' / 'promise', owed_by, text, due_at, closed_by_result;
--       the 87 commitment nodes are copied in as promise loops (their graph facts stay as evidence).
```

There is one writer per table: `context/work_store.py`. A CI guard (like the existing situation-writer ratchet) fails the build if any other module writes these tables.

## §12 · A worked example: `i1` before and after

**Before (today's graph):** six notes from different readers, four of them contradicting each other ([06 §5](06-MEASUREMENTS.md)). Two situations, both "dormant". No conclusion stored.

**After (one work item):**

| Field | Value |
|---|---|
| title | Reconsideration of the accelerator application |
| kind | `program` (basis `l2`: L2 already proposes it today as `proposed_kind`) |
| status | `waiting_them`, since 26 Aug |
| stage | `reconsideration_requested` (from the program playbook) |
| loops | founder's promise "share updated details within a week" → `kept` by the 11 Aug mail (`fulfils` link) · evaluator's offer to reconsider on updates → open, owed by them |
| claims in this work | three traction statements to the evaluator (11, 13 and 26 Aug); they `contradict` the claims made to two funds in May (the `p1` work) |
| next_expected | `{what: their decision, from: evaluator, by: +14 days from the next update, basis: playbook, if_missed: close}` |
| goal_links | serves "get into an accelerator" (proposed, unconfirmed) |
| verdict | "A pass with the door left open. Three updates sent, none answered. The next update must carry a new, checkable fact; then stop." |
| evidence_for | the incubator's final review (a new fact) |

The card the founder should see (ideal `i1`) is a view of this row. No evidence has to be re-read to produce it.

## §13 · The 20 ideal cards against the contract

Each ideal card is a view of a work item. These fields carry it:

| Ideal | Kind | Fields that make the card |
|---|---|---|
| `p1` | other ("one number") | claims + `contradicts` links; `ask_founder` |
| `f1` | program | `next_expected` (stated: the review slot); stage |
| `f2` | program | status `waiting_us`; loop: the application is incomplete (owed by us) |
| `f3` | program (child of the intro channel) | loop: the referral promised by them; `next_expected` missed |
| `f4` | program | `waiting_them`; `next_expected` (stated); no notification |
| `i1` | program | §12 |
| `i2` | investor | `answers` link = *not answered*; loop open, owed by us |
| `i3` | investor | meeting member; no outbound after it; `next_expected` (playbook) missed |
| `i4` | investor (wave) | one work, 12 members, 0 replies; `ask_founder` (which still matter) |
| `i5` | each affected work | a bounce member; loop `moot` (it never arrived) |
| `i6` | investor | status `done` (verified by a sent mail) |
| `s1` | customer | loop: their question, owed by us; dormant 6 months |
| `s2` | customer (wave) | one work, 21 members silent; `ask_founder` |
| `b1` | intro (×2, children) | loop: say yes or no, owed by us |
| `b2` | partner | 2 meeting members; no written next step |
| `b3` | intro (child) | `waiting_them`; `if_missed: close` |
| `c1` | compliance | bounce member + loop owed by them; `next_expected` missed |
| `c2` | vendor | `next_expected` (stated renewal date) |
| `h1` | hiring | loop: the offer, owed by them; coverage partial → `ask_founder` |
| `l1` | program | `waiting_them`; snoozed by the founder (a version written by the founder) |
