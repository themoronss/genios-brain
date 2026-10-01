r"""L5 · the validator, asked per claim instead of per paragraph.

⛔ FIRST, THE CORRECTION. `tree.yaml`'s `M13.C1.U02` reads *"widens the invention validator"*, and
the cross-check very nearly recorded that the validator did not exist. It does:
`deliver/render.py:334` `invention_ok(text, corpus_text, corpus_nums)`, called at `render.py:861`,
re-exported by `executive/validate.py:69`, covered by `tests/test_delivery.py`. The wrong conclusion
came from grepping `reminder_facts` — the name its own docstring uses — finding three files and no
validator among them. It is a generic function taking `corpus_text`, so its subject's name appears
nowhere near it. **A conclusion drawn from one name's absence**, which is the same mistake as
`no_model_wired` in L1 and the graph-revision guard in L3.

⛔ WIDENING IS NOT LOOSENING, AND THIS IS THE WHOLE DISCIPLINE OF THE FILE. `invention_ok` is
CALLED, not reimplemented, and it is called FIRST. Whatever it refuses, this refuses, with its
reason unchanged. Every existing `invention_ok` test must still pass untouched — that is the proof,
and it is why the old function is a dependency rather than a starting point.

WHAT IS ADDED, and each is a refusal the paragraph-level check could not express:

  1. An ungrounded token inside any claim is refused, in the same vocabulary `invention_ok` uses
     (`number:12`, `name:Acme`), so one reader understands both. This is the rule that fires.

  ⛔ AND TWO THAT CANNOT FIRE TODAY, SAID PLAINLY RATHER THAN LEFT TO BE DISCOVERED:

  2. AN `OBSERVED` CLAIM THAT CITES NOTHING IS NOT OBSERVED. "Lifted from a source" is the
     strongest thing a card can say and the easiest to say falsely — `claim_state._MODEL_MAY_WRITE`
     refuses `OBSERVED` to a model for exactly that reason.

  3. A `HYPOTHESISED` CLAIM MUST BE MARKED IN ITS OWN WORDING. `claim_state` requires a hypothesis
     be *"never rendered as fact"*, and the only thing that stops a sentence reading as fact is the
     sentence itself.

  Both are **unreachable through `claims_ok` as it stands**, because `claims.classify` establishes
  each one at the moment it tags: it will not write `OBSERVED` without the same `quotes_something`
  this function checks, and it writes `HYPOTHESISED` only on a hedge it found in the text. They are
  INVARIANT GUARDS over that classifier, not live refusals, and the tests drive them directly.

  ⛔ SAYING SO IS THE POINT. This programme has found "built, tested, green, and called by nothing"
  eight times, and an unreachable branch nobody labelled is how the ninth would start — somebody
  reads a passing test, believes a refusal is protecting production, and relaxes something upstream.
  The branch earns its place by being the thing that fails the day a classifier starts tagging from
  a field instead of from the sentence, which is a change somebody will one day want to make.

⛔ TOTALITY GUARD, BOTH DIRECTIONS. Every `ClaimState` must have a rule, and every rule must name a
real state. A state with no rule passes silently forever, which is how a vocabulary grows a member
nothing checks.

PURE. No I/O, no clock, no model.
"""
from __future__ import annotations

from dataclasses import dataclass

from genios_engine.contracts.claim_state import CLAIM_STATES, ClaimState
from genios_engine.deliver.claims import Claim, extract
from genios_engine.deliver.render import invention_ok


@dataclass(frozen=True, slots=True)
class ClaimRefusal:
    """One claim, refused, and on what. The sentence travels with the reason so a reject_detail
    names what a reader can actually go and look at."""

    sentence: str
    state: str
    reason: str

    def __str__(self) -> str:
        return f"{self.state}:{self.reason}"


def _observed_is_cited(claim: Claim, *, quotes_something: bool) -> str | None:
    if claim.state is ClaimState.OBSERVED and not quotes_something:
        return ("claims_to_be_observed_but_the_card_quotes_nothing")
    return None


def _hypothesis_is_marked(claim: Claim, **_: object) -> str | None:
    if claim.state is ClaimState.HYPOTHESISED and "hedged on" not in claim.reason:
        return "hypothesis_not_marked_in_its_own_wording"
    return None


def _nothing_is_invented(claim: Claim, **_: object) -> str | None:
    if claim.ungrounded:
        return claim.ungrounded[0]
    return None


#: Per state, the rules that apply. ⛔ `ENVELOPE` maps to an EMPTY tuple deliberately, and that is
#: not the same as being absent: an instruction asserts nothing, so it has nothing to ground — and
#: writing the empty tuple down is what stops the totality guard below from reading "not a claim"
#: as "nobody wrote a rule". The same reason `claim_state` keeps a not-a-claim member in the enum.
_RULES: dict[ClaimState, tuple] = {
    ClaimState.OBSERVED: (_observed_is_cited, _nothing_is_invented),
    ClaimState.INFERRED: (_nothing_is_invented,),
    ClaimState.HYPOTHESISED: (_hypothesis_is_marked, _nothing_is_invented),
    ClaimState.ENVELOPE: (),
}

# ⛔ AGAINST `ClaimState`, NOT `CLAIM_STATES` — AND THE IMPORT-TIME GUARD IS WHAT FOUND THE
# DIFFERENCE. `CLAIM_STATES` is *"the three that are actually claims. `ENVELOPE` is deliberately
# not one of them"*, so checking against it refused the `ENVELOPE` rule as a rule for something
# that is not a claim state — which is true and is not the question. This module validates every
# SENTENCE, and a sentence that is an instruction is one of the four things a sentence can be.
# Guarding against the narrower set would have left `ENVELOPE` sentences with no declared rule at
# all, passing silently forever, which is the failure the guard exists to catch.
_missing = set(ClaimState) - set(_RULES)
if _missing:                                                      # pragma: no cover - import guard
    raise RuntimeError(f"claim states with no validation rule: {sorted(m.value for m in _missing)}")
_unknown = set(_RULES) - set(ClaimState)
if _unknown:                                                      # pragma: no cover - import guard
    raise RuntimeError(f"validation rules for things that are not claim states: {_unknown}")
# ⛔ And the three that ARE claims must each carry at least one rule. `ENVELOPE` is the only state
# allowed an empty tuple, because an instruction has nothing to ground; letting any other state
# reach that state would be a claim nothing checks.
_toothless = {s.value for s in CLAIM_STATES if not _RULES[s]}
if _toothless:                                                    # pragma: no cover - import guard
    raise RuntimeError(f"claim states with no actual check: {sorted(_toothless)}")
del _missing, _unknown


def claims_ok(text: str, corpus_text: str, corpus_nums: set[str], *,
              quotes_something: bool = False
              ) -> tuple[bool, str | None, tuple[ClaimRefusal, ...]]:
    """`(ok, reject_detail, refusals)`. The old contract in the first two, the new detail in the third.

    ⛔ `invention_ok` RUNS FIRST AND ITS VERDICT IS FINAL. A caller swapping `invention_ok` for
    `claims_ok` can only ever see MORE refusals, never fewer — which is what makes this a widening
    rather than a rewrite, and what lets the old function's tests stand as the proof.
    """
    ok, detail = invention_ok(text, corpus_text, corpus_nums)
    if not ok:
        # The same reason string, unchanged. A widened validator that renames the old refusals
        # breaks every reader of `cards.reject_detail` and every count built on one.
        return False, detail, (ClaimRefusal(text, "whole_card", detail or "invention"),)

    refusals: list[ClaimRefusal] = []
    for claim in extract(text, corpus_text=corpus_text, corpus_nums=corpus_nums,
                         quotes_something=quotes_something):
        for rule in _RULES[claim.state]:
            reason = rule(claim, quotes_something=quotes_something)
            if reason:
                refusals.append(ClaimRefusal(claim.text, claim.state.value, reason))
                break
    if refusals:
        return False, str(refusals[0]), tuple(refusals)
    return True, None, ()


def observed_claims(text: str, corpus_text: str, corpus_nums: set[str], *,
                    quotes_something: bool = False) -> tuple[Claim, ...]:
    """The sentences this card presents as lifted from a source. The set a reviewer should read."""
    return tuple(c for c in extract(text, corpus_text=corpus_text, corpus_nums=corpus_nums,
                                    quotes_something=quotes_something)
                 if c.state is ClaimState.OBSERVED)


__all__ = ["ClaimRefusal", "claims_ok", "observed_claims"]
