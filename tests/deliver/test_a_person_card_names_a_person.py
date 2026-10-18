r"""A person card names a person, and a company card does not get renamed after one of its people.

⛔ WHAT WAS WRONG. `deliver/card_builder.resolved_person_name` carries its own measurement:

    "35 of 38 person cards named an address in the headline. The real name was already extracted —
     a `mention:person` observation carries {"name": "Maria Exconde"} — but the node's display_name
     stayed the address, so the headline spent its 60-character budget on
     'maria@alystventures.com'."

Somebody measured 38 cards, found 35 broken, wrote the resolver, and **nothing ever called it.**
Zero references anywhere in the repo, including tests — one of only four public functions in
`deliver/` with no caller at all.

⛔ THE DOCSTRING ALSO MADE A CLAIM THAT HAD STOPPED BEING TRUE: *"and the invention guard rejected
any draft that wrote 'Maria'."* `render._corpus` appends `q["name"]` for every quote it is handed,
so the name is grounded and `invention_ok` accepts it. The grounding half of the defect was closed
when the corpus was widened; only the headline half was still open. **A stale sentence inside the
docstring of the function this step is about** — and the reason
`test_the_resolved_name_passes_the_invention_validator` asserts it instead of repeating it.

⛔ AND THE PLAN SAID "WIRE IT", WHICH WOULD HAVE BEEN WRONG TWICE OVER. Measured first:

  * `name` in `build_draft` has exactly two assignments and three uses, so the subject chain is a
    single choke point — one edit covers the headline subject AND `compute_slots`.
  * ⛔ That chain already has a precedence: `outreach.counterparty` and `commitment.owed_to` are
    FACTS about who the reading concerns, and a `mention:person` name is an observation. The
    resolver must go LAST, replacing only the `or name` fallback.
  * ⛔ Without a `node_type == "person"` gate, a COMPANY card would be renamed after one of its
    people — `card_builder`'s own comment says a company node's quotes are "observations of the
    people who works_at it", because "the card names the company, and these are its people."
"""
from __future__ import annotations

import ast
import inspect
from datetime import datetime, timezone

import pytest

from genios_engine.deliver import card_builder
from genios_engine.deliver import delivery_health as H
from genios_engine.deliver.card_builder import resolved_person_name
from genios_engine.deliver.render import _corpus, invention_ok

EVAL = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

#: A person node is keyed on an email address — which is the whole defect.
ADDRESS = "maria@alystventures.com"
#: The name the extractor already had, one join away, on a `mention:person` observation.
REAL_NAME = "Maria Exconde"

PERSON_QUOTE = {"kind": "mention:person", "name": REAL_NAME,
                "quote": "can you send pricing before Friday?", "author": ADDRESS,
                "from_counterparty": True}

TEMPLATE = {
    "artifact_kind": "draft_reply",
    "render_hint": "name the person who wrote and what they asked",
    "fallback": {"headline": "{who} is owed a reply",
                 "situation": "They wrote {days} days ago and no reply has gone back."},
}


@pytest.fixture()
def draft(monkeypatch):
    """`build_draft` with the graph reads stubbed — the harness
    `tests/test_a_card_must_quote_what_was_said.py` already established."""
    monkeypatch.setattr(card_builder, "_real_sources", lambda *_a, **_k: set())
    monkeypatch.setattr(card_builder, "resolve_assignee", lambda *_a, **_k: ("u1", "rule"))
    monkeypatch.setattr(card_builder, "_group_memberships", lambda *_a, **_k: {})
    monkeypatch.setattr(card_builder, "co_recipients_for", lambda *_a, **_k: ())

    def _build(*, node=(ADDRESS, "person", {}, {}), quotes=(PERSON_QUOTE,)):
        monkeypatch.setattr(card_builder, "load_node", lambda *_a, **_k: node)
        signal = {"signal_id": "sig_1", "subject_node_id": "n1",
                  "reason_code": "first_response_overdue", "level": "prescriptive",
                  "score": 70, "capability_render": TEMPLATE}
        return card_builder.build_draft(object(), "org_1", signal,
                                        {"pack_id": "sales"}, EVAL, quotes=list(quotes))
    return _build


# ---------------------------------------------------------------------------------------------
# 1 · the defect, closed
# ---------------------------------------------------------------------------------------------

def test_a_mention_person_observation_supplies_the_subject(draft) -> None:
    """⛔ THE POINT. The name was always one join away; nothing read it."""
    card = draft()
    assert card["business_subject"] == REAL_NAME
    assert ADDRESS not in card["business_subject"]


def test_a_person_card_with_no_observation_keeps_the_address(draft) -> None:
    """⛔ NULL IS AN ANSWER. No `mention:person` observation → the address stands. A card must never
    invent a name, which is the failure the whole invention validator exists to prevent."""
    card = draft(quotes=())
    assert card["business_subject"] == ADDRESS


def test_a_quote_that_is_not_a_person_mention_supplies_nothing(draft) -> None:
    """A question or a company mention carries no person name, and must not be mined for one."""
    other = {"kind": "question", "quote": "what is the price?", "author": ADDRESS,
             "from_counterparty": True}
    assert draft(quotes=(other,))["business_subject"] == ADDRESS


def test_a_person_mention_with_an_empty_name_is_not_a_name(draft) -> None:
    """`q.get("name")` must be truthy, not merely present — an empty string is the address's
    problem restated, and `""` would blank the subject entirely."""
    blank = {**PERSON_QUOTE, "name": ""}
    assert draft(quotes=(blank,))["business_subject"] == ADDRESS


# ---------------------------------------------------------------------------------------------
# 2 · ⛔ the gate, which is the half the plan did not have
# ---------------------------------------------------------------------------------------------

def test_a_company_card_is_not_renamed_after_one_of_its_people(draft) -> None:
    """⛔ THE RISK THAT MADE THIS MORE THAN A ONE-LINE WIRING.

    `card_builder`'s own comment on the quote loader: a company node gets *"observations of the
    people who `works_at` it. Broader by nature, and honest at that width: **the card names the
    company, and these are its people.**"* So the quotes on a company card are other people's
    words, and resolving a name there renames the card after whichever of them spoke first.
    """
    card = draft(node=("alystventures.com", "company", {}, {}))
    assert card["business_subject"] == "alystventures.com"


def test_a_thread_card_is_not_renamed_either(draft) -> None:
    """A thread node's subject is a conversation. Its quotes are from that exact thread, so one of
    them naming a person says nothing about what the card is about."""
    card = draft(node=("Re: pricing", "thread", {}, {}))
    assert card["business_subject"] == "Re: pricing"


def test_a_counterparty_fact_still_wins_over_an_observation(draft) -> None:
    """⛔ THE PRECEDENCE, ASSERTED. `outreach.counterparty` is a FACT the extractor wrote about who
    the reading concerns; a `mention:person` name is an observation. The chain existed before this
    step for a reason its own comment gives — a synthetic anchor's display_name is not the card's
    subject — and putting the resolver ahead of it would have broken that."""
    facts = {"outreach.counterparty": {"value": "Nitesh Pant"}}
    card = draft(node=("Investor A — awaiting reply", "person", {}, facts))
    assert card["business_subject"] == "Nitesh Pant"


# ---------------------------------------------------------------------------------------------
# 3 · ⛔ the validator — asserted, never predicted
# ---------------------------------------------------------------------------------------------

def test_the_resolved_name_passes_the_invention_validator() -> None:
    """⛔ THE CLAIM THE DOCSTRING GOT WRONG, MEASURED INSTEAD OF REPEATED.

    `resolved_person_name` said the invention guard *"rejected any draft that wrote Maria"*. It does
    not: `_corpus` appends `q["name"]` for every quote, so the name is grounded for exactly the
    reason the quote is — it came off the source event, not from the model.

    ⛔ **And the rule if this ever fails is absolute: the fix is wrong, not the validator.** Never
    weaken a verify to make it pass.
    """
    corpus, nums = _corpus({}, {}, (), [PERSON_QUOTE])
    ok, why = invention_ok(f"{REAL_NAME} asked about pricing", corpus, nums)
    assert ok, f"a grounded, extractor-supplied name was refused as invented: {why}"

    # and the address stays legal too, because a card with no observation still has to render
    ok_addr, _ = invention_ok(f"{ADDRESS} asked about pricing", corpus, nums)
    assert ok_addr


def test_the_validator_still_refuses_a_name_nobody_said() -> None:
    """⛔ A validator that accepts the resolved name because it accepts everything is no validator.
    This is the counterweight to the test above."""
    corpus, nums = _corpus({}, {}, (), [PERSON_QUOTE])
    ok, why = invention_ok("Nikhil Sharma asked about pricing", corpus, nums)
    assert not ok and why, "an ungrounded name passed the invention guard"


# ---------------------------------------------------------------------------------------------
# 4 · ⛔ the mutation shapes this programme has already paid for
# ---------------------------------------------------------------------------------------------

def test_the_resolver_actually_REACHES_the_subject_chain() -> None:
    """⛔ In L4, removing an era bound turned a production number from 3,582 to 0 while 15 tests
    passed, because one test proved the boundary was IMPORTED and nothing proved it was USED.

    Read from the AST, with the docstring excluded BY IDENTITY (the first statement) rather than by
    value — `ast.get_docstring()` returns cleaned text while the node holds raw.
    """
    tree = ast.parse(inspect.getsource(card_builder.build_draft).lstrip())
    body = tree.body[0].body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    called = {n.func.id for stmt in body for n in ast.walk(stmt)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "resolved_person_name" in called, "build_draft never calls the resolver"

    # and it must be gated — an ungated call is the company-card defect
    compared = {ast.unparse(n.left) for stmt in body for n in ast.walk(stmt)
                if isinstance(n, ast.Compare)}
    assert any("node_type" in c for c in compared), (
        "the resolver is called without a node_type gate -- a company card would be renamed after "
        "whichever of its people spoke first")


def test_the_fallback_is_the_real_address_and_not_a_placeholder() -> None:
    """⛔ `5000` is a forbidden neutral default in `reason/`; the same rule applies to a name. A
    substituted placeholder would read as a measurement — *this person has no name on record* —
    when what is true is that no observation carried one."""
    assert resolved_person_name([], ADDRESS) == ADDRESS
    assert resolved_person_name([], "") == ""
    for placeholder in ("Unknown", "unknown", "n/a", "this account", "someone"):
        assert resolved_person_name([], ADDRESS) != placeholder


def test_the_first_person_mention_wins_and_the_order_is_the_loaders() -> None:
    """Two people mentioned: the resolver takes the first, and `load_evidence_quotes` emits newest
    first. ⛔ Pinned so a change to the loader's ordering is a deliberate change here too, rather
    than a silent change to whose name a card carries."""
    second = {**PERSON_QUOTE, "name": "Nitesh Pant"}
    assert resolved_person_name([PERSON_QUOTE, second], ADDRESS) == REAL_NAME
    assert resolved_person_name([second, PERSON_QUOTE], ADDRESS) == "Nitesh Pant"


# ---------------------------------------------------------------------------------------------
# 5 · the declaration, both directions
# ---------------------------------------------------------------------------------------------

def test_the_declaration_no_longer_claims_it_is_unwired() -> None:
    """L4 deleted `monitor.blocking_action` from `UNREACHED` the moment it was wired; the entry left
    behind is the lie, not the call."""
    assert "card_builder.resolved_person_name" not in H.KNOWN_UNWIRED
    assert "card_builder.resolved_person_name" not in H.DECLARED
    assert H.now_called() == (), f"a declared entry has acquired a caller: {H.now_called()}"
    assert H.undeclared() == (), f"something became unreached: {H.undeclared()}"


def test_every_remaining_defect_names_the_step_that_closes_it() -> None:
    """⛔ THIS TEST ASSERTED A MEMBERSHIP LIST AND BROKE ONE STEP LATER — THE THIRD TIME, AND I HAD
    WRITTEN THE RULE AGAINST IT IN THIS VERY STEP.

    It read `set(H.KNOWN_UNWIRED) == {"outbox.revive_undeliverable"}`. `STEP-15` then wired that
    function and correctly deleted the entry, so the table went empty and this failed on correct
    code. ⛔ **And `STEP-08` is where I diagnosed exactly this pattern** — rewriting
    `test_the_defects_are_not_filed_as_decisions` as an invariant and writing down *"a membership
    list shrinks every time the work succeeds; an invariant does not"* — and then wrote a new
    membership list a few sections later.

    **The rule was right and I did not generalise it.** What the old assertion actually carried was
    a LOG of where the table had got to, and a log belongs in a document. What is durable:

      * however many entries there are, each names the step that closes it
      * each one is genuinely unreached, checked from the other side by `undeclared()`
      * ⛔ an EMPTY table is a legitimate state — it means `deliver/` has no known-unwired defects
        left, which is the outcome the whole sequence was for
    """
    import re
    for name, (what, step) in H.KNOWN_UNWIRED.items():
        assert re.fullmatch(r"STEP-\d{2}", step), f"{name} has no closing step: {step!r}"
        assert len(what) > 80, f"{name}'s entry explains nothing"
        assert name in H.package_functions(), f"{name} does not exist"
    assert H.undeclared() == (), (
        f"a function left KNOWN_UNWIRED without acquiring a caller: {H.undeclared()}")
