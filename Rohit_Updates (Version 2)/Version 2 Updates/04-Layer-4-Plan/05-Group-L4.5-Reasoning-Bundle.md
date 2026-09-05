# Group L4.5 — The Reasoning Bundle (**the voice**) — the centerpiece

> **The founder's instruction:** *"reasoning wala part — content achha rahe, context achha
> rahe. Otherwise, without reasoning, cheezein polish nahi hongi, aur user ke saamne
> detail jaana chahiye."*
>
> This group is that instruction, made into a type with a validator.

---

## 1. Why this is a new group

Globe's L4.4.7 has a *Reasoning Trace* — an audit artifact for engineers. It does not
have a **customer-facing reasoning narrative**, because when Globe was written the
explanation was one sentence. The founder's bar is higher than the spec here, so v2 adds
a group rather than stretching an existing component.

**The wall today** — `intelligence.py`'s explanation validator enforces: **one sentence ·
no directives · no numbers · grounded in retrieved text**. The grounding discipline is
excellent and stays. The three caps make the founder's card **structurally impossible**:

```
WHY THIS MATTERS   -> needs a consequence claim        (blocked: needs numbers)
ROOT CAUSE         -> needs a causal claim             (blocked: one sentence)
RECOMMENDATION     -> needs an instruction             (blocked: no directives)
EXPECTED EFFECT    -> needs a quantified projection    (blocked: no numbers)
```

**The resolution:** the caps exist because, today, the sentence is generated *about* a
decision the model can see but not verify. v2 removes the reason for the caps — the
decision is fixed and typed first, every number is substituted by code, every claim is
bound to an evidence id — and then replaces the caps with a stricter, structural gauntlet.

---

## 2. The contract

```python
@dataclass(frozen=True)
class ReasoningBundle:
    decision_id: str
    action_id: str                    # V-3: MUST equal the decision's action id
    headline: str                     # <= 90 chars, the card title
    situation_summary: str            # what is happening
    why_it_matters: str               # the consequence, with templated numbers
    root_cause: str                   # the causal chain, evidence-bound
    recommendation_rationale: str     # why THIS action, over the alternatives
    expected_effect: str              # what changes if acted on; do-nothing contrast
    alternatives_narrative: str | None
    citations: tuple[Citation, ...]        # L3 corpus, byte-identical spans
    evidence_refs: tuple[str, ...]         # every claim traces to one
    numbers_used: Mapping[str, int]        # placeholder -> computed value (bp/whole)
    generation: str                        # 'llm:<model>@<version>' | 'template_fallback'
    bundle_hash: str
```

**`numbers_used` is the mechanism, not a note.** The model writes
`"{do_nothing_cost}"`, never `"$84,000"`. Code substitutes from computed values after
generation. A model that types a digit fails V-4 and the bundle is regenerated once, then
falls back to template.

---

## 3. The R-sites in operation

| Site | Input | Output | Tier | Cache key |
|---|---|---|---|---|
| **R-1** interpreter | an UNRESOLVED ambiguity flag on a fact the plan reads | `{classification, confidence_bp, span}` → **a Finding, consumed as evidence** | T2 | fact digest |
| **R-2** narrator | the **fixed** DecisionObject + Findings + citations | the five prose fields, with placeholders | T2 | `decision_hash` |
| **R-3** alternatives | `alternatives_rejected` + tradeoff evidence | `alternatives_narrative` | T1 | decision + candidate set |
| **R-4** effect framing | `do_nothing` + foresight numbers | `expected_effect`, placeholders only | T1 | folded into R-2's call |
| **R-5** consult | thin evidence, after DEFER is chosen | a targeted interpretation, **non-authoritative** | T2 | situation digest |

**R-1 is the Theory chat's law, verbatim.** *"Considering moving some workloads"* is
ambiguous; the model returns `{classification: EVALUATING_ALTERNATIVES,
confidence_bp: 7000}` **as evidence**; `core.risk` reads it like any other input; the
formula decides. The model never says "this is urgent."

---

## 4. The validation gauntlet (V-1 … V-7)

Run in order. Any failure → one regeneration → deterministic template. Every outcome is
recorded on the trace.

| # | Check | Fails when |
|---|---|---|
| V-1 | **Grounding** | a claim has no `evidence_ref` or citation |
| V-2 | **Citation fidelity** | a quoted corpus span is not byte-identical (L3's validator, reused) |
| V-3 | 🔴 **Decision fidelity** | `bundle.action_id != decision.action_id` — **constructor-level reject** |
| V-4 | **No raw numbers** | a digit appears in prose outside a `{placeholder}` |
| V-5 | **Placeholder resolution** | a placeholder has no entry in `numbers_used` |
| V-6 | **Scope** | prose names an entity absent from the situation |
| V-7 | **Length/shape** | a field exceeds its cap or is empty |

**V-3 is the doctrine's enforcement point.** It is the reason a model can write freely
here without ever being able to change what the company does.

---

## 5. What the customer finally sees

```
RENEWAL AT RISK · Northwind Traders · $84,000 · 11 days out          [confidence 78%]

WHY THIS MATTERS
  The renewal is 11 days out and the buying committee has gone quiet for 14 days,
  against a 6-day cadence for this account. $84,000 of ARR is exposed.

ROOT CAUSE
  Engagement dropped after the 3 Feb pricing thread. The economic buyer has not
  replied since; only the champion is active, and no alternative contact is warm.

RECOMMENDATION
  Send the renewal-risk outreach to the economic buyer today, referencing the
  pricing thread directly.
  Why this and not a discount offer: the corpus's blocking rule
  "no unapproved discount above 10%" eliminated the discount play, and the
  cost-vs-benefit axis favours outreach by 1,900 bp.

EXPECTED EFFECT
  Acting today restores the cadence before the decision window closes.
  Doing nothing: exposure compounds at roughly $2,800/day to renewal.

  Sources: 4 evidence items · Admin corpus rule ADM-014 · situation SIT-2291
```

Every bold number came from `numbers_used`. Every clause traces to an evidence id or a
citation. The decision that produced it was made by the formula in doc 04, before a single
word existed.

---

## 6. Fallback — the honest plain version

When generation fails, budget is exhausted, or the gauntlet rejects twice:

```
Renewal in 11 days · engagement gap 14 days vs 6-day cadence · $84,000 exposed.
Recommended: renewal-risk outreach to the economic buyer.
Alternatives eliminated: discount play (rule ADM-014).
Doing nothing: ~$2,800/day exposure to renewal.
[generation: template_fallback]
```
Plainer, **never less true** — and labelled, so nobody mistakes a fallback for a narrative.

---

## 7. Failure modes

| Mode | Guard |
|---|---|
| Model contradicts the decision | V-3, constructor-level |
| Model invents a number | V-4 + placeholder substitution |
| Model invents a citation | V-2, byte-identical span check |
| Model narrates a suppressed decision | bundles are generated **only for published decisions** |
| Cost blowup | cached on `decision_hash`; daily per-org cap (doc 11) |
| Latency on the card path | bundles generate **after** publication, never in the decision's critical path |
| Prose drift across a re-run | cache + `bundle_hash`; regeneration is explicit |
| PII in prose | prose is bound to evidence the tenant already owns; no cross-tenant text ever enters a prompt |

---

## Group acceptance gate — **K4: the voice** 🔴

```
pytest tests/reason/test_bundle_gauntlet.py -q
python scripts/bundle_review.py --org <pilot> --sample 25
```

| Metric | Gate |
|---|---|
| published decisions carrying a bundle | **100%** |
| bundles contradicting their decision | **0** (V-3 makes it structural) |
| bare numbers in prose | **0** |
| citations byte-identical | 100% |
| `template_fallback` rate | **< 15%** |
| **≥1 pilot card with WHY / ROOT CAUSE / RECOMMENDATION / EXPECTED EFFECT + a real L3 citation** | **the founder-bar moment** |
| 25-bundle golden review | passes the 10-second test (doc 09) |
