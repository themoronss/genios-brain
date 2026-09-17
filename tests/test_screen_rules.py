"""Router check 5 — what a rule answers so the model is never asked.

The bar is PRECISION: a rule fires only where it is plainly right. Everything softer belongs to
the model, and a test that widens a rule to catch one more case has to justify the false
positives it buys — a wrong item costs the manager's trust, a missed one costs one model call.
"""

from __future__ import annotations

from genios_engine.reason.moments import screen_rules as R

KAL = [{"text": "kal tak", "resolved": "2026-09-18", "time": "17:00"}]


def kinds(items):
    return [(i["kind"], i["who"], i["due"]) for i in items]


def test_the_shape_the_device_actually_sends_is_read():
    # "Priya Shah: …" strings, not {sender, text} dicts. Handling only the dict is why the
    # structural "was this said by someone?" check never fired outside tests.
    ls = R.lines(["Priya Shah: kal tak revised quote bhej dena",
                  "You: haan bhej deta hoon",
                  "Join meeting",                       # no sender — screen furniture
                  {"sender": "Rahul", "text": "PO raise kar dunga"},
                  {"sender": "You", "text": "ok"}])
    assert [(l.who, l.outgoing) for l in ls] == [
        ("Priya Shah", False), (None, True), ("Rahul", False), (None, True)]
    assert R.said(["Priya Shah: Can you send it?"]) == ["can you send it"]


def test_a_plain_hinglish_ask_needs_no_model():
    items = R.extract(["Priya Shah: kal tak revised quote bhej dena"], dates=KAL,
                      tz_name="Asia/Kolkata")
    assert kinds(items) == [("ask", "Priya Shah", "2026-09-18T17:00")]
    assert items[0]["quote"] == "kal tak revised quote bhej dena"
    assert items[0]["text"] == items[0]["quote"], "the quote IS the item — no paraphrase"
    assert items[0]["source"] == "rule"


def test_the_manager_s_own_promise_and_the_other_side_s_are_two_different_things():
    items = R.extract(["Priya Shah: MSA ka signed copy bhi chahiye",
                       "You: kal tak bhej deta hoon",
                       "Priya Shah: main bhi numbers bhej dungi"], dates=KAL, tz_name="Asia/Kolkata")
    got = {(k, w) for k, w, _ in kinds(items)}
    assert ("ask", "Priya Shah") in got
    assert ("my_promise", None) in got, "the manager's own promise names nobody as who"
    assert ("their_promise", "Priya Shah") in got
    # the due lands only on the line that carried the phrase
    due = {k: d for k, _, d in kinds(items)}
    assert due["my_promise"] == "2026-09-18T17:00" and due["ask"] is None


def test_english_asks_and_commitments():
    assert kinds(R.extract(["Rahul Mehta: could you please send the proposal"]))[0][:2] == ("ask", "Rahul Mehta")
    assert kinds(R.extract(["Rahul Mehta: any update on the MSA?"]))[0][:2] == ("ask", "Rahul Mehta")
    assert kinds(R.extract(["Rahul Mehta: we are waiting on the invoice"]))[0][:2] == ("ask", "Rahul Mehta")
    assert kinds(R.extract(["You: I'll send the deck tonight"]))[0][:2] == ("my_promise", None)
    assert kinds(R.extract(["Neha: will revert by EOD"]))[0][:2] == ("their_promise", "Neha")


def test_what_a_rule_refuses_to_guess():
    # Softer than a rule can be trusted with — this is what the model is for.
    for line in ["Priya Shah: jo pending hai wo bhej dena raat tak",   # object unknown
                 "Priya Shah: thanks, got it",
                 "Priya Shah: the pricing page has two doubts",
                 "Neha: deck?"]:
        got = R.extract([line])
        assert all(i["kind"] != "their_promise" for i in got), line
    # …and outright furniture is never an item
    for junk in ["Join meeting", "3 unread", "Priya Shah: typing", "Open"]:
        assert R.extract([junk]) == [], junk


def test_the_managers_own_question_is_not_an_item():
    # GeniOS owes the manager a reminder for what THEY promised, not for what they asked.
    assert R.extract(["You: kab tak milega?"]) == []
    assert R.extract(["You: can you please send the MSA"]) == []


def test_one_item_per_person_per_kind_newest_wording_wins():
    items = R.extract(["Priya Shah: quote bhej dena",
                       "Priya Shah: quote ka kya hua, still waiting"])
    assert len(items) == 1 and items[0]["quote"] == "quote ka kya hua, still waiting"
    assert len(R.extract(["A: send it please", "B: send it please", "C: send it please",
                          "D: send it please"])) == R.MAX_ITEMS


def test_an_ask_the_manager_already_answered_on_this_screen():
    screen = ["Priya Shah: kal tak revised quote bhej dena",
              "You: bhej diya, inbox check karo"]
    assert R.answered_after(screen, "kal tak revised quote bhej dena")
    assert not R.answered_after(screen, "bhej diya, inbox check karo")
    assert not R.answered_after(["Priya Shah: quote bhej dena"], "quote bhej dena")


def test_the_model_is_skipped_only_when_someone_has_judged_the_thread():
    items = R.extract(["Priya Shah: quote bhej dena"])
    assert R.enough(items, verdict_known=True)
    assert not R.enough(items, verdict_known=False), "work-vs-personal is never a rule's call"
    assert not R.enough([], verdict_known=True)


def test_a_long_line_is_quoted_short():
    long = "Priya Shah: " + " ".join(f"word{i}" for i in range(40)) + " bhej dena"
    q = R.extract([long])[0]["quote"]
    assert len(q.split()) == R.QUOTE_WORDS
