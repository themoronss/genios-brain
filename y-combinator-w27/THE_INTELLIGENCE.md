# The intelligence, produced

**Tenant:** `org_e97e86f858ad48b2bbf64b8a` (Rohit Swerashi) · 9 Sep 2026
**Method:** the shipped `y-combinator-w27` functions, imported and run against the live graph.
**Writes:** none. The session is opened with `default_transaction_read_only=on`, so Postgres
itself refuses a write — the real reading functions could not persist anything if they tried.
No LLM was called and no API budget was spent.

> **What this is and is not.** These are the *actual* functions — `read_awaiting_response`,
> `absence_receipt_event_ids`, `gather_l1_signals_for_events`, `substantive`, `_ASKS`,
> `quoted_regions` — run over the real rows. It is not a pipeline run: nothing was re-extracted,
> so L1's numbers are the shipped guards replayed over the 395 signals already stored, and the
> ranking below is the L1 receipt importance, before L2's composition modifiers and before L4
> ranks or L5.2 renders. **The card headlines and templates are untouched — those are L5.2 and
> deliberately out of scope for this pass.** Scripts and raw output are in `replay/`.

---

## Layer 1 — 395 stored signals, through the shipped guards

| | |
|---|---|
| refused as **reply history** | **23** |
| refused as a **thin receipt** | **8** |
| survive | **364** (92%) |

The refusals, top by importance:

```
  4560 bp  financial_obligation   'On Mon, 3 Aug 2026 at 08:00, Mr Rohit Swerashi wrote:'
  4560 bp  financial_obligation   'On Tue, 28 Jul 2026 at 12:39, Mr Rohit Swerashi wrote:'
  4560 bp  financial_obligation   'On Sat, 8 Aug 2026 at 14:22, Manik Pasricha wrote:'
  4240 bp  financial_obligation   'On Tue, 24 Jun 2025 at 11:37, Surge wrote:'
  3960 bp  financial_obligation   'On Thu, 16 Jul 2026 at 22:40, Aditya Dwivedi wrote:'
  3760 bp  deadline_stated        'On Tue, 28 Jul 2026 at 12:39, Mr Rohit Swerashi wrote:'

  3520 bp  financial_obligation   'Wed, 12 Aug 2026, 22:58'
  3520 bp  financial_obligation   'Wed 5 Aug 2026 2:15pm - 2:45pm (IST)'
  1240 bp  relationship_change    'Hii Vatsal,'
   880 bp  relationship_change    'Hi Rohit,'
   880 bp  relationship_change    'Hi Rohit and Boardy,'
```

**The two highest `financial_obligation` signals on the tenant were reply-attribution lines.**
They are gone. `'Hi Rohit,'` is no longer a relationship change.

92% survive, which is the number that matters in the other direction: this is a scalpel, not a
cull.

---

## Layer 2 — the readings, run on the live graph

| | Before | After |
|---|---|---|
| `awaiting_response` findings | 41 | **20** |
| nodes we had actually **asked** | 1 | **19** |
| absence situations carrying a real L1 bundle | **0 of 84** | **81 of 84** |
| importance spread on those situations | 4000 flat, **1 distinct value** | **880–4560 bp, 30 distinct values** |

That last row is the whole thing. Before, every absence situation in the tenant carried exactly
`4000` — the `DEFAULT_IMPORTANCE_BP` fallback — so a 50-day silence from a fund and a 2-day
silence from a newsletter were **literally the same number** and could not be ordered. They can
now be ordered.

Three situations still carry no receipt. Those are the `commitment_overdue` anchors, which reach
only a `company` node and have no message path. They stay held, honestly.

---

## The feed

`awaiting_response`, ranked by the receipt each one now carries:

| # | bp | Days | Follow-ups | Counterparty |
|---|---|---|---|---|
| 1 | 4560 | 28 | 0 | **Manik Pasricha** (Titan Capital) |
| 2 | 4560 | 28 | 0 | **vidushi@peakxv.com** |
| 3 | 4560 | 28 | 0 | **shivam@together.fund** |
| 4 | 4240 | 28 | 0 | **apply@surgeahead.com** |
| 5 | 4160 | 42 | 1 | tripathihk2014@gmail.com |
| 6 | 3920 | 28 | 0 | **harshita@peakxv.com** |
| 7 | 3920 | 28 | 0 | **piyush@3one4capital.com** |
| 8 | 3840 | 28 | 2 | adityad@iima.ac.in |
| 9 | 3600 | 27 | 1 | boardy@boardy.ai |
| 10 | 3600 | 13 | 0 | applications.initiate@hub71.com |
| 11 | 3520 | 28 | 1 | **team@zfellows.com** |
| 12 | 3520 | 22 | 1 | support@bharatkesuperfounders.com |
| 13 | 3520 | 13 | 5 | theresa.hoffmann@antler.co |
| 14 | 3400 | 50 | 0 | rohit@crescerelabs.com |
| 15 | 2440 | 28 | 0 | **madison@afore.vc** |
| 16 | 1940 | 28 | 0 | **siddhant@neon.fund** |
| 17 | 1920 | 28 | 0 | **joseph@afore.vc** |
| 18 | 1720 | 47 | 1 | notification@accubate.app |
| 19 | 1600 | 46 | 1 | vatsa@valiron.co |
| 20 | 1600 | 46 | 1 | Leslie Omonzane |

And separately, of these twenty, **19 nodes are now known to have been asked something** — the
flag that separates *"we are waiting on an answer we requested"* from *"we just have not written
lately."* It was set on exactly one node before.

### The same tenant, before

| # | Score | Headline |
|---|---|---|
| 1 | **63, critical** | *Deliver fundraising opportunities to sanchiconnect.tech NOW* |
| 2 | 50 | *Deliver fundraising opportunities to healthcare leaders* |
| 3 | 50 | *Deliver mentorship guidance from expert mentors now* |
| … | | 12 more, 6 of them the founder's own promises he never made |

Not one of the twenty counterparties above appeared anywhere in that feed.

---

## Layer 3 — activation gating, measured on the 381 stored packages

Activated domains: `['admin']`.

| Pack | Capability slots before | After |
|---|---|---|
| `sales` | **1306** | **0** |
| `customer_support` | **594** | **0** |
| `admin` | 311 | **311** |

**71 of 381 packages survive the filter.** 1900 capability slots of sales and customer-support
expertise stop being compiled for a founder's fundraising inbox — and with them goes the source
of Layer 4's ballot, where 270 of 512 candidates were sales plays holding the top of the utility
table.

Every `admin` slot is untouched. The filter removes what was never this tenant's, and nothing
else.

---

## What this does and does not settle

**Settled.** L1's guards refuse the right 31 of 395 and keep the other 364. L2 produces one
finding per conversation instead of two, knows which counterparties it actually asked, and can
finally rank an absence. L3 compiles only what the tenant switched on.

**Not settled, and it needs a real pipeline run.** These functions were run over the graph as it
stands. A live sweep would re-extract with the L1 guards in place, which changes which signals
exist, which changes the composition, which changes the final `importance_bp` and the admission
decision. **The numbers above are the direction and the shape, measured; they are not the
post-sweep truth.**

**Not touched at all.** L5.2 — the headline that discards the `situation` field, the templated
`do_nothing_consequence` and `why_now`, the four cards with a NULL situation, the two builders
that disagree about `business_subject`. Every one of those is still there, and every one of them
sits between this intelligence and what a person actually reads.
