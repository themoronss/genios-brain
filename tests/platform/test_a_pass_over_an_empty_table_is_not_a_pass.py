"""⛔⛔ STEP 3.2 · a correctness receipt over an empty table passes having proved nothing.

```
receipts                      48    32 correctness · 16 presence
⛔ correctness needing a witness  32
   presence needing one            0   they FAIL on an empty table already
witness DERIVED from the outer FROM  31
⛔ declared exceptions               3   a derived-table outer · a VIEW · a schema-level claim
```

A **correctness** receipt (`expect(0) is True`) asks *"did the wrong thing happen"* and answers 0
when it did not. ⛔ Over an empty table it also answers 0 — and `PASS` is reported. That is
condition **`P2`** of this programme's definition of production level (*the receipt can fail*), and
before this it was unmet **and invisible**.

✅ The `/readiness` endpoint's own docstring says what it exists to prevent: *"an empty sweep looked
healthy, **a skip read as a pass**, and 'Present / Wired / Tested' was communicated as active
intelligence."* ⛔⛔ **An unexercised correctness receipt counted as ready IS that skip** — so
`NOT_EXERCISED` withholds readiness rather than merely being reported.

⛔ AND THE SURFACES COULD NOT REPRESENT A THIRD ANSWER. `/readiness` computed `status != "PASS"` and
the release-gate CLI held a literal `{"PASS": …, "FAIL": …, "ERROR": …}[status]` — **which raises
`KeyError` on a status it has not met.** Adding one would have *crashed the release gate*, not
disagreed with it. `RECEIPT_STATUSES` is now the one answer and all three read it.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from genios_engine.platform import receipts as R
from genios_engine.platform import table_coverage as TC

ENGINE = Path(R.__file__).resolve().parent.parent
REPO = ENGINE.parent


# ------------------------------------------------------------------ U01 · the witness derivation

def test_every_correctness_receipt_has_a_witness_or_a_declared_reason():
    """⛔⛔ Both directions. A correctness receipt with neither is one that can pass over an empty
    table with nothing saying so."""
    naked = [r.claim for r in R.receipts("org_probe")
             if r.expect(0) is True
             and R.witness_sql(r, "org_probe") is None
             and r.claim not in R.WITNESS_EXCEPTIONS]
    assert not naked, (
        f"correctness receipts with no witness and no declared exception: {naked}. Either its "
        "outer `from` names a table -- in which case the witness derives itself -- or say in "
        "`WITNESS_EXCEPTIONS` why it needs none")


def test_no_presence_receipt_carries_a_witness():
    """The converse, and it is the half that keeps the table honest. A presence receipt asks *did
    anything happen* and FAILS on an empty table, so a witness would be noise that always passed."""
    witnessed = [r.claim for r in R.receipts("org_probe")
                 if r.expect(0) is not True and R.witness_sql(r, "org_probe") is not None]
    assert not witnessed, witnessed


def test_the_witness_counts_the_receipts_OWN_outer_table():
    """⛔ The outer `from`, not a table named in a join or a subquery -- those are not the subject
    of the claim, and witnessing one would witness the wrong thing."""
    outer = re.compile(r"^\s*select\s+.*?\bfrom\s+([a-z_][a-z_0-9]*)", re.I | re.S)
    checked = 0
    for receipt in R.receipts("org_probe"):
        probe = R.witness_sql(receipt, "org_probe")
        if probe is None or receipt.claim in R.WITNESS_EXCEPTIONS:
            continue
        match = outer.match(" ".join(receipt.sql.split()))
        assert match, receipt.claim
        assert f"from {match.group(1)} " in probe, (receipt.claim, probe)
        checked += 1
    assert checked >= 25, f"only {checked} witnesses were derived; the derivation may have moved"


def test_the_witness_inherits_the_RECEIPTS_scoping_and_not_the_callers():
    """⛔ A first version appended the org filter unconditionally. Right for all 48 receipts today
    and wrong as a rule: a FLEET-WIDE correctness receipt's table may carry no `org_id` column, and
    the witness would raise instead of answering. Measured before the change: 0 of 48 disagreed --
    a coincidence of the current set, not a reason."""
    for org in ("org_probe", None):
        for receipt in R.receipts(org):
            probe = R.witness_sql(receipt, org)
            if probe is None:
                continue
            assert (":org" in probe) == (":org" in receipt.sql), (receipt.claim, org)


def test_a_FLEET_WIDE_correctness_receipt_gets_an_UNSCOPED_witness():
    """⛔⛔ THE CASE THE REAL SET CANNOT TEST, AND A MUTATION SURVIVED BECAUSE OF IT.

    `witness_sql` appends the org filter only when the receipt itself carries `:org`. Removing that
    condition is a **no-op on all 48 receipts today** — measured: 0 of 48 disagree — so a mutation
    deleting it survived every test written against the real set.

    ⛔ It is not a no-op as a rule. A fleet-wide correctness receipt asks about the SCHEMA; its
    table may carry no `org_id` column at all, and a witness that appended `and org_id = :org`
    would RAISE rather than answer. That turns a green receipt into an ERROR for a reason that has
    nothing to do with its claim.

    So the case is constructed, because the current set cannot provide it.
    """
    fleet = R.Receipt("L9", "a schema-wide claim with no tenant in it",
                      "select count(*) from cards where lane is null",
                      lambda n: n == 0, "probe", fleet_wide=True)
    probe = R.witness_sql(fleet, "org_probe")
    assert probe == "select count(*) from cards where 1=1", (
        f"a fleet-wide receipt's witness came back as {probe!r}. It carries no `:org`, so neither "
        "may its witness -- its table may have no `org_id` column")

    scoped = R.Receipt("L9", "a tenant claim", "select count(*) from cards where org_id = :org",
                       lambda n: n == 0, "probe")
    assert R.witness_sql(scoped, "org_probe") == \
        "select count(*) from cards where 1=1 and org_id = :org"


def test_the_witness_refuses_a_name_that_is_not_a_table():
    """⛔⛔ An outer `from` can name a function, a CTE or a VIEW. A witness over a non-existent
    relation does not report 'unexercised' -- it RAISES. ⛔ The first version of `witness_sql` did
    not check, and this refusal is what makes `WITNESS_EXCEPTIONS` necessary rather than
    incidental."""
    fake = R.Receipt("L9", "a claim about a relation that is not a table",
                     "select count(*) from jsonb_each('{}'::jsonb) where 1=1",
                     lambda n: n == 0, "probe")
    assert R.witness_sql(fake, None) is None

    real = R.Receipt("L9", "a claim about a real table",
                     "select count(*) from cards where 1=1", lambda n: n == 0, "probe")
    assert R.witness_sql(real, None) == "select count(*) from cards where 1=1"


def test_a_witness_IS_a_presence_receipt_and_three_of_them_exist_explicitly():
    """⛔⛔ THE UNIFICATION, GUARDED AS A MEASUREMENT RATHER THAN AS PROSE.

    The derived witness for a correctness receipt over table T is
    `select count(*) from T where 1=1 …` — ✅ and for three tables that is **byte-identical** to
    the SQL of a presence receipt that already exists. So *"was this claim exercised"* and *"has
    this layer ever run"* are the same question, and 28 more of them are now derived instead of
    waiting to be written.

    ⛔ Guarding the NOTE would have been guarding prose; a mutation deleting it survived every
    other test. This guards the FACT, so if the fact changes the note has to change with it.
    """
    witnesses = {" ".join(w.split())
                 for w in (R.witness_sql(r, "org_probe") for r in R.receipts("org_probe")) if w}
    collisions = [r for r in R.receipts("org_probe")
                  if " ".join(r.sql.split()) in witnesses]
    assert len(collisions) == 3, [c.claim for c in collisions]
    for receipt in collisions:
        assert receipt.expect(0) is False, (
            f"{receipt.claim!r} collides with a witness and is NOT a presence receipt. The "
            "unification claims the two questions are the same -- a correctness receipt here "
            "would mean something else entirely")
    note = R.WITNESS_EXCEPTIONS.__doc__ or ""
    source = (ENGINE / "platform" / "receipts.py").read_text(encoding="utf-8")
    assert "A WITNESS IS A PRESENCE RECEIPT" in source + note, (
        "the measurement above holds and nothing in the module says so; the next reader meets "
        "three identical queries and no explanation")


def test_every_declared_exception_is_still_a_receipt_and_says_why():
    """Forward: a declared exception for a claim nobody makes any more is a lie."""
    claims = {r.claim for r in R.receipts(None)}
    orphans = sorted(set(R.WITNESS_EXCEPTIONS) - claims)
    assert not orphans, f"witness exceptions for claims that no longer exist: {orphans}"
    for claim, (sql, why) in R.WITNESS_EXCEPTIONS.items():
        assert why.count("`") >= 2, f"{claim}: the reason quotes no code"
        if sql is None:
            assert "NEEDS NO WITNESS" in why or "needs no witness" in why.lower(), claim


def test_the_view_exception_says_it_is_a_view_and_the_schema_agrees():
    """⛔ `counterfactual_ledger` is `create or replace view`, which is why
    `table_coverage._known_tables()` cannot see it -- and the exception has to say so, because the
    next reader will otherwise look for a missing table."""
    _sql, why = R.WITNESS_EXCEPTIONS["the counterfactual ledger joins end to end"]
    assert "VIEW" in why
    migrations = "\n".join(p.read_text(encoding="utf-8")
                           for p in sorted((REPO / "migrations").glob("*.sql")))
    assert "create or replace view counterfactual_ledger" in migrations
    assert "counterfactual_ledger" not in TC._known_tables()


def test_the_derived_table_exception_credits_the_declaration_that_already_existed():
    """✅ `receipt_coverage` already recorded *'the real source is reasoning_reasoner_results'*, so
    this witness is that declaration's sibling rather than a new judgement."""
    claim = "every reasoning unit that says nothing is one we declared"
    sql, why = R.WITNESS_EXCEPTIONS[claim]
    assert sql and "reasoning_reasoner_results" in sql
    from genios_engine.platform import receipt_coverage as C

    _package, existing = C.RECEIPT_PACKAGE[claim]
    assert "reasoning_reasoner_results" in existing, (
        "the declaration this exception credits no longer names that source -- check which is "
        "right before trusting either")
    assert "receipt_coverage" in why


# ------------------------------------------------------ U04 · the schema objects nobody can see

def test_every_view_in_the_schema_is_declared_invisible():
    """⛔⛔ Backward. `_known_tables()` reads `create table`, so a view is invisible to every
    measurement built on it -- and a table nobody can see is a table nobody can audit."""
    migrations = "\n".join(f.read_text(encoding="utf-8")
                            for f in sorted((REPO / "migrations").glob("*.sql")))
    views = set(re.findall(r"create (?:or replace )?view ([a-z_][a-z_0-9]*)", migrations))
    assert views, "no views found at all -- the measurement moved"
    undeclared = sorted(views - set(TC.SCHEMA_OBJECTS_NOT_SEEN))
    assert not undeclared, (
        f"views the coverage module cannot see and nobody declared: {undeclared}. Declare them, "
        "or teach `_known_tables()` a second grammar and say why that was worth it")


def test_every_declared_invisible_object_is_still_there_and_still_invisible():
    """Forward, both halves: a declaration for an object the schema dropped is a lie, and so is
    one for an object the module can now see."""
    migrations = "\n".join(f.read_text(encoding="utf-8")
                            for f in sorted((REPO / "migrations").glob("*.sql")))
    for name, (kind, why) in TC.SCHEMA_OBJECTS_NOT_SEEN.items():
        assert f"{kind} {name}" in migrations, f"{name}: no `create {kind}` in the migrations"
        assert name not in TC._known_tables(), (
            f"{name} is visible to `_known_tables()` now -- drop the entry")
        assert why.count("`") >= 2, f"{name}: the reason quotes no code"


def test_the_one_member_is_declared_as_LIVE_rather_than_as_a_leftover():
    """⛔ A blind spot over something nothing uses is a curiosity. This one is over an object a
    production route and a receipt both query, which is what makes it worth declaring."""
    _kind, why = TC.SCHEMA_OBJECTS_NOT_SEEN["counterfactual_ledger"]
    assert "intelligence_routes" in why and "receipt" in why.lower()
    route = (ENGINE / "api" / "intelligence_routes.py").read_text(encoding="utf-8")
    assert "counterfactual_ledger" in route, (
        "the route this entry credits no longer queries the view -- re-read whether the blind "
        "spot still matters")


def test_the_witness_exceptions_citation_of_that_table_RESOLVES():
    """⛔ `WITNESS_EXCEPTIONS` points at `SCHEMA_OBJECTS_NOT_SEEN` by name -- and when that
    sentence was written the constant did not exist yet. *A citation that does not resolve reads
    as a measurement and is not one*, and this one did not resolve for several minutes."""
    _sql, why = R.WITNESS_EXCEPTIONS["the counterfactual ledger joins end to end"]
    assert "SCHEMA_OBJECTS_NOT_SEEN" in why
    assert hasattr(TC, "SCHEMA_OBJECTS_NOT_SEEN")


# -------------------------------------------------------------- U02 · evaluate's fourth status

def _witness_set(org: str | None) -> set[str]:
    """Exactly the witness queries `evaluate()` will run, derived from the module itself.

    ⛔⛔ THE FAKES USED TO CLASSIFY A WITNESS BY SUFFIX — `sql.endswith("where 1=1 and org_id =
    :org")` — and **many RECEIPTS end exactly that way**, because `_org_filter` appends it. So a
    receipt's own query was treated as a witness, the broken-witness fake raised on it, and
    `test_a_witness_that_raises_…` passed **for the wrong reason**: it saw an ERROR, just not the
    one it was asserting about.

    ⛔ Found by a surviving mutation, and the hole was in the TEST DOUBLE rather than in the code.
    *A test double that misclassifies its inputs passes for the wrong reason* — and a suffix
    heuristic is the same family as a hand-listed token set.
    """
    return {" ".join(w.split()) for w in
            (R.witness_sql(receipt, org) for receipt in R.receipts(org)) if w}


class _Conn:
    """A connection whose tables are empty unless named in `populated`."""

    def __init__(self, populated: set[str], org: str | None = "org_probe") -> None:
        self.populated = populated
        self.witnesses = _witness_set(org)
        self.asked: list[str] = []

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.asked.append(sql)
        witness = sql in self.witnesses
        rows = any(f"from {t} " in sql + " " for t in self.populated)

        class _R:
            @staticmethod
            def scalar():
                return 1 if (witness and rows) else 0
        return _R()

    def rollback(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Engine:
    def __init__(self, conn) -> None:
        self._conn = conn

    def connect(self):
        return self._conn


def test_a_correctness_receipt_over_an_EMPTY_table_reports_NOT_EXERCISED():
    """⛔⛔ THE WHOLE POINT. Every receipt returns 0 and every witness returns 0, so every
    correctness claim 'holds' and none was exercised."""
    rows = R.evaluate(_Engine(_Conn(populated=set())), "org_probe")
    statuses = {r["status"] for r in rows}
    assert "NOT_EXERCISED" in statuses, statuses
    unexercised = [r for r in rows if r["status"] == "NOT_EXERCISED"]
    assert len(unexercised) >= 25, len(unexercised)
    for row in unexercised:
        assert "nothing exercised it" in row["detail"], row["detail"][:80]


def test_the_same_receipt_over_a_POPULATED_table_reports_PASS():
    """⛔ The converse. Without it, a bug that reported NOT_EXERCISED for everything would pass the
    test above -- *a grade needs its converse guarded*."""
    tables = {"sync_cursors", "parked_events", "qualified_signals", "cards"}
    rows = R.evaluate(_Engine(_Conn(populated=tables)), "org_probe")
    passing = [r for r in rows if r["status"] == "PASS"]
    assert passing, [r["status"] for r in rows][:6]
    claims = {r["claim"] for r in passing}
    assert any("sync cursor" in c for c in claims), sorted(claims)[:4]


def test_a_FAIL_is_never_downgraded_to_NOT_EXERCISED():
    """⛔ A failing receipt found a bad row, so the table demonstrably has rows. Asking the witness
    would be noise -- and reporting NOT_EXERCISED would hide a real failure.

    ⛔⛔ ASSERTED AS A PROPERTY, NOT AS A GLOBAL ABSENCE, and the first version was wrong for an
    interesting reason. It fed every query 7 and asserted `NOT_EXERCISED` appeared nowhere --
    ⛔ and it appeared once, correctly: *"the tenant is still being fed"* has a RANGE predicate,
    not a zero-test, so 7 satisfies it, and its witness then said the table was empty.

    ⛔ That also shows what `expect(0) is True` really is: a TWO-POINT PROBE of a predicate, not a
    classification. For a range receipt it answers "correctness" and the witness is right to run.
    So the claim here is the narrow one: **a row whose own predicate said False is a FAIL.**
    """

    class _Failing(_Conn):
        def execute(self, statement, params=None):
            sql = " ".join(str(statement).split())
            self.asked.append(sql)

            class _R:
                @staticmethod
                def scalar():
                    return 0 if sql in self.witnesses else 7   # tables empty; claims see 7
            return _R()

    rows = R.evaluate(_Engine(_Failing(populated=set())), "org_probe")
    by_claim = {r.claim: r for r in R.receipts("org_probe")}
    downgraded = [row["claim"] for row in rows
                  if row["status"] == "NOT_EXERCISED"
                  and by_claim[row["claim"]].expect(row["value"]) is False]
    assert not downgraded, (
        f"receipts whose own predicate said False were reported NOT_EXERCISED: {downgraded}. A "
        "failure hidden behind 'nothing exercised it' is worse than no receipt")
    assert any(r["status"] == "FAIL" for r in rows), [r["status"] for r in rows][:6]


def test_a_witness_that_raises_makes_the_receipt_an_ERROR_and_not_a_pass():
    """⛔⛔ An unverifiable pass is not a pass. The instrument failing is a finding ABOUT the
    instrument, and hiding it behind the receipt's own green is how a measurement stops being
    one -- the same reasoning as *an unrunnable receipt is a finding, never a skip*."""

    class _BrokenWitness(_Conn):
        def execute(self, statement, params=None):
            sql = " ".join(str(statement).split())
            self.asked.append(sql)
            if sql in self.witnesses:
                raise RuntimeError("UndefinedTable: relation does not exist")

            class _R:
                @staticmethod
                def scalar():
                    return 0
            return _R()

    rows = R.evaluate(_Engine(_BrokenWitness(populated=set())), "org_probe")
    errors = [r for r in rows if r["status"] == "ERROR"]
    assert errors, [r["status"] for r in rows][:6]
    # ⛔ EVERY error must be the WITNESS's, not some other failure. The first version asserted
    # `any(...)`, which a differently-broken fake satisfied while the claim went unchecked.
    assert all("UndefinedTable" in r["detail"] for r in errors), (
        [r["detail"][:60] for r in errors if "UndefinedTable" not in r["detail"]])
    assert "PASS" not in {r["status"] for r in rows if r["claim"] in
                          {x.claim for x in R.receipts("org_probe")
                           if R.witness_sql(x, "org_probe")}}, (
        "a receipt whose witness raised was still reported PASS -- an unverifiable pass is not a "
        "pass")


def test_the_witness_is_asked_only_on_a_pass(monkeypatch):
    """⛔⛔ TWO RECEIPTS, NOT FORTY-EIGHT, AND THREE WRONG VERSIONS GOT ME HERE.

    Attempt 1 asserted that FEWER witnesses ran than exist — wrong, because with every claim
    answering 0 every correctness receipt passes and every witness legitimately runs.

    Attempt 2 matched witness SQL by MEMBERSHIP — wrong, because two receipts over the same outer
    table share one witness string, so "this SQL was asked" says nothing about which receipt asked.

    Attempt 3 counted the calls — and still wrong, for the reason that turned out to be the most
    interesting thing in the unit: ⛔⛔ **three receipts' OWN SQL is identical to another receipt's
    derived witness.** `"compiled expertise packages exist"`, `"the delivery control plane has
    run"` and `"the learning engine has executed"` are each exactly
    `select count(*) from <table> where 1=1 …` — ✅ which is the witness, because **a witness IS a
    presence receipt**. Three of them already exist explicitly and the other 28 are derived.

    So the claim is asserted over a fixture of two, where attribution is unambiguous.
    """
    # ⛔ NEITHER receipt's SQL may equal `select count(*) from <table> where 1=1`, which is what
    # the witness derives to. Two drafts of this fixture collided — first the failing one, then the
    # passing one — and each time the witness call and the receipt call were indistinguishable.
    passing = R.Receipt("L9", "a claim that holds",
                        "select count(*) from cards where lane is null",
                        lambda n: n == 0, "probe")
    # ⛔ `where state = 'bad'`, NOT `where 1=1` — because a receipt whose SQL IS its own witness is
    # exactly the collision documented in `WITNESS_EXCEPTIONS`, and a first draft of this fixture
    # walked straight into it: the "failing" receipt passed, its witness ran, and both rows came
    # back NOT_EXERCISED. ✅ Confirmation that the collision is structural rather than incidental.
    failing = R.Receipt("L9", "a claim that does not",
                        "select count(*) from signals where state = 'bad'",
                        lambda n: n == 0, "probe")
    monkeypatch.setattr(R, "receipts", lambda org: [passing, failing])

    class _Two:
        def __init__(self) -> None:
            self.asked: list[str] = []

        def execute(self, statement, params=None):
            sql = " ".join(str(statement).split())
            self.asked.append(sql)
            bad = sql == "select count(*) from signals where state = 'bad'"

            class _R:
                @staticmethod
                def scalar():
                    if sql == "select count(*) from cards where 1=1":
                        return 0            # cards' witness: the table is empty
                    if sql == "select count(*) from signals where 1=1":
                        return 0            # signals' witness, which must never be asked
                    return 3 if bad else 0          # the failing claim finds three bad rows
            return _R()

        def rollback(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    conn = _Two()
    rows = R.evaluate(_Engine(conn), None)
    # ⛔ NO `or True` ANYWHERE. A first draft of this block carried two assertions that could not
    # fail, which is the defect this whole step is about wearing a test's clothes.
    assert [r["status"] for r in rows] == ["NOT_EXERCISED", "FAIL"], [r["status"] for r in rows]
    assert conn.asked.count("select count(*) from cards where 1=1") == 1, (
        "the PASSING receipt's witness was not asked exactly once")
    assert conn.asked.count("select count(*) from signals where 1=1") == 0, (
        "a FAILING receipt's witness was asked. It already found a bad row, so the table "
        "demonstrably has rows -- the question is noise and the `if ok:` guard is gone")


# ------------------------------------------- U03 · one answer about ready, three consumers

def test_the_status_table_covers_every_status_evaluate_can_return():
    rows = R.evaluate(_Engine(_Conn(populated=set())), "org_probe")
    unknown = sorted({r["status"] for r in rows} - set(R.RECEIPT_STATUSES))
    assert not unknown, f"statuses evaluate() returns that the table does not name: {unknown}"


def test_only_PASS_counts_as_ready():
    """⛔⛔ `NOT_EXERCISED` is NOT ready, and that is the step. `/readiness` exists because *"an
    empty sweep looked healthy, a skip read as a pass"* -- so counting an unexercised correctness
    receipt towards ready would be that same skip."""
    ready = {k for k, (ok, _why) in R.RECEIPT_STATUSES.items() if ok}
    assert ready == {"PASS"}, sorted(ready)
    assert R.RECEIPT_STATUSES["NOT_EXERCISED"][0] is False


def test_both_surfaces_read_the_table_rather_than_their_own_literal():
    """⛔⛔ THEY HAD ALREADY DRIFTED IN SHAPE: `/readiness` computed `status != "PASS"` and the CLI
    held `{"PASS": …, "FAIL": …, "ERROR": …}[status]` -- which RAISES `KeyError` on a status it has
    not met. Adding one would have crashed the release gate, not disagreed with it."""
    # ⛔⛔ CODE LINES ONLY, AND THAT IS THE FIFTH VARIANT OF THE SELF-WITNESS FAMILY. The first
    # version of this test searched the whole file -- and both modules' comments QUOTE the old
    # code they replaced, to explain what changed. ⛔ So the check against the old pattern found my
    # own explanation of why it is gone.
    #
    # The family so far: a declaration that falsifies its own count (`2.1`); one that satisfies
    # the test its source exists (`2.2`); a correction whose names nothing checked (`2.2`); a
    # quoted example counted as a real one (`3.1`); and now a comment quoting the code it replaced.
    # ⛔ The fix is never to delete the quote -- it is what makes the change readable.
    def code_only(path: Path) -> str:
        return "\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                          if not line.lstrip().startswith("#"))

    routes = code_only(ENGINE / "api" / "routes.py")
    cli = code_only(REPO / "scripts" / "runtime_receipts.py")
    assert "RECEIPT_STATUSES" in routes
    assert "RECEIPT_STATUSES" in cli
    assert 'r["status"] != "PASS"' not in routes, (
        "the endpoint computes readiness itself again; that is a second answer to a question the "
        "table owns")
    assert '{"PASS": "PASS", "FAIL": "FAIL", "ERROR": "ERR "}[' not in cli, (
        "the CLI's literal status dict is back, and it raises KeyError on a new status")


def test_the_cli_has_a_mark_for_every_status():
    spec = importlib.util.spec_from_file_location("rr", REPO / "scripts" / "runtime_receipts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module._MARKS) == set(R.RECEIPT_STATUSES), (
        f"marks {sorted(module._MARKS)} against statuses {sorted(R.RECEIPT_STATUSES)}")
    assert all(len(m) == 4 for m in module._MARKS.values()), module._MARKS


def test_the_endpoint_reports_the_third_bucket_separately():
    routes = (ENGINE / "api" / "routes.py").read_text(encoding="utf-8")
    for key in ('"not_exercised"', '"failing"', '"passing"', '"ready"'):
        assert key in routes, key


def test_the_behaviour_change_is_recorded_where_it_happens():
    """⛔ A tenant with sparse data now reports `ready: false` where it reported `true`. Not a new
    product decision -- the docstring states the principle -- but it has to be said out loud."""
    routes = (ENGINE / "api" / "routes.py").read_text(encoding="utf-8")
    assert "VISIBLE BEHAVIOUR CHANGE" in routes
    assert "19-PENDING" in routes, (
        "the change is not pointed at the page that carries it for Rohit")
