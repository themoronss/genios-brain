# Bridge contract

Layer 5 records the decision to communicate and its grounded fact corpus. Because Layer 5 cannot
import Layer 5.2, `deliver/executive_bridge.py` reads eligible Executive events and creates the
delivery row from below in the layer graph.

The bridge may format a transport candidate; it may not change owner, channel intent, urgency or
the reason Layer 5 recorded.
