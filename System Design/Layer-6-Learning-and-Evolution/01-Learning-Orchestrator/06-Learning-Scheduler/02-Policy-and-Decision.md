# Policy and decision

Expiry runs first. A unique weekly claim prevents duplicate replicas/retries. Claim, load, objects, transitions, publication and completion commit together or roll back.

The same batch, policy and evaluation time produce the same decision. Every hold/reject/review path
is reason-coded.
