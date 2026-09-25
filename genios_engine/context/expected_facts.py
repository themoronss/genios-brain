"""L2-2 · what a situation type's domain says could be absent — V-10's input, computed in L2.

⛔ **THIS MODULE EXISTS BECAUSE THE IMPORT RATCHET SAID SO.** V-10's first draft read
`context.domain_spec` from inside `contracts/situation.py`, behind a deferred import, with a
comment claiming the deferral kept the contract package's import rule intact. It did not:

    AssertionError: situation.py imports genios_engine.context

**A contract may import platform and stdlib only.** So the registry lookup lives here, in the
layer that owns the registry, and the answer is HANDED to the law — the same shape
`build_business_situation(refusal=...)` already uses: *"computed by the caller because this
builder holds no connection, and passed in."*

⛔ **AND IT IS KEYED BY SITUATION TYPE, NOT BY ANCHOR.** `domain_spec.domains_declaring` takes an
ANCHOR type and answers `()` for a situation type — a silent empty that reads exactly like *"this
type expects nothing"*. That is the same class of caller error that answered
`identity_status_absent` for the entire corpus in L2-0, and it cost this step a debugging pass.
"""
from __future__ import annotations

from genios_engine.context.domain_spec import registered_domains, spec_for


def expected_facts_for(situation_type: str) -> tuple[str, ...]:
    """The fact paths every registered domain declares for this situation type.

    Merged across domains rather than resolved to one, because a situation type can be claimed by
    more than one domain and V-10 only asks *"could anything have been missing here"*.

    Measured 2026-09-24: **26 of 37 registered situation types declare expected fields; 11 declare
    none.** For those eleven an empty `missing_facts` is the correct answer rather than a claim of
    completeness, which is what narrows V-10 from the plan's unconditional rule.
    """
    if not situation_type:
        return ()
    found: set[str] = set()
    for domain in registered_domains():
        found.update(spec_for(domain).fields_for(situation_type))
    return tuple(sorted(found))


__all__ = ["expected_facts_for"]
