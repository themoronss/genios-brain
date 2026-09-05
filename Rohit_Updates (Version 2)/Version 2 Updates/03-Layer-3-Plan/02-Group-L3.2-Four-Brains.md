# L3.2 — The Four Brains: storage, write paths, update triggers, content pipelines

> **The user's four questions, answered with verified code:** how does each brain store?
> is each active? who decides when it updates? where is the LLM and where is it
> deterministic? — and then the two new pipelines that fill the empty ones.

---

## 1. The four brains at a glance

| Brain | Holds | Store | Written by | Status today |
|---|---|---|---|---|
| **Expert** | general professional knowledge — what a competent operator knows | **Git** (`Domain Expertise/`) | **humans only** (PR) | ✅ content rich (1,389 files) · ❌ dark in production |
| **Organization** | THIS company's stated rules — thresholds, processes, criticality | `learned_brain_entries` | L6 publisher (governed) + admin console | ✅ machinery · ❌ **empty** |
| **Behavior** | what this company **actually does** — observed patterns | `learned_brain_entries` | L6 publisher only | ✅ machinery · ❌ **empty** |
| **Adaptive** | current priorities and stated preferences — short-lived by design | `learned_brain_entries` + `temporary_memories` (TTL) | L6 publisher only | ✅ machinery · ❌ **empty** |

**The gap between Organization ("what they say") and Behavior ("what they do") is itself
intelligence** — Globe names this, and it only exists if both brains carry content.

---

## 2. Storage — exactly how each brain persists (verified DDL)

### Expert Brain — Git files

```
Domain Expertise/<Domain>/
  domain.yaml                       the roster
  capabilities/<cat>/<cap>/
    capability.yaml                 identity · description · outcomes · failure_modes ·
                                    kpis · admission.accepted_content_hash
    knowledge.yaml                  which artifacts this capability carries
    situations/*.yaml               the doors L2 situations route through
  playbooks/ heuristics/ rules/ mental-models/ decision-frameworks/ objects/
  registry/situation-capability-map.yaml    GENERATED reverse index — never hand-edit
```

Integrity: `_tools/validate.py` (0 errors today) · admission hash = hash of content
**minus** the admission block, so any content edit invalidates acceptance and forces
re-review (`capability_resolver.py:123-131`). **This is the file-level "is it sahi?"
check, and it passes.**

### The three runtime brains — one versioned table

`migrations/0045_l6_learning.sql:113`:

```sql
learned_brain_entries (
    org_id, brain, subject, version,      -- PK: one lineage per (org, brain, subject)
    learning_id,                          -- provenance: which learning produced it
    value jsonb, visibility_scope, visibility,
    active boolean, supersedes int,
    created_at, deactivated_at,
    CONSTRAINT learned_brain_no_expert CHECK (brain IN ('organization','behavior','adaptive'))
)
UNIQUE (org_id, brain, subject) WHERE active   -- exactly one active version
```

Properties that must never regress:
- **one active version** per (org, brain, subject); supersession = `max(version)+1`
- byte-identical re-publish = `no_material_change` — **no version noise**
- rollback restores the **exact verified predecessor** (or an empty active slot); history intact
- **the `expert` value cannot be written — a database check, not a policy**
- `temporary_memories.expires_at` is **NOT NULL** — every Adaptive lease carries a clock

### How L3 reads them (`runtime_brains.py`)

Pinned immutable versions; selection **explicit** by capability / entity / subject key —
*"unrelated tenant memory is not swept into a package merely because it exists."*
On preference conflicts: **Adaptive > Organization > Behavior** (recent intent wins) —
**except** permission categories (`approval, compliance, constraint, permission, policy,
retention, security`), where **Organization is authoritative**: a founder's passing
preference cannot override a stated approval rule.

---

## 3. WHO decides an update, WHEN, HOW — the governance that already exists

Every write to the three runtime brains passes the **L6 promotion pipeline**
(`contracts/learning.py`, `feedback/governance.py`, `feedback/publisher.py`):

```
observation arrives (outcome, feedback, discovery, distillation)
   ↓ OBSERVED       one observation is noise; recorded, nothing more
   ↓ CANDIDATE      recurrence
   ↓ VALIDATED      deterministic floors from learning_policies:
                      min_observations · min_distinct_days · min_distinct_entities
                      (the third defeats "10 emails from the same person")
   ↓ GOVERNED       governance.py — prohibitions enforced,
                      "never looser than the policy allows"
   ↓ TEMPORARY | HUMAN_REVIEW | PROMOTED
   ↓ PUBLISHED      versioned write to learned_brain_entries
   (REJECTED / EXPIRED are first-class terminal states)
```

### The trigger table — per brain

| Brain | What triggers a write | Who approves | Cadence | Expiry |
|---|---|---|---|---|
| **Expert** | a human opens a PR; N-2/N-5 may **draft** | **human merge, always** — `knowledge_suggestions` stops at review; `expert_brain_changed` always false | on demand | never (versioned in git) |
| **Organization** | N-3 discovery from canon docs · admin console entry · L6 threshold discovery | admin-declared = trusted; **discovered = admin-confirmable; inferred = suggestion only, never auto-applied** (same three-rank rule as L2.1.4 authority view) | on canon ingest | `valid_until` on rule change |
| **Behavior** | N-4 distillation of L2.4 findings | **the floors decide** — min_observations etc.; no human needed because the input is measured behavior, not opinion | weekly batch | decays if the pattern stops recurring |
| **Adaptive** | founder feedback on cards (*"we're already migrating"*) · explicit statements | governance floors; short-lived by design | immediate → `temporary_memories` lease | **mandatory TTL**; promotion to durable only through the pipeline |

**Answer to "kaun decide karega":** deterministic policy floors + `governance.py` +
human review where the table says so. **A language model never decides a promotion** —
it only produces proposals that enter at OBSERVED.

---

## 4. LLM vs deterministic — per brain

| Brain | LLM does | Deterministic does |
|---|---|---|
| Expert | N-1 authoring (done) · N-2 review-assist · N-5 gap drafts — all offline, human-merged | catalog load, hashing, admission validation, routing |
| Organization | **N-3**: read a policy doc, extract candidate rules | CLG-09 gating, precedence, versioning, expiry |
| Behavior | **N-4**: label a measured pattern in words | **the measurement itself is L2.4's integer arithmetic**; CLG-10 gating; promotion floors |
| Adaptive | feedback parsing (free text → structured; Globe weight 55) | TTL, precedence, expiry sweep |

Same law as L1/L2: **the model constructs meaning; deterministic systems decide when
that meaning becomes authoritative.**

---

# 5. The two new content pipelines

> The brains are empty because nothing produces proposals. These two units are the
> supply side. Both feed the EXISTING L6 pipeline — no new governance is built.

## L3.2-U1 · N-3 — Organization-Brain discovery (CLG-09)

**WHAT** — Turns uploaded company canon (policy docs, SOPs, org charts — L1's
`internal_kind` lane) into candidate Organization-brain rules.

**WHY** — The Org brain's flagship content is approval thresholds — exactly the Authority
view the L2 plan needs (L2.1.4). Today the only source is manual console entry, which
means it stays empty. The company already *wrote its rules down*; GeniOS already
*ingests those documents* (L1 canon, authority rank 5); nothing reads them **as rules**.

**WHERE** — `genios_engine/packs/brains/org_discovery.py` (new)

**HOW**
```
1. TRIGGER   an internal_kind document lands (L1 canon) or changes
2. N-3 CALL  (T2) extract candidate rules, TYPED:
               {category: approval|policy|process|criticality,
                subject_type, threshold: Money|None, approver, quote, offsets}
3. VALIDATE  (deterministic, CLG-09)
               - evidence span verifies against the doc (reuse L1 ALG-08)
               - threshold Money parses via L1.5.3 — never a model number
               - approver resolves to a known person/role node — else HUMAN_REVIEW
               - category in the closed set
4. PROPOSE   enters L6 at OBSERVED with source=discovered
5. GOVERN    the standard pipeline; discovered rules publish as admin-confirmable —
             an admin sees them in the console and can veto
6. SERVE     runtime_brains reads them into every relevant package;
             the L2 Authority view (authority_rules) is fed from the same publications
```

**FAILURE MODES**

| Case | Mitigation |
|---|---|
| model invents a threshold not in the doc | span validation drops it — same anti-hallucination as L1 |
| two docs disagree ($50K vs $25K) | both proposed; conflict surfaces in the console; newer **signed/ratified** doc outranks |
| stale policy doc | rules carry the doc's version; a superseding doc expires the old rule (`valid_until`) |
| an "inferred" rule auto-enforcing | **cannot happen** — discovered rules are admin-confirmable, inferred are suggestion-only |

**ACCEPTANCE** — a fixture policy PDF stating *"contracts above \$50,000 require founder
approval"* produces exactly one candidate rule with a verifying span, Money in minor
units, and lands in the console pending confirmation; **zero** rules whose span fails
validation.

**REVERSE PROMPT**
```
TASK: Build Organization-brain discovery (N-3).
FILE: genios_engine/packs/brains/org_discovery.py

The Org brain is empty because its only write path is manual console entry. But the
company's rules are already WRITTEN DOWN in the policy docs L1 ingests as internal_kind
canon (authority rank 5). This unit reads those documents AS RULES.

IMPLEMENT the 6 steps in doc 02 section L3.2-U1.

HARD RULES:
1. The model extracts; it never publishes. Output enters the EXISTING L6 pipeline at
   OBSERVED with source=discovered. Do not build new governance — feedback/governance.py
   and learning_policies already exist and are correct.
2. Every candidate rule carries a verbatim quote + offsets, validated with the L1 span
   validator (capture/validate/spans.py ALG-08). Reuse it. An unverified span = dropped.
3. Thresholds parse through capture/validate/money.py. A model-emitted number that the
   parser cannot reproduce from the quote is dropped.
4. Approver must resolve to a known node via context/identity.py, else route the
   proposal to HUMAN_REVIEW instead of publishing.
5. Publications also feed authority_rules (the L2.1.4 Authority view) — one discovery,
   two consumers. Do not write two extractors.
6. Discovered rules are admin-confirmable and visible in the console BEFORE any card
   cites them.

TEST tests/packs/brains/test_org_discovery.py:
  - the $50K fixture -> one rule, verified span, Money(5_000_000, USD)
  - invented threshold -> dropped
  - unknown approver -> HUMAN_REVIEW
  - superseding doc -> old rule gets valid_until
```

## L3.2-U2 · N-4 — Behavior-Brain distillation (CLG-10)

**WHAT** — Turns L2.4 analytic findings into behavior-pattern statements.

**WHY** — Globe's Behavior brain examples (*"founder reviews large renewals ~2 weeks
out"*, *"approvals stall on Fridays"*) are **measurements plus a sentence**. L2.4 now
produces the measurements deterministically; nothing turns them into brain entries.

**WHERE** — `genios_engine/packs/brains/behavior_distill.py` (new)

**HOW**
```
1. TRIGGER   weekly batch over L2.4 outputs: trends, baselines, correlations, anomalies
2. GATE      (deterministic, CLG-10) a finding qualifies only if:
               observation window >= 60 days
               population/occurrence count meets learning_policies floors
               the metric is in a BEHAVIOR_ELIGIBLE registry (not every trend is a habit)
3. N-4 CALL  (T1) label the numbers as one pattern statement, span-locked to the
             numbers: {pattern_statement, subject, metric_refs, numbers TEMPLATED}
4. PROPOSE   enters L6 at OBSERVED with the metric evidence attached
5. FLOORS    min_observations / min_distinct_days / min_distinct_entities decide —
             no human needed: the input is measured behavior, not opinion
6. DECAY     a published pattern that stops recurring is superseded by its own absence
             (re-checked each batch; expiry through the same pipeline)
```

**The division is exact:** L2.4 computes *"41 of 41 approvals under \$5K, median lead
time 13 days"* (integer arithmetic, reproducible). N-4 writes *"the founder approves
small spends routinely and reviews large renewals about two weeks out"* (a sentence,
citable to those numbers). **The numbers are templated into the statement, never
generated by the model** — the same rule as L2's M-6 framing.

**FAILURE MODES**

| Case | Mitigation |
|---|---|
| pattern from 2 weeks of data | 60-day window gate |
| coincidence labelled as habit | learning_policies floors — the same ones that stop "10 emails from one person" |
| pattern persists after behavior changed | decay re-check each batch |
| model editorializes ("founder is a bottleneck") | statement schema is descriptive-only; judgment words rejected by a lexicon check; L4 draws conclusions, not the brain |

**ACCEPTANCE** — the 41/41-approvals fixture produces one OBSERVED proposal whose
statement contains the templated numbers; a 2-week trend produces **nothing**; a
published pattern whose metric flatlines is superseded within two batches.

---

## 6. Group acceptance gate

```
pytest tests/packs/brains -q
python scripts/brain_content_report.py --org <pilot>
```

| Metric | Gate |
|---|---|
| Organization entries for the pilot (discovered + confirmed) | **>= 3** |
| Behavior entries published through the floors | **>= 1** |
| Adaptive lease created from card feedback | **>= 1** |
| entries written outside the L6 pipeline | **0** |
| any write with `brain='expert'` | **impossible — DB constraint; test asserts the error** |
| a package whose brain slices are non-empty for the pilot | **>= 1** — the brains finally speak |
