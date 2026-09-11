# Version 3 Updates

**Status:** active
**Started:** 2026-09-11
**Predecessor:** `../Version 2 Updates/` (the layer-by-layer rebuild plans)

---

## What Version 3 is

Version 1 audited the system as specified. Version 2 wrote the rebuild plan, layer by layer.

**Version 3 is the repair, driven by what the live tenant actually does** — every change below
was motivated by a number measured read-only against `org_e97e…`, not by reading the plan.

The order is **Layer 1 first, completely, before Layer 2**. The reason is in the numbers: the
compiled lane had never produced a single card in the product's life, and every cause traced
back to something Layer 1 or Layer 2 either never wrote or never passed on.

---

## Layer 1 — what was wrong, measured

| Finding | Number |
|---|---|
| Events captured → emitted | 889 → 227 (26%) |
| **Events carrying no domain at all** | **815 of 889 (92%)** |
| Events passing ESQE because the budget ran out | **69**, against 59 that passed on merit |
| Documents parked and never drained | 187 |
| Signal types that have never once fired | **3 of 14** |
| Anything answering "what kind of exchange is this" | **nothing** |

The two structural findings behind those numbers:

**Four keyword tables recognised 8% of a real mailbox.** `fundraising`, `sales`, `support` and
`admin` only match language somebody thought to write down. Most mail is ordinary sentences —
*"can you send that across by Thursday"* — so 92% of events reached Layer 2 with nothing to
select a corpus by, and the one corpus the tenant had activated never got to speak.

**The system classified EVENTS and never the EXCHANGE.** `SignalType` has 14 members and every
one answers *"what business event happened"* — a deadline was stated, a commitment was made.
Nothing answered *"is this a vendor pitch, an interview thread, a receipt."* That is the same
hole that leaves `party.role` at one fact and `thread.objective` at zero across the whole graph.

---

## What Version 3 has changed so far

### 1 · Intent classification — `contracts/intent.py`

A `MessageIntent` record answering **what kind of exchange this is**, carried on every relevance
decision.

**It is deliberately NOT a fifteenth `SignalType`.** That enum is reduced to ONE primary per
event by a fixed precedence, and ranking "promotional" against "escalation" has no right answer
— a promotional email can also state a deadline. A message is BOTH, and that is only expressible
while the two are separate. Intent travels beside the taxonomy, never inside it.

| Axis | Values | Standing |
|---|---|---|
| `category` | automated · promotional · transactional · working · relational · unknown | observed |
| `tone` | neutral · warm · direct · urgent · frustrated · apologetic · unknown | observed |
| `formality` | formal · professional · casual · templated · unknown | observed |
| `motive` | a phrase, or absent | observed |
| `addressed_personally` · `human_authored` · `asks_for_reply` | true · false · **None** | observed |
| `engagement` | high · medium · low · unknown | **judgement** |

Three rules the contract enforces rather than documents:

- **Unknown is a real answer and is never guessed.** Every enum has an `unknown` member and
  every boolean is three-valued. An intent the model could not read arrives absent, because the
  gate treats a missing intent as "do not filter on this" and a wrong one as permission to
  delete somebody's mail.
- **`asks_for_reply is False`, never `not asks_for_reply`.** `None` means the reader could not
  tell, and "could not tell" must never read as "nobody is waiting".
- **Promotional is not noise.** Only machinery that asks nothing of us is. A person is behind a
  vendor pitch and they will follow up; `capture/gate/rules` already records what over-matching
  costs — `support@` and `hello@` are a real small business.

**What is deliberately absent:** "how much respect does this person have for us", "what are
their values", "will this convert". Those are claims about a relationship over time or about the
future. One message cannot carry them, and a field inviting a model to invent them would be a
fact-shaped guess. Engagement is offered as a banded judgement and nothing stronger — three
bands can be argued with, `6,400` cannot.

### 2 · The junk gate reads intent on the call it already makes

`relevance.py` asked one question. It now asks two on the same batched call — **no new LLM
call, no extra spend.** 1,342 calls already run for this tenant.

The prompt-injection defences are untouched: the item text stays fenced, the item number stays
outside the fence, and only the keys the prompt promised are read. A `confidence`, `priority` or
`score` the model volunteers still has no path into the package.

**Every field is independently optional.** A model that answers the business question well and
the category badly has its business answer honoured; an unreadable category degrades to
`unknown` rather than discarding the verdict. A string where a boolean belongs is refused, not
coerced — coercing `"yes"` is how `asks_for_reply` silently becomes true for a whole batch.

The five deterministic rules record `UNREAD`. They read an envelope, not a message, and a header
match must not masquerade as a reading of the exchange.

### 3 · Admin became the collector — the 92%

`admin` was widened to absorb everything a business **operates** on while it is the activated
corpus: money in and out, obligation and governance, people, time and access, place and thing.
Fundraising, sales and support keep their own patterns and are still tested **first**, so
widening admin cannot steal a thread that names a term sheet or a deal.

This is a **staging decision, not a taxonomy.** When a second corpus is activated its terms move
out of this pattern into its own file — a corpus edit, not a deploy.

And a collector for what still matches nothing: an emitted business message with no pattern hit
is filed under `admin` with `source="fallback"`.

**A fallback is not a classification, and `coverage_verdict` ignores it.** `coverage_ready` is
three-valued and `None` means *we never classified this event*; consulting coverage on a
collector hint would turn "we could not tell" into a verdict about whether the tenant has
connected enough systems. A wiring test named that collapse before it happened:

> *"a wiring change that made every event True-or-False by defaulting the unhinted ones would be
> hiding one bug under another."*

It was right, and the fix was to make the collector invisible to coverage rather than to move
the test.

---

## 4 · Intent on the extraction call too

The junk gate reads a subject line in a batch, before anyone has decided a message is worth
reading. The extractor already holds the whole message. Both calls run for every tenant today —
1,342 and 1,413 on the pilot — and only one was being asked what kind of exchange this is.

`MessageIntent.merged_with` folds the two: **field by field, and the richer reading wins only
where it actually spoke.** An `unknown` or a `None` from the fuller read is an absence, not a
correction — a silent extractor never erases what the gate found.

Three things the codebase refused, and was right to:

- **`intent` was already taken**, by something narrower — the SPEECH ACT of one message
  (`inform | request | commit | decide | escalate`), which `esqe/detector` reads to fire
  ESCALATION. So the field is `exchange_intent`.
- **Schema rule S-1 refused a nullable field** — *"an empty list or an empty mapping is how
  'nothing was found' is said here"*. The sentinel was unnecessary: an EMPTY `MessageIntent`
  already merges as a no-op, so silence needs no `None` of its own.
- **Schema rule S-2 refused a field its table had no rule for** — *"extend the validator with the
  field rather than letting the newest field be the unchecked one"*. A single nested record was a
  shape `_shape_of` did not know. It knows one now, kept separate from `MODEL_LIST` because a
  list arriving as an object and an object arriving as a list are opposite mistakes.

And no `evidence` field on the intent, on reflection. Every other claim carries spans because
every other claim is about a PHRASE. Intent is one reading of the whole message, and *"the tone
is warm"* has no quotable span — a field for it would invite a manufactured citation.

---

## Three things I claimed were defects and were not

Recorded because each was measured, asserted, and then withdrawn on evidence. The pattern is the
same every time: a number that looked alarming, and a downstream cost that did not exist.

### `anomaly` never fires — **not a defect**
I reported it had no detector. It has one; I grepped the lowercase string and missed
`SignalType.ANOMALY`. It is a deliberate last resort — `if not out and (...)` — and never fires
because the other thirteen predicates always catch something first. Working as designed.

### `information_conflict` never fires — **not a defect, a doctrine question**
43 conflicts exist on the pilot. All 43 are on `date.value`. The material list is four fields:
`contract.value`, `contract.renewal_date`, `contract.notice_period`, `deal.amount`. So every one
is filtered out.

Whether a **deadline disagreement** is material is a business judgement, not Layer 1's to make in
Python. Referred to Layer 2's situation lifecycle (L2.7.7), where a contested deadline is a
statement about a situation's state.

### `ambiguous_over_budget` — **not a defect**
69 events passed the gate on budget exhaustion against 59 on merit, and I began turning the guard
from a switch into a cap. Two tests pinned the existing behaviour. Checking before overriding
them: **`relevance_bp` is written at `pipeline.py:1114` and read by nobody** — not Layer 2, 3 or
4, not even `contracts/`. A rank-3000 event and a rank-6000 event are treated identically
everywhere downstream, so the guard costs nothing. Reverted.

The real finding underneath is the familiar one: a carefully ranked table — 8000 structured, 6000
a model that read the message, 3000 nobody decided, 500 bulk headers, each with documented
reasoning — **and no consumer.**

---

## 5 · The alias table pointed at a graph that no longer existed

**309 of 364 aliases resolved to a node with no row at any version.** 107 of 116 emails, 87 of 89
person names, 78 of 107 company names, 37 of 52 domains.

Three individually reasonable parts. `node_id` is minted per node. The erasure list cleared
`graph_nodes` and left `graph_aliases` standing. And `record_alias` inserted
`on conflict do nothing`, so a key already present was never revisited. Rebuild a tenant's graph
once and the alias table freezes against the first graph that ever existed.

**This is why `party.role` held one fact and `company.industry` none.** Not an extractor that
could not read them — a subject that could not resolve. `resolve_company_mention("Antler")`
returned a dead id, the caller's live-node check found nothing, and the claim was dropped. The
business-noun lane had been writing into a table where every name pointed at nothing.

Three changes:

- **`record_alias` takes over a dead key.** A key held by a node that no longer exists is
  UNOWNED — there is no claimant to overwrite. A key held by a LIVE node is a real duplicate and
  still refuses, because picking one moves every fact written from that mention onto the wrong
  person. The extra read happens only on the contended path.
- **`prune_dead_aliases` on the heartbeat**, because the takeover is lazy by nature: a person
  nobody writes about twice keeps a dead key for ever. It DELETES rather than repointing —
  guessing which live node inherits a name is the silent re-attribution `resolve_person_name`
  already refuses. Removal leaves the key free for the next real observation.
- **`graph_aliases` joins the erasure list**, before `graph_nodes`, so the state stops being
  created.

---

## Still open in Layer 1

| # | Item | State |
|---|---|---|
| 1 | `escalation` authority half | Both ranks are defined and read at `detector.py:413`, and **neither is ever supplied**. The producer must live where the org chart lives — Layer 5's `org_seats` / `seat_responsibilities` — and Layer 1 may not import it. Not buildable at this layer, and not fakeable: the tenant has **1 seat and 0 responsibilities** |
| 2 | 197 parked events, **none ever attempted** | See below. Deployment, not code |
| 3 | `relevance_bp` has no decision consumer | It IS recorded, on every event's trace row at `pipeline.py:1114`. A diagnostic that an operator can query is doing its job; inventing a gate for it would be adding a consumer to justify a number rather than the other way round. Left as a diagnostic, deliberately |
| 4 | 23 route tests unverified here | They answer `503 no database configured` — `GENIOS_TEST_DATABASE_URL` is unset and no Postgres exists on this machine. Not evidence of a defect, and **not evidence of health**. They cover the qualification control surface, the drops ledger and connector route wiring, and someone with a scratch Postgres should run them |

### On the parked queue — the machinery is right and has never run

197 parked, every one `status = pending` with `refetch_attempts = 0`.

| Reason | Count | What it is |
|---|---|---|
| DOC-02 unsupported | 125 | **`text/calendar` and `application/ics` — calendar invites**, skipped before download by the connector on purpose, because the calendar lane already covers meetings |
| DOC-06 ocr_unavailable | 41 | `image/png` and `image/jpeg`. OCR ships in the image now |
| DOC-05 fetch_failed | 21 | `application/pdf` |
| llm_junk_unconfident | 7 | Human review |
| extraction_parse_failed | 3 | Retryable |

I first reported this as "187 documents parked, drain them". That was wrong twice over. **125 of
them are calendar invites, not documents** — and they are correctly skipped, by a decision the
connector documents. Only 62 are genuinely waiting on a capability that now exists.

And the drain is not missing. `drain_parked`, `refetch_parked_attachments` and `drain_recapture`
are all built, all called from `run_maintenance_sweep`, and all on the heartbeat. Every one of
the 187 document parks carries `object_type = email_attachment`, which is exactly what the
refetch claims, and the claim query handles a NULL `next_attempt_at` correctly.

So the rows are **eligible and untouched**. That is a deployment question — has the sweep run
this code against them — and not one this repository can answer.
