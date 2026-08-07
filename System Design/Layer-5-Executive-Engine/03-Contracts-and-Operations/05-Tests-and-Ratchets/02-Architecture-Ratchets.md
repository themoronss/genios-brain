# Architecture ratchets

`tests/test_layer_topology.py` prevents Layer 5 from importing `deliver/` or `feedback/`.
Contract/schema tests prevent required tables, columns and cascade rules from disappearing.
Serialization tests protect immutability and stable identity.

These are build failures, not review conventions.
