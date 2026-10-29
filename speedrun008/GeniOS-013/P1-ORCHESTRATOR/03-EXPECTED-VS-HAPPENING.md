# P1 · Orchestrator · 03 · What's expected, and what's happening

**Expected** comes from Rohit's own words:
- the launch film (26 Oct);
- Rohit's 29 Oct description of the loops: "new customer → data → notebook → business situation → goals → intelligence"; "new data → questioning from the angle of the business situations and goals → notebook update → … → cards"; "notebook → correlate, analyse, lifecycle → business situation → goals update → cards";
- GeniOS-009/010.

**Happening** is measured ([01](01-WHATS-EXACTLY-THERE.md)).

| # | Expected | Happening in the product | Happening in the notebook |
|---|---|---|---|
| 1 | **Proactive.** "You're not checking dashboards, not tagging anything, and not prompting more and more" | Sweeps run after each sync. L2 thinks only when mail arrives | A person runs commands |
| 2 | **"Exactly as my company's data evolves"**: new data is read through the situations and goals already known | L2 re-reads the whole file; nothing it concluded is kept | Each situation is re-read from its last saved page plus only the new mail (judge prints "what we concluded last time"). Goals are not used to question the new data |
| 3 | **What didn't happen is noticed**: a reply that should have come, a follow-up never sent | 138 of 138 L2 runs came from new mail; the expert pass has date triggers but a small budget | An overdue expected-by date makes a card, for every date, including stale ones from July |
| 4 | **"Every department, every goal, every situation"**: goals are where the work is organised | Goals sync from the brief only; none approved; 0 cards linked | Goals formed after the pages; cards don't come from goals |
| 5 | **One reading per situation, one piece of intelligence about it** | Three card makers; a subject repeats up to 9 times | One card per situation, but 63 cards against the ideal's 20 |
| 6 | **Onboarding gives useful intelligence on day one** | No first-day pass; the brain judges ~12 files a day | `all` runs in ~40 minutes for $8.41 |
| 7 | **Delegate to a person or an agent, and every Done teaches** | Card actions, executions and outcomes are stored but not read back into situations or goals | Not represented |
| 8 | **Maintain:** correlate, analyse, decay, prioritise, as routine | Card expiry and the maintenance sweep only | Not represented; the card flood shows it |
| 9 | **The company's own time** ("today 11:30" means today, 11:30, there) | Not measured here | UTC only; the `f1` card was wrong because of it |
| 10 | **Spend goes where it matters** | A day budget; the nearest deadline goes first in the expert pass | Ours first, then newest first. The cap is summed over all builds |
| 11 | **What ran, and why, can be seen** | Receipts per pass; `daily_health` per tenant; seven switches with no single list | Every model call logged; phases print counts; no record of a whole run |
| 12 | **A day forward costs little** | Not measured | Not run yet (the target is under $0.50 a day) |

## Where the notebook already matches what's expected

1. **Pages instead of re-reading.** A situation is re-judged from its saved page plus the new mail only: a 4.8k-character median dossier against the product's 70,000. This is what makes a daily loop affordable.
2. **The as-of discipline.** A build knows its instant. Nothing after it is read, including meetings the copy hadn't seen yet. A replay can therefore be honest, day by day.
3. **Ours first.** When the budget is short, the situations where we wrote or where something was asked are judged first.
4. **One gateway for the model.** Every call is priced, capped, logged and attributable.

These four stay. The plan in [04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md) builds the loops on them.
