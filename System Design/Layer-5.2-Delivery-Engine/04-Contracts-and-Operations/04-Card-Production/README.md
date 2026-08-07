# Card Production

Builds and validates an execution-bound human-readable intelligence artifact. A card is a grounded presentation/read model consumed by Delivery Units; it is not an independent transport job or execution authority.

**Primary authority:** `card_builder.py`, `pipeline.py`, `render.py`, `slots.py`, `store.py`, `actions.py`

Only open signals with a live execution are eligible for card production. The card persists `execution_id`, source evidence and authority lineage. The Delivery Engine separately materializes the outbound logical delivery from the execution/event seam.

## Component modules

1. [Slots and Grounding](01-Slots-and-Grounding.md)
2. [Rendering and Validation](02-Rendering-and-Validation.md)
3. [Actions Bands and Digest](03-Actions-Bands-and-Digest.md)
