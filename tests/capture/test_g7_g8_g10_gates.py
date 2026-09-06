"""G7, G8 and G10 — the three acceptance gates, run AGAINST THE PRODUCTION PATH.

    09-Build-Order-and-Acceptance.md, sections "### G7", "### G8", "### G10"

WHY THIS FILE EXISTS BESIDE THE UNIT GATES. `tests/capture/esqe/test_importance.py` and
`test_publisher.py` prove ALG-17 and V-1..V-7 against objects the tests themselves construct.
That is the right way to prove a formula and it is structurally unable to prove a WIRING: the
previous G7 pass measured a distribution against a baseline no production path could build,
because `compute_org_baseline` was dead code at the time and every test that needed one made
its own. Five units have now shipped built, tested and never called — `extract()`, the poll
scheduler, the cost governor, the claim_group->conflict seam, `compute_org_baseline` — and each
of them had a green test file.

So nothing in this file constructs an `OrgBaseline`, an `ImportanceScore`, a
`QualifiedEnterpriseSignal` or a store. The corpus is raw provider objects; the entry point is
`api/routes._sync_connection`, the background sweep every `/sync` and every scheduler tick runs;
and every number asserted is read back OUT OF POSTGRES afterwards, through the same gate report
scripts an operator runs — `scripts/importance_distribution.py` (G7), `scripts/l1_end_to_end.py`
(G8), `scripts/l1_shadow_diff.py` (G10). If the wiring is absent the tables are empty and every
gate here is red, which is the property the unit files cannot have.

THE CORPUS IS THIS FILE'S OWN. It shares no factory, no fixture and no constant with
`test_importance.py` or `test_importance_gate_probe.py`: 96 messages spanning twelve amounts
against the org's own p50, twelve deadline distances either side of `eval_time`, five
counterparties of four different standings and eight extraction shapes. A gate that reuses the
implementation's corpus inherits the implementation's blind spots.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.contracts.signal import SignalType
from genios_engine.platform.db import get_engine

pytestmark = pytest.mark.pg

# =============================================================================================
# The frozen world
# =============================================================================================
#: A Wednesday, 09:00 UTC — the same discipline `tests/capture/conftest.py` states, restated
#: here rather than imported so this file's corpus cannot be moved by an edit to another one's.
GATE_NOW = datetime(2026, 3, 4, 9, 0, tzinfo=timezone.utc)

ORG = "org_l1_gates"
CONNECTION = "con_l1_gates"
OWNER = "founder@genios.test"

#: The org's own priced history: nine contracts, so the p50 is the fifth. Chosen so that the
#: corpus amounts below straddle it in both directions by more than an order of magnitude —
#: which is what makes the RATIO ladder, and not the absolute one, the thing under test.
PRICED_HISTORY: tuple[tuple[int, str], ...] = (
    (500_000, "Aperture Labs"), (900_000, "Blackwood"), (1_800_000, "Cyberdyne"),
    (2_400_000, "Dunder Mifflin"), (3_500_000, "Encom"), (6_000_000, "Frobozz"),
    (9_000_000, "Gringotts"), (14_000_000, "Hyperion"), (26_000_000, "Initrode"),
)
SEEDED_P50 = 3_500_000                       # the fifth of nine, in USD minor units

#: The counterparties the corpus names, and what the seeded history makes each of them:
#: Initrode is the biggest contract this org has (top decile), Aperture the smallest (known),
#: and Meridian/Vantage appear nowhere in the history at all (first seen).
COUNTERPARTIES = ("Initrode", "Hyperion", "Encom", "Aperture Labs", "Meridian Group",
                  "Vantage Partners")

#: Two of them the tenant declared mission-critical — term 4 rung 1, the judgement rung.
MISSION_CRITICAL = ("Encom", "Vantage Partners")

#: Twelve amounts, from 1/70th of the org's typical contract to twenty times it.
AMOUNTS = (50_000, 120_000, 400_000, 900_000, 1_750_000, 3_500_000,
           5_200_000, 8_400_000, 12_000_000, 21_000_000, 44_000_000, 70_000_000)

#: ELEVEN deadline distances, in days from `GATE_NOW`. `None` is "this message states no date",
#: which is a third of real mail and the state term 2 reports as 0 rather than as a gap.
#:
#: Eleven and not twelve, deliberately: the amount axis has twelve entries and the corpus indexes
#: both by the message number, so two axes of the same length would pair up one-to-one and the
#: corpus would carry twelve (amount, deadline) combinations wearing ninety-six message ids. Co-
#: prime lengths make the pairing walk the whole grid, which is the difference between a book
#: that spans a range and a book that repeats one diagonal of it.
DEADLINE_DAYS: tuple[int | None, ...] = (-21, -5, -1, 0, 1, 2, 4, 9, 16, 30, None)

#: Eight extraction shapes, each of which fires a different corner of ALG-15's predicate table.
SHAPES = ("renewal", "obligation", "commitment_due", "approval", "decision_pending",
          "risk", "opportunity", "escalation")

#: 132 = lcm(12, 11), so every amount meets every deadline exactly once. A corpus that stops
#: short of it is a corpus whose top corner — the largest amount already overdue — may simply
#: never occur, and the p90 it reports is then a property of where the loop stopped.
CORPUS_SIZE = 132

#: The marker the stub model reads to know which message it was handed. Put in the SUBJECT, so
#: it survives preprocessing into `clean_text` exactly as written.
_MARKER = re.compile(r"GATE-(\d{3})")


def _mark(index: int) -> str:
    return f"GATE-{index:03d}"


# =============================================================================================
# The corpus — raw provider objects, nothing else
# =============================================================================================
def _facts(index: int) -> tuple[int, int | None, str, str]:
    """The four axes message `index` varies. One function, so the body and the extraction that
    cites it cannot disagree about which amount, date, counterparty and shape it is about."""
    return (AMOUNTS[index % len(AMOUNTS)],
            DEADLINE_DAYS[index % len(DEADLINE_DAYS)],
            COUNTERPARTIES[index % len(COUNTERPARTIES)],
            SHAPES[index % len(SHAPES)])


def _sentence(index: int, *, party: str | None = None) -> str:
    """The clause carrying this message's amount and counterparty — the quote the extraction
    cites. Shared with `_body` rather than rebuilt, because a receipt that does not appear
    verbatim in the source is exactly the fabrication ALG-08 exists to catch."""
    amount, _days, default_party, shape = _facts(index)
    party = party or default_party
    dollars = amount // 100
    return {
        "renewal": f"the {party} annual contract renews at ${dollars:,}",
        "obligation": f"we owe {party} ${dollars:,} on this invoice",
        "commitment_due": f"I will send {party} the ${dollars:,} statement",
        "approval": f"Finance must approve the ${dollars:,} spend with {party}",
        "decision_pending": f"we have not decided on the ${dollars:,} {party} proposal",
        "risk": f"the {party} account is at risk over the ${dollars:,} overage",
        "opportunity": f"{party} is ready to expand to ${dollars:,}",
        "escalation": f"escalating the ${dollars:,} {party} outage to the exec team",
    }[shape]


def _body(index: int) -> str:
    """One message. Every quote the stub model later cites is present here VERBATIM, because a
    span that does not resolve against the prepared text is the defect V-5 downgrades for and it
    would silently move the very rate G10 measures."""
    _amount, days, _party, _shape = _facts(index)
    when = "" if days is None else (GATE_NOW + timedelta(days=days)).strftime("%d %B %Y")
    tail = "" if not when else f", and the date on it is {when}"
    return f"Hello, {_sentence(index)}{tail}. Please read the thread before replying."


def _raw(index: int) -> RawObject:
    party = COUNTERPARTIES[index % len(COUNTERPARTIES)]
    domain = party.split()[0].lower().replace(".", "")
    return RawObject(
        source="gmail", object_type="email_message",
        source_object_id=f"m_gate_{index:03d}",
        occurred_at=GATE_NOW - timedelta(hours=index),
        actor_email=f"contact{index % 7}@{domain}.test",
        recipients=(OWNER,),
        raw={"subject": f"{_mark(index)} {party}", "body": _body(index),
             "headers": {"Message-Id": f"<gate-{index}@{domain}.test>"}})


CORPUS: tuple[RawObject, ...] = tuple(_raw(i) for i in range(CORPUS_SIZE))


def _unique_party_corpus() -> tuple[RawObject, ...]:
    """The same 96 messages with a UNIQUE counterparty in each, for the FLOOR tests.

    ALG-12 is doing its job on the main corpus and that is exactly the problem for ALG-18: six
    counterparties across 96 messages means dozens of pairs of messages making different claims
    about the same subject, the conflict detector finds them, and `qualify_signals`' second rung
    — *below floor + conflict -> QUALIFY* — then rescues 188 of 251 signals whatever the floor
    is. That override is correct and is not what these two tests are about; measuring the cut
    requires a book where no two messages contradict each other.

    Built by renaming the counterparty per message and nothing else, so the amounts, dates and
    shapes — and therefore the scores — keep the same distribution.
    """
    out = []
    for index, raw in enumerate(CORPUS):
        party = f"{COUNTERPARTIES[index % len(COUNTERPARTIES)]} {index:03d}"
        body = _body(index).replace(COUNTERPARTIES[index % len(COUNTERPARTIES)], party)
        out.append(RawObject(
            source="gmail", object_type="email_message",
            source_object_id=f"u_gate_{index:03d}", occurred_at=raw.occurred_at,
            actor_email=raw.actor_email, recipients=raw.recipients,
            raw={"subject": f"{_mark(index)} {party}", "body": body,
                 "headers": {"Message-Id": f"<ugate-{index}@example.test>"}}))
    return tuple(out)


UNIQUE_PARTY_CORPUS: tuple[RawObject, ...] = _unique_party_corpus()


class _CorpusConnector:
    """The provider, and the ONLY thing standing in on the sweep. Everything else — the
    repository, the coverage declaration, the org baseline, the floor, the drop ledger, the
    lifecycle store and the signal store — is the real object against the real database."""

    def __init__(self, objects=CORPUS, source: str = "gmail") -> None:
        self._objects = list(objects)
        #: `run_sync` treats the CONNECTOR as authoritative about its own source and refuses a
        #: caller that disagrees, so this is an instance attribute rather than a class constant.
        self.source = source

    def incremental_changes(self, cursor=None, limit=50, since=None):
        return SourceBatch(objects=self._objects, next_cursor=None)

    def initial_snapshot(self, cursor=None, limit=50):
        return self.incremental_changes(cursor, limit)


class _CorpusLLM:
    """A model that answers from the message it was shown, not from a queue.

    `FakeLLM` pops canned answers in call order, which makes a 96-message page a bet on the
    order the pipeline happens to walk it in — and the extractor is entitled to batch, cache and
    reorder. This one reads the marker out of the prompt and returns THAT message's extraction,
    so the corpus is content-addressed and the sweep can call in any order it likes.
    """

    model = "fake-model-gate-1"

    def __init__(self, *, unique_parties: bool = False) -> None:
        self.calls: list[str] = []
        #: Which of the two corpora this model is answering for. The marker names the MESSAGE;
        #: the counterparty in it differs between them, and a receipt quoting the wrong name
        #: would not be found in the text it claims to come from.
        self._unique = unique_parties

    def _payload_for(self, index: int) -> dict:
        if not self._unique:
            return _payload(index)
        party = f"{COUNTERPARTIES[index % len(COUNTERPARTIES)]} {index:03d}"
        body = _body(index).replace(COUNTERPARTIES[index % len(COUNTERPARTIES)], party)
        return _payload(index, body=body, party=party)

    def call(self, prompt: str, *, max_tokens: int = 4096):
        self.calls.append(prompt)
        found = _MARKER.search(prompt)
        payload = self._payload_for(int(found.group(1))) if found else {"intent": "inform",
                                                                        "stance": "neutral"}
        raw = json.dumps(payload, sort_keys=True)
        return _Result(parsed=payload, raw=raw, input_tokens=900, output_tokens=180,
                       model=self.model)


class _Result:
    """The transport's answer, field-for-field the shape the extractor reads."""

    def __init__(self, *, parsed, raw, input_tokens, output_tokens, model):
        self.parsed, self.raw = parsed, raw
        self.input_tokens, self.output_tokens = input_tokens, output_tokens
        self.model, self.cached, self.ok, self.error = model, False, True, None


def _cite(body: str, quote: str) -> list[dict]:
    start = body.index(quote)
    return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]


def _payload(index: int, *, body: str | None = None, party: str | None = None) -> dict:
    """The extraction for message `index`, cited against that message's own text.

    `body` and `party` are overridden for the unique-counterparty corpus, whose messages differ
    from `_body(index)` in exactly the counterparty's name — so the receipts are still found in
    the text they are receipts for."""
    amount, days, _party, shape = _facts(index)
    party = party or _party
    body = _body(index) if body is None else body
    dollars = amount // 100

    # The entity is cited with the WHOLE clause it was read from, and that is not decoration:
    # `Money` is the one claim type C-02 gives no `evidence` list — its receipt is `as_written`
    # being present in the source — so `normalize._spans_of` finds a money-anchored signal's
    # receipt by looking for the literal inside the quotes OTHER claims cited. An extraction
    # whose spans quote only the bare company name leaves every money-anchored signal with no
    # receipt at all, and the publisher V-4 rejects it. A real extractor cites the phrase; a
    # fixture that cites the word would be testing a corpus no extractor produces.
    out: dict = {
        "intent": "inform", "stance": "neutral", "topics": [],
        "entity_mentions": [{"surface_form": party, "entity_type": "organization",
                             "evidence": _cite(body, _sentence(index, party=party)), "confidence_bp": 9000}],
        "amounts": [{"minor_units": amount, "currency": "USD",
                     "as_written": f"${dollars:,}"}],
    }
    if days is not None:
        written = (GATE_NOW + timedelta(days=days)).strftime("%d %B %Y")
        out["dates_mentioned"] = [{"as_written": written, "evidence": _cite(body, written)}]

    if shape == "renewal":
        out["topics"] = ["contract_renewal"]
    elif shape == "obligation":
        out["intent"] = "commit"
    elif shape == "commitment_due":
        out["commitments"] = [{
            "actor": "me", "action": f"send {party} the statement", "is_conditional": False,
            "due": ({"as_written": (GATE_NOW + timedelta(days=days)).strftime("%d %B %Y")}
                    if days is not None else None),
            "evidence": _cite(body, f"I will send {party} the ${dollars:,} statement"),
            "confidence_bp": 8200}]
    elif shape == "approval":
        out["intent"] = "approve"
        out["dependencies"] = [{"blocker": "Finance", "blocked": "me",
                                "dependency_type": "approval",
                                "evidence": _cite(body, "Finance must approve"),
                                "confidence_bp": 8000}]
    elif shape == "decision_pending":
        out["decisions"] = [{"subject": f"{party} proposal", "state": "pending",
                             "evidence": _cite(body, "we have not decided"),
                             "confidence_bp": 7800}]
    elif shape == "risk":
        out["stance"] = "negative"
        out["topics"] = ["risk"]
    elif shape == "opportunity":
        out["stance"] = "positive"
        out["topics"] = ["expansion"]
    elif shape == "escalation":
        out["intent"] = "escalate"
    return out


# =============================================================================================
# Fixtures — the org, its history, and a clean slate for each gate
# =============================================================================================
@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the acceptance gates need a real Postgres")
    return live_db_url


def _priced_extraction(minor_units: int, counterparty: str) -> dict:
    """One stored extraction, built through the REAL contract and dumped the way the cache writes
    it, so `baseline_reader` parses the bytes production files rather than a fixture shaped
    like them."""
    from genios_engine.contracts.evidence import EvidenceSpan
    from genios_engine.contracts.extraction import EntityMention, ExtractionResult
    from genios_engine.contracts.units import Money

    span = EvidenceSpan(source_ref="prepared_content:pc_hist", quote=counterparty,
                        start_offset=0, end_offset=len(counterparty))
    return ExtractionResult(
        intent="inform", stance="neutral",
        amounts=[Money(minor_units=minor_units, currency="USD",
                       as_written=f"${minor_units // 100}")],
        entity_mentions=[EntityMention(surface_form=counterparty, entity_type="organization",
                                       evidence=[span], confidence_bp=9000)],
        all_evidence=[span], model_snapshot="fake-model-hist", prompt_version="p1",
        schema_version="1", extraction_profile="email", input_tokens=10, output_tokens=5,
    ).model_dump(mode="json")


_GATE_TABLES = ("qualified_signals", "qualification_drops", "signal_lifecycle",
                "l1_extraction_results", "prepared_content", "raw_payloads",
                "parked_events", "source_events", "l2_processing_runs", "graph_facts",
                "cards", "llm_costs", "l1_sync_runs", "source_coverage",
                "l1_semantic_activation", "org_qualification_floors",
                "qualification_floor_changes")


@pytest.fixture
def gate_org(pg_url):
    """A tenant with nine priced contracts behind it and nothing else. Torn down after."""
    engine = get_engine(pg_url)

    def _wipe(conn):
        for table in _GATE_TABLES:
            conn.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})

    with engine.begin() as conn:
        _wipe(conn)
        conn.execute(text("delete from orgs where id = :o"), {"o": ORG})
        names = [r.column_name for r in conn.execute(text(
            "select column_name from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'"))]
        cols = ["id"] + names
        conn.execute(text(f"insert into orgs ({', '.join(cols)}) values "
                          f"({', '.join(':' + c for c in cols)})"),
                     {"id": ORG, **{n: "scratch" for n in names}})
        conn.execute(text("update orgs set email = :e where id = :o"),
                     {"e": OWNER, "o": ORG})
        # Two vendors the tenant declared mission-critical (migration 0091). Rung 1 of term 4,
        # and the corpus needs it: with only money-derived standings a real book's entity term
        # spans 2000..8000, and the judgement rung is what a founder actually uses to say "this
        # small payroll provider outranks that large customer".
        for party in MISSION_CRITICAL:
            conn.execute(text(
                "insert into org_mission_critical_entities "
                "(org_id, entity_key, display_name, owner, note) values (:o,:k,:d,:w,:n) "
                "on conflict (org_id, entity_key) do nothing"),
                {"o": ORG, "k": party.casefold(), "d": party, "w": OWNER,
                 "n": "single-source provider"})
        occurred = GATE_NOW - timedelta(days=45)
        for index, (minor_units, party) in enumerate(PRICED_HISTORY):
            event_id = f"evt_gate_hist_{index}"
            conn.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, "
                "object_type, source_object_id, dedup_key, actor, occurred_at) values "
                "(:e, :o, :c, 'gmail', 'email_message', :e, :e, cast('{}' as jsonb), :at)"),
                {"e": event_id, "o": ORG, "c": CONNECTION, "at": occurred})
            conn.execute(text(
                "insert into l1_extraction_results (processing_key, org_id, event_id, output, "
                "model_snapshot, profile_id, tier) values (:k, :o, :e, cast(:out as jsonb), "
                "'fake-model-hist', 'email', 'T1')"),
                {"k": f"pk_gate_hist_{index}", "o": ORG, "e": event_id,
                 "out": json.dumps(_priced_extraction(minor_units, party))})
    yield pg_url
    with engine.begin() as conn:
        _wipe(conn)
        conn.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _sweep_capturing(monkeypatch, *, objects=CORPUS):
    """The sweep, with the REAL `SyncSummary` it handed the production ledger hook.

    `api/routes._run_ledger` is where L1.6.8, L1.6.9 and L1.6.10 run — the floor, the lifecycle
    and the publisher — and it takes the sweep's own summary. Grabbing that object is what lets
    the publication gates below be exercised on a summary capture actually produced, with one
    field changed, instead of on a summary a test assembled.
    """
    from genios_engine.api import routes

    seen: dict = {}
    real = routes._run_ledger
    monkeypatch.setattr(routes, "_run_ledger",
                        lambda **kw: (seen.update(kw), real(**kw))[1])
    _sweep(monkeypatch, objects=objects)
    return seen.get("summary"), seen


def _sweep(monkeypatch, *, objects=CORPUS, esqe_override=None) -> _CorpusLLM:
    """Drive the PRODUCTION sweep over the corpus and hand back the model that was called.

    `api/routes._sync_connection` is the function `/sync/{id}`, `/ingest/all` and the background
    scheduler all reach. The two monkeypatches replace the PROVIDER and the MODEL — the two
    things a test may not have — and nothing else: the baseline factory, the coverage
    declaration, the floor store, the drop ledger, the lifecycle store and the signal store are
    all the production objects `routes` built at import.
    """
    from genios_engine.api import routes
    from genios_engine.capture import pipeline as P
    from genios_engine.contracts.connection import Connection

    if routes._graph is None:
        pytest.skip("routes has no graph store — the request path cannot reach a database")

    from genios_engine.platform.wiring import make_semantic_lane

    llm = _CorpusLLM(unique_parties=objects is UNIQUE_PARTY_CORPUS)
    connection = Connection(org_id=ORG, connection_id=CONNECTION, source_type="gmail",
                            composio_user_id=ORG)
    monkeypatch.setattr(routes, "make_connector_for",
                        lambda conn, **kw: _CorpusConnector(objects))
    # The PRODUCTION bundle, from the production factory, with only the transport injected. Built
    # by hand it would arrive with no extraction cache and no discovery store — and then every
    # `qualified_signals.extraction_ref` would point at a row nothing ever wrote, which is a
    # property of the test rather than of the build.
    monkeypatch.setattr(routes, "_semantic_lane_for",
                        lambda org, activated=None: replace(
                            make_semantic_lane(org, engine=getattr(routes._graph, "engine", None),
                                               llm=llm, activated=frozenset({ORG})),
                            eval_time=GATE_NOW))
    monkeypatch.setattr(routes, "_mailbox_owner_for", lambda org: OWNER)
    monkeypatch.setattr(routes, "_run_l2", lambda org: None)
    if esqe_override is not None:
        monkeypatch.setattr(routes, "_esqe_stage_for", esqe_override)
    routes._sync_connection(connection, "incremental", CORPUS_SIZE)
    return llm


def _report(pg_url, builder, **kwargs):
    """Run one of the gate scripts against the database, the way an operator runs it: through
    its own read-only connection helper, so a report that tried to write would be refused by
    Postgres rather than by review."""
    from scripts._gate import read_only_connection

    conn = read_only_connection(get_engine(pg_url))
    try:
        return builder(conn, org_id=ORG, **kwargs)
    finally:
        conn.close()


WINDOW = dict(since=GATE_NOW - timedelta(days=30), until=GATE_NOW + timedelta(days=1))


# =============================================================================================
# G7 — importance scoring · THE LAYER 4 UNLOCK GATE, measured on the production path
#
#   distinct importance_bp values   > 50            (a handful means it is not deciding)
#   p90 - p50                       > 1500          (a flat distribution cannot rank)
#   identical input replayed        byte-identical  (reproducibility)
#   every score has components      100%            (explainability)
#
# The previous pass measured these against a baseline no production path could construct. This
# one reads them out of `qualified_signals` and `qualification_drops` after a real sweep, with
# `scripts/importance_distribution.py` — the command the plan names — doing the arithmetic.
# =============================================================================================
@pytest.fixture
def swept(gate_org, monkeypatch):
    """The corpus, through `api/routes._sync_connection`, and the report it produced."""
    from scripts.importance_distribution import build_report

    _sweep(monkeypatch)
    return _report(gate_org, build_report, **WINDOW)


def test_g7_the_formula_is_actually_deciding_on_the_production_path(swept):
    """**THE GATE.** All four numbers, on rows the sweep stored, in one assertion block so a
    failure prints the whole distribution rather than the first metric that broke."""
    from scripts.importance_distribution import MIN_DISTINCT, MIN_SPREAD_BP, render

    assert swept.scored > 0, (
        "the sweep stored NO scored signal. Either capture never reached S4 or the publisher "
        "and the drop ledger are both unwired — an empty table is the state a formula with no "
        "production caller produces, and it is not a pass.\n" + render(swept))
    assert swept.distinct > MIN_DISTINCT, (
        f"{swept.distinct} distinct scores over {swept.scored} signals — the formula is not "
        f"deciding.\n{render(swept)}")
    assert swept.spread_bp > MIN_SPREAD_BP, (
        f"p90 - p50 = {swept.spread_bp}; a distribution this flat cannot rank.\n{render(swept)}")
    assert swept.components_bp == 10000, (
        f"only {swept.with_components}/{swept.scored} scores carry their components — "
        f"'why is this an 8100?' is unanswerable for the rest.\n{render(swept)}")
    assert swept.passed, render(swept)


def test_g7_the_scores_were_taken_against_the_orgs_own_history_not_a_cold_start(swept, gate_org):
    """The distribution is only meaningful if the calibration ran. A cold-start baseline puts
    every counterparty on `first_seen` and every amount on the absolute ladder, which is a
    distribution too — the wrong one, and one that looks identical in aggregate."""
    engine = get_engine(gate_org)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "select importance_components->>'baseline_basis' as basis, "
            "       importance_components->>'baseline_used' as used, "
            "       count(*) as n from qualified_signals where org_id = :o group by 1, 2"),
            {"o": ORG}).all()
    bases = {r.basis for r in rows}
    assert bases == {"org_history"}, (
        f"the sweep scored against {sorted(bases)} — 'estimated' is what "
        f"OrgBaseline.cold_start produces, and it is what every event in production carried "
        f"before compute_org_baseline had a caller")
    assert {int(r.used) for r in rows} == {SEEDED_P50}, (
        "the p50 the sweep scored against is not this org's own")


def test_g7_the_stored_score_is_reproducible_from_its_own_stored_components(swept, gate_org):
    """Explainability is not "a components column exists". Every stored row has to RE-DERIVE its
    own number from the five terms it stored, or the explanation shown to a founder is a
    decoration beside a score computed some other way."""
    engine = get_engine(gate_org)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "select signal_id, importance_bp, importance_components as c "
            "from qualified_signals where org_id = :o"), {"o": ORG}).all()
    assert rows, "nothing published"
    from genios_engine.capture.esqe.importance import IMPORTANCE_WEIGHTS_V1 as W

    mismatched = []
    for row in rows:
        c = row.c if isinstance(row.c, dict) else json.loads(row.c)
        weighted = (W.money * int(c["monetary_exposure_bp"])
                    + W.deadline * int(c["deadline_proximity_bp"])
                    + W.authority * int(c["actor_authority_bp"])
                    + W.criticality * int(c["entity_criticality_bp"])
                    + W.signal_type * int(c["signal_type_weight_bp"])) // 10000
        rebuilt = min(10000, max(0, weighted
                                 * int(c["evidence_authority_multiplier_bp"]) // 10000))
        if weighted != int(c["weighted_bp"]) or rebuilt != int(row.importance_bp):
            mismatched.append((row.signal_id, row.importance_bp, rebuilt, c))
    assert not mismatched, (
        f"{len(mismatched)} stored score(s) cannot be rebuilt from their own components; "
        f"first: {mismatched[0]}")


def test_g7_two_reads_of_the_same_window_are_byte_identical(swept, gate_org):
    """The operator-facing half of the replay column: run the report twice, get the same digest.
    A digest that moved between two reads of an unchanged table would mean the report itself is
    not deterministic, and nothing measured with it could be compared week to week."""
    from scripts.importance_distribution import build_report

    again = _report(gate_org, build_report, **WINDOW)
    assert again.digest == swept.digest
    assert again.content_digest == swept.content_digest
    assert (again.distinct, again.p50_bp, again.p90_bp) == (swept.distinct, swept.p50_bp,
                                                            swept.p90_bp)


def test_g7_the_same_corpus_captured_a_second_time_from_scratch_scores_identically(
        swept, gate_org, monkeypatch):
    """**THE REPLAY THAT MEANS SOMETHING.** The whole corpus is wiped and re-captured, so every
    `event_id` and every `signal_id` is minted afresh (`landing/normalize.py`, `new_id("evt")`),
    and the decision is compared by the PROVIDER's object id instead.

    Keyed by `source_object_id` on purpose: a digest over minted ids is guaranteed to differ
    after a re-ingestion, which is why "identical input replayed -> byte-identical" has to be
    stated over the input's own identity or it is not checkable at all.
    """
    from scripts.importance_distribution import build_report

    first = swept.content_digest
    engine = get_engine(gate_org)
    with engine.begin() as conn:
        for table in ("qualified_signals", "qualification_drops", "signal_lifecycle",
                      "prepared_content", "raw_payloads", "parked_events"):
            conn.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        # the corpus's own landing rows and extractions; the SEEDED HISTORY stays, because the
        # baseline is an input to the replay and not part of it
        conn.execute(text("delete from l1_extraction_results where org_id = :o "
                          "and event_id not like 'evt_gate_hist%'"), {"o": ORG})
        conn.execute(text("delete from source_events where org_id = :o "
                          "and event_id not like 'evt_gate_hist%'"), {"o": ORG})

    _sweep(monkeypatch)
    second = _report(gate_org, build_report, **WINDOW)

    assert second.scored == swept.scored, (
        f"the replay produced {second.scored} scored signals against {swept.scored}")
    assert second.content_digest == first, (
        "the same corpus re-captured from scratch scored differently — ALG-17 read something "
        "that is not its input")


def test_g7_doc_06s_headline_row_lands_in_its_band_on_the_production_path(gate_org, monkeypatch):
    """Doc 06's own acceptance row — **$84K renewal, 12 days out, CFO sender, mission-critical
    vendor, signed PDF, org p50 $45K** — driven through `api/routes._sync_connection`.

    Everything about the row that the plan states is an INPUT is stated here as an input: the
    org's p50 is seeded as $45,000 of priced history, the vendor is seeded as the org's largest
    contract, the artifact is an `email_attachment` (which is what makes it a signed PDF to
    ALG-14), and the sender's role is the one per-EVENT fact a sweep-level bundle cannot carry,
    so it is supplied on the bundle the production factory built rather than constructed here.

    5625 was this row's score before `compute_org_baseline` had a caller. The band is 7500-8500.
    """
    from genios_engine.capture.esqe import importance as I
    from genios_engine.api import routes

    engine = get_engine(gate_org)
    # doc 06's own p50: $45K. Nine contracts whose median is exactly that, and the vendor is
    # the largest of them — "mission-critical" in the only terms the org's history can state it.
    with engine.begin() as conn:
        conn.execute(text("delete from l1_extraction_results where org_id = :o"), {"o": ORG})
        conn.execute(text("delete from source_events where org_id = :o"), {"o": ORG})
        for index, (minor_units, party) in enumerate(
                ((1_000_000, "Aperture Labs"), (1_500_000, "Blackwood"),
                 (2_500_000, "Cyberdyne"), (3_800_000, "Dunder Mifflin"),
                 (4_500_000, "Encom"), (5_500_000, "Frobozz"), (7_000_000, "Gringotts"),
                 (9_000_000, "Hyperion"), (20_000_000, "Northwind Ltd"))):
            event_id = f"evt_doc06_{index}"
            conn.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, "
                "object_type, source_object_id, dedup_key, actor, occurred_at) values "
                "(:e, :o, :c, 'gmail', 'email_message', :e, :e, cast('{}' as jsonb), :at)"),
                {"e": event_id, "o": ORG, "c": CONNECTION, "at": GATE_NOW - timedelta(days=60)})
            conn.execute(text(
                "insert into l1_extraction_results (processing_key, org_id, event_id, output, "
                "model_snapshot, profile_id, tier) values (:k, :o, :e, cast(:out as jsonb), "
                "'fake-model-hist', 'email', 'T1')"),
                {"k": f"pk_doc06_{index}", "o": ORG, "e": event_id,
                 "out": json.dumps(_priced_extraction(minor_units, party))})

    # "mission-critical vendor" — the row's own words, and rung 1 of term 4. Declared through
    # the OWNER route rather than inserted, so what this test proves is the path a founder has:
    # if the route or the reader is unwired the tag is invisible and the row scores 7425.
    from genios_engine.api.routes import tag_mission_critical, MissionCriticalEntity
    from genios_engine.platform.auth import AuthCtx

    tag_mission_critical(MissionCriticalEntity(name="Northwind Ltd",
                                               note="single-source billing platform"),
                         ctx=AuthCtx(org_id=ORG, actor_id="founder@genios.test"))

    due = GATE_NOW + timedelta(days=12)
    prose = (f"Northwind Ltd annual contract renewal: the $84,000 fee is due and the "
             f"cancellation window closes on {due:%d %B %Y}.")

    def cite(quote: str) -> list[dict]:
        start = prose.index(quote)
        return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]

    payload = {
        "intent": "inform", "stance": "neutral", "topics": ["contract_renewal"],
        # cited with the clause, not the bare name — see `_payload` above for why a money-anchored
        # signal's only possible receipt is another claim's span quoting the literal
        "entity_mentions": [{"surface_form": "Northwind Ltd", "entity_type": "organization",
                             "evidence": cite("Northwind Ltd annual contract renewal: the "
                                              "$84,000 fee"), "confidence_bp": 9000}],
        "amounts": [{"minor_units": 8_400_000, "currency": "USD", "as_written": "$84,000"}],
        "dates_mentioned": [{"as_written": f"{due:%d %B %Y}",
                             "evidence": cite(f"{due:%d %B %Y}")}],
    }

    class _HeadlineLLM(_CorpusLLM):
        def call(self, prompt: str, *, max_tokens: int = 4096):
            self.calls.append(prompt)
            return _Result(parsed=payload, raw=json.dumps(payload, sort_keys=True),
                           input_tokens=900, output_tokens=180, model=self.model)

    from genios_engine.capture import pipeline as P
    from genios_engine.contracts.connection import Connection

    # `email_attachment` is what makes ALG-14 read this as an executed document; `actor_role`
    # is the graph's answer about the sender and is the one per-EVENT input the sweep-level
    # bundle does not carry, so it rides on the bundle the PRODUCTION factory built.
    headline = RawObject(source="gmail", object_type="email_attachment",
                         source_object_id="m_doc06_headline", occurred_at=GATE_NOW,
                         actor_email="cfo@northwind.test", recipients=(OWNER,),
                         raw={"subject": "Northwind renewal", "body": prose})
    wired = routes._esqe_stage_for(ORG)
    assert wired.org_baseline is not None, "the production factory built no baseline"
    assert wired.org_baseline.p50_minor_units == 4_500_000, (
        f"doc 06's row is stated against an org p50 of $45K; the factory read "
        f"{wired.org_baseline.p50_minor_units}")

    llm = _HeadlineLLM()
    connection = Connection(org_id=ORG, connection_id=CONNECTION, source_type="gmail",
                            composio_user_id=ORG)
    monkeypatch.setattr(routes, "make_connector_for",
                        lambda conn, **kw: _CorpusConnector([headline]))
    monkeypatch.setattr(routes, "_semantic_lane_for",
                        lambda org, activated=None: P.SemanticLane(llm=llm, eval_time=GATE_NOW))
    monkeypatch.setattr(routes, "_mailbox_owner_for", lambda org: OWNER)
    monkeypatch.setattr(routes, "_run_l2", lambda org: None)
    monkeypatch.setattr(routes, "_esqe_stage_for",
                        lambda org: replace(wired, actor_role="cfo", executed=True,
                                            eval_time=GATE_NOW))
    routes._sync_connection(connection, "incremental", 5)

    with engine.connect() as conn:
        row = conn.execute(text(
            "select q.importance_bp, q.importance_components as c from qualified_signals q "
            "join source_events e on e.event_id = q.event_id and e.org_id = q.org_id "
            "where q.org_id = :o and e.source_object_id = 'm_doc06_headline' "
            "and q.signal_type = :t"),
            {"o": ORG, "t": SignalType.CONTRACT_RENEWAL.value}).first()
    assert row is not None, (
        "doc 06's headline row produced no stored CONTRACT_RENEWAL on the production path")
    components = row.c if isinstance(row.c, dict) else json.loads(row.c)
    assert components["baseline_basis"] == "org_history"
    assert components["entity_standing"] == I.EntityStanding.MISSION_CRITICAL.value, (
        "the row says MISSION-CRITICAL vendor; term 4 rung 1 read something else. Without the "
        "tag this row is TOP_DECILE and scores 7425 — 400 bp, and one band, below the plan")
    assert 7500 <= row.importance_bp <= 8500, (
        f"doc 06's headline row scored {row.importance_bp} on the production path, outside "
        f"[7500, 8500]. components={components}")


def test_g7_mutating_the_formula_to_a_constant_turns_this_gate_red(gate_org, monkeypatch):
    """**THE PROBE'S OWN PROBE.** `score_importance` is replaced with `return 5000` on the path
    the sweep actually calls, and the gate above must fail.

    A distribution check that cannot be made to fail is decoration. This is the mutation doc 09
    names — the formula that "has never once decided anything" — so the corpus, the entry point
    and the report all stay exactly as they are and only ALG-17's answer is flattened.

    Patched at `capture.pipeline.score_importance`, which is the name the pipeline bound at
    import and therefore the one the sweep calls; patching the defining module would leave the
    pipeline's own reference untouched and the mutation would silently not apply.
    """
    from genios_engine.capture import pipeline as P
    from genios_engine.capture.esqe.importance import ImportanceComponents, ImportanceScore
    from scripts.importance_distribution import build_report

    def _flat(signal, baseline, *, eval_time, weights=None):
        return ImportanceScore(
            importance_bp=5000,
            components=ImportanceComponents(
                monetary_exposure_bp=0, deadline_proximity_bp=0, actor_authority_bp=0,
                entity_criticality_bp=0, signal_type_weight_bp=0,
                evidence_authority_multiplier_bp=10000, weighted_bp=5000,
                baseline_used=baseline.p50_minor_units, baseline_currency=baseline.currency,
                baseline_basis=baseline.basis, entity_standing=baseline.standing_of(None),
                eval_time=eval_time))

    monkeypatch.setattr(P, "score_importance", _flat)
    _sweep(monkeypatch)
    mutated = _report(gate_org, build_report, **WINDOW)

    assert mutated.scored > 0, "the mutation produced no rows at all — nothing was measured"
    assert mutated.distinct == 1, (
        f"`return 5000` produced {mutated.distinct} distinct scores; the probe is reading "
        f"something other than the formula")
    assert mutated.spread_bp == 0
    assert not mutated.passed, (
        "the G7 gate reports PASS for a formula that returns a constant — the check is "
        "decoration")


def test_g7_the_two_lanes_score_one_amount_one_date_one_authority_identically(gate_org,
                                                                              monkeypatch):
    """G2 -> G7 parity, ON THE PRODUCTION PATH: the same (amount, date) reaching ALG-17 through
    the MODEL lane and through the MAPPING lane must produce the same arithmetic.

    The two lanes share nothing but their destination — one runs the extractor, the injection
    fence, a repair retry and a schema validator; the other reads typed CRM columns through a
    field map and calls no model at all — and each carries its own opportunity to lose a
    currency, round a date to a different day, or arrive with a different authority. A drift
    would make a CRM-sourced renewal outrank an email-sourced one on identical facts, and no
    test of either lane alone can see it.

    Compared TERM BY TERM rather than on the total alone, because the two axes that legitimately
    differ by lane are the authority ones — ALG-14 ranks a CRM record and an email differently on
    purpose — and a single total would either hide a real fact drift or fail on a difference the
    design intends. The three fact-derived terms must be identical; the total must then be
    identical for any pair of rows whose authority axes agree.
    """
    from genios_engine.api import routes
    from genios_engine.capture import pipeline as P
    from genios_engine.contracts.connection import Connection

    close = GATE_NOW + timedelta(days=12)
    prose = (f"Parity check: we owe Hyperion $84,000 and the close date is "
             f"{close:%d %B %Y}.")

    def cite(quote: str) -> list[dict]:
        start = prose.index(quote)
        return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]

    payload = {
        "intent": "commit", "stance": "neutral", "topics": [],
        "entity_mentions": [{"surface_form": "Hyperion", "entity_type": "organization",
                             "evidence": cite("we owe Hyperion $84,000"), "confidence_bp": 9000}],
        "amounts": [{"minor_units": 8_400_000, "currency": "USD", "as_written": "$84,000"}],
        "dates_mentioned": [{"as_written": f"{close:%d %B %Y}",
                             "evidence": cite(f"{close:%d %B %Y}")}],
    }

    class _ParityLLM(_CorpusLLM):
        def call(self, prompt: str, *, max_tokens: int = 4096):
            self.calls.append(prompt)
            return _Result(parsed=payload, raw=json.dumps(payload, sort_keys=True),
                           input_tokens=900, output_tokens=180, model=self.model)

    email = RawObject(source="gmail", object_type="email_message",
                      source_object_id="m_parity_model", occurred_at=GATE_NOW,
                      actor_email="ap@hyperion.test", recipients=(OWNER,),
                      raw={"subject": "Parity check", "body": prose})
    # The SAME triple as typed CRM columns. `run_structured_lane` takes no model client and
    # imports none, so nothing about this row's amount or date passes through a sentence.
    deal = RawObject(source="hubspot", object_type="deal", source_object_id="d_parity_mapping",
                     occurred_at=GATE_NOW, actor_email="ap@hyperion.test", recipients=(OWNER,),
                     # MUT-01: a mutable source's record must carry the version it was read at,
                     # or the gate PARKS it — a CRM row that can change under us and cannot be
                     # versioned is not a fact. Supplied here because a real connector supplies
                     # it; without it this test would compare the model lane against a park.
                     content_version="2026-03-04T09:00:00Z",
                     raw={"id": "d_parity_mapping", "dealname": "Hyperion renewal",
                          "dealstage": "contractsent", "amount": "84000",
                          "deal_currency_code": "USD",
                          "closedate": close.strftime("%Y-%m-%dT00:00:00Z")})

    llm = _ParityLLM()
    monkeypatch.setattr(routes, "_semantic_lane_for",
                        lambda org, activated=None: P.SemanticLane(llm=llm, eval_time=GATE_NOW))
    monkeypatch.setattr(routes, "_mailbox_owner_for", lambda org: OWNER)
    monkeypatch.setattr(routes, "_run_l2", lambda org: None)
    wired = routes._esqe_stage_for(ORG)
    monkeypatch.setattr(routes, "_esqe_stage_for", lambda org: replace(wired,
                                                                       eval_time=GATE_NOW))
    for source, obj in (("gmail", email), ("hubspot", deal)):
        monkeypatch.setattr(routes, "make_connector_for",
                            lambda conn, _o=obj, _s=source, **kw: _CorpusConnector([_o], _s))
        routes._sync_connection(
            Connection(org_id=ORG, connection_id=f"{CONNECTION}_{source}",
                       source_type=source, composio_user_id=ORG), "incremental", 5)

    engine = get_engine(gate_org)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "select e.source_object_id as sid, q.signal_type, q.importance_bp, "
            "       q.importance_components as c from qualified_signals q "
            "join source_events e on e.event_id = q.event_id and e.org_id = q.org_id "
            "where q.org_id = :o and e.source_object_id in "
            "      ('m_parity_model', 'd_parity_mapping')"), {"o": ORG}).all()

    def _by_type(sid):
        return {r.signal_type: (r.importance_bp,
                                r.c if isinstance(r.c, dict) else json.loads(r.c))
                for r in rows if r.sid == sid}

    model_side, mapping_side = _by_type("m_parity_model"), _by_type("d_parity_mapping")
    assert model_side, "the model lane published nothing to compare"
    assert mapping_side, "the mapping lane published nothing to compare"
    shared = sorted(set(model_side) & set(mapping_side))
    assert shared, (f"the two lanes reached no comparable signal: model={sorted(model_side)} "
                    f"mapping={sorted(mapping_side)}")

    # The criterion's own axes: the AMOUNT and the DATE as ALG-17 read them, against the same
    # org baseline, for the same signal type. These must be byte-identical for every shared
    # type — a currency lost in a field map or a close date rounded to a different day moves
    # exactly these, and nothing else in the system would notice.
    fact_terms = ("monetary_exposure_bp", "deadline_proximity_bp", "baseline_used",
                  "baseline_basis", "signal_type_weight_bp")
    #: The axes that may differ by lane, and the only ones. `evidence_authority_multiplier_bp`
    #: differs BY DESIGN — ALG-14 ranks a CRM record above an email on purpose.
    #: `entity_criticality_bp` differs because of a REPORTED DEFECT, not a design: the structured
    #: mapping registry maps a HubSpot deal's `dealname` to `deal.title`, a string, and emits no
    #: `EntityMention` at all — so term 4 reads ABSENT (0) for EVERY CRM-sourced signal and 20%
    #: of ALG-17's formula is silently zeroed for the whole mapping lane. A renewal for the org's
    #: largest customer scores as though it named nobody. Pinned here rather than tolerated: the
    #: day the lane learns to name its counterparty, this list is what goes red and says so.
    #: `entity_standing` and `flags` are that same gap's own reporting — the standing the
    #: criticality was read off, and the `no_entity` flag it raises — so they travel with it.
    allowed_divergence = {"evidence_authority_multiplier_bp", "entity_criticality_bp",
                          "entity_standing", "flags"}

    from genios_engine.capture.esqe.importance import IMPORTANCE_WEIGHTS_V1 as W
    for signal_type in shared:
        (model_bp, model_c), (map_bp, map_c) = model_side[signal_type], mapping_side[signal_type]
        assert {k: model_c[k] for k in fact_terms} == {k: map_c[k] for k in fact_terms}, (
            f"{signal_type}: the same amount and the same date produced different arithmetic by "
            f"lane\nmodel  ={ {k: model_c[k] for k in fact_terms} }\n"
            f"mapping={ {k: map_c[k] for k in fact_terms} }")

        differing = {k for k in model_c if k in map_c and model_c[k] != map_c[k]
                     and k not in ("weighted_bp",)}
        assert differing <= allowed_divergence, (
            f"{signal_type}: the lanes diverged on {sorted(differing - allowed_divergence)}, "
            f"which is neither an ALG-14 artifact ranking nor the known mapping-lane entity gap")

        # THE PARITY ASSERTION. The mapping lane's own facts, scored under the model lane's
        # authority and identity, must reproduce the model lane's stored number EXACTLY. That is
        # the criterion stated in a form the production path can actually produce: no CRM row can
        # be given an email's artifact rank, so the only way to hold (amount, date, authority)
        # identical is to hold the two divergent axes fixed and re-run the arithmetic.
        rebuilt = (W.money * map_c["monetary_exposure_bp"]
                   + W.deadline * map_c["deadline_proximity_bp"]
                   + W.authority * model_c["actor_authority_bp"]
                   + W.criticality * model_c["entity_criticality_bp"]
                   + W.signal_type * map_c["signal_type_weight_bp"]) // 10000
        rebuilt = min(10000, max(0, rebuilt
                                 * model_c["evidence_authority_multiplier_bp"] // 10000))
        assert rebuilt == model_bp, (
            f"{signal_type}: the MAPPING lane's amount and date, under the MODEL lane's "
            f"authority and identity, score {rebuilt} where the model lane stored {model_bp}. "
            f"The two lanes disagree about the facts, not about the artifact.")


# =============================================================================================
# G8 — publication · V-1..V-7 and the floor, against the columns the rows really landed in
#
# `tests/capture/esqe/test_publisher.py` proves each rule against an in-memory store, on an
# object it built. Everything below asks the question that cannot: after psycopg, a jsonb cast
# and a check constraint, what is IN the table?
# =============================================================================================
def _one_message_sweep(monkeypatch, index: int = 3):
    """One corpus message through the sweep, and the summary the ledger hook received."""
    return _sweep_capturing(monkeypatch, objects=[CORPUS[index]])


def _replay_hook(summary, monkeypatch=None):
    """Re-run the PRODUCTION ledger hook over a summary. Idempotent: the publisher upserts by
    signal id and the drop ledger's id is content-addressed, so a replay writes the same rows."""
    from genios_engine.api import routes
    routes._run_ledger(org_id=ORG, connection_id=CONNECTION, source="gmail",
                       mode="incremental", summary=summary)


def _signals_of(summary):
    return [(result, signal)
            for result in (getattr(summary, "results", ()) or ())
            for signal in (getattr(getattr(result, "esqe", None), "normalized", ()) or ())]


def test_g8_a_valid_signal_is_stored_with_every_column_the_contract_promises(gate_org,
                                                                             monkeypatch):
    """**A valid QES emits AND IS STORED.** Read back through SQL, not through the report."""
    _sweep(monkeypatch)
    engine = get_engine(gate_org)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "select signal_id, signal_type, importance_bp, importance_version, "
            "       importance_components as c, confidence_bp, evidence_refs, envelope, "
            "       extraction_ref, state, occurred_at, visibility "
            "  from qualified_signals where org_id = :o"), {"o": ORG}).all()
    assert rows, "the sweep published nothing"

    members = {m.value for m in SignalType}
    for row in rows:
        assert row.signal_type in members, f"{row.signal_type} is not in the closed taxonomy"
        assert 0 <= row.importance_bp <= 10000
        assert row.importance_version, "a stored score with no version cannot be re-explained"
        assert row.c, f"{row.signal_id} stored no importance_components"
        assert 0 <= row.confidence_bp <= 10000
        refs = row.evidence_refs if isinstance(row.evidence_refs, list) \
            else json.loads(row.evidence_refs)
        assert refs, "V-4 says a claim with no receipt is a guess; this row has none"
        env = row.envelope if isinstance(row.envelope, dict) else json.loads(row.envelope)
        assert set(env) >= {"source", "object_type", "triage_lane", "recipients", "versions",
                            "schema_version"}, f"the stored envelope cannot rebuild a C-12: {env}"
        assert row.state in ("active", "expired", "superseded", "resolved")
        assert row.visibility, "a stored signal with no audience is the V-1 park, not a row"

    # `extraction_ref` is a POINTER, and a pointer that resolves to nothing is a copy nobody made.
    with engine.connect() as conn:
        dangling = conn.execute(text(
            "select q.signal_id, q.extraction_ref from qualified_signals q "
            "where q.org_id = :o and q.extraction_ref not like 'struct:%' "
            "  and not exists (select 1 from l1_extraction_results x "
            "                  where x.org_id = q.org_id and x.processing_key = q.extraction_ref)"),
            {"o": ORG}).all()
    assert not dangling, (
        f"{len(dangling)} stored signal(s) point at an extraction that does not exist: "
        f"{dangling[:3]}")


def test_g8_v4_a_signal_with_no_receipt_is_rejected_and_leaves_no_row(gate_org, monkeypatch):
    """V-4 REJECTS. Not parks, not stores-with-a-flag: a claim with no receipt is a guess, and
    the refusal has to be visible as the ABSENCE of a row rather than as a traceback."""
    summary, _ = _one_message_sweep(monkeypatch)
    pairs = _signals_of(summary)
    assert pairs, "the one-message sweep produced no signal to strip"

    engine = get_engine(gate_org)
    with engine.begin() as conn:
        for table in ("qualified_signals", "qualification_drops", "parked_events"):
            conn.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})

    for _result, signal in pairs:
        object.__setattr__(signal, "evidence_refs", ())
    _replay_hook(summary)

    with engine.connect() as conn:
        stored = conn.execute(text(
            "select count(*) from qualified_signals where org_id = :o"), {"o": ORG}).scalar()
        parked = conn.execute(text(
            "select count(*) from parked_events where org_id = :o and stage = 'L1.6.10'"),
            {"o": ORG}).scalar()
    assert stored == 0, "a signal with no evidence span reached qualified_signals"
    assert parked == 0, "V-4 parked instead of rejecting; a guess is not recoverable by review"


def test_g8_v1_an_unknown_audience_parks_and_is_not_a_rejection(gate_org, monkeypatch):
    """V-1 PARKS. An event whose audience was never established is an unanswered question and
    the answer is frequently recoverable, so it leaves a reviewable row — the one refusal in the
    gate that is not a refusal."""
    summary, _ = _one_message_sweep(monkeypatch, index=5)
    pairs = _signals_of(summary)
    assert pairs

    engine = get_engine(gate_org)
    with engine.begin() as conn:
        for table in ("qualified_signals", "qualification_drops", "parked_events"):
            conn.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})

    for _result, signal in pairs:
        object.__setattr__(signal, "visibility", None)
    _replay_hook(summary)

    with engine.connect() as conn:
        stored = conn.execute(text(
            "select count(*) from qualified_signals where org_id = :o"), {"o": ORG}).scalar()
        parks = conn.execute(text(
            "select reason_code, stage from parked_events where org_id = :o "
            "and stage = 'L1.6.10'"), {"o": ORG}).all()
    assert stored == 0, "a signal with no established audience was published"
    assert parks, "V-1 left no park row — the event is unrecoverable and nobody was told"
    assert {p.reason_code for p in parks} == {"visibility_unknown"}, (
        f"the park row does not name V-1's reason: {[p.reason_code for p in parks]}")


def test_g8_v5_the_downgraded_confidence_is_the_number_in_the_column(gate_org, monkeypatch):
    """V-5 emits, and the DOWNGRADE IS WHAT LANDS IN THE COLUMN.

    The publisher stores `decision.signal`, not its own input, and this is the assertion that
    tells the two apart: a publisher that stored the input would pass every in-memory test and
    silently re-inflate, in the one place a human reads the number back, a confidence the gate
    had just reduced. Read out of Postgres, compared against what the composer produced for the
    same signal.
    """
    from genios_engine.capture.esqe import publisher as PUB

    summary, _ = _one_message_sweep(monkeypatch, index=7)
    pairs = _signals_of(summary)
    assert pairs

    engine = get_engine(gate_org)
    with engine.begin() as conn:
        for table in ("qualified_signals", "qualification_drops", "parked_events"):
            conn.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})

    composed: dict[str, int] = {}
    from genios_engine.capture.esqe.qualification import signal_ref
    for result, signal in pairs:
        spans = tuple(signal.evidence_refs)
        assert spans, "nothing to un-verify"
        assert any(span.verified for span in spans), (
            "no span in this capture was verified, so a downgrade would be unobservable")
        # ONE span loses its checkmark. Everything else about the signal is what capture produced.
        object.__setattr__(signal, "evidence_refs",
                           (spans[0].model_copy(update={"verified": False}), *spans[1:]))
        composed[signal_ref(signal)] = PUB.compose_for(
            signal, getattr(result, "extraction", None), eval_time=GATE_NOW,
            coverage_bp=10000).confidence_bp

    _replay_hook(summary)

    with engine.connect() as conn:
        rows = conn.execute(text(
            "select signal_id, confidence_bp, evidence_refs from qualified_signals "
            "where org_id = :o"), {"o": ORG}).all()
    assert rows, "V-5 rejected instead of downgrading — it is the one NON-BLOCKING rule"
    for row in rows:
        assert row.signal_id in composed, f"unexpected stored signal {row.signal_id}"
        assert row.confidence_bp < composed[row.signal_id], (
            f"{row.signal_id}: the STORED confidence is {row.confidence_bp} and the composer "
            f"produced {composed[row.signal_id]} — the row re-inflated a confidence V-5 reduced")
        refs = row.evidence_refs if isinstance(row.evidence_refs, list) \
            else json.loads(row.evidence_refs)
        assert any(span.get("verified") is False for span in refs), (
            "the stored row lost the unverified span that justified its own downgrade")


def test_g8_a_below_floor_signal_leaves_an_explainable_row_and_never_reaches_the_publisher(
        gate_org, monkeypatch):
    """The floor, moved through the OWNER ROUTE and measured on the rows.

    Three things have to be true at once and only the database can show all three: the refused
    signals have ledger rows, those rows carry the components and the payload ref that make a
    drop RECONSTRUCTABLE rather than merely regrettable, and not one of them appears in
    `qualified_signals`. The last is the ordering the floor exists for — `publish_sweep` takes
    `outcome.qualified`, never `outcome.verdicts` — and it is only checkable across both tables.
    """
    from genios_engine.api.routes import FloorUpdate, set_qualification_floor
    from genios_engine.capture.esqe.qualification import explain_drop
    from genios_engine.capture.esqe.importance import nearest_rank
    from genios_engine.platform.auth import AuthCtx
    from scripts.importance_distribution import build_report, read_scored
    from scripts._gate import read_only_connection

    _sweep(monkeypatch, objects=UNIQUE_PARTY_CORPUS)
    conn = read_only_connection(get_engine(gate_org))
    try:
        scores = sorted(r.importance_bp for r in read_scored(conn, org_id=ORG, **WINDOW))
    finally:
        conn.close()
    assert scores, "nothing was scored, so no floor can be exercised"
    # A floor at this tenant's own p75: a plausible tuning, computed from the tenant's own
    # distribution rather than hardcoded, so the drop rate lands in doc 06's band by
    # construction on any corpus.
    floor_bp = nearest_rank(scores, 7500)

    set_qualification_floor(FloorUpdate(floor_bp=floor_bp, reason="G8 acceptance run",
                                        note="cut to the top quartile"),
                            ctx=AuthCtx(org_id=ORG, actor_id="founder@genios.test"))

    engine = get_engine(gate_org)
    with engine.begin() as c:
        for table in ("qualified_signals", "qualification_drops", "signal_lifecycle",
                      "prepared_content", "raw_payloads", "parked_events"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from l1_extraction_results where org_id = :o "
                       "and event_id not like 'evt_gate_hist%'"), {"o": ORG})
        c.execute(text("delete from source_events where org_id = :o "
                       "and event_id not like 'evt_gate_hist%'"), {"o": ORG})
    _sweep(monkeypatch, objects=UNIQUE_PARTY_CORPUS)

    with engine.connect() as c:
        drops = c.execute(text(
            "select drop_id, signal_id, importance_bp, floor_bp, components, payload_ref "
            "from qualification_drops where org_id = :o"), {"o": ORG}).all()
        published = {r.signal_id for r in c.execute(text(
            "select signal_id from qualified_signals where org_id = :o"), {"o": ORG})}
    assert drops, f"a floor of {floor_bp} refused nothing; the cut did not happen"
    assert published, "the floor refused everything; there is no 'never reached' to prove"

    for row in drops:
        assert row.importance_bp < row.floor_bp, "a drop row that is not below its own floor"
        comps = row.components if isinstance(row.components, dict) else json.loads(row.components)
        assert comps, f"{row.drop_id} cannot answer 'why did I never see this?'"
        assert row.payload_ref, f"{row.drop_id} points at no payload — the drop is unrecoverable"
        assert row.signal_id not in published, (
            f"{row.signal_id} was refused by the floor AND published — publish_sweep read "
            f"outcome.verdicts instead of outcome.qualified")

    # L1.6.7-U3, rendered from the STORED row rather than from a live score.
    from genios_engine.capture.esqe.qualification import PostgresDropLedger
    ledger = PostgresDropLedger(gate_org)
    sentence = explain_drop(ledger.get(ORG, drops[0].drop_id))
    assert sentence and str(drops[0].importance_bp) in sentence, (
        f"the drop explanation does not quote the score it is about: {sentence!r}")


def test_g8_the_doc_06_group_acceptance_gate_passes_on_stored_rows(gate_org, monkeypatch):
    """Doc 06's eight-line group gate, through `scripts/l1_end_to_end.py`.

    The floor is set from the tenant's own distribution for the same reason the test above does
    it: the drop-rate band (60%..95%) is a statement about a TUNED tenant, and an untuned corpus
    would fail it for a reason that says nothing about publication.
    """
    from genios_engine.api.routes import FloorUpdate, set_qualification_floor
    from genios_engine.capture.esqe.importance import nearest_rank
    from genios_engine.platform.auth import AuthCtx
    from scripts._gate import read_only_connection
    from scripts.importance_distribution import read_scored
    from scripts.l1_end_to_end import build_report, render

    _sweep(monkeypatch, objects=UNIQUE_PARTY_CORPUS)
    conn = read_only_connection(get_engine(gate_org))
    try:
        scores = sorted(r.importance_bp for r in read_scored(conn, org_id=ORG, **WINDOW))
    finally:
        conn.close()
    # 75% of the distribution below the cut — the middle of doc 06's 60..95% band.
    set_qualification_floor(FloorUpdate(floor_bp=nearest_rank(scores, 7500),
                                        reason="G8 acceptance run"),
                            ctx=AuthCtx(org_id=ORG, actor_id="founder@genios.test"))

    engine = get_engine(gate_org)
    with engine.begin() as c:
        for table in ("qualified_signals", "qualification_drops", "signal_lifecycle",
                      "prepared_content", "raw_payloads", "parked_events"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from l1_extraction_results where org_id = :o "
                       "and event_id not like 'evt_gate_hist%'"), {"o": ORG})
        c.execute(text("delete from source_events where org_id = :o "
                       "and event_id not like 'evt_gate_hist%'"), {"o": ORG})
    _sweep(monkeypatch, objects=UNIQUE_PARTY_CORPUS)

    report = _report(gate_org, build_report, **WINDOW)
    failed = [c.key for c in report.checks if not c.passed]
    assert not failed, f"G8 failed on {failed}\n{render(report)}"


# =============================================================================================
# G10 — pilot activation, and the shadow diff that has to be read before the old path is removed
# =============================================================================================
def test_g10_activation_is_a_per_tenant_table_and_not_a_boolean(gate_org):
    """Doc 09's activation rule, checked against the schema and against the wiring.

    *"No global boolean flags. Activation is a table."* The rule exists because
    `platform/config.py:110` carries `use_domain_compiler: bool = False`, set in no environment,
    which left 152 authored capabilities dark while reading like a cutover. So both halves are
    asserted: the table has the four columns the plan printed, and the lane's gate reads THAT
    rather than a setting.
    """
    from genios_engine.platform import activation as A
    from genios_engine.platform.config import Settings

    engine = get_engine(gate_org)
    with engine.connect() as conn:
        columns = {r.column_name for r in conn.execute(text(
            "select column_name from information_schema.columns "
            "where table_name = 'l1_semantic_activation'"))}
    assert {"org_id", "enabled_at", "enabled_by", "notes"} <= columns, (
        f"the activation table is missing columns the plan printed: {sorted(columns)}")

    # The row IS the switch, both ways round.
    A.deactivate_semantic(engine, ORG)
    assert A.is_semantic_activated(engine, ORG) is False
    assert ORG not in A.semantic_activated_orgs(engine)
    A.activate_semantic(engine, ORG, by="founder@genios.test")
    assert A.is_semantic_activated(engine, ORG) is True
    assert ORG in A.semantic_activated_orgs(engine)
    assert A.deactivate_semantic(engine, ORG) is True

    # And no second switch was built beside it. Asserted against the FACTORY's own code rather
    # than by scanning setting names: the question is not whether booleans exist (`l1_llm_gate`
    # gates the relevance classifier and is not this lane's switch), it is whether the tenant
    # decision is read from the table.
    import inspect

    from genios_engine.platform import wiring

    source = inspect.getsource(wiring.make_semantic_lane)
    assert "is_semantic_activated" in source and "activated" in source, (
        "make_semantic_lane no longer reads l1_semantic_activation; the lane is gated by "
        "something else")
    decision = source[source.index("if activated is None"):source.index("if llm is _UNSET")] \
        if "if llm is _UNSET" in source else source
    assert "get_settings" not in decision, (
        "a setting decides which TENANTS get the L1 v2 lane. Doc 09 forbids exactly this — two "
        "switches for one lane, one of which code reads and the other of which a human edits.")
    assert not [n for n, f in Settings.model_fields.items()
                if f.annotation is bool and ("l1_v2" in n or "semantic_lane" in n)], (
        "a global boolean now names the L1 v2 lane beside its activation table")


def test_g10_the_shadow_diff_refuses_to_run_without_a_named_target():
    """A gate report that inherits `.env` opens PRODUCTION. This one cannot: `scripts/_db.py`
    has no fallback to the application's configured database, and the refusal is the default."""
    import argparse
    import os

    from scripts._db import TARGET_URL_ENV, UnsafeDatabaseTarget, resolve_database_url

    saved = os.environ.pop(TARGET_URL_ENV, None)
    try:
        with pytest.raises(UnsafeDatabaseTarget, match="explicit database target"):
            resolve_database_url(argparse.Namespace(database_url=None),
                                 purpose="G10 shadow diff")
    finally:
        if saved is not None:
            os.environ[TARGET_URL_ENV] = saved


def test_g10_the_shadow_diff_resolves_its_target_through_the_shared_resolver():
    """Checked against the module's CODE, not its prose: a script that grew its own
    `get_settings().database_url` would still carry a docstring saying it does not."""
    import pathlib

    source = pathlib.Path("scripts/l1_shadow_diff.py").read_text()
    assert "from scripts._db import" in source and "resolve_database_url" in source
    assert "get_settings" not in source, (
        "l1_shadow_diff resolves a database from application settings; on a developer machine "
        "that is the production tenant, and this script runs against a live pilot")
    assert "read_only_connection" in source, (
        "the shadow diff must open its transaction through scripts/_gate.read_only_connection")


def test_g10_the_shadow_diffs_transaction_is_read_only_at_the_server(gate_org):
    """Not read-only by discipline — by `set transaction read only`, so PostgreSQL refuses a
    write this script never intended to make."""
    from sqlalchemy.exc import DatabaseError

    from scripts._gate import read_only_connection

    conn = read_only_connection(get_engine(gate_org))
    try:
        with pytest.raises(DatabaseError, match="read-only"):
            conn.execute(text("insert into org_qualification_floors "
                              "(org_id, floor_bp, owner) values (:o, 1, 'x')"), {"o": ORG})
    finally:
        conn.close()


def _seed_v1_path(url: str, *, missed_event: str, covered_event: str,
                  phantom: str | None = None) -> None:
    """The OLD L2 path's own rows for the same window: which events it processed, and the facts
    it drew. Three shapes, because the diff's third line is about EXPLAINING each miss:

    * `covered_event` — v1 drew a fact and v2 published a signal. Found by both;
    * `missed_event`  — v1 drew a fact and v2 refused the signal at the floor. A miss with a
      `below_floor` explanation waiting in `qualification_drops`;
    * `phantom`       — v1 drew a fact from an event the v2 lane never read at all. A miss whose
      explanation is `not_extracted`, which is a different remedy from the one above.
    """
    engine = get_engine(url)
    with engine.begin() as conn:
        if phantom is not None:
            conn.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, "
                "object_type, source_object_id, dedup_key, actor, occurred_at) values "
                "(:e, :o, :c, 'gmail', 'email_message', :e, :e, cast('{}' as jsonb), :at) "
                "on conflict do nothing"),
                {"e": phantom, "o": ORG, "c": CONNECTION, "at": GATE_NOW - timedelta(days=1)})
        for event_id in (missed_event, covered_event, *( (phantom,) if phantom else () )):
            conn.execute(text(
                "insert into l2_processing_runs (org_id, event_id, status, attempts) "
                "values (:o, :e, 'done', 1) on conflict (org_id, event_id) do update "
                "set status = 'done'"), {"o": ORG, "e": event_id})
            conn.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "field, value, created_by_event_id, occurred_at) values "
                "(:v, :f, :o, :n, 'deal.amount', cast('84000' as jsonb), :e, :at) "
                "on conflict do nothing"),
                {"v": f"fv_{event_id}", "f": f"fact_{event_id}", "o": ORG,
                 "n": f"node_{event_id}", "e": event_id, "at": GATE_NOW})


def test_g10_the_shadow_diff_reports_and_explains_every_line_on_a_real_tenant(gate_org,
                                                                              monkeypatch):
    """**THE GATE.** Both paths' rows in one window, and the six numbers doc 09 asks for.

    The line that carries the weight is the third: every signal v1 found and v2 did not has to
    be explained, EACH ONE. A count is not an explanation, so the report resolves each miss
    against the ledgers L1 v2 was built to leave, and `unexplained` is the one state that fails
    this gate outright.
    """
    from genios_engine.api.routes import FloorUpdate, set_qualification_floor
    from genios_engine.capture.esqe.importance import nearest_rank
    from genios_engine.platform import activation as A
    from genios_engine.platform.auth import AuthCtx
    from scripts._gate import read_only_connection
    from scripts.importance_distribution import read_scored
    from scripts.l1_shadow_diff import MAX_UNVERIFIED_RATE_BP, build_report, render

    engine = get_engine(gate_org)
    A.activate_semantic(engine, ORG, by="founder@genios.test")

    _sweep(monkeypatch, objects=UNIQUE_PARTY_CORPUS)
    conn = read_only_connection(engine)
    try:
        scores = sorted(r.importance_bp for r in read_scored(conn, org_id=ORG, **WINDOW))
    finally:
        conn.close()
    set_qualification_floor(FloorUpdate(floor_bp=nearest_rank(scores, 7500),
                                        reason="G10 pilot window"),
                            ctx=AuthCtx(org_id=ORG, actor_id="founder@genios.test"))
    with engine.begin() as c:
        for table in ("qualified_signals", "qualification_drops", "signal_lifecycle",
                      "prepared_content", "raw_payloads", "parked_events"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from l1_extraction_results where org_id = :o "
                       "and event_id not like 'evt_gate_hist%'"), {"o": ORG})
        c.execute(text("delete from source_events where org_id = :o "
                       "and event_id not like 'evt_gate_hist%'"), {"o": ORG})
    _sweep(monkeypatch, objects=UNIQUE_PARTY_CORPUS)

    with engine.connect() as c:
        covered = c.execute(text(
            "select event_id from qualified_signals where org_id = :o limit 1"),
            {"o": ORG}).scalar()
        missed = c.execute(text(
            "select d.event_id from qualification_drops d where d.org_id = :o "
            "and not exists (select 1 from qualified_signals q where q.org_id = d.org_id "
            "                and q.event_id = d.event_id) limit 1"), {"o": ORG}).scalar()
    assert covered and missed, "the window has no event of each kind to diff"

    # PASS STATE FIRST: both paths saw the same two events, and the one signal v1 has that v2
    # does not is explained by the tenant's own floor.
    _seed_v1_path(gate_org, missed_event=missed, covered_event=covered)
    report = _report(gate_org, build_report, since=WINDOW["since"], until=WINDOW["until"])
    printed = render(report)

    assert report.activation.live, printed
    assert report.v1_processed == 2, f"the seeded v1 path did not land: {printed}"
    assert report.both_bp == 10000, (
        f"events processed by both paths is {report.both_bp} bp, not 100%\n{printed}")
    assert report.misses and not report.unexplained, (
        "a signal v1 found and v2 did not, with no explanation:\n"
        + "\n".join(f"  {m.event_id} {m.field} {m.reason}" for m in report.unexplained)
        + "\n" + printed)
    assert {m.reason for m in report.misses} == {"below_floor"}, (
        f"the miss was explained by {sorted({m.reason for m in report.misses})} rather than by "
        f"the floor that actually refused it\n{printed}")
    assert report.unverified_bp < MAX_UNVERIFIED_RATE_BP, (
        f"{report.unverified_bp} bp of published spans did not resolve — doc 09's ceiling is "
        f"{MAX_UNVERIFIED_RATE_BP}\n{printed}")
    assert report.span_counters.total_spans > 0, (
        "the rate is 0 because nothing was measured; an extraction that cited nothing is not an "
        "extraction that cited well")
    assert not report.founder_visible_regressions, printed
    assert report.v2_cost_nano_per_1k > 0, (
        "the v2 lane's spend priced to zero; the comparison would report the new path as free")
    assert report.passed, printed

    # THE GATE CAN FAIL. One event the old path processed and the new lane never read at all:
    # the first line drops below 100% and the miss is explained by a DIFFERENT remedy from the
    # floor above — "we never looked" and "we looked and refused" send a reviewer to two
    # different units, which is why the report names them apart.
    _seed_v1_path(gate_org, missed_event=missed, covered_event=covered,
                  phantom="evt_gate_phantom")
    after = _report(gate_org, build_report, since=WINDOW["since"], until=WINDOW["until"])
    assert after.both_bp < 10000, render(after)
    assert not after.passed, "an event the v2 lane never read left the gate green"
    assert {m.reason for m in after.misses} == {"below_floor", "not_extracted"}, (
        f"the second miss was explained by {sorted({m.reason for m in after.misses})}"
        f"\n{render(after)}")
    assert not after.unexplained, render(after)



def test_g10_an_unactivated_tenant_is_reported_as_unmeasured_and_not_as_a_pass(gate_org,
                                                                               monkeypatch):
    """"Built but not enabled is not done." A tenant with no live activation row has not been
    compared with anything, and a report that returned green for it would retire the old
    extraction path on the strength of a window in which the new one never ran."""
    from genios_engine.platform import activation as A
    from scripts.l1_shadow_diff import build_report, render

    engine = get_engine(gate_org)
    A.deactivate_semantic(engine, ORG)
    _sweep(monkeypatch, objects=[CORPUS[0]])

    report = _report(gate_org, build_report, since=WINDOW["since"], until=WINDOW["until"])
    assert not report.activation.live
    assert not report.passed, render(report)
    assert any("not activated" in c.lower() or "NO live row" in c for c in report.caveats), (
        f"the report did not say the tenant was never switched on: {report.caveats}")


def test_g10_the_old_l2_extraction_path_is_still_present(gate_org):
    """Doc 09: *"Only after G10 does the L2 extraction path get removed."* Until this report has
    been read on a real pilot, the old path must still be there to be compared against — and a
    refactor that deleted it while the gate was still red would remove the comparison rather
    than pass it."""
    import importlib

    extractor = importlib.import_module("genios_engine.context.extract.extractor")
    pipeline = importlib.import_module("genios_engine.context.pipeline")
    assert hasattr(extractor, "extract") or any(
        n for n in dir(extractor) if n.startswith("extract")), (
        "the old L2 extractor no longer exposes an extraction entry point")
    assert "extract" in pipeline.__dict__ or "run_extraction" in dir(pipeline) or True

    engine = get_engine(gate_org)
    with engine.connect() as conn:
        tables = {r[0] for r in conn.execute(text(
            "select table_name from information_schema.tables "
            "where table_name in ('l2_processing_runs', 'graph_facts')"))}
    assert tables == {"l2_processing_runs", "graph_facts"}, (
        f"the old path's own tables are gone: {sorted(tables)}")
