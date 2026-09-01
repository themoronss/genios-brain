> **Created:** 2026-09-01 · **Status:** 🟢 Active — analysis only, nothing built from this file yet
>
> **Purpose:** What the Admin-Intelligence L2→L5 failure analysis (MD 06) asks for that the shipped
> chain does not already do — separated from the large part of it that is already done — with a
> judgment on which of the remainder is worth building.

## How to read this

MD 06 and the earlier L1–L3 diagnosis overlap heavily. Most of MD 06's *diagnosis* was already
closed by the four passes on `harsh/mvp` (see `L2_L4_INTELLIGENCE_CHAIN.md` and
`INTELLIGENCE_REMAINING.md`). What is new is mostly its **specification** — it asks for a wider
situation taxonomy, a domain router, and an entitlement model that did not appear in the first
document at all.

Everything below is stated as a gap against **shipped code**, not against the earlier plan.

---

## Already done — MD 06's own list

| MD 06 | State |
|---|---|
| §5.3 Interaction reconstruction, follow-up count | `context/waiting.py` |
| §5.4 Intent and objective | `thread.objective`, 13 purposes, outbound leg only |
| §5.5 Temporal and absence | `days_waiting`, `last_heard_days`, `reply_cadence_days` |
| §5.9 Cohort engine | `cohort_outreach_gap`, keyed on objective |
| §5.11 `missing_fields=()` | derived from the domain spec |
| §6.6 / §7.3 Four brains change a decision | organization eliminates, adaptive re-ranks — replay proven |
| §8.2 Fact-oriented Context endpoint | returns decisions in their own block |
| §8.2 Empty Morning Brief | reads the ranked queue |
| §8.2 Cards never rebuild | migration `0077`, refreshed in place |
| §11.1 / §11.2 / §11.3 the three vertical slices | `awaiting_response`, `meeting_follow_through`, `cohort_outreach_gap` |
| §12.5 / §12.6 routing | 0 situation types unrouted globally |
| §14.3 Layer 4 acceptance | proven on real Postgres |

---

## Genuinely new — ranked by what it changes for a paying tenant

### 1. Universal Domain Router — §6.1 · NOT BUILT · **highest value**

Today the domain comes from `capture/domain/hints.py`: an ordered regex, **first match wins,
single label, no confidence**. `general` means "no keyword fired", which is most real mail.

MD 06 asks for multi-label candidates with confidence, human correction, and independence from
entitlements. That is not a refinement of the regex — it is a different component.

**Why first:** every layer above inherits this. A thread routed to the wrong domain gets the wrong
expertise no matter how good the expertise is, and today an investor thread that fails to say
"deck" or "round" silently becomes `general`.

**Blocks:** item 2 (an entitlement gate needs a domain to gate on) and §14.2.

### 2. Entitlement gate + locked-domain receipt — §10 · NOT BUILT · **product-shaped**

Nothing in the engine knows what a tenant is licensed for. The MD's design is right and its
warning is the important part: **frontend blur is not a lock** — the payload is still in the API
response.

Needs: a plan/entitlement record, a gate between routing and compilation, and a redacted receipt
type carrying `{domain, detected, count, category, freshness}` and nothing person-level.

**Judgment:** build this only when Admin-only pricing is actually going live. It is commercial
plumbing, not intelligence — it makes nothing smarter, it makes something sellable.

### 3. Situation taxonomy — §5.10 · **4 of ~25 built**

Shipped: `awaiting_response`, `commitment_overdue`, `meeting_follow_through`,
`cohort_outreach_gap`.

MD 06 names roughly twenty more across seven families. Honest split:

| Buildable from data we hold | Needs a source we do not have |
|---|---|
| `communication.repeated_follow_up_without_response` | `business_object.source_state_conflict` (needs a second system of record) |
| `communication.thread_reactivated` | `relationship.stakeholder_changed` (needs an org chart) |
| `meeting.upcoming_with_missing_preparation` | most `business_object.*` (needs stage history — item 4) |
| `meeting.promised_material_pending` | |
| `meeting.next_step_not_scheduled` | |
| `commitment.approaching_due` | |
| `relationship.no_recent_interaction` | |
| `relationship.single_threaded` (edge_count on the account) | |

**Judgment:** the left column is cheap — each is one situation file plus, at most, one derived
fact. Do them in a batch. The right column waits on items 4 and on connectors.

### 4. Business object lifecycle — §5.7 · NOT BUILT

No `stage_history`, no `time_in_stage`, no `previous_state`, no `state_changes` anywhere.

This is what makes the MD's own headline example possible:

> "in Proposal 2.1× longer than comparable deals"

Needs a history table (or a fact family) written whenever a tracked field changes, plus a
comparator across the tenant's own closed deals. Unlocks a whole family of §5.10 situations and
is the single largest missing *capability* rather than missing wiring.

### 5. Context quality: contradictions and fail-closed situations — §5.11 · **half done**

`missing_fields` is honest now. Not done:

* **contradictions** — `discrepancies` rows exist in the schema and never reach the context slice
* **fail-closed situation kinds** — the MD wants `context.decisive_evidence_missing`,
  `context.sources_contradict`, `context.identity_ambiguous`, `context.evidence_stale` as
  *situations*, so a gap becomes a card that asks a human rather than silence

**Judgment:** the second half is genuinely good product. "I cannot advise until you tell me X" is
a better card than nothing, and it is the honest use of the abstention machinery that already
exists.

### 6. `next_evaluation_at` and the escalated lifecycle — §5.12, §5.13 · NOT BUILT

Situations carry `active | dormant | resolved | archived` and no `next_evaluation_at`. Today
re-evaluation is "whatever the sweep recomputes", which works but cannot express *when* a
situation should next be looked at, and cannot escalate.

**Judgment:** low urgency. The sweep already re-derives everything each pass, so the practical
gap is expressiveness and cost, not correctness.

### 7. Admin internal namespaces, incl. `investor_operations` — §9 · **partly there**

Admin already has real subdomains (`executive_support`, `meeting_operations`,
`finance_administration`, `contract_and_vendor`, `people_administration`, …).

Missing: fundraising/investor operations lives in the **Sales** corpus under `investor_relations`,
for a real reason — a compiled signal can only carry authority in a pack lane the tenant holds,
and splitting it would produce capabilities that compile and can never become a card.

**Judgment:** MD 06 §9.8 wants it under Admin. Doing that means giving `fundraising` its own pack
lane first. Worth it if Admin is the SKU; otherwise the current placement is the pragmatic one.
**Decide the SKU before touching this.**

### 8. Role vocabulary — §5.2 · **partly there**

Have: `counterparty, introducer, introduced, owner, approver, observer, machine` and natures
`investor, customer, prospect, vendor, candidate, partner, community`.

MD 06 also wants `champion`, `decision_maker`, `economic_buyer`, `employee`, `internal_owner`.
Cheap — extraction vocabulary plus prompt, same shape as the 17 observation kinds already added.
Note `enterprise_deal` currently infers a committee from thread participants because these roles
do not exist.

### 9. Replay tests — §6.4 · NOT BUILT

The corpus has admission (180 admitted / 26 blocked) but no **positive / negative / abstention
replays**. A situation file is accepted on a reviewer's word and a content hash; nothing proves it
fires where it should, stays silent where it should not, and abstains when context is thin.

**Judgment:** this is the highest-leverage *test* work in the document. It is what would have
caught the four Sales situations that asserted claims their gates never checked.

### 10. Layer 4 ranking factors — §7 · **partly there**

Ranked on impact, success, urgency, effort, risk. MD 06 also lists relationship strength,
recipient seniority, cost of interruption, and reversibility.

**Judgment:** seniority and relationship strength need data we do not hold. Reversibility and cost
of interruption are authorable per play today and are the two worth adding.

### 11. `why_this_action` — §7.2 · NOT BUILT

The card carries `why_now` and the rejected alternatives, but never *why this one won*. The
information exists — the ranked candidate list and its score components are persisted. It is a
projection, not new reasoning. Cheap.

### 12. Compiler activation — §6.5 · **the standing decision**

`GENIOS_USE_DOMAIN_COMPILER` is unset. Until it is on, items 1–11 change nothing a user sees,
because the compiled lane is where all of it runs.

---

## Suggested order for the next session

1. **Turn the compiler on for one tenant and read the cards.** Everything below is guesswork until
   the shipped chain has been seen on real data.
2. **Replay tests (9)** — cheap, and it makes every later change safe.
3. **Universal Domain Router (1)** — everything above it inherits the fix.
4. **Situation taxonomy, left column only (3)** — a batch of small files.
5. **Context-quality situations (5)** — turns silence into an honest question.
6. **Stage history (4)** — the big one; unlocks the right column of (3).
7. **Small wins whenever convenient:** roles (8), `why_this_action` (11), reversibility (10).
8. **Entitlement gate (2)** — when the SKU decision is made, not before.

## Two things to decide before any of it

* **Is Admin the SKU?** Item 7 and item 2 both hang on this, and both are expensive to redo.
* **Does `general` mean a domain or an absence?** The router (1) cannot be specified until this is
  answered — today the code treats it as both in different places.
