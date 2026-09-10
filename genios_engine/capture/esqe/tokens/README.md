# Token tables — the customer's own words

Three word lists decided whether a message raised a signal, and they were Python literals.

## What that cost

Anisha's clinic writes *"three no-shows this week and the ultrasound room is down for
calibration"*. No token in `RISK_TOKENS` matches — `no-show` and `calibration` are not in it —
there is no Commitment, no ResolvedDate and no Money, so `_detect_all` returns `[]`. Then
`classify_signals` returns `None`, `normalized` is empty, `importance` is an empty tuple, and the
ESQE trace records `signal_type=None, signals=0`.

The message was read, extracted, judged business-relevant, and produced **no signal**, because no
Python predicate recognised the customer's own vocabulary. That is the same shape as the
`thread.objective` zero-facts bite, one layer earlier.

## What stays in Python, and why

Only the **token tables** are the customer's language. The claim-shaped predicates — Commitment,
ResolvedDate, Money, Conflict — read typed contract objects and are genuinely universal: a
promise is a promise in every business. They are not here and must not move here.

## Shape

```yaml
signal_type: RISK_FLAGGED     # a member of contracts/signal.SignalType — never a new name
predicate_id: risk_topic      # what lands in the receipt, so a fire can be explained
tokens: [no_show, no-show, calibration, recall, incident]
```

`signal_type` must name an existing `SignalType`. A row naming anything else is skipped: the
enum is a REJECT boundary, the key of the precedence order and the type weight, and its own
docstring states the governance for adding one (a schema version bump plus corpus review). This
lane widens the WORDS that reach an existing kind; it does not mint kinds.

## Tokens are matched, not interpreted

A token matches the extraction's normalised topic tokens exactly. There is no stemming and no
fuzzy match, deliberately — `renew`, `renewal`, `renewals` and `renewing` are four rows in the
shipped table rather than one stem, because a stemmer that decides `renegotiation` is a renewal
is a decision nobody reviewed.
