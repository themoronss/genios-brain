# THE REVIEW, TAKEN OVER · 18 situations become 3 — and the 15 need nobody

> **Date:** 2026-10-01. Rohit read the generated queue and said it was unanswerable: *"samajh mein
> nahi aa raha… context hai na kuch hai. Main karun to karun kaise?"*
> **He was right, and the fault was mine.** I asked an engineering question in product clothing.

---

## PART 0 · WHAT I GOT WRONG ABOUT THE QUEUE

`QUEUE.md` and `review.html` asked, of ten situations: *"is matching on the type alone right here,
or does it need a condition?"*

**That question cannot be answered without reading the matching engine.** Whether an empty
`matches.when` is correct depends on whether the L2 situation type a route carries is a *computed
state* or a *category* — which is a fact about `context/support_situations.py`, not a judgement
about what an executive wants. I put it to the one person in the building who should never have to
know that, and I put it eighteen times.

> **A reviewer can only be asked what the evidence cannot settle.** Everything the evidence settles
> is the engineer's job, and handing it over as a question is how a review queue becomes busywork.

---

## PART 1 · WHAT THE EVIDENCE SETTLES — and it settles 15 of the 18

### ⛔ FIVE ARE DELIBERATELY BLOCKED, AND FULLY DECLARED. They need no review.

    csat_detractor · entitlement_expired · major_incident_declared
    sla_breach_imminent · ticket_reopened

They carry **no** `l2_situation_types` and instead a `pending_l2_situation_types` entry, which is
the mechanism for *"routed by nothing, and here is why."* Each entry carries all four things a
reader needs:

    type           the L2 type that must exist
    owner_layer    L1 or L2 — WHO must build it
    nearest_today  the closest type that exists now, so nobody guesses
    note           a full specification of what the type must mean

Example, `major_incident_declared`: *"Must mean: a named human has declared an incident, with a
severity, a start time, a blast radius…"*, owner_layer **L2**, nearest today `unanswered_email`.

**A situation that cannot route cannot be validated against anything, and when its type is finally
built it will need reviewing again against the real thing.** Reviewing them now is work that has to
be redone. They are correctly parked and the parking is documented better than most code.

### TEN MORE ARE CUSTOMER SUPPORT, AND THAT DOMAIN IS ON HOLD

Only **Admin** is activated for any tenant. `Customer Support Expertise/deferrals.yaml` says it in
its own words: *"Customer Support is on hold. Nothing here switches a domain on, nothing here is
compiled for any tenant, and the only activated corpus remains Admin."*

Approving a Customer Support situation today changes **nothing** for any tenant. It is not wrong to
do it; it is simply not a thing anyone is waiting on.

### AND THE "NO CONDITION" ALARM WAS MINE, NOT THE CORPUS'S

Of the thirteen routed situations, five carry no `matches.when`:

    bug_awaiting_engineering · escalation_requested · first_response_overdue
    queue_overloaded · repeat_contact

**An empty `when` is correct for all five, and the reason is upstream.**
`context/support_situations.py` is a deterministic reader that *computes* these states — its own
header: *"Intent, escalation, workaround and fix are read by closed deterministic lexicons over the
masked text L1 already persisted… **NO LLM ANYWHERE IN HERE.**"* It mints a situation of type
`first_response_overdue` only when the first response really is overdue.

> **The L2 situation type IS the condition.** A `when` on top of it would re-check what the layer
> below already decided — and could disagree with it, which is worse than not asking.

So the right answer to my own question was *"no condition needed"*, in all five cases, and it was
answerable from the code.

---

## PART 2 · WHAT IS ACTUALLY LEFT · three situations, all Admin, all conditional

    admin.sit.campaign_awaiting_reply       priority 6500bp · 21 days · card: brief
    admin.sit.condition_awaiting_review     priority 5600bp · 90 days · card: draft_reply
    admin.sit.organization_gone_quiet       priority 6200bp · 30 days · card: brief

All three are **routed and fire today** on the only activated domain. All three **carry conditions**,
and every predicate was checked against production:

    campaign.contacted >= 3 · campaign.awaiting >= 2 · exists campaign.quote        7 rows each
    exists condition.text · exists condition.quote                                23 rows each
    organization.awaiting >= 2 · organization.longest_wait_days >= 7               7 rows each

**Nothing is broken in them.** The remaining question is the one the evidence genuinely cannot
settle, and it is a product question of one line each: **does a founder want this card?**

---

## PART 3 · ⛔ THE ONE THING I CANNOT DO, AND WHY IT IS NOT A TECHNICALITY

I can analyse all eighteen. I cannot write `metadata.review_status: approved`.

That field's whole meaning is *a named human read these exact bytes*. The five situations already
carrying it carry `reviewed_by: harsh`. The corpus states the rule it exists to stop: *"an author
flipping `stub: true -> false` in a text editor granted production authority."* An AI writing
`approved` with `reviewed_by: ai` is that flip with a different hand on it.

So the handover is: **I did every part of this that is evidence, and the signature is one line from
Rohit on three situations.** Not eighteen judgements with no context — three product questions, and
a yes on all three is a legitimate answer.

### What approving still does NOT do
It sets `review_status: approved`. The situation stays refused until `identity.status` also becomes
`stable` — the deliberate second gate, and the same half-state five situations are already in
(ALARM D-A2).
