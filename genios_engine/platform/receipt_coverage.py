r"""Which package each production receipt guards — declared, so the count is never prose again.

⛔ WHY THIS MODULE EXISTS. `STEP-10` claimed *"L5 is 9,431 lines and carried 2 of the programme's 33
receipts — 4,715 lines per guard"*, and the number was **wrong in three ways**: `deliver/` carried
**5**, lines per guard was **1,886**, and **four** of the five worked rather than one. The count had
been derived once, by hand, by filtering on `Receipt.layer` — and `genios_engine/LAYERS.py` warns in
its own docstring that *"Atlas 5.2 is our `deliver` (6), and Atlas 6 is our `feedback` (7) — **so
always name the package, never the digit alone**."* The filter named the digit.

⛔ The wrong number then appeared in **eleven documents**, because *repetition is not corroboration*
— and **no assertion depended on it**, which is exactly why it survived review. *A claim worth
asserting is worth storing as data.*

⛔ THE MAPPING IS DECLARED, NOT PARSED, AND THAT WAS MEASURED FIRST. An outer-`from` resolver fails
on **4 of 40** receipts, each of which reads `select … from ( <subquery> )` — a derived table whose
real source is inside the parentheses. Two earlier attempts at parsing produced confident wrong
answers: `[a-z_]+` stops at the digit in `l2_convergence` and reports the table as `l`, and
`jsonb_each` is a function rather than a table. **A resolver that is merely stricter is not more
correct**, so each claim names its package by hand and a guard checks the SET in both directions.

⛔ `Receipt.layer` IS NOT TOUCHED, AND THAT IS DELIBERATE. `receipts(layer)` filters on that string,
so relabelling changes which receipts an operator's layer-scoped run executes. The labels are a
mixture of two vocabularies — `944b4f76` *("all seven layers")* used `LAYERS.py`'s numbering and
`22d598b1` *("all six product layers")* mixed the Atlas's into the same field — and sorting that out
is a decision, not a tidy-up. This module answers the question the label cannot, and leaves it
alone.

⛔ A THIRD CATEGORY EXISTS AND FORCING IT INTO A PACKAGE WOULD BE A LIE. Some claims go red for
reasons **no package can fix**: a tenant with no seats, no manager, no pack binding, no channel. A
human adds those. Calling them `deliver/`'s guards or `context/`'s guards would inflate a package's
coverage with work it cannot do, so they are declared `READINESS`.
"""
from __future__ import annotations

from genios_engine.platform.receipts import receipts

#: Claims that go red for a reason no engine package can repair — a human must act on the tenant.
READINESS = "readiness"

#: ⛔ `{claim: (package, why)}` for every production receipt.
#:
#: `package` is the engine package whose behaviour the receipt guards — **not** necessarily the
#: package that writes the table. A receipt over `graph_facts` can guard `reason/`'s contract
#: against `context/`'s data, and the thing an operator would go and read is `reason/`.
#:
#: ⛔ Checked in BOTH directions by `tests/platform/test_a_receipt_names_the_package_it_guards.py`:
#: a new receipt with no entry fails the build, and an entry naming a claim that no longer exists
#: fails it too. **Referred to by CLAIM, never by position** — receipt numbers are positional and
#: inserting one earlier in the list moves every number after it.
RECEIPT_PACKAGE: dict[str, tuple[str, str]] = {
    # ── capture/ · read + normalise reality ────────────────────────────────────────────────
    "no sync cursor is ahead of the clock": (
        "capture", "A cursor past the clock means the connector will skip real events"),
    "no warm-lane row is parked where nothing can see it": (
        "platform",
        "⛔ `platform/warm_lane.py` parks a row whose attempts ran out — the schema comments it "
        "*'parked for a human, never retried'* — and then every reader excludes it: `_OPEN` is "
        "`done_at is null and parked_at is null`, `api/routes`'s backlog count uses the same "
        "predicate, `housekeep` warns on the OPEN backlog and prunes only finished rows. ⛔ The "
        "health signal does not merely miss these rows, it excludes them by construction, so a "
        "stuck tenant reports a clean lane. Filed under `platform` because the lane, the "
        "predicate and the park are all `warm_lane.py`'s"),
    "the parked queue is not a black hole": (
        "capture", "Parked events must be reviewable; `capture/` owns the park and the triage"),
    "every captured event that reached no signal says where it stopped": (
        "capture",
        "⛔ `capture/journey.py` exists for one sentence — *'a system that discards 92% of what a "
        "founder was sent has to be able to answer \"why did I never see X?\" in one query'* — and "
        "records that the join was missing while every layer wrote its own refusal down. The "
        "sibling drop receipt asks a narrower question (can a model's JUDGMENT still be reviewed); "
        "this one asks whether an answer exists at all. Filed under `capture` because the event, "
        "the trace and the park are all its own"),
    "every drop we might be wrong about can still be reviewed": (
        "capture", "The gate's drops keep their payload and trace — `capture/`'s own contract"),
    "every archived mail can still be read": (
        "capture", "STEP-03: the gate archives what it used to delete, and the archive keeps its "
                   "body — `capture/pipeline.py` writes it, `capture/` owns the promise"),
    "the tenant is still being fed": (
        "capture", "No recent `source_events` means the connectors stopped, which is `capture/`'s"),
    "attachments carry readable text": (
        "capture", "`document_jobs` is the OCR/extraction pipeline this package owns"),

    # ── platform/ · the schema itself ──────────────────────────────────────────────────────
    "a deleted tenant leaves nothing behind": (
        "platform", "⛔ A claim about the SCHEMA, not a tenant: every org-scoped table reachable "
                    "from `orgs` must cascade. `platform/` owns migrations and the cascade, and "
                    "the receipt is declared fleet-wide for the same reason"),

    # ── context/ · situation intelligence ──────────────────────────────────────────────────
    "no person node holds thread state fed by several threads": (
        "context", "A person node with two live `thread.ball_in_court` facts is a graph-merge "
                   "defect. ⛔ Its outer `from` is a derived table; the real source is "
                   "`graph_facts`"),
    "no live row points at a node a merge absorbed": (
        "context",
        "⛔ `context/`'s THIRD receipt and the first about entity merge — the one operation that "
        "rewrites identity across the graph. 50,877 lines and 124 files had two receipts, neither "
        "covering it, and `merge.py`'s own comment names the failure: *'Missing one leaves rows "
        "pointing at a closed node.'* The pairs are DERIVED from the three declared constants, so "
        "a sixth table entering the merge loop enters this receipt without an edit"),
    "the sweep settles instead of chasing itself": (
        "context", "`l2_convergence` is this package's own convergence ledger"),

    # ── packs/ · domain expertise, a plane ─────────────────────────────────────────────────
    "compiled expertise packages exist": (
        "packs", "`expertise_packages` is this package's compiler output"),

    # ── reason/ · deterministic cognition ──────────────────────────────────────────────────
    "the live pass has actually run, not only the shadow pass": (
        "reason", "`reasoning_runs` is this package's run ledger"),
    "every reasoning unit that says nothing is one we declared": (
        "reason", "A silent unit must be a DECLARED silence. ⛔ Derived-table outer `from`; the "
                  "real source is `reasoning_reasoner_results`"),
    "every unit that runs and never completes is a declared one": (
        "reason", "The third kind of silence — runs and never completes. ⛔ Derived-table outer "
                  "`from`; the real source is `reasoning_reasoner_results`"),
    "no fact holds two authority scales at once": (
        "capture", "⛔ The table is `graph_facts` (`context/`'s) and the comparison is "
                   "`context/graph_store.fact_write_action`'s -- but the LADDER is "
                   "`capture/validate/authority`'s, it is the thing that defines what a rank "
                   "means, and `UNINTERPRETABLE_RANKS` there is where the collision is declared. "
                   "*A receipt guards a contract, not a table*: an operator reading this goes to "
                   "the ladder to find out which scale is right"),
    "no live connection feeds a source that satisfies no capability": (
        "capture", "⛔ The table is `connections` (`0002_l1_tables.sql`) and the CLAIM is "
                   "`capture/source_registry`'s: it decides what `buildable` means and which "
                   "capability a source satisfies. An operator reading this goes to the "
                   "descriptor, which is the one place a source is described"),
    "every recently qualified signal carries a coverage verdict": (
        "capture", "`qualified_signals.coverage_ready` is written by `capture/pipeline`'s "
                   "`coverage_verdict` off `capture/esqe/domain.tag_domains`. The CLAIM is the "
                   "contract's own sentence -- *a freshly gated event always carries a real bool* "
                   "-- so an operator reading this goes to the domain tagger"),
    "no published reasoning package was routed by picking one of several domains": (
        "reason", "⛔ The table is `expertise_packages` (`0047_l3_domain_compiler.sql`, so L3's) "
                  "and the CLAIM is about `reason/adapters/expertise`'s `domain_ids[0]`, which "
                  "becomes `CapabilityManifest.domain` and picks the TENANT PACK in "
                  "`reason/domain_shadow`. The thing an operator would go and read is the routing "
                  "site. *A receipt guards a contract, not a table* -- the same reason the bound "
                  "fact-path receipt is `reason/` while its table is `context/`'s"),
    "the current reasoning era selects, not only defers": (
        "reason", "An era that only defers is a reasoner that never decides"),
    "every fact path a reasoning unit binds is written or declared unwritten": (
        "reason", "⛔ The table is `graph_facts` (`context/`'s) and the CLAIM is about the paths a "
                  "reasoning unit BINDS — the thing an operator would go and read is `reason/`'s "
                  "roster. *A receipt guards a contract, not a table*"),
    "more than one candidate is ever considered": (
        "reason", "A scorer that sees one candidate is not choosing. ⛔ Derived-table outer "
                  "`from`; the real source is `reasoning_candidates`"),
    "the score components the scorer writes NOW are measured, not placeholders": (
        "reason", "`reasoning_candidates`' component columns, as the live scorer writes them"),
    "the system has abstained at least once": (
        "reason", "An engine that never abstains is not applying its own confidence floor"),

    # ── executive/ · decisions and who/where they reach ────────────────────────────────────
    "every action that needs sign-off can name who signs": (
        "executive", "`execution_actions` joined to `authority_rules`. ⛔ `feedback/` WRITES the "
                     "rules; `executive/` is the package that must honour them, and it is where "
                     "an operator would look"),
    "decisions become tracked commitments": (
        "executive", "`executions` is this package's own ledger. ⛔ Labelled `L5`, which under "
                     "`LAYERS.py` is `executive` (5) — one of the few labels that is consistent"),

    # ── deliver/ · render, gate, send, track ───────────────────────────────────────────────
    "every delivered card carries a lane, or is labelled unrouted": (
        "deliver", "`cards.output_lane`. ⛔ ERRORs until migrations `0189`/`0190` are applied"),
    "no card outlives its own window in a live state": (
        "deliver", "The 12-hour grace is derived from a measured 6.0-hour sweep interval"),
    "a card parked for want of a channel is revived when one appears": (
        "deliver", "`delivery_outbox` joined to `org_channels`; the revive is this package's"),
    "no delivery attempt is left unsettled long enough to be ambiguous": (
        "deliver", "`delivery_attempts` — the v2 control plane's own ledger"),
    "cards distinguish a warning from an order": (
        "deliver", "`cards.level`. ⛔ Labelled `L6`, which under `LAYERS.py` is `deliver` (6)"),
    "no card gives an order with an empty draft": (
        "deliver", "A prescriptive card with no body is this package's render contract"),
    "the delivery control plane has run": (
        "deliver", "`delivery_outbox` — whether the v2 plane has written anything at all"),

    # ── feedback/ · the learning engine ────────────────────────────────────────────────────
    "the learning engine has executed": (
        "feedback", "`learning_runs` — the weekly per-tenant claim"),
    "no completed learning run hides whether it dropped inbox rows": (
        "feedback", "⛔ This layer's FIRST correctness receipt (`S5`). Guards the visibility of "
                    "`inbox_unconsumed`, not the known drop"),
    "every proposal a completed learning run made is recorded as a decision": (
        "feedback", "⛔ The Atlas's no-silent-drop contract (`S6`). One evaluation row per "
                    "proposal, held and refused included"),
    "no learning transition takes an edge the contract forbids": (
        "feedback", "⛔ `ALLOWED_LEARNING_TRANSITIONS`, derived into the SQL. `publisher.publish` "
                    "wrote `governed → published` until `S6`"),
    "no active brain value is narrower than the surface that renders it": (
        "feedback",
        "⛔ The half the code guard cannot reach. `feedback/target_policy` proves statically that "
        "no PRODUCER proposes a constrained durable value; the human approval path rehydrates "
        "visibility from `learning_objects.visibility`, so only a query against the data can "
        "close it. Filed under `feedback` because the sinks are `publisher`'s and the gap it "
        "guards is Atlas L7 #5 — even though the unguarded READER lives in `api/`"),
    "no learning input has been quarantined": (
        "feedback", "⛔ `learning_input_rejections`' first reader (`S7`). Routine discovery "
                    "refusals are excluded — those are counted per run in "
                    "`org_rule_discovery_runs.counters`"),
    "a completed learning run says which seams it lost, not only which were empty": (
        "feedback", "⛔ `L7-29`'s *expose the empty reason*. `quarantined_seams` beside "
                    "`degraded_seams`"),
    "calibration has executed": (
        "feedback", "`calibration_runs` — the weekly precision/auto-mute pass"),
    "the counterfactual ledger joins end to end": (
        "feedback", "⛔ A VIEW (`0072`), joining signal → card → events → verdict → delivery → "
                    "execution → spend. Nothing writes it, by design"),
    "a human verdict has reached the loop": (
        "feedback", "⛔ `card_feedback_verdicts` is written by `api/`; the package that must "
                    "CONSUME it is `feedback/`, and a red means the loop has no human input"),

    # ── readiness · no package can repair these ────────────────────────────────────────────
    "the tenant's own identities are known": (
        READINESS, "⛔ `org_seats` with no rows means nobody has been added to the tenant. No "
                   "engine package can fix that — a human invites a seat"),
    "the tenant has at least one active seat": (
        READINESS, "⛔ The same fact asked as a readiness gate. Forcing it into a package would "
                   "inflate that package's coverage with work it cannot do"),
    "at least one seat has a manager": (
        READINESS, "⛔ `manager_seat_id` is the standing line an authority override sits on, and "
                   "it is set by a human during onboarding"),
    "the tenant is bound to a pack": (
        READINESS, "⛔ `packs/` COMPILES packs; binding one to a tenant is an activation "
                   "decision. A red here is 'nobody activated a domain', not a defect in `packs/`"),
    "there is a channel this tenant can be reached on": (
        READINESS, "⛔ `org_channels` is written by `api/` when a human connects Slack. A red "
                   "means the tenant is unreachable, which `deliver/` cannot repair — and L5's "
                   "own findings record that an empty outbox on a channel-less tenant is the "
                   "EXPECTED state"),
}


def declared_claims() -> frozenset[str]:
    return frozenset(RECEIPT_PACKAGE)


def live_claims() -> tuple[str, ...]:
    """Every claim `platform/receipts.py` actually ships, in order."""
    return tuple(r.claim for r in receipts(None))


def undeclared_receipts() -> tuple[str, ...]:
    """⛔ Receipts with no declared package — a new guard whose coverage nobody counted."""
    return tuple(c for c in live_claims() if c not in RECEIPT_PACKAGE)


def stale_declarations() -> tuple[str, ...]:
    """⛔ The second direction: an entry naming a claim that no longer ships."""
    live = frozenset(live_claims())
    return tuple(sorted(c for c in RECEIPT_PACKAGE if c not in live))


def duplicate_claims() -> tuple[str, ...]:
    """⛔ Two receipts sharing one claim string would collapse into one entry and under-count.

    `receipts()` is a list, and nothing stops two entries from carrying the same claim — at which
    point a dict keyed on the claim silently loses one. The guard that makes this mapping
    trustworthy has to rule that out rather than assume it.
    """
    seen: dict[str, int] = {}
    for claim in live_claims():
        seen[claim] = seen.get(claim, 0) + 1
    return tuple(sorted(c for c, n in seen.items() if n > 1))


def receipts_per_package() -> dict[str, int]:
    """`{package: how many production receipts guard it}` — the number `STEP-10` got wrong."""
    out: dict[str, int] = {}
    for claim in live_claims():
        pkg = RECEIPT_PACKAGE.get(claim, (None, ""))[0]
        if pkg:
            out[pkg] = out.get(pkg, 0) + 1
    return out


def correctness_per_package() -> dict[str, int]:
    """`{package: receipts that go red when a row EXISTS}`.

    ⛔ The distinction the L6 re-crosscheck turned on: a **presence** receipt (`expect(0)` False)
    asks *"has it run?"* and is satisfied by one successful tick; a **correctness** receipt
    (`expect(0)` True) asks *"is what it wrote right?"*. `feedback/` had **four receipts and zero
    correctness** before `S5`. Counting guards without reading them hid that for the whole
    programme — *guards per line counts guards; it does not read them.*
    """
    out: dict[str, int] = {}
    for receipt in receipts(None):
        pkg = RECEIPT_PACKAGE.get(receipt.claim, (None, ""))[0]
        if pkg and receipt.expect(0) is True:
            out[pkg] = out.get(pkg, 0) + 1
    return out


def thin_declarations() -> tuple[str, ...]:
    """Entries whose reason says nothing usable. A mapping with no reason per row teaches a reader
    to skip the rows that have one."""
    return tuple(sorted(c for c, (_pkg, why) in RECEIPT_PACKAGE.items() if len(why) < 30))


__all__ = ["READINESS", "RECEIPT_PACKAGE", "correctness_per_package", "declared_claims",
           "duplicate_claims", "live_claims", "receipts_per_package", "stale_declarations",
           "thin_declarations", "undeclared_receipts"]
