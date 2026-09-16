"""Which readings are producing nothing, declared — with a reason and a mover.

A READING THAT RETURNS NOTHING IS INDISTINGUISHABLE FROM ONE THAT IS BROKEN, from the card side
and from the log. Five lanes in this layer were dead for months while looking wired, and every one
was found by accident rather than by a check:

  * `dependency_stated` — 95 claims dropped a sweep, noticed in a census
  * the nine business nouns — 1,211 extracted, 5 in the graph, noticed in a field count
  * thread names — noticed by the person reading the cards
  * `median` in `read_outreach_cohorts` — an unbound global, found by a test written for something else
  * `meeting_follow_through` — TWO faults, an unbound `_MEETINGS` and a join on a fact no writer
    has ever produced, found in a sweep's warning log

This file is the same fact where it cannot be missed. `tests/context/test_no_lane_is_silently_
dead.py` fails when a registered reading produces nothing and is not listed here, and fails just as
loudly when a lane listed here starts producing and nobody removed it. It is the reading-level twin
of `patterns/routing.UNROUTED_PATTERN_TYPES`, and it carries that file's rule: a permanent
exception list is a way to never fix anything, so every entry names what would end it.

DORMANT IS NOT BROKEN, AND THE DIFFERENCE IS THE WHOLE POINT. A lane with nothing to say on this
tenant's data is correct. A lane that CANNOT say anything on any tenant's data is a defect wearing
the same face. Each entry below has to say which it is.
"""

#: `{reading anchor: why it produces nothing, and what would change that}`.
DORMANT_LANES: dict[str, str] = {
    "unnamed_blocker":
        "DATA, NOT CODE. The field is written only where the BLOCKED end of a dependency resolves "
        "to a node and the blocker does not. Layer 1 extracts dependencies between OUTCOMES — "
        "'interview slot offer for GeniOS', 'Shortlisting and showcase participation' — so on a "
        "mail-only tenant NEITHER end resolves and the traversal refuses before an absence can be "
        "typed. Measured 2026-09-15: 95 claims read, 0 missing prerequisites, and still 95 of 95 "
        "after the person-name index landed, because these endpoints are not names. The refusal "
        "is right: a false chain is worse than a missing one. Full reasoning in "
        "`context/blocker_situations.py`. "
        "MOVES WHEN: L1 extracts a dependency whose blocked end is a party rather than an "
        "outcome — a tenant with a ticketing or project source, or an extractor asked for the "
        "owing party alongside the owed outcome.",

    "condition_met":
        "THE PARSER REFUSES, AND IT IS RIGHT TO. `correlate_timeline` sorts every dormant "
        "condition into satisfied / waiting / unknown / review, and `condition_met` reads the "
        "first. Measured 2026-09-15: 15 conditions built, **15 of them to review and 0 to the "
        "other three**, because `parse_condition` turns none of them into a checkable predicate. "
        "The texts are why: 'if you're open to it', 'when you get a chance, just loop them into "
        "this thread', 'if that works for Rohit of course'. Those are social conditions, not "
        "mechanical ones, and a parser that forced them into predicates would manufacture "
        "satisfaction events out of politeness. `condition_in_review` is the lane built for "
        "exactly this and it produces 13 cards from the same 15 conditions, so nothing is lost. "
        "MOVES WHEN: a tenant's mail carries conditions with a checkable shape — a date, a "
        "threshold, a named deliverable — which `parse_condition` already handles and this "
        "tenant's correspondence does not contain.",

    "cohort":
        "THE GROUPING KEY CANNOT GROUP. `read_outreach_cohorts` groups people by an identical "
        "`thread.objective`, and the objective L1 supplies is a bespoke SENTENCE that names its "
        "participants — 'introduction and meeting between Rohit and Shourya', 'schedule a meeting "
        "between Hirdesh and Rohit'. A sentence built that way is unique to its thread by "
        "construction, so two people practically never share one. Measured 2026-09-17 across all "
        "189 distinct objectives: 236 subjects carry one and only 24 of those subjects are "
        "PEOPLE — the rest are thread nodes — so four objectives reach two people and none "
        "reaches three, against a `_MIN_COHORT` of 3. The earlier reading of this said every "
        "group has exactly one person; four have two, and the lane is just as dormant. "
        "The lane needs a CATEGORICAL objective — the closed set `_OUTREACH_OBJECTIVES` "
        "describes — and deriving one from the sentence by matching words in Layer 2 would be a "
        "keyword rule tuned on one tenant's vocabulary, which is the failure this layer exists to "
        "avoid. `campaign_awaiting_reply` answers the group question meanwhile, from the sentence "
        "we actually SENT, which is shared across recipients by construction. "
        "MOVES WHEN: L1's prompt and contract ask for a categorical objective alongside the "
        "sentence. Nothing in Layer 2 changes when it does — the reading and the "
        "person-to-thread traversal already work.",

    "meeting":
        "NOTHING HAS HAPPENED YET, and this is the only entry here that is purely a matter of "
        "time. The query and the reading were both broken until 2026-09-15 — an unbound "
        "`_MEETINGS` raised on every sweep, and underneath it a join on "
        "`meeting.external_counterparty`, a field zero rows in this database have ever carried. "
        "Both are fixed, and the lane now finds the tenant's one qualifying meeting: 'Spotlight "
        "call-2' with one genuine external attendee. It produces no card because that meeting is "
        "on 2026-09-21 — in the future — and a follow-through card about a meeting nobody has had "
        "yet would be exactly the invented touch `touch-outside-mail.yaml` objects to. Another org "
        "in the same database goes 0 -> 7 with the fix. "
        "MOVES WHEN: that meeting happens. No code change is involved and none should be.",
}


def undeclared(producing: dict[str, int]) -> tuple[str, ...]:
    """Anchors that produced nothing this run and are not declared above.

    `producing` is `{anchor: findings}` as the readings actually answered. Returns the anchors a
    reader has to explain — the class that has cost this layer five lanes.
    """
    return tuple(sorted(a for a, n in producing.items() if not n and a not in DORMANT_LANES))


def revived(producing: dict[str, int]) -> tuple[str, ...]:
    """Anchors declared dormant that are producing again — the entry is now a lie."""
    return tuple(sorted(a for a, n in producing.items() if n and a in DORMANT_LANES))


__all__ = ["DORMANT_LANES", "revived", "undeclared"]
