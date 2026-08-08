# Domain Expertise — the Expert Brain

> **This folder is Layer 3's authored half.** Human-authored, version controlled, reviewed, and
> **never mutated by the system** — Atlas Rule 06. Layer 6 may raise a suggestion against it;
> only a person merges one.

Layer 3 has two halves and they are easy to confuse:

| | Where | What it is | Who writes it |
|---|---|---|---|
| **Expert Brain** | **this folder** | What the *profession* knows — capabilities, objects, situations, inference patterns | A human, in Git |
| **Runtime packs** | [`genios_engine/packs/`](../genios_engine/packs/) | Tenant *configuration* — thresholds, weights, rules, plays | Merged per tenant at runtime |

The packs already exist and are untouched by this folder. The direction is one-way: this library
is the upstream source, and a later compiler step will emit and validate pack content from it.
Two competing truths about what a sales rule is would be worse than one incomplete one.

---

## The hierarchy

```
Domain
 └─ Subdomain             the lifecycle, in order — a numbered folder
     └─ Capability        a unit of professional competence — a FOLDER
         └─ Situation     the load-set selector — five objects, not forty
             └─ Object    the smallest reusable knowledge unit
```

A capability is a folder, not a file:

```
capabilities/03-qualification/lead-qualification/
├── capability.yaml     purpose, expertise, KPIs, handoffs — and no numbers
├── objects.yaml        the load-set. REFERENCES ONLY, never an inline object
└── situations/         the situations this capability owns
```

`objects.yaml` is split out deliberately. Changing what a capability loads is then a one-file
diff a reviewer can read without wading through prose, and the core/scoped split is visible at
a glance instead of buried in a list.

---

## Core and scoped objects

```
objects/core/<name>.yaml            loaded by MORE THAN ONE capability
objects/<capability>/<name>.yaml    loaded by EXACTLY ONE
```

`Decision Maker` is needed by five capabilities, so it is authored once in `core/`. `Concession`
belongs to negotiation and would be noise anywhere near prospecting, so it lives in
`objects/negotiation/`.

**This is decided by the reference graph, not by intent, and `validate.py` enforces it in both
directions** — a scoped object two capabilities load is an error telling you to promote it; a
core object one capability loads is a warning telling you it may want demoting. Without that
enforcement, six months in `core/` becomes "objects we happened to author early" and the
distinction stops carrying information.

The scope is in the id, which makes it self-locating and lets the same noun exist twice without
collision: `sales.obj.core.decision_maker`, `sales.obj.negotiation.concession`.

---

## The one rule that makes this library worth having

**Every inference pattern carries both a human `statement` and a machine `when`.**

```yaml
- id: dm.requested_the_contract
  statement: "Asked for the contract and gave a verbal yes."     # for a reviewer
  status: executable
  when:                                                          # for the engine
    - {has_obs: contract_requested}
    - {has_obs: verbal_yes}
  yields: {confidence_bp: 8800, property: authority_level, value: final_approver}
```

Prose alone cannot fire. There is no runtime that evaluates *"a person who approves contracts in
email"* except a model, and reaching for a model here defeats the entire architecture. The `when`
block speaks the engine's own whitelisted grammar, transcribed verbatim from
[`genios_engine/reason/engine.py`](../genios_engine/reason/engine.py) into
[`_schema/vocabulary.yaml`](_schema/vocabulary.yaml).

A pattern that *cannot* be expressed yet is `status: needs_signal` and names what Layer 1 or 2
would have to emit. Those are not gaps in the authoring — they are the **backlog**, and
`_tools/backlog.py` ranks them by how many patterns each unblocks.

### Three rules the grammar will silently punish you for breaking

- **`IN` is uppercase.** [`engine.py:71`](../genios_engine/reason/engine.py#L71) tests
  `op == "IN"`. A lowercase `in` falls through to the numeric branch and evaluates `False`
  forever.
- **Conditions in a `when` list are ANDed.** There is no `or`. Express alternatives as two
  patterns — which is exactly how the engine works.
- **Quote any flow-mapping scalar containing a comma.** `{signal: contact role, seniority}`
  parses as two keys, not one string. The validator caught seven of these on its first run.

---

## Authoring

Every score is an **integer basis point**, `0–10000`, on a field ending `_bp`. Atlas Rule 03:
floats do not hash reproducibly across machines, so a threshold met on one worker is missed on
another, and the bug surfaces months later as *"why did it not remind me?"*.

Copy the shape of the reference files:

| Authoring | Copy from |
|---|---|
| A core object | `Sales Expertise/objects/core/decision-maker.yaml` — all 18 sections |
| A capability | `Sales Expertise/capabilities/03-qualification/lead-qualification/` |
| A situation | `.../buying-committee-analysis/situations/enterprise-deal.yaml` |
| A model branch | `Sales Expertise/models/b2b/model.yaml` |

The 18 object sections. Six are required so a first pass can be incremental; the other twelve
may be absent.

```
identity*  description*  components   properties*  relationships*  states
business_rules   decision_factors   inference_patterns*   inputs   outputs
events   actions   constraints   evidence   metrics   examples   metadata*
```

**No numbers in `capability.yaml`.** Thresholds, weights and scores are Layer 4's arithmetic and
live in the pack manifest. The moment a threshold appears in a capability, the Layer 3/4 boundary
has leaked. (Object `decision_factors` do carry `weight_bp`, and must sum to exactly 10000.)

---

## Tools

```bash
python "Domain Expertise/_tools/validate.py"     # errors fail; --strict fails on warnings too
python "Domain Expertise/_tools/plan.py"         # refresh domain.yaml planned_objects
python "Domain Expertise/_tools/index.py"        # regenerate registry/ + coverage report
python "Domain Expertise/_tools/backlog.py"      # rank the Layer 1/2 signal asks
python "Domain Expertise/_tools/render.py"       # regenerate the _book/ Markdown
```

`validate.py` runs two passes. **Structure** checks each file against its JSON Schema and needs
`jsonschema`; if it is missing the pass is *skipped with a notice*, never silently passed.
**Semantics** always runs and covers what no schema can express:

- **pattern honesty** — a pattern marked `executable` whose fact paths or observation kinds the
  pipeline does not emit is an error. The check this tool exists for: without it the library
  fills with expertise that looks live and never fires, and nobody finds out until someone asks
  why the system is quiet.
- **scope integrity** — core/scoped placement checked against the reference graph, both ways
- **link integrity** — an unauthored object id is an error unless `plan.py` has declared it
- **L2 binding** — `matches.l2_situation_types` ⊆ the types Layer 2 actually emits
- **layout** — capability folders have both required files, situations sit under their
  `owner_capability`, objects sit in their scope folder
- predicate grammar, operator closure, and `_bp` range

`_book/` and `registry/` are **generated**. Edit the YAML.

---

## Layout

```
Domain Expertise/
├── _schema/       7 JSON Schemas + vocabulary.yaml (the runtime contract)
├── _tools/        validate · plan · index · backlog · render
├── _book/         GENERATED Markdown
└── Sales Expertise/
    ├── domain.yaml            9 subdomains · id scheme · core roster · glossary
    ├── objects/
    │   ├── core/              the shared library
    │   └── <capability>/      objects belonging to exactly one capability
    ├── capabilities/<NN-subdomain>/<capability>/
    │   ├── capability.yaml
    │   ├── objects.yaml
    │   └── situations/
    ├── models/                B2B · B2C · PLG · channel · government … + verticals
    ├── offerings/             product · service · hybrid + types
    └── registry/              GENERATED map + signal backlog
```
