# Rules and decision

Preference fields resolve independently in this order:

1. this seat + this channel;
2. this seat + all channels;
3. all seats + this channel;
4. tenant default.

`null` means “inherit,” so setting only a timezone does not erase the tenant quiet-hours policy.
Presence is accepted only for the same tenant/seat and while its lease is live. Invalid preference
values degrade to protective defaults and produce a visible configuration error instead of taking
another tenant’s drain down.

The resolved context is data, not a final verdict. Delivery Policy and Timing & Interruptibility
consume it and their decisions compose with “most restrictive wins” semantics.
