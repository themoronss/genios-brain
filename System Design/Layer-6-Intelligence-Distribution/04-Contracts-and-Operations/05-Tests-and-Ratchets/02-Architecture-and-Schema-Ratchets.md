# Architecture and schema ratchets

Topology tests allow `deliver/` to consume Layer 5 but prevent it from importing Atlas Layer 6
feedback authority. Schema tests protect preference, delivery and presence columns/indexes and
tenant erasure behavior.

Adapter contracts keep channel implementations substitutable without granting them policy power.
