# Admission types

`DeliveryCandidate` carries tenant/recipient/channel, band/interrupt intent and timing metadata.
Policy and timing return typed decisions: SEND, DEFER or SUPPRESS, each with stable reason and
optional next eligible time.

Combination is monotonic toward safety: suppression wins; the latest deferral binds; otherwise
send.
