# GeniOS-008 — the rules every piece of work follows

**Written for:** Rohit, Harsh and every coding agent, including Claude. **Set:** 18 Oct 2026, on Rohit's
instruction. A change to this page needs Rohit's yes.

## Rule 1 · All work is on the new architecture

1. **The architecture is [`00-ARCHITECTURE.md`](00-ARCHITECTURE.md)** (Design Atlas v2). It is the only
   target. The old flow in today's code — `capture/` → `context/` forms the situation → `packs/` +
   `reason/` → a `signals` row → a card — is **not** a target. It is what we migrate away from.
2. **Every item is judged against the new architecture, never against today's code.** If the code does
   something in the old place or the old way, that is a **finding to fix**. It is never a reason to call the
   item "already built", "not a defect", or "belongs in another layer".
3. **Every plan item cites the section of `00-ARCHITECTURE.md` it implements.** An item that cannot cite
   one is not in the plan.
4. **The architecture changes only by editing `00-ARCHITECTURE.md`, with Rohit's yes.** Nothing else
   (a STEP file, a finding, a convenient seam in the code) changes it.

## Rule 2 · How the migration is done — beside, never instead of

1. **Contracts first.** The new boundary objects (`ReasoningResult`, `DecisionObject`, `SituationSeed`,
   and the stored `QualifiedEnterpriseSignalBundle`) are written before any behaviour moves.
2. **The new path is built beside the old one, in shadow.** It writes its own rows and shows no card
   until it is switched on.
3. **The golden set compares the two paths.** A switch happens only when the new path scores at least as
   well as the old one on the board (must-detect, must-abstain, forbidden outputs).
4. **Switch one situation type at a time.** Each switch is one commit, with a one-line way back.
5. **The old path is deleted at the end.** A situation-forming site in `context/` disappears when its type
   has switched.
6. **What was already built is reused, not rebuilt.** See `02-MIGRATION-PLAN.md` §2 for each STEP and
   where it lands in the new architecture.

## Rule 3 · Guards that keep it from drifting again (they run in CI)

1. **The card guard:** after a type is switched, a card of that type must trace to a `ReasoningResult`.
2. **The ratchet:** the list of places in `context/` that create or refresh a situation can only
   **shrink**. A new site turns CI red.
3. **The layer guard:** a model call may live only where `00-ARCHITECTURE.md` allows one (L1 extraction
   and detection; L2's bounded pass; L5 and L6 wording and parsing). A new model call elsewhere turns CI red.

## Rule 4 · How we work, layer by layer

1. **Rohit opens each layer.** Nothing on a layer starts, not even a read-only audit, until he says so in
   that turn. He gives the layer's details, and the work follows them.
2. **Each layer folder has the same files:**
   - `00-START-HERE` — the layer's state on one screen;
   - `01-AS-IS` — measured against the new architecture;
   - `02-PLAN` — every item citing `00-ARCHITECTURE`;
   - `03-LOG` — append-only; a correction is a new line;
   - `04-FOR-HARSH` — what to pull, deploy, run and watch.
3. **Per change:** that change's own tests, plus a mutation check (the fix removed → its test fails). Then
   push to `speedrun008`. **The full suites run in CI, not locally.** No fresh scratch database unless the
   change touches SQL.
4. **Push per group of changes.** Do not wait idle for CI; read its result and fix what it finds.
5. **Harsh's note is written with the code, not after.** Every pushed group updates the layer's
   `04-FOR-HARSH`:
   - what changed;
   - the migrations;
   - the switches;
   - the commands;
   - what he should see;
   - how it goes wrong;
   - how to roll back.
6. **Questions are asked once, together, at the start of a layer.** After that, the work runs on the
   answers and on the recommended defaults written in the plan.

## Rule 5 · Words

1. **Layers are named by product number and package:** L1 `capture/`, L2 `reason/` + `packs/`, L3 `context/`,
   L4 `executive/`, L5 `deliver/`, L6 `feedback/`.
2. **No bare digit from another numbering.** `LAYERS.py` and the old dossier number layers differently.
