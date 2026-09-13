"""The hot lane (SCREEN_INTEL_P3 / plan §6): the seat's graph slice, moment capabilities, guards.

    common.py   seat-visible read fragments (private facts / private evidence) + value parsing
    slice.py    GET /v1/seats/me/slice — full or delta, versioned per seat
    recall.py   moment.counterparty_recall (P-02) — deterministic, one hop, no LLM
    guards.py   shadow flag, DND, quiet hours, per-seat rate limits
    store.py    persist (transactional outbox), cache/dedupe, feedback, history, retention
"""
