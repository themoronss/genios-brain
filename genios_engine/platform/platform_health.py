r"""What `platform/` deliberately does not call — the cross-cutting plane's declared silence.

⛔ TWO PATTERNS DOMINATE, AND BOTH ARE ASYMMETRIES. **The rollback halves of live features are
unwired** — `l2_activation.deactivate` and `l3_activation.deactivate` can each turn one switch off,
and nothing can reach either, so a feature that an operator can enable through a surface can only be
disabled from a Python shell. And **the funnel's three reads have no reader** while its five counters
are written every pass.

⛔ ONE FUNCTION WAS RESCUED FROM THIS TABLE BY HAND. `realtime.purge_expired` looked unreached and is
called at `api/routes.py:964` as `store.purge_expired()` behind a `hasattr` check — **duck-typed
dispatch, which no static walk can see.** Retention IS enforced. Sixteen other candidates turned out
to be name collisions (`list.extend`, `Path.resolve`, `.read()`), which is why each was read rather
than counted.

The machinery is `platform/reachability.py`, shared rather than copied. ⛔ Three wiring mechanisms
are subtracted before anything reaches this table — a **call**, a **decorator**, a **reference**
(`Depends(f)`, a dispatch table, a registry) — and a fourth cannot be: **duck-typed dispatch**
(`store.purge_expired()` on a variable) is invisible to any static walk, so every entry below was
hand-checked against it. One function was rescued that way; sixteen candidates turned out to be name
collisions.
"""
from __future__ import annotations

from pathlib import Path

from genios_engine.platform.reachability import (engine_sources, missing, now_called,
                                                 package_functions, undeclared)

_PKG = Path(__file__).resolve().parent
_ENGINE = _PKG.parent


#: ⛔ Public functions in `platform/` with no production caller — `{name: (why, mover)}`.
#:
#: CLOSED, and checked in BOTH directions by `tests/platform/test_the_platform_layer_says_what_it_does_not_call.py`.
UNREACHED: dict[str, tuple[str, str]] = {
    # ───────────────────────────────── receipt_coverage · guards per package as DATA (7)
    # ⛔ ALL SEVEN ARE BUILD-TIME REPORT FUNCTIONS over the checked-in receipt list. They take no
    # production data, so their answer cannot differ between two runs of the same build — the
    # filing `feedback/` uses for its own seven, and the lesson L5 paid for with `lane_recall`:
    # **a function that takes no production data cannot be measuring production.**
    #
    # ⛔ THEY EXIST BECAUSE A HAND-DERIVED COUNT WAS WRONG IN ELEVEN DOCUMENTS. `STEP-10` claimed
    # *"L5 is 9,431 lines and carried 2 of the programme's 33 receipts — 4,715 lines per guard"*;
    # `deliver/` carried **5**, the figure was **1,886**, and **four** of the five worked. The count
    # had been derived once by filtering `Receipt.layer` — the digit `LAYERS.py` forbids reading
    # alone. *A claim worth asserting is worth storing as data.*
    # ─────────────────────────────────── the table-coverage guards (the `context/` audit)
    # ⛔ THIS BLOCK SAID "(5)" AND TWO OF THE FIVE WERE LIES. `table_usage` and
    # `written_without_a_receipt` are called by `scripts/context_coverage_report.py`, the report
    # generator written in the same step — and `reachability.SCRIPTS_ARE_CALLERS` is `True`, so a
    # script IS a caller. ⛔ The full suite caught it:
    # `test_no_declared_entry_has_quietly_acquired_a_caller[platform]`, with the right message —
    # *"the entry is the lie, not the call."*
    #
    # ⛔ AND IT IS EVIDENCE FOR THE OPEN POLICY CALL. `19-PENDING` asks *"does `scripts/` count as
    # a caller?"* and the flag's own comment records the answer as **my call taken while the
    # question was open**. A generator an operator runs to learn which tables nothing checks is
    # exactly the case the recommendation was built on — so this step produced a real instance of
    # it rather than another argument.
    #
    # The three below have no caller at all: nothing but the guard that enforces this table reads
    # them, which is the shape every entry here has.
    # ⛔ BUILD-TIME PROPERTY GUARDS, the same filing as `receipt_coverage`'s below. They read the
    # repo's SQL and the migrations and answer questions about a FIXED checkout — identical on
    # every run, touching no production data. The half that only production can answer is a
    # RECEIPT: *"no live row points at a node a merge absorbed"*.
    "table_coverage.illegal_column_updates": (
        "⛔ Every update of a WRITE-ONCE table outside its declared allowlist. Returns `()` and "
        "the emptiness is load-bearing: `learning_objects` holds the whole learning ledger's "
        "immutable proposals, `publisher.persist`'s first line states the contract — *'Insert an "
        "**immutable** proposal at `state`'* — and until 2026-10-03 **nothing asserted it**. The "
        "engine has exactly two `update learning_objects` statements and both set only `state`",
        "⛔ MOVES WHEN a proposal legitimately needs a mutable field, which is a contract decision. "
        "A build-time guard rather than a receipt on purpose: a value rewritten in place leaves no "
        "trace unless `semantic_hash` is recomputed, and recomputing it in SQL would mean "
        "reimplementing the canonical serialisation in a second language"),
    "table_coverage.undeclared_unread_writes": (
        "The positive half of `UNREAD_WRITES` — a package writing a table nothing reads, "
        "undeclared. ⛔ The audit's first pass named SIX and nine survived three broadenings of "
        "the resolver; this is what stops a tenth arriving silently",
        "MOVES WITH `stale_unread_declarations` — the two halves of one both-ways check"),
    "table_coverage.stale_unread_declarations": (
        "The negative half: a declared write-only table that now has a reader. ⛔ It is how "
        "`edge_coverage_declarations` and `l2_model_runs` were RETRACTED rather than left standing",
        "MOVES WITH `undeclared_unread_writes` — the two halves of one both-ways check"),
    "table_coverage.deletion_list": (
        "The tables the tenant `/reset` loop names, read off `api/account_routes.py`'s AST. ⛔ It "
        "exists to STOP a false finding: 77 of 183 org-scoped tables are in neither that list nor "
        "`RETAINED_AFTER_ERASURE`, which reads as a retention hole and is not one — `/reset` "
        "deliberately *'keeps the account, connections, tasks'* and ACCOUNT erasure is done by "
        "migration 0033's foreign keys",
        "MOVES WHEN the erasure contract changes shape. ⛔ The invariant itself is already guarded "
        "against the DEPLOYED schema by the receipt *'a deleted tenant leaves nothing behind'*, "
        "which is the only thing that can see a child cascading through a parent"),

    "receipt_coverage.undeclared_receipts": (
        "⛔ A BUILD-TIME TOTALITY GUARD. *'Receipts with no declared package — a new guard whose "
        "coverage nobody counted.'* Direction one of two, so a receipt added tomorrow cannot "
        "change a package's coverage unnoticed. One test caller, which is the correct and only one",
        "MOVES WHEN an operator surface shows guards per package. ⛔ Never into a sweep: the answer "
        "is a property of the checked-in receipt list and is identical on every run"),

    "receipt_coverage.stale_declarations": (
        "⛔ THE SECOND DIRECTION, AND IT CAUGHT ME TWICE ON ITS FIRST RUN. *'An entry naming a "
        "claim that no longer ships.'* I built the declaration from a dump that truncated each "
        "claim at 62 characters, so two keys were cut short — direction one called them undeclared "
        "and this one called them stale, naming both halves of one mistake. ⛔ **A totality guard "
        "that runs one way is half a guard**, and the half that is easy to skip is the half that "
        "found this",
        "MOVES WITH `undeclared_receipts` — the two check one mapping from opposite sides and "
        "neither is wanted at runtime"),

    "receipt_coverage.duplicate_claims": (
        "⛔ *'Two receipts sharing one claim string would collapse into one entry and under-count.'* "
        "`receipts()` is a LIST and nothing stops two entries carrying the same claim, at which "
        "point a dict keyed on the claim silently loses one. **The guard that makes this mapping "
        "trustworthy has to rule that out rather than assume it**",
        "⛔ MOVES WHEN `Receipt` carries a unique id of its own. Until then the claim IS the key, "
        "and the house rule is to refer to a receipt by its claim because numbers are positional"),

    "receipt_coverage.receipts_per_package": (
        "⛔⛔ THE NUMBER `STEP-10` GOT WRONG, now derived. *'{package: how many production receipts "
        "guard it}'*. It also found that the step was aimed at the wrong package: `context/` is "
        "**50,877 lines with TWO guards** — 25,438 per guard, **5.4x worse than the 4,715 that "
        "triggered `STEP-10`** — while `deliver/` is now the third-best covered package in the "
        "product",
        "MOVES WHEN a readiness or ops surface prints coverage per package. ⛔ That surface is "
        "exactly what would have caught the original error, and it does not exist"),

    "receipt_coverage.correctness_per_package": (
        "⛔ *'{package: receipts that go red when a row EXISTS}'* — the distinction the L6 "
        "re-crosscheck turned on. A **presence** receipt asks *'has it run?'* and is satisfied by "
        "one successful tick; a **correctness** receipt asks *'is what it wrote right?'*. "
        "`feedback/` had four receipts and **zero** correctness before `S5`. ⛔ Counting guards "
        "without reading them hid that for the whole programme: *guards per line counts guards; it "
        "does not read them*",
        "MOVES WITH `receipts_per_package` — the two halves of one coverage report, and neither is "
        "wanted at runtime"),

    "receipt_coverage.declared_claims": (
        "The declared key set as a frozenset — a reader for the two direction checks and for any "
        "test that needs to compare the declaration against something else without importing the "
        "dict and re-deriving it",
        "MOVES WITH the two direction checks it serves"),

    "receipt_coverage.thin_declarations": (
        "⛔ *'Entries whose reason says nothing usable.'* **A mapping with no reason per row teaches "
        "a reader to skip the rows that have one** — the rule `STEP-17` established for every "
        "declaration table in this engine, applied to this one",
        "MOVES WHEN the reason becomes a structured field rather than prose. ⛔ L5 learned that "
        "one the hard way: a substring check on prose passed on correct data and failed on correct "
        "data, which is why `UNCUT_OVER` carries a structured `measured_by`"),

    "l3_activation.is_l3_activated": (
        "⛔ ITS DOCSTRING CALLS ITSELF *'The hot-path read'* AND NOTHING ON ANY PATH READS IT. Ten test callers, zero production callers. *'Whether ONE tenant's ONE domain compiles on this pass.'* ⛔ The module's own header explains the design — *'FAIL CLOSED ON THE GATE, OPEN ON THE CONSOLE'* — and names this among the gate functions; the gate is enforced elsewhere, by `l3_activated_orgs` and the compiler's own per-tenant read at `:274`, which that line says is *'distinct from calling `is_l3_activated` three times'*. **So the single-domain read was superseded by a batched one and kept its name**",
        "⛔ MOVES WHEN a caller genuinely wants ONE domain's answer, or when it is deleted. The batched read exists because three single reads were the slower shape — so this is superseded in place rather than forgotten"),

    "l3_activation.l3_activated_orgs": (
        "*'Every org with ONE domain live. Empty for any reason it cannot be read.'* Five test callers. ⛔ The fail-closed default is the load-bearing part: a read that cannot answer returns EMPTY, so an unreadable activation table deactivates rather than activating everyone",
        "MOVES WHEN a sweep iterates activated orgs. ⛔ The compiler asks per tenant instead, which is the opposite direction and already wired"),

    "l3_activation.deactivate": (
        "*'Switch ONE domain off. True when a LIVE row was switched off — the rollback half of th'*e activation pair. Three test callers. ⛔ **The rollback half of a live feature, and it is the half nothing calls.** Activation is wired; turning it off is a function with no surface",
        "⛔ MOVES WHEN an operator can deactivate without SQL. That is the moment it is wanted and the moment it is urgent — a rollback nobody can reach is a rollback that does not exist"),

    "l2_activation.deactivate": (
        "*'Switch ONE switch off. True when a LIVE switch was switched off.'* Two test callers. ⛔ The same shape one layer down, and the same asymmetry: the switch can be turned on by a live path and off only from a Python shell",
        "MOVES WITH `l3_activation.deactivate` — ⛔ the two rollbacks are one operator need and shipping one is half an answer"),

    "funnel.read_sweep": (
        "*'One sweep's funnel, with `None` for a stage that wrote no row.'* Three test callers, and the `None` is deliberate: a stage that wrote nothing is distinguishable from one that wrote zero. ⛔ The five funnel counters ARE written on every pass; this is the read",
        "MOVES WHEN a surface shows the funnel. ⛔ The counters are the thing `19-PENDING` quotes by hand, which is what a missing reader looks like in practice"),

    "funnel.biggest_loss": (
        "*'Which adjacent pair lost the most, as `(from_stage, to_stage, lost)`.'* Five test callers. ⛔ The one-line answer to *where is the product leaking*, computed and asked by nothing",
        "MOVES WITH `read_sweep` — ⛔ the loss is derived from the sweep, so a reader for one is a reader for both"),

    "funnel.read_latest": (
        "*'Recent counter rows, newest sweep first. For an operator, not for a decision.'* No callers and no tests. ⛔ Its docstring names its reader — an operator — and the surface that reader would use does not exist",
        "MOVES WITH `read_sweep`. ⛔ **A function that names its reader and has no caller is a surface that was never built**"),

    "realtime.replay": (
        "*'The seat's events (and the org-wide ones) after `after_seq`, oldest first. One stateme'*nt. No callers and no tests. ⛔ The reconnect path of a realtime stream: a client that drops and comes back needs exactly this, and nothing serves it",
        "⛔ MOVES WHEN the SSE surface supports reconnect. Until then a dropped client loses the events it missed, which is the gap this function was written to close"),

    "analytics.identify": (
        "*'Update an account's person properties without recording a product action.'* No callers and no tests. The distinction is the point — identify is not an event — and nothing identifies",
        "MOVES WHEN onboarding or billing names a person to the analytics sink. ⛔ Product actions ARE recorded, so the sink is live and only the person properties are unset"),

    "analytics.stats": (
        "⛔ NO DOCSTRING, NO TEST, NO CALLER — one of two in this package with nothing anywhere. ⛔ **Why it is unreached is recorded nowhere**, and `analytics.py` otherwise documents itself carefully, which makes the silence here conspicuous rather than typical",
        "⛔ MOVES WHEN somebody who knows what it was for writes one line above it. Flagged in `HANDOFF-CODING-AGENT.md`"),

    "cache.l2key": (
        "*'L2 extraction cache key — ORG-SCOPED so tenant A's extraction can never be served to'* tenant B. Three test callers. ⛔ The org scoping is the whole safety property, and the live cache path builds its key elsewhere",
        "MOVES WHEN the L2 cache is read through one key builder. ⛔ Two key builders for one cache is exactly the shape that leaks across tenants, so this is worth closing before it is wanted"),

    "cache.okey": (
        "⛔ NO DOCSTRING, one test caller. An org-scoped key helper beside `l2key`, and nothing records how the two differ",
        "MOVES WITH `l2key` — ⛔ and whoever moves them should write down which key is for which cache, because the names do not say"),

    "billing.to_points": (
        "*'Credits -> points. A POSITIVE charge never lands on zero: rounding a real charge to fr'*ee is the failure it refuses. Five test callers. ⛔ The rounding rule stated once; the live billing path converts inline",
        "MOVES WHEN billing converts through one function. ⛔ The refusal to round a real charge to zero is a money property, and two implementations of a money rule is the worst kind of duplicate"),

    "crypto.generate_key": (
        "*'One-off helper to mint a GENIOS_CRYPTO_KEY.'* One test caller. ⛔ Correctly uncalled: it is a setup tool a human runs once per environment, and a key minted on a code path would be a key nobody recorded. The `Fernet.generate_key()` inside it is the library's, not this one",
        "⛔ MOVES WHEN it is deleted in favour of a documented shell one-liner. Never by being called: a secret generated by the engine is a secret with no owner"),

    "seats.backfill_owner_seats": (
        "*'Seat every org that has none. Orgs with seats are left completely alone.'* One test caller. ⛔ The idempotence is the load-bearing part — it cannot disturb a configured org — which is what makes it safe to run and uninteresting to schedule",
        "⛔ MOVES WHEN it is run, which needs an operator. Flagged for Harsh with the other backfills"),

}


#: ⛔ REACHED, BUT BY A MECHANISM NO STATIC WALK CAN SEE — `{name: (how, evidence)}`.
#:
#: A second table, because putting a REACHED function into `UNREACHED` would be a lie by that
#: table's own name. **A package gets the tables its triage needs**, and `platform/` needs this one
#: for exactly one function.
#:
#: ⛔ Duck-typed dispatch is the fourth wiring mechanism and the only one that cannot be resolved
#: statically: `store.purge_expired()` on a variable could be any object's method. The scan reports
#: it unreached, a human reads the call site, and the answer goes here — which is why every entry in
#: this package was hand-checked against it. Sixteen other candidates turned out to be name
#: collisions (`list.extend` with 96 apparent hits, `Path.resolve` with 74, `.read()` with 8).
REACHED_BY_DISPATCH: dict[str, tuple[str, str]] = {
    "realtime.purge_expired": (
        "⛔ CALLED THROUGH A DUCK-TYPED STORE, SO RETENTION *IS* ENFORCED. `api/routes.py:964` "
        "does `if hasattr(store, \"purge_expired\"): retention[name] = store.purge_expired()` "
        "inside the maintenance heartbeat, over every store that offers the method. Its own "
        "docstring says *'Retention: events older than 7 days, in bounded batches (maintenance "
        "heartbeat)'* — and that claim is TRUE, which is why this is not an `UNREACHED` entry.",
        "⛔ I NEARLY RECORDED THE OPPOSITE. The scan said zero callers and the docstring said "
        "'maintenance heartbeat', which reads exactly like a stale claim — the sixth instance of "
        "that shape in this programme would have been a false one. One grep for `.purge_expired(` "
        "found the real call. **A function reached by duck-typed dispatch looks identical to one "
        "nobody calls, and only the call site can tell them apart.**"),
}


def _sources() -> dict[str, str]:
    return engine_sources(_ENGINE)


def platform_functions() -> dict[str, str]:
    """`{"module.function": module}` for every declarable public function in `platform/`."""
    return package_functions(_PKG)


def platform_undeclared() -> tuple[str, ...]:
    """Unreached public functions in `platform/` that this module does not declare."""
    return undeclared(_PKG, _sources(),
                      frozenset(UNREACHED) | frozenset(REACHED_BY_DISPATCH))


def platform_missing() -> tuple[str, ...]:
    """⛔ Declared entries naming a function that does not exist — the second direction."""
    return missing(_PKG, frozenset(UNREACHED))


def platform_now_called() -> tuple[str, ...]:
    """⛔ Declared entries the engine HAS started calling — the entry that has become a lie."""
    return now_called(_sources(), frozenset(UNREACHED))


__all__ = ["REACHED_BY_DISPATCH", "UNREACHED", "platform_functions", "platform_missing", "platform_now_called", "platform_undeclared"]
