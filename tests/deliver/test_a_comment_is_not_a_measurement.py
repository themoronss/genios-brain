r"""A comment is not a measurement, and a module header that undercounts its own surface is worse.

⛔ FOUR STALE STATEMENTS IN ONE SUBSYSTEM, all measured 2026-10-01, and in every single case **the
behaviour was correct and only the sentence a human reads was wrong** — so no test failed, no receipt
went red, and the error was invisible until somebody answered a question from it.

    deliver/push.py:19        "push_card_to_agents -- proactive ... (fired by L5 when a card is
                              emitted)".  ⛔ Nothing fired it. Agents receive by POLLING
                              (`agent_api.poll_signals`), and `push.py`'s own next line says the
                              bodies are identical -- so pushing would change WHO initiates, not
                              WHAT arrives.

    deliver/push.py:18-22     ⛔ "Two flavours, one transport:" followed by ONE bullet, and then a
                              line beginning "in the org that registered a webhook" -- the orphaned
                              TAIL of a deleted `push_action_to_agents` bullet. The block said two
                              and listed one, and the leftover fragment read as a sentence.

    deliver/units.py:70       "`channels/base.get_channel` returns Slack or None -- one
                              implementation across every push channel named here."  ⛔ It returns
                              Slack **or** `AgentWebhookChannel`. `channels/agent.py` is the LARGEST
                              adapter in that folder and landed two days after `base.py`. And this
                              sentence is the JUSTIFICATION for `PUSH_REQUIRES_ADAPTER`, so a reader
                              deciding whether to build the agent adapter was told to build a second
                              one.

    tests/test_delivery_units.py:67   ⛔ THE SAME CLAIM, IN A TEST DOCSTRING. The wrong sentence
                              propagated into the test guarding the thing, so anyone checking
                              whether the claim was guarded found a test that repeated it. Its
                              ASSERTIONS were always correct -- they are about `teams`, which
                              genuinely has no adapter.

⛔ WHY PROSE CANNOT BE GUARDED BY GREPPING FOR THE WRONG WORDS. The obvious guard -- assert the
string "returns Slack or None" appears nowhere -- **fails on the corrected comment**, which says
*"this comment said 'returns Slack or None' until 2026-10-01"*. A grep for a known-false phrase
matches the record of its own correction. That would have been the seventeenth time a substring check
in this programme matched the author's own words.

**So a factual claim is guarded by making the fact DERIVABLE and naming it in exactly one place**, and
a missing claim is guarded structurally. That is what the four tests below do, and none of them reads
prose for correctness.
"""
from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path

from genios_engine.deliver import delivery_health as H
from genios_engine.deliver.channels.base import get_channel
from genios_engine.deliver.units import (CHANNEL_NEEDS_CREDENTIAL, PUSH_REQUIRES_ADAPTER,
                                         _implemented_channels)

_PKG = Path(H.__file__).resolve().parent

#: ⛔ Adapters that exist, named here ON PURPOSE rather than derived. A derived assertion would
#: pass forever and never make anybody look at the prose that explains the set. Naming them means a
#: third adapter fails this test, and whoever lands it has to come here and read the comment in
#: `units.py` that justifies `PUSH_REQUIRES_ADAPTER` -- which is the only moment that comment is
#: ever going to be re-read.
_ADAPTERS_THAT_EXIST = frozenset({"slack", "agent_push"})

#: ⛔ A CLOSED SET OF VERBS, not a general language model. A comment asserting that a function IS
#: called is the dangerous shape; a comment describing what it WOULD do is fine and common. These
#: are the phrasings that make a claim about wiring.
_CLAIMS_A_CALLER = (
    "fired by", "fired when", "is fired", "called by", "is called",
    "invoked by", "is invoked", "triggered by", "is triggered", "runs when", "is run by",
)


def _comments(path: Path) -> list[tuple[int, str]]:
    """Every COMMENT token in one file — ⛔ from the token stream, never from a docstring.

    `ast.get_docstring()` returns CLEANED text while the node holds RAW, and this programme has been
    bitten by that once already: excluding a docstring by value let it through and a test failed on
    its own prose. Comments are a separate token type, so there is no ambiguity about what is being
    read.
    """
    src = path.read_text(encoding="utf-8")
    return [(t.start[0], t.string) for t in tokenize.generate_tokens(io.StringIO(src).readline)
            if t.type == tokenize.COMMENT]


# ---------------------------------------------------------------------------------------------
# 1 · ⛔ the general guard — this is the one that outlives the four corrections
# ---------------------------------------------------------------------------------------------

def test_no_comment_claims_a_declared_unreached_function_is_called() -> None:
    """⛔ THE GENERAL FORM OF THE SPECIFIC DEFECT, and the reason this step is not just four edits.

    `delivery_health` declares 25 functions that production does not call. A comment asserting that
    one of them IS called is a statement somebody will act on -- the next person asking *"do agents
    get notified when a card is emitted?"* read `push.py:19`'s parenthesis and answered yes.

    **A guard written for one member of a closed table is half of that**, so this walks the whole
    table rather than the one entry that was wrong. It is scoped to `deliver/`, where the
    declaration lives; the engine-wide form needs `STEP-17` first.
    """
    declared = {q.split(".", 1)[1]: q for q in H.DECLARED}
    offenders = []
    for path in sorted(_PKG.glob("*.py")):
        for lineno, comment in _comments(path):
            low = comment.lower()
            for fn, qualified in declared.items():
                if fn in low and any(verb in low for verb in _CLAIMS_A_CALLER):
                    offenders.append((f"{path.name}:{lineno}", qualified, comment.strip()[:90]))
    assert not offenders, (
        "a comment asserts that a function declared as uncalled is called -- the comment is the "
        f"lie, not the declaration: {offenders}")


def test_the_guard_can_actually_fire() -> None:
    """⛔ A guard that matches nothing passes on any codebase. This proves the detector works, using
    the exact comment that was removed from `push.py:19` rather than a synthetic one."""
    declared = {q.split(".", 1)[1]: q for q in H.DECLARED}
    removed = ('#   • push_card_to_agents   — proactive "here\'s a new signal" '
               "(fired by L5 when a card is emitted).")
    low = removed.lower()
    assert any(fn in low and any(v in low for v in _CLAIMS_A_CALLER) for fn in declared), (
        "the detector no longer recognises the comment it was written for -- either the verb set "
        "or the declaration changed, and this test is the only thing that would have said so")


# ---------------------------------------------------------------------------------------------
# 2 · ⛔ the adapter set — a fact made derivable, and named in exactly one place
# ---------------------------------------------------------------------------------------------

def test_the_implemented_adapter_set_is_computed_and_not_described() -> None:
    """`_implemented_channels()` must equal the set you get by CALLING `get_channel`.

    ⛔ This is why the `units.py` comment being wrong never broke anything: the behaviour was always
    computed at runtime, so `capability_report` has been right all along. Only the sentence was
    wrong -- **the dangerous combination**, because nothing fails.
    """
    computed = frozenset(ch for ch in PUSH_REQUIRES_ADAPTER if get_channel(ch) is not None)
    assert _implemented_channels() == computed, (
        "the implemented set is being described rather than computed")
    assert computed == _ADAPTERS_THAT_EXIST, (
        f"the adapter registry changed: {sorted(computed)} vs the named "
        f"{sorted(_ADAPTERS_THAT_EXIST)}. ⛔ Update _ADAPTERS_THAT_EXIST here AND the comment above "
        "`PUSH_REQUIRES_ADAPTER` in units.py, which explains the set and went four weeks out of "
        "date the last time an adapter landed without anybody re-reading it")


def test_four_of_the_six_push_channels_still_have_no_adapter() -> None:
    """⛔ Stated as a number so it is a measurement rather than an impression — the same discipline
    `executive/unreached.py` applies to its own count.

    `api`, `email`, `teams` and `webhook` have no implementation at all. ⛔ **Not a code defect**:
    `capability_report` reports every one of them fail-closed and names `no_adapter` as OUR gap
    rather than the tenant's. It is a deployment and product fact, and it is pinned here so that
    building one is a deliberate edit rather than a surprise.
    """
    missing = PUSH_REQUIRES_ADAPTER - _implemented_channels()
    assert missing == {"api", "email", "teams", "webhook"}, sorted(missing)
    assert len(PUSH_REQUIRES_ADAPTER) == 6
    # every channel with no adapter still needs a credential, so none of them can be reported
    # operational by the looser of the two gates either
    assert missing <= CHANNEL_NEEDS_CREDENTIAL


# ---------------------------------------------------------------------------------------------
# 3 · ⛔ a header that undercounts its own surface
# ---------------------------------------------------------------------------------------------

def test_every_push_entry_point_is_named_in_the_module_header() -> None:
    """⛔ THE DELETED BULLET, GUARDED GENERALLY.

    `push.py`'s header announced *"Two flavours, one transport:"* and listed ONE, because the
    `push_action_to_agents` bullet had been deleted and its second half -- *"in the org that
    registered a webhook (Hermes or the client's own tool)"* -- was left behind, reading as a
    sentence about the bullet above it.

    This asserts that **every `push_*` entry point appears in the leading comment block**, so a
    deleted bullet or a new flavour both fail here. ⛔ It checks COVERAGE, not correctness: it does
    not read the prose for meaning, only for whether the surface is accounted for. The scope is
    `push_*` rather than every public function on purpose -- `authoritative_card_projection` is the
    projection both flavours share, not a flavour, and demanding the header list it would be
    asserting a convention the module never adopted.
    """
    path = _PKG / "push.py"
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    first_statement = min(
        (n.lineno for n in tree.body
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Assign))),
        default=10 ** 9)
    header = " ".join(c for line, c in _comments(path) if line < first_statement)
    flavours = sorted(n.name for n in tree.body
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and n.name.startswith("push_"))

    assert len(flavours) == 2, (
        f"push.py now has {len(flavours)} push entry points: {flavours}. The header says 'Two "
        "flavours' -- update both or neither")
    missing = [f for f in flavours if f not in header]
    assert not missing, (
        f"these push entry points are not named in push.py's header: {missing}. A header that "
        "announces a count and lists fewer is how a deleted bullet leaves its tail behind")


def test_the_unwired_flavour_is_declared_and_the_fail_closed_one_is_too() -> None:
    """Both halves of `push.py` are in `delivery_health`, for opposite reasons, and the header now
    says which is which: one is PULL_ONLY, the other raises on purpose.

    ⛔ Pinned as a pair because filing them under one reason is exactly what three tables exist to
    prevent -- *wiring the fail-closed shim is the incident it exists to refuse.*
    """
    assert "push.push_card_to_agents" in H.UNREACHED
    assert "push.push_action_to_agents" in H.UNREACHED
    assert "agent_api.poll_signals" in H.PULL_ONLY, (
        "the pull half must stay declared, or the reason the push half can be unwired disappears")
    assert H.now_called() == (), f"a declared entry acquired a caller: {H.now_called()}"
