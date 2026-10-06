"""Which Atlas mutations the founder set already drives — and, for the rest, why not yet.

`speedrun008/YC-II W27/` STEP-01 §3.7. A replay
mutation is a sentence: "change this input, and the decision must change this way". It becomes a
check on the engine only where a founder case IS that input — then its pass condition is written
below as predicates over the case's run (`engine_runner.run_case`), and the mutation's own
`implemented` flag decides how a failure reads: a blocked mutation is a strict xfail, so the day its
capability lands the check passes, the xfail fails, and the spec must say `possible_today`.

Every other mutation of replays 01–07 is NOT EXPRESSIBLE and is counted apart from *blocked*: the
engine may well fail it, but no case puts that input in front of it yet, and a mutation with no
input is a guess. Each says why; the next case batch takes them from here.

Predicates, all over one case's run:

  card_about / min / max   cards whose text names any of the terms, counted over every sweep
  mentions                 …and each of those cards says these words
  level_in                 …and each of those cards is at one of these levels
  memory                   these objects reached memory — the WITNESS that keeps "no card" from
                           passing on a chain that never reached the stage
  no_phrase                no card carries these phrases
"""
from __future__ import annotations

#: (replay id, mutation index) → the case that drives it and the predicates that are its pass
#: condition.
EXPRESSED: dict[tuple[str, int], dict] = {
    # 01 · m01 — no new material milestone: no action, AND the trigger that would unblock the send
    # is visible. A card that only stays silent satisfies half of it, so the check asks for the
    # visible half too: one wait or observation card about Tara that names the milestone.
    ("01", 1): {"case": "F14", "card_about": ["Tara", "Fjord"], "min": 1, "max": 1,
                "level_in": ["wait", "observation"], "mentions": ["milestone"],
                "memory": ["tara"], "no_phrase": ["last chance", "checking in"],
                "why": "Tara asked for real news only; nothing material happened since"},
    # 02 · m04 — the connector itself makes a bounded ask: its own item.
    ("02", 4): {"case": "F09", "card_about": ["Introly"], "min": 1,
                "why": "the connector asks which stage the founder is raising at"},
    # 03 · m00 — a counterparty proposes a time; the founder accepts or declines.
    ("03", 0): {"case": "F26", "card_about": ["Neha", "Orbitly"], "min": 1, "mentions": ["30 Sep"],
                "no_phrase": ["You promised", "Deliver"],
                "why": "Neha proposed Tuesday 30 Sep, 11 am IST"},
    # 03 · m01 — the founder proposed availability; the ball is theirs.
    ("03", 1): {"case": "F39", "card_about": ["Rohan", "Castlerock"], "max": 0,
                "memory": ["proposal"], "no_phrase": ["You promised", "Deliver"],
                "why": "the founder offered Thursday or Friday; Rohan has not answered"},
    # 03 · m05 — a past meeting nobody confirmed took place: observation or review only.
    ("03", 5): {"case": "F40", "card_about": ["Meera", "Tallgrass", "meera@tallgrass.test"],
                "level_in": ["observation", "review"], "mentions": ["confirm"],
                "memory": ["call"], "no_phrase": ["recap", "happened"],
                "why": "a calendar entry for 13 Aug and nothing after it; the output must say the "
                       "occurrence is unconfirmed"},
    # 04 · m01 — answered on another channel, with an explicit reference: the request closes.
    ("04", 1): {"case": "F38", "card_about": ["Pooja", "Greenleaf"], "max": 0, "memory": ["done"],
                "why": "Pooja thanks the founder for confirming on WhatsApp"},
    # 06 · m04 — "send material updates; I may reconsider": wait for a milestone.
    ("06", 4): {"case": "F14", "card_about": ["Tara", "Fjord"], "max": 0, "memory": ["tara"],
                "no_phrase": ["last chance", "checking in"],
                "why": "a deferred, conditional investor"},
}

_NO_CASE = "no founder case puts this input in front of the engine yet"
#: Why a replay's other mutations cannot be expressed, by what their pass condition talks about.
NOT_EXPRESSIBLE: dict[str, str] = {
    "01": f"{_NO_CASE}: consent labels, update-history conflicts, identity collisions, an "
          "uncovered investor capability made visible, and delivery receipts are not inputs any "
          "case carries",
    "02": f"{_NO_CASE}: three concurrent introductions, a forwarded group intro, a declined "
          "intro, a shared display name and delivery reconciliation are each a case to write",
    "03": f"{_NO_CASE}: acceptance, counter-proposal, cancellation, a disconnected calendar, two "
          "parallel meetings, an ambiguous time zone, a delegate and a provider timeout",
    "04": f"{_NO_CASE}: an in-thread reply, parallel asks, a vague 'done', partial sync, a revoked "
          "completion, an agent reply, a send race and a namesake",
    "05": f"{_NO_CASE}: verified attendance, cancellation, a declined invitee, a transcript, a "
          "promised deck and a confidential segment are not in any case",
    "06": f"{_NO_CASE}: a filled role, a closed-won handoff, a rejection, a Q4 deferral, a reopen, "
          "a job change, a CRM conflict, revoked consent and a corrected rejection",
    "07": "the runner reads cards, not the compiler's route dispositions, stub manifests, "
          "permission traces or package versions these pass conditions name",
}


def expression(replay_id: str, index: int) -> dict | None:
    return EXPRESSED.get((replay_id, index))


def check(spec: dict, run) -> list[str]:
    """The pass condition's failures on one run — empty when it holds."""
    from tests.replays.marking import cards_about, says

    problems: list[str] = []
    about = spec.get("card_about") or []
    matched = cards_about(run, tuple(about)) if about else []
    if "min" in spec and len(matched) < spec["min"]:
        problems.append(f"{len(matched)} card(s) about {about}; at least {spec['min']} expected")
    if "max" in spec and len(matched) > spec["max"]:
        problems.append(f"{len(matched)} card(s) about {about}; at most {spec['max']} allowed")
    for card in matched:
        missing = [t for t in spec.get("mentions") or [] if not says(card.text, t)]
        if missing:
            problems.append(f"card {card.card_id} does not say {missing}")
        levels = spec.get("level_in")
        if levels and card.level not in levels:
            problems.append(f"card {card.card_id} is {card.level!r}, not one of {levels}")
    for oid in spec.get("memory") or []:
        if int(run.memory.get(oid, 0)) == 0:
            problems.append(f"{oid} never reached memory — the check would pass on nothing")
    for card in run.cards:
        for phrase in spec.get("no_phrase") or []:
            if phrase.lower() in card.text.lower():
                problems.append(f"card {card.card_id} says {phrase!r}")
    if run.misses or not all(run.chain_ok):
        problems.append("the run itself failed (cassette miss or a chain crash)")
    return problems
