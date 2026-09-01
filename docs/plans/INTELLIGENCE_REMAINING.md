> **Created:** 2026-09-01 · **Status:** 🟢 Active — D, E, F and G all shipped. One product decision open, plus deploy
>
> **Purpose:** What is left after `L2_L4_INTELLIGENCE_CHAIN.md`, ranked by effect on card quality
> rather than by the order the audit listed it — with the items deliberately NOT being done, named.

## How this was ranked

The audit MD is a reference, not a work order. Several of its items are real and cheap, one is
expensive and would change nothing today, and three are out of scope for a card-quality problem.
The ordering below is by **how much a real card improves per unit of work**, which is not the
audit's order.

## Pass D — `outreach.objective` gets a writer ✅ SHIPPED

**Why first.** Every `awaiting_response` card currently declares this missing on every row, and it
is the field that separates a FOLLOW-UP from a REMINDER. Without it these are the same card:

- an investor sitting on a fundraising ask
- an investor who is merely owed a quarterly update
- a vendor waiting on a signature

`relationship.nature` already says what they ARE to us. It does not say what we WANT from this
exchange, and the advice turns on the second, not the first.

Vertical: extraction prompt → `Extraction.objective` → `thread.objective` fact → projected onto
the `outreach` anchor → an `objective` slot the card may state → the situation's render hint stops
saying "do not state what the outreach was for".

## Pass E — the surfaces stop bypassing the intelligence ✅ SHIPPED

Cheapest large win, and the direct cause of "I am shown facts, not intelligence":

| Surface | State today |
|---|---|
| `GET /morning-brief` | returns literal `{"headline": None, "considered": 0, "priorities": []}` |
| `POST /context` | queries graph facts directly; never invokes reasoning |
| insights feed | carries headline/situation/action/priority and DROPS why-now, alternatives, uncertainty, outcome contract |

All three read from tables that already hold better answers. This is plumbing, not new
intelligence — which is exactly why it is worth doing before anything expensive.

## Pass F — cohort engine ✅ SHIPPED

The user's own repeated example: *"314 Capital / Far Network ke jitne founders aur VCs ko email
kiya, kaun reply nahi kar raha?"* Today each person is a separate situation and nothing reads the
campaign. Follows `periodic.py`'s existing shape — a tenant-anchored node carrying aggregates —
so it needs no new concept, and Pass D is a hard prerequisite: a cohort is defined by a shared
OBJECTIVE, not by a shared email domain.

## Pass G — the four brains change a decision ✅ SHIPPED

`reason/` still has **zero** read sites for `organization_rules` / `behavior_patterns` /
`adaptive_preferences`; they travel in the manifest and the knowledge hash only.

**Ranked below the surfaces deliberately.** The acceptance test the audit proposes — same evidence
+ different company rule → different decision — is the right test, but `learned_brain_entries` is
near-empty on every live tenant, so a consumer written today changes nothing a user could see. It
is a correctness fix for a claim we make ("it learns how we operate"), not a card-quality fix, and
it should land once there is learned state to consume.

## Not doing, and why

| Item | Why not |
|---|---|
| 153 `capability.yaml` made executable | Highest volume, lowest current return. The **situation** files are what gate and route; they are now executable. A capability file's prose reaches the card through plays, which already work. |
| Layer 1 connectors (Slack, Stripe, Zendesk, Jira) | Not a card-quality problem — a coverage problem, and a different kind of project. |
| Stage history / time-in-stage | Needs CRM history nobody has connected. Would be an invented series. |
| Locked-Sales upgrade receipt | A product/pricing feature, not a fix. Belongs with entitlements. |
| Outcome-learning proof | Needs the above shipped and time in production. Cannot be built ahead of the data. |

## The acceptance test the audit asked for — passing

> *Same evidence + different company rule must produce a meaningfully different decision.*

Run on real Postgres, one situation, two authored plays, three knowledge states:

| Company knowledge | Decision | How |
|---|---|---|
| none | `ask_for_intro` | both plays 5,000bp, tie broken by play id |
| this tenant's measured outcomes | `chase_by_email` | adaptive re-scored them 6,140 vs 3,860 |
| a stated policy: "never go around a contact to their introducer" | `chase_by_email` | `ask_for_intro` **eliminated**, not merely out-ranked |

The third row is the one that matters: a policy removes an option before ranking, which is the
difference between a policy and a preference.

## Card overlap ✅ RESOLVED — the cohort absorbs only what it can already say

A campaign of five silent contacts produced five per-person cards AND a cohort card. Six cards
about one campaign is not six pieces of intelligence.

Suppressing all five would have been wrong in the other direction, because the per-person
judgment DIFFERS once somebody has been chased: *"chased twice with no reply, another reminder is
unlikely to be what changes this"* is an instruction about that relationship, and an aggregate
cannot make it. So **only the never-chased are absorbed** — the cohort states them as a group
("never chased: 3") and names them in its own artifact, which is exactly as much as an individual
card would have said. Everyone the cohort can only COUNT keeps their own card.

Lives in `deliver/pipeline.py::_cohort_absorbed`, deliberately: Layer 2 mints both situations
because both are true, and deciding that one presentation makes the other redundant is a judgment
about what a person should be shown. Computed over the whole signal list before any card is built,
so the queue does not depend on build order. Reported as `absorbed_by_cohort` — a suppression
nobody can see the size of is indistinguishable from a bug that lost cards.

## OPEN — a single-event counterparty produces no card at all

Found by running the cohort scenario on real Postgres, and **not on any earlier list**.

Two of six contacts — the ones we had emailed exactly once and never heard from — minted a
situation, compiled, reasoned, and were **BLOCKED**. Measured, not inferred:

```
outcome_kind | evidence_n | count
blocked      |          0 |     2
decision     |          1 |     4
```

The `evidence_required` policy fail-closes when no upstream unit can ground the action in the
frozen snapshot, and their snapshot carried zero evidence. The root cause is upstream of the
policy: **facts written onto a synthetic anchor carry no `graph_source_refs`** (`_write_fact` in
`support_situations.py` inserts into `graph_facts` alone), so an anchor's evidence has to arrive
through its `concerns` neighbour — and a neighbour with one captured event supplies too little.

Deliberately not fixed here. `evidence_required` is a fail-closed gate that `reason/store.py` and
`reason/authority.py` both re-prove, and loosening it at the end of a long session to admit
thin-evidence cards is the wrong direction. The right fix is to give derived anchor facts their
own source refs, so the provenance that already exists is not lost in the derivation.

Mitigated meanwhile, and arguably correctly: these people are exactly the ones the cohort card
covers, so cold outreach is visible as a campaign even where no individual card can be built.

## Resume points

Each pass is independently shippable and leaves the suite green. On resume, read this table:

| Pass | State |
|---|---|
| D — objective writer | ✅ shipped. Extraction contract → `thread.objective` (outbound leg only) → `outreach.objective` on the anchor → an `objective` slot. `unknown` is never written, so an unplaced thread keeps the field in `missing` rather than satisfying it with a meaningless label. Objective values are PURPOSES (`selling`, `customer_issue`, `operations`) not department names — `test_projections` forbids a Layer 2 file naming a domain, and the collision was a category error anyway. |
| E — surfaces | ✅ shipped. All three read the decisions that already existed, each re-checking `AUTHORITATIVE_SIGNAL_PREDICATE` — a brief is acted on without opening anything else and may not show a superseded conclusion. Running the real chain (L2 → compile → signal → card → surface) on Postgres found **five bugs no hermetic test could reach**: slots read `thread.*` while a compiled card's subject is the `outreach` anchor holding `outreach.*` (every compiled card fell back to sentinels for the numbers it was built to state); the Context panel matched only `subject_node_id` so the anchor's decision was invisible on the person it concerns; the sentinel `"the commitment"` was being written into `unresolved_item` as if it were a fact; `why_now` was NULL on the richest cards; and the anchor's graph-browsing display name repeated the situation in the headline. |
| F — cohort | ✅ shipped. Keyed on the **objective**, not the organisation: two partners at two firms are one raise, while a fundraising thread and a vendor thread with the same firm are two things needing opposite answers. Firms travel as a facet. Fires at ≥3 contacted / ≥2 waiting / ≥1 chaseable. Two corrections found by running it on a real campaign: gating on `awaiting_beyond_normal` alone was nearly unfireable (it needs two prior replies before a person's cadence exists, which early in a raise nobody has) — replaced by `cohort.chaseable` = never-chased + past-normal; and that count is now **absent rather than zero** when nobody's cadence was knowable, because "0 past their usual reply time" read as "we checked and nobody is late" on a campaign we could not check at all. |
| G — brains | ✅ shipped. Two seams, both already designed and neither touching a frozen shape. **Adaptive** — `feedback/units.unit_recommendation_learning` has been publishing `{"play": ..., "success_rate_bp": ...}` per play from labelled outcomes and nothing ever read it; that number is now the play's `success_probability_bp`, which is a weighted term in the ranking model and previously sat at the 5,000bp default for every compiled play. **Organization** — a permission-category rule naming a play now reaches `core.constraint`'s `blocked_play_ids`, the tenant block list the unit already documents as "a hard, id-level retirement a tenant can apply without touching authored expertise", producing a `tenant_policy_block` ELIMINATE row that `store.py` and `authority.py` both re-prove. **Behavior has no consumer** and the manifest says so (`brain_influence.behavior_consumed: False`) rather than implying otherwise. `brain_influence` now reports EFFECTS (which plays were blocked, which were re-scored) instead of a row count — a count of forty entries about plays a capability does not declare was how "the brains reached the decision" stayed unfalsifiable. |
