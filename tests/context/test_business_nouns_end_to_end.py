"""One fake model call; real extraction, ALG-08, QES adapter and graph fact/ref SQL."""
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.capture.semantic.extractor import extract
from genios_engine.capture.validate.spans import apply_verdicts
from genios_engine.context import pipeline
from genios_engine.context.qes_adapter import adapt_qes_extraction
from genios_engine.context.situations import coverage_score
from tests.test_business_noun_prompt import request_for
from .test_business_noun_authority import business_store
from .test_business_fact_store import fact_store
from .test_support_derived_provenance import NOW


@pytest.mark.parametrize("supported", [True, False])
def test_signature_and_stated_purpose_reach_graph_receipts_or_remain_explicitly_missing(business_store,supported):
    body = "Subject: This thread is for fundraising.\nJane\nPartner and Investor at Example Capital." if supported else "Thanks, received."
    facts = []
    if supported:
        for field,subject,value,quote in [
            ("party.role","Jane","investor","Partner and Investor at Example Capital."),
            ("person.title","Jane","Partner","Partner and Investor at Example Capital."),
            ("thread.objective","thread","fundraising","This thread is for fundraising.")]:
            start = body.index(quote)
            facts.append(dict(field=field,subject=subject,value=value,standing="observed",
                confidence_bp=9000,evidence=[dict(quote=quote,start_offset=start,end_offset=start+len(quote))]))
    payload = dict(intent="inform",stance="neutral",business_facts=facts)
    class FakeModel:
        model = "fixture-2026-09-10"
        temperature = 0
        calls = 0
        def call(self,prompt,*,max_tokens=4096):
            self.calls += 1
            assert "business_facts" in prompt and body in prompt
            return SimpleNamespace(parsed=payload,raw=json.dumps(payload),input_tokens=100,
                output_tokens=30,model=self.model,ok=True,error=None)
    model = FakeModel()
    outcome = extract(request_for(body),llm=model,nonce="deadbeefcafe0001")
    assert model.calls == 1 and outcome.result is not None
    verified,_ = apply_verdicts(outcome.result,body,locale="en_US")
    qes = adapt_qes_extraction(verified.model_dump(mode="json"),confidence_bp=9000)
    pipeline.process_event(org_id="o",event_id="e",source="gmail",content=body,
        sender_email="jane@example.com",sender_name="Jane",recipient_emails=[],thread_id="t",
        occurred_at=NOW,llm=None,store=business_store,qualified_extraction=qes)
    with business_store.engine.connect() as c:
        rows = c.execute(text("select f.field,r.event_id,r.evidence from graph_facts f join graph_source_refs r on r.fact_version_id=f.fact_version_id where f.org_id='o' and f.status='active'")).mappings().all()
        fields = {r["field"] for r in rows}
        expected = {"party.role":"party.role","thread.objective":"thread.objective"}
        coverage,missing = coverage_score(present_fields=fields,expected=expected)
        assert (coverage,missing) == ((100,[]) if supported else (0,["party.role","thread.objective"]))
        assert len(rows) == (3 if supported else 0)
        for row in rows:
            receipt = json.loads(row["evidence"])
            assert row["event_id"] == "e" and receipt["standing"] == "observed"
            assert receipt["spans"][0]["quote"] in body
            assert receipt["spans"][0]["verified"] is True
