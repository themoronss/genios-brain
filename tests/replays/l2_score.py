"""L2 rebuild D1 — the golden set down the NEW path, scored beside today's (offline, the ideal reader, no spend).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… python -m tests.replays.l2_score [F03 F07 …]

Each case runs twice through the real chain: as today (the expert reviews its files), and with
`GENIOS_GOLDEN_L2=1` (the Layer 2 judgment reviews them and makes the cards — `l2_cards`). Both are answered by the
ideal reader — the L2 judgment from the case's own expert answer (`ideal_reader.l2_judgment_for`) — so a difference
is the PATH's, never the model's. Nothing is recorded: no cassette is written or read. Prints one line per case and
the board: the switch rule (`speedrun008/GeniOS-008/01-RULES.md` Rule 2) is that the new path is at least as good.
"""
from __future__ import annotations

import os
import sys
from collections import Counter


def _run(case, l2: bool):
    from tests.replays.engine_runner import L2_PATH_ENV, run_case
    from tests.replays.ideal_reader import IdealReader
    from tests.replays.marking import judge
    if l2:
        os.environ[L2_PATH_ENV] = "1"
    else:
        os.environ.pop(L2_PATH_ENV, None)
    try:
        run = run_case(case, IdealReader(case))
        return judge(case, run), len(run.cards)
    except BaseException as exc:      # noqa: BLE001 — an unanswerable prompt is a result of the run, said
        return exc, 0
    finally:
        os.environ.pop(L2_PATH_ENV, None)


def main(ids: list[str]) -> int:
    from tests.replays.founder_case import load_cases
    from tests.replays.engine_runner import pin_scratch_database
    pin_scratch_database()
    cases = [c for c in load_cases() if not ids or c.case_id in ids]
    board: Counter = Counter()
    for case in cases:
        old, old_cards = _run(case, l2=False)
        new, new_cards = _run(case, l2=True)
        o = getattr(old, "verdict", f"error:{type(old).__name__}")
        n = getattr(new, "verdict", f"error:{type(new).__name__}")
        board[(o, n)] += 1
        flag = "  " if o == n else ("↑ " if n == "pass" else "↓ ")
        why = "" if o == n else f"  new: {getattr(new, 'reason', str(new))[:120]}"
        print(f"{flag}{case.case_id} {case.kind:<13} today {o:<15} ({old_cards} cards)  L2 {n:<15} "
              f"({new_cards} cards){why}", flush=True)
    print("\nboard (today -> L2):")
    for (o, n), k in sorted(board.items()):
        print(f"  {o:>15} -> {n:<15} {k}")
    worse = sum(k for (o, n), k in board.items() if o == "pass" and n != "pass")
    print(f"\nnew path loses {worse} case(s) today passes")
    return 0 if worse == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
