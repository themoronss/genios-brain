# Sales Expertise — folder map

> **How would a seasoned sales operator read this situation?**
>
> Not what is true — that is Layer 2. Not what to do — that is Layer 4.

[← Authoring guide](../README.md) · [Browsable book](../_book/Sales%20Expertise/index.md) ·
[Signal backlog](registry/signal-backlog.md)

---

## Where this stands

| | |
|---|---|
| Files | **101**, all passing `validate.py` |
| Subdomains | 9 |
| Capabilities | **46** — 1 complete, 45 stub |
| Situations | 3 |
| Objects | 6 authored, 20 declared in `planned_objects` |
| Model branches | 17 models + 16 verticals |
| Offering branches | 3 families + 9 types |
| Inference patterns | **33 executable · 23 blocked** on 23 distinct signals |
| Layer 2 coverage | **15 of 26** emitted situation types routed (57%) |

Phase 1 was deliberately *thin breadth plus one deep vertical*: every capability exists so the
map is complete, and one vertical is authored to the bottom so there is a reference to copy.

---

## Layout

```
Sales Expertise/
├── domain.yaml                    9 subdomains · id scheme · planned_objects · glossary
│
├── capabilities/                  46, numbered by lifecycle order
│   ├── 01-market-and-targeting/       3
│   ├── 02-prospecting-and-outreach/   8
│   ├── 03-qualification/              5   ← lead-qualification.yaml is complete
│   ├── 04-discovery-and-solution/     4
│   ├── 05-proposal-and-commercials/   4
│   ├── 06-closing/                    4
│   ├── 07-post-sale-and-growth/       7
│   ├── 08-revenue-operations/         7
│   └── 09-sales-management/           4
│
├── situations/                    inbound-lead · outbound-prospect · enterprise-deal
├── objects/                       decision-maker · champion · budget
│                                  buying-committee · timeline · icp
├── models/                        b2b/ b2c/ (with verticals/) · plg · slg · channel
│                                  partner · franchise · distributor · reseller
│                                  government · enterprise · mid-market · smb
│                                  inside-sales · b2b2c · d2c · marketplace
├── offerings/                     product/ service/ hybrid/  (+ types)
└── registry/                      GENERATED — do not edit
```

---

## Start here

| Reading for | Open |
|---|---|
| The reference object — all 18 sections, 4 executable and 6 blocked patterns | [objects/decision-maker.yaml](objects/decision-maker.yaml) |
| The reference capability — what a promoted stub looks like | [capabilities/03-qualification/lead-qualification.yaml](capabilities/03-qualification/lead-qualification.yaml) |
| How a situation binds to Layer 2 | [situations/enterprise-deal.yaml](situations/enterprise-deal.yaml) |
| How a branch declares a diff instead of a copy | [models/b2b/model.yaml](models/b2b/model.yaml) |
| What Layers 1 and 2 must build next | [registry/signal-backlog.md](registry/signal-backlog.md) |

---

## The two gaps this library found

Both are outputs of the authoring, not defects in it.

**Eleven Layer 2 situation types route nowhere.** The pipeline emits them and no situation
binds them, so no capability will ever compile for them and the failure is silent:

`budget_freeze` · `champion_left` · `closed_lost_risk` · `commitment_overdue` ·
`competitor_in_live_deal` · `deal_sentiment_negative` · `discount_pressure` ·
`objection_open` · `pricing_objection` · `proposal_no_response` · `timeline_slip`

Most want a fourth and fifth situation — a *deal-at-risk* and a *commercial-negotiation*
situation would absorb nine of the eleven.

**Twenty-three patterns are blocked on signals that do not exist.** Ranked by how many they
unblock, the top asks are `crm.contact.role` (3 patterns), `account.industry` (2) and
`account.prior_deal_outcomes` (2). Three individually high-value ones stand out:

- **`contract_signed`** — Layer 2 emits `contract_requested` but never `contract_signed`. The
  strongest possible proof of purchasing authority happens on every won deal and is discarded.
- **`crm.deal.close_date_history`** — slip count is the strongest single loss predictor in most
  pipelines, and it is already sitting in CRM field history that the connector does not read.
- **`derived.sentiment_by_person`** — sentiment is deal-scoped today, so the engine can say the
  room is unhappy but never who. Locating the dissenter is what Buying Committee exists to do.

---

## What comes next

| Phase | Work |
|---|---|
| **2** | Complete the Qualification subdomain — promote its 4 remaining stubs, author the ~15 objects they need |
| **3** | Author B2B and B2C overlays against real Phase-2 content, before the fan-out depends on the mechanism |
| **4** | Promote the other 8 subdomains; author the remaining ~100 objects |
| **5** | Compiler: emit and validate pack manifests from this library; add the test that every emitted L2 type resolves to a capability |
