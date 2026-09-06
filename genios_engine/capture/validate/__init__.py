"""L1.5 · the pure validators — the layer that turns what a model said into what can be checked.

ALG-08 spans, ALG-09 dates, ALG-10 money, ALG-13 confidence. Every module in here is a pure
function over contract types: no database, no network, no model call, no clock read, and no
float. Those are not testing conventions, they are the reason this package can be replayed —
a validator that reads a clock resolves last March's "next week" against today, and a
validator that calls a model is just another extractor wearing a validator's name.
"""
