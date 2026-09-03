# L2.1 — Enterprise Context Graph (8 views)

**Group responsibility:** hold what is true about the company.

**Group law:** *Eight views over ONE graph — not eight graphs.* A view is a lens; the same
node appears in several.

**Tables:** `graph_nodes`, `graph_facts`, `graph_edges`, `graph_observations`
**Status:** 5 of 8 built. One view missing entirely, two partial.

---

## The eight views

| # | View | Status | Where |
|---|---|---|---|
| L2.1.1 | Entity | ✅ | `graph_nodes`, typed |
| L2.1.2 | Relationship | ✅ | `graph_edges`, typed |
| L2.1.3 | Temporal | ⚠️ | `valid_from`/`last_reinforced` — **no history**, see L2.4.1 |
| **L2.1.4** | **Authority** | ❌ | **MISSING ENTIRELY** |
| L2.1.5 | Ownership | ✅ | `open_loops`, ball-in-court |
| L2.1.6 | Communication | ✅ | thread facts, contact frequency (`97aeb46`), account rollups (`d11f6e7`) |
| L2.1.7 | Resource | ⚠️ | money attaches; `deal.value` **deliberately not derived** |
| L2.1.8 | Knowledge | ✅ | `canon.py`, `document_register.py` |

---

# ❌ L2.1.4 · Authority View — MISSING

### L2.1.4-U1 · Approval thresholds as data

**WHAT** — Who can approve what, at what threshold, with what delegation.

**WHY** — Globe is explicit: *"`Arjun approves contracts > \$50K` lives here as **data**,
not as an `if` statement."* A grep of `context/` for approval thresholds returns nothing.

**The downstream cost is specific.** Two Layer 4 reasoning units cannot fire without it:
- **Policy unit** — *"which organisational rules bind"* has no rules to read
- **Constraint unit** — *"what cannot happen"* has no thresholds to check

And Globe's **Founder Bottleneck** surface — which it rates *"highest 'I can't unsee this'
value"* — is built entirely on this view: *"this person is the only approver for N open
items"* is an Authority-view query.

**WHERE** — `genios_engine/context/authority.py` + migration

**STORAGE**
```sql
create table if not exists authority_rules (
    org_id        text not null,
    rule_id       text not null,
    subject_type  text not null,        -- contract | expense | hiring | legal | discount
    threshold_minor_units bigint,       -- null = applies at any value
    currency      text,
    approver_node_id text not null,
    delegate_node_id text,              -- who may act in their absence
    source        text not null,        -- discovered | admin_declared | inferred
    evidence_ref  text,                 -- the document or setting it came from
    valid_from    timestamptz not null,
    valid_until   timestamptz,
    primary key (org_id, rule_id, valid_from)
);
```

**Keyed by `valid_from`, so authority is historical.** *"Who could approve this in March?"*
must be answerable, because a decision made in March was correct against March's rules.

**HOW — three sources, ranked:**
```
1. admin_declared  a human set it in the console        -> authority 10000, trusted
2. discovered      extracted from an uploaded policy    -> authority 8000, admin-confirmable
                   document (L1 internal_kind canon)
3. inferred        observed behaviour: this person has     -> authority 5000, NEVER
                   approved N of N requests in this           auto-applied; surfaced as
                   class over 90 days                         a suggestion to confirm
```

**Rule 3 is deliberately advisory.** Inferring an approval threshold from behaviour and
then enforcing it would let the system invent governance. It proposes; a human confirms.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Stale threshold | wrong approver named on a card | `valid_until`; Globe's own named L4 failure is *"Policy unit reads a stale threshold"* |
| Inferred rule auto-applied | the system invents governance | source ranking; inferred rules never enforce |
| No rule for a class | silent gap | absence returns `no_authority_rule`, distinct from "anyone may approve" |

**ACCEPTANCE**
```
pytest tests/context/test_authority.py -q
# an admin_declared rule beats a discovered one for the same class
# an inferred rule is returned as a SUGGESTION and never as an enforceable rule
# a rule with valid_until in the past is not returned for now, but IS returned
#   for an as_of query in its validity window
# an unmatched class returns no_authority_rule, not an empty permissive answer
```

---

# ⚠️ L2.1.3 · Temporal View

Exists as `valid_from` / `last_reinforced` / decay inputs. **The gap is history**, and it
is owned by **L2.4.1 Metric History Store** — see doc 04. Nothing to build here beyond
ensuring the temporal fields feed the sampler.

---

# ⚠️ L2.1.7 · Resource View

`derived.py:182-184` records the restraint:

> *"`deal.value` is deliberately NOT derived... a wrong one would flow straight into
> prioritisation."*

**That was correct** when the only source of a value was an unvalidated model output.
**L1 v2 changes the premise:** `Money` now arrives normalized (ALG-10), span-verified
(ALG-08), authority-ranked (ALG-14), and with conflicts detected (ALG-12).

**Change:** derive `deal.value` **only** from a `Money` claim that is span-verified and
carries no unresolved conflict. A conflicted or unverified amount leaves the field
`unknown` — never a guess. Record which claim won and why.

This unblocks L1's `ALG-17` monetary term and L2.7.4's base, both of which need a value.

**ACCEPTANCE** — a verified unconflicted `Money` derives `deal.value`; a conflicted one
leaves it `unknown` and links the `Conflict`; an unverified one never derives.

---

## Group acceptance gate

```
pytest tests/context/test_authority.py tests/context/test_graph_views.py -q
```

| Metric | Gate |
|---|---|
| authority rules present for a pilot tenant | > 0 |
| inferred rules auto-applied | **0** |
| `deal.value` derived from an unverified `Money` | **0** |
| as-of authority query returns the rule valid at that time | passes |
