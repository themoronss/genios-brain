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

## Still open in Layer 1

| # | Item | State |
|---|---|---|
| 1 | `escalation` never fires | `prior_recipient_authority_rank` is defined at `detector.py:145`, read at `:413`, and **supplied by nobody**. The thread-parties half is wired |
| 2 | `information_conflict` never fires | `conflicts` **is** passed; ALG-12 produces none for these events. Cause not yet found |
| 3 | `anomaly` never fires | **No detector exists at all** |
| 4 | `ambiguous_over_budget` | 69 events passed the gate because the budget ran out, against 59 on merit. A fail-open that is larger than the merit path |
| 5 | 187 parked documents | OCR now ships in the image; the queue has never been drained |
| 6 | Intent on the extraction call | The junk gate reads a snippet. The extraction call reads the full message and is where `motive`, `tone` and `formality` should be filled |

Items 1–3 are the same shape as everything else found this week: **the detector exists and the
input is never supplied.**
