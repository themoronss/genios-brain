"""GeniOS-011 S44.U1 · the ideal-card gap scorecard: "a good card" as a measured gap, not an opinion.

    .venv/bin/python -m pytest -q tests/scripts/test_ideal_card_gap.py
    GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest -q tests/scripts/test_ideal_card_gap.py

Rohit (23 Oct): a local ideal-state dashboard shows the cards he wants; the website's cards are nothing
like them. `scripts/ideal_card_gap.py` puts each ideal card beside the product card for the same
counterparty and scores it field by field. What is held here:

  * a subject cut mid-word, over 90 characters or not starting with a verb is not "clear";
  * a product field that reads the same on two product cards is "not its own" (the repeated-text check);
  * matching is by the counterparty — email first, then company domain (never a free-mail domain), then
    name — one product card per ideal card and one ideal card per product card, in a stated order;
  * a quote is the counterparty's own words: never our own mail, never the card's own reading;
  * the report is a markdown table and a JSON with totals; exit 0 for any report, `--assert-min-found`
    is the CI lever;
  * `--from-dashboard` reads the dashboard's CARDS array through `node`, or says why it cannot;
  * `--database-url` reads the card rows on a connection whose transaction is `read only` first.

⛔ SYNTHETIC DATA ONLY. Every person, company, address and sentence below is invented. The real ideal
dashboard holds Rohit's mail and is never copied into the repo, a test or a fixture.
"""
from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path

import pytest
from sqlalchemy import text

from scripts import ideal_card_gap as gap

SCRIPT = Path(gap.__file__)


# ── synthetic fixtures ─────────────────────────────────────────────────────────────────────────────

def _ideal(**over) -> dict:
    """One ideal card in the dashboard's field names — every person and word invented."""
    card = {
        "id": "i1", "lane": "decide", "cat": "sales",
        "head": "Confirm Thursday 4 pm with Asha Verma (Northwind)",
        "sum": "Asha asked for a slot to walk through the pilot terms.",
        "why": "She holds the budget and the quarter closes on Friday.",
        "reco": "Offer Thursday 4 pm and attach the pilot terms.",
        "how": "Reply in her thread.",
        "steps": ["Reply with Thursday 4 pm", "Attach the pilot terms"],
        "who": "You", "by": "Wed 18:00", "forWhom": "Asha Verma · Northwind",
        "avoid": "Do not send the full contract yet.",
        "doneWhen": "She accepts the invite.",
        "ifNot": "The pilot slips to next quarter.",
        "alt": "Offer Friday 10 am instead.",
        "wait": "Stop if she declines twice.",
        "goal": "g-pilot-q4",
        "draft": "Hi Asha, Thursday 4 pm works — terms attached.",
        "tools": [["Gmail", "mail", "2 days ago"]],
        "quotes": [["Could we find 30 minutes this week for the terms?",
                    "Asha · Email (asha@northwind.example)", "2 days ago"]],
        "people": [["Asha Verma", "Head of Ops · Northwind"]],
    }
    card.update(over)
    return card


def _product(**over) -> dict:
    """One product card as `GET /cards/{id}` returns it — every value invented."""
    card = {
        "card_id": "c1",
        "headline": "Confirm Thursday 4 pm with Asha Verma",
        "situation": "Asha asked to walk through the pilot terms this week.",
        "why_now": "The quarter closes Friday and she holds the budget.",
        "business_subject": "Asha Verma",
        "recommended": {"who": "Founder", "what": "Offer Thursday 4 pm with the pilot terms",
                        "for_whom": "Asha Verma", "by_when": "Wed 18:00",
                        "to": "asha@northwind.example"},
        "decision": {"recommendation": {"steps": ["Reply with Thursday 4 pm", "Attach the terms"],
                                        "avoid": "Hold the full contract until she asks."}},
        "do_nothing_consequence": "The pilot moves to next quarter.",
        "success_signal": "Asha accepts the Thursday invite.",
        "alternative": "Offer Friday 10 am.",
        "wait_or_stop": "Stop after a second decline.",
        "goal": {"id": "g-pilot-q4", "title": "Close the Q4 pilot"},
        "artifact": {"kind": "draft", "body": "Hi Asha — Thursday 4 pm works; terms attached."},
        "context_tags": ["app:gmail"],
        "why": [{"sentence": "headline", "source": "expert_check",
                 "quotes": ["Could we find 30 minutes this week for the terms?"]}],
    }
    card.update(over)
    return card


def _other_product(card_id: str, subject: str, email: str, **over) -> dict:
    """A second, unrelated product card whose every text is its own."""
    first = subject.split()[0]
    own = dict(card_id=card_id, headline=f"Reply to {subject} about the renewal",
               situation=f"{first} asked whether the renewal price holds.",
               why_now=f"{first}'s renewal is due this month.",
               business_subject=subject,
               recommended={"who": "Founder", "what": f"Send {first} the renewal quote",
                            "for_whom": subject, "by_when": "Fri", "to": email},
               decision={"recommendation": {"steps": [f"Quote {first} the renewal price"],
                                            "avoid": f"Do not discount {first}'s plan."}},
               do_nothing_consequence=f"{first}'s renewal lapses.",
               success_signal=f"{first} signs the renewal.",
               alternative=f"Call {first} instead.", wait_or_stop=f"Stop if {first} churns.",
               goal={"id": f"g-{card_id}"},
               artifact={"body": f"Hi {first}, here is the renewal quote."},
               why=[{"sentence": "headline", "quotes": [f"{first}: does the price hold?"]}])
    own.update(over)
    return _product(**own)


def _card(report: dict, ideal_id: str) -> dict:
    [card] = [c for c in report["cards"] if c["ideal_id"] == ideal_id]
    return card


# ── subject clear ──────────────────────────────────────────────────────────────────────────────────

def test_a_clear_subject_is_clear():
    ok, why = gap.subject_clear("Confirm Thursday 4 pm with Asha Verma")
    assert ok, why


def test_a_subject_cut_mid_word_is_not_clear():
    ok, why = gap.subject_clear("Confirm Thursday 4 pm with Asha about the contr…")
    assert not ok and "cut" in why


def test_a_subject_cut_at_a_joiner_is_not_clear():
    ok, why = gap.subject_clear("Send the pilot terms to")
    assert not ok and "cut" in why


def test_a_subject_over_ninety_characters_is_not_clear():
    ok, why = gap.subject_clear("Confirm " + "a very long subject line " * 4)
    assert not ok and "90" in why


def test_a_subject_that_does_not_start_with_a_verb_is_not_clear():
    ok, why = gap.subject_clear("Asha Verma — relationship open, nothing moving")
    assert not ok and "verb" in why


def test_a_cut_product_subject_fails_subject_clear_in_the_report():
    cut = _product(headline="Confirm Thursday 4 pm with Asha about the contr…")
    report = gap.build_report([_ideal()], [cut])
    subject = _card(report, "i1")["fields"]["subject"]
    assert subject["ok"] is False and "cut" in subject["why"]
    assert subject["product"].startswith("Confirm Thursday")


# ── the whole card, and the repeated-text check ────────────────────────────────────────────────────

def test_a_card_with_every_field_its_own_scores_every_field():
    report = gap.build_report([_ideal()], [_product()])
    card = _card(report, "i1")
    assert card["found"] is True and card["product_card_id"] == "c1"
    failed = {name: f["why"] for name, f in card["fields"].items() if not f["ok"]}
    assert failed == {}
    assert set(card["fields"]) == set(gap.FIELD_NAMES)
    assert report["totals"]["cards_found"] == 1 and report["totals"]["cards"] == 1
    assert report["totals"]["fields_filled"] == report["totals"]["fields"] == len(gap.FIELD_NAMES)


def test_a_why_shared_by_two_product_cards_is_not_its_own():
    shared = "Founders who wait a week lose the deal."
    asha = _product(why_now=shared)
    ravi = _other_product("c2", "Ravi Menon", "ravi@lakeside.example", why_now=shared)
    report = gap.build_report([_ideal()], [asha, ravi])
    why = _card(report, "i1")["fields"]["why"]
    assert why["ok"] is False and "not its own" in why["why"]
    assert why["product"] == shared
    # Everything else on the card is its own, so only the shared field is marked.
    others = {n for n, f in _card(report, "i1")["fields"].items() if not f["ok"]}
    assert others == {"why"}


def test_repeated_text_is_compared_after_case_and_space_are_ignored():
    asha = _product(success_signal="They reply.")
    ravi = _other_product("c2", "Ravi Menon", "ravi@lakeside.example", success_signal="  they   REPLY. ")
    report = gap.build_report([_ideal()], [asha, ravi])
    assert _card(report, "i1")["fields"]["done_when"]["ok"] is False


def test_stock_steps_shared_by_two_cards_are_not_their_own():
    stock = {"recommendation": {"steps": ["Reply in the thread"], "avoid": "Hold the contract."}}
    asha = _product(decision=stock)
    ravi = _other_product("c2", "Ravi Menon", "ravi@lakeside.example",
                          decision={"recommendation": {"steps": ["Reply in the thread"],
                                                       "avoid": "Ravi's own avoid."}})
    report = gap.build_report([_ideal()], [asha, ravi])
    assert _card(report, "i1")["fields"]["how_steps"]["ok"] is False


def test_an_empty_field_is_not_filled_and_says_so():
    report = gap.build_report([_ideal()], [_product(alternative="   ", goal=None)])
    fields = _card(report, "i1")["fields"]
    assert fields["alternative"]["ok"] is False and fields["alternative"]["why"] == "empty"
    assert fields["goal"]["ok"] is False


def test_who_by_needs_both_the_who_and_the_by_when():
    report = gap.build_report([_ideal()], [_product(recommended={"who": "Founder", "what": "x y",
                                                                  "to": "asha@northwind.example"})])
    who_by = _card(report, "i1")["fields"]["who_by"]
    assert who_by["ok"] is False and "by" in who_by["why"]


def test_a_field_the_ideal_card_does_not_have_is_not_counted():
    ideal = _ideal(draft="", alt=None)
    report = gap.build_report([ideal], [_product()])
    fields = _card(report, "i1")["fields"]
    assert "draft" not in fields and "alternative" not in fields
    assert report["totals"]["fields"] == len(gap.FIELD_NAMES) - 2


# ── quotes are the counterparty's own words ────────────────────────────────────────────────────────

def test_a_quote_from_our_own_mail_is_not_the_counterpartys():
    ours = _product(why=[{"sentence": "headline",
                          "quotes": [{"quote": "Sharing the terms now.", "from_counterparty": False}]}])
    report = gap.build_report([_ideal()], [ours])
    quotes = _card(report, "i1")["fields"]["quotes"]
    assert quotes["ok"] is False


def test_a_quote_whose_author_is_unknown_is_not_claimed_as_theirs():
    unknown = _product(why=[{"quote": "Can we talk Thursday?", "from_counterparty": None}])
    assert _card(gap.build_report([_ideal()], [unknown]), "i1")["fields"]["quotes"]["ok"] is False


def test_a_quote_that_is_the_cards_own_reading_is_not_a_quote():
    reading = "Asha asked to walk through the pilot terms this week."
    own = _product(why=[{"sentence": "headline", "quotes": [reading]}])
    assert _card(gap.build_report([_ideal()], [own]), "i1")["fields"]["quotes"]["ok"] is False


def test_a_counterparty_quote_dict_counts():
    theirs = _product(why=[{"kind": "ask", "quote": "Could we meet Thursday?", "from_counterparty": True}])
    assert _card(gap.build_report([_ideal()], [theirs]), "i1")["fields"]["quotes"]["ok"] is True


# ── matching ───────────────────────────────────────────────────────────────────────────────────────

def test_matching_by_email_when_no_name_agrees():
    ideal = _ideal(people=[["Asha", "Ops"]], forWhom="")
    product = _product(business_subject="A. V.", recommended={
        "who": "Founder", "what": "Offer Thursday", "for_whom": "Northwind ops",
        "by_when": "Wed", "to": "ASHA@northwind.example"})
    report = gap.build_report([ideal], [product])
    card = _card(report, "i1")
    assert card["found"] is True and card["matched_by"] == "email"


def test_matching_by_company_domain():
    ideal = _ideal(people=[], forWhom="", quotes=[["Hi", "Email (ops@northwind.example)", "1 d"]])
    product = _product(business_subject="Northwind", recommended={
        "who": "Founder", "what": "Offer Thursday", "by_when": "Wed", "to": "asha@northwind.example"})
    card = _card(gap.build_report([ideal], [product]), "i1")
    assert card["found"] is True and card["matched_by"] == "domain"


def test_a_free_mail_domain_never_matches_two_people():
    ideal = _ideal(people=[], forWhom="", quotes=[["Hi", "Email (asha.v@gmail.com)", "1 d"]])
    product = _product(business_subject="Ravi Menon", recommended={
        "who": "Founder", "what": "Reply", "by_when": "Wed", "to": "ravi.m@gmail.com"}, why=[])
    card = _card(gap.build_report([ideal], [product]), "i1")
    assert card["found"] is False


def test_matching_by_name():
    product = _product(recommended={"who": "Founder", "what": "Offer Thursday", "by_when": "Wed"},
                       why=[{"quotes": ["Could we meet?"]}])
    card = _card(gap.build_report([_ideal()], [product]), "i1")
    assert card["found"] is True and card["matched_by"] == "name"


def test_an_ideal_card_with_no_product_card_is_not_found_and_scores_nothing():
    ravi = _other_product("c2", "Ravi Menon", "ravi@lakeside.example")
    report = gap.build_report([_ideal()], [ravi])
    card = _card(report, "i1")
    assert card["found"] is False and card["product_card_id"] is None
    assert all(f["ok"] is False and f["why"] == "no product card" for f in card["fields"].values())
    assert report["totals"]["cards_found"] == 0 and report["totals"]["fields_filled"] == 0


def test_one_product_card_answers_one_ideal_card_and_email_beats_name():
    by_name = _ideal(id="i_name", people=[["Asha Verma", "Ops"]], quotes=[], forWhom="")
    by_email = _ideal(id="i_email", people=[], forWhom="",
                      quotes=[["Hi", "Asha · Email (asha@northwind.example)", "1 d"]])
    report = gap.build_report([by_name, by_email], [_product()])
    assert _card(report, "i_email")["found"] is True
    assert _card(report, "i_name")["found"] is False, "the product card is already the email match's"


def test_the_first_product_card_in_rank_order_wins_a_tie():
    first = _product(card_id="c_first")
    second = _product(card_id="c_second", headline="Book a call with Asha Verma")
    card = _card(gap.build_report([_ideal()], [first, second]), "i1")
    assert card["product_card_id"] == "c_first"


def test_the_operator_named_as_self_is_never_the_counterparty():
    ideal = _ideal(people=[["Rohan Founder", "you"]], forWhom="", quotes=[])
    product = _other_product("c2", "Rohan Founder", "rohan@ourco.example")
    assert _card(gap.build_report([ideal], [product]), "i1")["found"] is True
    report = gap.build_report([ideal], [product], self_keys=["Rohan Founder", "rohan@ourco.example"])
    assert _card(report, "i1")["found"] is False


# ── the report ─────────────────────────────────────────────────────────────────────────────────────

def test_markdown_holds_the_totals_and_a_row_per_field_with_the_products_value():
    report = gap.build_report([_ideal()], [_product(alternative="")])
    md = gap.render_markdown(report)
    assert "cards found 1/1" in md
    assert f"fields filled {len(gap.FIELD_NAMES) - 1}/{len(gap.FIELD_NAMES)}" in md
    assert "| alternative |" in md and "✗" in md and "✓" in md
    assert "Confirm Thursday 4 pm with Asha Verma" in md


def test_a_long_product_value_is_truncated():
    long_line = "Asha asked " + "about the pilot terms and the timeline " * 6
    report = gap.build_report([_ideal()], [_product(situation=long_line)])
    shown = _card(report, "i1")["fields"]["summary"]["product"]
    assert len(shown) <= gap.SHOWN_CHARS and shown.endswith("…")


def test_a_pipe_in_a_value_does_not_break_the_table():
    report = gap.build_report([_ideal()], [_product(alternative="Call | or mail")])
    assert "Call \\| or mail" in gap.render_markdown(report)


def _write(tmp_path, name, data) -> str:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def test_main_writes_markdown_and_json_and_exits_zero_with_nothing_found(tmp_path, capsys):
    ideal = _write(tmp_path, "ideal.json", [_ideal()])
    product = _write(tmp_path, "product.json",
                     {"cards": [_other_product("c2", "Ravi Menon", "ravi@lakeside.example")]})
    out_json = tmp_path / "gap.json"
    out_md = tmp_path / "gap.md"
    code = gap.main(["--ideal", ideal, "--product", product,
                     "--json", str(out_json), "--md", str(out_md)])
    assert code == 0
    kept = json.loads(out_json.read_text(encoding="utf-8"))
    assert kept["unit"] == gap.UNIT and kept["totals"]["cards_found"] == 0
    assert "cards found 0/1" in out_md.read_text(encoding="utf-8")


def test_assert_min_found_is_the_ci_lever(tmp_path):
    ideal = _write(tmp_path, "ideal.json", {"cards": [_ideal()]})
    product = _write(tmp_path, "product.json", [_product()])
    assert gap.main(["--ideal", ideal, "--product", product, "--assert-min-found", "1"]) == 0
    assert gap.main(["--ideal", ideal, "--product", product, "--assert-min-found", "2"]) == 1


def test_a_list_dump_with_details_reads_the_detail_over_the_queue_row(tmp_path):
    queue_row = {"card_id": "c1", "headline": "Asha Verma"}
    dump = {"cards": [queue_row], "details": {"c1": _product()}}
    cards = gap.load_product(_write(tmp_path, "product.json", dump))
    assert cards[0]["headline"] == "Confirm Thursday 4 pm with Asha Verma"
    assert cards[0]["why_now"]


def test_an_unreadable_input_is_exit_two(tmp_path, capsys):
    bad = tmp_path / "ideal.json"
    bad.write_text("{not json", encoding="utf-8")
    product = _write(tmp_path, "product.json", [_product()])
    assert gap.main(["--ideal", str(bad), "--product", product]) == 2


# ── --from-dashboard: node, never a regex over JavaScript ──────────────────────────────────────────

_DASHBOARD_JS = """
const CATS = { sales: 'Sales' };
const catBy = (k) => CATS[k];
const CARDS = [
  { id: 'd1', head: 'Confirm Thursday with Asha Verma', people: [['Asha Verma', 'Ops']],
    cat: catBy('sales') },
];
window.__seen = true;
"""


def test_from_dashboard_without_node_is_the_documented_error(tmp_path, monkeypatch):
    js = tmp_path / "02-data.js"
    js.write_text(_DASHBOARD_JS, encoding="utf-8")
    monkeypatch.setattr(gap.shutil, "which", lambda name: None)
    with pytest.raises(gap.DashboardUnreadable, match="node"):
        gap.extract_dashboard_cards(str(js))
    product = _write(tmp_path, "product.json", [_product()])
    assert gap.main(["--from-dashboard", str(js), "--product", product]) == 2


def test_from_dashboard_reads_the_cards_array_through_node(tmp_path):
    """No skip: on a machine without node this asserts the documented error instead."""
    js = tmp_path / "02-data.js"
    js.write_text(_DASHBOARD_JS, encoding="utf-8")
    if shutil.which("node") is None:
        with pytest.raises(gap.DashboardUnreadable, match="node"):
            gap.extract_dashboard_cards(str(js))
        return
    cards = gap.extract_dashboard_cards(str(js))
    assert cards == [{"id": "d1", "head": "Confirm Thursday with Asha Verma",
                      "people": [["Asha Verma", "Ops"]], "cat": "Sales"}]


def test_a_dashboard_file_with_no_cards_array_is_refused(tmp_path):
    js = tmp_path / "02-data.js"
    js.write_text("const GOALS = [];\n", encoding="utf-8")
    with pytest.raises(gap.DashboardUnreadable):
        gap.extract_dashboard_cards(str(js))


def test_the_script_never_parses_javascript_with_a_regex():
    """By the AST: no regex call takes the dashboard source. The only JavaScript reader is node."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"), feature_version=(3, 11))
    extract = next(n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "extract_dashboard_cards")
    called = {getattr(c.func, "attr", getattr(c.func, "id", None))
              for c in ast.walk(extract) if isinstance(c, ast.Call)}
    assert "run" in called
    assert not called & {"findall", "search", "match", "finditer", "sub", "compile"}


def test_the_script_parses_as_python_311():
    ast.parse(SCRIPT.read_text(encoding="utf-8"), feature_version=(3, 11))


# ── --database-url: read-only, and on a real database ──────────────────────────────────────────────

class _FakeConn:
    def __init__(self):
        self.statements = []
        self.closed = False

    def execute(self, statement, params=None):
        self.statements.append((str(statement), params))
        return _FakeResult()

    def close(self):
        self.closed = True


class _FakeResult:
    def mappings(self):
        return []


class _FakeEngine:
    def __init__(self):
        self.connections = []

    def connect(self):
        conn = _FakeConn()
        self.connections.append(conn)
        return conn


def test_the_database_read_opens_a_read_only_transaction_first(tmp_path, monkeypatch):
    import genios_engine.platform.db as db
    engine = _FakeEngine()
    monkeypatch.setattr(db, "get_engine", lambda url: engine)
    ideal = _write(tmp_path, "ideal.json", [_ideal()])
    code = gap.main(["--ideal", ideal, "--database-url", "postgresql://u:p@localhost:5432/x",
                     "--org", "org_s44u1_fake"])
    assert code == 0
    [conn] = engine.connections
    assert conn.statements[0][0] == "set transaction read only"
    assert conn.statements[1][1] == {"org": "org_s44u1_fake"}
    assert conn.closed


def test_a_database_read_needs_an_org(tmp_path):
    ideal = _write(tmp_path, "ideal.json", [_ideal()])
    assert gap.main(["--ideal", ideal, "--database-url", "postgresql://u:p@localhost:5432/x"]) == 2


ORG_PG = "org_g011_s44u1_pg"


@pytest.fixture
def seeded(live_db_url):
    """One org with one open app card about the synthetic Asha — committed, because the scorecard
    opens its own connection. Removed afterwards."""
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the card read runs on a migrated scratch "
                    "database")
    from genios_engine.platform.db import get_engine
    engine = get_engine(live_db_url)

    def _clean():
        with engine.begin() as c:
            c.execute(text("delete from cards where org_id=:o"), {"o": ORG_PG})
            c.execute(text("delete from signals where org_id=:o"), {"o": ORG_PG})
            c.execute(text("delete from orgs where id=:o"), {"o": ORG_PG})

    _clean()
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'G011 S44.U1')"), {"o": ORG_PG})
        c.execute(text(
            "insert into signals (signal_id, org_id, rule_id, subject_node_id, score, reason_code, "
            "eval_time, candidate_steps) values ('sig_s44u1', :o, 'r', 'n', 90, 'unanswered_email', "
            "now(), cast(:steps as jsonb))"),
            {"o": ORG_PG, "steps": json.dumps(["Reply with Thursday 4 pm"])})
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, "
            "score, state, expires_at, business_subject, why_now, recommended) values ('card_s44u1', "
            "'sig_s44u1', :o, 'prescriptive', 'high', 'Confirm Thursday 4 pm with Asha Verma', "
            "'Asha asked to walk through the pilot terms.', 90, 'queued', now() + interval '1 day', "
            "'Asha Verma', 'The quarter closes Friday.', cast(:rec as jsonb))"),
            {"o": ORG_PG, "rec": json.dumps({"who": "Founder", "what": "Offer Thursday 4 pm",
                                             "by_when": "Wed"})})
    try:
        yield live_db_url
    finally:
        _clean()


@pytest.mark.pg
def test_the_card_read_runs_read_only_on_the_migrated_schema(seeded, tmp_path):
    ideal = _write(tmp_path, "ideal.json", [_ideal()])
    out_json = tmp_path / "gap.json"
    code = gap.main(["--ideal", ideal, "--database-url", seeded, "--org", ORG_PG,
                     "--json", str(out_json)])
    assert code == 0
    card = _card(json.loads(out_json.read_text(encoding="utf-8")), "i1")
    assert card["found"] is True and card["product_card_id"] == "card_s44u1"
    fields = card["fields"]
    assert fields["subject"]["ok"] and fields["why"]["ok"] and fields["recommendation"]["ok"]
    assert fields["how_steps"]["ok"], "the signal's candidate steps are the card row's steps"
    assert fields["draft"]["ok"] is False and fields["goal"]["ok"] is False
