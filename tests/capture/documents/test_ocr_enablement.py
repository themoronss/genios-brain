"""L1.3.4-U2 · OCR enablement — *"enable per-tenant, not globally"*, and the third input.

doc-03's fix list for U2 opens with two deployment clauses — add Tesseract to the container
image, and enable it per tenant — and the reason both are needed at once is that a single global
boolean cannot tell apart the two states the deploy is actually in. `enable_ocr=false` parks
scanned documents. `enable_ocr=true` on an image with no binary is *worse than false*: every
scanned attachment now takes the OCR branch, the first one raises, and a flag meant to turn a
feature on has turned empty documents into failed syncs.

So the decision takes three inputs and returns the reason it reached, in the words that fix it.
The rule is pure and lives beside the unit it governs; `platform/wiring.py` supplies the two
booleans (the setting, and whether the binary is on the host) and does nothing else.
"""
from __future__ import annotations

import pytest

from genios_engine.capture.documents.enablement import (OcrAvailability, parse_org_allowlist,
                                                        resolve_ocr_availability)

ORG = "org_pilot"


@pytest.mark.parametrize(
    "global_enabled, allow, deny, engine_present, enabled, availability, why", [
        (False, (),      (),      True,  False, OcrAvailability.DISABLED_GLOBALLY.value,
         "the fleet default is off and this org asked for nothing"),
        (True,  (),      (),      True,  True,  OcrAvailability.ENABLED.value,
         "the fleet default is on"),
        (False, (ORG,),  (),      True,  True,  OcrAvailability.ENABLED.value,
         "the per-tenant rollout doc-03 asks for: one org, no global flip"),
        (True,  (),      (ORG,),  True,  False, OcrAvailability.DISABLED_FOR_TENANT.value,
         "a tenant opt-OUT that the fleet default can override is not an opt-out"),
        (False, (ORG,),  (ORG,),  True,  False, OcrAvailability.DISABLED_FOR_TENANT.value,
         "deny beats allow — the safe direction when a config contradicts itself"),
        (True,  (ORG,),  (),      False, False, OcrAvailability.ENGINE_MISSING.value,
         "no binary on the host outranks every flag: this is the deploy state doc-03 names"),
        (False, (),      (),      False, False, OcrAvailability.ENGINE_MISSING.value,
         "still engine_missing, because the fix is different from turning a flag on"),
        (False, ("other_org",), (), True, False, OcrAvailability.DISABLED_GLOBALLY.value,
         "another org's allowlist entry is not this org's"),
    ])
def test_three_inputs_decide_and_the_answer_says_which_one_did(
        global_enabled, allow, deny, engine_present, enabled, availability, why):
    d = resolve_ocr_availability(org_id=ORG, global_enabled=global_enabled,
                                 allowlist=frozenset(allow), denylist=frozenset(deny),
                                 engine_present=engine_present)
    assert (d.enabled, d.availability) == (enabled, availability), why
    assert d.detail, "an operator must be able to read what to change"


def test_a_caller_with_no_org_falls_back_to_the_fleet_default():
    """The upload door before an org is resolved, and any internal caller. The allowlist simply
    does not apply — it must never be read as "no org id, so allow everything"."""
    assert resolve_ocr_availability(org_id=None, global_enabled=False,
                                    allowlist=frozenset({ORG}), denylist=frozenset(),
                                    engine_present=True).enabled is False
    assert resolve_ocr_availability(org_id=None, global_enabled=True, engine_present=True).enabled


@pytest.mark.parametrize("raw, expected", [
    ("org_a,org_b",      {"org_a", "org_b"}),
    (" org_a , org_b ",  {"org_a", "org_b"}),
    ("org_a,,",          {"org_a"}),          # a trailing comma must not create an id of ""
    ("",                 set()),
    (None,               set()),
    (",  ,",             set()),
])
def test_the_env_list_is_parsed_once_and_never_yields_an_empty_org_id(raw, expected):
    assert parse_org_allowlist(raw) == expected


#: The two Python modules `tesseract_available()` probes with `find_spec`, beside the binary.
BINDINGS = ("pytesseract", "PIL")


def _bindings(monkeypatch, *, present: tuple[str, ...]) -> None:
    """Put BOTH halves of the availability probe under the test's control.

    ⛔ WHY THIS EXISTS. `tesseract_available()` requires the binary **and** the bindings, and a test
    that stubs only `shutil.which` is asserting a positive outcome while one prerequisite is still
    whatever the host happens to have. On a host without `pytesseract` installed — which is this
    repo's dev host, and is why the L1 receipt reports 872 unsupported `document_jobs` — the probe
    correctly answered False and the test read that correct answer as a product failure.

    It delegates to the real `find_spec` for every other module, so stubbing the probe cannot
    quietly change how anything else imports.
    """
    import importlib.util as _iu

    real = _iu.find_spec

    def fake(name, *a, **kw):
        if name in BINDINGS:
            return object() if name in present else None
        return real(name, *a, **kw)

    monkeypatch.setattr("genios_engine.capture.documents.tesseract.importlib.util.find_spec", fake)


def test_the_wiring_returns_no_engine_rather_than_one_that_raises(monkeypatch):
    """The end of the U2 story, at the seam that decides it. On a host with no Tesseract binary,
    `enable_ocr=true` must produce None (scanned documents park, recoverably) and NOT an engine
    that throws inside a sync batch."""
    import genios_engine.platform.wiring as wiring
    from genios_engine.platform.config import Settings

    monkeypatch.setattr(wiring, "get_settings",
                        lambda: Settings(enable_ocr=True, ocr_enabled_orgs=ORG))
    _bindings(monkeypatch, present=BINDINGS)
    monkeypatch.setattr("genios_engine.capture.documents.tesseract.shutil.which",
                        lambda _name: None)
    assert wiring.make_ocr(ORG) is None

    monkeypatch.setattr("genios_engine.capture.documents.tesseract.shutil.which",
                        lambda _name: "/usr/bin/tesseract")
    engine = wiring.make_ocr(ORG)
    assert engine is not None and engine.name == "tesseract-eng"
    # …and an org that is on neither list still gets nothing while the fleet default is off.
    monkeypatch.setattr(wiring, "get_settings",
                        lambda: Settings(enable_ocr=False, ocr_enabled_orgs=ORG))
    assert wiring.make_ocr("org_other") is None
    assert wiring.make_ocr(ORG) is not None


@pytest.mark.parametrize("missing", list(BINDINGS))
def test_the_binary_without_its_bindings_wires_nothing(monkeypatch, missing):
    """⛔ The regression `tesseract.py` says reached production, and the half no test covered.

    Its own words: *"the deploy image gained the apt packages while `pytesseract` and `Pillow` were
    in no requirements file, so the binary probe said yes, an engine was wired, and every scanned
    document came back `ocr_failed: ModuleNotFoundError`."* The binary being present is the state
    that makes this dangerous, because it is the state where a one-input probe says yes.

    Both bindings are parametrised: `all()` over two names is one `and` away from checking one.
    """
    import genios_engine.platform.wiring as wiring
    from genios_engine.platform.config import Settings

    monkeypatch.setattr(wiring, "get_settings",
                        lambda: Settings(enable_ocr=True, ocr_enabled_orgs=ORG))
    monkeypatch.setattr("genios_engine.capture.documents.tesseract.shutil.which",
                        lambda _name: "/usr/bin/tesseract")
    _bindings(monkeypatch, present=tuple(m for m in BINDINGS if m != missing))

    assert wiring.make_ocr(ORG) is None, (
        f"the binary is present and {missing} is not; wiring an engine here converts every scanned "
        f"document into ocr_failed: ModuleNotFoundError")


def test_the_probe_is_not_answered_by_the_binary_alone(monkeypatch):
    """The probe must ask about the bindings at all — a `shutil.which`-only probe passes the test
    above only by accident of what the host has installed."""
    from genios_engine.capture.documents import tesseract

    asked: list[str] = []
    monkeypatch.setattr(tesseract.shutil, "which", lambda _name: "/usr/bin/tesseract")

    import importlib.util as _iu
    real = _iu.find_spec
    monkeypatch.setattr(
        "genios_engine.capture.documents.tesseract.importlib.util.find_spec",
        lambda name, *a, **kw: (asked.append(name), object())[1] if name in BINDINGS
        else real(name, *a, **kw))

    assert tesseract.tesseract_available() is True
    assert set(asked) == set(BINDINGS), f"the probe must ask about both bindings; asked {asked}"
