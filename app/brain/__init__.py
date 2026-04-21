"""Brain — reasoning loop.

Phase 2: event bus (Redis Streams) → router → detectors → reasoner → scorer → gate.
Output is logged only; dispatch to recommendations table lands in Phase 3.
"""
