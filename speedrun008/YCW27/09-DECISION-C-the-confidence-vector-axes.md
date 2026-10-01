# DECISION C · the ConfidenceVector axes — measured, so the decision is one word

> **Date:** 2026-10-01. This is `02-DECISIONS.md` #1, the last of the four that is still open and
> still matters. It is also the only thing standing under Atlas cell **L2-07**.
> **Nothing is blocked on it** — all six layers were built without it — but it is the one open
> decision with a measurement under it rather than a preference.

---

## THE CONFLICT, AS STATED

| | Axes |
|---|---|
| **The code** | `evidence` · `freshness` · `consistency` · `identity` · `coverage` · `analytic` |
| **The Atlas** | `evidence` · `frame` · `temporal` · `causal` · `authority` · `coverage` |

Two overlap exactly (`evidence`, `coverage`). One is the same thing under another name
(`temporal` ≈ `freshness`). **Three on each side have no counterpart.**

---

## PART 1 · WHAT THE CODE'S SIX ACTUALLY ARE — and the law over them

`contracts/situation.ConfidenceVector`, and the law is the interesting part:

> *"Six axes, each of which may honestly have **NO basis**, plus the composed number. `overall_bp`
> is **bounded by the weakest axis** that went into it. Composition is otherwise a machine for
> manufacturing certainty: several weak axes agreeing is not corroboration, and a mean over them
> produces a number larger than anything it was computed from."*

Each axis is `int | None`, and `None` means *no basis*, never zero:

    evidence_bp      are the receipts real and plural?            event count x source count
    freshness_bp     how old is the newest thing we know?         None is NOT stale
    consistency_bp   do the sources agree?                        open discrepancies
    identity_bp      are we sure these are the same people?       open merge proposals
    coverage_bp      did we see enough to be talking about this?  None = COVERAGE_UNKNOWN
    analytic_bp      how good are the comparative inputs?         None = no comparative claim

And `composed_from` stores **which** axes went in — *"because 'we left freshness out because we
could not measure it' and 'freshness was fine' are different facts that an inferred rule would
collapse."*

---

## PART 2 · THE MEASUREMENT THAT DECIDES IT

### The code's six are not a proposal. They are six populated columns.

    context_situations                459 situations stored
      confidence_evidence             459 non-null
      confidence_freshness            459 non-null
      confidence_consistency          459 non-null
      confidence_identity             459 non-null
      confidence_analytic             459 non-null
      confidence_overall              459 non-null
      coverage                        459 non-null

### Two of the Atlas's three new axes are not implemented anywhere.

    frame_bp        0 references in the engine
    causal_bp       0 references in the engine
    authority_bp   39 references  — but see below, and it is a trap

> ⛔ **So "adopt the Atlas's axes" is not a rename.** It would replace four axes computed and
> persisted on every one of 459 rows with three for which nothing in the product computes a number,
> and it would leave `identity`, `consistency` and `analytic` with nowhere to go. That is not a
> vocabulary change; it is discarding working measurements in favour of unimplemented ones.

### ⛔ AND `authority_bp` LOOKS LIKE A FREE WIN. IT IS NOT.

The one Atlas axis with code behind it has **three different meanings in three places**, and none of
them is the one L2-07 asks for:

    actor_authority_bp                   capture/validate/authority.py  — is the SENDER senior?
                                         "whether the sender is the CFO or a no-reply robot"
    graph_facts.source_authority
    graph_facts.authority_rank           6,253 rows — which SOURCE wins a conflict?
    situation_resolution_claims
      .authority_bp                      529 rows — how authoritative is this CLAIM of resolution?

L2-07's complaint is *"role/source-readiness **completeness** is not part of the blocking vector"* —
a property of the **situation**, not of a sender, a source or a claim. Composing an axis out of the
three above would conflate three measures that answer three questions. **It would be a number that
looks like authority and means nothing in particular**, which is the exact failure the
weakest-axis law exists to prevent.

---

## PART 3 · THE RECOMMENDATION — A, and the reason is arithmetic

**Keep the code's six axes. Correct the Atlas.**

* `temporal` → it is already there, called `freshness`. **A naming correction in the Atlas.**
* `frame`, `causal` → nothing computes them and nothing is waiting on them. **Drop from the Atlas
  until something does**, or keep them as a stated future axis with nothing claimed.
* `identity`, `consistency`, `analytic` → computed on 459 of 459 rows. **The Atlas should carry
  them**, because they are what this system actually measures.

### ⛔ But the Atlas's one substantive point stands and is NOT closed by option A

L2-07 is right: **situation readiness is not in the blocking vector.** A situation can carry a high
`overall_bp` while the sources that would have confirmed it were never connected. That is a real
gap, it is not solved by any existing `authority_bp`, and it would need its own axis computed from
`capture/coverage`'s readiness model.

**That is a build, not a decision**, and it changes behaviour — a seventh axis would bind
`overall_bp` through the weakest-axis law, so some situations would correctly become less
confident. It should be its own unit, after this decision, and it is the honest way to close L2-07.

---

## WHAT IS NEEDED FROM ROHIT — one word

| | Option | Consequence, measured |
|---|---|---|
| **A** ← recommended | keep the code's six, correct the Atlas | zero code change · zero migration · the Atlas gains three axes it does not currently name and loses two nothing computes |
| **B** | adopt the Atlas's six | a migration over 459 rows · four computed axes deleted · `frame` and `causal` null on every row from day one · `authority` conflated from three unrelated measures |
| **C** | keep both vocabularies, map between them | two names for one number, in a structure whose whole purpose is that a reader can tell *no basis* from *measured zero*. The mapping would be the fourth vocabulary in a system that already documents four |

**Say "A" and I will correct the Atlas's cell and close `02-DECISIONS` #1.** The readiness axis then
becomes a named unit with its own crosscheck, which is how L2-07 actually gets closed rather than
renamed.
