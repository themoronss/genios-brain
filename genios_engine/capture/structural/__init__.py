"""L1.3 · the structural lane (Stage S1) — what a model must never be asked to find.

Two components live here and both are pure functions of bytes:

* `tokens` — ALG-04, the Structural Parser (L1.3.5). An ordered regex ruleset over
  `PreparedContent.clean_text` that records every objectively identifiable token with its
  character offsets. It runs BEFORE any model, and three consumers read its output without
  ever asking a model for it: the tier router (ALG-05) reads the currency and date counts,
  the conflict detector (ALG-12) compares a model-claimed amount against the literals that
  were actually present, and the span validator (L1.5.1) checks a claimed amount corresponds
  to a token found here.
* `threads` — ALG-03, the Thread Reconstructor (L1.3.6). Direction, turn index and whose turn
  it is, derived from the reply chain rather than guessed from a prompt. *An outbound offer
  read as an inbound request* is a fault this codebase has already shipped once.

**The separation these modules exist to enforce is find-versus-interpret.** `$84K` leaves
`tokens.scan` as a `currency_token` with a raw string and a pair of offsets and nothing else.
Turning it into `Money(8_400_000, "USD")` is ALG-10's job and happens LATER, in
`capture/validate/money.py`, precisely so the model's claim and the source's literal are two
comparable objects rather than one number nobody can audit.

PURE — no clock, no model, no database, no network, and no float. Offsets and counts are ints
because an offset that is 41.999999 is an offset that highlights the wrong character.
"""
