"""L1 Capture — the only layer that touches raw customer data.

connect → acquire → land → preprocess → documents → gate → triage → gated_event.
This package is built stage-by-stage; landing spine is first.
"""
