"""L2-8 · the cutover, enumerated — and it is not three flips, it is seven.

⛔ **THE PLAN SAYS THREE, AND SAYS WHY THAT MATTERS:** *"any one alone leaves the system in a state
that looks working and is not."* It was written before L2-0…L2-7 ran, and **four of those steps
each left a switch behind deliberately** — declared, evidenced, and not armed until somebody had
the number.

**Nothing enumerated them.** Four switches in four findings files is four switches somebody
rediscovers one at a time: the *"prose stale, code right"* drift this repository has caught five
times, and the same gap L2-6 found when three completed steps had deferred work onto L2-5 with
nothing collecting it.

⛔ **AND THE PARITY GATE IS A NUMBER WRITTEN DOWN BEFORE THE RUN.** The shadow pass has been
counting for months and **nobody has read its tallies.** The moment somebody does, a threshold
chosen afterwards is a threshold chosen to pass. `PARITY_MEASURED_AT` stays `None` until the
numbers are read, and a test asserts that the gate predates them.

This module holds no logic that runs on a sweep. It is data plus two pure functions, checked at
import — the same idiom as `SITUATION_STAGES`, `DARK_DOMAINS`, `ADMISSION_REASONS` and `CHECKS`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Switch:
    """One thing that must be flipped for Layer 2 to be live, and what it costs alone."""

    owner: str
    flips: str
    #: ⛔ What must be TRUE first. A switch with no stated precondition is one somebody flips
    #: because it seemed fine on the day.
    precondition: str
    #: What breaks if this one is flipped and the others are not.
    alone: str
    #: Whether it is on TODAY. A test reads the code and refuses a row that disagrees, so a flip
    #: that forgets to update this table fails the build rather than happening quietly.
    armed: bool = False


SWITCHES: dict[str, Switch] = {
    # --- the three `shadow_compile`'s own contract names -----------------------------------------
    "publisher": Switch(
        owner="the L3 plan, pre-dating L2",
        flips="`shadow_compile(live=True)` with a real publisher, per tenant via "
              "`l3_activation.activated_domains` — never `use_domain_compiler`, which is one "
              "boolean for every tenant at once",
        precondition="the parity gate below, read from a real shadow run (Harsh 29)",
        alone="`expertise_packages` is never written, so every compile is measurement and the "
              "cards keep coming from the legacy lane"),
    "require_admission": Switch(
        owner="the L3 plan",
        flips="`require_admission=True` on the live compiler (it is already True at "
              "`domain_shadow.py:857`; measurement mode relaxes it at :847)",
        precondition="⛔ **NONE — L2-0 measured it free.** 155 of 155 authored capabilities are "
                     "admissible, every content hash recomputed and verified. The plan budgeted "
                     "for 334 going dark; that number counted FILES",
        alone="unreviewed doctrine could carry authority on a live card, which is the one thing "
              "the admission ceremony exists to prevent"),
    "execution_mode": Switch(
        owner="the L3 plan",
        flips="`ExecutionMode.LIVE` and an emitted `signals` row (`domain_shadow.py:1138`, "
              "already conditional on `live_row`)",
        precondition="`publisher` and `require_admission` first — publishing before admission is "
                     "enforced is the ordering failure",
        alone="delivery cannot build a card at all, and the card cannot say which brain authored "
              "it"),

    # --- the four L2-0…L2-7 each left, deliberately ----------------------------------------------
    "fundraising_route": Switch(
        owner="L2-4",
        flips="`_L2_TO_L3_DOMAIN['fundraising'] = 'sales'` — one line, reversible",
        precondition="the pilot's fundraising situation count (Harsh 26). Arming it makes every "
                     "fundraising situation activatable at once",
        alone="⛔ **Nothing breaks, and that is why it is easy to forget.** The doctrine exists — "
              "`sales.sit.live_investor_relationship`, stable and approved — and the pilot's "
              "dominant domain simply keeps not reaching it"),
    "observing_laws": Switch(
        owner="L2-2",
        flips="`LAW_ACTIONS[L2Law.V9]` and `[V10]` from `OBSERVE` to `REJECT` — one line each",
        precondition="the `BY LAW` block of the refusal report (Harsh 24): how many live "
                     "situations arming them would refuse",
        alone="nothing breaks; interpretations that cite nothing keep publishing, and the report "
              "keeps counting them"),
    "cards_from_situations": Switch(
        owner="L2-7",
        flips="an `l4_activations` row for `cards_from_situations`, per tenant",
        precondition="migration 0182, then the collapse ratio (Harsh 27) — the headline number of "
                     "the whole plan, and one nothing has ever printed",
        alone="the founder keeps seeing one card per SIGNAL: three rules on one situation stay "
              "three cards that can never merge"),
    "situation_reasoner": Switch(
        owner="L2-5",
        flips="an `l4_activations` row for `situation_reasoner`, per tenant",
        precondition="migration 0183. ~$15.64/month at Haiku on the measured shape (Harsh 28)",
        alone="Layer 2 never interprets anything; the sweep runs exactly as it does today"),
}

#: ⛔ ORDER MATTERS, AND ONE ALONE IS THE FAILURE. Admission before publication, publication before
#: the emitted row; the four later switches each stand on their own measurement and may be armed
#: in any order after the first three.
CUTOVER_ORDER: tuple[str, ...] = (
    "require_admission", "publisher", "execution_mode",
    "fundraising_route", "observing_laws", "cards_from_situations", "situation_reasoner",
)


def is_armed(name: str) -> bool:
    """Read the CODE, not the table. A flip that forgets to update `SWITCHES` fails the build."""
    if name == "require_admission":
        # Already True on the live path; measurement mode relaxes it deliberately. "Armed" here
        # means the LIVE lane is reachable, which is `publisher`'s question, not this one.
        return False
    if name == "fundraising_route":
        from genios_engine.reason.domain_shadow import _L2_TO_L3_DOMAIN

        return _L2_TO_L3_DOMAIN.get("fundraising") is not None
    if name == "observing_laws":
        from genios_engine.contracts.situation import LAW_ACTIONS, L2Law, LawAction

        return any(LAW_ACTIONS[law] is LawAction.REJECT for law in (L2Law.V9, L2Law.V10))
    if name in ("publisher", "execution_mode"):
        from genios_engine.platform.config import get_settings

        try:
            return bool(get_settings().use_domain_compiler)
        except Exception:      # noqa: BLE001 — no settings means no global flag, which is off
            return False
    # The two activation-row switches are per tenant and have no global state to read: a row is
    # the only truth, and this table describes the DEFAULT, which is off.
    return False


@dataclass(frozen=True, slots=True)
class ParityRule:
    """One number the shadow pass must show before `live=True` is earned."""

    reading: str
    threshold: int
    #: `at_most` or `at_least`.
    direction: str
    why: str


#: ⛔ **FIXED BEFORE THE RUN.** Every reading is a key `shadow_compile` already writes — a gate
#: that reads a tally nothing emits passes forever, which is L2-0's defect pointed at the cutover.
PARITY_GATE: dict[str, ParityRule] = {
    "no_unroutable_errors": ParityRule(
        reading="error", threshold=0, direction="at_most",
        why="a per-situation exception on the shadow lane becomes a lost card on the live one. "
            "Zero, because the pass already catches per situation and counts — a non-zero here "
            "is a bug that is being tolerated rather than a situation that is hard"),
    "nothing_fails_to_persist": ParityRule(
        reading="persist_error", threshold=0, direction="at_most",
        why="the live lane's whole difference from shadow is that it writes. A pass that cannot "
            "write in shadow will not learn to in live"),
    "most_situations_compile": ParityRule(
        reading="compiled", threshold=100, direction="at_least",
        why="the pilot carries 159 active situations (`l1_refusal`). Below 100 compiled, the "
            "corpus is not reaching the majority of them and turning the lane on would publish "
            "a minority view of the tenant"),
    "reasoning_reaches_the_same_rows": ParityRule(
        reading="reasoned", threshold=100, direction="at_least",
        why="compiled-but-not-reasoned is a package nobody read. The two numbers moving together "
            "is what makes 'it works' mean something"),
    "no_reading_crashed": ParityRule(
        reading="reasoner_failed", threshold=0, direction="at_most",
        why="L2-5's consult cannot kill the compile by design, so a non-zero here is silent and "
            "would stay silent — the exact shape L2-0 spent a step ending"),
}

#: ⛔ Stays `None` until somebody reads the shadow tallies. A test asserts it, so the gate above is
#: provably older than the numbers it judges.
PARITY_MEASURED_AT: str | None = None


@dataclass(frozen=True, slots=True)
class ParityVerdict:
    passed: bool
    failures: tuple[str, ...]


def evaluate_parity(counts) -> ParityVerdict:
    """The gate, against one sweep's tallies. Pure — no clock, no I/O.

    ⛔ **AN ABSENT TALLY FAILS.** *"`None` is not a low number — it is nobody having measured."* A
    missing key must not read as a clean run, which is how a gate comes to pass on a pass that
    never happened.
    """
    failures: list[str] = []
    for name, rule in PARITY_GATE.items():
        if rule.reading not in (counts or {}):
            failures.append(f"{name}: `{rule.reading}` was not measured")
            continue
        value = int((counts or {})[rule.reading])
        ok = value <= rule.threshold if rule.direction == "at_most" else value >= rule.threshold
        if not ok:
            failures.append(f"{name}: `{rule.reading}` is {value}, needs "
                            f"{rule.direction.replace('_', ' ')} {rule.threshold}")
    return ParityVerdict(passed=not failures, failures=tuple(failures))


def _check() -> None:
    assert set(CUTOVER_ORDER) == set(SWITCHES), "a switch with no place in the order"
    for name, switch in SWITCHES.items():
        for field in ("owner", "flips", "precondition", "alone"):
            assert getattr(switch, field), f"{name}: {field} is empty"
    for name, rule in PARITY_GATE.items():
        assert rule.direction in ("at_most", "at_least"), f"{name}: unknown direction"
        assert isinstance(rule.threshold, int) and not isinstance(rule.threshold, bool)
        assert rule.reading and rule.why, f"{name}: a number with no reason"


_check()

__all__ = ["CUTOVER_ORDER", "PARITY_GATE", "PARITY_MEASURED_AT", "SWITCHES", "ParityRule",
           "ParityVerdict", "Switch", "evaluate_parity", "is_armed"]
