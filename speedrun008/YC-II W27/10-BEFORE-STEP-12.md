# 10 · Before STEP-12 — every step before it, complete and aligned

**Written for:** Rohit, then Harsh. **As of:** 2026-10-10, at `db6328cd` (pushed).

On 10 Oct you gave STEP-12 its go on one condition: *"make sure ki step 12 se pehle step 0 se lekar
step 12 ke beech mein jitni bhi steps hain, saari ki saari cheezein completed hon, proper aligned hon
… us hisaab se hi build karna hai, ek-ek cheez."* This page is the answer: what was checked, what is
complete, what is not, and the block that closes the rest before STEP-12's first unit.

## 1 · How it was checked

Three read-only audits — STEP-00…04, STEP-05…08, STEP-09…11 — read every step file's promises (its
*Expected*, its *Verify*, its check and build record, its QA record) against the code at `db6328cd`,
and against your five documents (`09`). I re-checked their key claims by hand (the 45-day dormancy, the
missing `vendor` kind, the three verify paths that do not exist, the re-sync's warning). The last QA
run, at `bac34d35`, is green on every tier; nothing after it changed code.

## 2 · The answer, per step

| Step | Claude's build | What is NOT complete or not aligned |
|---|---|---|
| 00 one branch | complete | deploy (Harsh); B17–B19 measured only in production |
| 01 golden set | **not aligned** | 25 of 47 cases forbid nothing; forbidden phrases match as substrings (`marking.py:139`); follow-up *a* (the first-connect door) never built; **the ~11 cases `09` placed right after STEP-04 (the benchmark's shapes, a renewal, a verified close) never landed** |
| 02 change gate | complete, narrowed | its health check only proves the gate runs; no probe for flips or DEFER-expired cards; the targets disagree (`00` vs the step) |
| 03 gate keeps everything | complete, with orphans | `skim` handed to STEP-07 and never built; the AI filter still answers keep/drop and lists "automated matchmaking" (F02) |
| 04 who is us | complete | the repair does not re-type old nodes (the docs say it does); D6's Gmail address is not in Harsh's command; no case where our company domain is also the platform's |
| 05 every item enters memory | complete, one clause unbuilt | *"a later signal upgrades it"* is not built and not tested |
| 06 nothing lost silently | complete | its §6 verify names a test file that does not exist |
| 07 company brief | complete | its §6 verify names a missing file; the dashboard screen is not this repo's |
| 08 the re-sync | **not aligned** | the 365-day reach is a recommendation, not a check: `--apply` only warns on a short window, the health check passes at 60 days, and no test reaches past ~50 days |
| 09 workstreams | complete, two numbers unmeasured | "every investor in the brief has a file" and "one file per subject" are not measured; **no `vendor` kind** (`09` G5, D18) |
| 10 the expert's numbers | complete, two narrowings unrecorded | your reply time split by who wrote first; screen touches in the timeline; history (F113) still keyed by anchor only |
| 11 founder playbooks (M30) | complete | **D33 is data, not behaviour** — every file still goes quiet at 45 days; programmes still form investor situations, hidden today only because nothing is admitted; M31 after your review |

Every step also carries **status drift** — files that still say "pending Rohit's push", tree blocks still
`approved_in_progress`, deploy notes that name the wrong latest migration. None changes behaviour; all
of it misleads the next reader.

## 3 · The block that closes it — `yc2_w27_align` (M34), proposed

| | What | Why it comes before STEP-12 |
|---|---|---|
| **C1 the exam** | 11 new golden cases (F48–F58: five benchmark shapes, three brief-only, a renewal, a verified close, our company domain = the platform's) with labels; forbidden lists for the 25 cases without one; forbidden matched as a claim, not a substring; re-recorded; the board restated | STEP-12 is measured on this exam. Without these cases it would be measured without the benchmark's best items (`09` G1) |
| **C2 promised, not built** | the `vendor` kind; D33 in code (a file's quiet window by its kind); the re-sync's reach (refuse a short window, a check of how far memory reaches, an acceptance at 190 days); STEP-05's later-signal upgrade, measured then built or struck; F113; STEP-09's two numbers; STEP-02's probes; programmes never decided as investors; the first-connect door test | each is a promise a built step made, or an input the expert reads |
| **C3 decisions and the trail** | D15–D19 into `06`; D52–D55 for the narrowings; an owner for every orphaned deferral; a guard that keeps this folder consistent; the drift corrected, step files renamed | a plan that says something false is a plan nobody can trust |
| **C4 STEP-12 amended** | §8.8 and the units its check dropped: stage dwell, the time-passes what-if, a situation's lifecycle fields, history in the dossier, the portal's notices (F99), in-motion names (F125, F127), the expert proposing a kind (F132), the triggers per file | so STEP-12 builds everything its plan promised |

Units, artifacts and verify commands are in `tree.yaml`, block `yc2_w27_align`.

## 4 · Not Claude's — and they stay open

- **Harsh:** the deploy (`08` checklist); `GENIOS_L4_LLM_DECISION_MAKER`'s value; the Composio toolkit pin.
- **Rohit:** the two review sheets (D45); after the deploy D14, D23, the brief, the window (D5 / D16), D35;
  D42–D44, D48; the doctrine lines in your own documents (`09` G4); a second mailbox before any
  "beats an LLM" claim (`09` G8).
