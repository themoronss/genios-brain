# Domain specs — the seam Layer 3 plugs into

*`context/domain_spec.py`*

> **The requirement that shaped this file:** more domains are coming. Sales, support and admin
> today; engineering, legal, hiring later.
>
> **So Layer 2 must keep working for domains it has never heard of** — and adding one must never
> require editing Layer 2.

---

## §1 · The leak this closed

Layer 2 Step 3 shipped these tables **inside `situations.py`**:

```python
_TYPE_BY_ANCHOR = {("company", "sales"): "opportunity", ("company", "support"): "support_case", …}
_EXPECTED_FIELDS = {"deal": {"deal.stage": "pipeline stage", …}, …}
```

That is **domain expertise sitting in the context layer**. Two problems, and the practical one
is worse than the principled one:

| | |
|---|---|
| **Principle** | the architecture is explicit that context holds what is *true*, never what a domain *means* |
| **Practice** | with the knowledge inlined, every new domain would require editing Layer 2 — the layer that must stay stable |

The knowledge moved behind a registry, and Layer 2 stopped knowing any domain by name.

---

## §2 · What a spec holds — and what it deliberately does not

```python
@dataclass(frozen=True, slots=True)
class DomainSpec:
    domain: str
    display_name: str = ""
    situation_types: dict[str, str]          # anchor node type → what an executive calls it
    expected_fields: dict[str, dict[str, str]]   # situation type → {fact field: plain-language gap}
```

**No thresholds. No rules. No priorities.** Those are decisions, and a decision made here would
be a decision made twice, since Layer 4 already makes them.

| Method | Returns | Fallback |
|---|---|---|
| `type_for(anchor_type)` | the situation type | `"<domain>_<anchor>"` |
| `fields_for(situation_type)` | expected fields | `{}` |

---

## §3 · Open by default — the property that matters

An unregistered domain is **not an error, not a gap, and not a special case.**

```python
def spec_for(domain):
    """NEVER raises and never returns None."""
    name = (domain or "").strip().lower() or "general"
    return _SPECS.get(name) or generic_spec(name)
```

| For an unknown domain | Result | Why |
|---|---|---|
| situation type | `engineering_company` | **visibly unmapped**, never mislabelled as something it is not |
| expected fields | `{}` | |
| coverage | **100%** — "we expect nothing, so nothing is missing" | |
| display name | `"Engineering"` | derived from the name |

### The trap in that third row

A registry returning "no expectations" as **"nothing known"** would report every situation in a
new domain as completely uncovered — absence read as negative evidence, which this codebase
refuses everywhere else.

**It would make every new domain look broken on the day it was added.**

`coverage_score` handles it explicitly:

```python
if not expected:
    return 100, []          # not (0, ["everything"])
```

Pinned by `test_projections.py::test_a_new_domain_is_not_reported_as_completely_uncovered`.

---

## §4 · How Layer 3 takes over

```python
from genios_engine.context.domain_spec import DomainSpec, register

register(DomainSpec(
    domain="engineering",
    display_name="Engineering",
    situation_types={"company": "incident", "project": "delivery"},
    expected_fields={"incident": {"incident.severity": "severity", …}},
))
```

**Overwriting is allowed and is the point.** The four built-in specs are placeholders; a registry
that refused to be overwritten would force Layer 2 to be edited to *remove* them first — exactly
what this seam exists to prevent.

`extend(domain, **changes)` adjusts one registered domain without restating it.

### The one file that names a domain

`domain_spec.py` registers `sales`, `support`, `admin` and `general` at import. They live there
as **data, not logic**.

An earlier test asserted *"Layer 2 holds no domain knowledge"* — while **excluding the one file
that names domains.** The knowledge had moved 200 lines sideways and the test was checking
everywhere it wasn't.

The honest claim, now enforced by
`test_domain_names_appear_in_exactly_one_file_in_the_context_layer`: **one place, and it is
overridable.** Every other file in `context/` is domain-blind.

---

## §5 · `spec_version()` — determinism on a stored path

The subtle problem, found in review.

`situation_type`, `coverage` and `missing` are **derived** from these specs and then
**persisted** to `context_situations`. So:

- A registry change silently rewrites stored values on the next refresh, with nothing recording
  that the *definition* moved rather than the *world*.
- Two workers with different import order could write different types for the same situation.

```python
def spec_version() -> str:
    return stable_id("dspec", {name: asdict(spec) for name, spec in sorted(_SPECS.items())})
```

Stamped into every situation's `inputs` as `domain_spec_version`. A re-typing becomes
**attributable**: the row says which registry produced it, and a diff in this hash explains a
change that would otherwise look like the world changed.

Same idea as the pack registry's effective snapshot, which every signal already carries.

---

## §6 · The registry is not the universe

```python
registered_domains()   # what someone has DESCRIBED
```

**Not the list of domains that exist.** Data can carry a domain nobody registered — and Layer 2
must keep working when it does.

This is why [projections](03-Projections.md) discover lenses from `context_situations` rather
than from this registry. A domain arriving in the data before anyone describes it still gets a
working lens; `registered: false` simply means "present, not yet described", which is a normal
state while a domain is being introduced.

---

## §7 · The four built-in specs

| Domain | Anchor → type | Expected fields |
|---|---|---|
| `sales` | deal → `deal` · company → `opportunity` · person → `prospect_relationship` | `deal.stage`, `deal.amount`, `deal.close_date`, `commitment.due_at`, `thread.ball_in_court` |
| `support` | company → `support_case` · person → `support_contact` | `thread.ball_in_court` |
| `admin` | company → `account_admin` | `subscription.current_period_end` |
| `general` | company/person → `relationship` | `thread.ball_in_court` |

### Why "decision maker" and "budget" are absent

They are the obvious things to expect on a sales deal. They are not here because **nothing
deterministic writes them.** Checking for a field no source produces yields a report that is
always right and never useful — every situation missing everything.

They belong here the day a source starts producing them.

---

## §8 · Edge cases

| Input | Result |
|---|---|
| `spec_for(None)` / `spec_for("")` | the `general` spec |
| `spec_for("SALES")` | the `sales` spec — case-insensitive, so one domain never becomes two lenses |
| `register(DomainSpec(domain=""))` | `ValueError` |
| `type_for` on an unmapped anchor | `"<domain>_<anchor>"` |
| A domain in the data, not in the registry | works fully; `registered: false` |

---

*Related: [Situation Assembly](01-Situation-Assembly.md) · [Projections](03-Projections.md) · [Coverage and Missing](../04-Context-Quality-Engine/02-Coverage-and-Missing.md)*
