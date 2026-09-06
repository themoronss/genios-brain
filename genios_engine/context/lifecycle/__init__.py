"""L2.7.7 · situation lifecycle — the parts of "when does this end" that were missing.

`context/situations.py` owns the lifecycle decision itself and always has. What it could not do
was hear somebody SAY a thing was finished: `terminal_by_fact` is one field (`deal.stage`), one
source, two values, so *"all sorted, we signed yesterday"* landed as fresh activity and made a
finished situation look more alive than it had before anyone said it was over.

This package is M-4 — the detector for that sentence — and it is deliberately split so that the
half which must be replayable has no database and no model in it:

    contract.py   the vocabulary, the two floors, the authority table
    authority.py  who said it (deterministic; the machine test runs first)
    gate.py       whether to spend a call at all
    prompt.py     what the model is asked, and what is accepted back
    judge.py      ALG-08, the authority weighting, the floors — the DECISION
    ledger.py     many claims about one situation, reduced to one word
    store.py      the SQL
    resolution.py the pass the drain runs

`detect_resolutions` is the entry point, and `context/runner.process_pending` calls it on every
drain, immediately after the situation refresh whose statuses it re-derives.
"""
from __future__ import annotations

from genios_engine.context.lifecycle.contract import (
    DetectionSweep,
    Message,
    Obligation,
    ResolutionClaim,
    ResolutionDescription,
)
from genios_engine.context.lifecycle.resolution import detect_resolutions

__all__ = ["DetectionSweep", "Message", "Obligation", "ResolutionClaim",
           "ResolutionDescription", "detect_resolutions"]
