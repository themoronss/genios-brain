"""Rule 3.3 · THE LAYER GUARD: a model call lives only where `00-ARCHITECTURE.md` allows one.

GeniOS-011 S04.U1 builds the third of the three CI guards `speedrun008/GeniOS-008/01-RULES.md`
Rule 3 requires (`02-MIGRATION-PLAN.md` L0-5, "the model-site guard"). Rule 3.3: "a model call may
live only where 00-ARCHITECTURE.md allows one (L1 extraction and detection; L2's bounded pass; L5
and L6 wording and parsing). A new model call elsewhere turns CI red."

WHY IT EXISTS. `tests/test_every_llm_call_site_is_metered.py` already turns CI red on any new
module that calls a model — but for BILLING. It asks "does this spend reach the ledger?", never
"is this layer allowed to think?". A model call added to `context/` (L3, "Model: none") that
records its cost passes the register, and the old flow — L3 judging before L2 reasons — grows
back with a green build.

WHAT IT CHECKS.

  1. The layer table this file encodes IS `00-ARCHITECTURE.md` "The layers": the packages of each
     layer, and whether its Model column allows a call. Read from the document, so an edit there
     shows up here.
  2. Every model site the two registers name — `tests/replays/harness.SITE_MARKERS` (by site) and
     the metering register `_SITES` (by module) — is mapped to the layer the architecture gives
     its work, and lives in that layer's package.
  3. Every module whose AST calls a model (`<…llm…/…client…>.call(`, `messages.create(`,
     `messages.batches`) is in a package whose layer allows one. This is the check that stands on
     the code alone: a planted `llm.call` in `context/` is red here even before anybody registers
     it.
  4. What is out of place TODAY is declared once, in `OUT_OF_PLACE`, and that list only SHRINKS
     (the same ratchet Rule 3.2 gives the situation writers). The one on every sweep is
     `context/lifecycle` · `detect_resolutions` (`02-MIGRATION-PLAN.md` L2-12, L3-7); the rest are
     reached on demand or not at all, and each line says which.

WHAT TO DO WHEN IT FAILS.

  * "out of place" — a model call landed in a layer that may not hold one. Move it: L3 asks L2
    through a `ReasoningResult` or an EvidenceNeed, L0 hands it to the layer that owns the work.
    Do not add it to `OUT_OF_PLACE`; that list only shrinks.
  * "no longer out of place" — a declared site moved home or was deleted. Delete its line. That
    is the ratchet turning.
  * "has no home" — a new site in a register. Say which layer's work it is in `MARKED_SITES` /
    `METERED_MODULES`, citing 00-ARCHITECTURE's Model column.
"""
from __future__ import annotations

import ast
import functools
import re
from pathlib import Path

from tests.replays.harness import SITE_MARKERS
from tests.test_every_llm_call_site_is_metered import _SITES as METERING_REGISTER

_ROOT = Path(__file__).resolve().parents[1]
_ENGINE = _ROOT / "genios_engine"
_ARCHITECTURE = _ROOT / "speedrun008" / "GeniOS-008" / "00-ARCHITECTURE.md"

# ── 00-ARCHITECTURE.md, "The layers" ─────────────────────────────────────────────────────────

#: layer → (its packages, does its Model column allow a call). Checked against the document.
LAYERS: dict[str, tuple[frozenset[str], bool]] = {
    "L0": (frozenset({"contracts", "platform", "api"}), False),   # "never"
    "L1": (frozenset({"capture"}), True),          # "extraction, detection, link suggestion"
    "L2": (frozenset({"reason", "packs"}), True),  # "0–3 bounded calls per situation"
    "L3": (frozenset({"context"}), False),         # "none"
    "L4": (frozenset({"executive"}), True),        # "wording only"
    "L5": (frozenset({"deliver"}), True),          # "wording only, validated"
    "L6": (frozenset({"feedback"}), True),         # "parse corrections only"
}

#: THE TRANSPORT. `LLMClient` is the one client every layer's call goes through; it counts tokens
#: and decides nothing (the metering register: "records": False). It is the mechanism, not a site:
#: where a call LIVES is where `.call(` is written. Its folder is history, not a placement claim.
TRANSPORT = "context/llm/client.py"

# ── every model site, and the layer whose work it is ────────────────────────────────────────

#: `tests/replays/harness.SITE_MARKERS` — site → (home layer(s), what it does).
MARKED_SITES: dict[str, tuple[tuple[str, ...], str]] = {
    "junk_gate": (("L1",), "detection: is ONE email junk"),
    "junk_gate_batch": (("L1",), "detection: which of SEVERAL emails are junk"),
    "relevance": (("L1",), "detection: business relevance of a message"),
    "domains": (("L1",), "extraction: the domains a message belongs to"),
    "extraction": (("L1",), "extraction: structured facts from a message"),
    "resolution": (("L2",), "judges whether a message ends a situation — L2-12 moves it to L2"),
    "decider": (("L2",), "the old chain's decision pass"),
    "r1": (("L2",), "R1, the reader inside the reasoning layer"),
    "narrator": (("L5",), "wording: ONE card"),
    "bundle_narrator": (("L2",), "R-2: narrates a decision already made"),
    "expert": (("L2",), "R-7: the expert's review of one file"),
    "reason_l2": (("L2",), "R-9: the Layer 2 judgment of one subject"),
    "angle": (("L2",), "an angle: a judgment over one subject — L3-7 moves angles to L2"),
    "cohort": (("L2",), "M-9 drafts a cohort predicate a person approves — plan §1 'move to L2'"),
    "screen_insight": (("L2",), "reads what is on a manager's screen and judges what matters"),
    "org_rule_extract": (("L2",), "N-3: proposes organisation-brain rules (Plane D, `packs/`)"),
}

#: The metering register (`tests/test_every_llm_call_site_is_metered._SITES`) — module → (home
#: layer(s), what it does). `TRANSPORT` is the one module it lists that is not a site.
METERED_MODULES: dict[str, tuple[tuple[str, ...], str]] = {
    "capture/gate/relevance.py": (("L1",), "detection: the junk gate"),
    "capture/esqe/relevance.py": (("L1",), "detection: ESQE relevance"),
    "capture/semantic/extractor.py": (("L1",), "extraction: LLM-2"),
    "capture/domain/proposer.py": (("L1",), "extraction: domain labels"),
    "context/extract/extractor.py": (("L1",), "extraction — L1's job; this is the legacy copy"),
    "context/angles/asker.py": (("L2",), "an angle's judgment — L3-7 moves angles to L2"),
    "context/lifecycle/resolution.py": (("L2",), "detect_resolutions — L2-12 moves it to L2"),
    "context/analytic/cohort.py": (("L2",), "M-9's predicate draft — plan §1 'move to L2'"),
    "reason/intelligence.py": (("L2",), "answers a question over the graph"),
    "reason/bundle/gate.py": (("L2",), "R-2's narration of a decided bundle"),
    "reason/llm_decision_maker.py": (("L2",), "the old chain's decision pass"),
    "reason/llm_interpretation.py": (("L2",), "R1's interpretation"),
    "reason/brief_drafter.py": (("L2",), "proposes company-brief lines from memory patterns"),
    "reason/moments/screen_insight.py": (("L2",), "the screen judge"),
    "reason/moments/screen_memory_batch.py": (("L2",), "batches screen memories for the judge"),
    "reason/moments/seat_profile.py": (("L2",), "the weekly profile the screen judge reads"),
    "reason/moments/draft_review.py": (("L2",), "notes on a draft; never proposes wording"),
    "deliver/render.py": (("L5",), "wording: the card"),
    "packs/brains/org_rule_extract.py": (("L2",), "N-3 (Plane D)"),
    "packs/brains/behavior_distill.py": (("L2",), "N-4 (Plane D), not wired"),
    "api/intelligence_routes.py": (
        ("L2", "L5"), "/v1/intelligence/draft words a reply (L5) inside the API (L0)"),
}

# ── the ratchet over what is out of place today ─────────────────────────────────────────────

#: Where the list STARTED (GeniOS-011 S04.U1, measured at 0cc8d83c). Frozen history.
_OUT_OF_PLACE_AT_THE_START: frozenset[str] = frozenset({
    "context/lifecycle/resolution.py", "context/lifecycle/prompt.py",
    "context/angles/asker.py", "context/analytic/cohort.py", "context/extract/extractor.py",
    "api/intelligence_routes.py",
})
_OUT_OF_PLACE_STARTED_AT = 6

#: THE LIVE LIST — model sites that live outside their layer today. Delete a line when the site
#: moves home or is deleted. Never add one.
OUT_OF_PLACE: dict[str, str] = {
    # ⛔ THE ONE ON THE SWEEP. `context/runner.process_pending` calls `detect_resolutions` with the
    # chain's client on every drain — the only model call that runs inside L3's own sweep.
    "context/lifecycle/resolution.py":
        "detect_resolutions: an `llm.call` per unexamined message, EVERY drain (L2-12, L3-7)",
    "context/lifecycle/prompt.py": "detect_resolutions' prompt (the `resolution` site)",
    # Reached on demand, or not at all — out of place all the same (Rule 1.2: the old place is a
    # finding, never a reason to call it fine).
    "context/angles/asker.py":
        "`model_asker`: no engine caller supplies an asker; the sweep runs with none (L3-7)",
    "context/analytic/cohort.py":
        "`llm_predicate_drafter`: on demand from `api/cohort_routes`, a person approves (plan §1)",
    "context/extract/extractor.py":
        "legacy extraction: `process_event` callers pass llm=None; L1's extraction is the seam",
    "api/intelligence_routes.py":
        "`draft_reply` calls the model inside L0's API (`intelligence_draft`)",
}

# ── reading the code (AST only) ─────────────────────────────────────────────────────────────

_CLIENTISH = re.compile(r"llm|client", re.IGNORECASE)


def _receiver_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):                      # `_client(key, model).call(…)`
        return _receiver_name(node.func)
    return ""


def calls_a_model(source: str) -> bool:
    """Does this source invoke a model — in every spelling the metering register names, read
    from the AST: the shared client's `.call(` on an llm/client receiver, a raw
    `messages.create(`, and the Message Batches API."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            func = node.func
            if func.attr == "call" and _CLIENTISH.search(_receiver_name(func.value)):
                return True
            if (func.attr == "create" and isinstance(func.value, ast.Attribute)
                    and func.value.attr == "messages"):
                return True
        if (isinstance(node, ast.Attribute) and node.attr == "batches"
                and isinstance(node.value, ast.Attribute) and node.value.attr == "messages"):
            return True
    return False


@functools.lru_cache(maxsize=1)
def _engine_model_modules() -> frozenset[str]:
    return frozenset(str(path.relative_to(_ENGINE)) for path in sorted(_ENGINE.rglob("*.py"))
                     if calls_a_model(path.read_text(encoding="utf-8")))


def _layer_of(module: str) -> str | None:
    package = module.split("/")[0]
    return next((layer for layer, (packages, _ok) in LAYERS.items() if package in packages), None)


def _home_problems(module: str, homes: tuple[str, ...], label: str) -> tuple[list[str], bool]:
    """(problems, is it out of place) for one site."""
    problems: list[str] = []
    for home in homes:
        if home not in LAYERS or not LAYERS[home][1]:
            problems.append(f"{label} is mapped to {home}, whose Model column allows no call")
    layer = _layer_of(module)
    return problems, layer not in homes


def placement_problems(*, marked: tuple[tuple[str, str, str], ...] = SITE_MARKERS,
                       metered: dict[str, dict[str, object]] = METERING_REGISTER,
                       discovered: frozenset[str] | None = None,
                       out_of_place: dict[str, str] = OUT_OF_PLACE) -> list[str]:
    """Everything wrong with where the model sites live. Empty = green."""
    discovered = _engine_model_modules() if discovered is None else discovered
    problems: list[str] = []
    misplaced: set[str] = set()

    for site, module, _marker in marked:
        if site not in MARKED_SITES:
            problems.append(f"SITE_MARKERS site {site!r} ({module}) has no home: say which "
                            "layer's work it is in MARKED_SITES")
            continue
        found, away = _home_problems(module, MARKED_SITES[site][0], f"site {site!r}")
        problems += found
        if away:
            misplaced.add(module)
    stale = sorted(set(MARKED_SITES) - {site for site, _m, _p in marked})
    problems += [f"MARKED_SITES names {site!r}, which SITE_MARKERS no longer has" for site in stale]

    for module in metered:
        if module == TRANSPORT:
            continue
        if module not in METERED_MODULES:
            problems.append(f"metered module {module} has no home: say which layer's work it is "
                            "in METERED_MODULES")
            continue
        found, away = _home_problems(module, METERED_MODULES[module][0], module)
        problems += found
        if away:
            misplaced.add(module)
    problems += [f"METERED_MODULES names {module}, which the metering register no longer has"
                 for module in sorted(set(METERED_MODULES) - set(metered))]

    # Stand on the code: a module that calls a model must sit in a layer that may hold one,
    # registered or not.
    for module in sorted(discovered - {TRANSPORT}):
        layer = _layer_of(module)
        if layer is None or not LAYERS[layer][1]:
            misplaced.add(module)

    for module in sorted(misplaced - set(out_of_place)):
        where = _layer_of(module) or "no layer in 00-ARCHITECTURE"
        problems.append(f"a model call out of place: {module} ({where}) — 00-ARCHITECTURE does "
                        "not allow one there. Move it to the layer that owns the work")
    for module in sorted(set(out_of_place) - misplaced):
        problems.append(f"{module} is no longer out of place — delete it from OUT_OF_PLACE; the "
                        "list shrinks")
    grown = sorted(set(out_of_place) - _OUT_OF_PLACE_AT_THE_START)
    if grown:
        problems.append(f"OUT_OF_PLACE grew: {grown}. It only shrinks")
    if len(out_of_place) > _OUT_OF_PLACE_STARTED_AT:
        problems.append(f"OUT_OF_PLACE holds {len(out_of_place)} (it started at "
                        f"{_OUT_OF_PLACE_STARTED_AT} and may only fall)")
    return problems


# ── the guard ───────────────────────────────────────────────────────────────────────────────

def _architecture_layers() -> dict[str, tuple[frozenset[str], bool]]:
    """`00-ARCHITECTURE.md` "The layers", read from the document's own table."""
    text = _ARCHITECTURE.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if re.match(r"\|\s*\*\*L\d", line)]
    header = next(line for line in text.splitlines()
                  if line.startswith("| Layer |") and "| Model |" in line)
    columns = [c.strip() for c in header.strip("|").split("|")]
    out: dict[str, tuple[frozenset[str], bool]] = {}
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        layer = re.match(r"\*\*(L\d)", cells[0]).group(1)            # type: ignore[union-attr]
        packages = frozenset(p.strip("/") for p in re.findall(r"`([^`]+)`",
                                                                cells[columns.index("Package")]))
        model = cells[columns.index("Model")].lower()
        out[layer] = (packages, model not in ("never", "none"))
    return out


def test_the_layer_table_is_the_architectures() -> None:
    assert _architecture_layers() == LAYERS, (
        "00-ARCHITECTURE.md 'The layers' and this file's LAYERS disagree — the document wins; "
        "update LAYERS and re-read every site's home")


def test_every_model_site_lives_where_the_architecture_allows_it() -> None:
    problems = placement_problems()
    assert not problems, "\n".join(problems)


def test_the_out_of_place_list_only_shrinks() -> None:
    assert len(_OUT_OF_PLACE_AT_THE_START) == _OUT_OF_PLACE_STARTED_AT
    assert set(OUT_OF_PLACE) <= _OUT_OF_PLACE_AT_THE_START
    assert len(OUT_OF_PLACE) <= _OUT_OF_PLACE_STARTED_AT


def test_detect_resolutions_is_the_exception_on_the_sweep() -> None:
    """The one out-of-place call L3's own sweep makes is `detect_resolutions`, reached from
    `context/runner.process_pending` through the `context.lifecycle` package, with the chain's
    client. Pinned from the AST, so the declaration above cannot drift from the code."""
    tree = ast.parse((_ENGINE / "context" / "runner.py").read_text(encoding="utf-8"))
    pending = next(node for node in tree.body
                   if isinstance(node, ast.FunctionDef) and node.name == "process_pending")
    imported = {alias.asname or alias.name
                for node in ast.walk(pending) if isinstance(node, ast.ImportFrom)
                and node.module == "genios_engine.context.lifecycle" for alias in node.names}
    assert "detect_resolutions" in imported
    calls = [node for node in ast.walk(pending) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == "detect_resolutions"]
    assert len(calls) == 1 and any(k.arg == "llm" for k in calls[0].keywords)
    assert "context/lifecycle/resolution.py" in OUT_OF_PLACE


def test_the_one_module_excused_as_transport_is_the_registers_transport() -> None:
    """`TRANSPORT` is excused from placement because it decides nothing — which the metering
    register says in its own words ("records": False, no purpose). Any other module claiming that
    status would have to be a site."""
    spec = METERING_REGISTER[TRANSPORT]
    assert spec.get("records") is False and not spec.get("purpose")
    others = sorted(m for m, s in METERING_REGISTER.items()
                    if m != TRANSPORT and s.get("records") is False)
    assert not others, f"a second module calls itself a transport: {others}"


def test_the_ast_scan_finds_every_metered_site() -> None:
    """A scan that finds nothing passes for ever: the AST reading must see every module the
    metering register lists — both are about the same calls."""
    missing = sorted(set(METERING_REGISTER) - _engine_model_modules())
    assert not missing, f"metered modules the AST scan does not see calling a model: {missing}"


# ── negative controls: a planted violation turns the guard red ─────────────────────────────

def test_control_a_model_call_planted_in_context_is_red() -> None:
    planted = "def judge(llm, prompt):\n    return llm.call(prompt, max_tokens=10)\n"
    assert calls_a_model(planted)
    problems = placement_problems(
        discovered=_engine_model_modules() | {"context/planted_rule3_judge.py"})
    assert any("context/planted_rule3_judge.py" in p and "out of place" in p for p in problems)


def test_control_a_raw_anthropic_call_planted_in_the_api_is_red() -> None:
    planted = ("def ask(client, prompt):\n"
               "    return client.messages.create(model='m', max_tokens=1, messages=[])\n")
    assert calls_a_model(planted)
    problems = placement_problems(
        discovered=_engine_model_modules() | {"api/planted_rule3_routes.py"})
    assert any("api/planted_rule3_routes.py" in p for p in problems)


def test_control_a_model_call_outside_every_layer_is_red() -> None:
    problems = placement_problems(discovered=_engine_model_modules() | {"mcp/planted_rule3.py"})
    assert any("mcp/planted_rule3.py" in p and "no layer" in p for p in problems)


def test_control_a_marked_site_moved_into_l3_is_red() -> None:
    moved = tuple((site, "context/planted_narrator.py" if site == "narrator" else module, mark)
                  for site, module, mark in SITE_MARKERS)
    problems = placement_problems(marked=moved)
    assert any("context/planted_narrator.py" in p for p in problems)


def test_control_a_metered_site_with_no_home_is_red() -> None:
    grown = dict(METERING_REGISTER)
    grown["executive/planted_rule3_wording.py"] = {"records": True, "purpose": ("planted",)}
    problems = placement_problems(metered=grown)
    assert any("executive/planted_rule3_wording.py" in p and "no home" in p for p in problems)


def test_control_a_new_line_in_the_out_of_place_list_is_red() -> None:
    grown = dict(OUT_OF_PLACE)
    grown["context/planted_rule3_judge.py"] = "planted"
    problems = placement_problems(
        discovered=_engine_model_modules() | {"context/planted_rule3_judge.py"},
        out_of_place=grown)
    assert any("grew" in p for p in problems)
    assert any("may only fall" in p for p in problems)


def test_control_a_site_moved_home_shrinks_the_list() -> None:
    """detect_resolutions moved to `reason/` (as L2-12 plans): its line here must go."""
    moved = tuple((site, "reason/lifecycle/prompt.py" if site == "resolution" else module, mark)
                  for site, module, mark in SITE_MARKERS)
    metered = {("reason/lifecycle/resolution.py" if m == "context/lifecycle/resolution.py" else m): s
               for m, s in METERING_REGISTER.items()}
    discovered = (_engine_model_modules() - {"context/lifecycle/resolution.py"}) | {
        "reason/lifecycle/resolution.py"}
    problems = placement_problems(marked=moved, metered=metered, discovered=discovered)
    assert any("context/lifecycle/resolution.py is no longer out of place" in p for p in problems)
    assert any("context/lifecycle/prompt.py is no longer out of place" in p for p in problems)
    assert any("has no home" in p and "reason/lifecycle/resolution.py" in p for p in problems)


def test_control_a_site_in_its_own_layer_is_green() -> None:
    """The guard is about placement, not about calling a model at all: a new L2 site is fine."""
    problems = placement_problems(discovered=_engine_model_modules() | {"reason/planted_ok.py"})
    assert not [p for p in problems if "reason/planted_ok.py" in p], problems
