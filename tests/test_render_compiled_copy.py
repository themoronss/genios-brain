"""The compiled brain's cards read as advice, not as stubs.

Eleven of the design partner's eighteen live compiled cards rendered `raw_slot` — a fallback
body, not authored copy — and the four causes were independent. Each is pinned here against the
shape that actually shipped.
"""
import json

from genios_engine.deliver.render import (
    HEADLINE_CAP, SITUATION_CAP, _fit, _prompt, invention_ok, render_copy,
)
from genios_engine.deliver.slots import SENTINELS, compute_slots, grounded_slots


def _llm(headline, situation, artifact):
    class _R:
        ok, model, input_tokens, output_tokens = True, "m", 1, 1
        parsed = {"headline": headline, "situation": situation, "artifact": artifact}

    class _LLM:
        def call(self, prompt, max_tokens=600):
            return _R()
    return _LLM()


# ── 1 · the invention guard and the apostrophe ──────────────────────────────────
def test_a_contraction_is_not_an_invented_company():
    """`_proper_nouns` stripped every non-alphanumeric, so "We've" became "Weve" — a capitalised
    token in no dictionary, hence an invented entity. Eight of the eleven artifact rejections on
    the live cards were exactly this, and each threw away a correct draft."""
    corpus = "acme is in negotiation"
    for contraction in ("We've sent it", "What's blocking this", "They're waiting", "I'll send it"):
        ok, why = invention_ok(contraction, corpus, set())
        assert ok, f"{contraction!r} rejected as {why}"


def test_a_quoted_company_is_still_judged():
    """Stripping the surrounding quote must not consume the word: 'Initech' reduces to Initech,
    which is ungrounded, not to an empty token that skips the check entirely."""
    ok, why = invention_ok("They mentioned 'Initech' as the incumbent", "acme is in negotiation", set())
    assert not ok and why == "name:Initech"


def test_a_possessive_entity_is_still_judged():
    ok, why = invention_ok("Initech's team replied", "acme is in negotiation", set())
    assert not ok and why == "name:Initech"


def test_an_ordinary_capitalised_noun_is_not_an_entity():
    """"Before the call", "Decision needed", "Meeting notes" — prose capitalises the first word
    of every sentence, and all three were rejected as invented companies on live cards."""
    for sentence in ("Before the call, confirm scope.", "Decision needed on scope.",
                     "Meeting notes attached."):
        ok, why = invention_ok(sentence, "acme scope", set())
        assert ok, f"{sentence!r} rejected as {why}"


def test_a_spelled_number_is_still_a_claim():
    """Exempting "Three" while `_digit_runs` still checks "3" would make the guard depend on how
    the model chose to write the same claim."""
    ok, why = invention_ok("Three items are open", "acme is in negotiation", set())
    assert not ok and why == "name:Three"


# ── 2 · sentinel slots never reach the model ────────────────────────────────────
def test_the_prompt_never_states_a_slot_we_could_not_compute():
    """compute_slots fills an absent fact with a sentinel so the DETERMINISTIC template stays
    grammatical. Handing those over as "Key slots" presented them as facts, and all eighteen
    compiled cards came back saying "several open items blocking commitment ... in open stage for
    several days ... No value set" about accounts with no deal in play."""
    slots = {"entity": "acme.com", "who": "acme.com", **{k: v for k, v in SENTINELS.items()
                                                         if k not in ("entity", "who")}}
    prompt = _prompt("opportunity", {"render_hint": "h"}, {"company.domain": {"value": "acme.com"}},
                     slots)
    for sentinel in ("several open items", "no value set", "the commitment"):
        assert sentinel not in prompt
    assert "acme.com" in prompt
    # Stated as unknown rather than merely omitted — otherwise the model reaches for a filler.
    assert "NOT KNOWN" in prompt and "money" in prompt.split("NOT KNOWN")[1].split("\n")[0]


def test_grounded_slots_keeps_only_computed_values():
    slots = dict(SENTINELS, entity="acme.com")
    assert grounded_slots(slots) == {"entity": "acme.com"}


def test_a_sentinel_is_not_grounding_for_the_invention_guard():
    """Leaving sentinels in the corpus would license the model to write "several open items" and
    have the guard agree it was grounded."""
    slots = dict(SENTINELS, entity="Acme")
    out = render_copy(reason_code="opportunity",
                      template={"fallback": {"headline": "{entity}", "situation": "{entity} open"}},
                      facts={"company": {"value": "Acme"}}, slots=slots,
                      llm=_llm("Acme", "Acme has Several open items", "ok"))
    assert json.loads(out["reject_detail"])["situation"].startswith("V-02")


# ── 3 · an over-cap line loses its last sentence, not its meaning ───────────────
def test_an_over_cap_situation_keeps_its_leading_sentence():
    """Ten of eighteen compiled cards came back 142-158 characters against a 140 cap, and the
    rejection swapped a correct, specific sentence for the template's bare `{stage}` slot: the
    literal word "open"."""
    first = "Acme asked for the security review before signing."
    over = first + " " + "x" * (SITUATION_CAP - len(first))
    assert len(over) > SITUATION_CAP
    out = render_copy(reason_code="opportunity",
                      template={"fallback": {"headline": "{entity}", "situation": "{stage}"}},
                      facts={"company": {"value": "Acme"}, "ask": {"value": over}},
                      slots={"entity": "Acme", "stage": "open"},
                      llm=_llm("Acme", over, ""))
    assert out["situation"] == first
    assert out["render_mode"] == "llm"          # nothing was rejected — a sentence was dropped
    assert out["reject_code"] is None
    assert json.loads(out["reject_detail"])["situation"].startswith("V-01-trimmed")


def test_a_single_over_cap_sentence_still_falls_back():
    """No complete sentence fits, so there is nothing honest to keep. Law 3 holds: never truncate."""
    assert _fit("y" * (HEADLINE_CAP + 20), HEADLINE_CAP) is None
    out = render_copy(reason_code="opportunity",
                      template={"fallback": {"headline": "{entity} — fit not assessed",
                                             "situation": "{entity} arrived unassessed."}},
                      facts={"company": {"value": "Acme"}}, slots={"entity": "Acme"},
                      llm=_llm("A" * (HEADLINE_CAP + 20), "Acme arrived unassessed.", ""))
    assert out["headline"] == "Acme — fit not assessed"
    assert out["reject_code"] == "V-01"


def test_fit_never_cuts_a_word():
    kept = _fit("One. Two. Three.", 9)
    assert kept == "One. Two."


# ── 4 · a clause we cannot substantiate is dropped, not worded ──────────────────
def test_an_unknown_slot_drops_its_own_clause():
    out = render_copy(reason_code="opportunity",
                      template={"fallback": {"headline": "{entity} — {money} at stake",
                                             "situation": "{stage}"}},
                      facts={}, slots=dict(SENTINELS, entity="Acme"), llm=None)
    assert out["headline"] == "Acme"
    assert SENTINELS["money"] not in out["headline"]


def test_a_slot_with_no_clause_of_its_own_keeps_its_placeholder():
    """"Deliver {action} to {entity} today" cannot lose `{action}` without shipping "Deliver  to
    acme today". A grammatical placeholder beats a broken sentence, and this line never reaches
    the model either way."""
    out = render_copy(reason_code="commitment_overdue",
                      template={"fallback": {"headline": "Deliver {action} to {entity} today",
                                             "situation": "{entity} is waiting."}},
                      facts={}, slots=dict(SENTINELS, entity="Acme"), llm=None)
    assert out["headline"] == f"Deliver {SENTINELS['action']} to Acme today"


def test_a_fallback_headline_is_never_blank():
    """Cutting clauses can empty a line, and a card still has to name its subject. The floor is
    the entity, not an empty string that reads as a broken card."""
    out = render_copy(reason_code="opportunity",
                      template={"fallback": {"headline": " — ", "situation": "{entity} open."}},
                      facts={}, slots=dict(SENTINELS, entity="Acme"), llm=None)
    assert out["headline"] == "Acme"


def test_compute_slots_uses_the_declared_sentinels():
    from datetime import datetime, timezone
    slots = compute_slots("opportunity", "acme.com", {}, datetime(2026, 8, 26, tzinfo=timezone.utc))
    assert grounded_slots(slots) == {"entity": "acme.com", "who": "acme.com"}


# ── 5 · the compiled brain supplies its own copy ────────────────────────────────
def test_build_draft_prefers_the_capability_copy_over_the_pack(monkeypatch):
    """`effective["templates"]` is keyed by the TENANT PACK's reason codes; a compiled signal's
    reason_code is its situation type, which no pack authors. The lookup returned `{}` for every
    compiled card — an empty render_hint, so the prompt carried no guidance, and an empty
    fallback, so a rejected line shipped as the default `{stage}` slot: the word "open"."""
    from datetime import datetime, timezone
    from genios_engine.deliver import card_builder

    monkeypatch.setattr(card_builder, "load_node",
                        lambda *_a, **_k: ("acme.com", "company", {}, {}))
    monkeypatch.setattr(card_builder, "_real_sources", lambda *_a, **_k: set())
    monkeypatch.setattr(card_builder, "resolve_assignee", lambda *_a, **_k: ("u1", "rule"))

    authored = {"artifact_kind": "draft_reply", "render_hint": "the fit judgment, nothing else",
                "fallback": {"headline": "{entity} — fit not assessed",
                             "situation": "Interest arrived from {entity}."}}
    signal = {"signal_id": "sig_1", "subject_node_id": "n1", "reason_code": "opportunity",
              "level": "observation", "score": 60, "capability_render": authored}
    effective = {"pack_id": "sales", "templates": {"unanswered_email": {"render_hint": "pack"}}}

    draft = card_builder.build_draft(object(), "org_1", signal, effective,
                                     datetime(2026, 8, 26, tzinfo=timezone.utc))
    assert draft["_template"] == authored


def test_build_draft_still_uses_the_pack_for_a_legacy_signal(monkeypatch):
    """A legacy signal carries no `capability_render` and must fall through unchanged — neither
    lane may take the other's copy."""
    from datetime import datetime, timezone
    from genios_engine.deliver import card_builder

    monkeypatch.setattr(card_builder, "load_node",
                        lambda *_a, **_k: ("acme.com", "company", {}, {}))
    monkeypatch.setattr(card_builder, "_real_sources", lambda *_a, **_k: set())
    monkeypatch.setattr(card_builder, "resolve_assignee", lambda *_a, **_k: ("u1", "rule"))

    pack_template = {"render_hint": "pack copy", "fallback": {"headline": "{entity}",
                                                              "situation": "{stage}"}}
    signal = {"signal_id": "sig_2", "subject_node_id": "n1", "reason_code": "unanswered_email",
              "level": "observation", "score": 60}
    effective = {"pack_id": "general", "templates": {"unanswered_email": pack_template}}

    draft = card_builder.build_draft(object(), "org_1", signal, effective,
                                     datetime(2026, 8, 26, tzinfo=timezone.utc))
    assert draft["_template"] == pack_template


def test_the_authored_copy_travels_from_the_situation_to_the_manifest():
    """The seam the live path depends on: a `render:` block on a situation file has to arrive on
    `rcap.manifest->'metadata'->'render'`, which is what delivery reads."""
    from genios_engine.packs.compiler.models import RoutePlan

    plan = RoutePlan(domain_ids=("sales",), situation_ids=("sales.sit.x",),
                     capability_ids=("sales.a.b",), required_object_ids=("sales.obj.core.company",),
                     optional_object_ids=(), never_object_ids=(),
                     render={"artifact_kind": "draft_reply", "render_hint": "h",
                             "fallback": {"headline": "{entity}", "situation": "s"}},
                     render_situation_id="sales.sit.x")
    assert plan.render["artifact_kind"] == "draft_reply"
    assert plan.render_situation_id == "sales.sit.x"


# ── 6 · a headline is clause-joined, not sentence-joined ───────────────────────
#
# Both cases below are from the design partner's live queue on 2026-08-27. Six of twenty-four
# newly built cards were rejected at 61 or 62 characters against a 60 cap and replaced by
# template copy, because `_fit` only knows how to drop a trailing SENTENCE and a headline has
# none — one clause-joined fragment, `re.findall` returns it whole, nothing fits, None.
def test_an_over_cap_headline_drops_its_trailing_clause_instead_of_falling_back():
    from genios_engine.deliver.render import _fit_clauses

    head = "bharatkesuperfounders.com — rejected from the cohort — status still open"
    kept = _fit_clauses(head, HEADLINE_CAP)
    assert kept == "bharatkesuperfounders.com — rejected from the cohort"
    assert len(kept) <= HEADLINE_CAP
    assert not kept.endswith("—")          # no dangling join where a clause was removed


def test_a_fallback_headline_is_never_cut_mid_word():
    """`{entity} — relationship open, nothing moving` with a fifty-character address shipped as
    `invoice+statements+acct_1ika5ja3kz32dpo1@stripe.com — relati` — a hard slice at the cap."""
    from genios_engine.deliver.render import _trim_to_word

    long_address = "invoice+statements+acct_1ika5ja3kz32dpo1@stripe.com"
    out = render_copy(reason_code="relationship",
                      template={"fallback": {
                          "headline": "{entity} — relationship open, nothing moving",
                          "situation": "An active relationship with {entity}."}},
                      facts={}, slots={"entity": long_address}, llm=None)
    assert len(out["headline"]) <= HEADLINE_CAP
    assert not out["headline"].endswith("relati")
    # The address itself has no space to break on, so slicing it is the only option left — but
    # that is the ONLY case where a mid-token cut is allowed.
    assert _trim_to_word("x" * 80, HEADLINE_CAP) == "x" * HEADLINE_CAP


def test_the_copys_own_vocabulary_is_not_read_as_an_invented_company():
    """`The`, `Positive`, `Multiple`, `Fit` and `Presentation` each cost a live card on
    2026-08-27: the guard read a sentence-opening ordinary word as a name nobody mentioned."""
    for word in ("The", "Positive", "Multiple", "Fit", "Presentation", "A", "An"):
        ok, why = invention_ok(f"{word} thread is open with Acme.", "acme", set())
        assert ok, f"{word} was rejected as an invented name ({why})"
    # And the guard still does its job: a company nobody mentioned is still caught.
    ok, why = invention_ok("Initech will vouch for us.", "acme", set())
    assert not ok and why == "name:Initech"


def test_a_hyphenated_word_is_judged_by_its_parts_not_as_one_mashed_token():
    """`AI-guided` was stripped to `AIguided` — a token in no language and therefore in no
    corpus — so the guard called it an invented company and threw the card away. Same failure the
    apostrophe rule already documents, wearing a different punctuation mark."""
    from genios_engine.deliver.render import _proper_nouns

    assert _proper_nouns("An AI-guided review with Acme.") == ["AI", "Acme"]
    assert invention_ok("An AI-guided review.", "we sent an ai note", set()) == (True, None)
    # Splitting on the hyphen must not blunt the guard: a name in either half is still caught.
    assert invention_ok("Follow-up with Initech.", "acme", set()) == (False, "name:Initech")
