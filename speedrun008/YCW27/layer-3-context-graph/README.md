# L3 · Context Graph — `context/`

**118 files · 49,713 lines — the largest package.** Milestone **M10**, 5 units.

> What does the company now know, and how is it connected?

In code this package is called **Situation Intelligence**, deliberately: *"the old name says where
the layer sits, and this layer's output is a SITUATION — assembled, judged by eight admission laws,
and exposed only if admitted. Describing it as a graph builder is how a card came to be wired to a
signal while the situation layer was bypassed."*

---

## The two graphs

| | Evidence Graph | Intelligence Graph |
|---|---|---|
| holds | what **sources** said | what **we** concluded |
| tables | `graph_nodes` · `graph_facts` · `graph_edges` + 7 more | ⛔ **none of its own** — a foreign-key chain |
| visible to a founder | yes — the graph canvas | no, deliberately |
| ranks its claims | yes — `authority_rank` | no — *"we have no rank over ourselves"* |

```
context_situations.situation_id
  ├→ situation_interpretations   (0183)
  └→ signals.situation_id        (0182)
        └→ signals.reasoning_decision_hash   (0031, FK)
              └→ executions.decision_hash    (0041)
                    └→ execution_outcomes.decision_hash
```

**Nothing deletes a signal** — 0 hard deletes, 12 status updates — so the chain cannot die. Keep it
that way: unknowns, expectations and decision needs become **typed fields on interpretations**,
never new tables.

---

## What it owns

| Area | Modules |
|---|---|
| graph core | `graph_store.py` (69 KB) · `merge.py` · `identity.py` · `canon.py` |
| correlation | 10 `correlation*.py` · 5,234 lines — **joins only** |
| situations | `situations.py` · `situation_bso.py` (124 KB) · `situation_publisher.py` |
| readings | `outreach_situations.py` (119 KB) · `support_situations.py` (101 KB) · meeting/condition/blocker |
| scoring | `importance.py` (78 KB) · `attention.py` · `conversion.py` |
| analytic | `analytic/` — trend, anomaly, cohort, peer baseline, comparator |
| quality | `quality/` · `residue.py` · `window.py` · `lane_health.py` |
| model-gated | `angles/` — four angles, each on a queue the rules refused |
| the spine | `runner.py` (105 KB) · `pipeline.py` (133 KB) |

**The group law for correlation:** *"correlation answers one question — do these belong to the same
thing? It does not prioritise, score risk, or recommend."* Every correlator is a **join**. Not one
computes a comparison across a population — that is why `analytic/` is a separate group.

---

## Measured today

| | |
|---|---|
| Active situations on the pilot | **66** (admin 53 · support 8 · fundraising 4 · sales 1) |
| Admitted vs held | **223 admitted · 467 held** |
| Top hold reasons | `verified_evidence_required` 398 · `qes_required` 398 · `source_coverage_insufficient` 69 |
| Shadow pass | 39 compiled · 39 reasoned · 19 admission_hold · 5 no_route · 3 incomplete |
| Model angles | 4, each gated on a deterministic refusal |

⛔ **467 held against 223 admitted is the largest thing in Layer 2** — not the fundraising route,
which is 4 of 66.

The sweep runs as a **cycle**: state situations → residue → angles → readings again → re-rank.
Four readings consume something written after their first run, so a **second pass** is required
rather than a reordering — reordering would break the coverage measurement residue depends on.

---

## What changes — M10

### `M10.C1` The bounded query API

| Unit | What |
|---|---|
| `U01` | the read request — seeds, allowed edges, states, window, max hops, max nodes, unknowns, contradictions, the asking seat's visibility. **Bounded by default** |
| `U02` | the bounded reader — one capped traversal, returning the revision it read |
| `U03` | compare-and-set on write — a run that read revision N cannot overwrite N+1; the loser is re-queued, never merged blindly |

### `M10.C2` A hold that asks

| Unit | What |
|---|---|
| `U04` | `situation_publisher`'s HOLD raises the `EvidenceNeed` that would clear it |
| `U05` | a met need clears its hold next sweep; an unavailable one closes it with a reason |

⛔ HOLD's existing rule must survive: only **recoverable** incompleteness is held. An absence no
future sweep can repair is not held, and on HOLD and REJECT the `situation` field is `None` so no
caller can publish by reaching through.

## Open

`context/` spans product L2 **and** L3 — decision 4. Until that is settled, M10 and M11 must not be
scheduled in parallel: both would edit this package.

## Read these first

`context/situation_publisher.py` · `context/residue.py` · `context/quality/window.py` ·
`context/runner.py` (the sweep's ordering comments)
