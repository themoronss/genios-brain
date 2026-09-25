# Evidence Graph vs Intelligence Graph — the difference, and when each is used

**2026-09-25** · plain explanation. The mechanics are in
[`06-HOW-BOTH-GRAPHS-WORK.md`](06-HOW-BOTH-GRAPHS-WORK.md).

---

## 1. The difference, in one line each

| | |
|---|---|
| **Evidence Graph** | **What the world is.** Facts that came from a source. Somebody or something said it. |
| **Intelligence Graph** | **What we did about it.** Conclusions GeniOS reached, cards it sent, and what happened next. |

## 2. ⛔ The one test that separates them

> **"Can you point at the sentence that says this?"**

**Yes** → Evidence Graph. **No, we worked it out** → Intelligence Graph.

That test is not a style preference. It is enforceable: every Evidence Graph row is required to
have a `graph_source_refs` entry carrying an `event_id` and a character span. **A row that cannot
name its sentence cannot be written there.**

---

## 3. Worked examples — which graph, and why

| the claim | graph | why |
|---|---|---|
| *Acme's deal stage is `negotiation`* | **Evidence** | the CRM field says it. Rank R2, has a receipt |
| *John's email is john@acme.io* | **Evidence** | the message header says it |
| *John works at Acme* | **Evidence** | derived from the domain — still traceable to a source |
| *There was a meeting on Tuesday with 4 people* | **Evidence** | the calendar says it |
| *The last reply was from them, 9 days ago* | **Evidence** | measured off real messages |
| **⛔ *This deal is at risk*** | **Intelligence** | **nobody said this.** We concluded it from silence + stage + days |
| **⛔ *You should chase Acme today*** | **Intelligence** | a recommendation. No source contains it |
| *We sent Rohit a card about Acme on Monday* | **Intelligence** | a fact about **us**, not about the world |
| *Rohit ignored that card* | **Intelligence** | an outcome of our own action |
| *Rohit said "stop telling me about Acme"* | **⚠️ both** | he **said** it → Evidence. What we do about it → Intelligence |

### 3.1 · The hard case, and how the test resolves it

**"John is the decision maker."**

| how we know | graph |
|---|---|
| John wrote *"I'll sign it this week"* | **Evidence** — point at the sentence |
| John attended every meeting and nobody else replied | **Intelligence** — that is a conclusion, not a quote |

**Same sentence on the card. Two different graphs, depending on where it came from.** And the card
must say which — *"John said he will sign"* is a far stronger claim than *"John appears to be the
decision maker"*, and a user who cannot tell them apart will eventually be burned by the second one
and stop trusting the first.

---

## 4. When each is USED

### Evidence Graph

| | |
|---|---|
| **written** | every time an email, meeting, or document arrives — **synchronously, per event** |
| **read** | every sweep, by the 9 correlators, to build situations |
| **read** | when a card must show *why* — the receipt behind the claim |
| **read** | *"what did we know on 12 March?"* — audit, security review, replay |

### Intelligence Graph

| | |
|---|---|
| **written** | a situation is produced · a decision is made · a card is delivered · an outcome lands |
| **read** | ⛔ **before reasoning** — *"have we been here before? what did we say? did it work?"* |
| **read** | when the user says *"stop telling me this"* — the mute needs something to attach to |
| **read** | to measure the product — *how many of our decisions actually led anywhere* |

---

## 5. ⛔ When each is NOT used — this is the important half

### The Evidence Graph is NEVER used for

| | why |
|---|---|
| storing anything GeniOS concluded | it would get an `authority_rank` and start **competing with a CRM** on the same ladder |
| anything without a source | the receipt requirement is the whole value; one exception ends it |
| ranking, scoring, prioritising | those are judgements. **The graph describes; it does not decide** |

### The Intelligence Graph is NEVER used for

| | why |
|---|---|
| answering *"what is Acme's deal stage?"* | that is a fact. Asking our own opinion for it is how a guess becomes a record |
| being shown to the user **as evidence** | our conclusion is not evidence for our conclusion |
| ⛔ **feeding itself back as a fact** | **the single most dangerous move in the design** — §6 |

## 6. ⛔ Why the wall between them has to be a wall

Suppose *"this deal is at risk"* gets written into the Evidence Graph as a `graph_fact`. Three
things break immediately, and all three are silent:

**1 · It gets an authority rank.** Now our guess sits on the same R1–R4 ladder as a CRM field. A
later rank-2 source that disagrees opens a `discrepancy` against **our own opinion**, as if two
sources were in conflict. They are not. One of them is us.

**2 · `noop` counts it as corroboration.** The Evidence Graph treats a repeated value as
independent confirmation and climbs the ladder **60 → 85 → 100**. So the same model, reaching the
same conclusion twice, reads as **two independent sources agreeing** — and confidence rises on
nothing at all. This is the worst failure in the whole design, because the number goes **up** and
looks healthier.

**3 · Replay stops being an audit.** Once a conclusion and a fact live in the same table with the
same shape, no later reader can separate **what a source said** from **what a model guessed.** The
receipt discipline is spent, permanently, and no migration recovers it — the provenance was never
recorded.

**This is `Observation ≠ Inference ≠ Hypothesis`, enforced by two stores rather than one flag —
because a flag can be forgotten on one write path, and a table cannot.**

---

## 7. Why each one is needed — what breaks without it

### Without the Evidence Graph

| | |
|---|---|
| **No situation can exist at all** | a situation is three emails, a meeting and a silence **seen together**. Seeing together is correlation, and correlation needs a graph |
| **Every claim is unverifiable** | a card says *"Acme is at risk"* and cannot show one line of why |
| **No audit is possible** | *"what did you know in March?"* — the first question every enterprise security review asks |

### Without the Intelligence Graph

| | |
|---|---|
| **Every sweep is the first sweep** | measured: `prior_decision` appears **0 times** in the entire engine |
| **The same card goes out four times** | nothing in the pipeline can see that three already went |
| ***"Stop telling me this"* has nowhere to live** | a mute needs a decision to attach to, and decisions are not addressable |
| ⛔ **You cannot tell whether GeniOS is working** | no outcome is joined to the decision that caused it, so *"did our advice help?"* is unanswerable |

**That last one is the founder's problem, not an engineer's.** Today there is no query that answers
*"of the decisions we made last month, how many led to anything."* The data exists in
`execution_outcomes` — with 7 terminal labels, `seconds_to_close` and `progress_bp` — and it does
not join back to a situation, so it can be counted but never explained.

---

## 8. How each one gets built

### Evidence Graph — already built, runs on every event

```
1. find_or_create_node()   identity by canonical_key (acme.io), not by hashing content
2. fact_write_action()     one pure function → insert | noop | historical | discrepancy | supersede
3. graph_source_refs       the receipt: event_id + {span, text, page, bbox}
4. bump_version()          one counter per org
```

Reading is one predicate, half-open: `valid_from <= T and (valid_to is null or valid_to > T)`.
Nothing is ever deleted — it is closed.

### Intelligence Graph — the same machinery, three rules changed

```
1. identity        (situation_id, slice_digest)   ← 0183 ALREADY has this unique key
2. write action    insert | noop | restated | reversed | expired
3. receipt         the context slice itself       ← 0183 ALREADY stores it
```

**The three changed rules, and why each had to change:**

| | Evidence | Intelligence | because |
|---|---|---|---|
| **conflict** | authority rank **R1–R4** | **recency of the slice** | ⛔ we have no rank over ourselves. Two GeniOS readings are both GeniOS. What decides is **which one saw more** |
| **lapsing** | impossible — a fact needs a source to contradict it | **`expired`** | a conclusion goes stale on its own. *"An interpretation that never expires is not an interpretation"* |
| **repetition** | corroboration by **source** | corroboration by **slice** | the same conclusion from a **different** slice is real confirmation; from the same slice it is nothing |

### What is already there

| | |
|---|---|
| `context_situations` | the situation, with `anchor_node_id` **already pointing into the Evidence Graph** |
| `situation_interpretations` (0183) | one reading per (situation, slice), **with the slice**, `outcome`, `valid_until` |
| `execution_outcomes` | `decision_hash`, 7 terminal labels, `seconds_to_close`, `progress_bp` |
| `reasoning_evidence_id_map` (0117) | the bridge from a decision's evidence back into the Evidence Graph |

**Four tables holding the right data, with zero edges between them.** The work is not collecting the
information. It is linking it and reading it back.

---

## 9. One scenario, both graphs, five days

| | **Evidence Graph** | **Intelligence Graph** |
|---|---|---|
| **Mon** 3 emails + 1 meeting | nodes: person, company, deal, thread · edges: `works_at`, `attended` · facts: `deal.stage='negotiation'` (R2), `ball_in_court='them'` · **4 receipts** | — |
| **Mon** sweep | correlators group → producer emits a deal situation → **BSO** | `situation` node opens |
| **Mon** reasoner | — | reads the slice → concludes **"chase"** → `insert`, valid until Thu |
| **Mon** card sent | — | `delivery` node, `delivered_as` edge |
| **Tue** nothing changes | nothing written | `noop` — same slice. **Nothing is paid for.** |
| **Wed** CRM also says `negotiation` | `noop` = **corroboration**. `src_count` 1→2, confidence **60→85** | — |
| **Wed** user ignores the card | — | `outcome` node: `expired_untouched` |
| **Thu** a reply arrives | `ball_in_court` them→us: **`supersede`**, old row closed at now() | slice changed → new reading → **"no chase"** → `reversed`, `supersedes` edge |
| **Thu** sweep | correlators read it | ⛔ **correlators read this too** — the situation now carries *"chased once, ignored"* |
| **Thu** the card | — | ⛔ **not sent again** — not because a rule forbade it, but because **the correlator could see the first one** |

**Today, the last three rows do not happen.** Every Evidence column above is real and running. The
Intelligence column is four tables that never link, and that nothing reads back.
