"""Which pattern situation types no domain claims — declared, with a reason and a mover.

A PATTERN THAT FIRES INTO AN UNBOUND TYPE PRODUCES NOTHING, and produces it silently. The chain is
pattern → `pattern_fires.situation_type` → a situation of that type → an L3 capability keyed on it
→ a card. When no authored situation binds the type, the chain ends at step three: the corpus
tooling reports it as *"emitted by Layer 2, bound by no domain — no capability will ever compile
for it"*, and nothing in the engine or the test suite says a word.

That report is a line in a tool nobody runs on a normal day. This file is the same fact where it
cannot be missed: `tests/context/patterns/test_every_pattern_can_reach_a_card.py` fails if a seed
pattern's type is neither bound nor listed here, and fails just as loudly if an entry here has
since been bound and nobody removed it. `tests/test_nothing_is_written_and_never_read.KNOWN_UNREAD`
is the same idea for fields, and its rule applies here: a permanent exception list is a way to
never fix anything, so every entry names the condition under which it stops being one.

WHY THESE FIVE ARE NOT SIMPLY AUTHORED AWAY. Four of them cannot fire at all on a tenant whose
only connected source is mail, and authoring a reviewed situation document for a pattern that
cannot produce a candidate would add corpus nobody can test against real data — the "more dead
code, not less" argument `KNOWN_UNREAD` already makes for `derived.contract_spend.summary`. The
binding is the LAST step for these, not the first.
"""

#: `{situation_type: why it is unbound, and what would change that}`.
#:
#: Checked in both directions. An entry that becomes bound must be deleted, and a seed pattern
#: whose type is neither bound nor here fails the suite — so this cannot silently rot into a list
#: of things that used to be true.
UNROUTED_PATTERN_TYPES: dict[str, str] = {
    "vendor_renewal_decision":
        "Anchored on `node_type: subscription`, and the pattern's own header states the problem "
        "in its first line: 'a pattern anchored on a node type nothing creates is a pattern that "
        "can never fire'. Nothing mints subscription, contract or invoice nodes on a tenant using "
        "the built-in mappings — only a client-supplied GENIOS_STRUCTURED_MAPPINGS does, which is "
        "the same reason `derived.contract_spend.summary` sits in KNOWN_UNREAD. Binding it today "
        "would author a reviewed document for a pattern that cannot produce a candidate. "
        "MOVES WHEN: a tenant emits subscription nodes, at which point "
        "`admin.sit.vendor_relationship_live` is the authored neighbour to extend rather than a "
        "new file.",
    "meeting_preparation_gap":
        "Requires `meeting.agenda` to come back GENUINELY_ABSENT, and no writer in the engine "
        "produces `meeting.agenda` at all — so the absence can only ever be UNKNOWABLE, which the "
        "pattern correctly refuses to fire on. Its own header says why that distinction matters: "
        "'a calendar we can read and an agenda field we cannot are the same empty string, and "
        "only the typed answer tells them apart'. The gap is an ingestion one, not a corpus one. "
        "MOVES WHEN: a calendar source writes `meeting.agenda` and an expectation map declares "
        "it, so absence can be typed.",
    "relationship_going_cold":
        "Needs `account.status = active` on a company anchor plus a declining TREND and a "
        "bottom-quartile COHORT position on `engagement.touch_count_28d`, with the pattern's own "
        "floors — trend confidence >= 5000, population >= 5. A tenant whose counterparties are "
        "investors and introducers has no account population to be a quartile of, and the pattern "
        "is right to stay silent rather than call a small correspondent a leaving customer. "
        "MOVES WHEN: a tenant carries enough company anchors for the cohort floor to be "
        "satisfiable, which is a data question and not a binding one.",
    "commitment_unresolved":
        "Requires `commitment.delivered_at` GENUINELY_ABSENT, which needs an expectation map "
        "declaring that field for absence to be typed rather than UNKNOWABLE — the pattern's own "
        "header lists this as one of the two things that would keep it silent. Deliberately NOT "
        "bound to `commitment_overdue`, which is the nearest live type: that one says a promise's "
        "date has passed, this one says we checked for delivery and found none, and a card "
        "claiming the second on the evidence of the first is the stronger claim made without the "
        "receipt. MOVES WHEN: an expectation map declares `commitment.delivered_at`.",
    "founder_bottleneck":
        "The one here whose inputs are computed rather than ingested: `authority_view.bottleneck` "
        "resolves `authority.sole_approver_subject_count` at eval time and injects it into the "
        "slice, from ENFORCEABLE rules only. It is unbound because no domain has claimed the "
        "situation, not because it cannot fire — and the honest reason to leave it is that on a "
        "two-person company every approval is sole-approved, so the pattern is structurally true "
        "and tells a founder nothing they do not know. MOVES WHEN: a domain authors it, which is "
        "worth doing for a tenant with a real approval chain.",
}

__all__ = ["UNROUTED_PATTERN_TYPES"]
