# Defer, suppress and cancel

DEFER changes `next_attempt_at` and `defer_count` without touching attempts. SUPPRESS is terminal
policy refusal. CANCEL means the underlying work/authority is no longer live.

Keeping all three prevents quiet hours, opt-out and subject closure from collapsing into the same
operator diagnosis.
