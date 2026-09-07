"""J4 · THE ORGANIZATION BRAIN IS FILLED BY A REAL DOCUMENT, THROUGH THE REAL ROUTES.

    pytest tests/feedback/test_org_brain_filled_through_the_routes.py -q   (needs a scratch PG)

WHAT THIS FILE IS FOR, AND WHY IT IS NOT THE ONE NEXT DOOR
----------------------------------------------------------
`tests/packs/brains/test_org_discovery.py` proves the UNIT: hand `run_org_discovery` a document
and three hand-written candidates and the right things happen. That is a claim about a function.
J4's row — *organization entries (discovered + admin-confirmed) >= 3* — is a claim about a
PRODUCT: that a founder who uploads their operating policy ends up with an Organization brain.
Those are different claims, and only the second one is worth a gate row, so every step here is
driven through the HTTP surface a dashboard actually calls:

    POST /api/org/{org}/upload                 the founder uploads `operating-policy.txt`
      -> BackgroundTasks -> sweep_org_rule_discovery      (upload_routes.py's own scheduling)
      -> N-3's production prompt at the model site
      -> CLG-09                                            (packs/brains/org_discovery.py)
      -> admit_discovery -> preflight -> govern -> persist  (the SAME four L6 functions
                                                             orchestrator.run_learning calls)
    GET  /v1/learning/objects?state=human_review           the console queue
    POST /v1/learning/objects/{id}/review {approve:true}   a human confirms
      -> feedback.publisher.publish  -> learned_brain_entries
      -> project_confirmed_rule      -> authority_rules
    GET  /v1/learning/brains                               what the tenant now knows

Nothing below calls `sweep_org_rule_discovery`, `run_org_discovery`, `gate_candidates`,
`admit_discovery`, `publish` or `project_authority_rules`. A test that calls them proves the
functions work and proves nothing about whether an uploaded document reaches them — which was
exactly the state J4 was measured in.

THE DOCUMENT IS A DOCUMENT, NOT A FIXTURE ENGINEERED TO PASS
------------------------------------------------------------
`POLICY_DOC` is a plausible seed-stage operating policy: fourteen statements across six sections,
SEVEN of which are rules the company binds itself to and SEVEN of which are the prose that
surrounds them in every real handbook — a mission line, an aspiration, a nicety, a description of
what usually happens. The point of the seven non-rules is that CLG-09 has to REFUSE them, and the
refusal has to be for the reason the design names. `RULES_BY_DESIGN` and `PROSE_BY_DESIGN` below
state which is which BEFORE the run, so "the classifier admitted a non-rule" is a red test rather
than a number nobody reads.

THE ONLY THING STANDING IN IS THE MODEL, AND IT IS DELIBERATELY OVER-EAGER
--------------------------------------------------------------------------
`_Model` is the T2 site's transport, exactly as `_LLM` is in
`tests/capture/test_upload_door_publishes.py`. It is wrapped in the PRODUCTION
`LLMOrgRuleExtractor`, so the real `PROMPT`, the real JSON contract and the real `MAX_RULES` trim
all execute; the fake is only the thing that would otherwise cost money and vary between runs.

It is written to make the gate WORK rather than to make the test pass: it proposes EVERY sentence
in the document as a candidate rule, with no notion of deontic force, and pointer fields picked by
the crudest plausible reading (first class word in the sentence, first amount, first named role).
So the admitted set is CLG-09's verdict and nobody else's — if the gate leaked, this file would be
the thing that showed it, and the seven prose sentences would land in a brain that decisions are
read from.
"""

from __future__ import annotations

import json
import re
from collections import Counter

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.api import learning_routes, upload_routes
from genios_engine.context.canon import canon_title_key
from genios_engine.packs.brains import org_rule_extract
from genios_engine.packs.brains.org_discovery import REFUSAL_REASONS
from genios_engine.platform.auth import AuthCtx, get_auth_ctx
from genios_engine.platform.db import get_engine

pytestmark = pytest.mark.pg

ORG = "org_j4_org_brain"
ADMIN = "founder@northwindlabs.test"
FILE_NAME = "operating-policy.txt"

#: A seed-stage company's operating policy. Six sections, fourteen statements, written the way a
#: founder writes one — the binding clauses live inside the prose rather than in a list of them.
POLICY_DOC = """NORTHWIND LABS - OPERATING POLICY, REVISION 3

Purpose
Northwind Labs exists to help small teams ship faster than they thought possible.
We would rather tell a customer an uncomfortable truth early than a comfortable one late.

Commercial approvals
Any contract with a total value above $50,000 must be approved by the founder before it is signed.
A discount greater than 15% requires approval from the founder.
We try hard to close every deal before the end of the quarter.

Spending
An expense above $2,000 requires approval from the head of finance.
Vendor invoices are usually paid within thirty days of receipt.
Team lunches are on the company whenever a new customer signs.

Hiring
Every hiring offer must be approved by the founder before it is sent to a candidate.
We aim to reply to every applicant within one week.

Security
Customer data must not be copied onto a personal device.
Access to the production database requires sign-off from the head of engineering.
We care deeply about security and review our posture every quarter.

Support
A customer refund must be issued within thirty days of the request.
"""

#: The seven statements that ARE rules — a condition, a consequence, and (for approvals) an
#: authority — with the brain subject each must land on. Stated before the run.
RULES_BY_DESIGN: dict[str, str] = {
    "Any contract with a total value above $50,000 must be approved by the founder before it is"
    " signed.": "orgrule:approval:contract",
    "A discount greater than 15% requires approval from the founder.":
        "orgrule:approval:discount",
    "An expense above $2,000 requires approval from the head of finance.":
        "orgrule:approval:expense",
    "Every hiring offer must be approved by the founder before it is sent to a candidate.":
        "orgrule:approval:hiring",
    "Customer data must not be copied onto a personal device.": "orgrule:policy:data",
    "Access to the production database requires sign-off from the head of engineering.":
        "orgrule:approval:database",
    "A customer refund must be issued within thirty days of the request.":
        "orgrule:policy:refund",
}

#: The seven that are not. A mission line, a value, an aspiration, a description of what usually
#: happens, a nicety, a target, a reassurance. Every one of them is the sentence CLG-09 exists to
#: keep out of a brain, and every one of them is phrased the way founders actually phrase them.
PROSE_BY_DESIGN: tuple[str, ...] = (
    "Northwind Labs exists to help small teams ship faster than they thought possible.",
    "We would rather tell a customer an uncomfortable truth early than a comfortable one late.",
    "We try hard to close every deal before the end of the quarter.",
    "Vendor invoices are usually paid within thirty days of receipt.",
    "Team lunches are on the company whenever a new customer signs.",
    "We aim to reply to every applicant within one week.",
    "We care deeply about security and review our posture every quarter.",
)

#: `A discount greater than 15% requires approval from the founder.` is a rule by every part of
#: CLG-09's definition and it is NOT admitted, because the production prompt offers "20%" as a
#: `threshold_as_written` example while ALG-10 is a MONEY parser and answers UNPARSEABLE_TOKEN.
#: Pinned as its own constant, and asserted in its own test, because it is a finding about the
#: unit rather than a property of this fixture — see the test for what it costs a tenant.
PERCENTAGE_RULE = "A discount greater than 15% requires approval from the founder."

#: WHAT N-3 ACTUALLY READS IS NOT THE FILE — IT IS THE PREPARED CHUNK, and `_emit_chunk` passes
#: the FILE NAME as that chunk's subject, so `prepared_content.clean_text` begins
#: `operating-policy.txt\n\n` and every span offset in this run is relative to THAT string. It is
#: worth stating rather than hiding behind a tidier fixture: N-3's coordinate system carries one
#: line the founder never wrote, the extractor is shown it like any other line, and CLG-09 refuses
#: it — `operating-policy.` has no deontic force. Measured below as its own number.
DOOR_SUBJECT_LINE = f"{FILE_NAME}\n\n"

#: The roles the policy names, and the identity-layer keys they resolve through. A canon title
#: alias is how a ROLE resolves (org_discovery.resolve_approver_node) — the same key an
#: `org_structure` or `employee_profile` document would have claimed.
APPROVERS: dict[str, str] = {
    "the founder": "node_j4_founder",
    "the head of finance": "node_j4_finance",
    "the head of engineering": "node_j4_engineering",
}

# ══════════════════════════════════════════════════════════════════════════════════════════════
# The model site's transport. Over-eager on purpose — see the module docstring.
# ══════════════════════════════════════════════════════════════════════════════════════════════

#: A statement is a run of characters ending in a full stop. Section headings carry none, so they
#: are not statements — which is also how a reader tells them apart.
SENTENCE = re.compile(r"[^.\n]+\.")

#: The class words a model asked for "the class of thing governed" would reach for. Deliberately
#: NOT including "customer", so the fallback below is exercised and so `Customer data ...` is
#: read as a rule about data rather than about customers.
_CLASS_WORDS = ("contract", "discount", "expense", "hiring", "refund", "vendor", "invoice",
                "database", "data", "offer", "deal", "team", "security", "applicant")
_AMOUNT = re.compile(r"\$[\d,]+(?:\.\d{2})?|\b\d+(?:\.\d+)?%")
_APPROVAL_WORDS = re.compile(r"approv|sign-?off", re.IGNORECASE)
_DOC_BLOCK = re.compile(r"<<<DOC\n(.*)\nDOC\n\nA RULE", re.DOTALL)


def _subject_type(sentence: str) -> str:
    """The crudest plausible reading: the first class word in the sentence, else its first word."""
    hits = [(m.start(), word) for word in _CLASS_WORDS
            if (m := re.search(rf"\b{word}s?\b", sentence, re.IGNORECASE))]
    if hits:
        return min(hits)[1]
    first = re.search(r"[A-Za-z]{2,}", sentence)
    return first.group(0).lower() if first else "thing"


def _approver(sentence: str) -> str | None:
    hits = [(sentence.lower().index(role), role) for role in APPROVERS
            if role in sentence.lower()]
    return min(hits)[1] if hits else None


def candidates_for(document: str) -> list[dict]:
    """Every statement in the document, proposed as a rule. No judgment of any kind."""
    out: list[dict] = []
    for match in SENTENCE.finditer(document):
        raw = match.group(0)
        lead = len(raw) - len(raw.lstrip())
        quote = raw.strip()
        start = match.start() + lead
        amount = _AMOUNT.search(quote)
        out.append({
            "category": "approval" if _APPROVAL_WORDS.search(quote) else "policy",
            "subject_type": _subject_type(quote),
            "quote": quote,
            "start_offset": start,
            "end_offset": start + len(quote),
            "threshold_as_written": amount.group(0) if amount else None,
            "approver_as_written": _approver(quote),
        })
    return out


class _Result:
    def __init__(self, payload: dict) -> None:
        self.parsed = payload
        self.raw = json.dumps(payload, sort_keys=True)
        self.input_tokens, self.output_tokens = 1800, 900
        self.model = "fake-model-org-rule-extract"
        self.cached, self.ok, self.error = False, True, None


class _Model:
    """The transport under the PRODUCTION `LLMOrgRuleExtractor`. Records every prompt it saw."""

    model = "fake-model-org-rule-extract"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def call(self, prompt: str, *, max_tokens: int = 4096):
        self.prompts.append(prompt)
        block = _DOC_BLOCK.search(prompt)
        assert block, "the N-3 prompt did not carry the document it was supposed to read"
        return _Result({"rules": candidates_for(block.group(1))})


# ══════════════════════════════════════════════════════════════════════════════════════════════
# The tenant
# ══════════════════════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — J4's org row needs real Postgres")
    return live_db_url


def _wipe(conn) -> None:
    """Every row this tenant owns, in whatever FK order the schema happens to need.

    Discovered rather than listed: this test writes through the WHOLE upload door — capture,
    prepared content, L1's finalizer, L6 — and a hand-maintained table list is how a test starts
    leaking rows into the next run of itself the day one of those doors gains a table.
    """
    tables = sorted({r[0] for r in conn.execute(text(
        "select table_name from information_schema.columns "
        "where table_schema = 'public' and column_name = 'org_id'"))})
    for _ in range(4):
        remaining = []
        for table in tables:
            savepoint = conn.begin_nested()
            try:
                conn.execute(text(f'delete from "{table}" where org_id = :o'), {"o": ORG})
                savepoint.commit()
            except Exception:                                  # noqa: BLE001 — an FK, next pass
                savepoint.rollback()
                remaining.append(table)
        tables = remaining
        if not tables:
            break
    conn.execute(text("delete from orgs where id = :o"), {"o": ORG})


@pytest.fixture
def seeded(pg_url):
    """A tenant with a DECLARED locale and three named roles. Both are things a company states.

    The locale is not decoration: ALG-10 refuses "$50,000" rather than guessing between USD, CAD
    and AUD, so a tenant that has declared none gets a counted `threshold_unparseable` and an
    empty brain. The roles are canon title aliases — the identity layer's own key for "who is the
    founder", claimed by an org-structure document in production and by three rows here.
    """
    engine = get_engine(pg_url)
    with engine.begin() as conn:
        _wipe(conn)
        required = [r[0] for r in conn.execute(text(
            "select column_name from information_schema.columns where table_name = 'orgs' "
            "and is_nullable = 'NO' and column_default is null and column_name <> 'id'"))]
        cols = ["id"] + required
        conn.execute(text(f"insert into orgs ({', '.join(cols)}) "
                          f"values ({', '.join(':' + c for c in cols)})"),
                     {"id": ORG, **{c: "Northwind Labs" for c in required}})
        conn.execute(text("update orgs set locale = 'en-US', email = :e where id = :o"),
                     {"e": ADMIN, "o": ORG})
        for role, node_id in APPROVERS.items():
            conn.execute(text(
                "insert into graph_aliases (org_id, alias_type, alias_key, node_id, origin) "
                "values (:o, 'canon', :k, :n, 'anchor') on conflict do nothing"),
                {"o": ORG, "k": canon_title_key(role), "n": node_id})
    yield engine
    with engine.begin() as conn:
        _wipe(conn)


@pytest.fixture
def client(seeded, monkeypatch):
    """The dashboard's two routers behind an owner credential, and nothing else stood in.

    `make_org_rule_extractor` is replaced rather than `make_llm_client`: the wiring factory is
    shared with L1's extraction lane and L2's classifier, and swapping it would hand this test's
    canned JSON to doors that are not under test.
    """
    model = _Model()
    monkeypatch.setattr(org_rule_extract, "make_org_rule_extractor",
                        lambda client=None: org_rule_extract.LLMOrgRuleExtractor(model))
    app = FastAPI()
    app.include_router(upload_routes.router)
    app.include_router(learning_routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(org_id=ORG, actor_id=ADMIN)
    test_client = TestClient(app)
    test_client.model = model
    return test_client


# ══════════════════════════════════════════════════════════════════════════════════════════════
# The route drivers. Every one of them is an HTTP call.
# ══════════════════════════════════════════════════════════════════════════════════════════════

def upload_policy(client, *, tag: str = "policy", body: str = POLICY_DOC) -> dict:
    """The founder uploads the policy and tags it as canon. The tag is what makes it rule-bearing:
    `normalize_kind('policy')` puts the chunks in the internal family at authority rank 4."""
    response = client.post(f"/api/org/{ORG}/upload",
                           files={"file": (FILE_NAME, body.encode(), "text/plain")},
                           data={"tag": tag})
    assert response.status_code == 200, response.text
    return response.json()


def pending(client) -> list[dict]:
    """The console's review queue, as the dashboard reads it."""
    response = client.get("/v1/learning/objects",
                          params={"state": "human_review", "target": "organization"})
    assert response.status_code == 200, response.text
    return response.json()["objects"]


def confirm(client, learning_id: str) -> dict:
    response = client.post(f"/v1/learning/objects/{learning_id}/review", json={"approve": True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "promoted"
    assert body["expert_brain_changed"] is False, "Law 3 — the Expert Brain is human territory"
    assert body["published"] not in (None, "object_unreadable", "identity_mismatch",
                                     "rejected"), body
    return body


def brains(client) -> list[dict]:
    response = client.get("/v1/learning/brains")
    assert response.status_code == 200, response.text
    return response.json()["brains"]


def confirm_everything(client) -> list[dict]:
    return [confirm(client, obj["learning_id"]) for obj in pending(client)]


def receipt(engine) -> dict:
    """`org_rule_discovery_runs` — the run's own counters, written by the unit, read by nobody
    else. The arithmetic below is the unit's claim about itself and is checked against the
    lifecycle rows, not trusted."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "select outcome, counters from org_rule_discovery_runs where org_id = :o"),
            {"o": ORG}).mappings().all()
    merged: Counter = Counter()
    for row in rows:
        merged.update({k: v for k, v in (row["counters"] or {}).items() if isinstance(v, int)})
    return {"runs": len(rows), "outcomes": [r["outcome"] for r in rows], **merged}


def rejections(engine) -> Counter:
    with engine.connect() as conn:
        return Counter(r[0].split(":")[0] for r in conn.execute(text(
            "select reason_code from learning_input_rejections where org_id = :o"), {"o": ORG}))


def brain_rows(engine) -> list[dict]:
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(
            "select brain, subject, version, active, value from learned_brain_entries "
            "where org_id = :o order by subject, version"), {"o": ORG}).mappings()]


# ══════════════════════════════════════════════════════════════════════════════════════════════
# J4 — the gate row
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_an_uploaded_policy_fills_the_organization_brain_through_the_console(client, seeded):
    """J4: organization entries (discovered + admin-confirmed) >= 3.

    One HTTP upload, one HTTP read of the queue, one HTTP confirmation per entry. If any link in
    that chain is unwired — the background task, the extractor factory, governance's destination,
    the review route's publish — this is empty, which is the state the gate measured.
    """
    upload_policy(client)
    queue = pending(client)
    assert len(queue) >= 3, ("the upload door did not fill the review queue — "
                             f"discovery receipt: {receipt(seeded)}")
    confirm_everything(client)

    entries = [b for b in brains(client) if b["brain"] == "organization" and b["active"]]
    assert len(entries) >= 3, f"J4 organization row NOT earned: {entries}"
    assert len(entries) == len(RULES_BY_DESIGN) - 1        # the percentage rule; see its own test
    assert sorted(e["subject"] for e in entries) == sorted(
        s for q, s in RULES_BY_DESIGN.items() if q != PERCENTAGE_RULE)
    assert all(e["version"] == 1 for e in entries)
    # Every one of them says where it came from, in the vocabulary doc 02 fixed:
    # admin_declared > discovered > inferred.
    assert {row["value"]["authority_source"] for row in brain_rows(seeded)} == {"discovered"}


def test_the_five_numbers_the_gate_asks_for(client, seeded):
    """statements -> extracted -> admitted -> confirmed -> entries, each one measured.

    The chain is asserted link by link because only the last number is visible in the brain, and a
    pipeline that loses candidates silently between any two of them looks identical from the end.
    """
    # 1 · what the DOCUMENT contained.
    statements = SENTENCE.findall(POLICY_DOC)
    assert len(statements) == 14
    assert len(RULES_BY_DESIGN) + len(PROSE_BY_DESIGN) == 14
    # …and what N-3 was shown, which is one line longer: the upload door prepends the file name
    # as the chunk's subject. Counted separately so neither number is quietly the other.
    assert len(SENTENCE.findall(DOOR_SUBJECT_LINE + POLICY_DOC)) == 15

    upload_policy(client)
    counters = receipt(seeded)
    assert counters["runs"] == 1 and counters["outcomes"] == ["ran"]
    # 2 · what N-3 extracted. Every statement it was shown, because this model gates nothing.
    assert counters["candidates"] == 15, "N-3 did not see every statement in the document"
    # 3 · what CLG-09 admitted, and its complement. `admitted` vs `human_review` is CLG-09's own
    # split (an approver it could not resolve would land in the second); `awaiting_human` is
    # GOVERNANCE's, and it is 6 because an Organization proposal always stops for a human.
    assert counters["admitted"] == 6 and counters["human_review"] == 0
    assert counters["refused"] == 9                  # 7 prose + the file name + the percentage
    assert counters["proposed"] == 6 and counters["awaiting_human"] == 6
    assert counters["admitted"] + counters["refused"] == counters["candidates"]

    confirmed = confirm_everything(client)
    assert len(confirmed) == 6
    entries = [row for row in brain_rows(seeded) if row["active"]]
    assert len(entries) == 6
    assert all(row["brain"] == "organization" for row in entries)


def test_clg09_refuses_the_prose_for_the_reason_the_design_names(client, seeded):
    """The seven sentences that are not rules, and the counted reason each was refused.

    This is the assertion the gate row cannot make: a run that admitted all fourteen would report
    fourteen organization entries and PASS J4 while filling a decision-grade brain with a mission
    statement. Every refusal is named, so a leak here is a red test rather than a bigger number.
    """
    upload_policy(client)
    reasons = rejections(seeded)
    assert set(reasons) <= set(REFUSAL_REASONS), f"an unnamed refusal reason: {reasons}"
    assert len(PROSE_BY_DESIGN) == 7
    assert reasons["no_deontic_force"] == 8          # the seven, plus the door's file-name line
    assert reasons["threshold_unparseable"] == 1
    assert sum(reasons.values()) == 9

    # Each of the seven is refused by NAME, so a leak shows up as a missing row rather than as a
    # larger total that a reader would have to reconcile by hand.
    with seeded.connect() as conn:
        refused_text = [r[0] for r in conn.execute(text(
            "select reason_code from learning_input_rejections where org_id = :o "
            "and reason_code like 'no_deontic_force%'"), {"o": ORG})]
    for prose in PROSE_BY_DESIGN:
        assert any(prose[:80] in row for row in refused_text), prose
    assert any(FILE_NAME.split(".")[0] in row for row in refused_text)

    # And nothing that reads like prose reached the brain.
    confirm_everything(client)
    statements = {row["value"]["statement"] for row in brain_rows(seeded)}
    assert not (statements & set(PROSE_BY_DESIGN))
    assert statements == set(RULES_BY_DESIGN) - {PERCENTAGE_RULE}


def test_a_percentage_threshold_costs_the_tenant_a_real_rule(client, seeded):
    """A FINDING, pinned as a test rather than written in a report nobody re-runs.

    `A discount greater than 15% requires approval from the founder.` has a condition, a
    consequence and an authority. It is a rule by every clause of CLG-09's own definition, the
    production prompt names "20%" as a legal `threshold_as_written`, and it is still refused —
    because `threshold_as_written` is validated by ALG-10, which is a MONEY parser, and "15%"
    comes back UNPARSEABLE_TOKEN. The whole rule is dropped, not the threshold.

    What that costs: discount authority is the single most common approval rule a sales-led
    startup writes down, and it is the one shape this unit cannot read. The refusal is COUNTED
    and visible, which is the design working as designed; the gap is that a percentage bound has
    no representation between `Money` and nothing.
    """
    upload_policy(client)
    confirm_everything(client)

    subjects = {row["subject"] for row in brain_rows(seeded)}
    assert RULES_BY_DESIGN[PERCENTAGE_RULE] not in subjects
    with seeded.connect() as conn:
        reason = conn.execute(text(
            "select reason_code from learning_input_rejections "
            "where org_id = :o and reason_code like 'threshold_unparseable%'"),
            {"o": ORG}).scalar()
    assert reason and "15%" in reason, reason
    # Not a currency question: the tenant HAS declared a locale, and the money rules in the same
    # document parsed under it.
    assert "orgrule:approval:contract" in subjects and "orgrule:approval:expense" in subjects


# ══════════════════════════════════════════════════════════════════════════════════════════════
# The discipline the gate attacks
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_the_upload_alone_writes_no_brain_and_no_authority(client, seeded):
    """THE MODEL PROPOSES; DETERMINISTIC GOVERNANCE DECIDES. The document is uploaded, N-3 has
    run, six proposals exist — and the tenant's brain is still empty until a named human says so.

    Asserted at the two tables a decision path actually reads, because "it goes to human review"
    is a claim about governance's return value and this is a claim about the database.
    """
    upload_policy(client)
    with seeded.connect() as conn:
        assert conn.execute(text("select count(*) from learning_objects where org_id = :o "
                                 "and state = 'human_review'"), {"o": ORG}).scalar() == 6
        assert conn.execute(text("select count(*) from learned_brain_entries where org_id = :o"),
                            {"o": ORG}).scalar() == 0
        assert conn.execute(text("select count(*) from authority_rules where org_id = :o"),
                            {"o": ORG}).scalar() == 0
    assert brains(client) == []


def test_every_admitted_rule_climbed_the_l6_ladder_before_it_reached_a_human(client, seeded):
    """No proposal skipped a rung, and the floors' verdict was RECORDED rather than waived.

    A declaration is not a recurrence: one document, one day, one entity. `admit_discovery`
    evaluates the recurrence floors anyway and writes their verdict into the Validated transition,
    so a reviewer sees what the evidence would have carried on its own. A run in which that detail
    is missing is a run in which the floors were quietly skipped for this route.
    """
    upload_policy(client)
    with seeded.connect() as conn:
        rows = conn.execute(text(
            "select learning_id, from_state, to_state, reason_code, detail "
            "from learning_transitions where org_id = :o"), {"o": ORG}).mappings().all()
    by_object: dict[str, dict[str, str]] = {}
    for row in rows:
        by_object.setdefault(row["learning_id"], {})[row["from_state"] or ""] = row["to_state"]
    assert len(by_object) == 6
    for learning_id, edges in by_object.items():
        walk, state = [], ""
        while state in edges:
            state = edges.pop(state)
            walk.append(state)
        assert not edges, f"{learning_id}: transitions off the chain: {edges}"
        assert walk == ["observed", "candidate", "validated", "governed", "human_review"], walk
    floors = [row["detail"] for row in rows if row["reason_code"] == "floors_evaluated"]
    assert len(floors) == 6
    assert all("floors_ok" in (d or {}) and "floors_reason" in (d or {}) for d in floors)


def test_the_confirmed_approval_rules_reach_the_authority_view(client, seeded):
    """ONE DISCOVERY, TWO CONSUMERS — and the second one appears only after the confirmation,
    inside the review route's own transaction. The four approvals bind; the two policy statements
    name no signatory and correctly bind nobody."""
    upload_policy(client)
    last = confirm_everything(client)[-1]
    assert last["authority_rules"]["upserted"] == 4

    with seeded.connect() as conn:
        rules = conn.execute(text(
            "select subject_type, threshold_minor_units, currency, approver_node_id, source, "
            "evidence_ref, valid_until from authority_rules where org_id = :o "
            "order by subject_type"), {"o": ORG}).mappings().all()
    assert [r["subject_type"] for r in rules] == ["contract", "database", "expense", "hiring"]
    assert all(r["source"] == "discovered" and r["valid_until"] is None for r in rules)
    assert all(r["evidence_ref"].startswith("prepared_content:") for r in rules)
    by_type = {r["subject_type"]: r for r in rules}
    assert by_type["contract"]["threshold_minor_units"] == 5_000_000
    assert by_type["expense"]["threshold_minor_units"] == 200_000
    assert by_type["contract"]["currency"] == by_type["expense"]["currency"] == "USD"
    # A role resolves through the identity layer's own key, and the two heads are not the founder.
    assert by_type["contract"]["approver_node_id"] == APPROVERS["the founder"]
    assert by_type["expense"]["approver_node_id"] == APPROVERS["the head of finance"]
    assert by_type["database"]["approver_node_id"] == APPROVERS["the head of engineering"]
    # Hiring names an approver but no amount — a threshold is optional, an authority is not.
    assert by_type["hiring"]["threshold_minor_units"] is None


def test_re_uploading_the_same_policy_adds_nothing(client, seeded):
    """A founder who uploads the same file twice does not get a second brain, a second version or
    a second review task. Content addressing at the door, the document VERSION key at the unit."""
    upload_policy(client)
    confirm_everything(client)
    before = brain_rows(seeded)

    second = upload_policy(client)
    assert second["duplicate"] is True
    assert pending(client) == []
    assert brain_rows(seeded) == before
    assert receipt(seeded)["runs"] == 1


def test_a_document_the_company_did_not_bind_itself_to_is_never_read(client, seeded):
    """The cost gate, driven through the door rather than asserted about the function: the SAME
    fourteen statements uploaded as a wiki page cost no extraction and produce no proposal.

    `normalize_kind('handbook') == 'wiki'`, which is doc 02's own counter-example — a sentence in
    a handbook is not a rule however confidently it is phrased.
    """
    upload_policy(client, tag="handbook", body=POLICY_DOC + "\nThis page is a wiki.\n")
    assert client.model.prompts == [], "a T2 extraction was paid for on a wiki page"
    assert pending(client) == []
    with seeded.connect() as conn:
        assert conn.execute(text("select count(*) from learning_objects where org_id = :o"),
                            {"o": ORG}).scalar() == 0


def test_the_model_site_ran_the_production_prompt(client, seeded):
    """The only thing stood in is the transport. The prompt N-3 shipped is the prompt in
    `org_rule_extract.PROMPT`, with its closed category set and its copy-the-quote rule — a test
    whose fake extractor bypassed that would be proving a stub."""
    upload_policy(client)
    assert len(client.model.prompts) == 1
    prompt = client.model.prompts[0]
    assert "DOCUMENT KIND: policy" in prompt
    assert '"approval"' in prompt and '"criticality"' in prompt
    assert "COPY the quote" in prompt
    assert "NEVER compute or normalise a number" in prompt
    assert "Any contract with a total value above $50,000" in prompt


def test_the_j4_report_reads_this_orgs_row_as_earned(client, seeded):
    """The gate's OWN instrument, pointed at the tenant these routes just filled.

    `scripts/brain_content_report.py` is the literal J4 command block, and it asks two questions a
    count cannot: how did each entry get there, and did anything reach the brain without a proposal
    behind it. Running it here rather than re-implementing its arithmetic is what makes this row
    earned rather than asserted — including the part that would fail if N-3's unit name ever
    drifted out of `_pipeline_units()`, which would silently reclassify every discovered entry as
    `unattributed` and turn one gate row red while leaving the count green.

    The behavior and adaptive rows are 0 here on purpose: they are the other half of this wave, and
    a fixture that faked them would make this report say something it did not measure.
    """
    from datetime import datetime, timezone

    from scripts import brain_content_report as report

    upload_policy(client)
    confirm_everything(client)
    with seeded.connect() as conn:
        built = report.build_report(conn, org_id=ORG, at=datetime.now(timezone.utc))

    organization = built.brain("organization")
    assert organization.entries == 6 >= report.MIN_ORGANIZATION_ENTRIES
    assert organization.by_provenance == {"discovered": 6}
    assert built.outside_pipeline == 0
    assert built.unattributed == 0
    assert built.expert_rows == 0
    rows = {label: (ok, measured) for label, ok, measured in built.checks}
    assert rows[f"organization entries >= {report.MIN_ORGANIZATION_ENTRIES}"] == (True, "6")
    assert rows["writes outside the L6 pipeline == 0"][0] is True
    assert rows["entries with unnameable provenance == 0"][0] is True
    assert rows["rows with brain='expert' == 0"][0] is True


# ══════════════════════════════════════════════════════════════════════════════════════════════
# The provenance join — the gate row that a fabricated identity turns red
# ══════════════════════════════════════════════════════════════════════════════════════════════

def test_every_brain_entry_names_the_proposal_the_human_approved(client, seeded):
    """A BUG THIS FILE FOUND, pinned where it broke: at the join, not at the count.

    `learned_brain_entries.learning_id` is the only thread from a brain a decision reads back to
    the proposal a named human approved, and `LearningObject` is content-addressed — its id IS
    its identity hash. `learning_routes._publish_approved` rebuilds the object from the row, and
    it rebuilt `Visibility.derived_from` as `str(<json array>)`; `Visibility.__post_init__` then
    ran `tuple()` over that STRING, so the rehydrated lineage was a tuple of single CHARACTERS.
    The rehydration did not fail — it SUCCEEDED under a different hash, and every approval wrote
    its brain entry under an id that joins back to nothing. Six discovered rules, six entries,
    and `scripts/brain_content_report.py` read all six as `unattributed`: J4's "writes outside
    the L6 pipeline == 0" row, red, on a path whose count row was green.

    So the assertion is the JOIN and the HASH, never the count. `semantic_hash` is now compared
    before the publish, which is why `identity_mismatch` is a sink this test also forbids.
    """
    upload_policy(client)
    approved = {obj["learning_id"] for obj in pending(client)}
    sinks = {body["published"] for body in confirm_everything(client)}
    assert "identity_mismatch" not in sinks, "the rehydrated object was not the object"

    with seeded.connect() as conn:
        rows = conn.execute(text(
            "select e.learning_id, e.subject, o.unit, o.state, o.semantic_hash "
            "from learned_brain_entries e "
            "left join learning_objects o on o.org_id = e.org_id "
            "and o.learning_id = e.learning_id "
            "where e.org_id = :o and e.active"), {"o": ORG}).mappings().all()
    assert len(rows) == 6
    # Every entry joins, to a PROMOTED N-3 proposal, and to one of the objects this test approved.
    assert all(row["unit"] == "org_rule_discovery" for row in rows), \
        "a brain entry with no proposal behind it — the L6 pipeline was bypassed"
    assert all(row["state"] == "promoted" for row in rows)
    assert {row["learning_id"] for row in rows} == approved
    # …and the id is the content hash it claims to be, not a coincidence of the same length.
    assert all(row["learning_id"] == f"lo_{row['semantic_hash'][:24]}" for row in rows)


def test_an_edited_policy_supersedes_the_rule_it_replaces(client, seeded):
    """Invariant #8 through the DOOR: one active version per (org, brain, subject).

    The J0-J4 gate found this index was only ever exercised through `publish_brain`, which
    deactivates first — so the constraint could be downgraded and 140 tests would stay green.
    This drives it the way a founder does: revision 3 is uploaded and confirmed, the threshold
    changes, revision 4 is uploaded and confirmed, and the tenant is left with ONE binding answer
    to "what does a $60,000 contract need?" rather than two that disagree.
    """
    upload_policy(client)
    confirm_everything(client)

    revised = POLICY_DOC.replace("REVISION 3", "REVISION 4").replace("$50,000", "$75,000")
    second = upload_policy(client, body=revised)
    assert second.get("duplicate") is not True, "an edited policy was mistaken for the same file"
    assert len(pending(client)) == 6, "the edited document was not read again"
    confirm_everything(client)

    with seeded.connect() as conn:
        versions = conn.execute(text(
            "select version, active, value from learned_brain_entries where org_id = :o "
            "and subject = 'orgrule:approval:contract' order by version"),
            {"o": ORG}).mappings().all()
        # The index is the enforcement, so ask the DATABASE how many actives it is holding.
        actives = conn.execute(text(
            "select subject, count(*) from learned_brain_entries where org_id = :o and active "
            "group by subject having count(*) > 1"), {"o": ORG}).all()
    assert actives == [], f"more than one active version per subject: {actives}"
    assert [(v["version"], v["active"]) for v in versions] == [(1, False), (2, True)]
    assert versions[0]["value"]["threshold_minor_units"] == 5_000_000
    assert versions[1]["value"]["threshold_minor_units"] == 7_500_000
    # And the Authority view moved with it rather than accumulating a second open window.
    with seeded.connect() as conn:
        binding = conn.execute(text(
            "select threshold_minor_units from authority_rules where org_id = :o "
            "and subject_type = 'contract' and valid_until is null"), {"o": ORG}).all()
    assert [r[0] for r in binding] == [7_500_000]


def test_a_lossy_rehydration_refuses_to_publish_under_a_fabricated_identity(client, seeded):
    """THE GUARD ITSELF, driven — because deleting it broke NOTHING when the gate mutated it.

    `_publish_approved` compares the rehydrated object's `semantic_hash` against the column
    `persist()` wrote, and refuses with the sink `identity_mismatch` when they differ. That check
    was added because the `derived_from` round-trip was lossy; but the two tests above only prove
    the round-trip is lossless TODAY, so removing the comparison left 420 tests green. A guard
    against the NEXT lossy field has to be exercised by a lossy field, and the honest way to make
    one is to corrupt the stored row the way a crash or an older writer's format would: the row
    still parses, the object still rebuilds, and it rebuilds as a DIFFERENT object.

    The claim is both halves of the refusal — the sink is named, and NOTHING is written. A brain
    entry attributed to no proposal is the "writes outside the L6 pipeline" row, and it is worse
    than an approval that could not publish, because an unpublished approval is visible in the
    console and re-runnable while a mis-attributed entry is neither.
    """
    upload_policy(client)
    victim = pending(client)[0]["learning_id"]

    # A lineage that is not the lineage the object was hashed with. The row stays valid JSON and
    # the rehydration below still SUCCEEDS — which is exactly the failure mode: it succeeds as
    # something else.
    with seeded.begin() as conn:
        conn.execute(text(
            "update learning_objects set visibility = "
            "jsonb_set(visibility, '{derived_from}', cast(:d as jsonb)) "
            "where org_id = :o and learning_id = :l"),
            {"d": json.dumps(["internal_kind:policy", "evt_a_different_event"]),
             "o": ORG, "l": victim})

    response = client.post(f"/v1/learning/objects/{victim}/review", json={"approve": True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["published"] == "identity_mismatch", body
    assert body["expert_brain_changed"] is False

    with seeded.connect() as conn:
        entries = conn.execute(text(
            "select count(*) from learned_brain_entries where org_id = :o "
            "and learning_id = :l"), {"o": ORG, "l": victim}).scalar()
        # …and not under the fabricated id either. NOTHING was written by this approval.
        total = conn.execute(text(
            "select count(*) from learned_brain_entries where org_id = :o"), {"o": ORG}).scalar()
        rules = conn.execute(text(
            "select count(*) from authority_rules where org_id = :o"), {"o": ORG}).scalar()
    assert entries == 0, "a brain entry was written under an identity that joins back to nothing"
    assert total == 0
    assert rules == 0
