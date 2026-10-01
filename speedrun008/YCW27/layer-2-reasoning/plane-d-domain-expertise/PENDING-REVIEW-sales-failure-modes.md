# ⛔ PENDING YOUR SIGNATURE — `failure_modes` for two Sales capabilities

**Written for:** Harsh (CTO) — the named reviewer on both files — and Rohit.
**Date:** 2026-09-30. **Not applied. Deliberately.**

---

## Why this is a document and not a commit

`sales.qualification.lead_qualification` and `sales.post_sale_and_growth.customer_success` are the
only two capabilities in the corpus — of 155 — that declare no `failure_modes`. Real gap, small,
and I wrote the content.

⛔ **Then I reverted it, and that is the point.** Both files carry:

```yaml
metadata:
  review_status: approved
  reviewed_by: harsh
  reviewed_at: 2026-08-24
admission:
  accepted_content_hash: <hash of the content Harsh actually read>
```

Adding a block changes the content, so `_admission_reason` returns
`content_changed_since_acceptance` and the capability stops carrying authority. That is **exactly
what the hash pin is for** — the corpus's own words: *"the difference between accepting a FILE and
accepting its CONTENT."*

And `_tools/admit.py --accept` **would have stamped it anyway**, because it only refuses what is not
already marked approved — and these are. So re-stamping would have put **Harsh's signature, dated
2026-08-24, on seven paragraphs he has never read.**

Two of this repo's own tests caught the un-stamping immediately, which is the guard working:

```
test_the_whole_shipped_corpus_is_stamped_now   → content_changed_since_acceptance ×2
test_the_measured_corpus_is_healthy_and_says_so → 153 == 155 failed
```

> ⛔ **I will not forge an acceptance, and I will not leave the suite red to look complete.** So the
> content is here, the corpus is back to 155/155 admitted, and the one step that is a human's stays
> a human's.

## How to apply it — two minutes

1. Paste each block below into its file, between `outcomes:` and `kpis:`.
2. Read it. Change anything you disagree with — it is domain judgment, and it is mine, not yours.
3. Update `reviewed_at` to today (and `reviewed_by` if it should be you rather than Harsh).
4. `.venv/bin/python "Domain Expertise/_tools/admit.py" --accept --all`
5. `.venv/bin/python -m pytest tests/packs/ -q` — back to 155/155.

---

## `lead-qualification`

**File:** `Domain Expertise/Sales Expertise/capabilities/03-qualification/lead-qualification/capability.yaml`

```yaml
failure_modes:
  - >
    Qualifying on interest instead of on purchase. A demo booked, a deck downloaded and a
    reply within the hour all read as progress and none of them is evidence that money can
    move. The question this capability asks is whether a purchase is POSSIBLE; enthusiasm is
    an input to that answer and is routinely mistaken for it.
  - >
    Taking authority from a title. "Head of" resolves to a decision maker in the CRM and to
    a recommender in the room, and the two are indistinguishable on a business card. The
    outcome demands authority VERIFIED rather than inferred, and the verification is one
    question nobody enjoys asking.
  - >
    Recording an absent compelling event as an unknown. "No deadline mentioned" and "we
    asked and there is none" are the same field and opposite facts: the first is work not
    done, the second is a qualified answer. Collapsing them is how a pipeline fills with
    deals that were never going to close this quarter and never said so.
  - >
    Budget state left at `unknown` because asking felt early. It is the cheapest field to
    leave blank and the most expensive one to be wrong about, and it stays blank precisely
    on the deals where the answer would have changed what happened next.
  - >
    `Continue by default`. The capability's own outcome forbids it and it remains the most
    common verdict in every pipeline: nothing was disqualified, nothing was committed to,
    and the deal advances on the absence of a decision rather than the presence of one.
  - >
    Disqualifying on fit alone while the ICP is stale. A profile written before a pricing
    change will reject the accounts the company can now serve, and it will do so quietly,
    because a disqualified lead generates no argument and no review.
  - >
    Re-qualifying from the record instead of from the counterparty. Six weeks on, the budget
    line, the sponsor and the deadline have all moved, and the qualification that is read
    back is the one taken when the deal was new. A qualification has a shelf life and the
    record does not say so.
```

---

## `customer-success`

**File:** `Domain Expertise/Sales Expertise/capabilities/07-post-sale-and-growth/customer-success/capability.yaml`

```yaml
failure_modes:
  - >
    Reading warmth as health. A friendly thread on an unused product is the single most
    reliable precursor to a churn nobody saw coming, and it presents as the healthiest
    signal in the account. The capability's own outcome separates adoption from tone for
    this reason, and the separation is the first thing abandoned under time pressure.
  - >
    Taking relationship state from the last CRM edit. The field says `active` because
    somebody typed it, not because anybody spoke. Observed contact and recorded status
    diverge silently and always in the optimistic direction, because nobody updates a record
    to say a relationship has gone quiet.
  - >
    `Stay in touch`. The outcome names it explicitly: it is what gets written when nobody
    decided. It survives review because it is never wrong, and it commits no one to
    anything, which is the same property.
  - >
    Treating a healthy non-buying relationship as a stalled deal. The capability exists
    apart from the deal capabilities precisely to prevent this, and the pressure to reclassify
    a good relationship as pipeline is strongest exactly when the forecast is short.
  - >
    Measuring the outcome the vendor sells instead of the one the customer bought. Usage of
    the product is not the same as the result it was purchased for, and a capability that
    reports the first while the second is failing will be confidently wrong for two quarters.
  - >
    Escalating on a single bad interaction. One curt reply is noise; a pattern is a signal,
    and the difference requires history this capability must go and read rather than infer
    from the message in front of it.
  - >
    An open loop named on our side only. "What we owe them" is easy to see and "what we are
    waiting on" is invisible until it is late — and a relationship where WE are the blocker
    and nobody recorded it is the one that ends without a conversation.
```

---
