"""Golden-replay harness — the acceptance layer every phase exit gate in the program depends on.

The twelve replays in `Rohit_Updates/Secret War Updates/09-Golden-Replays/` are SPECIFICATIONS,
not bug reports. Each names a business situation, the decision the system must reach, and — the
part that matters — a table of deterministic mutations: change one input, and the required
decision changes in a stated way. That table is the only thing that can tell "the card looked
reasonable" apart from "the system reasoned correctly", so until it is executable, every exit
gate in the implementation program is an opinion.

Three properties this harness must have, in priority order:

  HONEST         A replay assertion the engine cannot express is marked blocked, not skipped and
                 not quietly weakened. Most mutations depend on machinery that does not exist yet
                 (counterparty roles, an abstention vocabulary, thread state, an execution weld),
                 and a suite that pretends otherwise is worse than none — it certifies the gap.
                 Blocked assertions are `xfail(strict=True)`, so the day the capability lands the
                 test fails *because it passed* and the marker has to be deleted.

  PINNED         Fixtures carry their own clock, graph version, corpus version and config
                 snapshot. A replay that reads `datetime.now()` has stopped being a replay.

  DETERMINISTIC  Every replay runs twice with the LLM disabled and must produce identical
                 decisions. If a decision moves while its inputs do not, the reasoning is not
                 deterministic, and no amount of prompt work repairs that.
"""
