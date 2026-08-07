# Mechanism and persistence

Enqueue stamps the delivery object identity and context required for later drain. Result projection reads the same row and maps status/reason/attempt/timing facts into `DeliveryResult`.

All writes remain organization-scoped and reason-coded so retry/recovery cannot erase the original
attempt.
