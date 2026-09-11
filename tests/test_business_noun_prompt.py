"""Business context rides inside the existing, cache-keyed extraction call."""
from datetime import datetime, timezone

from genios_engine.capture.semantic import extractor as ex
from genios_engine.contracts.prepared_content import PreparedContent


TEXT = "Subject: Seed fundraising\nJane Doe\nPartner, Investor at Example Capital"


def request_for(text=TEXT):
    return ex.ExtractionRequest(org_id="o", event_id="e", source="gmail", profile_id="email",
        tier="T2", prepared=PreparedContent(prepared_content_id="e", event_id="e",
            clean_text=text, language="en"),
        envelope=ex.EventEnvelope(direction="inbound", sender="Jane Doe <jane@example.com>",
            recipients=("rohit@genios.example",), subject="Seed fundraising"),
        eval_time=datetime(2026, 9, 10, 12, tzinfo=timezone.utc), timezone="UTC", locale="en_US")


def test_the_existing_call_names_all_nine_business_fields_and_the_authority_boundary():
    call = ex.assemble_call(request_for(), nonce="deadbeefcafe0001")
    for field in ("party.role", "relationship.nature", "deal.stage", "deal.value", "person.title",
                  "company.industry", "thread.objective", "campaign.objective", "organization.relationship"):
        assert field in call.prompt
    for rule in ("BUSINESS FACTS", "signature", "subject", "judgement", "observed",
                 "unknown", "A send alone", "existing named campaign"):
        assert rule in call.prompt
    # Envelope is already a cache-key component; old answers cannot serve the new instruction.
    assert "BUSINESS FACTS" in call.envelope
    assert TEXT in call.prompt
    assert "Do not invent offsets into the envelope" in call.envelope
