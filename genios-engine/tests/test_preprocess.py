from __future__ import annotations

from genios_engine.capture.preprocess.preprocess import preprocess


def test_masks_high_risk_pii_and_maps_offsets_back():
    src = "Please verify PAN ABCDE1234F before Friday."
    pc = preprocess(src)

    # PAN masked, replaced by a token
    assert "ABCDE1234F" not in pc.clean_text
    assert "[PAN]" in pc.clean_text
    assert len(pc.masked_spans) == 1 and pc.masked_spans[0].pii_type == "PAN"

    # offset map: the token position maps back to the PAN's start in the source
    token_pos = pc.clean_text.index("[PAN]")
    assert pc.to_source_offset(token_pos) == src.index("ABCDE1234F")

    # a passthrough char maps 1:1
    p_pos = pc.clean_text.index("Please")
    assert pc.to_source_offset(p_pos) == src.index("Please")


def test_phone_not_masked_by_default_but_masked_when_enabled():
    src = "Call me at 9876543210 today."
    assert "9876543210" in preprocess(src).clean_text                 # default: kept
    assert "9876543210" not in preprocess(src, mask_phone=True).clean_text  # opt-in: masked


def test_language_detection():
    assert preprocess("kal tak bhej dunga, jaldi karo").language == "hinglish"
    assert preprocess("Please send the revised contract by Friday").language == "en"


def test_protected_line_has_deadline_and_question():
    pc = preprocess("Budget is approved. Can you send the contract by Friday?")
    assert pc.protected_spans, "deadline + question line should be protected"
