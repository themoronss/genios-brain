"""One signal name, one measurement — pinned for the four contact metrics.

THE FAILURE THIS FILE EXISTS TO PREVENT, concretely. `derived.contact_frequency` was authored
into eleven Customer Support inference patterns and meant four different numbers across them:

  * an ACCOUNT's contacts per week          — 5 patterns. This is what `reason/baselines.py`
                                              actually ships, paired with the
                                              `contact_rate_per_account` baseline.
  * a PERSON's contacts per week            — 4 patterns. Same unit, different denominator
                                              population. Never written.
  * a PERSON's SHARE of an account's inbound — 1 pattern. A proportion, not a rate; it cannot
                                              be compared against a per-week baseline at all.
  * a COUNT of an account's distinct callers — 1 pattern. An integer, and the only shape a
                                              named-caller allowance can be checked against.

Because all four shared one name, `Domain Expertise/_tools/backlog.py` ranked the signal as
"unblocks 11" and shipping the writer promoted exactly 2 patterns to `executable`. The backlog
was counting a NAME, not a measurement, and the roadmap was priced off that count.

The two structural checks below are the ones that would have caught it before it shipped:
validate.py only ever checked a pattern's `when` conditions against the vocabulary, so a
`requires_signals` entry could name a path in neither census and nothing anywhere objected. The
pin table is the backstop — attaching a new pattern to any of these four names forces an edit
here, which forces the author to say which of the four measurements they mean.
"""
from __future__ import annotations

import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS = ROOT / "Domain Expertise"


# ── the pin ──────────────────────────────────────────────────────────────────────────────────
# path -> (anchor, unit, {every pattern id permitted to name it}).
# Anchor and unit are the two things the old name left the reader to guess, and guessing them
# wrong is the entire defect. A path may hold exactly one pair of them.
CONTACT_SIGNALS: dict[str, tuple[str, str, set[str]]] = {
    # SHIPPED. reason/baselines.py rolls a company's people up through the works_at edge.
    "derived.contact_frequency": ("account", "contacts_per_week", {
        "cs.churn.contact_rate_below_this_accounts_own_norm",   # executable
        "ticket.repeat_contact_from_the_same_account",          # executable
        "cs.churn.the_same_unresolved_thing_asked_again",       # blocked on ticket_reopened
        "ent.serving_beyond_what_was_bought",                   # blocked on account.arr
        "ka.repeat_contact_after_self_service",                 # blocked on self_service_attempted
    }),
    # UNWRITTEN. One human's contacts per week — the account rate cannot stand in, because a
    # quiet company can still contain one person on their fourth ticket this week.
    "derived.person_contact_rate": ("person", "contacts_per_week", {
        "req.repeat_contact_inside_a_week",
        "cs.sent.reopened_or_repeat_contact",
        "esc.the_diagnosis_restarted",
        "contact.is_a_proxy_for_someone_else",
    }),
    # UNWRITTEN. A proportion of a whole, in basis points. No rate contains one.
    "derived.person_inbound_share": ("person", "basis_points", {
        "account.the_relationship_is_one_person_deep",
    }),
    # UNWRITTEN. An integer count of people, which neither a rate nor a share can produce.
    "derived.account_distinct_contacts": ("account", "count_of_people", {
        "plan.the_named_caller_limit_is_being_exceeded",
    }),
}

#: Exactly one of the four has a writer. Everything else about this file follows from that.
WRITTEN = "derived.contact_frequency"


def _vocabulary() -> dict:
    return yaml.safe_load((CORPUS / "_schema/vocabulary.yaml").read_text())


def _object_docs():
    """Every authored object file in every domain, skipping the generated registries."""
    for path in sorted(CORPUS.rglob("objects/**/*.yaml")):
        if "registry" in path.parts or "_book" in path.parts or "_archive" in path.parts:
            continue
        doc = yaml.safe_load(path.read_text())
        if isinstance(doc, dict) and "identity" in doc and "inference_patterns" in doc:
            yield path, doc


def _patterns():
    for path, doc in _object_docs():
        ip = doc.get("inference_patterns") or {}
        for kind in ("deterministic", "heuristic"):
            for pat in ip.get(kind) or []:
                if isinstance(pat, dict) and pat.get("id"):
                    yield path, doc["identity"]["name"], pat


def _named_by(pat: dict) -> set[str]:
    """Every fact path one pattern names, whether as a requirement or as a live condition."""
    named = {rs["name"] for rs in (pat.get("requires_signals") or []) if rs.get("name")}
    for cond in pat.get("when") or []:
        for key in ("path", "exists", "absent", "neighbor_fact"):
            if key in cond:
                named.add(cond[key])
    return named


# ── the pin itself ───────────────────────────────────────────────────────────────────────────
def test_each_contact_name_is_claimed_by_exactly_the_patterns_pinned_here():
    """Drift in either direction fails: a new site, or a site quietly repointed elsewhere.

    This is the check that makes the defect impossible to repeat silently. Adding a pattern to
    one of these names now requires editing the table above, and the table demands an anchor and
    a unit — which is exactly the question nobody was asked the first time.
    """
    found: dict[str, set[str]] = {name: set() for name in CONTACT_SIGNALS}
    for _path, _obj, pat in _patterns():
        for name in _named_by(pat) & set(CONTACT_SIGNALS):
            found[name].add(pat["id"])

    for name, (anchor, unit, pinned) in CONTACT_SIGNALS.items():
        assert found[name] == pinned, (
            f"{name} ({anchor}-level, {unit}) is claimed by a different set of patterns than "
            f"this file pins.\n  added:   {sorted(found[name] - pinned)}\n"
            f"  removed: {sorted(pinned - found[name])}\n"
            f"If you added one: say which of the four contact measurements it needs and pin it "
            f"here. Reusing a name for a second measurement is the defect this test exists for.")


def test_the_four_measurements_are_four_distinct_names():
    """A pattern may not read two of these at once, and no two may collapse into one name."""
    assert len(set(CONTACT_SIGNALS)) == 4
    seen: dict[str, str] = {}
    for name, (_anchor, _unit, pinned) in CONTACT_SIGNALS.items():
        for pid in pinned:
            assert pid not in seen, (
                f"pattern {pid} names both {seen[pid]} and {name} — if it genuinely needs two "
                f"contact measurements say so explicitly here, and if it does not, one of the "
                f"two is the old ambiguity coming back")
            seen[pid] = name


def test_only_the_measurement_with_a_writer_is_called_substrate():
    """The vocabulary is a census of what exists. Three of these four do not exist.

    Pinned against the writer's own source rather than against a second hand-maintained list:
    the census drifting away from `reason/baselines.py` is how a name comes to claim more than
    it delivers, which is the whole of this defect.
    """
    vocab = _vocabulary()
    substrate = set(vocab["substrate"]["fact_paths"])
    planned = set(vocab["planned_substrate"]["fact_paths"])
    writer = (ROOT / "genios_engine/reason/baselines.py").read_text()

    for name in CONTACT_SIGNALS:
        key = name.split(".", 1)[1]
        if name == WRITTEN:
            assert name in substrate and name not in planned, f"{name} ships; census disagrees"
            assert f'"{key}:' in writer, (
                f"{name} is declared substrate but baselines.py no longer writes a {key!r} key")
        else:
            assert name in planned and name not in substrate, (
                f"{name} has no writer, so it belongs in planned_substrate and nowhere else")
            assert f'"{key}:' not in writer, (
                f"baselines.py writes {key!r} — move {name} into substrate in the same commit")


# ── the structural holes that let it through ─────────────────────────────────────────────────
def test_the_two_censuses_never_overlap():
    """A path is written or it is not. Appearing in both makes the census unreadable.

    Scoped to the overlap and not to exhaustiveness on purpose. `validate.py` checks a pattern's
    `when` conditions against the vocabulary and never its `requires_signals`, so roughly seventy
    `derived.*` asks across Admin, Sales and Customer Support sit in NEITHER census today — a
    real and separate hole, far wider than these four names, and not something this fix is
    entitled to close by making the suite red. What is pinned here is the narrower rule the
    contact defect broke: none of these four may drift into both lists, and the exhaustiveness
    of the four is asserted by `test_only_the_measurement_with_a_writer_is_called_substrate`.
    """
    vocab = _vocabulary()
    substrate = set(vocab["substrate"]["fact_paths"])
    planned = set(vocab["planned_substrate"]["fact_paths"])
    assert not (substrate & planned), f"in both censuses at once: {sorted(substrate & planned)}"


def test_no_pattern_is_executable_on_a_measurement_nobody_writes():
    """`status: executable` is a claim that it runs today. Three of these four cannot."""
    vocab = _vocabulary()
    substrate = set(vocab["substrate"]["fact_paths"])

    for _path, obj, pat in _patterns():
        if pat.get("status") != "executable":
            continue
        for rs in pat.get("requires_signals") or []:
            if rs.get("kind") == "derived" and rs.get("name") not in substrate:
                raise AssertionError(
                    f"{obj}/{pat['id']} is marked executable but requires {rs['name']!r}, which "
                    f"nothing writes — mark it needs_signal")
