# P3 · Plane D · 05 · How it will be done at production level

**Owner:** Harsh and the agents Harsh assigns, for the code. A named reviewer for the knowledge: the founder for the Founder Office during the design-partner stage, and GeniOS's named domain reviewers once the corpus serves many tenants (§4). Rohit approves each domain's activation per tenant and the decisions in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md).
**The specification is [07](07-THE-PLANE-D-SPEC.md).** This file says how it reaches production: where it lives, the order, the switches, the migration and the operations.
**Rule:** each step first passes in the notebook ([04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md)).
**Architecture rules that bind every step** (GeniOS-008 `01-RULES`):
- beside, never instead of;
- contracts first;
- switch one situation type at a time;
- the ratchet only shrinks;
- every item cites 00-ARCHITECTURE.

---

## 1 · Where the knowledge lives

- **The YAML is the source of truth** (`Domain Expertise/`), with one schema for every domain (`_schema/`, `_tools/validate.py`). It changes only through a reviewed pull request.
- **The pack is compiled from it** by the existing compiler (`genios_engine/packs/compiler/`):
  - the catalog, the index by kind, stage and event (P3-1), and the content hash;
  - written once per deploy as an immutable file in object storage, named by its hash;
  - loaded into in-memory registries by each process.

  It is never edited by hand, and never by a model.
- **No table holds the units.** Postgres holds only what a tenant's runs produce:
  - `expertise_packages`: the package each judgment received (it exists, with 100 rows in the first week);
  - the activation rows (§3);
  - the usage rollup (§8).
- **Company facts never enter the corpus.** They live in the brains, in Postgres (P2 §8), and reach a unit through its adaptation points (07 §10).

## 2 · One bridge for every reasoning path

- **One module**, `packs/compiler/expertise_view.py`, replaces the per-path renderers: the expert dossier's playbook block, `playbook_reader`'s claims, and the notebook's `playbook_text`.
- **It renders the package** the compiler built for the situation (P3-7), selected by the situation's kind, stage and events (P3-1, P3-8).
- **It renders whole** (P3-2): every step of every move, every rule with its conditions, the review labels, and the ids the model must cite (P4-5).
- **It keeps to a budget** (start: 6,000 tokens of expertise per judgment), and every cut is counted in the text.
- **It renders the four brains as four labelled blocks,** each entry with its state, and the person's confirmed preferences; no brain entry is rendered as a unit.
- **When nothing applies, it says so,** by kind, stage and event, and the lane is capped at investigation or observation: no recommendation without knowledge behind it.

## 3 · Activation per tenant and per department

- **Domains are switched per tenant** by rows (`platform/l3_activation`), never by a global flag. The plan sets which domains a tenant is entitled to; each row's state, **live**, **shadow** or **off**, lies within it, and the row holds the pack pointer for that domain (P3-17, §7).
- **Defaults by kind of tenant,** with no hand step:
  - **founder:** the Founder Office and Admin together, shown as "Admin › Founder office" (D-P3-5). Admin's founder units (follow-up, renewals, filings, registrations, commitments, correspondence) are selected through the index, whichever domain wrote them;
  - **team:** each department's domain comes on with that department.
- **The bar** (D-P3-8): a domain goes **live** for a tenant only at Reliable, with its six tests shown and a shadow report on record. Below the bar it runs in **shadow**: receipts, no cards.
- **An off domain contributes facts, never judgment** (Atlas: entitlement first).
- **Rollback** is one row: the domain back to shadow or off for that tenant. Nothing else is undone.

## 4 · Review as a workflow, not a hope

- **Who reviews:**
  - **The corpus is shared by every tenant,** so a review is a product act, not a tenant's. During the design-partner stage, the founder reviews the Founder Office line by line (`06` D45), and Harsh reviews Admin.
  - At scale, GeniOS's **named domain reviewers** own each domain. A customer never edits the corpus. A customer's "not how we work" goes to that customer's brains (07 §10), and becomes a corpus review item only when it recurs across companies (07 §12).
- **The review sheet:** one per capability, as a page or a pull request. The reviewer accepts, edits or rejects each line, beside its sources and its cases.
- **The one act:** the reviewer's acceptance records the name, the date and the content hash, and switches the unit to `stable` (P3-12). The validator refuses `stable` without all three, matching the current bytes.
- **The pull request runs** the lint, the cases and the shadow comparison (§5, §7) before it can merge.
- **A review item from learning** is a draft unit diff, opened as a pull request from a bot branch that no code merges (07 §12). Across companies it comes only from tenants that opted in, redacted to counts, unit ids and structure (D-P3-13).
- **A rejected line** becomes `deprecated` with its reason, and leaves the pack.
- **An unreviewed line** is shown to the model labelled. A card resting mainly on unreviewed knowledge says so, and is capped.
- **The daily health report lists:**
  - what is waiting for review, with the reviewer named;
  - the units in the half-state (it must be 0);
  - the units whose `review_by` falls within 30 days.

## 5 · Knowledge is tested like code

**CI runs on every change** to the YAML, the compiler or the bridge:
- the schema and D-Unit lint, and the vocabulary check (every `facts_required` path has a writer);
- the 40 routing cases;
- every unit's must-cite, must-not-cite, negative and outcome cases (P3-6), over recorded judgments, so CI spends nothing on models;
- the guards D-1 to D-26 (07 §15); CI fails if a guard listed there has no test.

**What fails the build:**
- a unit that fires where it must not, or stays silent where it must speak;
- a live unit missing a contract field with no stated reason;
- a rejected unit that can still be rendered.

**Before a new pack goes live,** it runs in shadow (§7).

## 6 · Migration: from the compiled lane to the model's path

1. **Beside, not instead.** The compiler builds a package for every situation L2 judges (P3-7), while the compiled lane keeps rendering its templates as today.
2. **The model's paths switch to the bridge** (P3-2) per tenant, behind the tenant's loop row (P1 §4).
3. **The compiled lane retires per situation type and per tenant,** only after the parity gate on that tenant's golden cases (P1 §4). The ratchet only shrinks.
4. **The old renderers are deleted** once no path calls them: `playbook_reader`'s claims, the dossier's playbook block, `nb/common.playbook_text`.
5. **The corpus migrates to the D-Unit contract unit by unit** (D-P3-6). The Founder Office and Admin's founder units go first, then each department before it goes live anywhere.
6. **The 165 half-state units** are re-read and switched on by their reviewer (D-P3-7) before P3-12's gate is switched on, so the gate never hides knowledge that was approved.

## 7 · Versions, pins, shadow, rollback

- **Every unit has a semver, and every pack a content hash.** There is one pack per domain and a cross-domain index with its own hash; a domain is released and rolled back on its own.
- **Every judgment records** the pack hash, the unit versions it was given and the brain snapshot (P2 §4.7).
- **A replay** loads the exact pack from object storage by its hash. A pack stays kept while any retained judgment cites it.
- **Shadow:** a new pack runs beside the live one on the acceptance set and the golden cases. It goes live only if it is at least as good on must-cite, must-not-cite and the ideal cards. The comparison is written to the log.
- **Re-judging after a deploy** follows the versions of the units each judgment cited, not the pack hash: an unrelated change re-judges nothing.
- **The pointer per tenant per domain** records the hash, `activated_at` and `activated_by`; L4's input gate reads it before planning an execution.
- **Rollback** is the pointer moved back, per tenant and per domain, logged. It changes no stored judgment; the next judgments use the old pack.

## 8 · Monitoring: does the knowledge reach, and does it earn its place?

**Per tenant per day,** in the daily health row:
- **coverage:** the share of judged situations with at least one reviewed unit behind them (target at least 85% for a founder tenant), and with any unit at all;
- packages per judgment (must be 1), units per package, and cuts by the budget;
- the share of unreviewed units in packages;
- the half-state count (must be 0) and units past `review_by`;
- fact paths named by no unit, and paths named with no writer (must be 0).

**Per unit, per week,** in a small rollup table (`expertise_unit_stats`: tenant, unit, version, week), built nightly from `expertise_packages` and the judgments' citations:
- selected, cited, conditions failed (P4-5), cut by the budget;
- the founder's verdicts on the cards resting on it (P5, L6);
- outcomes when its advice was followed.

A unit never selected for 90 days, or always contradicted, goes to the review queue.

**The gap backlog and the uncovered report** (07 §11): every "No authored knowledge" line counted by kind, stage and event, with the top gaps weekly; they set the authoring order. Also weekly: reviewed, case-backed units, and review minutes per unit.

**Alerts:**
- a judgment without its package;
- a rejected unit rendered;
- the half-state count above 0;
- coverage falling by more than 10 points in a day;
- a pack change that makes the acceptance set worse.

## 9 · Size and cost

- **The pack:** 1,489 YAML files, 13 MB on disk today. Compiled, it loads in memory in each process.
- **The expertise block:** a budget per judgment (start: 6,000 tokens), measured from the first day. Today the founder's full investor and programme knowledge renders in about 6,000 characters. Selecting by kind, stage and event keeps the block to the units that apply.
- **Cost:** the block sits in the cached part of the prompt where the same units repeat across situations. Its tokens are counted in P1's money report (P1 05 §6), per tenant.
- **Authoring cost** is one-time per unit: drafting with sources is a few dollars per capability. Reviewing is people's time, planned per capability (20–40 minutes).

## 10 · Authoring and localisation at scale

- **The pipeline for every new unit:**
  1. the authoring brief;
  2. an AI draft with a source for every line;
  3. the lint;
  4. its cases;
  5. a named review;
  6. a shadow run;
  7. live.
- **A new domain is content only:** the meta-schema, its golden cases, a review and a shadow run. No code.
- **Localisation:** units about law, tax, compliance and programmes carry `jurisdiction`, `valid_from` and `review_by` (P3-19). The compiler selects by the tenant's jurisdiction. A `review_by` calendar feeds the review queue. India first; another country is a set of units, never a fork of the corpus.

## 11 · Safety, privacy and limits

- **No company facts or personal data in the corpus.** A lint checks for names, amounts and addresses (D-8). Examples are synthetic; cases refer to copies by id.
- **Sources are cited and quoted briefly,** within their licences.
- **Every unit states its authority boundary.** A unit can never move a `human_only` act (a send, a payment, a signature) into GeniOS's hands; P5's delegation rules apply.
- **Legal, tax and compliance units** are labelled "general guidance, not legal advice" wherever a person sees them.

## 12 · Failure modes, and what happens

| Failure | What happens |
|---|---|
| The pack fails to build | The deploy fails in CI; the previous pack stays live |
| A unit's bytes change without a review | Its hash no longer matches: it is unreviewed and labelled until re-reviewed |
| The compiler fails for one situation | The judgment runs, saying "No authored knowledge could be compiled" with the error's id. A receipt is written and an alert raised. It is never silently run without expertise |
| The expertise is over budget | The lowest-ranked units are cut, and every cut is counted in the text |
| A domain's cases start failing | It returns to shadow for new tenants; live tenants get an alert and the reviewer a queue item |
| A unit is found wrong in production | Its reviewer rejects it, a new pack goes out, and the situations whose last judgment cited it are re-judged |
| A unit passes its `review_by` date | It is labelled, and never grounds an authoritative card until re-reviewed |

## 13 · What must never happen

- **A rule shown without its conditions.**
- **A move cut to its first step without the cut being counted.**
- **Knowledge chosen by one key from one domain** while knowledge elsewhere applies.
- **A judgment without its package recorded,** or a package whose pack cannot be replayed.
- **A rejected unit rendered,** or an unreviewed one rendered without its label.
- **A model deciding a review state,** or writing any corpus file.
- **A YAML change that skips its cases.**
- **Company facts or personal data in the corpus.**
- **A domain judging for a tenant** without its activation row and its bar.
- **A unit that instructs a send, a payment or a signature.**
- **A package wider than its situation's audience.**
- **A clock read inside Plane D;** time arrives as `eval_time`.
- **A safety, legal or compliance unit muted** by dismissals.
- **Customer data in the shared corpus,** or a cross-company review item that carries any.
