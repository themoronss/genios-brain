"""Which golden cases' decider prompts carry corpus claims (F121's section), and frame lines."""
import sys
from tests.replays import cassettes
from tests.replays.founder_case import load_cases
from tests.replays.engine_runner import pin_scratch_database, run_case
from tests.replays.harness import RecordedLLM, identify_site

class Keeping(RecordedLLM):
    def __init__(self, c):
        super().__init__(c); self.prompts = []
    def call(self, prompt, **kw):
        self.prompts.append((identify_site(prompt), prompt)); return super().call(prompt, **kw)

pin_scratch_database()
ids = sys.argv[1:]
for case in load_cases():
    if ids and case.case_id not in ids:
        continue
    llm = Keeping(cassettes.load(case))
    run_case(case, llm)
    dec = [p for s, p in llm.prompts if s == "decider"]
    claims = [p for p in dec if "WHAT AN EXPERT WOULD KNOW HERE" in p]
    framing = [p for p in dec if "HOW AN EXPERT READS THIS KIND OF SITUATION" in p]
    nulls = sum('"rule": null' in p for _, p in llm.prompts)
    print(f"{case.case_id} decider={len(dec)} with_claims={len(claims)} with_framing={len(framing)} nulls={nulls}", flush=True)
    if claims:
        block = claims[0].split("WHAT AN EXPERT WOULD KNOW HERE", 1)[1].split("\n\n", 1)[0]
        print("   ", block[:600].replace("\n", "\n    "), flush=True)
