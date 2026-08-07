# Validation dimensions

Validation checks observations, distinct days, confidence, noise, conflict, freshness and business
value. Each dimension has an integer threshold and a stable reason code. Repetition/confidence can
hold a candidate; excessive noise/conflict, stale evidence or low value can reject.

Explicit Runtime memory follows a separate TTL-safe one-observation rule.
