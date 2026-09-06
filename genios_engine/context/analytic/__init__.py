"""L2.4 · the ANALYTIC STRATUM — what is true ACROSS entities and ACROSS time.

Every other package in `context/` answers a question about one subject as it stands now. This
one answers the two questions no per-subject read can: *how does this compare to its own past*
and *how does it compare to its peers*. Both need a stored series, which is why `history.py` is
the first thing here and everything else in the group reads from it.

The measurement is deterministic and integer-only by design (doc 04): a comparison needs a
stable measuring instrument, and a trend judged by a model in March and again in September
produces a disagreement that can be attributed neither to the business nor to the model.
"""
