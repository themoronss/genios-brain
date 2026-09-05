# Layer 1 Plan — Crosscheck and Corrections

**Performed:** 2026-09-03, before commit
**Method:** the Layer 1 v2 plan audited against four independent reference points, with
every finding verified against code rather than against the plan's own claims.

| # | Reference | Question asked |
|---|---|---|
| R1 | **GeniOS Globe** (spec of record) | is every specified L1 component accounted for? |
| R2 | **Customer expectation** (founder bar, \$100/mo) | can the plan actually serve it? |
| R3 | **Our design conversation** | is the agreed doctrine faithfully captured? |
| R4 | **The plan against itself** | is it internally consistent and implementable? |

**Result: 9 findings. 2 critical, both fixed. 7 minor, all fixed.**

---

## R1 — vs Globe: component coverage

All **48** Globe L1 components are accounted for. Two are deliberately dropped with a
written reason; none were lost by accident.

| Globe component | Where it went in v2 |
|---|---|
| L1.3a Entity Extraction | -> L1.4 semantic (`entity_mentions`) |
| L1.3a Relationship Extraction | -> L1.4 semantic (`relationships`) |
| L1.3a **Embedding Generation** | **dropped — MAP B, with reason and revisit condition** |
| L1.3b Entity Linking | -> L1.5.4 Entity Canonicalizer (provisional; L2 authoritative) |
| L1.5 **Vector index** | **dropped — MAP B** |
| all others | 1:1 into the 7 v2 groups |

### 🔴 P-01 — CRITICAL — the structured lane was missing

**Finding.** The plan's four-stage spine routed *every* event through S2 semantic
extraction. But `capture/structured/registry.py` registers four mappings —
`hubspot.deal.v1`, `stripe.subscription.v1`, `gcal.event.v1`,
`postgres.customer_accounts.v1` — and `gate/gate.py` S1.5 short-circuits structured
events past extraction entirely. **No component in the seven groups owned this path.**

**Why it is critical, and not a tidy-up.** A HubSpot deal has `amount` as a typed field.
Asking a model to "extract" it is waste *and* a hallucination risk — the model can be
wrong; the column cannot. More importantly: **billing and product-usage data are
structured**, and those are exactly the sources the founder's churn-cohort, LTV-lookalike
and pricing-cohort questions depend on. A plan describing only the unstructured path
would have left the highest-value data GeniOS will ever ingest with no route through
Layer 1.

**Fix applied.**
- `00-Overview` — new section **"The structured bypass"**: structured events run
  `S1 -> L1.3.9 mapper -> S3 -> S4`, skipping S2. Includes a route/confidence/authority
  table per source class.
- `03-Group-L1.3` — new component **L1.3.9 Structured Mapper (ALG-21)**, 3 units, with a
  full spec and reverse prompt. Emits the same `ExtractionResult` shape from a registered
  mapping; `field_confidence = 10000` (a typed field is not a guess); authority rank 4;
  synthesized evidence spans with `verified=True`.
- `09-Build-Order` — added to W2; G2 now asserts **zero LLM calls** on a structured
  fixture, and that a mapping-sourced fact and a model-sourced fact with identical inputs
  produce an identical `importance_bp`.
- New algorithm **ALG-21** registered in MAP D.

---

## R2 — vs the customer bar

Walked each of the founder's stated expectations against the plan.

| Expectation | Served by | Verdict |
|---|---|---|
| E2 discovers patterns nobody named | L1.4.5 Open Lane | ✅ L1's contribution: stop destroying the raw material |
| E3 ranked by revenue impact | L1.6.7 `importance_bp` (ALG-17) | ✅ this is the L4 unlock |
| E5 explainable | evidence spans + `importance_components` | ✅ |
| E2 churn cohorts / LTV lookalikes / pricing cohorts | billing + usage sources | ⚠️ **depended on P-01** — now fixed |
| E4 near-zero founder work | L1.1 connector priority, P0 = HubSpot expansion | ✅ |
| E1 agent pre-action consult | not L1 (L5 / agent API) | out of scope, correctly |
| E6 influenced-revenue proof | L1 supplies `Money` + evidence; attribution is L6 | partial, correctly scoped |

### 🔴 P-02 — CRITICAL — conflict detection could not catch the founder's own example

**Finding.** L1.5.5 specified grouping as *"group all claims across **the event's**
extractions"*. But `capture/connectors/composio.py:383` states plainly:

> *"One Gmail message → `[email_message]` + one `[email_attachment]` per file."*

**They are separate events.** So the \$84K-in-email vs \$74K-in-signed-PDF case — the
exact scenario raised in conversation and the reason the component exists — would have
landed in two different groups and **never been compared.** The unit would have shipped,
passed its own tests, and silently failed the one case it was built for.

**Fix applied.**
- `05-Group-L1.5` — new component **L1.5.0 Claim Group Assembler**, 2 units:
  - **ALG-22 `subject_key` derivation** (also closes P-03 below)
  - **ALG-23 claim group assembly** — groups by `thread_group_key`, walking
    `parent_object_id` upward: attachment → email → thread. Both links are **already
    populated** in the data (`composio.py:499` and `:452`), so this is a traversal, not
    new ingestion work.
- L1.5.5 step 1 rewritten to consume L1.5.0's groups, with the cross-event requirement
  called out inline.
- `09-Build-Order` — G5 now requires the fixture to present the two claims **as separate
  events**, and states why: *"a fixture that puts both claims in one event passes for the
  wrong reason and would hide the defect this gate exists to catch."*

---

## R3 — vs our design conversation

Doctrine faithfully captured. Verified point by point:

| Agreed | In the plan |
|---|---|
| L1 = Hybrid Intelligence Extraction Layer | ✅ doc 00 §1 |
| Deterministic → LLM semantic → deterministic validation → qualified signal | ✅ doc 00 §2, the four-stage spine |
| LLM heavy at L1, light at L2, zero at L3, ambiguity-only at L4 | ✅ doc 00 §3 + README |
| The model describes, never scores | ✅ stage law + structural enforcement (importance is not in the extraction schema) |
| LLM output is not final truth: evidence → validation → conflict → signal | ✅ S3 entire, L1.5.1 + L1.5.5 |
| The \$84K vs \$74K worked case | ✅ **and P-02 fixed so it actually works** |
| "Best of the best details" | ✅ Open Lane + vocabulary decoupled from rules |
| Reverse engineering: units → components → groups → layer | ✅ doc 09, ten waves |
| Reverse prompts for the coding agent | ✅ 13 blocks |

### 🟡 P-04 — profile coverage overstated

The W4 acceptance gate required *"30 messages spanning all 5 profiles"* — but `chat`
has no source (Slack is priority P4, unbuilt) and `transcript` has none (audio is
missing, L1.3.4-U3). The gate was unsatisfiable and would have blocked W4 on unrelated
connector work.

**Fixed.** Doc 04 now carries an honest coverage table: golden corpus is 15 email + 10
document + 5 CRM note. `chat` and `transcript` are written and unit-tested against
synthetic fixtures so the code path exists, but are explicitly **not part of the W4 gate**
and join when their connectors land.

---

## R4 — the plan against itself

### 🟡 P-03 — `subject_key` used but never defined

Referenced by L1.5.5 (conflict grouping) and L1.6.9 (supersession) with no definition —
making both unimplementable. **Fixed:** ALG-22, a five-rule ordered cascade in L1.5.0-U1,
deterministic and stable across runs.

### 🟡 P-05 — four components had no unit specs

L1.6.2 Signal Normalizer, L1.6.4 Source Analyzer, L1.6.5 Business Relevance and L1.6.6
Domain Mapping appeared in the component map with unit counts but had no written spec.
For a document whose purpose is to be handed to a coding agent, a row in a table is not a
specification. **Fixed:** all four now carry full specs with HOW, LLM decision, failure
modes and acceptance.

### 🟡 P-06 — LLM-5 declared in MAP A but never specified

The fifth LLM site (ambiguous business relevance) was in the map with no trigger
condition and no prompt. **Fixed** in L1.6.5-U1: an explicit rules-first cascade (known
counterparty, `internal_kind`, structured source, bulk headers, service account) with the
model seeing only the ambiguous remainder, plus a budget guard — if the ambiguous share
exceeds 10% for an org, that is a graph-coverage problem, so **alert rather than spend**.

### 🟡 P-07 — component count

Verified: 16 + 6 + 9 + 10 + 9 + 10 + 5 = **65** components after the two additions
(was 63). MAP D now lists **23** algorithms (was 20).

### 🟡 P-08 — waves for "already exists" components

L1.3.1/3.2/3.3/3.7 were marked "exists" with no wave. They still need regression tests so
a refactor cannot quietly weaken them. Covered by the **"What must not regress"**
checklist in doc 09 (10 items, each citing file:line or a commit hash).

---

## Summary of changes made

| Doc | Change |
|---|---|
| `00-Overview-and-Doctrine` | + "The structured bypass" section; + ALG-21/22/23 in MAP D |
| `03-Group-L1.3` | + **L1.3.9 Structured Mapper**, 3 units, full spec + reverse prompt |
| `04-Group-L1.4` | golden-corpus profile coverage made honest |
| `05-Group-L1.5` | + **L1.5.0 Claim Group Assembler**, 2 units, full spec + reverse prompt; L1.5.5 grouping rewritten |
| `06-Group-L1.6` | + 4 full unit specs (Normalizer, Source Analyzer, Business Relevance, Domain Mapping) |
| `09-Build-Order` | L1.3.9 into W2; L1.5.0 into W5; G2 and G5 assertions strengthened |

---

## What this crosscheck did NOT find

Recorded so the next reviewer knows what was already checked:

- **No missing Globe components.** All 48 map to a v2 home or a documented drop.
- **No contradiction between the plan and the agreed doctrine.**
- **No float, clock or LLM leakage** in any group the plan marks deterministic — the
  three CI greps in doc 05 and doc 06 enforce it.
- **No global feature flag** anywhere in the plan; activation is the per-tenant
  `l1_v2_activation` table throughout.
- **Numbering is consistent** — every unit id referenced in doc 09 and doc 10 resolves to
  a spec in docs 01–08.

## Honest limitation

This is a **plan review, not an implementation review.** It verifies that the plan is
complete, internally consistent, faithful to the spec and to the agreed doctrine, and
that its claims about the current codebase are true at commit `b4d4d15`. It cannot verify
that the plan **works** — that is what acceptance gates G0–G10 are for, and gate **G7**
(the `importance_bp` distribution check) is the one that will tell you whether the
central bet paid off.
