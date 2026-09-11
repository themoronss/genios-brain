# L2 — Worked Example, End to End

> One situation, traced through every Layer 2 group, showing **where each LLM site fires
> and where it does not** — and then the same situation three weeks later, which is where
> today's system breaks and v2 does not.

---

## Setup

Acme AI. Gmail, Calendar, Drive, HubSpot connected. Zendesk **not** connected.
`coverage_epoch = 4`.

**Layer 1 v2 hands Layer 2 four `QualifiedEnterpriseSignal`s, all sharing one `trace_id`:**

| # | signal_type | importance_bp | key payload |
|---|---|---|---|
| 1 | `CONTRACT_RENEWAL` | 8100 | `Money(8_400_000, USD)` verified · `ResolvedDate(Oct 15, EXACT)` · cancellable_until Sep 15 |
| 2 | `DECISION_PENDING` | 6400 | subject "AWS migration" · state `pending` · dependency Finance→Founder |
| 3 | `FINANCIAL_OBLIGATION` | 5900 | spend trend claim, 3 months |
| 4 | `DEADLINE_STATED` | 5200 | calendar absence — no review meeting |

Every one carries verified evidence spans and `coverage_ready = True` for the admin domain.

---

## Pass 1 — the drain

### L2.2 · Graph engines

```
identity cascade:  "AWS" / "Amazon Web Services" / "aws-billing@amazon.com"
                   -> domain match on amazon.com  -> ONE node, deterministically
                   M-1 DOES NOT FIRE  (cascade was conclusive)

edge typing:       contract --renews_on--> 2026-10-15        rule table, no LLM
                   Finance --blocks--> renewal_decision      rule table, no LLM
                   M-2 DOES NOT FIRE
```

**Two LLM sites available, neither fires.** This is the gating working as intended — the
clear cases never reach a model.

### L2.3 · Cross-correlation

```
anchor selection:  contract node wins ANCHOR_PRIORITY
                   (tenant node deliberately excluded — otherwise it would
                    swallow every conversation in the org into one situation)

all 4 signals -> one correlation group

L2.3.8 dependency chain (BLG-05, NEW):
    Finance --blocks[approval]--> migration_decision
    migration_decision --blocks[decision]--> renewal_decision
    chain length 3, no cycle
    blocked_count(renewal_decision) = 2   -> written as a derived fact

M-3 DOES NOT FIRE  (single thread, no ambiguous cross-conversation candidate)
M-5 DOES NOT FIRE  (no conditional commitment in this set)
```

### L2.4 · Analytic stratum — **all deterministic, zero LLM**

```
metric_history read (L2.4.1-U2), 6 monthly points, gaps explicit:

  engagement.touch_count_28d   14, 12, 11, 9, 8, 6
  gap_reason for every period: GENUINELY_ZERO      (org was active, sources healthy)

L2.4.3 trend (BLG-08):
    coverage_ratio 10000 (no gaps) -> passes step 1
    integer least squares -> slope
    normalized against mean (step 3, the step people skip)
    relative_slope_bp = -1240  ->  DECLINING
    streak_periods = 6
    trend_confidence_bp = 7100     (capped ceiling is 8000)

L2.4.5 cohort position (BLG-10):
    cohort "vendor_spend_growth_quartile"  population 14  (>= 5 floor, passes)
    spend growth percentile_bp = 9300  -> TOP DECILE
    carries cohort_id + population_size + p25/p50/p75   (Law 2)

L2.4.8 anomaly (BLG-13):
    baseline = median of own trailing 6, MAD-based
    z_like 3.2 MAD AND deviation_bp 3400 -> BOTH conditions -> FLAGGED
```

**This is the discovered pattern, and no model was involved:** *engagement declining six
months running, spend growth in the top decile of its peer group, spend 3.2 MAD above its
own baseline.* Nobody wrote a rule naming AWS. Every number is reproducible and citable.

### L2.5 · Context quality

```
L2.5.5 typed absence (BLG-15):
    decision.scheduled -> calendar IS connected, nothing found
                       -> GENUINELY_ABSENT
                       -> licenses_negative_inference = True
                       -> "no review is scheduled" is SAFE TO SAY

    support.ticket_count -> Zendesk NOT connected
                         -> UNKNOWABLE
                         -> licenses nothing, degrades coverage_score
                         -> NOT used in any inference

coverage_epoch stamped: 4
```

**The two absences are treated differently, and that difference is the whole point of the
component.**

### L2.1 · Authority view (NEW)

```
authority_rules:  contract, threshold 5_000_000 minor units, approver = founder
                  source = admin_declared    -> authority 10000
$84K > $50K       -> approver resolved: founder
```

### L2.6 · Pattern matching

```
pattern vendor_renewal_unowned v1:

  1 contract.auto_renews == true                    ✓ fact
  2 contract.value >= @authority_threshold          ✓ resolved to 5_000_000 from L2.1
  3 contract.cancellable_until within 30 days       ✓ temporal — 12 days
  4 decision.scheduled GENUINELY_ABSENT             ✓ absence  (NOT satisfied by UNKNOWABLE)
  5 edge owns from @anchor missing                   ✓ edge

  required 5/5 MATCHED

  optional_signals:
    migration_discussed observation                 ✓ +1500 bp
    engagement DECLINING (conf 7100 >= 5000)        ✓ +1000 bp
```

**Conditions 4 and 5 are only expressible because L2.5.5 and the Authority view exist.**
Conditions 6 and 7 (the optional trend signal) only because L2.4 exists. **This one pattern
declaration is a churn detector nobody wrote code for.**

### L2.7 · Business situation

```
L2.7.3 clustering:  4 signals share the contract entity -> ONE situation, not four cards
                    M-8 DOES NOT FIRE  (deterministic shared-entity merge was conclusive)

L2.7.4 importance (BLG-18):
    base = MAX(8100, 6400, 5900, 5200) = 8100        <- max, NOT mean
    + corroboration      3 distinct sources          +1000
    + trend modifier     DECLINING, conf 7100        +1000
    + cohort modifier    top decile, pop 14          +1000
    + anomaly modifier   flagged                      +800
    + dependency         blocked_count 2              +400
                                        modifier cap  +4000  (reached)
    coverage penalty     coverage_ready True          x1.0
    = 10000 (clamped from 12100)

    importance_components stored — every term, so "why 10000?" is answerable

L2.7.2 framing — M-6 FIRES  (T2)
    input: member facts + matched conditions, visibility-filtered FIRST
    output: headline, span-constrained
    numbers TEMPLATED IN, not generated:
      "Your $84,000 AWS agreement auto-renews in 42 days and nobody owns the decision"
    validation: every noun traces to a supplied fact ✓

L2.7.7 lifecycle:  terminal_by_fact False, status ACTIVE
                   M-4 DOES NOT FIRE  (no new message landed on an open situation yet)
```

### Output

```
BusinessSituationObject
  type              vendor_renewal_decision
  importance_bp     10000      (NOT the hardcoded 5000)
  confidence_bp     8400
  confidence_vector evidence 8800 · freshness 9100 · consistency 10000
                    identity 10000 · coverage 6200 · analytic 7400
                    ^^ coverage 6200 because Zendesk is absent — honestly discounted
  pattern_id        vendor_renewal_unowned
  matched_conditions 5 (each with its satisfying evidence)
  trends            1 DECLINING
  cohort_positions  1 top-decile, population 14
  anomalies         1 flagged
  missing_facts     decision.scheduled GENUINELY_ABSENT
                    support.ticket_count UNKNOWABLE
  evidence          7 verified spans
  coverage_epoch    4
```

### Convergence (L-4)

```
pass 1: state changed
pass 2: importance recomputed after the dependency fact landed -> changed
pass 3: state_hash identical -> CONVERGED, break
```

**LLM calls this pass: 1** (M-6 framing). Eight sites available, one fired.

---

## Three weeks later — where today's system breaks

Maya writes:

> *"Hey — we signed the 1-year renewal yesterday, all sorted. Thanks for the nudge!"*

### What happens today

```
new event -> lands on the open situation
          -> last_seen_at bumped
          -> decide_lifecycle:  terminal_by_fact?  deal.stage is not closedwon
                                                   (this is a contract, not a deal)
                                -> FALSE
                                -> resolved_by_human?  nobody clicked
                                -> gone_quiet?  no, activity is RECENT
                                => STATUS_ACTIVE

RESULT: the situation looks MORE alive than before.
        The founder is nudged again tomorrow about a renewal that is signed.
```

**This is Globe's named credibility failure, reproduced exactly:** *"It told me about a
contract I cancelled last week."*

### What happens in v2

```
L2.7.7 gate (deterministic, before any call):
    status == ACTIVE                    ✓
    new signal landed this drain        ✓
    terminal_by_fact == False           ✓
    -> M-4 FIRES  (T2)

L1 already extracted from this message:
    DecisionState(subject="renewal", state="made")     -> strong prior

M-4 returns:
    verdict        RESOLVED
    scope          renewal_decision            (scoped — not the whole situation blindly)
    speaker_role   owner                       (Maya owns Finance; weight 1.0)
    quote          "we signed the 1-year renewal yesterday"
    offsets        [18, 58]
    confidence_bp  8700

Deterministic validation:
    span verifies against source (ALG-08 reused)        ✓
    speaker authority: owner, weight 1.0                ✓
    "signed ... yesterday" is a COMPLETION, not an intent  ✓  (edge case 1)
    confidence 8700 above floor                          ✓

APPLY:  status = RESOLVED
        resolved_by = RESOLVED_BY_STATEMENT
        resolution_evidence = the span
        -> reversible: re-derived every pass, un-resolves if contradicted

RESULT: the situation closes. No further nudge.
        And if Maya writes next week "actually finance blocked it",
        M-4 returns CONTRADICTED and it reopens.
```

**LLM calls this pass: 1** (M-4). And that single call is the difference between a system
that understands and a system that nags.

---

## What this example demonstrates

| Claim | Where it shows |
|---|---|
| **Gating works.** 8 LLM sites available, 1 fired per pass | M-1/2/3/5/8 all skipped — the cascade was conclusive |
| **Pattern discovery needs no model** | trend + cohort + anomaly, all integer arithmetic |
| **The analytic stratum is what makes patterns declarable** | conditions 6–7 of the pattern only exist because L2.4 does |
| **Typed absence is load-bearing** | `GENUINELY_ABSENT` licensed a claim; `UNKNOWABLE` licensed nothing |
| **Importance actually varies** | 10000, not 5000 — and every term is stored |
| **`max` not `mean`** | 8100 base from the strongest signal, not the average of four |
| **Coverage is honestly discounted** | confidence vector `coverage 6200` because Zendesk is missing |
| **Resolution is the difference between understanding and nagging** | the three-weeks-later trace |
| **Convergence terminates** | 3 passes, hash-checked |

---

## Cost of this example

| Pass | LLM calls | Tier |
|---|---|---|
| Initial drain | 1 (M-6 framing) | T2 |
| Subsequent drains, situation unchanged | **0** — member-set hash unchanged, cache hit | — |
| Three weeks later, resolution message | 1 (M-4) | T2 |

**Two T2 calls across three weeks for a situation worth \$84,000 to get right.**

That ratio is the argument for the architecture — and, per doc 11, it is a ratio that must
be **measured on a pilot**, not asserted from an example.
