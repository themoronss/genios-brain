"""L2-4 · a routing miss, counted with its name — because a drop with no name is a delete.

⛔ **THE COUNT ALREADY EXISTED AND THREW AWAY THE ONE THING THAT MAKES IT ACTIONABLE.**
`domain_shadow` tallies `counts["unactivatable_domain"]`, added after this exact silence was found:

    A situation whose L2 domain no corpus claims compiles in measurement mode, publishes no
    package and emits no signal — on EVERY tenant configuration… There was no count for it, so
    "shadow_situations" absorbed it alongside rows a tenant could switch on tomorrow, and the two
    are not the same fact.

**It is a scalar.** `unactivatable_domain: 69` cannot say whether to author `fundraising` first or
`general` first — and the same comment says the answer is not close: *"`general:relationship` is
the most-authored type in the corpus and the largest on the pilot (55 rows)"*, against two
fundraising types. **55 of the pilot's 159 active situations are one dark type.**

L1 wrote the rule: **`DROP ≠ DELETE`** — *"you log why dropped, which rule, which threshold, which
evidence. So when the founder says 'why didn't GeniOS tell me about this?' you can trace the
failure."* A routing miss is a drop.

PURE — no I/O, no clock. It takes a counts dict and adds to it, which is what makes it testable
without a sweep and what let the wiring check be a test rather than a hope.
"""
from __future__ import annotations

from typing import Any, MutableMapping

#: The key that existed before this module. Kept, and kept FIRST, because a dashboard or a gate
#: reading it must not notice this change: a refinement that renames the number somebody watches
#: is a refinement that breaks a watch.
SCALAR_KEY = "unactivatable_domain"

#: A domain that routes nowhere and that `DARK_DOMAINS` does not declare. **This is the `support`
#: defect returning** — a spelling seam that silently returned `()` for 33 situations — so it is
#: counted like any other AND marked, because a tally that cannot say "this one is a surprise" is
#: a tally that normalises one.
UNDECLARED_KEY = "unroutable_undeclared"


def tally_unroutable(counts: MutableMapping[str, Any], *,
                     l2_domain: Any, situation_type: Any) -> None:
    """Record one situation that no authored corpus can read.

    Three keys, deliberately, because three different people act on them:

        unactivatable_domain                 the total. Unchanged, for whoever already reads it
        unroutable:<domain>                  WHICH corpus to author
        unroutable:<domain>:<type>           WHICH SITUATION that corpus must describe first

    A corpus is authored per situation type, not per domain, so the third key is the one an
    author can act on — and dropping it would leave the number true and useless.
    """
    domain = str(l2_domain or "").strip().lower() or "unknown"
    # `unknown` rather than skipping: a row with no type is still a row that produced nothing,
    # and omitting it would make the per-type keys fail to sum to the total.
    stype = str(situation_type or "").strip().lower() or "unknown"

    counts[SCALAR_KEY] = int(counts.get(SCALAR_KEY, 0)) + 1
    counts[f"unroutable:{domain}"] = int(counts.get(f"unroutable:{domain}", 0)) + 1
    counts[f"unroutable:{domain}:{stype}"] = int(
        counts.get(f"unroutable:{domain}:{stype}", 0)) + 1

    # Imported at call time: `reason` may import `context` (lower layer), and doing it here keeps
    # the module importable in a test that has no context configured.
    from genios_engine.context.domain_silence import is_dark

    if not is_dark(domain):
        counts[UNDECLARED_KEY] = int(counts.get(UNDECLARED_KEY, 0)) + 1


__all__ = ["SCALAR_KEY", "UNDECLARED_KEY", "tally_unroutable"]
