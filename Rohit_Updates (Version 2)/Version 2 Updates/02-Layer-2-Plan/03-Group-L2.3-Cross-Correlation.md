# L2.3 — Cross-Correlation Engine

**Group responsibility:** connect what no single tool can connect.

**Group law:** *Correlation answers one question — do these belong to the same thing?
It does not prioritise, score risk, or recommend.* **LLM forbidden.**

**Package:** `genios_engine/context/correlation.py`
**Status:** **2 of 8 built.** The three missing ones are each load-bearing.

---

## Component map

| # | Correlator | BLG | Status | Evidence |
|---|---|---|---|---|
| L2.3.1 | Cross Tool | BLG-01 | ✅ | `correlate_event`, `choose_anchors` |
| L2.3.2 | Cross Conversation | — | ✅ | `thread_correlations` |
| L2.3.3 | Cross User | — | ⚠️ | `lift_people_to_their_companies` — a lift, not role synthesis |
| **L2.3.4** | **Cross Timeline** | **BLG-06** | ❌ | **MISSING** |
| L2.3.5 | Cross Resource | — | ⚠️ | `lift_companies_to_their_deals`; no contract↔spend |
| L2.3.6 | Cross Domain | — | ⚠️ | `resolve_domain`; degraded-carry unverified |
| **L2.3.7** | **Cross Organization** | — | ❌ | **MISSING** |
| **L2.3.8** | **Dependency Correlation** | **BLG-05** | ❌ | **MISSING** |

---

## An honest note about this group

Globe calls this *"probably the biggest moat"*. It is also worth stating plainly what
these eight components are and are not.

**Every one of Globe's eight correlators is a JOIN.** *"Do these belong to the same
thing?"* Not one computes a **comparison across a population**. That is why the founder's
*"these 3 leads share traits with your highest-LTV customers"* has no home here — and why
**L2.4, the Analytic Stratum, exists as a separate group.**

Correlation assembles the subject. The analytic stratum compares it to others. Both are
needed; conflating them is how the moat gets over-claimed.

---

# ❌ L2.3.8 · Dependency Correlation (BLG-05) — highest value of the three

### L2.3.8-U1 · Blocking chain construction

**WHAT** — Builds `A blocks B blocks C` chains from `Dependency` claims.

**WHY** — Globe: *"what makes deadlines more than a calendar."* Without it, Deadline
Intelligence degrades to a reminder app — which Globe itself names as that surface's
failure mode: *"'Deadline tomorrow' is the calendar's job and adds nothing."*

It also feeds two things directly:
- **L2.7.4 modifier 3d** — *N items blocked on this* is an importance term. The cost of an
  unresolved decision is the blocked work, not the decision.
- **L4's Dependency unit** — currently has no chain to reason over.

**Input is now available:** L1 v2's `ExtractionResult.dependencies[]` carries
`blocker · blocked · dependency_type · evidence`. Today nothing consumes it.

**WHERE** — `genios_engine/context/correlation_dependency.py`

**HOW** (BLG-05)
```
1. EDGES      materialize each Dependency claim as a typed graph edge
              (blocker) --blocks[type]--> (blocked)
2. RESOLVE    both endpoints through identity (L2.2.4) so "Finance" and
              "finance@acme.ai" are one node
3. CHAINS     depth-first from each unblocked root, max depth 6
              (deeper than 6 is almost always an identity-resolution error)
4. CYCLES     detect circular waits -> emit a `circular_wait` observation.
              A is waiting on B and B on A is itself intelligence — Globe's
              Ownership surface is built on exactly this
5. MISSING    a dependency whose blocker node does not exist
              -> `missing_prerequisite` observation
6. COUNT      blocked_count per node -> written as a derived fact for L2.7.4
```

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Bad identity resolution creates false chains | phantom blocking | endpoints resolved through the same identity cascade as everything else; unresolved endpoint -> no edge |
| Resolved dependency stays in the chain | nagging about done work | dependency edges carry `resolved_at`; chains read only unresolved |
| Depth explosion | expensive traversal | max depth 6, and a depth-6 chain is flagged as a likely identity defect |

**ACCEPTANCE**
```
pytest tests/context/test_dependency_correlation.py -q
# A->B->C builds one chain of 3
# A->B, B->A emits circular_wait
# a dependency on an unknown node emits missing_prerequisite
# blocked_count is written as a derived fact
# a resolved dependency drops out of the chain
```

**REVERSE PROMPT**
```
TASK: Build dependency correlation. This is what makes a deadline more than a calendar.
FILE: genios_engine/context/correlation_dependency.py

INPUT NOW EXISTS: L1 v2 emits ExtractionResult.dependencies[] with
blocker/blocked/dependency_type/evidence. Nothing consumes it today.

ALGORITHM: the 6 ordered steps in doc 03 section L2.3.8-U1.

HARD RULES:
1. Resolve BOTH endpoints through the existing identity cascade (context/identity.py).
   An unresolved endpoint produces NO edge — never a guessed one. A false blocking chain
   is worse than a missing one because it nags a real person about phantom work.
2. Max chain depth 6. A deeper chain is almost always an identity-resolution error;
   flag it as such rather than traversing further.
3. Circular waits are OUTPUT, not errors. Emit a circular_wait observation — "A waits on
   B, B waits on A" is exactly the Ownership intelligence surface.
4. Dependency edges carry resolved_at. Chains read only unresolved edges.
5. Write blocked_count per node as a derived fact — L2.7.4 modifier 3d consumes it.
6. PURE traversal. The graph read is injected; the algorithm takes nodes and edges.

TEST tests/context/test_dependency_correlation.py — every row in the ACCEPTANCE list,
plus a 10-deep chain that stops at 6 and flags.
```

---

# ❌ L2.3.4 · Cross Timeline (BLG-06)

### L2.3.4-U1 · Dormant condition satisfaction

**WHAT** — Detects when a condition someone stated months ago has now been met.

**WHY** — This is Globe's **Opportunity Intelligence** surface, and it is the one Globe
calls *"the surface people remember"*: *"a partner said they'd revisit once you had two
enterprise references. You closed the second 11 days ago."*

It is also, of Globe's fifteen Admin surfaces, **the closest to the founder's own
register** — forward-looking, revenue-adjacent, and genuinely non-obvious because the two
events are months apart and no human is holding both in mind.

**HOW** (BLG-06)
```
1. STORE      a Commitment with is_conditional=true and condition_text
              (L1 v2 already extracts both) becomes a DORMANT CONDITION node
2. INDEX      parse the condition into a checkable predicate where possible:
                 "two enterprise references"  -> count(account.segment=enterprise) >= 2
                 "after funding closes"       -> exists(event: funding_closed)
                 unparseable                  -> stored, checked by human review only
3. SWEEP      on each drain, re-evaluate every open dormant condition against the
              CURRENT graph
4. SATISFY    newly true -> emit condition_satisfied with BOTH evidence spans:
              the original statement AND the satisfying fact
5. HALF-LIFE  a satisfied condition decays: full strength 30 days, then declines.
              Globe: "a satisfied condition has a short half-life — act while the
              evidence is fresh"
```

**Step 4's two-span evidence is the whole point.** The card must show the sentence from
May *and* the fact from August. Either alone is unconvincing.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Rhetorical condition matched | nagging about a throwaway line | only `is_conditional` commitments with a parseable predicate auto-fire; the rest are review-only |
| Already handled offline | stale suggestion | a dismissal here is recorded as `already_handled`, a coverage signal, **not** as `wrong` |
| Condition never becomes checkable | silent accumulation | unparseable conditions surface in a review queue, not in cards |

**ACCEPTANCE** — a conditional commitment from 4 months ago, whose predicate the current
graph now satisfies, emits `condition_satisfied` carrying **both** evidence spans; an
unparseable condition never auto-fires.

---

# ❌ L2.3.7 · Cross Organization

### L2.3.7-U1 · Same party, different context

**WHAT** — The same external party appearing as vendor, customer, investor and advisor.

**WHY** — Globe names the client-scope boundary as a **data-leak class** blocker: four
customer types cannot be safely onboarded until the scope model can express their
separation. This is that separation.

**HOW** — one identity, N context-scoped role edges. The identity merges; the **contexts
do not**. A fact learned in the vendor context must not surface in the investor context
unless visibility permits.

**This is a safety component before it is an intelligence component.** Build it with
`c63def1`'s subject-exclusion visibility, and test the negative case first: a fact from
context A must **not** appear in context B.

---

## Existing correlators — what must not regress

| Component | Preserve |
|---|---|
| L2.3.1 Cross Tool | **The tenant node is deliberately excluded from `ANCHOR_PRIORITY`.** Without that exclusion a tenant node reachable from correspondence swallows every conversation in the org into one situation. Subtle, correctly pre-empted, easy to break |
| L2.3.2 Cross Conversation | `thread_correlations` + `joins_window` / `merged_span` |
| L2.3.3 / L2.3.5 | the lift functions; extend rather than replace |

---

## Group acceptance gate

```
pytest tests/context/test_correlation.py tests/context/test_dependency_correlation.py -q
grep -rn "LLMClient\|anthropic" genios_engine/context/correlation*.py    # no matches
```

| Metric | Gate |
|---|---|
| dependency chains built on a pilot tenant | > 0 |
| circular waits detected and emitted | reported |
| conditions stored as dormant | > 0 |
| a fact from one org-context leaking into another | **0 — safety gate** |
| tenant node appearing as a correlation anchor | **0** |
