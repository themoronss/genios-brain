"""M1.C1.L-logic.V2.U04 · a receipt that lands in reply history is not a receipt for this message.

    pytest tests/capture/semantic/test_history_evidence.py -q

THE FOURTH OUTCOME. `bind_evidence` had three: the claim brought its own receipt, the binder
synthesized one, or the claim was dropped for having none. All three assume that a quote found in
`prepared_text` is a quote from THIS message. Mail is quoted, so that assumption is false for
every reply: the raw body of a twelfth-turn message contains eleven older ones, and a model
reading it extracts eleven older messages' claims and dates them today.

MEASURED ON THE PILOT before this check existed:

  * 23 qualified signals whose entire receipt was an attribution line. One of them,
    "On Sat, 8 Aug 2026 at 14:22, Manik Pasricha wrote:", was stored as a `financial_obligation`
    at 4560 bp — the SECOND-HIGHEST importance on the whole tenant.
  * ~60 signals that were one sentence counted once per message that quoted it. Rohit wrote
    "we can expect the numbers to hit nearly ~$2-3k MRR" once; it produced ten `contract_renewal`
    signals across ten events. Measured: `copies == distinct_events` in every duplicate group,
    and 395 signal rows are 395 distinct (event, type, quote) triples — no within-event
    duplication anywhere, so deduplication was never the fix.

The half that matters most is the second block of tests: a live claim in a reply must survive.
A guard that drops the sender's own sentence because the message happens to quote something is
worse than the defect.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.semantic.evidence_binder import ClaimDraft, bind_evidence
from genios_engine.contracts.evidence import EvidenceSpan

pytestmark = pytest.mark.unit

SOURCE_REF = "prepared_content:evt_history"

# The exact shape the pilot produced.
REPLY = (
    "Thanks — I'll send the signed order form on Thursday.\n"
    "\n"
    "On Sat, 8 Aug 2026 at 14:22, Manik Pasricha wrote:\n"
    "> As we can see the need of the product, we can expect the numbers to hit\n"
    "> nearly ~*$2-3k MRR*.\n"
)
NO_HISTORY = "I'll send the signed order form on Thursday."


def draft(claim_text: str, *, evidence: tuple[EvidenceSpan, ...] = ()) -> ClaimDraft:
    return ClaimDraft(field="commitments", claim_text=claim_text, confidence_bp=8_000,
                      evidence=evidence)


def span_for(quote: str, text: str) -> EvidenceSpan:
    """A receipt built by FINDING the quote, so no test here hand-counts an offset."""
    start = text.find(quote)
    assert start >= 0 and text.find(quote, start + 1) < 0, f"bad fixture quote {quote!r}"
    return EvidenceSpan(source_ref=SOURCE_REF, quote=quote, start_offset=start,
                        end_offset=start + len(quote), verified=False)


def bind(*drafts, text: str = REPLY):
    return bind_evidence(drafts, prepared_text=text, source_ref=SOURCE_REF)


# =============================================================================================
# The defect, stated directly.
# =============================================================================================
def test_a_claim_standing_only_on_the_quoted_thread_is_refused():
    """The ten `contract_renewal` signals. Rohit wrote this sentence once, months ago; ten later
    messages quoted it back at him and each one produced a signal."""
    quoted = span_for("we can expect the numbers to hit", REPLY)

    out = bind(draft("revenue expectation", evidence=(quoted,)))

    assert out.claims == ()
    assert out.counters.quoted_history == 1


def test_the_attribution_line_itself_is_refused():
    """The 4560 bp `financial_obligation`. An attribution line is not a business claim no matter
    who is named in it."""
    header = span_for("On Sat, 8 Aug 2026 at 14:22, Manik Pasricha wrote:", REPLY)

    out = bind(draft("payment reference", evidence=(header,)))

    assert out.claims == ()
    assert out.counters.quoted_history == 1


def test_a_synthesized_receipt_found_only_in_history_is_refused_too():
    """The recovery path must not become the way around the guard. A model that cites nothing and
    whose words appear only in the quoted thread has still read somebody else's message."""
    out = bind(draft("nearly ~*$2-3k MRR*"))

    assert out.claims == ()
    assert out.counters.quoted_history == 1
    assert out.counters.synthesized == 0


def test_history_drops_are_counted_apart_from_hallucinations():
    """`no_evidence` blocks a prompt release; this must not inflate it. They say opposite things:
    one is a model asserting what the message does not say, the other is a model reading a real
    sentence from the wrong day."""
    out = bind(draft("the moon is a hologram"),
               draft("nearly ~*$2-3k MRR*"))

    assert out.counters.no_evidence == 1
    assert out.counters.quoted_history == 1


# =============================================================================================
# And the half that matters more — a real claim in a reply must survive.
# =============================================================================================
def test_the_senders_own_promise_in_a_reply_still_binds():
    """THE REGRESSION THIS GUARD COULD CAUSE. Almost every real commitment on the tenant arrives
    in a reply. Dropping live text because the message quotes something would be worse than the
    defect it fixes."""
    live = span_for("I'll send the signed order form on Thursday", REPLY)

    out = bind(draft("send the order form", evidence=(live,)))

    assert len(out.claims) == 1
    assert out.claims[0].evidence == (live,)
    assert out.counters.carried_own_evidence == 1
    assert out.counters.quoted_history == 0


def test_a_claim_keeps_its_live_receipt_and_loses_only_the_historical_one():
    """Per receipt, not per claim. Stapling a quoted sentence beside a real one must not cost the
    real one, and must not buy the quoted one a way through."""
    live = span_for("I'll send the signed order form on Thursday", REPLY)
    quoted = span_for("nearly ~*$2-3k MRR*", REPLY)

    out = bind(draft("send the order form", evidence=(live, quoted)))

    assert len(out.claims) == 1
    assert out.claims[0].evidence == (live,), "the historical receipt is not a receipt here"
    assert out.counters.quoted_history == 0, "the claim survived, so nothing was refused"


def test_a_message_with_no_history_is_completely_unaffected():
    """Bit-identical behaviour for a first-turn message, which is what makes this safe to ship:
    the guard cannot change any outcome on text it finds no history in."""
    live = span_for("send the signed order form", NO_HISTORY)

    out = bind(draft("send the order form", evidence=(live,)), text=NO_HISTORY)

    assert len(out.claims) == 1
    assert out.claims[0].confidence_bp == 8_000
    assert out.counters.quoted_history == 0


def test_confidence_is_untouched_by_the_guard():
    """The binder does not second-guess a receipt it keeps. This unit refuses or it does not; it
    never prices."""
    live = span_for("I'll send the signed order form on Thursday", REPLY)

    [bound] = bind(draft("send the order form", evidence=(live,))).claims

    assert bound.confidence_bp == 8_000
    assert bound.synthesized is False


def test_a_quote_that_straddles_the_boundary_is_refused():
    """Any overlap disqualifies. Full containment would make the guard avoidable by widening the
    quote until it reached back into the live text."""
    start = REPLY.index("wrote:")
    straddle = EvidenceSpan(source_ref=SOURCE_REF, quote=REPLY[start:start + 30],
                            start_offset=start, end_offset=start + 30, verified=False)

    out = bind(draft("straddling claim", evidence=(straddle,)))

    assert out.claims == ()
    assert out.counters.quoted_history == 1


def test_the_denominator_still_counts_every_claim():
    """`claims_in` must survive the new drop, or a prompt that lost everything to history would
    report a clean rate."""
    out = bind(draft("nearly ~*$2-3k MRR*"),
               draft("send the order form",
                     evidence=(span_for("I'll send the signed order form on Thursday", REPLY),)))

    assert out.counters.claims_in == 2
    assert out.counters.bound == 1
