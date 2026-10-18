"""Record each case with the ideal reader; where it refuses, save the full prompt and the error
(the reader is never made to guess — the answer is then authored in the case, and this runs again).
Nothing is saved to a cassette here."""
import os, sys, json
from pathlib import Path
sys.path.insert(0, os.getcwd())               # run from the repository root
OUT = Path(os.environ.get("TMPDIR", "/tmp")) / "s09_prompts"
OUT.mkdir(exist_ok=True)
from tests.replays import cassettes, ideal_reader
from tests.replays.engine_runner import pin_scratch_database
from tests.replays.founder_case import load_cases
from tests.replays.harness import identify_site
from tests.replays.marking import judge

class Saving(ideal_reader.IdealReader):
    def call(self, prompt, *, max_tokens=4096, **kw):
        try:
            return super().call(prompt, max_tokens=max_tokens, **kw)
        except ideal_reader.IdealReaderError as e:
            site = identify_site(prompt)
            n = len(list(OUT.glob(f"{self.case.case_id}-{site}-*.txt")))
            (OUT / f"{self.case.case_id}-{site}-{n}.txt").write_text(f"ERROR: {e}\n\n{prompt}")
            raise

pin_scratch_database()
for case in load_cases():
    if case.case_id not in sys.argv[1:]:
        continue
    try:
        run, answers = cassettes.record(case, Saving(case))
        mark = judge(case, run)
        print(case.case_id, "RECORDABLE", mark.verdict, mark.reason[:140], flush=True)
    except ideal_reader.IdealReaderError as e:
        print(case.case_id, "REFUSED", str(e)[:300], flush=True)
