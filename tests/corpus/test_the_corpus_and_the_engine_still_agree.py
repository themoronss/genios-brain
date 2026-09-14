"""The corpus tools are excellent and nothing ran them.

`Domain Expertise/_tools/validate.py` enforces the rule the whole library turns on — *"AUTHOR THE
TRUTH, MARK WHAT CANNOT FIRE"* — and it enforces it in both directions: a situation binding a type
Layer 2 cannot emit is refused, and a situation DEFERRING a type Layer 2 already emits is an error
too, "because that one belongs in `l2_situation_types` and is silently routing nothing".

None of it ran on a commit. The suite cites the tool in comments — one test's docstring says
"validate.py errors on the mirror image" — and no test has ever executed it. Every guarantee held
only for as long as somebody remembered to run a script by hand.

`_tools/index.py` has the same shape and a sharper edge. It GENERATES
`registry/situation-capability-map.yaml`, `authoring.py` states that "the generated registry is
never hand-edited", and the compile reads that file rather than the situation documents. So an
author who edits a situation and does not regenerate leaves the engine routing on a stale map,
with every source file looking correct. Nothing detected that either.

These tests are deliberately thin wrappers. The logic belongs to the tools; what was missing was
anybody running them.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[2]
_CORPUS = _ROOT / "Domain Expertise"
_VALIDATE = _CORPUS / "_tools" / "validate.py"
_INDEX = _CORPUS / "_tools" / "index.py"
_REGISTRY = "registry/situation-capability-map.yaml"


def _run(script: Path, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                          cwd=str(cwd))


def _vocabulary() -> dict:
    return yaml.safe_load((_CORPUS / "_schema" / "vocabulary.yaml").read_text())


def _situations() -> list[tuple[Path, dict]]:
    out = []
    for path in _CORPUS.glob("*/capabilities/*/*/situations/*.yaml"):
        doc = yaml.safe_load(path.read_text())
        if isinstance(doc, dict):
            out.append((path, doc))
    return out


# ── the tool, run the way CI would run it ────────────────────────────────────────────────────

def test_the_corpus_validator_reports_no_errors() -> None:
    """Run as a subprocess so the exit code asserted is the exit code a pipeline reads — the same
    reason `test_convergence` shells out to the derivation DAG check instead of importing it."""
    result = _run(_VALIDATE, _ROOT)
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]
    assert "0 error(s)" in result.stdout


def test_the_validator_is_not_running_degraded() -> None:
    """ITS OWN RECORDED FAILURE, held here. Without `jsonschema` the tool checks SEMANTICS only,
    prints a NOTICE, and then reports "0 error(s) — OK" — and its comment records what that cost:
    "three situation files on this branch carried" structural faults while the summary said the
    corpus was fine. A skip is not a pass, and a green line from a degraded run is worse than red.
    """
    pytest.importorskip("jsonschema", reason="the validator degrades silently without it")
    result = _run(_VALIDATE, _ROOT)
    assert "NOTICE" not in result.stdout, result.stdout[:2000]


# ── the generated registry is what the compile actually reads ────────────────────────────────

def test_the_generated_registry_matches_its_sources(tmp_path: Path) -> None:
    """THE FAILURE THIS CATCHES IS INVISIBLE IN REVIEW. The compile routes on
    `situation-capability-map.yaml`, which is generated; every situation document can be correct
    while the map is a version behind, and a diff of the source files shows nothing wrong.

    Regenerated into a COPY so the real tree is never touched: a test that rewrites the corpus to
    check it would leave a failing run having silently fixed the thing it was reporting.
    """
    work = tmp_path / "corpus"
    shutil.copytree(_CORPUS, work)
    result = _run(work / "_tools" / "index.py", work)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]

    stale = []
    for committed in sorted(_CORPUS.glob(f"*/{_REGISTRY}")):
        regenerated = work / committed.relative_to(_CORPUS)
        if yaml.safe_load(regenerated.read_text()) != yaml.safe_load(committed.read_text()):
            stale.append(str(committed.relative_to(_ROOT)))
    assert stale == [], (
        f"{stale} does not match what `_tools/index.py` produces from the situation documents. "
        f"The compile reads the generated map, so this is the engine routing on a stale answer. "
        f"Run `python '_tools/index.py'` from the Domain Expertise directory and commit the "
        f"result — the registry is never hand-edited.")


def test_every_domain_has_a_generated_registry() -> None:
    domains = {p.name for p in _CORPUS.glob("* Expertise")}
    mapped = {p.parents[1].name for p in _CORPUS.glob(f"*/{_REGISTRY}")}
    assert domains == mapped, f"no generated registry for {sorted(domains - mapped)}"


# ── the deferral census, in both directions ──────────────────────────────────────────────────

def _pending_names() -> dict[str, list[str]]:
    """`{deferred type: the situations deferring it}`.

    AN ENTRY IS A RECORD, NOT A NAME. `pending_l2_situation_types` carries `type`, `owner_layer`,
    `nearest_today` and a `note` explaining what would emit the type and — the part that makes the
    register worth having — why binding it to the nearest live type would be wrong. Both shapes
    are read because the schema permits a bare string and the authored files use the record.
    """
    found: dict[str, list[str]] = {}
    for path, doc in _situations():
        for entry in ((doc.get("matches") or {}).get("pending_l2_situation_types") or ()):
            name = entry.get("type") if isinstance(entry, dict) else entry
            if name:
                found.setdefault(str(name), []).append(str(path.relative_to(_CORPUS)))
    return found


def test_every_deferral_says_what_would_emit_it_and_why_not_the_nearest_type() -> None:
    """THE RULE THE REGISTER EXISTS FOR, and the authored files already keep it:
    "binding 'SLA breach imminent' to `unanswered_email` because it is the closest thing
    available is the failure this section prevents, and it is worse than a gap because it looks
    like coverage." A bare name would defer the type without defending the deferral."""
    thin = []
    for path, doc in _situations():
        for entry in ((doc.get("matches") or {}).get("pending_l2_situation_types") or ()):
            if not isinstance(entry, dict) or len(str(entry.get("note") or "").split()) < 30:
                thin.append(f"{path.relative_to(_CORPUS)}: {entry!r}"[:160])
    assert thin == [], thin


def test_every_deferred_type_is_counted_in_the_planned_census() -> None:
    """`validate.py` only WARNS here, and a warning inside 296 others is not a signal. The
    vocabulary says why the census matters: "the census records what is asked for, and an ask
    nobody records is an ask nobody is tracking" — it is how `backlog.py` counts demand for a
    pack that does not exist yet."""
    planned = set((_vocabulary().get("planned_substrate") or {}).get("l2_situation_types") or ())
    missing = {name: where for name, where in _pending_names().items() if name not in planned}
    assert missing == {}, (
        f"{sorted(missing)} are deferred by an authored situation and absent from "
        f"`planned_substrate.l2_situation_types`, so nothing counts the ask: {missing}")


def test_no_deferred_type_is_one_layer_two_already_emits() -> None:
    """THE MIRROR, and the one that silently routes nothing. A situation that DEFERS a type the
    engine already emits has parked a live lane on a wish list — the vocabulary calls this out
    explicitly, and `condition-now-satisfied.yaml` spent months bound to the nearest live type for
    want of one line. Here it is as a suite failure rather than a tool's exit code."""
    substrate = set((_vocabulary().get("substrate") or {}).get("l2_situation_types") or ())
    live = {name: where for name, where in _pending_names().items() if name in substrate}
    assert live == {}, (
        f"{sorted(live)} are deferred by an authored situation and Layer 2 emits them today — "
        f"move each to `matches.l2_situation_types` so it actually routes: {live}")


def test_the_two_censuses_do_not_overlap() -> None:
    """A type cannot be both emitted and planned; one of the two entries would silently win."""
    vocab = _vocabulary()
    substrate = set((vocab.get("substrate") or {}).get("l2_situation_types") or ())
    planned = set((vocab.get("planned_substrate") or {}).get("l2_situation_types") or ())
    assert substrate & planned == set(), sorted(substrate & planned)
