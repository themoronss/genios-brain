# Actions, bands and digest

Card actions are typed (`run_play`, `do_it_myself`, `snooze`, `wrong`, `requeue`), revalidate authority and write both human and card audit events. Presentation bands inform card treatment and routing inputs, but action handling cannot bypass the execution boundary.

Card presentation has its own surfaced-state budget. Outbound intrusive attention is separately enforced by the Delivery Engine's frozen daily and hourly database reservations. The two controls must not be described as one counter.

An `enqueue_digest(...)` implementation can build a stable non-intrusive aggregate, but the active `run_distribution(...)` loop does not currently invoke it. Scheduled digest production is therefore an integration gap, not a fully active runtime path.

Card interaction and delivery receipt are separate evidence. Neither, by itself, proves the downstream Layer 5 business outcome.
