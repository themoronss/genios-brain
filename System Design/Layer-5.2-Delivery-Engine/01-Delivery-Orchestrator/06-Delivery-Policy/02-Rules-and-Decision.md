# Rules and decision

Rules are ordered by blast radius so the recorded reason names the real cause:

1. failed execution authority/hash/current-reminder or source-visibility proof -> cancel or reject
   before any provider attempt;
2. disabled tenant -> `SUPPRESS`;
3. active tenant hold -> `DEFER` to its stated end;
4. inactive/unregistered channel -> `SUPPRESS`;
5. below channel minimum band -> `SUPPRESS`;
6. inactive recipient -> `SUPPRESS`;
7. recipient opt-out -> `SUPPRESS`;
8. otherwise -> `SEND`.

Policy is evaluated before timing. A terminal policy refusal cannot be made louder by a timing
decision; a timed tenant hold and timing deferrals compose to the latest opening. No LLM can
override these rules.
