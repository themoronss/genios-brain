# Inputs and context

The resolver keys every read by `org_id`, recipient seat and concrete channel. Its inputs are:

- the delivery candidate already materialized from an `ExecutionObject`;
- preference rows from most-specific seat+channel through tenant wildcard defaults;
- the latest unexpired `delivery_presence` lease for that seat;
- delivered intrusive-message history for the rolling hourly count; and
- an explicit timezone-aware evaluation time.

Presence contains activity, current surface, focus mode, optional `busy_until`, observation time
and mandatory expiry. A browser, desktop, mobile or agent client may publish it, but calendar
existence alone is not treated as proof of current activity.

Context participates throughout the safe pre-send window. Valid presence can influence the route
when the delivery is materialized, and the minute materializer refreshes queued rows whose attempt
ledger proves non-delivery. Policy, quiet hours, busy state and burst history are resolved again at
drain time. Once `started`, `unknown` or `delivered` evidence exists, recipient/route changes stop
being automatic because moving the intent could duplicate or leak it.
