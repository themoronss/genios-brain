from layers.layer1_retrieval.retrieval_engine import RetrievalEngine
from layers.layer2_judgement.judgement_engine import JudgementEngine


def test_layer2_judgement_engine():
    retrieval = RetrievalEngine()
    judgement = JudgementEngine()

    bundle = retrieval.run(
        intent="Follow up with Investor X",
        workspace_id="w1",
        actor_id="u1"
    )

    report = judgement.run(bundle)

    assert report.risk.level in ["low", "medium", "high"]
    assert report.policy.status == "needs_approval"
    assert report.needs_approval is True
    assert report.ok_to_act is True