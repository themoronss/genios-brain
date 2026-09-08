"""Layer 4 · R-3 and R-4 — narrating a decision that is already fixed.

Both sites in this module run AFTER `DecisionMaker.decide()` has committed. Neither is given a
candidate to choose between, a score to weigh or a rule to apply: R-3 is handed the elimination that
already happened and asked to say it in English, and R-4 is handed two computed numbers and asked to
frame them in one sentence. That is Law 2 as a module boundary — there is no input here from which a
decision could be changed, because the decision is an input.

**R-3 · WHY OPTION B LOST.** The elimination chain already carries the rule id and the byte-identical
statement (Layer 3's J1 weld proved that). The job is to narrate what is there and *nothing that is
not*: a rejection reason the chain did not record is a reason the model may not invent, and
:func:`_parse_alternatives` enforces it — every quoted span must be byte-identical to a statement we
supplied, and prose that names none of the recorded options is refused rather than shown.

**R-4 · WHAT CHANGES IF WE ACT.** `do_nothing_cost_bp` is computed by `core.cost` and composed by
`decision_maker.do_nothing_record`; foresight's close probability is arithmetic over the tenant's own
history. The model is given those integers as PLACEHOLDER NAMES and never as digits, so the sentence
it writes cannot contain a number it made up — doc 05's mechanism, applied one field earlier than the
bundle. What comes back is `expected_effect` plus a `numbers_used` mapping the bundle can carry
straight into `ReasoningBundle`, which is why R-4 "runs with R-2" without either site importing the
other.

**THE FIVE STANDING GUARDS, PER SITE.** Decision fixed first (both take a decided outcome as input) ·
every claim evidence-bound (R-3's options and R-4's numbers are the only material either prompt sees)
· numbers templated, never generated (V-4 is checked here, before the bundle sees the text) ·
deterministic template fallback (:func:`template_alternatives`, :func:`template_expected_effect`) ·
cached on the decision hash (the seed both sites pass to the gate).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from genios_engine.contracts.reasoning import (
    BUNDLE_FIELD_CAPS,
    TEMPLATE_FALLBACK,
    CandidateDisposition,
    CheckOutcome,
    bare_numbers,
    placeholders,
)
from genios_engine.reason.llm_sites import (
    SITE_R3,
    SITE_R4,
    SiteReceipt,
    SiteRejection,
    run_site,
    with_correction,
)

#: V-7's caps, borrowed from the bundle contract rather than re-declared. R-3 fills
#: `alternatives_narrative` and R-4 fills `expected_effect`, so a cap that disagreed with the
#: bundle's would produce prose the bundle constructor then refused — a rejection discovered one
#: layer too late.
ALTERNATIVES_CAP = BUNDLE_FIELD_CAPS["alternatives_narrative"]
EFFECT_CAP = BUNDLE_FIELD_CAPS["expected_effect"]

#: Anything the model wrote inside double quotes. A quotation is a claim of byte-identity, and doc
#: 05's V-2 is exactly that check — reused here so an invented citation is caught at the site that
#: produced it rather than at the bundle that carried it.
_QUOTED = re.compile(r"[\"“]([^\"”]{4,})[\"”]")

#: The numbers R-4 may reference. A closed vocabulary because `numbers_used` keys are placeholders a
#: card substitutes into: a name nobody computed is an unresolvable placeholder (V-5), and a name
#: that resolves to something we did not measure is worse.
EFFECT_NUMBERS = ("do_nothing_cost_bp", "days_to_horizon", "close_probability_bp",
                  "play_win_rate_bp")

#: R-3's one number: how far the winner outscored the strongest option that lost.
ALTERNATIVES_NUMBERS = ("utility_gap_bp",)

#: The last-resort fallback, for the case where even the template carries a digit — a play id with a
#: number in it ("plan_b2"). True, bundle-constructible, and it points at the structured record
#: rather than pretending the detail does not exist.
GENERIC_ALTERNATIVES = ("Other options were considered and eliminated; the reasons are recorded "
                        "beside this card.")


def digit_free(text: Any, fallback: str) -> str:
    """`text` when it carries no digit, `fallback` otherwise.

    THE RULE THIS SERVES IS NOT COSMETIC. `ReasoningBundle` refuses ANY digit outside a placeholder
    in any prose field (V-4, constructor-level), and both of these sites fill a bundle field. So a
    stored string that carries a number — a headline reading "Renewal · 84,000", a rule id like
    ADM-014, a manifest sentence quoting basis points — cannot travel into prose at all, however true
    it is: it would produce a narration the bundle constructor then refuses, i.e. a card with no
    narrative rather than a card with a plain one.

    Identifiers and numbers reach the customer through STRUCTURE instead — `alternatives_rejected`
    carries the rule id, `numbers_used` carries the integers — which is also the only shape in which
    they are checkable.
    """
    body = str(text or "").strip()
    return body if body and not bare_numbers(body) else fallback


@dataclass(frozen=True, slots=True)
class NarrativeResult:
    """One narrated field: the text with placeholders intact, the numbers, and the receipt."""

    text: str
    numbers_used: Mapping[str, int]
    generation: str
    receipt: SiteReceipt

    @property
    def fell_back(self) -> bool:
        return self.generation == TEMPLATE_FALLBACK

    @property
    def rendered(self) -> str:
        """The customer-facing string: every placeholder replaced by its computed value.

        The same substitution `ReasoningBundle.render` performs, and it is code doing it in both
        places — there is no path by which a model's digits reach a card.
        """
        out = self.text
        for name, value in self.numbers_used.items():
            out = out.replace("{" + name + "}", str(value))
        return out


# =================================================================================================
# R-3 · the alternatives
# =================================================================================================

@dataclass(frozen=True, slots=True)
class RejectedOption:
    """One candidate that lost, as the elimination chain recorded it.

    Every field is READ, never derived: `reason_code` and `rule_id` come off the check that
    eliminated the candidate, and `statement` is the authored claim quoted byte-identically by
    Layer 3's compiler. A blank `statement` means the chain recorded no citation for this rejection,
    and the narration then has nothing to quote — which is the correct outcome, not a gap to fill.
    """

    play_id: str
    disposition: str
    utility_bp: int | None = None
    reason_code: str = ""
    rule_id: str = ""
    statement: str = ""

    def label(self) -> str:
        return self.play_id.replace("_", " ")

    def as_record(self) -> dict[str, Any]:
        return {"play_id": self.play_id, "disposition": self.disposition,
                "utility_bp": self.utility_bp, "reason_code": self.reason_code,
                "rule_id": self.rule_id, "statement": self.statement}


def rejected_options(decision: Any, *, constraints: Sequence[Mapping[str, Any]] = ()
                     ) -> tuple[RejectedOption, ...]:
    """The elimination chain of one `ReasoningDecision`, in the shape R-3 narrates.

    `constraints` is the decision's own `constraints_applied` — Layer 3's compiled corpus rules, each
    naming the candidates it eliminated and carrying the authored statement. Joining them here is what
    lets "why not the discount play?" be answered with the rule that blocked it, in the words the
    corpus actually uses.

    THE JOIN IS ON `candidate_id`, NOT ON `play_id`. `eliminated_candidate_ids` holds candidate ids —
    `rule_compiler` maps its blocked plays through `eliminated_by_play` before writing them, and the
    contract then re-checks that every named id IS eliminated on this decision. Joining on the play id
    would silently match nothing, which is a rule id that quietly stops reaching a card while every
    test that supplies play ids goes on passing.
    """
    by_candidate: dict[str, Mapping[str, Any]] = {}
    for record in constraints or ():
        statement = str(record.get("statement") or "")
        rule_id = str(record.get("rule_id") or "")
        for candidate_id in record.get("eliminated_candidate_ids") or ():
            by_candidate.setdefault(str(candidate_id),
                                    {"rule_id": rule_id, "statement": statement})

    selected_id = getattr(decision, "selected_candidate_id", None)
    out: list[RejectedOption] = []
    for candidate in getattr(decision, "candidates", ()) or ():
        if candidate.candidate_id == selected_id:
            continue
        reason_code = ""
        for check in getattr(candidate, "checks", ()) or ():
            # ELIMINATE and nothing else. `CheckOutcome` has exactly four members and only one of
            # them removes a candidate; a WARN annotates and an ADJUST rescores, and reporting
            # either as the reason an option "lost" would put a sentence on a card that the chain
            # does not support.
            if getattr(check.outcome, "value", check.outcome) == CheckOutcome.ELIMINATE.value:
                reason_code = check.reason_code
                break
        joined = by_candidate.get(str(candidate.candidate_id), {})
        disposition = getattr(candidate.disposition, "value", candidate.disposition)
        out.append(RejectedOption(
            play_id=candidate.play_id, disposition=str(disposition),
            utility_bp=int(candidate.utility_bp),
            reason_code=reason_code or ("eliminated" if str(disposition) ==
                                        CandidateDisposition.ELIMINATED.value else "outranked"),
            rule_id=str(joined.get("rule_id") or ""),
            statement=str(joined.get("statement") or "")))
    # Eliminated first, then by how close they came. The order is what the narration reads as
    # "the strongest alternative", so it must not depend on candidate ordering inside the decision.
    out.sort(key=lambda option: (option.disposition != CandidateDisposition.ELIMINATED.value,
                                 -(option.utility_bp or 0), option.play_id))
    return tuple(out)


def rejected_options_from_card(payload: Any) -> tuple[RejectedOption, ...]:
    """The same shape, read off a STORED card's `rejected_candidates` receipt.

    The card path is the one a human opens on demand, hours after the run whose in-memory decision is
    long gone. Reading the stored receipt rather than re-running the decision is what makes R-3
    answerable at expand time — and it is also why the narration can never disagree with the card: it
    is narrating the card's own row.
    """
    rows = payload if isinstance(payload, (list, tuple)) else ()
    out: list[RejectedOption] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        play_id = str(row.get("play_id") or "").strip()
        if not play_id:
            continue
        utility = row.get("utility_bp")
        # `eliminated_by` is what the COMPILED lane stores (`domain_shadow._rejected_candidates`):
        # the authored doctrine that removed this candidate, rule id and byte-identical statement
        # together, already proven against the corpus before the row was written. The flat
        # `rule_id`/`statement` keys are read too, for a row written by any other producer.
        eliminated_by = row.get("eliminated_by")
        first = eliminated_by[0] if isinstance(eliminated_by, (list, tuple)) and eliminated_by \
            and isinstance(eliminated_by[0], Mapping) else {}
        out.append(RejectedOption(
            play_id=play_id,
            disposition=str(row.get("disposition") or "eliminated"),
            utility_bp=(int(utility) if isinstance(utility, int)
                        and not isinstance(utility, bool) else None),
            reason_code=str(row.get("reason_code") or ("blocking_rule" if first else "")),
            rule_id=str(row.get("rule_id") or first.get("rule_id") or ""),
            statement=str(row.get("statement") or first.get("statement") or "")))
    out.sort(key=lambda option: (option.disposition != CandidateDisposition.ELIMINATED.value,
                                 -(option.utility_bp or 0), option.play_id))
    return tuple(out)


def alternatives_numbers(options: Sequence[RejectedOption],
                         selected_utility_bp: int | None) -> dict[str, int]:
    """R-3's computed numbers. Empty when the gap is not measurable, never zero.

    Zero would say "the winner and the runner-up scored the same", which is a finding. An absent
    number says "we did not measure it", which is the truth when a candidate carries no utility.
    """
    if selected_utility_bp is None:
        return {}
    scored = [option.utility_bp for option in options if option.utility_bp is not None]
    if not scored:
        return {}
    return {"utility_gap_bp": int(selected_utility_bp) - max(scored)}


def template_alternatives(options: Sequence[RejectedOption],
                          numbers: Mapping[str, int]) -> str:
    """The deterministic fallback — plainer, never less true, and labelled by its `generation`.

    Doc 05 §6's shape: what was eliminated, and by what. A rule id is quoted when the chain recorded
    one and omitted when it did not, because a sentence that implies a citation nobody stored is the
    exact failure the narration guard exists to prevent.
    """
    if not options:
        return ""
    parts: list[str] = []
    for option in options[:3]:
        # The rule ID is deliberately NOT in the sentence — see `digit_free`. It is on the record
        # this narration is returned beside, where a reader can check it rather than read it.
        if option.rule_id:
            parts.append(f"{option.label()} (blocked by a corpus rule)")
        elif option.reason_code:
            parts.append(f"{option.label()} ({option.reason_code.replace('_', ' ')})")
        else:
            parts.append(option.label())
    text = "Alternatives eliminated: " + "; ".join(parts) + "."
    if "utility_gap_bp" in numbers:
        text += (" The chosen action outranked the closest alternative by {utility_gap_bp} "
                 "basis points.")
    return digit_free(text, GENERIC_ALTERNATIVES)[:ALTERNATIVES_CAP]


def _alternatives_prompt(options: Sequence[RejectedOption], numbers: Mapping[str, int]) -> str:
    lines = []
    for option in options:
        row = f"- {option.label()}: {option.disposition}"
        if option.reason_code:
            row += f", recorded reason `{option.reason_code}`"
        if option.rule_id:
            row += f", eliminated by rule {option.rule_id}"
        if option.statement and not bare_numbers(option.statement):
            # Only a DIGIT-FREE statement is offered for quotation. A statement carrying a number
            # cannot be quoted into a bundle field at all (V-4), so offering it would be inviting a
            # generation the validator must then refuse.
            row += f'\n    the rule says, verbatim: "{option.statement}"'
        lines.append(row)
    number_lines = "\n".join(f"  {{{name}}} = the {name.replace('_', ' ')}" for name in numbers)
    return (
        "A decision has ALREADY been made. Explain, to the person who has to act on it, why the "
        "other options were not chosen. You are not re-evaluating anything.\n\n"
        "THE OPTIONS THAT LOST, and the reason each one lost, exactly as recorded:\n"
        + "\n".join(lines) + "\n\n"
        + ("PLACEHOLDERS you may use. Write the placeholder, never a digit:\n" + number_lines + "\n\n"
           if number_lines else "NUMBERS: none are available. Do not write any digit.\n\n")
        + "RULES:\n"
        "- Give no reason that is not in the list above. If a reason is not recorded, do not "
        "supply one.\n"
        "- You may quote a rule's words only if you copy them EXACTLY as given, inside double "
        "quotes. Quote only from the wordings offered above.\n"
        "- Never write a digit. Use a placeholder from the list, or no number at all.\n"
        f"- At most {ALTERNATIVES_CAP // 6} words, two or three sentences.\n\n"
        'Answer with JSON and nothing else: {"alternatives_narrative": "<your text>"}')


def _validate_prose(text: str, *, cap: int, numbers: Mapping[str, int],
                    statements: Sequence[str], require_number: bool) -> tuple[str, dict[str, int]]:
    """The shared gauntlet subset these two sites can run alone, in doc 05's order.

    V-4 (no bare numbers), V-5 (every placeholder resolves), V-2 (a quotation is byte-identical) and
    V-7 (length and shape) are all answerable from the generation plus the material we handed the
    model — so they run HERE, at the site, where a rejection costs one retry. V-1's per-claim
    grounding and V-6's scope check need the situation and stay with the bundle's own gauntlet.

    Returns the accepted text and the numbers it actually REFERENCED, which is the symmetry the
    bundle constructor requires: a number computed and never shown is either a missing sentence or a
    stale substitution, and a bundle carrying one is refused.
    """
    body = str(text or "").strip()
    if not body:
        raise SiteRejection("empty_generation")
    if len(body) > cap:
        raise SiteRejection("over_length", f"{len(body)}>{cap}")
    bare = bare_numbers(body)
    if bare:
        raise SiteRejection("bare_number", ",".join(bare)[:80])
    used = placeholders(body)
    unresolved = [name for name in used if name not in numbers]
    if unresolved:
        raise SiteRejection("unresolved_placeholder", ",".join(unresolved)[:80])
    residue = re.sub(r"\{[a-z][a-z0-9_]{0,63}\}", "", body)
    if "{" in residue or "}" in residue:
        raise SiteRejection("malformed_placeholder")
    for quote in _QUOTED.findall(body):
        if not any(quote.strip() in statement for statement in statements if statement):
            raise SiteRejection("unverifiable_quotation", quote[:80])
    if require_number and not used:
        raise SiteRejection("no_number_referenced")
    return body, {name: int(numbers[name]) for name in used}


def narrate_alternatives(*, org_id: str, decision_hash: str,
                         options: Sequence[RejectedOption],
                         selected_utility_bp: int | None = None,
                         gate: Any = None, cache: Any = None,
                         subject_ref: str | None = None) -> NarrativeResult:
    """R-3 · why the options that lost, lost. On card expand or on demand.

    The precondition is a recorded elimination: with no rejected option there is no alternative to
    narrate, and a site that ran anyway would be inventing the comparison the card claims to be the
    outcome of.
    """
    numbers = alternatives_numbers(options, selected_utility_bp)
    statements = [option.statement for option in options
                  if option.statement and not bare_numbers(option.statement)]

    def _parse(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        body, used = _validate_prose(
            str(payload.get("alternatives_narrative") or ""), cap=ALTERNATIVES_CAP,
            numbers=numbers, statements=statements, require_number=False)
        labels = {option.label().lower() for option in options}
        labels |= {option.play_id.lower() for option in options}
        if not any(label and label in body.lower() for label in labels):
            raise SiteRejection("names_no_recorded_option")
        return {"text": body, "numbers_used": used}

    def _fallback() -> Mapping[str, Any]:
        text = template_alternatives(options, numbers)
        used = {name: int(numbers[name]) for name in placeholders(text)}
        return {"text": text, "numbers_used": used}

    result = run_site(
        site=SITE_R3, org_id=org_id,
        seed={"decision_hash": str(decision_hash),
              "options": [option.as_record() for option in options],
              "numbers": dict(numbers)},
        precondition=bool(options),
        build_prompt=lambda feedback: with_correction(
            _alternatives_prompt(options, numbers), feedback), parse=_parse,
        fallback=_fallback, gate=gate, cache=cache, subject_ref=subject_ref)
    return NarrativeResult(text=str(result.payload.get("text") or ""),
                           numbers_used=dict(result.payload.get("numbers_used") or {}),
                           generation=result.generation, receipt=result.receipt)


# =================================================================================================
# R-4 · the expected effect
# =================================================================================================

@dataclass(frozen=True, slots=True)
class EffectInputs:
    """Everything R-4 is allowed to know: two computed numbers and two optional base rates.

    `do_nothing` is `decision_maker.do_nothing_record`'s output verbatim — `{cost_bp, horizon,
    statement, source}` — and `source` is load-bearing: `manifest_fallback` means no unit measured an
    inaction cost, so the framing must not imply one was computed. That is why
    :func:`effect_numbers` reads `cost_bp` only when the source is `computed`.
    """

    do_nothing: Mapping[str, Any] = field(default_factory=dict)
    #: Foresight's Wilson-bounded close probability for this deal, in basis points, when the tenant
    #: has enough closed history for one. None is an honest answer and produces no placeholder.
    close_probability_bp: int | None = None
    #: The play's own earned success rate, same discipline.
    play_win_rate_bp: int | None = None
    #: Whole days to the nearest material date, from the same `horizon` the decision carries.
    horizon_days: int | None = None
    action_label: str = "the recommended action"

    @property
    def computed(self) -> bool:
        return str(self.do_nothing.get("source") or "") == "computed"

    @property
    def safe_action_label(self) -> str:
        """The label as it may appear in prose. A card headline routinely carries a number
        ("Renewal · 84,000 · 11 days out"), and a number in prose is a number the bundle refuses —
        so a headline with digits is replaced rather than repaired."""
        return digit_free(self.action_label, "the recommended action")


def effect_numbers(inputs: EffectInputs) -> dict[str, int]:
    """R-4's placeholder mapping — only numbers something actually computed.

    A `manifest_fallback` do-nothing contributes NO cost number, so the framing can say what it knows
    and stay silent about what it does not, instead of rendering a zero that reads like a measurement.
    """
    numbers: dict[str, int] = {}
    cost = inputs.do_nothing.get("cost_bp")
    if inputs.computed and isinstance(cost, int) and not isinstance(cost, bool):
        numbers["do_nothing_cost_bp"] = int(cost)
    for name, value in (("days_to_horizon", inputs.horizon_days),
                        ("close_probability_bp", inputs.close_probability_bp),
                        ("play_win_rate_bp", inputs.play_win_rate_bp)):
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            numbers[name] = int(value)
    return numbers


def template_expected_effect(inputs: EffectInputs, numbers: Mapping[str, int]) -> str:
    """The deterministic fallback. Doc 05 §6's plain version of the same two facts."""
    clauses: list[str] = []
    if "days_to_horizon" in numbers:
        clauses.append("Acting now addresses this {days_to_horizon} days before the nearest "
                       "material date.")
    else:
        clauses.append(
            f"Acting on {inputs.safe_action_label} addresses this while it is still open.")
    if "do_nothing_cost_bp" in numbers:
        clauses.append("Doing nothing carries a measured inaction cost of {do_nothing_cost_bp} "
                       "basis points.")
    elif inputs.do_nothing.get("statement"):
        clauses.append(str(inputs.do_nothing["statement"]))
    if "close_probability_bp" in numbers:
        clauses.append("This deal's base close rate is {close_probability_bp} basis points; the "
                       "estimate is not a forecast of this outcome.")
    text = " ".join(clauses)
    # A stored `do_nothing.statement` is code-generated prose that may carry digits (it names the
    # measured cost). It is TRUE, but it is not templated, so it cannot travel into a field the
    # bundle will check for bare numbers — and a fallback that fails the bundle's own gauntlet is a
    # fallback that produces no card at all.
    if bare_numbers(text):
        text = " ".join(clause for clause in clauses if not bare_numbers(clause))
    return text[:EFFECT_CAP]


def _effect_prompt(inputs: EffectInputs, numbers: Mapping[str, int]) -> str:
    number_lines = "\n".join({
        "do_nothing_cost_bp": "  {do_nothing_cost_bp} = the measured cost of doing nothing, in "
                              "basis points",
        "days_to_horizon": "  {days_to_horizon} = whole days until the nearest material date",
        "close_probability_bp": "  {close_probability_bp} = this tenant's base close rate for "
                                "deals like this, in basis points — a base rate, not a forecast",
        "play_win_rate_bp": "  {play_win_rate_bp} = how often this play has worked for this "
                            "tenant, in basis points",
    }[name] for name in EFFECT_NUMBERS if name in numbers)
    return (
        "A decision has ALREADY been made and the action is fixed. Write ONE short framing of what "
        "changes if it is acted on, and what it costs to do nothing.\n\n"
        f"THE ACTION: {inputs.safe_action_label}\n\n"
        + ("PLACEHOLDERS you may use. Write the placeholder, never a digit:\n" + number_lines
           if number_lines else "NUMBERS: none were computed. Do not write any digit.")
        + "\n\nRULES:\n"
        "- Never write a digit. Use a placeholder from the list above, or no number at all.\n"
        "- Do not promise an outcome. A base rate is a base rate; say so.\n"
        "- Do not recommend anything, rank anything, or describe anything as urgent.\n"
        f"- At most {EFFECT_CAP // 6} words, two sentences.\n\n"
        'Answer with JSON and nothing else: {"expected_effect": "<your text>"}')


def frame_expected_effect(*, org_id: str, decision_hash: str, inputs: EffectInputs,
                          gate: Any = None, cache: Any = None,
                          subject_ref: str | None = None) -> NarrativeResult:
    """R-4 · `do_nothing` plus foresight, framed, with every number templated.

    Runs with R-2 (the bundle folds this straight into `expected_effect` and merges `numbers_used`)
    and on demand beside R-3 when a card is expanded. The precondition is that there is something to
    frame: with no computed number AND no stored do-nothing statement, a framing would be prose about
    nothing.
    """
    numbers = effect_numbers(inputs)

    def _parse(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        body, used = _validate_prose(
            str(payload.get("expected_effect") or ""), cap=EFFECT_CAP, numbers=numbers,
            statements=(), require_number=bool(numbers))
        return {"text": body, "numbers_used": used}

    def _fallback() -> Mapping[str, Any]:
        text = template_expected_effect(inputs, numbers)
        used = {name: int(numbers[name]) for name in placeholders(text)}
        return {"text": text, "numbers_used": used}

    result = run_site(
        site=SITE_R4, org_id=org_id,
        seed={"decision_hash": str(decision_hash), "numbers": dict(numbers),
              "source": str(inputs.do_nothing.get("source") or ""),
              "action": inputs.safe_action_label},
        precondition=bool(numbers) or bool(inputs.do_nothing.get("statement")),
        build_prompt=lambda feedback: with_correction(_effect_prompt(inputs, numbers), feedback),
        parse=_parse, fallback=_fallback,
        gate=gate, cache=cache, subject_ref=subject_ref)
    return NarrativeResult(text=str(result.payload.get("text") or ""),
                           numbers_used=dict(result.payload.get("numbers_used") or {}),
                           generation=result.generation, receipt=result.receipt)


__all__ = ["ALTERNATIVES_CAP", "ALTERNATIVES_NUMBERS", "EFFECT_CAP", "EFFECT_NUMBERS",
           "GENERIC_ALTERNATIVES", "EffectInputs", "NarrativeResult", "RejectedOption",
           "alternatives_numbers", "digit_free",
           "effect_numbers", "frame_expected_effect", "narrate_alternatives", "rejected_options",
           "rejected_options_from_card", "template_alternatives", "template_expected_effect"]
