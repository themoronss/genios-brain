"""The pack's vocabulary, shaped for the extraction prompt.

Layer 3 owns domain vocabulary — `sales_v1.py` says so in the comment above its own `schema`
block: *"L2 extraction whitelist + L1 hints (domain vocabulary lives here, not in the engine)"*.
That contract was declared and never connected: `registry.effective()` dropped `schema` and
`capture`, and `build_prompt` took no pack argument, so the extractor ran one hardcoded
B2B-SaaS ontology for every tenant regardless of which pack they were on.

The visible cost was two-sided. Rules read `deal.status` while the extractor, never told the
name, wrote `status` — so the rule was dead on arrival. And the model, given three examples and
an ellipsis for `field`, invented 268 distinct field names in one org, 192 of them used exactly
once.

This module turns whatever the pack declares into two prompt fragments. It is deliberately
tolerant: a pack that declares nothing yields the engine's own defaults, so an unmigrated tenant
behaves exactly as before rather than losing its vocabulary entirely.
"""
from __future__ import annotations

from genios_engine.context.vocabulary import CANONICAL_OBS_KINDS

#: Fields the engine itself derives or requires regardless of domain. A pack may add to these;
#: it may not remove them, because the engine's own rules and lifecycle read them.
ENGINE_FIELDS: tuple[str, ...] = (
    "thread.last_inbound", "thread.last_outbound", "thread.ball_in_court",
    "commitment.due_at", "commitment.action",
    "role", "company",
)


def observation_vocabulary(effective: dict | None) -> tuple[str, ...]:
    """The observation kinds this tenant's rules actually CONSULT.

    Read from the rules' own `has_obs` / `no_obs` / `neighbor_has_obs` clauses, which is where
    the dependency really lives. The obvious-looking source — `schema.signal_vocab` — is the
    list of reason codes a pack EMITS (`stalled_deal`, `closed_lost_risk`), not the observations
    it reads. Confusing the two is the same category error that keyed the Layer 3 corpus on
    signal reason codes and made 73 of 73 situations unroutable; here it would have told the
    model to emit rule names as observations.

    Falls back to the canonical set when nothing is declared: emitting a kind no rule reads is
    wasteful, emitting nothing at all is fatal.
    """
    kinds: list[str] = []
    for pack in _packs(effective):
        for rule in pack.get("rules") or ():
            if not isinstance(rule, dict):
                continue
            for cond in rule.get("when") or ():
                if not isinstance(cond, dict):
                    continue
                for key in ("has_obs", "no_obs", "neighbor_has_obs"):
                    kind = cond.get(key)
                    if isinstance(kind, str) and kind:
                        kinds.append(kind)
    # UNION with the canonical set, never a restriction to it. The pack's job here is to
    # GUARANTEE its own kinds are asked for; narrowing the model to only those would stop
    # extracting the observations that carry the most intent and happen to have no rule yet —
    # `meeting_request` (183 occurrences in one org), `question` (83), `next_step_agreed` (27),
    # `positive_reply` (34). Those are the evidence a future rule needs; refusing to capture
    # them because today's corpus is thin would make the corpus permanently thin.
    ordered = list(dict.fromkeys(kinds)) + sorted(CANONICAL_OBS_KINDS - set(kinds))
    return tuple(ordered)


#: Fields a pack may DECLARE but the model must never be asked to find, because the engine
#: computes them. Declaring a field in `schema.fields` serves two purposes that look the same and
#: are not: it lets a capability cite the field as evidence, and it puts the field in the
#: extraction prompt. For a computed field only the first is wanted.
#:
#: `context/meeting_lifecycle.py` derives five booleans from the calendar and opens with
#: "Deterministic. No model. Every field is derivable from what the calendar already gives us."
#: All three of `general`, `admin` and `customer_support` then declared them, so every extraction
#: asked a language model to decide whether a meeting it cannot see was attended. It answered:
#: on the design partner's graph `meeting.scheduled` holds `'Monday 10 Aug 2026, 10:30am -'` on
#: 30 person nodes, `meeting.start_at` holds `'18th August 2026, 4:00 PM'` beside the calendar's
#: clean ISO value, and `meeting.status` holds `canceled` where `meeting_lifecycle` and every
#: authored predicate spell it `cancelled`.
#:
#: Those person-level guesses are not harmlessly ignored. They arrive in the NEIGHBOUR facts of
#: every person-anchored situation — which is where `admin.obj.core.meeting`,
#: `admin.obj.core.action_item`, `admin.obj.calendar_management.time_block` and
#: `admin.obj.core.deadline` read them — so an authored inference pattern was resolving against
#: whichever writer landed last.
#:
#: Stripped here rather than deleted from the packs, deliberately: the declarations are correct
#: (a capability may cite these), pack bytes are immutable so removing them means a version bump
#: and a `promote_packs` run on every existing tenant, and the same one-line mechanism already
#: exists for `derived.*` immediately below.
COMPUTED_FIELDS: tuple[str, ...] = (
    "meeting.scheduled", "meeting.occurred", "meeting.attended",
    "meeting.external_counterparty", "meeting.open_loop",
)


def field_vocabulary(effective: dict | None) -> tuple[str, ...]:
    """The fact field names the tenant's rules actually read, plus the engine's own."""
    declared: list[str] = []
    for pack in _packs(effective):
        declared.extend((pack.get("schema") or {}).get("fields") or ())
    # `derived.*` is computed by the reasoner from other facts, never extracted. Offering it to
    # the model invites a plausible invented value that the engine then overwrites — or worse,
    # does not, and a rule reads a number nobody measured. `COMPUTED_FIELDS` is the same rule for
    # fields whose names do not share a prefix.
    names = [f for f in dict.fromkeys(list(ENGINE_FIELDS) + declared)
             if f and not f.startswith("derived.") and f not in COMPUTED_FIELDS]
    return tuple(names)


def classifier_hints(effective: dict | None) -> str:
    """The pack's own description of what its domain looks like, for the L1 gate."""
    hints = [str((pack.get("capture") or {}).get("classifier_hints") or "").strip()
             for pack in _packs(effective)]
    return " · ".join(h for h in hints if h)


def vocabulary_note(effective: dict | None) -> str:
    """One sentence naming the domains in play, so the model knows what it is reading for."""
    ids = [str(p.get("pack_id") or "").strip() for p in _packs(effective)]
    ids = [i for i in ids if i]
    if not ids:
        return "This is how the system detects business and relationship moments:"
    return (f"This tenant reasons over the {', '.join(sorted(set(ids)))} domain(s); these are the "
            "moments its rules can act on:")


def _packs(effective: dict | None) -> list[dict]:
    """Accept a single effective config or a collection of them.

    `registry.effective()` returns one pack, but a tenant is bound to several (sales + general),
    and the extractor must see the union — a fact named by one pack and dropped because another
    was consulted is the same silent loss in a smaller costume.
    """
    if not effective:
        return []
    if isinstance(effective, dict):
        return list(effective.values()) if "pack_id" not in effective else [effective]
    return [p for p in effective if isinstance(p, dict)]
