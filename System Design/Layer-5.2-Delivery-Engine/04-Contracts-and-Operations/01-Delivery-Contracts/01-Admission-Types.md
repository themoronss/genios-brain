# Admission types

## DeliveryCandidate

`DeliveryCandidate` carries `org_id`, `subject_id`, proposed `channel`, `channel_class`, importance `band`, interrupt intent and optional recipient. The constructor validates the enum-shaped values. Its `intrusive` property derives from channel physics: it is true only for `ChannelClass.CHAT`, independently of the presentation-level interrupt flag.

The candidate is not yet a durable delivery. Audience resolution, destination, format, route plan, priority and execution lineage are materialized later into `DeliveryObject`.

## AdmissionDecision

Admission produces one typed verdict:

- `SEND`: the current candidate may proceed;
- `DEFER`: retry at the timezone-aware `not_before` time; or
- `SUPPRESS`: terminal policy refusal.

Every non-send decision carries a stable reason code. A defer without an aware future clock is invalid.

Combining independent decisions is monotonic toward safety: suppression wins, otherwise the latest deferral binds, otherwise send. No later permissive rule can erase an earlier suppression or shorten a required hold.
