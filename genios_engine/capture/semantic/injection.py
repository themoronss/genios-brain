"""L1.4.7 · the prompt injection guard — the seam where attacker-written text stops being text.

Every message this system reads was written by somebody outside it. A prospect, a vendor, a
stranger who bought our address: each of them can put any string they like into the one part of
the prompt we do not control. Doc 04 states the defence in three layers and is explicit about
which one actually holds:

    1. the content is delimited by a NONCE fence the sender cannot guess;
    2. prompt block 2 (SAFETY) says the content is data;
    3. **structural guarantee** — the model cannot set any `_bp` field, cannot set
       `signal_type`, cannot set `visibility`. A fully successful injection still cannot raise
       its own importance, because importance is not in its output schema at all.

*"That third point is the real defense. Prompt text is advisory; the schema is enforcement."*
This module owns 1, asserts that 2 is where it must be, and cannot own 3 — 3 lives in
`contracts/extraction.ExtractionResult`, which refuses `importance_bp` and `priority_bp` at
construction. `SCHEMA_ENFORCED_ABSENT` below names those fields, read off the contract rather
than retyped, so the test that proves the guarantee proves it about the real type.

WHAT THIS MODULE PORTS, AND WHAT IT FIXES. The existing defence is commit `54e8ca1`
(`context/extract/prompt.py`): the body is wrapped in `<<<MESSAGE>>> … <<<END MESSAGE>>>` and
the prompt says do not obey it. The prose half is good and is preserved verbatim — it is now
`profiles.SAFETY_BLOCK`, shared by all five templates. The fence half has a hole this module
closes: **that fence is a constant**. Anyone who has seen one of our prompts — or who guesses
the most obvious delimiter in the world — can write `<<<END MESSAGE>>>` in an email body, and
from the model's point of view the untrusted region ended and the next line is the operator
speaking. Doc 04's nonce is the fix, and escaping is what makes the nonce hold even when the
attacker somehow has it.

    L1.4.7-U1 · `fence`       — content becomes a nonce-delimited, structurally neutralised block
    L1.4.7-U2 · `scan_output` — model output that echoes an instruction is suspect

**THE ESCAPE IS LENGTH-PRESERVING, AND THAT IS NOT AN AESTHETIC CHOICE.** The model's evidence
offsets are measured against exactly the characters it was shown, and L1.4.6 aligns those
offsets back to `PreparedContent.clean_text` by adding a chunk start and walking a mask map.
An escape that deleted or expanded a character would displace every offset after it, and the
symptom is not an error: it is a correctly-read quote that fails `content[start:end] == quote`
and is discarded as a hallucination. So each neutralised character is replaced by exactly one
other character (`<` → `‹`, `[` → `⟦`), `len(body) == len(content)` is asserted at
construction, and `span_is_escaped` is how a caller asks whether a particular span crosses one
of the few characters that differ.

**NOTHING IS REMOVED.** The SAFETY block tells the model to extract a directive as reported
speech — *"the message says: ignore previous instructions"* is a real fact about a real
message, and a phishing attempt is exactly the kind of thing a founder should be told about.
Stripping the payload would destroy the evidence span that proves it was there. So this module
reports (`InjectionSignal`, `risk_bp`) and neutralises only what could be mistaken for the
prompt's own STRUCTURE — never the words.

The escaped set is therefore narrow and precise: the nonce fence in any of its shapes, and the
literal block markers `profiles.py` builds the instruction spine from. Ordinary prose that
merely talks about ignoring instructions is left byte-for-byte alone and merely flagged.

PURITY. No clock, no DB, no model. One source of randomness — the nonce — and it is injectable
so a test can name it, which is the only way a test can construct the payload that contains the
fence it is testing. `capture/semantic/` may call an LLM; this file does not, because a guard
that asked a model whether it was being attacked would be asking the attacker.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass

from genios_engine.capture.semantic.profiles import (BLOCK_MARKERS, CONTENT_MARKER, END_MARKER,
                                                     ENVELOPE_MARKER, PROMPT_BLOCK_NAMES)
from genios_engine.contracts.extraction import FORBIDDEN_RESULT_FIELDS

#: Hex characters in a nonce. 16 is 64 bits: the fence is not a secret that must survive
#: cryptanalysis, it must survive *guessing by someone who has read our prompt*, and 64 bits of
#: per-message randomness makes a forged close marker a coincidence nobody has ever had.
NONCE_CHARS = 16

#: The fence, as parts. Assembled rather than typed as two literals so `open_marker`,
#: `close_marker` and the regex that escapes forgeries of them are one fact — a fence whose
#: escape pattern is a separately-typed literal is a fence that stops being escaped the day
#: somebody renames it.
FENCE_LEAD = "<<<"
FENCE_TAIL = ">>>"
OPEN_LABEL = "CONTENT"
CLOSE_LABEL = "END"


def open_fence(nonce: str) -> str:
    """The literal that opens the untrusted region for `nonce`."""
    return f"{FENCE_LEAD}{OPEN_LABEL}_{nonce}{FENCE_TAIL}"


def close_fence(nonce: str) -> str:
    """The literal that closes it. The one string an attacker would need and cannot have."""
    return f"{FENCE_LEAD}{CLOSE_LABEL}_{nonce}{FENCE_TAIL}"


#: The SAFETY block's marker, taken from the registry that builds it. `check_placement` asserts
#: this marker precedes the fence, because a "the content below is data" instruction placed
#: AFTER the data is an instruction the model reads too late.
SAFETY_MARKER = BLOCK_MARKERS[PROMPT_BLOCK_NAMES.index("SAFETY")]

#: Fields the OUTPUT SCHEMA refuses, read off the contract. This is doc 04's third point and the
#: only part of the defence that is enforcement rather than advice: a model that emitted
#: `importance_bp` would be refused by `ExtractionResult` at construction, so a successful
#: injection has nowhere to put a score. Named here so `scan_output` can notice the attempt
#: BEFORE it becomes a parse failure with no explanation attached.
SCHEMA_ENFORCED_ABSENT = tuple(sorted(FORBIDDEN_RESULT_FIELDS))

#: Names doc 04 lists alongside the `_bp` fields — routing and visibility. They are not fields
#: on `ExtractionResult` at all, which is the strongest form of the guarantee: there is no key
#: to refuse because there is no key. Kept for `scan_output`, which flags an output naming one.
ROUTING_FIELDS_ABSENT = ("signal_type", "visibility")

#: One neutralising substitute per structural character, each exactly ONE code point so the
#: substitution cannot move an offset. Visually near-identical on purpose: a person reading a
#: logged prompt should see the shape of what the sender wrote, and only the model needs the
#: two strings to be unequal.
NEUTRALISE = {"<": "‹", ">": "›", "[": "⟦", "]": "⟧"}

_NONCE_RE = re.compile(rf"\A[0-9a-f]{{{NONCE_CHARS}}}\Z")

#: A fence in ANY nonce, not only ours. A payload carrying `<<<END_0000…>>>` with a fabricated
#: nonce cannot close the real fence, but it can persuade the model that the untrusted region
#: ended — the model has no way to know which of two well-formed fences is authentic. So every
#: fence-shaped literal is neutralised and the sender's guess is reported.
_FENCE_SHAPE = re.compile(
    rf"{re.escape(FENCE_LEAD)}(?:{OPEN_LABEL}|{CLOSE_LABEL})_[0-9a-f]{{{NONCE_CHARS}}}"
    rf"{re.escape(FENCE_TAIL)}")

#: The instruction spine's own literals — the six block markers, the terminator, and the two
#: section headers — plus the generic `[BLOCK n: NAME]` shape, so an invented seventh block is
#: neutralised as readily as a copy of a real one.
_FRAME_LITERALS = tuple(BLOCK_MARKERS) + (END_MARKER, ENVELOPE_MARKER, CONTENT_MARKER)
_FRAME_SHAPE = re.compile(
    "|".join([r"\[BLOCK \d{1,2}: [A-Z][A-Z ]{0,30}\]"]
             + [re.escape(literal) for literal in _FRAME_LITERALS]))

#: The two escape classes, and what each one is called when it is reported as a signal.
FENCE_FORGERY = "fence_forgery"
FRAME_FORGERY = "frame_forgery"


@dataclass(frozen=True)
class InjectionPattern:
    """One recognised attack shape: what to look for, what to call it, what it is worth.

    `weight_bp` is a fixed integer per KIND, not per occurrence — see `_risk_bp`. It is a
    severity label expressed in basis points so it composes with every other score in Layer 1,
    and it is authored here rather than learned: a guard whose sensitivity drifts with traffic
    is a guard that quietly stops firing on the traffic that trained it.
    """

    kind: str
    weight_bp: int
    pattern: re.Pattern[str]
    why: str


#: The classic payloads, in the order doc 04 and the 54e8ca1 commit message name them. Each is
#: deliberately narrow: a false positive costs nothing (the text is kept, the flag is advisory)
#: but a pattern broad enough to fire on every business email makes `risk_bp` a constant, and a
#: constant is not a signal.
INJECTION_PATTERNS: tuple[InjectionPattern, ...] = (
    InjectionPattern(
        kind="instruction_override", weight_bp=4000,
        pattern=re.compile(
            r"\b(?:ignore|disregard|forget|override|overrule)\b[^.\n]{0,48}?"
            r"\b(?:previous|prior|above|preceding|earlier|all|any|your)\b[^.\n]{0,48}?"
            r"\b(?:instruction|prompt|rule|direction|guideline|constraint)s?\b"
            r"|\bnew instructions?\s*[:\-]"
            r"|\bthe (?:real|actual|true) (?:task|instruction|prompt)\b",
            re.IGNORECASE),
        why="the canonical payload — an imperative aimed at the reader of the prompt rather "
            "than at the recipient of the message"),
    InjectionPattern(
        kind="role_reassignment", weight_bp=2000,
        pattern=re.compile(
            r"\byou are (?:now|no longer|actually)\b"
            r"|\bfrom now on,? you\b"
            r"|\byour (?:new|real) (?:role|task|job|instructions?)\b"
            r"|\bpretend (?:to be|you are)\b",
            re.IGNORECASE),
        why="reassigning the reader's role is how a payload gets past a refusal that names the "
            "role it was given"),
    InjectionPattern(
        kind="fake_turn", weight_bp=3000,
        pattern=re.compile(
            r"^[ \t]*(?:system|assistant)[ \t]*:"
            r"|<\|im_(?:start|end)\|>"
            r"|<\|(?:system|assistant|user)\|>"
            r"|</?system>"
            r"|\[[ \t]*(?:system|assistant)(?:[ \t]+(?:prompt|message|note))?[ \t]*\]"
            r"|^[ \t]*#{1,6}[ \t]*system\b",
            re.IGNORECASE | re.MULTILINE),
        why="a forged conversation turn — the payload claims to be the operator speaking rather "
            "than the message being read"),
    InjectionPattern(
        kind="fake_schema", weight_bp=3000,
        pattern=re.compile(
            r"\breturn (?:only |exactly |just )?(?:this|the following)\b[^.\n]{0,24}"
            r"\b(?:json|shape|object|format|schema)\b"
            r"|\brespond (?:only )?(?:with|in)\b[^.\n]{0,24}\bjson\b"
            r"|\boutput (?:the following|exactly)\b"
            r"|\"?(?:" + "|".join(SCHEMA_ENFORCED_ABSENT + ROUTING_FIELDS_ABSENT) + r")\"?\s*[:=]",
            re.IGNORECASE),
        why="a forged output contract — if the model takes the payload's schema for ours the "
            "extraction is shaped by the attacker even when no field is obeyed"),
    InjectionPattern(
        kind="score_injection", weight_bp=2500,
        pattern=re.compile(
            r"\b(?:set|mark|treat|rate|flag|raise|bump)\b[^.\n]{0,32}"
            r"\b(?:importance|priority|urgency|relevance|severity|critical|urgent)\b",
            re.IGNORECASE),
        why="an attempt to score the message from inside the message. The highest-false-positive "
            "kind here — a real sender writes \"please treat this as urgent\" — which is why it "
            "is reported and never acted on: the model has no score field to move"),
)

#: Weights for the two escape classes. Higher than any prose pattern: prose that argues with the
#: prompt is common and mostly harmless, whereas a payload carrying our own structural literals
#: is a deliberate, informed attempt at the frame itself.
_ESCAPE_WEIGHTS_BP = {FENCE_FORGERY: 5000, FRAME_FORGERY: 3500}

#: The ceiling every basis-point score in Layer 1 shares.
BP_FULL = 10000


@dataclass(frozen=True)
class InjectionSignal:
    """One thing worth reporting about a payload, with the span that proves it.

    Offsets are into the ORIGINAL content and, because escaping preserves length, are equally
    valid against `FencedContent.body`. `quote` is the matched text as the sender wrote it —
    pre-escape, so a reviewer reading a signal sees the attack rather than our neutralisation
    of it.
    """

    kind: str
    start: int
    end: int
    quote: str
    why: str

    def __post_init__(self) -> None:
        if self.start < 0 or self.end <= self.start:
            raise ValueError(f"{self.kind}: span [{self.start}, {self.end}) is not a real region")


@dataclass(frozen=True)
class FenceEscape:
    """One neutralised structural literal: where it was, what it was, what replaced it.

    Recorded rather than merely done, because the caller has one question this answers and
    nothing else can: *is the quote my model just returned inside a region I altered?* A claim
    whose evidence lands here will fail span verification downstream, and this is the difference
    between "the model hallucinated" and "we changed the text under it".
    """

    start: int
    end: int
    original: str
    replacement: str
    kind: str

    def __post_init__(self) -> None:
        if len(self.original) != len(self.replacement):
            raise ValueError(
                f"escape at {self.start} changed length ({len(self.original)} -> "
                f"{len(self.replacement)}); every evidence offset after it would be displaced")


@dataclass(frozen=True)
class FencedContent:
    """L1.4.7-U1's output: the untrusted region, delimited and structurally neutralised.

    `body` is the string the model sees and therefore the coordinate frame its offsets are in.
    `text` is `body` wrapped in the two markers, and is what goes into `render_prompt`'s
    `content` substitution. Both are carried because the caller needs the first to align
    evidence and the second to build the prompt, and deriving one from the other at each call
    site is how the two come to disagree about whether the markers are inside the frame.
    """

    nonce: str
    open_marker: str
    close_marker: str
    body: str
    text: str
    source_chars: int
    escapes: tuple[FenceEscape, ...]
    signals: tuple[InjectionSignal, ...]
    risk_bp: int

    def __post_init__(self) -> None:
        if len(self.body) != self.source_chars:
            raise ValueError(
                f"fenced body is {len(self.body)} characters but the content was "
                f"{self.source_chars}; every evidence offset the model returns would be wrong")
        if self.open_marker in self.body or self.close_marker in self.body:
            raise ValueError(
                "the fenced body still contains a fence marker — the escape pass did not run or "
                "did not cover the shape that reached it, and the untrusted region can be closed "
                "from inside")

    @property
    def escaped(self) -> bool:
        """Did anything in this payload have to be neutralised? The one-line answer a log wants."""
        return bool(self.escapes)

    def span_is_escaped(self, start: int, end: int) -> bool:
        """Does `[start, end)` in the model's frame overlap a character we altered?

        The check a caller runs before blaming the model for a quote that does not verify.
        Offsets are half-open and in the same frame as `body`.
        """
        if end <= start:
            raise ValueError(f"span [{start}, {end}) is not a real region")
        return any(escape.start < end and start < escape.end for escape in self.escapes)

    def check_placement(self, prompt_text: str) -> None:
        """Assert this fence sits where a fence must sit in the prompt it was rendered into.

        Five properties, and each of them is a way the guard silently becomes decoration:

        * the fenced text appears in the prompt at all — otherwise something re-escaped,
          re-wrapped or truncated it between here and the model;
        * each marker appears exactly ONCE. Two open markers mean two regions claim to be the
          untrusted one, and the model picks;
        * the SAFETY block precedes the fence, because "what follows is data" arrives too late
          after the data;
        * `[CONTENT]`, when present, introduces the fence rather than following it;
        * nothing but whitespace follows the close marker. Text after the fence is an
          instruction positioned exactly where a successful injection would put one, and the
          prompt assembler cannot tell the two apart afterwards.

        Raises `ValueError` naming the violated property. It raises rather than returning a
        verdict because there is no correct way to continue: the prompt is already wrong, and
        sending it is the whole failure.
        """
        if self.text not in prompt_text:
            raise ValueError("the fenced content does not appear in the prompt verbatim; "
                             "something altered it between fencing and rendering")
        for name, marker in (("open", self.open_marker), ("close", self.close_marker)):
            count = prompt_text.count(marker)
            if count != 1:
                raise ValueError(f"the {name} fence marker appears {count} times in the prompt; "
                                 "exactly one untrusted region may be delimited")
        opened_at = prompt_text.index(self.open_marker)
        closed_at = prompt_text.index(self.close_marker)
        safety_at = prompt_text.find(SAFETY_MARKER)
        if safety_at < 0:
            raise ValueError(f"the prompt carries no {SAFETY_MARKER} block; the fence would "
                             "delimit untrusted content that was never declared untrusted")
        if safety_at > opened_at:
            raise ValueError(f"{SAFETY_MARKER} appears AFTER the fence opens; an instruction "
                             "that the content is data is read too late to frame the data")
        content_at = prompt_text.find(CONTENT_MARKER)
        if 0 <= opened_at < content_at:
            raise ValueError(f"{CONTENT_MARKER} appears after the fence opened, so the marker "
                             "falls inside the untrusted region instead of introducing it")
        trailing = prompt_text[closed_at + len(self.close_marker):]
        if trailing.strip():
            raise ValueError(
                f"{len(trailing.strip())} characters of prompt follow the close fence: "
                f"{trailing.strip()[:80]!r}. Anything after the untrusted region is an "
                "instruction in the exact position a successful injection would occupy")


def _mint_nonce() -> str:
    """A fresh fence nonce. `secrets`, not `random`: the whole property is unguessability."""
    return secrets.token_hex(NONCE_CHARS // 2)


def _neutralise(literal: str) -> str:
    """Replace each structural character with its one-code-point substitute."""
    return "".join(NEUTRALISE.get(ch, ch) for ch in literal)


def _escape_structure(content: str) -> tuple[str, tuple[FenceEscape, ...]]:
    """Neutralise every fence-shaped and frame-shaped literal, preserving every offset.

    One pass over the union of the two shapes rather than two sequential passes, because a
    sequential second pass would measure its offsets against a string the first pass had
    already rewritten, and the recorded escape spans would name positions in an intermediate
    string that no caller ever sees.
    """
    escapes: list[FenceEscape] = []
    pieces: list[str] = []
    cursor = 0
    combined = f"(?P<fence>{_FENCE_SHAPE.pattern})|(?P<frame>{_FRAME_SHAPE.pattern})"
    for match in re.finditer(combined, content):
        kind = FENCE_FORGERY if match.group("fence") is not None else FRAME_FORGERY
        original = match.group(0)
        replacement = _neutralise(original)
        pieces.append(content[cursor:match.start()])
        pieces.append(replacement)
        cursor = match.end()
        escapes.append(FenceEscape(start=match.start(), end=match.end(), original=original,
                                   replacement=replacement, kind=kind))
    pieces.append(content[cursor:])
    return "".join(pieces), tuple(escapes)


def _scan_patterns(content: str) -> tuple[InjectionSignal, ...]:
    """Every classic payload the content matches, in offset order.

    One signal per match, not per kind: a reviewer opening a flagged message wants to see each
    place the payload appears. `_risk_bp` is what collapses them to one score per kind, so a
    thread quoting the same forged turn nine times does not read as nine times the threat.
    """
    found: list[InjectionSignal] = []
    for spec in INJECTION_PATTERNS:
        for match in spec.pattern.finditer(content):
            if match.start() == match.end():
                continue
            found.append(InjectionSignal(kind=spec.kind, start=match.start(), end=match.end(),
                                         quote=match.group(0), why=spec.why))
    return tuple(sorted(found, key=lambda s: (s.start, s.end, s.kind)))


def _risk_bp(signals: tuple[InjectionSignal, ...]) -> int:
    """Integer basis points, one contribution per DISTINCT kind, capped at BP_FULL.

    Summing per occurrence would make length the dominant term: a long forwarded thread that
    quotes one phishing attempt would outscore a short, precisely-aimed payload. What the
    reader is being told is *how many different ways this message tried*, which is the question
    that separates a newsletter with an unfortunate sentence from an actual attempt.
    """
    weights = {**_ESCAPE_WEIGHTS_BP, **{p.kind: p.weight_bp for p in INJECTION_PATTERNS}}
    total = sum(weights.get(kind, 0) for kind in {s.kind for s in signals})
    return min(BP_FULL, total)


def fence(content: str, *, nonce: str | None = None) -> FencedContent:
    """L1.4.7-U1 · wrap untrusted content in a nonce fence it cannot close from inside.

    Three things happen, in this order, and the order is the design:

    1. **scan** the content as the sender wrote it, so every reported span and quote is the
       attack rather than our redaction of it;
    2. **escape** every fence-shaped and frame-shaped literal, one code point for one code
       point, so no evidence offset moves;
    3. **wrap** in `<<<CONTENT_nonce>>> … <<<END_nonce>>>`.

    `nonce` is injectable for exactly two callers: a test, which cannot otherwise build a
    payload containing the fence it is testing, and a replay that must reproduce a stored
    prompt byte-for-byte. Production omits it and gets 64 fresh bits. A supplied nonce is
    validated against the same shape a minted one has, because a caller passing `""` or
    `"MESSAGE"` would rebuild the guessable fence this unit exists to replace.

    Empty content is refused, matching `render_prompt`: a model asked to extract from nothing
    invents, and the tokens are spent either way.
    """
    if not content.strip():
        raise ValueError("content is empty — there is nothing to fence, and a model asked to "
                         "extract from nothing invents")
    if nonce is None:
        nonce = _mint_nonce()
    elif not _NONCE_RE.fullmatch(nonce):
        raise ValueError(
            f"nonce {nonce!r} is not {NONCE_CHARS} lowercase hex characters. A short, empty or "
            "guessable nonce is the static `<<<MESSAGE>>>` fence this unit replaced — any "
            "sender who has seen one prompt can then close the region from inside a message")
    signals = _scan_patterns(content)
    body, escapes = _escape_structure(content)
    signals = tuple(sorted(
        signals + tuple(InjectionSignal(
            kind=escape.kind, start=escape.start, end=escape.end, quote=escape.original,
            why=("a fence-shaped literal in the payload — an attempt to end the untrusted "
                 "region from inside it") if escape.kind == FENCE_FORGERY else
                ("a literal from the prompt's own instruction spine — an attempt to forge a "
                 "block the operator wrote")) for escape in escapes),
        key=lambda s: (s.start, s.end, s.kind)))
    opener, closer = open_fence(nonce), close_fence(nonce)
    return FencedContent(nonce=nonce, open_marker=opener, close_marker=closer, body=body,
                         text=f"{opener}\n{body}\n{closer}", source_chars=len(content),
                         escapes=escapes, signals=signals, risk_bp=_risk_bp(signals))


#: `scan_output` finding kinds. Named constants because a caller branches on them and a branch
#: on a string literal typed twice is a branch that stops matching after a rename.
FENCE_ECHOED = "fence_echoed"
FRAME_ECHOED = "frame_echoed"
FORBIDDEN_FIELD_EMITTED = "forbidden_field_emitted"
INSTRUCTION_ECHOED = "instruction_echoed"
REPORTED_SPEECH = "reported_speech"

#: What each output finding contributes to the output risk score. `REPORTED_SPEECH` is zero and
#: is still emitted: it is the finding that says *we looked, and this one is fine* — without it
#: a reviewer cannot tell a clean output from an unexamined one.
_OUTPUT_WEIGHTS_BP = {
    FENCE_ECHOED: 5000,
    FRAME_ECHOED: 3000,
    FORBIDDEN_FIELD_EMITTED: 4000,
    INSTRUCTION_ECHOED: 3500,
    REPORTED_SPEECH: 0,
}


@dataclass(frozen=True)
class OutputFinding:
    """One thing worth reporting about what the model sent back."""

    kind: str
    detail: str
    quote: str


@dataclass(frozen=True)
class OutputVerdict:
    """L1.4.7-U2's answer: is this output the extraction we asked for, or the payload's?

    `suspect` is the decision; `findings` is why. The verdict is advisory by construction — the
    schema is what refuses a forbidden field, and L1.4.3 decides whether a suspect output is
    parked or merely flagged. What this type guarantees is that the decision is never made from
    nothing.
    """

    suspect: bool
    findings: tuple[OutputFinding, ...]
    risk_bp: int


def scan_output(raw: str, *, fenced: FencedContent) -> OutputVerdict:
    """L1.4.7-U2 · audit model output for the marks of an injection that landed.

    Four questions, and the fourth is the one that needs the input to answer:

    * **did the fence leak?** The nonce or either marker in the output means the model is
      reproducing its prompt rather than describing a message. Nothing legitimate puts a
      per-message random token in an extraction;
    * **did the instruction spine leak?** A block marker or `[END BLOCKS]` in the output is the
      same failure one step less severe;
    * **is a refused field being emitted?** `importance_bp`, `priority_bp`, `signal_type`,
      `visibility` — the contract will refuse the first two and has no key for the last two, so
      this never produces a bad row. It produces the reason a row was refused, which is the
      part that would otherwise be lost;
    * **is an instruction echoed?** Here the input matters. The SAFETY block *instructs* the
      model to extract a directive as reported speech, so `"ignore previous instructions"` in
      the output is CORRECT when the message contained it — that is the extraction working. It
      is suspect only when the phrase is in the output and was NOT in the content, because then
      the model produced an instruction nobody sent it. Collapsing those two cases is how a
      guard ends up flagging every successful extraction of a phishing email and getting turned
      off.

    `fenced` is required, not optional, for exactly that reason: without the input scan the
    fourth question cannot be asked and the unit degrades into a phrase blocklist.
    """
    if not raw:
        raise ValueError("output is empty — an empty completion is a call failure for L1.4.3 to "
                         "park, not an injection verdict to compute")
    findings: list[OutputFinding] = []
    lowered = raw.lower()

    for name, marker in (("nonce", fenced.nonce), ("open marker", fenced.open_marker),
                         ("close marker", fenced.close_marker)):
        if marker.lower() in lowered:
            findings.append(OutputFinding(
                kind=FENCE_ECHOED,
                detail=f"the fence {name} appears in the output; the model is reproducing its "
                       "prompt rather than describing the message",
                quote=marker))
            break

    for literal in _FRAME_LITERALS:
        if literal in raw:
            findings.append(OutputFinding(
                kind=FRAME_ECHOED,
                detail=f"{literal} appears in the output; the instruction spine is being echoed "
                       "back instead of applied",
                quote=literal))
            break

    emitted = [name for name in SCHEMA_ENFORCED_ABSENT + ROUTING_FIELDS_ABSENT
               if name.lower() in lowered]
    if emitted:
        findings.append(OutputFinding(
            kind=FORBIDDEN_FIELD_EMITTED,
            detail=f"the output names {', '.join(emitted)}, which the extraction schema refuses "
                   "or does not define. The row would be rejected at the contract; this is the "
                   "reason why",
            quote=emitted[0]))

    in_content = {signal.kind for signal in fenced.signals}
    for spec in INJECTION_PATTERNS:
        match = spec.pattern.search(raw)
        if match is None:
            continue
        if spec.kind in in_content:
            findings.append(OutputFinding(
                kind=REPORTED_SPEECH,
                detail=f"a {spec.kind} phrase appears in the output and the content contained "
                       "one too — this is the SAFETY block working: the directive is extracted "
                       "as something the message said",
                quote=match.group(0)))
            continue
        findings.append(OutputFinding(
            kind=INSTRUCTION_ECHOED,
            detail=f"a {spec.kind} phrase appears in the output but NOT in the content, so the "
                   "model produced an instruction nobody sent it",
            quote=match.group(0)))

    risk = min(BP_FULL, sum(_OUTPUT_WEIGHTS_BP.get(kind, 0)
                            for kind in {finding.kind for finding in findings}))
    return OutputVerdict(suspect=risk > 0, findings=tuple(findings), risk_bp=risk)


__all__ = ["BP_FULL", "CLOSE_LABEL", "FENCE_ECHOED", "FENCE_FORGERY", "FENCE_LEAD", "FENCE_TAIL",
           "FORBIDDEN_FIELD_EMITTED", "FRAME_ECHOED", "FRAME_FORGERY", "INJECTION_PATTERNS",
           "INSTRUCTION_ECHOED", "NEUTRALISE", "NONCE_CHARS", "OPEN_LABEL", "REPORTED_SPEECH",
           "ROUTING_FIELDS_ABSENT", "SAFETY_MARKER", "SCHEMA_ENFORCED_ABSENT", "FenceEscape",
           "FencedContent", "InjectionPattern", "InjectionSignal", "OutputFinding",
           "OutputVerdict", "close_fence", "fence", "open_fence", "scan_output"]
