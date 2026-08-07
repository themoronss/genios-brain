# Builder, Publisher and Output

The builder emits unit `outcome_analysis`, target `metrics`, and subject
`outcome:<capability>:<play>:audience:<acl-hash>`. It preserves exact outcome refs, independent
execution refs, source traces, execution-derived visibility and first/last seen times.

The shared publisher writes only the governed metric. Recommendation Learning and Knowledge
Evolution separately derive Adaptive and review-suggestion proposals from the same measurement and
record its learning ID in `metadata.derived_from`; derivation neither rereads sources nor increases
evidence.
