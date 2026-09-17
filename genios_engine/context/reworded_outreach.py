"""L2.3 · one outreach, typed five different ways — M-3's answer, on a card.

`correlation_conversation` groups outbound mail by the EXACT sentence and refuses anything softer.
`campaign_candidates` publishes what that refusal left behind, with the distinctive words the sends
have in common. `same_situation_two_threads` adjudicates each one. This is where a `one_campaign`
verdict becomes something a founder sees, and until now the chain ended one step short: the queue
was built, the question asked, the answer stored, and nobody told.

IT IS NOT A CAMPAIGN AND THE CARD NEVER SAYS IT IS. `find_campaigns` mints a `Campaign`, and it
still requires the exact sentence to match — that is unchanged, and the angle still writes nothing
to the graph. What this mints is a different, narrower claim: these sends share distinctive wording
this tenant does not use everywhere, they went out inside one window to enough people, and a model
reading the sentences judged them one message reworded. `outreach.exact_sentence` is declared
ABSENT, because its absence is the entire reason the deterministic grouping did not fire.

`same_topic_not_one_message` MINTS NOTHING, and that is the verdict this tenant will see most. Five
introductions answered personally in one morning share the raise vocabulary and reach the queue
every time; they are five relationships, not one outreach, and each already has its own card. Only
`one_campaign` produces a group.

IT YIELDS TO THE GROUP CARDS THAT ALREADY EXIST. `read_campaign_silence` sets the rule next door —
"one group of people gets one group card" — and computes coverage from the cohort reading's own
`inputs["members"]`. This does the same against BOTH, because a founder shown "your raise outreach"
and "one outreach, reworded" about the same eight people has been told one thing twice.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

#: ONE SPELLING OF WHAT A GROUP IS, imported rather than restated. `find_candidates` already
#: refuses a near-miss below this, and `correlation_conversation` calls it "the smallest number
#: where 'how is this OUTREACH going' is a different question from 'what about this person'" —
#: kept identical on purpose so the two readings cannot disagree about what a group is. Repeated
#: here because this function is also driven directly by a test, and a floor that lives only in
#: the producer is a floor a caller can walk past.
from genios_engine.context.correlation_conversation import MIN_RECIPIENTS

#: The one verdict that becomes a card. See the module docstring.
ONE_CAMPAIGN = "one_campaign"

#: Its own anchor. The second group-shaped subject in this layer after `cohort`, and it groups on
#: a different thing again: `cohort` groups by stated OBJECTIVE, `campaign` by an exact SENTENCE,
#: and this by wording a model judged to be one message.
ANCHOR_REWORDED = "reworded_outreach"

#: How many of a candidate's recipients are named on the card. The rest are counted, never hidden:
#: `outreach.recipients` is the true number and the list is a sample, the same split
#: `read_outreach_cohorts` keeps between `cohort.contacted` and the names it prints.
MAX_NAMED = 6

#: How many of these one sweep may produce. `campaign_candidates.MAX_CANDIDATES` already caps the
#: queue at forty; this is the smaller ceiling on how many become cards.
MAX_PER_SWEEP = 8


def _at(value: Any) -> datetime | None:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return value if isinstance(value, datetime) else None


def _window_hours(candidate: Mapping[str, Any]) -> int | None:
    first, last = _at(candidate.get("first_sent")), _at(candidate.get("last_sent"))
    if first is None or last is None:
        return None
    return max(0, int((last - first).total_seconds() // 3600))


def read_reworded_outreach(candidates: Sequence[Mapping[str, Any]], now: datetime,
                           names: Mapping[str, str] | None = None,
                           covered: frozenset[str] | set[str] = frozenset()) -> list:
    """One finding per near-miss a model called one message.

    `covered` is the set of node ids some other GROUP reading already speaks about. A candidate
    every one of whose recipients is covered yields entirely — not partially, because a group card
    about the leftovers of another group card is a third description of the same morning.
    """
    from genios_engine.context.outreach_situations import _Finding

    findings: list = []
    for candidate in list(candidates)[:MAX_PER_SWEEP]:
        if str(candidate.get("verdict") or "") != ONE_CAMPAIGN:
            continue
        recipients = [str(r) for r in (candidate.get("recipients") or ()) if str(r).strip()]
        if len(recipients) < MIN_RECIPIENTS:
            continue
        if covered and all(node in covered for node in recipients):
            continue

        candidate_id = str(candidate.get("candidate_id") or "").strip()
        if not candidate_id:
            continue
        shared = [str(w) for w in (candidate.get("shared_tokens") or ())]
        sentences = [str(s) for s in (candidate.get("sentences") or ())]
        sends = int(candidate.get("sends") or len(recipients))

        facts: list[tuple[str, object, str]] = [
            ("outreach.sends", sends, "number"),
            ("outreach.recipients", len(recipients), "number"),
            # THE EVIDENCE, AND THE REASON THE CARD CAN BE ARGUED WITH. A stored similarity score
            # is undebuggable — `correlation_conversation` refuses one by name. These are the
            # actual words every member has in common, so a reader agrees or dismisses in one
            # second, which is also what was shown to the model.
            ("outreach.shared_words", ", ".join(shared[:8]), "string"),
            # The model's word, carried as what it is. Never a number, and never a rank.
            ("outreach.reading", ONE_CAMPAIGN, "enum"),
        ]
        if sentences:
            facts.append(("outreach.distinct_wordings", len(sentences), "number"))
        hours = _window_hours(candidate)
        if hours is not None:
            facts.append(("outreach.window_hours", hours, "number"))
        named = [str((names or {}).get(node) or "").strip() for node in sorted(recipients)]
        named = [n for n in named if n][:MAX_NAMED]
        if named:
            facts.append(("outreach.named", ", ".join(named), "string"))

        headline = (f"one outreach, reworded {len(sentences)} ways to {len(recipients)} people"
                    if sentences else
                    f"one outreach to {len(recipients)} people, in different wordings")
        findings.append(_Finding(
            anchor=ANCHOR_REWORDED,
            canonical_key=f"reworded:{candidate_id}",
            display_name=headline,
            facts=facts,
            # A REPRESENTATIVE, not the scope — the same split `read_outreach_cohorts` records.
            # `outreach.recipients` is what this is really about.
            concerns_node=sorted(recipients)[0],
            correlation_id=f"reworded:{candidate_id}",
            evidence_nodes=tuple(sorted(recipients)),
            # DECLARED, AND THE FIRST ONE IS THE POINT. There is no shared sentence — that absence
            # is exactly why `find_campaigns` did not group these, so a card implying a campaign in
            # its sense would be claiming the receipt it does not have. Who replied is not in the
            # candidate either: it carries what was SENT.
            missing=["outreach.exact_sentence", "outreach.replied"],
            inputs={"reading": ANCHOR_REWORDED,
                    # WHO THIS COVERS, so a later group-shaped reading can yield to it exactly as
                    # this one yields to the cohort and campaign readings.
                    "members": sorted(recipients),
                    "derived_from": "campaign_candidates near-miss, adjudicated `one_campaign` by "
                                    "same_situation_two_threads; no exact shared sentence"},
        ))
    return findings


__all__ = ["ANCHOR_REWORDED", "MAX_NAMED", "MAX_PER_SWEEP", "ONE_CAMPAIGN",
           "read_reworded_outreach"]
