"""16-U2 · where a message sits in its thread, from the headers the message already carries.

⛔ **THE DEFECT THIS CLOSES IS NOT A MISSING FIELD. IT IS A WRONG ONE, STATED CONFIDENTLY, ON EVERY
EXTRACTION THIS PRODUCT HAS EVER RUN.**

`pipeline._thread_place` reads `raw["thread_position"]` and `raw["thread_depth"]` and falls back to
`(1, 1)`. The fallback is correct and well-argued — *"a single message with no thread metadata is
genuinely the first of one"*. **No connector has ever supplied the metadata.** So `_envelope_block`
renders this into every prompt in production:

    thread position: message 1 of 1

The twelfth turn of a renewal negotiation is described to the model as the first and only message in
its thread, and `ThreadContext.turn_index` is 0 for the entire corpus. A missing field fails loudly
at the first reader; a **wrongly-stated** one never fails at all.

**THE HEADER WE WERE ALREADY CAPTURING ANSWERS IT, FOR FREE.** RFC 5322 §3.6.4: `References` holds
the parent's `References` plus the parent's `Message-ID`, oldest first. N references means N
ancestors, so this message is the (N+1)th. Gap 2 of this step captures that header for
`assemble_chain`; the position falls out of the same read.

**WHY NOT `threads.get`.** It would give an exact thread size, and it costs one request per thread
against a shared rate limit on every sync. §9 is explicit that the goal is not *"fetch everything"*
but *"know what we fetch, and why we do not fetch the rest"* — so the choice is recorded in
`manifest.py` rather than paid for.

**WHY `depth` EQUALS `position`.** One message cannot state its thread's total size, and inventing
one would be precisely the failure step 15 was built to end: reporting the size of what we hold as
the size of what exists. `_thread_context`'s own docstring already settles the honest reading —
*"at capture time this event genuinely IS the newest message of its thread"* — so `(4, 4)` says
**"message 4, and the newest so far"**. That is the same claim the existing `(1, 1)` default makes
for a lone message. This generalises that default; it does not replace it.
"""
from __future__ import annotations

import re

#: A `Message-ID` token. Angle brackets are the spec, and a relay that strips them is common enough
#: that refusing the bare form would silently read a real reply as an opening message — the bug.
_MESSAGE_ID = re.compile(r"<([^<>]+)>")


def _ids(raw: str | None) -> list[str]:
    """Message-ids from one header value, **order preserved and duplicates removed**.

    Deduplicated because a broken client repeats an ancestor and a repeated id would inflate the
    position. An inflated position is a confident lie in exactly the way the current one is — the
    fix must not swap a wrong number for a different wrong number.
    """
    text = (raw or "").strip()
    if not text:
        return []
    found = _MESSAGE_ID.findall(text)
    if not found:
        # A relay rewrote the header without angle brackets. Whitespace-separated is the only
        # shape worth salvaging; anything else is not a message-id list.
        found = text.split()
    seen: dict[str, None] = {}
    for one in found:
        token = one.strip().strip("<>")
        if token:
            seen.setdefault(token, None)
    return list(seen)


def thread_place_from_references(*, references: str | None,
                                 in_reply_to: str | None) -> tuple[int, int]:
    """`(position, depth)` for one message, derived from its own threading headers.

    Returns the pair `_thread_place` reads, in the shape `EventEnvelope` validates: 1-based, and
    never a position past its depth.

    * no headers → `(1, 1)`, an opening message, **and the string it renders is unchanged** — which
      is what keeps the extraction cache warm for every non-reply in the corpus;
    * `In-Reply-To` with no `References` → `(2, 2)`. Some clients send only the former, and reading
      `(1, 1)` there would tell the model an obvious reply opened its thread;
    * N unique references → `(N + 1, N + 1)`.

    The parent is counted only when `References` did not already name it, which is the normal case:
    a well-formed `References` ends with the `In-Reply-To` value.
    """
    ancestors = _ids(references)
    parent = _ids(in_reply_to)
    for one in parent:
        if one not in ancestors:
            ancestors.append(one)
    position = len(ancestors) + 1
    return position, position


def reference_ids(references: str | None) -> tuple[str, ...]:
    """The `References` header as the tuple `ThreadMessage.references` declares, oldest first.

    The SAME parser `thread_place_from_references` counts, deliberately. Two readings of one header
    is how a prompt saying "message 4 of 4" ends up beside a three-link chain, and a disagreement
    between the position and the chain would be unfalsifiable from either side.
    """
    return tuple(_ids(references))


__all__ = ["reference_ids", "thread_place_from_references"]
