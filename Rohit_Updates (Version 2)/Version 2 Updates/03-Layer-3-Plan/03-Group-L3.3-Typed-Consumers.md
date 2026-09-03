# L3.3 — Typed Consumers (the weld fix)

> **The one big piece of new code in Layer 3, and the prerequisite for flipping the
> switch.** Today 446 of 712 knowledge artifacts (63%) have no runtime reader, and the
> adapter's own docstring warns what happens without this work: *"activation would LOOK
> successful while producing generic output."*

**Group responsibility:** every artifact class the corpus carries gets a typed consumer
at the L3→L4 seam — or a named, counted reason it has none.

**Package:** `genios_engine/reason/adapters/` (extending `expertise.py`)
**LLM sites:** **zero** — this is compilation and binding, all deterministic.

---

## The inventory being unlocked

| Class | Count | Today | New consumer |
|---|---|---|---|
| playbooks | 227 | plays, **alphabetical cap 4** | CLG-07 selection-aware cap |
| **rules** | 46 | `no_steps_artifact_unsupported` | **CLG-06 → `core.constraint` checks** |
| **heuristics** | 280 | skipped | **CLG-08 → citations** |
| mental-models | 61 | skipped | CLG-08 → framing blocks |
| decision-frameworks | 59 | skipped | CLG-08 → framing blocks |

What survives and must not regress: the **receipts**. Every refusal today is counted with
a reason (`skipped[rule_id] = ...`). The new consumers extend that receipt, never replace it.

---

# L3.3-U1 · Rule compiler (CLG-06)

**WHAT** — Compiles authored `rules/` (typed when/then, `severity`, `enforced_by:
L4_constraint`) into `core.constraint` checks the Decision Maker already runs.

**WHY** — The corpus carries 46 rules like
`urgency-must-belong-to-the-buyer.yaml` with `severity: blocking` — and **no parser
exists**, so "blocking" rules block nothing. Prescriptions can violate the corpus's own
doctrine today. This is the E5 gap: a card cannot say *"do X **because** <expert rule>"*
if the rule never reaches the decision.

**WHERE** — `genios_engine/reason/adapters/rule_compiler.py`

**HOW** (CLG-06)
```
1. PARSE     the rule's when/then blocks are already machine-predicated YAML —
             parse into the same predicate tree grammar as L2 cohorts
             (operators whitelist; no free evaluation)
2. BIND      `when` predicates bind against the ExpertisePackage's situation slice
             (three-state: TRUE / FALSE / UNKNOWN — reuse the Context Adapter's verdicts)
3. EMIT      severity: blocking  -> a HARD check in core.constraint:
                                    a candidate violating it is eliminated,
                                    with the rule id in alternatives_rejected
             severity: warning   -> a recorded caution on the DecisionObject
4. UNKNOWN   a rule whose `when` evaluates UNKNOWN does not fire and does not block —
             it is recorded as `rule_unevaluable` with the missing predicate named.
             An unevaluable blocking rule must never silently pass OR silently block.
5. RECEIPT   per package: rules_compiled / rules_fired / rules_unevaluable / rules_skipped
```

**FAILURE MODES**

| Case | Mitigation |
|---|---|
| an unparseable when/then | `rule_parse_failed` receipt + validate.py check so it is caught at authoring, not at runtime |
| a blocking rule fires on UNKNOWN inputs | step 4 — three-state, never coerced |
| two rules contradict | both fire; contradiction surfaces on the decision as a named conflict — L4 abstains rather than picking silently |
| rule references an object the package didn't load | `rule_unevaluable(missing_object)` — and the registry's load-set gets the object added |

**ACCEPTANCE** — the `urgency-must-belong-to-the-buyer` fixture eliminates a violating
candidate and the elimination names the rule; the same rule with an UNKNOWN predicate
neither fires nor blocks and is receipted; a warning-severity rule annotates without
eliminating.

**REVERSE PROMPT**
```
TASK: Compile authored corpus rules into core.constraint checks.
FILE: genios_engine/reason/adapters/rule_compiler.py

THE GAP: Domain Expertise carries 46 rules/ artifacts with typed when/then and
severity: blocking, enforced_by: L4_constraint — e.g.
"Domain Expertise/Sales Expertise/rules/closing/urgency-must-belong-to-the-buyer.yaml".
No parser exists. Blocking rules block nothing.

IMPLEMENT the 5 steps in doc 03 section L3.3-U1.

HARD RULES:
1. Predicate grammar = the same whitelisted operator tree as L2 cohorts. No eval(), no
   free expressions.
2. THREE-STATE binding. UNKNOWN neither fires nor blocks; it is receipted as
   rule_unevaluable with the missing predicate named. Coercing UNKNOWN either way is the
   bug this codebase has spent months avoiding — do not reintroduce it.
3. severity: blocking -> candidate elimination recorded in alternatives_rejected with
   the rule id and the quote. severity: warning -> annotation only.
4. Contradicting rules -> both recorded, decision abstains; never silently pick one.
5. Extend the existing receipt dict in reason/adapters/expertise.py; do not replace it.
6. PURE. No LLM, no DB writes beyond the package metadata.

TEST tests/reason/adapters/test_rule_compiler.py — every ACCEPTANCE row in doc 03,
plus: an unparseable rule fails validate.py at authoring time.
```

---

# L3.3-U2 · Citation binder (CLG-08)

**WHAT** — Attaches heuristics (280), mental-models (61) and decision-frameworks (59) to
the `DecisionObject` as **citation material**: id + statement + evidence pointer.

**WHY** — E5: every prescription must carry auditable reasoning. Today the "why" bottoms
out at play steps. The expert claim that turns a fact into advice — *"warmth is close to
uncorrelated with intent"* — is retrieved, hashed, and discarded. Cards read as facts
with a verb because the expert voice never travels.

**HOW**
```
1. SELECT   heuristics whose capability matched the situation AND whose declared
            applicability tags intersect the fired pattern's conditions —
            deterministic tag intersection, not similarity
2. CAP      max 5 citations per decision, ranked by (capability match, tag overlap
            count, artifact recency) — deterministic sort, receipted truncation
3. ATTACH   DecisionObject.citations: (artifact_id, class, statement, source_ref)
4. RENDER   L5's card render receives citations as OPTIONAL material with the same
            span discipline: the statement is quoted verbatim from the artifact,
            never paraphrased by the model
5. FRAMING  mental-models / frameworks attach as framing_blocks for the L4
            explanation renderer — input material, never new claims
```

**ACCEPTANCE** — a compiled decision in a matched capability carries >= 1 citation with a
verbatim statement and source ref; truncation beyond 5 is receipted; a card render that
includes a citation quotes it byte-identically.

---

# L3.3-U3 · Selection-aware play cap (CLG-07)

**WHAT** — Replaces the alphabetical `candidates[:MAX_PLAYS]` cut with a ranked selection.

**WHY** — Today which plays survive the cap depends on **rule-id sort order**. The cap
itself is legitimate (the Decision Maker ranks a small candidate set); alphabetical
selection is not.

**HOW**
```
rank plays by:  1. situation-fit — play's declared situations include the fired one
                2. capability admission recency (re-stamped = maintained)
                3. authored priority within the capability, if declared
                4. rule id (final deterministic tie-break — LAST, not first)
keep MAX_PLAYS; receipt the truncated with over_play_cap as today
```

**ACCEPTANCE** — a situation-fit play beats an alphabetically-earlier generic play; the
sort is byte-stable across runs.

---

## Group acceptance gate

```
pytest tests/reason/adapters -q
python scripts/weld_report.py --org <pilot>
```

| Metric | Gate |
|---|---|
| artifact classes with a typed consumer | **5 of 5** |
| `no_steps_artifact_unsupported` receipts on rules/heuristics/models/frameworks | **0** (replaced by their own consumers' receipts) |
| a blocking rule eliminating a candidate on the pilot | **>= 1**, named in `alternatives_rejected` |
| a decision carrying a heuristic citation | **>= 1** |
| UNKNOWN-predicate rules silently passing or blocking | **0** |
| LLM calls in this group | **0** |
