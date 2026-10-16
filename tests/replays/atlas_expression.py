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

STEP-14 (`yc2_w27_s14` M43.C6.L-integration.V2.U08, s14-D5) — replay 02 is about several contacts at once, which one
`card_about` cannot say:

  each                     term groups, one per contact: exactly one card the app showed about each, and no card
                           about two of them — the Atlas's target precision
  open_at_end              …and each of those cards is still open after the last sweep: none closed by another's reply
  versioned                the card about these terms has two versions or more — it moved on, never a second card
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
    # 02 · STEP-14 (`yc2_w27_s14` M43.C6.L-integration.V2.U08, s14-D5): the connector's introductions, one file each.
    # m00 — three introductions in three threads: three distinct files, a decision each naming one contact.
    ("02", 0): {"case": "F59", "each": [["Tara", "Quillstone"], ["Malhotra", "Ferncrest"], ["Anaya", "Harborline"]],
                "memory": ["tara", "dev", "anaya"], "no_phrase": ["Reply to Introly", "write to Introly"],
                "why": "Introly introduced Tara, Dev and Anaya in three threads; each replied with an ask of their own"},
    # m01 — the three in ONE forwarded thread: split per contact, never the whole body as one ask.
    ("02", 1): {"case": "F60", "each": [["Kiran", "Pinewood"], ["Rhea", "Saltmarsh"], ["Vikram", "Brightwell"]],
                "memory": ["forward"], "no_phrase": ["three introductions", "Reply to Introly"],
                "why": "one Introly mail copies Kiran, Rhea and Vikram, each with an ask in the one body"},
    # m02 — one contact replied, two silent: the replied one moves on, the two stand, none closed.
    ("02", 2): {"case": "F61", "each": [["Sana", "Driftwood"], ["Omkar", "Redfern"], ["Tanvi", "Copperleaf"]],
                "open_at_end": True, "versioned": ["Sana", "Driftwood"], "memory": ["sana"],
                "why": "Sana proposed Wednesday at 2 pm; Omkar and Tanvi stayed silent"},
    # m03 — one contact's call booked, another's time proposed: no cross-contact calendar fact on a card.
    ("02", 3): {"case": "F62", "card_about": ["Ira", "Lanternfish"], "min": 1, "max": 1, "mentions": ["Tuesday"],
                "memory": ["farhan", "ira"], "no_phrase": ["14 August", "4 pm"],
                "why": "Farhan booked Thursday 14 August himself; Ira only proposed Tuesday 12 August"},
    # 02 · m04 — the connector itself makes a bounded ask: its own item.
    ("02", 4): {"case": "F09", "card_about": ["Introly"], "min": 1,
                "why": "the connector asks which stage the founder is raising at"},
    # m05 — the introduced address is missing: one discriminating question, no action, never a guessed address.
    ("02", 5): {"case": "F63", "card_about": ["Ishaan", "Corvane"], "min": 1, "max": 1, "level_in": ["review"],
                "mentions": ["address"], "memory": ["intro"], "no_phrase": ["ishaan@", "Reply to Introly"],
                "why": "the introduction names Ishaan and Corvane and carries no address of his"},
    # m07 — a declined introduction: stopped, and the connector's later nudge reopens nothing; its history kept.
    ("02", 7): {"case": "F64", "card_about": ["Zara", "Northlake"], "max": 0, "memory": ["decline", "nudge"],
                "no_phrase": ["last chance", "checking in"],
                "why": "Zara declined the day of the introduction; Introly asked a week later whether you connected"},
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
    # STEP-14 (s14-D5): m00, m01, m02, m03, m05 and m07 are driven by F59–F64 (above); three stay declared.
    "02": f"{_NO_CASE}: m06, one display name for two anchored people — identity's first claim still wins an "
          "alias (the replay's own blocked_on), and no step of YC-II W27 plans the candidate set; m08, a "
          "connector thread's private facts kept from another contact's file — seat-private items reach no "
          "file's card yet (STEP-15 shows them in the brief, s14-D6) and no per-fact use scope is planned; m09, "
          "a direct send with an unknown provider result — no card action reaches the execution subsystem, so "
          "there is no attempt to reconcile (no step owns it yet)",
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
    groups = [tuple(g) for g in spec.get("each") or ()]
    last = len(run.chain_ok) - 1
    for group in groups:
        shown = cards_about(run, group, shown=True)
        if len(shown) != 1:
            problems.append(f"{len(shown)} card(s) about {'/'.join(group)} the app showed; exactly 1 expected")
        if spec.get("open_at_end"):
            problems += [f"card {c.card_id} about {'/'.join(group)} is not open after the last sweep"
                         for c in shown if last not in c.sweeps]
    for card in run.cards:
        named = [g for g in groups if any(says(card.text, t) for t in g)]
        if len(named) > 1:
            problems.append(f"card {card.card_id} names more than one contact: "
                            + ", ".join("/".join(g) for g in named))
    versioned = tuple(spec.get("versioned") or ())
    if versioned:
        moved = cards_about(run, versioned)
        if not moved:
            problems.append(f"no card about {'/'.join(versioned)} to have moved on")
        problems += [f"card {c.card_id} about {'/'.join(versioned)} has {len(c.versions)} version(s); "
                     "it moved on, so two or more" for c in moved if len(c.versions) < 2]
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
