# L3.4 — Admin Corpus V1

> **V1 activates the Admin domain first**, per Globe's own scope discipline. This
> document is the corpus work: route the unrouted, author the two missing Globe
> surfaces, defer what Globe never asked for, and stand up the two authoring-assist
> LLM sites.

**Corpus state (verified):** 57 capabilities · 10 categories · 14 situations ·
25 objects (20 core + 5 scoped) · `validate.py` = 0 errors · 153/153 admission-stamped
across all domains · **36/57 routed**.

---

## 1. The taxonomy mismatch, stated honestly

**The corpus was authored as an "admin department"; Globe's Admin is "founder operating
intelligence."** The overlap is strong — 12 of Globe's 15 surfaces have at least a
partial corpus home — but the corpus spends 10 capabilities on `facilities-and-assets`
and `travel-and-events` (which Globe never asked for) while Globe's #13 and #14 have
no home at all.

| Globe surface | Corpus home | Status |
|---|---|---|
| 1 Commitment | `executive_support.commitment_tracking`, `meeting_operations.action_item_tracking` | ✅ |
| 2 Follow-up / Relationship | `live_admin_contact` + `follow_up_coordination` | ⚠️ |
| 3 Deadline | `obligation_falls_due`, `statutory_filing` | ✅ |
| 4 Scheduling / Meeting | `meeting_operations.*` (5), `meeting_ahead` | ✅ strong |
| 5 Decision debt | `decision_waiting_on_a_person`, `approval_coordination` | ✅ |
| 6 Ownership | `delegation_and_task_routing` | ⚠️ U3 below |
| 7 Founder Bottleneck | `gatekeeping`, `approval_coordination` | ⚠️ U3 below |
| 8 Coordination | meeting ops partial | ⚠️ Globe: do NOT ship in V1 |
| 9 Process | `process_improvement`, `sop_management`, `service_level_management` | ✅ |
| 10 Document Integrity | `records_and_documentation.*` (5) | ✅✅ |
| 11 Vendor & Contract | `contract_and_vendor.*` (6), `vendor_relationship_live` | ✅✅ |
| 12 Financial Obligation | `finance_administration.*` (6), `money_owed_either_way`, `spend_against_a_commitment` | ✅✅ |
| **13 Goal & Progress** | — | ❌ **U2** |
| **14 Opportunity** | — | ❌ **U1** |
| 15 Risk | `compliance_and_governance.*` (6) | ⚠️ observation-only per Globe |

---

# L3.4-U1 · Author `admin.opportunity_tracking` — the missing flagship

**WHAT** — The capability behind Globe surface #14, *"the surface people remember"*:
*"a condition someone set four months ago is now met."*

**WHY** — Globe rates it V1-reachable on Gmail+Calendar alone, and it is the one Admin
surface written in the founder's own register (forward-looking, revenue-adjacent). Its
machinery is already planned: **L1 v2 extracts conditional commitments; L2 v2's BLG-06 +
M-5 detect satisfaction and emit `condition_satisfied`.** What is missing is the
capability that gives that signal an expert reading.

**Situations (new):** `admin.sit.condition_now_satisfied` · `admin.sit.dormant_commitment_reopenable`
**Knowledge to author:** heuristics — *"a satisfied condition has a short half-life — act
while the evidence is fresh"* (Globe's own line); playbook — reopen with the satisfying
evidence named; rule — never reopen from a `RELATIVE`-certainty satisfaction alone;
failure modes — rhetorical conditions, already-handled offline (dismissal =
`already_handled`, a coverage signal, not `wrong`).

# L3.4-U2 · Author `admin.goal_and_progress` — Globe #13

**WHAT** — Expected progress vs observed evidence, on a stated goal.

**WHY** — Globe: *"needs a goal to exist as data… if the founder has not stated a target
and a date, **ask once** and stay silent — never invent a benchmark."* The consuming
machinery exists in the L2 v2 plan (trends, baselines); the expertise reading is missing.

**Situations (new):** `admin.sit.goal_behind_pace` · `admin.sit.goal_has_no_evidence`
**Key rule to author:** no stated goal → the capability's only output is the one-time
ask. Silence after that. (This rule is `severity: blocking` — and thanks to CLG-06 it
will actually block.)

# L3.4-U3 · Sharpen Ownership + Founder Bottleneck

**WHAT** — Add the two findings Globe centers that the corpus only implies:
`work_item_unowned` (Ownership #6) and `approvals_converging_on_one_person`
(Bottleneck #7) as explicit situations on `delegation_and_task_routing` and
`gatekeeping`/`approval_coordination`.

**WHY** — Both read from things now built: typed absence (`GENUINELY_ABSENT` owner —
L2.5.5) and the L2.4 baseline (*"41/41 approvals under \$5K"* → the delegated-threshold
recommendation, which N-4 also distills into the Behavior brain). Globe's tone warning is
authored in as a rule: *lead with evidence and a structural fix, never a judgement about
a person.*

# L3.4-U4 · Route the 21 unrouted capabilities

**WHAT** — Every capability gets a door or a named reason it has none (the `fddb67d`
discipline, now applied to Admin).

**HOW** — For each of the 21: (a) map to an existing situation in the reverse index,
(b) author a missing situation if the capability is V1-relevant, or (c) mark
`routing: deferred` with a reason. Regenerate the index (`_tools/index.py`); hand-editing
the generated map stays forbidden.

**ACCEPTANCE** — `capabilities_routed + capabilities_deferred == 57`, each deferred row
carries a reason string; the registry regenerates cleanly.

# L3.4-U5 · Defer facilities-and-assets + travel-and-events (10 caps)

**WHAT** — Mark both categories `activation: deferred` for V1. **Not deleted** — the
knowledge is sound; it is out of Globe's V1 scope and out of the founder-intelligence
bar. They do not route, do not compile into packages, and do not count against
activation gates.

# L3.4-U6 · N-2 Review assist

**WHAT** — When a capability's content changes (admission hash invalidates), an LLM
pre-review runs the admission checklist — outcomes measurable? failure modes named?
KPIs typed? knowledge reachable? — and produces a review sheet. **A human accepts;
`admit.py` re-stamps.** The model never stamps.

**WHY** — 153 stamps exist; keeping them honest at scale is the work. This turns
re-review from a chore into a 5-minute confirmation, which is what makes the
invalidation mechanism sustainable instead of ignorable.

# L3.4-U7 · N-5 Gap authoring

**WHAT** — When a situation routes to **no** capability (the routing miss counter), N-5
drafts the missing capability skeleton — identity, question, outcomes, failure modes,
one playbook — schema-valid, `stub: true`, `admission` absent, for human completion.

**WHY** — The corpus counterpart of L1's open lane: the system can *name what it does not
know*. A draft is never compiled (no admission hash → resolver refuses); it exists to
make the authoring backlog concrete instead of invisible.

**Note on the 259 unauthored roster objects:** overwhelmingly CS-domain; Admin's own 25
objects are complete. The 259 stay a **CS-activation prerequisite**, tracked, not V1 work.

---

## Group acceptance gate

```
python "Domain Expertise/_tools/validate.py"        # stays 0 errors
python "Domain Expertise/_tools/index.py"           # regenerates
pytest tests/packs/test_admin_routing.py -q
```

| Metric | Gate |
|---|---|
| Admin capabilities routed or explicitly deferred | **57/57** |
| Globe surfaces with a corpus home (of the 13 in-scope for V1) | **13/13** (#8 Coordination and #15 Risk-prescriptive stay out, per Globe) |
| `opportunity_tracking` + `goal_and_progress` authored, stamped, routed | both |
| deferred categories compiling into packages | **0** |
| N-5 drafts that compiled without human admission | **0 — structurally impossible, test asserts** |
