"""The golden board — what the founder set and the Atlas replays say about the engine, in two lines.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://…/genios_test python scripts/golden_score.py
    … python scripts/golden_score.py --json scores.json          # also write it, machine-readable
    … python scripts/golden_score.py --assert-recorded "speedrun008/YC-II W27/03-FINDINGS.md"

`speedrun008/YC-II W27/STEP-01-PENDING-owner-rohit-and-harsh-the-golden-set.md` §5. Every founder
case is replayed from its cassette through the real chain (`tests/replays/engine_runner.py`) and
marked (`tests/replays/marking.py`); every Atlas mutation a founder case drives is checked on that
case's run (`tests/replays/atlas_expression.py`). The board:

    founder golden set   must-detect  P/N (k not expressible)  must-abstain  P/M (x not exercised)
                         forbidden outputs F
    atlas replays 01–07  passing a/80  blocked b/80  not expressible c

and, under it, where the must-detect cases were lost (the gate, before memory, in reasoning).
Every later step quotes this board before and after, and is not DONE while its rows have not
moved.

**It refuses rather than prints a number from nothing.** No scratch database, a production host,
or a cassette miss is exit 2: a board computed over a chain that never ran is the "pass over an
empty table" this repository already paid for once.

`--assert-recorded FILE` reads the two board lines written in FILE (03-FINDINGS §F, the
before-score) and exits 1 unless they are exactly what this run measures.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

FOUNDER_LINE = re.compile(r"^founder golden set .*$", re.M)
ATLAS_LINE = re.compile(r"^atlas replays 01–07 .*$", re.M)


def measure() -> dict:
    """Replay every case and every driven mutation; return the board's numbers."""
    from tests.replays import atlas_expression as ax
    from tests.replays import cassettes
    from tests.replays.engine_runner import pin_scratch_database
    from tests.replays.founder_case import load_cases
    from tests.replays.harness import load_specs
    from tests.replays.marking import FAIL, NOT_EXERCISED, NOT_EXPRESSIBLE, PASS, judge

    pin_scratch_database()
    cases = load_cases()
    by_id = {c.case_id: c for c in cases}
    runs, marks = {}, {}
    for case in cases:
        runs[case.case_id] = cassettes.replay(case)
        marks[case.case_id] = judge(case, runs[case.case_id])
    detect = [m for m in marks.values() if m.kind == "must_detect"]
    abstain = [m for m in marks.values() if m.kind == "must_abstain"]
    count = Counter
    board = {
        "must_detect": {"pass": sum(m.verdict == PASS for m in detect), "of": len(detect),
                        "not_expressible": sum(m.verdict == NOT_EXPRESSIBLE for m in detect),
                        "fail": sum(m.verdict == FAIL for m in detect),
                        "lost_at": dict(count(m.lost_at for m in detect
                                              if m.verdict == FAIL and m.lost_at))},
        "must_abstain": {"pass": sum(m.verdict == PASS for m in abstain), "of": len(abstain),
                         "not_exercised": sum(m.verdict == NOT_EXERCISED for m in abstain),
                         "fail": sum(m.verdict == FAIL for m in abstain)},
        "forbidden_outputs": sum(len(m.forbidden_hits) for m in marks.values()),
        "cases": {cid: {"verdict": m.verdict, "lost_at": m.lost_at, "reason": m.reason}
                  for cid, m in sorted(marks.items())},
        "sources": sorted({cassettes.source_of(c) for c in cases}),
    }
    driven = {f"{n:02d}" for n in range(1, 8)}
    total = sum(len(s.mutations) for s in load_specs() if s.replay_id in driven)
    passing = blocked = 0
    for (_replay, _index), expression in sorted(ax.EXPRESSED.items()):
        problems = ax.check(expression, runs[by_id[expression["case"]].case_id])
        passing += not problems
        blocked += bool(problems)
    board["atlas"] = {"passing": passing, "blocked": blocked, "of": total,
                      "not_expressible": total - len(ax.EXPRESSED)}
    return board


def lines(board: dict) -> tuple[str, str]:
    d, a, x = board["must_detect"], board["must_abstain"], board["atlas"]
    founder = (f"founder golden set   must-detect  {d['pass']}/{d['of']} "
               f"({d['not_expressible']} not expressible)   must-abstain  {a['pass']}/{a['of']} "
               f"({a['not_exercised']} not exercised)   forbidden outputs  "
               f"{board['forbidden_outputs']}")
    atlas = (f"atlas replays 01–07  passing  {x['passing']}/{x['of']}   blocked  "
             f"{x['blocked']}/{x['of']}   not expressible  {x['not_expressible']}")
    return founder, atlas


def recorded(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    founder, atlas = FOUNDER_LINE.findall(text), ATLAS_LINE.findall(text)
    if len(founder) != 1 or len(atlas) != 1:
        raise SystemExit(f"{path}: expected exactly one recorded board (one `founder golden set` "
                         f"line and one `atlas replays 01–07` line), found {len(founder)} and "
                         f"{len(atlas)}")
    return founder[0].rstrip(), atlas[0].rstrip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--json", metavar="FILE", help="also write the board, with every case, here")
    ap.add_argument("--assert-recorded", metavar="FILE",
                    help="exit 1 unless FILE records exactly this board (03-FINDINGS §F)")
    args = ap.parse_args(argv)

    from tests.replays.engine_runner import RunnerRefused
    from tests.replays.harness import CassetteMiss
    try:
        board = measure()
    except RunnerRefused as refused:
        print(f"golden board REFUSED: {refused}", file=sys.stderr)
        return 2
    except CassetteMiss as miss:
        print(f"golden board REFUSED: {miss}", file=sys.stderr)
        return 2

    founder, atlas = lines(board)
    print(founder)
    print(atlas)
    lost = board["must_detect"]["lost_at"]
    print("must-detect cases lost at:  " + "  ".join(f"{k} {v}" for k, v in sorted(lost.items())))
    print(f"model answers:  {', '.join(board['sources'])} (06-DECISIONS D12c)")
    if args.json:
        Path(args.json).write_text(json.dumps(board, indent=1) + "\n", encoding="utf-8")
    if args.assert_recorded:
        want = recorded(Path(args.assert_recorded))
        if want != (founder, atlas):
            print(f"\nthe board recorded in {args.assert_recorded} is not this one:\n"
                  f"  recorded: {want[0]}\n            {want[1]}\n"
                  f"  measured: {founder}\n            {atlas}", file=sys.stderr)
            return 1
        print(f"matches the board recorded in {args.assert_recorded}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
