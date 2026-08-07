# Immutability and round-trip

Contract values are frozen and canonicalized. Serialization followed by deserialization must
preserve meaning and identity. Time values are timezone-aware; scores and thresholds use integers
rather than ambient floating behavior.

Mutable lifecycle state is stored beside the contract, never by rewriting its semantic fields.
