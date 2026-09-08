"""N-3 · Organization-Brain discovery (CLG-09) — the company's written rules, read AS RULES.

THE GAP THIS CLOSES
-------------------
`learned_brain_entries` has been empty since migration 0045 shipped. The Organization brain's
flagship content is approval thresholds — *"contracts above $50,000 require founder approval"* —
and its only write path was manual console entry, which means it stayed empty. Meanwhile the
company already WROTE ITS RULES DOWN, and GeniOS already ingests those documents: L1's
`internal_kind` canon lane lands a policy or an SOP at authority rank 4, above any system of
record. Nothing read them as rules. This unit does.

WHAT IT IS NOT
--------------
It is not a decision-maker and it is not a publisher. A model reads the document and PROPOSES
typed candidates; everything after that is deterministic, and the proposal enters the EXISTING
Layer 6 pipeline through `feedback/org_rule_ingest.admit_discovery` at OBSERVED with source
``discovered``. No new governance is built here.

**THIS MODULE TOUCHES NO DATABASE AND NO CLOCK.** It is Layer 3, and the import ratchet
(`tests/test_layer_topology.py`) makes that one-way: a producer cannot call the Layer 6
governance that judges it, and it must not be able to. Everything here is a pure function of a
`CanonDocument`, a list of model candidates and an approver resolver. The driver that loads the
document, calls the model, persists the proposal and projects the confirmed rule lives on the
Layer 6 side, in `genios_engine/feedback/org_rule_ingest.py`, and it is the only half that can
reach a store at all. Nothing anywhere in this pipeline writes `learned_brain_entries` except
`feedback.publisher.publish_brain`, reached through governance — and that table refuses
`brain='expert'` at the database (`learned_brain_no_expert`).

CLG-09 — WHICH EXTRACTED STATEMENTS QUALIFY AS RULES
----------------------------------------------------
This is the judgment that decides whether the Organization brain fills with policy or with
noise, so it is stated here in code rather than left to a prompt. **A sentence in a handbook is
not a rule. A rule has a CONDITION, a CONSEQUENCE, and an AUTHORITY behind it.** Each of the
three is a gate, and each gate is checked against the DOCUMENT'S OWN BYTES, never against what
the model asserted:

  AUTHORITY OF THE SOURCE  the document's canon kind must be rule-bearing
                           (`RULE_BEARING_CANON_KINDS`). A policy, an SOP, a price list and an
                           org chart are things a company BINDS ITSELF TO. A wiki page, a
                           product description, a project note or an employee profile are not,
                           however confidently they are phrased — and `normalize_kind` maps
                           "handbook" onto `wiki`, which is precisely doc 02's counter-example.
                           This gate is also the cost gate: it is evaluated BEFORE the model is
                           called, so a tenant's wiki does not pay for a T2 extraction.

  EVIDENCE                 the quote must verify against the prepared text with ALG-08
                           (`capture/validate/spans.verify_span`). An invented sentence is
                           dropped — the same anti-hallucination rule L1 applies to every fact.
                           The STATEMENT stored afterwards is the source's bytes at the offsets
                           ALG-08 actually found, never the model's copy of them.

  CONSEQUENCE              the verified statement must carry DEONTIC FORCE — an obligation, a
                           permission or a prohibition (`_DEONTIC`). "Contracts above $50,000
                           require founder approval" binds; "we usually look closely at large
                           contracts" describes. The check runs on the DOCUMENT'S words, so a
                           model cannot talk a description into a rule by labelling it one.

  CONDITION                the statement must name the class of thing it governs: the candidate's
                           `subject_type` has to appear in the verified quote. A rule about
                           "contracts" that never says "contract" is a rule about nothing.
                           A monetary threshold is optional (a hiring approval has no amount)
                           but when one is claimed it must be a SUBSTRING of the verified quote
                           and must parse through L1.5.3 (`capture/validate/money.parse_money`).
                           **The model never emits a number.** It points at the characters; ALG-10
                           does the arithmetic. A threshold the parser cannot reproduce from the
                           quote is dropped, which is what makes "the model invented $75,000"
                           impossible rather than unlikely.

  AUTHORITY OF THE RULE    an `approval` rule must name an approver, that approver must appear in
                           the verified quote, and it must resolve to a real node
                           (`_resolve_approver`: an email alias, an observed person name, or a
                           canon employee/org-structure title — the three keys the identity layer
                           actually holds). An unresolved approver does NOT drop the rule: doc 02
                           says route it to human review, so the proposal is made and marked
                           `authority_pending`, and it can never mint an `AuthorityRule` because
                           `approver_node_id` is required by that contract. For the three
                           non-approval categories the authority IS the canon document — that is
                           what rank 4 means — and no approver is required.

Every refusal is NAMED and COUNTED (`REFUSAL_REASONS`), written to `learning_input_rejections`,
and summarised on the run receipt. A candidate that vanished without a counter is the failure
mode this whole file exists to avoid.

ONE DISCOVERY, TWO CONSUMERS
----------------------------
A confirmed `approval` rule is both an Organization-brain entry (read by
`packs/compiler/runtime_brains.py` into every relevant `ExpertisePackage`) and an
`AuthorityRule` (the L2.1.4 Authority view). `org_rule_ingest.project_authority_rules` derives
the second from the first, keyed on `authority_rule_id` below, so there is ONE extractor and one
source of truth — and the authority row appears only AFTER a human confirms the brain entry,
which is what "visible in the console BEFORE any card cites them" means in practice.
"""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

from genios_engine.capture.validate.money import parse_money_outcome
from genios_engine.capture.validate.spans import SpanVerdict, verify_span
from genios_engine.contracts.brain_address import BrainAddress, org_scope
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.learning import (
    LearningEvidence,
    LearningObject,
    LearningPolicy,
    LearningTarget,
    Visibility,
    VisibilityScope,
)
from genios_engine.contracts.units import Money, Ratio, parse_ratio

#: The unit name every proposal carries. `learning_objects.unit` is how the console, the
#: projection and any later audit tell an N-3 discovery from a weekly analysis unit.
DISCOVERY_UNIT = "org_rule_discovery"
#: The `learning_input_rejections.seam` value for refusals from this unit.
DISCOVERY_SEAM = "brains.org_discovery"
#: doc 02's three-rank authority vocabulary: admin_declared > discovered > inferred.
DISCOVERY_SOURCE = "discovered"

#: The closed category set (doc 02 step 3). Closed on purpose: an open vocabulary here would let
#: the model invent a category nothing downstream can route, which is inventory, not intelligence.
ORG_RULE_CATEGORIES: frozenset[str] = frozenset({"approval", "criticality", "policy", "process"})

#: The categories that name an approver and therefore mirror into `authority_rules`. The other
#: three are statements the company binds itself to with no single signatory.
AUTHORITY_BEARING_CATEGORIES: frozenset[str] = frozenset({"approval"})

#: Canon kinds a company BINDS ITSELF TO. See CLG-09 in the module docstring — this is the
#: "a sentence in a handbook is not a rule" gate, and `normalize_kind("handbook") == "wiki"`.
RULE_BEARING_CANON_KINDS: frozenset[str] = frozenset({"org_structure", "policy", "pricing", "sop"})

#: Brain-subject prefix. One lineage per (category, subject_type) so a superseding document
#: SUPERSEDES — `learned_brain_entries` keeps exactly one active version per (org, brain,
#: subject), and a subject keyed on the document would fork one rule into one entry per upload.
SUBJECT_PREFIX = "orgrule"

#: The span grades whose quote is literally present in the source. ALG-08's own words: "fuzzy
#: here means whitespace, never semantics" — there is no edit distance and no paraphrase anywhere
#: in that cascade, so all four are real citations and the two that are not are the two refused.
_VERIFIED_GRADES: dict[SpanVerdict, int] = {
    SpanVerdict.VERIFIED: 10000,
    SpanVerdict.VERIFIED_WHITESPACE: 10000,
    SpanVerdict.VERIFIED_RELOCATED: 9000,      # real words, wrong offsets — ALG-08's 9/10
    SpanVerdict.VERIFIED_FUZZY: 7000,          # real words modulo whitespace — ALG-08's 7/10
}

#: DEONTIC FORCE. Obligation, permission and prohibition markers — the linguistic difference
#: between a rule and a description. Deliberately a small, boring, word-boundary lexicon over the
#: DOCUMENT's text: a bigger one would start admitting "should consider" and "we prefer", which is
#: exactly how a handbook's prose leaks into a brain that decisions are read from.
_DEONTIC = re.compile(
    r"\b("
    r"must|shall|may\s+not|cannot|can\s?not|"
    r"require[sd]?|required|requirement|requires|"
    r"mandatory|obligator(?:y|ily)|prohibited|forbidden|not\s+permitted|"
    r"approval|approve[sd]?|authoris(?:e|ed|ation)|authoriz(?:e|ed|ation)|"
    r"sign[-\s]?off|signoff|needs\s+to\s+be|has\s+to\s+be|is\s+not\s+allowed|only\s+.{0,40}\bmay\b"
    r")\b", re.IGNORECASE)

#: A subject_type is a class name the packs already speak (contract, expense, hiring, discount,
#: legal…). Lowercase, short, no punctuation — it becomes part of a brain subject key.
_SUBJECT_TYPE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")

#: Every reason this unit may refuse a candidate. Declared as data so the counters, the ledger
#: rows and the tests share one vocabulary and a new refusal cannot be added without naming it.
REFUSAL_REASONS: tuple[str, ...] = (
    "approver_missing",
    "approver_not_in_quote",
    "duplicate_rule",
    "kind_not_rule_bearing",
    "malformed_span",
    "malformed_subject_type",
    "no_deontic_force",
    "span_unverified",
    "subject_type_not_in_quote",
    "threshold_not_in_quote",
    "threshold_unparseable",
    "unknown_category",
)


class Disposition(str, Enum):
    """What CLG-09 decided about one candidate."""

    #: Every gate passed. The proposal is made and, once a human confirms it, it can bind.
    ADMITTED = "admitted"
    #: Proposed, but something a human must supply is missing (today: an unresolvable approver).
    #: It can never mint an `AuthorityRule` — `approver_node_id` is required by that contract.
    HUMAN_REVIEW = "human_review"
    #: Dropped, with a named reason.
    REFUSED = "refused"


@dataclass(frozen=True, slots=True)
class CanonDocument:
    """One canon document as this unit reads it. No clock, no connection, no store."""

    org_id: str
    event_id: str
    kind: str                       # a normalised INTERNAL_KINDS value
    title: str
    text: str                       # the PREPARED text — the coordinate system offsets live in
    occurred_at: datetime           # the source-observation time; never the wall clock
    #: The dedup key L1 minted from `(source_object_id, content_version)`. Editing a policy and
    #: re-submitting changes it, which is exactly the "this is a new version of that rule" signal.
    version_key: str
    #: The connection's DECLARED locale, or None. Never guessed: "$50,000" is USD, CAD or AUD and
    #: ALG-10 refuses rather than picking one. A refusal here is visible and counted.
    locale: str | None = None

    @property
    def source_ref(self) -> str:
        """The EvidenceSpan coordinate system — L1's own `prepared_content:<event_id>` shape."""
        return f"prepared_content:{self.event_id}"

    @property
    def rule_bearing(self) -> bool:
        return self.kind in RULE_BEARING_CANON_KINDS


@dataclass(frozen=True, slots=True)
class Refusal:
    """One candidate that did not become a rule, and why. Named, counted, and stored."""

    reason: str
    detail: str = ""

    def __post_init__(self) -> None:
        if self.reason not in REFUSAL_REASONS:
            raise ValueError(f"{self.reason!r} is not a declared refusal reason")


@dataclass(frozen=True, slots=True)
class GatedRule:
    """A candidate that survived CLG-09, carrying the receipts that let it survive."""

    category: str
    subject_type: str
    statement: str                       # the DOCUMENT's bytes, at ALG-08's corrected offsets
    span: EvidenceSpan
    verdict: SpanVerdict
    disposition: Disposition
    threshold: Money | None = None
    #: The percentage threshold, when the amount was written as one. A rule has AT MOST ONE
    #: threshold and it is either money or a ratio — never both — so these two fields are
    #: mutually exclusive by construction in `gate_candidates` rather than by a validator here.
    ratio: Ratio | None = None
    approver_as_written: str | None = None
    approver_node_id: str | None = None

    @property
    def subject(self) -> str:
        """The brain subject key — one lineage per (category, subject_type)."""
        return f"{SUBJECT_PREFIX}:{self.category}:{self.subject_type}"

    @property
    def authority_pending(self) -> bool:
        """True when a human must name the approver before this rule can bind anything."""
        return (self.category in AUTHORITY_BEARING_CATEGORIES
                and self.approver_node_id is None)

    @property
    def confidence_bp(self) -> int:
        """The span grade, in basis points. Integer, from ALG-08's own factors — never a float."""
        return _VERIFIED_GRADES[self.verdict]


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """Everything one document produced: the rules, the refusals, and the arithmetic."""

    doc: CanonDocument
    rules: tuple[GatedRule, ...] = ()
    refusals: tuple[Refusal, ...] = ()
    candidates_seen: int = 0

    def counters(self) -> dict[str, int]:
        counts = {"candidates": self.candidates_seen,
                  "admitted": sum(1 for r in self.rules
                                  if r.disposition is Disposition.ADMITTED),
                  "human_review": sum(1 for r in self.rules
                                      if r.disposition is Disposition.HUMAN_REVIEW),
                  "refused": len(self.refusals)}
        for reason in REFUSAL_REASONS:
            n = sum(1 for r in self.refusals if r.reason == reason)
            if n:
                counts[f"refused_{reason}"] = n
        return counts

    @property
    def accounted_for(self) -> bool:
        """Every candidate the model produced became a rule or a NAMED refusal.

        The no-silent-drop contract as arithmetic rather than as a promise. A document refused at
        the kind gate never reaches the per-candidate loop, so its candidates are accounted for by
        that single refusal — which is why the comparison is `>=` on that one path only.
        """
        if not self.doc.rule_bearing:
            return len(self.refusals) == 1
        return len(self.rules) + len(self.refusals) == self.candidates_seen


# =================================================================================================
# CLG-09 — the gate. Pure: no database, no clock, no model.
# =================================================================================================

def _word_in(needle: str, haystack: str) -> bool:
    """Is `needle` present in `haystack` as a word, allowing an English plural?

    Deliberately crude and deliberately not a stemmer: the question is only "does the document
    say the thing the candidate claims it says", and a fuzzy matcher here would re-open the
    paraphrase door ALG-08 closes one gate earlier.
    """
    stem = re.escape(needle.strip().lower().replace("_", " "))
    if not stem:
        return False
    return re.search(rf"\b{stem}(?:s|es)?\b", haystack.lower()) is not None


def _resolve_span(doc: CanonDocument, candidate: Mapping[str, Any]
                  ) -> tuple[EvidenceSpan, SpanVerdict] | Refusal:
    quote = candidate.get("quote")
    start, end = candidate.get("start_offset"), candidate.get("end_offset")
    try:
        span = EvidenceSpan(source_ref=doc.source_ref, quote=quote,
                            start_offset=int(start), end_offset=int(end))
    except Exception as exc:                          # noqa: BLE001 — a shape error IS a refusal
        return Refusal("malformed_span", f"{type(exc).__name__}: {exc}"[:200])
    verdict, corrected = verify_span(span, doc.text)
    if verdict not in _VERIFIED_GRADES:
        return Refusal("span_unverified", verdict.value)
    return corrected, verdict


def _gate_one(doc: CanonDocument, candidate: Mapping[str, Any],
              resolve_approver: Callable[[str], str | None]) -> GatedRule | Refusal:
    """One candidate through CLG-09, cheapest gate first. Returns a rule or a named refusal."""
    category = str(candidate.get("category") or "").strip().lower()
    if category not in ORG_RULE_CATEGORIES:
        return Refusal("unknown_category", category[:60])

    subject_type = str(candidate.get("subject_type") or "").strip().lower().replace(" ", "_")
    if not _SUBJECT_TYPE.fullmatch(subject_type):
        return Refusal("malformed_subject_type", subject_type[:60])

    resolved = _resolve_span(doc, candidate)
    if isinstance(resolved, Refusal):
        return resolved
    span, verdict = resolved
    statement = span.quote                            # the DOCUMENT's bytes, not the model's copy

    if not _DEONTIC.search(statement):
        # A description, not a rule. This is the handbook sentence CLG-09 exists to keep out, and
        # the check is on the document's own words so no model assertion can override it.
        return Refusal("no_deontic_force", statement[:120])

    if not _word_in(subject_type, statement):
        return Refusal("subject_type_not_in_quote", subject_type)

    threshold: Money | None = None
    ratio: Ratio | None = None
    as_written = candidate.get("threshold_as_written")
    if as_written not in (None, ""):
        as_written = str(as_written)
        if as_written not in statement:
            # The model pointed at characters that are not in the sentence it cited. This is the
            # invented-threshold catch, and it fires BEFORE the parser so a plausible-but-absent
            # number can never become an integer somebody signs against.
            return Refusal("threshold_not_in_quote", as_written[:60])
        parsed = parse_money_outcome(as_written, locale=doc.locale)
        if parsed.money is None:
            # NOT MONEY — TRY THE OTHER DIMENSION BEFORE REFUSING THE WHOLE RULE.
            #
            # *"A discount greater than 15% requires approval from the founder"* used to die here.
            # `threshold_as_written` was validated by ALG-10 alone, a money cascade, which answers
            # UNPARSEABLE_TOKEN for `15%` — and the refusal took the rule with it, not just the
            # number. The condition, the consequence and the named authority were all present and
            # all discarded, and discount authority is the most common approval rule a sales-led
            # startup writes down.
            #
            # `parse_ratio` is deterministic and total (`contracts/units`), so this is a second
            # exact reading of the same characters, not a second guess at them. The
            # invented-threshold catch above still runs FIRST and is unchanged: a percentage that
            # is not literally in the cited sentence is still refused as `threshold_not_in_quote`.
            ratio = parse_ratio(as_written)
            if ratio is None:
                return Refusal(
                    "threshold_unparseable",
                    f"{as_written[:40]}: {parsed.failure.value if parsed.failure else '?'}")
        else:
            threshold = parsed.money

    approver_as_written = candidate.get("approver_as_written")
    approver_as_written = (str(approver_as_written).strip()
                           if approver_as_written not in (None, "") else None)
    approver_node_id: str | None = None
    if category in AUTHORITY_BEARING_CATEGORIES:
        if approver_as_written is None:
            return Refusal("approver_missing", subject_type)
        if not _word_in(approver_as_written, statement):
            return Refusal("approver_not_in_quote", approver_as_written[:60])
        approver_node_id = resolve_approver(approver_as_written)
    elif approver_as_written is not None and not _word_in(approver_as_written, statement):
        # A non-approval rule may still name someone; if it does, the name still has to be in the
        # document. Dropping the NAME rather than the rule would silently rewrite what was said.
        return Refusal("approver_not_in_quote", approver_as_written[:60])

    disposition = (Disposition.HUMAN_REVIEW
                   if category in AUTHORITY_BEARING_CATEGORIES and approver_node_id is None
                   else Disposition.ADMITTED)
    return GatedRule(category=category, subject_type=subject_type, statement=statement, span=span,
                     verdict=verdict, disposition=disposition, threshold=threshold, ratio=ratio,
                     approver_as_written=approver_as_written, approver_node_id=approver_node_id)


def gate_candidates(doc: CanonDocument, candidates: Sequence[Mapping[str, Any]], *,
                    resolve_approver: Callable[[str], str | None] | None = None
                    ) -> DiscoveryResult:
    """CLG-09 over one document's candidates. Pure — the only impurity is the resolver callable.

    A non-rule-bearing document refuses ONCE, at the document, and never reaches the per-candidate
    gates: the kind is a fact about the source's authority, not about any one sentence in it.
    """
    if not doc.rule_bearing:
        return DiscoveryResult(doc=doc, refusals=(Refusal("kind_not_rule_bearing", doc.kind),),
                               candidates_seen=len(candidates))

    resolver = resolve_approver or (lambda _name: None)
    rules: list[GatedRule] = []
    refusals: list[Refusal] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        outcome = _gate_one(doc, candidate, resolver)
        if isinstance(outcome, Refusal):
            refusals.append(outcome)
            continue
        key = (outcome.subject, outcome.statement)
        if key in seen:
            # One document restating one rule is one rule. Without this a policy that repeats its
            # approval matrix in a summary table would propose the same entry twice and the second
            # would supersede the first for no reason — the version noise invariant #8 forbids.
            refusals.append(Refusal("duplicate_rule", outcome.subject))
            continue
        seen.add(key)
        rules.append(outcome)
    return DiscoveryResult(doc=doc, rules=tuple(rules), refusals=tuple(refusals),
                           candidates_seen=len(candidates))


# =================================================================================================
# The proposal — a LearningObject, and nothing else
# =================================================================================================

def proposed_value(doc: CanonDocument, rule: GatedRule) -> dict[str, Any]:
    """What the Organization brain would hold. JSON-only, and every claim carries its receipt.

    Note what is NOT here: any prose the model wrote. `statement` is the document's bytes,
    `threshold_*` came out of ALG-10, `approver_node_id` out of the identity layer, and the only
    model-authored strings that survive are `category` (a closed set), `subject_type` (matched
    against the document) and `approver_as_written` (matched against the document). A model
    cannot editorialise into this dict because there is nowhere for prose to land.
    """
    return {
        "category": rule.category,
        "subject_type": rule.subject_type,
        "statement": rule.statement,
        "statement_hash": hashlib.sha256(rule.statement.encode()).hexdigest(),
        "threshold_minor_units": None if rule.threshold is None else rule.threshold.minor_units,
        "currency": None if rule.threshold is None else rule.threshold.currency,
        "threshold_as_written": (
            rule.threshold.as_written if rule.threshold is not None
            else (rule.ratio.as_written if rule.ratio is not None else None)),
        # THE RATIO ARM. Kept in its own field rather than folded into `threshold_minor_units`:
        # 1500 basis points and 1500 minor units are the same integer and mean nothing alike, and
        # a reader that had to consult `currency` to find out which it was holding would get it
        # wrong once. `None` on a money rule and on a rule with no threshold at all.
        "threshold_basis_points": None if rule.ratio is None else rule.ratio.basis_points,
        "approver_as_written": rule.approver_as_written,
        "approver_node_id": rule.approver_node_id,
        "authority_pending": rule.authority_pending,
        "authority_source": DISCOVERY_SOURCE,
        "evidence": {"source_ref": rule.span.source_ref, "start_offset": rule.span.start_offset,
                     "end_offset": rule.span.end_offset, "verdict": rule.verdict.value},
        "document": {"event_id": doc.event_id, "kind": doc.kind, "title": doc.title,
                     "version_key": doc.version_key,
                     "stated_at": doc.occurred_at.isoformat()},
        # THE ADDRESS — what this rule is ABOUT, in the one vocabulary a situation also speaks.
        #
        # Tenant-wide, and that is a judgement worth stating rather than defaulting into. An
        # Organization rule is extracted from the tenant's OWN approved policy document, gated on
        # that document's bytes and confirmed by a human; it is a declaration by the company about
        # the company. Its subject key — `orgrule:<category>:<subject_type>` — names its own
        # taxonomy and nothing any situation knows about itself, which is exactly why it selected
        # into zero packages before this existed. The narrower address does not exist to be
        # written: a policy does not say which capability will need it.
        #
        # `orgwide` is minted only by `brain_address.org_scope`, and only Organization knowledge
        # may carry it — `BrainAddress` refuses it for Behaviour and Adaptive, because a
        # measurement or a preference that bound everywhere would be a rule nobody approved.
        "address": BrainAddress(
            org_id=doc.org_id, brain="organization",
            tokens=org_scope(doc.org_id),
            authority={"source": DISCOVERY_SOURCE, "category": rule.category,
                       "subject_type": rule.subject_type,
                       "document_event_id": doc.event_id,
                       "document_version_key": doc.version_key,
                       "approver_node_id": rule.approver_node_id,
                       "authority_pending": rule.authority_pending}).as_value(),
    }


def build_proposal(doc: CanonDocument, rule: GatedRule, *, policy: LearningPolicy) -> LearningObject:
    """One gated rule as an immutable L6 proposal. Times come from the DOCUMENT, not the clock."""
    return LearningObject(
        org_id=doc.org_id, unit=DISCOVERY_UNIT, target=LearningTarget.ORGANIZATION,
        subject=rule.subject, proposed_value=proposed_value(doc, rule),
        evidence=LearningEvidence(
            # ONE verified span in ONE canon document, stated honestly. A declaration is not a
            # recurrence and this unit does not dress it up as one: the recurrence floors read
            # these numbers and their verdict is recorded on the Validated transition
            # (`l6_entry.enter_l6`), where a reviewer can see it.
            observations=1, independent_refs=1, distinct_days=1, positive=1, negative=0,
            confidence_bp=rule.confidence_bp, distinct_entities=1,
            source_refs=(rule.span.source_ref,)),
        visibility=Visibility(scope=VisibilityScope.ORGANIZATION,
                              derived_from=(f"internal_kind:{doc.kind}", doc.event_id)),
        first_seen_at=doc.occurred_at, last_seen_at=doc.occurred_at,
        policy_key=policy.policy_key)


# =================================================================================================
# The model site (T2) — a protocol, so the gate is testable without one
# =================================================================================================

class OrgRuleExtractor(Protocol):
    """The N-3 model call. It PROPOSES typed candidates; CLG-09 decides.

    Every field it returns is either a closed-set token or a pointer into the document. It is
    never asked for a number, a paraphrase or a judgment — see `org_rule_extract` for the prompt
    and for why that shape is the whole anti-hallucination design.
    """

    def propose(self, *, text: str, kind: str, title: str) -> Sequence[Mapping[str, Any]]: ...


# =================================================================================================
# Approver resolution — the identity layer's real keys, and no others
# =================================================================================================

def resolve_approver_node(conn, *, org_id: str, name: str) -> str | None:
    """A name in a policy → an existing node id, or None. Never creates and never guesses.

    Three keys, in descending strength, and they are the three the identity layer actually holds:
    an email alias proves one human; an observed person-name alias is exact-match only and returns
    NOBODY when two people share it; a canon title alias is how a ROLE ("Founder", "Head of
    Finance") resolves — an `employee_profile` or `org_structure` document the company wrote.
    None is the ordinary answer for a company that has declared none of the three, and doc 02
    says what to do with it: human review, not a guess.
    """
    from genios_engine.context.canon import canon_title_key
    from genios_engine.context.identity import (ALIAS_CANON, ALIAS_EMAIL, resolve_alias,
                                                resolve_person_name)
    from genios_engine.platform.identity import norm_email

    cleaned = (name or "").strip()
    if not cleaned:
        return None
    email = norm_email(cleaned)
    if email:
        hit = resolve_alias(conn, org_id=org_id, alias_type=ALIAS_EMAIL, alias_key=email)
        if hit:
            return hit
    hit = resolve_person_name(conn, org_id=org_id, name=cleaned)
    if hit:
        return hit
    title_key = canon_title_key(cleaned)
    if title_key:
        return resolve_alias(conn, org_id=org_id, alias_type=ALIAS_CANON, alias_key=title_key)
    return None




def authority_rule_id(subject: str) -> str:
    """A stable `authority_rules.rule_id` per brain subject.

    Derived from the SUBJECT, not from the document, and that is the whole point: a superseding
    policy re-states the same rule, so it must CLOSE its predecessor's window rather than open a
    second parallel rule for the same class. Keying on the document would give a company that
    re-uploads its approvals policy two live approvers for one threshold.
    """
    return f"orgrule_{hashlib.sha256(subject.encode()).hexdigest()[:20]}"


__all__ = ["AUTHORITY_BEARING_CATEGORIES", "CanonDocument", "DISCOVERY_SEAM", "DISCOVERY_SOURCE",
           "DISCOVERY_UNIT", "DiscoveryResult", "Disposition", "GatedRule", "ORG_RULE_CATEGORIES",
           "OrgRuleExtractor", "REFUSAL_REASONS", "RULE_BEARING_CANON_KINDS", "Refusal",
           "SUBJECT_PREFIX", "authority_rule_id", "build_proposal", "gate_candidates",
           "proposed_value", "resolve_approver_node"]
