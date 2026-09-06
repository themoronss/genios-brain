"""L2.7.7-U1 step 1 · THE DETERMINISTIC GATE — the volume control, and the cost control.

Doc 07 states it in three lines and every one of them is a refusal:

    fires ONLY when: situation.status == ACTIVE
                     AND a new signal landed on it this drain
                     AND terminal_by_fact is False        <- a fact beats a statement, ALWAYS
    Otherwise: no call.

Everything this module does is decide NOT to spend a call, and it is written as a cascade of
named refusals rather than one boolean because *"the sweep made 4000 calls"* and *"the sweep made
none"* are both answerable only if the reason each situation was skipped is a value, not a
missing log line.

TWO PLACES WHERE THIS GATE IS WIDER THAN DOC 07'S THREE LINES, both forced by the plan's own
failure modes:

1. **A statement-closed situation is still examined.** Doc 07 failure mode 5 requires *"done"
   then "actually not yet"* to REOPEN, and by the time the second message lands the first one has
   already moved the situation out of ACTIVE. A gate that read `status == ACTIVE` literally would
   make `CONTRADICTED` unreachable in exactly the case it was written for — the wrong close would
   be permanent, which is the opposite of the reversibility doc 12 calls "the structural guard
   behind all nine". So the gate also fires on `resolved`/`partial` rows WE closed from a
   statement. It does NOT fire on a human's resolution (a person's decision is not overturned by
   a sentence) and it does not fire on a fact's (rule 3 above).
2. **A machine or unattributable sender is refused HERE, before the call**, per doc 12 case 7:
   *"service accounts ignored at the gate, before any call."*

BUDGET LIVES HERE TOO, and its exhaustion is a REFUSAL WITH A NAME (`no_budget_situation`,
`no_budget_org`) rather than a silent skip — doc 11: *"budget exhausted -> falls back to
`terminal_by_fact` and LOGS."* The per-situation cap is doc 11's *"M-4 fires per situation per
day: max 3"*; the per-org cap is its *"per-org daily L2 LLM calls: 200"*, counted over THIS
site's own ledger (see `store.py` for why that is a floor on the truth and not the whole of it).

NO CLOCK. Every count is taken against `eval_time`, which the drain reads once at the process
boundary and passes down.
"""
from __future__ import annotations

from dataclasses import dataclass

from genios_engine.context.lifecycle.authority import is_ignored_speaker
from genios_engine.context.situations import (
    RESOLVED_BY_STATEMENT,
    STATUS_ACTIVE,
    STATUS_PARTIALLY_RESOLVED,
    STATUS_RESOLVED,
)

__all__ = ["GateDecision", "MAX_CALLS_PER_ORG_PER_DAY", "MAX_CALLS_PER_SITUATION_PER_DAY",
           "gate_decision"]

#: Doc 11's two ceilings. Named constants because both are tuning knobs whose numbers appear in
#: an operator's report, and a literal buried in a comparison is a number nobody can find.
MAX_CALLS_PER_SITUATION_PER_DAY = 3
MAX_CALLS_PER_ORG_PER_DAY = 200

# The refusal vocabulary. Stored in the sweep record, so a drain that made no calls can say which
# of these it was.
SKIP_TERMINAL_BY_FACT = "terminal_by_fact"
SKIP_STATUS = "status_not_eligible"
SKIP_HUMAN_RESOLVED = "resolved_by_human"
SKIP_NO_NEW_SIGNAL = "no_new_signal"
SKIP_ALREADY_EXAMINED = "already_examined"
SKIP_NO_TEXT = "no_prepared_text"
SKIP_SPEAKER_IGNORED = "speaker_ignored"
SKIP_BUDGET_SITUATION = "no_budget_situation"
SKIP_BUDGET_ORG = "no_budget_org"
FIRES = "fires"


@dataclass(frozen=True, slots=True)
class GateDecision:
    """Whether to spend a model call on this (situation, message), and why not when not."""

    fires: bool
    reason: str

    @property
    def budget_exhausted(self) -> bool:
        return self.reason in (SKIP_BUDGET_SITUATION, SKIP_BUDGET_ORG)


def status_is_eligible(status: str | None, resolved_by: str | None) -> bool:
    """ACTIVE, or a state this unit itself put the situation into.

    A human's resolution and a fact's are both excluded, and they are excluded for DIFFERENT
    reasons that happen to produce the same answer: a fact outranks a statement by rule, and a
    human's decision is not something a sentence in an email gets to overturn — the existing
    lifecycle already reopens a human resolution on new evidence, and it does so without a model.
    """
    if status == STATUS_ACTIVE:
        return True
    return (status in (STATUS_RESOLVED, STATUS_PARTIALLY_RESOLVED)
            and resolved_by == RESOLVED_BY_STATEMENT)


def gate_decision(*, status: str | None, resolved_by: str | None, terminal_by_fact: bool,
                  has_new_signal: bool, already_examined: bool, has_text: bool,
                  speaker_role: str | None, calls_today_for_situation: int,
                  calls_today_for_org: int) -> GateDecision:
    """The whole of step 1, in the order the refusals must be asked.

    ORDER IS LOAD-BEARING. `terminal_by_fact` is first because it is the only rule that must hold
    even when everything else says go — doc 07's *"a fact beats a statement, ALWAYS"* — and
    because a situation whose CRM says closed-won is exactly the situation whose thread is still
    noisy with congratulations. Budget is LAST so that an org over its ceiling reports
    `no_budget_*` for the situations that would really have been called, rather than hiding
    behind refusals that had nothing to do with money.
    """
    if terminal_by_fact:
        return GateDecision(False, SKIP_TERMINAL_BY_FACT)
    if not status_is_eligible(status, resolved_by):
        return GateDecision(False, SKIP_HUMAN_RESOLVED if resolved_by == "human"
                            else SKIP_STATUS)
    if not has_new_signal:
        return GateDecision(False, SKIP_NO_NEW_SIGNAL)
    if already_examined:
        return GateDecision(False, SKIP_ALREADY_EXAMINED)
    if not has_text:
        # No prepared text is not "an empty message": it is a message whose spans could not be
        # verified against anything, so a verdict about it could never carry a receipt.
        return GateDecision(False, SKIP_NO_TEXT)
    if is_ignored_speaker(speaker_role):
        return GateDecision(False, SKIP_SPEAKER_IGNORED)
    if calls_today_for_situation >= MAX_CALLS_PER_SITUATION_PER_DAY:
        return GateDecision(False, SKIP_BUDGET_SITUATION)
    if calls_today_for_org >= MAX_CALLS_PER_ORG_PER_DAY:
        return GateDecision(False, SKIP_BUDGET_ORG)
    return GateDecision(True, FIRES)


def candidate_prior(decision_states: object, subject: str) -> bool:
    """Step 2 · the deterministic CANDIDATE signal — L1 already read this message.

    Doc 07: *"the signal's extraction already carries `decision_states[]` and `commitments[]` from
    L1. If a DecisionState says `state == "made"` for this subject -> strong prior."*

    A prior is exactly that: it is recorded on the call and it NEVER substitutes for the verdict.
    A `made` decision about "pricing" does not mean the renewal is finished, and a resolution
    with no prior is not rejected for lacking one — L1's extractor is not asked about resolution,
    so its silence is not evidence of absence. What the prior earns is a place in the prompt and
    a column in the ledger: when M-4's precision is measured later, "did L1 already think a
    decision had been made here" is the first thing worth cutting the numbers by.
    """
    needle = " ".join(str(subject or "").lower().split())
    if not needle:
        return False
    for entry in decision_states or []:                      # type: ignore[union-attr]
        if not isinstance(entry, dict):
            continue
        if str(entry.get("state") or "").strip().lower() != "made":
            continue
        said = " ".join(str(entry.get("subject") or "").lower().split())
        if said and (said in needle or needle in said):
            return True
    return False
