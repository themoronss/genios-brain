# Event vocabulary

Lifecycle entries use a fixed audit vocabulary: created, queued, delivery confirmed, started,
waiting, blocked/unblocked, reminded, escalated, reassigned, action completed, suppressed,
replanned, completed, cancelled, expired and archived.

Every transition carries reason code, actor, explicit time and detail. Queued is never rewritten
into delivered; transport confirmation remains a later event.
