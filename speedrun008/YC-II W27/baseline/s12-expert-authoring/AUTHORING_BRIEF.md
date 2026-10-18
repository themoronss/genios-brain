# Brief — author the expert's answers for a batch of golden cases (STEP-12, `06` D49)

You are writing, for a set of golden test cases, the answer a faithful strong model would give when the
GeniOS "expert" (R-7) reviews one FILE — one piece of the founder's work (an investor, a programme, a
hire, an intro…). The golden set's "ideal reader" serves these answers to the real prompts so the engine
can be tested end to end without spending on a live model. Decision `06` D49: Claude writes them, per
case, from the case's own text, each marked `claude`.

Repository (read only — do NOT edit any file in it):
the repository root
Scratch folder (write here only):
a scratch folder outside the repository
(below: `S12`).

## Inputs, per case id (e.g. F21)

1. The case: `tests/replays/specs/founder/<ID>.json` in the repository — its objects (the mails and
   meetings), `kind` (`must_detect` or `must_abstain`), `expected`, `forbidden`, and `notes`. This is the
   story; read it first.
2. The expert prompts the case's sweeps produce: `S12/probe/<ID>.json` — a list of `{"key", "prompt"}`,
   one per distinct prompt, in the order the chain asked. `key` names the FILE (its counterparty key).
   Each `prompt` is the full checklist prompt; the part between `<dossier>` and `</dossier>` is what the
   expert is shown. A file may have several prompts (later sweeps); the FIRST one is its first dossier.
3. `tests/replays/expert_files.json` (built by `build_expert_files.py` from the probe) — per case, per file key: `evidence` (every id the file's FIRST dossier
   prints in square brackets — the only ids you may cite) and `stages` (the stage names its playbook
   lists, or empty).
4. The shape: `genios_engine/reason/expert/prompt.py` (`SCHEMA`, `RULES`, `CHECKLIST`) and the contract
   `genios_engine/contracts/expert_review.py` (`ExpertReview.from_mapping`, `validate`).

## Output, per case

`S12/answers/<ID>.json`:

```json
{"expert": [{"when": ["<counterparty-key>"], "by": "claude", "answer": { …the review, in SCHEMA's shape… }}],
 "expert_declared": {}}
```

One entry per file the case reviews (every key in `expert_files.json` for that case). `when` is exactly
`["<key>"]` — the key in angle brackets, as the dossier writes it (`Counterparty: … <key> (…)`).
`expert_declared` maps a key to a one-sentence reason ONLY if a file genuinely cannot be answered (rare;
prefer answering).

## Hard rules — the checker enforces every one

1. **No digits anywhere in any text** — claims, frames, scenarios, reasons, the next move's who/what/
   for_whom, alternative, wait_or_stop, done_when, draft, the proposed kind's why. Say "over a week",
   "twice", "the eleventh", "Monday". (`next_move.by_when` is a date field, not text: `YYYY-MM-DD` or
   null — prefer null unless the case states the date.)
2. **Cite only what the first dossier offered**: every fact's `evidence`, and every id in an inference's or
   pattern's `based_on` (other than `fact:N`), and a proposed kind's `evidence`, must be in that file's
   `evidence` list. Event ids look like `evt_…`; also `num:…`, `pb:…`, `loop:…`, `promise:…` etc.
3. **Stage**: null, or exactly one name from that file's `stages` list (the name, not the label).
4. **Every list holds something**: at least one fact (with at least one id), `frames.rivals` ≥ 1,
   `scenarios.signals_to_watch` ≥ 1, `appraisal.reasons` ≥ 1. Levels are words: stakes/urgency
   `low|medium|high`, reversibility `reversible|costly_to_reverse|irreversible`. Mode: `act|find_out|
   wait|nothing|blocked`; `act` and `find_out` need a `next_move` {who, what, for_whom, by_when}.
5. **Faithful, not hopeful**: what a careful 30-year chief of staff concludes from THIS dossier as written,
   and the case's text — never the answer the founder wishes. Where the dossier is thin, say so in
   `unknowns`. Facts state only what the cited item shows.
6. **Mode follows the case**: in a `must_detect` case, the file the case is about (see `expected` — the
   cards it expects, `about`) gets `act` or `find_out` with a concrete next move; other files of that case
   are judged on their own (often `wait` or `nothing`). In a `must_abstain` case, every file is `nothing`,
   `wait` or `blocked` — the case exists to prove the engine stays quiet.
7. **Forbidden words**: never write any of the case's `forbidden` names or phrases in any text (e.g. never
   say a meeting "happened" unless the dossier shows it did).
8. **proposed_kind**: null unless THE FILE says `Kind of work: not named by the brief` (or a kind the case
   shows is plainly wrong) AND the case text makes the kind plain — then `{"kind": one of investor |
   program | compliance | hiring | intro | partner | vendor, "why": …, "evidence": [ids]}`.
9. **draft**: only when the mode is `act` and the move is a message — short, in the founder's voice (the
   founder is Arjun Rao, Nimbus Labs), no digits; otherwise null.
10. **Later prompts of the same file**: your one answer is served to every prompt of that file, so it must
    stay true for all of them — cite only first-dossier ids. If a later dossier shows a material change
    (they replied, a meeting was booked), you MAY add a second entry BEFORE the general one, with `when`
    `["<key>", "<a phrase or id only the later dossier contains>"]` — the first entry whose terms all
    appear wins. Keep this rare.

## Check, then report

Run, from the repository root:

```
.venv/bin/python "speedrun008/YC-II W27/baseline/s12-expert-authoring/check_answers.py" S12/probe S12/answers <ID> <ID> …
```

Fix until it exits 0 for every case of your batch. Then report, per case: the files answered, the mode
of each, and any declared file with its reason. Do not edit the repository; do not touch other batches'
files.
