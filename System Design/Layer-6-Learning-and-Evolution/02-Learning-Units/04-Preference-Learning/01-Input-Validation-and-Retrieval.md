# Input, Validator and Retriever

## Input / Validator

All preference fields must be present. Values are canonically serialized for grouping so semantically identical structure has stable identity.

## Retriever

The batch contains current canonical explicit feedback; silence and inferred behavior are excluded.

The unit never crosses tenant boundaries and never replaces missing source evidence with generated
facts.
