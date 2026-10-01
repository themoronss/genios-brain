# Admin Expertise — the complete directory schema

**Measured 2026-09-27 against `Domain Expertise/Admin Expertise/`.**
**59 capabilities · 34 situations · 211 files under `capabilities/` · 403 YAML files total.**

> ⛔ **The headline is at the bottom, in PART 5.** The corpus has written down **210 signals it is
> waiting for**, each tagged with the layer that owns it. That is a roadmap it wrote for itself, and
> it is worth more than the rest of this document.

---

# PART 1 · THE TREE

```
Domain Expertise/Admin Expertise/
│
├── domain.yaml            301 lines  the domain's identity, subdomains, objects, glossary
├── deferrals.yaml         260 lines  ⛔ the named reason a capability has no door
│
├── capabilities/          211 yaml · 89 subdirs   ← 59 capabilities in 10 groups
│   └── <NN-group>/
│       └── <capability>/
│           ├── capability.yaml     the expertise
│           ├── knowledge.yaml      what knowledge attaches to it
│           ├── objects.yaml        the LOAD-SET
│           └── situations/         0–8 situation files (optional)
│
├── objects/               25 yaml   ⛔ the executable core — see PART 4
│   ├── core/              20        shared by more than one capability
│   └── <scoped>/           5        one capability each
│
├── heuristics/            60 yaml · 59 subdomains   one per subdomain, mostly
├── playbooks/             58 yaml · 58 subdirs      step-by-step procedures
├── models/                20 yaml · 11 subdirs      operating models
├── offerings/             15 yaml ·  4 subdirs      service shapes
├── rules/                  9 yaml ·  9 subdirs      hard rules
├── roles/                  1 yaml                  who answers for what
├── verticals/              1 yaml                  industry variants
└── registry/               1 yaml   ⛔ GENERATED — the situation↔capability map
```

## The ten capability groups

| group | capabilities | situations |
|---|---|---|
| `01-executive-support` | **8** | ⛔ **20** |
| `02-meeting-operations` | 5 | 3 |
| `03-records-and-documentation` | 5 | 1 |
| `04-compliance-and-governance` | 6 | 1 |
| `05-contract-and-vendor-administration` | 6 | 1 |
| `06-finance-administration` | 6 | 2 |
| `07-people-administration` | 6 | 1 |
| `08-facilities-and-assets` | 5 | 1 |
| `09-travel-and-events` | 5 | 1 |
| `10-admin-operations` | 7 | 3 |
| | **59** | **34** |

⛔ **20 of 34 situations sit in `01-executive-support` alone.** The other nine groups carry 1–3
each. So the Admin brain is deep on the executive-assistant surface and thin everywhere else — that
concentration is a finding, not an accident of counting.

---

# PART 2 · EVERY FILE TYPE'S SCHEMA

## `capability.yaml` — the expertise

```yaml
identity:       id · name · domain · subdomain · version · status · stub
description:    what this capability runs, as prose
question:       the one question it answers
outcomes:       [what good looks like, each with its reasoning]
failure_modes:  [⛔ how it goes wrong — often the most valuable block]
kpis:           [{name, unit, description, direction}]
handoffs:       upstream / downstream / parallel capability ids
applies_to:     models: [...] · offerings: [...]
metadata:       owner · created_by · reviewed_by · review_status · reviewed_at · notes
admission:      ⛔ accepted_content_hash        ← THE GATE
```

⛔ **There is no `reads:` block in a capability.** That lives in heuristics and objects.

## `situations/*.yaml` — when this capability applies

```yaml
identity:                  id · status
description:
matches:                   ⛔ l2_situation_types: [...]   ← the routing key
also_serves:               other situation types it can serve
objects:                   which objects it needs
priority_bp:               integer basis points
typical_duration_days:
signals_of_progress:       [...]
signals_of_decay:          [...]
render:                    how it appears on a card
metadata: · admission:
```

## `objects.yaml` — the LOAD-SET

```yaml
capability: admin.<subdomain>.<capability>
core:       required: [admin.obj.core.*]   optional: [...]
scoped:     required: [...]                optional: [...]
```

Its own header: *"REFERENCES ONLY, never an inline object… **required** = a missing one blocks the
compile. **optional** = absence lowers confidence rather than blocking (Layer 3 strategy S8) — a
situation the compiler cannot fully feed should still produce the answer the requester is waiting on,
at a lower confidence, not withhold it."*

## `knowledge.yaml` — what attaches

```yaml
capability: · playbooks: · heuristics: · mental_models: · rules: · decision_frameworks:
```

## `heuristics/**/*.yaml` — the doctrine

```yaml
identity:      id · name · kind: heuristic · domain · scope · owner_capability · version · status
purpose:       statement · answers: [questions] · not: [what it is NOT]
heuristic:
  statement:         the expert's actual view
  why:              ⛔ prints on the card — a card that instructs without a why is an order
  confidence_bp:     e.g. 7500
  applies_when:      when the rule holds
  breaks_down_when:  ⛔ when the rule is WRONG — the most valuable block in the file
  reads:            ⛔ [object ids AND substrate fact paths]
  contradicts:       [other heuristic ids]
  pattern_ref:      ⛔ [inference-pattern ids from objects/] ← the executable link
when_to_use:
  situations: [...] · conditions: [{exists: …} / {path: …, op: …, value: …}] · signals: [...]
  do_not_use_when: [...]
objects_used: · outcomes: · failure_modes: · limits: · variants: · metrics: · references: · metadata:
```

⛔ **`heuristics/` carry NO `admission` block — 0 of 60.** See PART 3.

## `objects/core/*.yaml` — the richest file type, 23 top-level keys

```yaml
identity: · purpose: · attributes: · states: · relationships:
inference_patterns:   ⛔ THE EXECUTABLE LAYER — see PART 4
inputs: · outputs: · events: · actions: · preconditions: · constraints:
business_rules: · decision_factors: · evidence: · metrics: · dependencies:
exceptions: · best_practices: · anti_patterns: · examples: · references: · metadata:
```

## The rest

| file | keys |
|---|---|
| `playbooks/` | identity · purpose · when_to_use · **steps** · objects_used · limits · failure_modes · variants · references · metadata |
| `rules/` | identity · purpose · **rule** · objects_used · outcomes · failure_modes · limits · variants · metrics · references · metadata |
| `models/` `offerings/` `verticals/` | identity · description · characteristics · capabilities (+ objects for verticals) · metadata |
| `roles/` | identity · description · **answerable_for** · render · metadata |
| `domain.yaml` | activation · identity · description · question · **subdomains** · id_scheme · **core_objects** · **planned_objects** · glossary · metadata |
| `deferrals.yaml` | domain · version · **deferred** · metadata |
| `registry/situation-capability-map.yaml` | ⛔ **generated** — map · deferred_capabilities · suppressed_situations · deferral_contradictions · **pending_l2_types** · routed_l2_types · unrouted_l2_types · orphan_capabilities · unreachable_objects · stats |

---

# PART 3 · ⛔ THREE EDIT RULES — the most practical page here

| file type | `admission` hash | compiler checks it? | safe to edit? |
|---|---|---|---|
| `capability.yaml` | ✅ has one | ✅ **yes** | ❌ **NO — an edit un-accepts it** |
| `situations/*.yaml` | ✅ recorded | ❌ **no** — `admit.py` says so | ✅ yes |
| `heuristics/*.yaml` | ⛔ **0 of 60** | — | ✅ **yes, freely** |
| `objects/*.yaml` | none | — | ✅ yes |

`capability_resolver._admission_reason` hashes the document **minus** the admission block:

> *"The hash pin is the difference between accepting a FILE and accepting its CONTENT — **an edit
> after review silently un-accepts, which is the point.**"*

**To edit a capability legally:**

```bash
# 1. edit the content
# 2. re-stamp — but this only RECORDS an approval that already exists
python "Domain Expertise/_tools/admit.py" --accept <capability.id>
python "Domain Expertise/_tools/admit.py" --check      # verify the whole corpus
```

⛔ `admit.py` refuses to grant review: *"It deliberately does **NOT** grant review. `--accept`
refuses anything the reviewer has not already marked approved with their name on it."*

**Current state:** `201 admitted · 0 stamped · 0 drifted · 23 blocked · 0 HOLLOW`

---

# PART 4 · ⛔ THE EXECUTABLE LAYER — `inference_patterns`

This is the part that actually runs, and it lives in **objects**, not in capabilities.

```yaml
inference_patterns:
  deterministic:            # 139 across Admin
    - id: cmt.dated_promise
      statement: "An action and an agreed date are both present on this node."
      status: executable
      when:
        - {exists: commitment.action}
        - {exists: commitment.due_at}
      yields: {confidence_bp: 9500, attribute: state, value: …}

  heuristic:                # 216 across Admin
    - id: cmt.we_owe_this_one
      statement: "There is an open action and the ball is on our side of the thread."
      status: executable
      when:
        - {exists: commitment.action}
        - {path: thread.ball_in_court, op: "=", value: us}
      yields: …
```

## How a heuristic reaches a pattern

```
heuristics/<subdomain>/<file>.yaml
    heuristic.pattern_ref: [cmt.we_owe_this_one, …]
              │
              └────► objects/core/<object>.yaml
                         inference_patterns.heuristic[].id
```

⛔ **All 20 `pattern_ref` values in Admin's heuristics resolve to real pattern ids. 20 of 20.** The
wiring is intact.

## ⛔ The numbers, and the first surprise

| | |
|---|---|
| total inference patterns | **355** (139 deterministic + 216 heuristic) |
| ⛔ `status: executable` | **123** |
| ⛔ `status: needs_signal` | **232 — 65%** |
| ⛔ **distinct fact paths across ALL executable `when` clauses** | **SEVEN** |

**Those seven are the entire executable surface of the Admin brain:**

```
commitment.due_at  40×      thread.ball_in_court 35×     thread.last_inbound 32×
commitment.action  25×      meeting.start_at     17×     meeting.status      10×
derived.engagement  8×
```

⛔ **123 executable patterns rest on seven facts.** That is the real measure of how much of this
corpus can run today — and it is a far more precise number than "46 of 141 substrate fields are
consumed", which is what an earlier pass measured.

---

# PART 5 · ⛔⛔ THE ROADMAP THE CORPUS WROTE FOR ITSELF

The 232 blocked patterns do **not** have a `when` clause. They have **`requires_signals`** — and
every one of them names what it is waiting for **and which layer owns it**.

```yaml
- id: cmt.owner_is_named
  statement: "The promise records who owns it."
  status: needs_signal
  yields: {confidence_bp: 9500, attribute: owner_ref, value: null}
  requires_signals:
    - kind: fact_path
      name: commitment.owner
      owner_layer: L2
      note: "The extractor emits the action and the date and DROPS THE SUBJECT OF THE SENTENCE.
             Every executable pattern above therefore ASSUMES THE PROMISE IS OURS, which is the
             exact failure this object exists to prevent — roughly half of a real administrator's
             register is other people's promises to the organisation. HIGHEST-VALUE GAP IN THE
             ADMIN BRAIN BY A DISTANCE."
```

## The totals

| | |
|---|---|
| `requires_signals` entries | **416** |
| ⛔ **owner_layer: L1** | **237** |
| ⛔ **owner_layer: L2** | **179** |
| ⛔ **distinct signals named** | **210** |

**by `kind`:** `fact_path` 252 · `obs_kind` 106 · `derived` 50 · `baseline` 8

## The most-demanded signals

| demand | signal | owner |
|---|---|---|
| 10× | `employee.end_at` | L1 |
| 9× | `leaver_confirmed` | L2 |
| 9× | `approval.state` | L1 + L2 |
| 9× | `contract.end_at` | L1 |
| 9× | `obligation.due_at` | L1 |
| 7× | `document.approved_at` | L1 + L2 |
| 7× | `approval.approver` | L1 |
| 7× | `contract.notice_period_days` | L1 |
| 7× | `employee.start_at` | L1 |
| 6× | `document.version` · `evidence_provided` · `approval.requested_at` · `obligation.authority` · `document.retention_until` | L1 / L2 |

## ⛔ What this changes

**The Admin corpus does not have an authoring gap. It has a SUPPLY gap, and it has already
documented the supply gap itself — 210 named signals, split 237/179 between L1 and L2, each with a
sentence explaining what it is worth.**

Earlier passes measured *"Admin consumes 46 of 141 declared substrate fields"* and concluded the next
step was authoring more `reads:`. ⛔ **That framing was wrong.** The corpus reads what exists. What
it is missing is what L1 and L2 do not yet emit — and it says so, per pattern, with an owner.

### The single highest-value item, in the corpus's own words

**`commitment.owner` — owner_layer L2.** The extractor keeps the action and the date and throws away
*who owes it*. So every executable commitment pattern silently assumes the promise is **ours**, when
*"roughly half of a real administrator's register is other people's promises to the organisation."*

**That is one fact path, and it unblocks the most-used object in the domain.**

---

# PART 6 · HOW TO WORK WITH THIS CORPUS

```bash
# verify every hash, see what is blocked and why
python "Domain Expertise/_tools/admit.py" --check

# what no authored corpus can read, per domain
python scripts/unroutable_report.py --corpus-only

# corpus health by the compiler's own admission rules
.venv/bin/python -c "
from genios_engine.reason.domain_shadow import expert_catalog
from genios_engine.packs.compiler.capability_resolver import corpus_health
for d, x in corpus_health(expert_catalog()).items(): print(d, x)"

# the other tools
"Domain Expertise/_tools/"  →  validate.py · index.py · plan.py · render.py · backlog.py
```

## ⛔ Four traps

1. **Editing `capability.yaml` un-accepts it.** Re-stamp with `admit.py --accept`, and only where a
   human has already approved.
2. **A `draft` situation may be deliberate.** Check `registry/…::pending_l2_types` and
   `deferrals.yaml` first — one Admin situation records that flipping it *"would cost a false
   assurance."*
3. **`reads:` is not the executable seam.** `inference_patterns[].when` is. A path in `reads:` with
   no pattern behind it changes nothing that runs.
4. **The seven desk anchors** — `thread · backlog_item · escalation · contact_intent · topic ·
   mailbox · workaround` — are declared by **`support` only**. Authoring Admin doctrine over those
   fact families builds for a situation that never forms.
