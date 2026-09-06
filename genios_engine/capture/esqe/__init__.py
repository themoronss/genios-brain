"""L1.6 · ESQE — Enterprise Signal Qualification. Stage S4, the single gateway to Layer 2.

*"Decide what kind of thing this is, whether it matters, and how big it is."* This package's
group law is one sentence and it is the reason the package exists: **all scoring lives here, and
none of it is done by a model.** Everything a founder is eventually ranked by has to be
reproducible from the same stored extraction, which a model's opinion about the same prose is
not.

Two units ship in this module set:

* `detector.py`   — ALG-15, L1.6.1-U1: a deterministic predicate table over the validated
  `ExtractionResult`. Answers *is there a signal here, and which kinds*. One event may legitimately
  produce several.
* `classifier.py` — ALG-16, L1.6.3-U1: a constant precedence order over the closed 14-member
  taxonomy. Answers *which of those kinds is the primary one*.
* `importance.py` — ALG-17, L1.6.7: five weighted integer terms over the VALIDATED facts.
  Answers *how big is this thing*, which is the number Layer 4's utility formula was missing
  and the reason `priority_override` replaced that formula outright.

They are separate because a detector that also ranked would make adding a predicate a change to
the ordering, and the ordering is the half that has to stay frozen for a March card and a
September card to be comparable.

Neither unit reads a clock, a database or a model. `eval_time` is a parameter.
"""

from genios_engine.capture.esqe.classifier import (PRECEDENCE, SignalClassification,
                                                   classify_signals, precedence_rank)
from genios_engine.capture.esqe.detector import (MAX_SIGNALS_PER_EVENT, DetectedSignal,
                                                 DetectionInput, DetectionOutcome, detect_signals)
from genios_engine.capture.esqe.importance import (IMPORTANCE_VERSION, IMPORTANCE_WEIGHTS_V1,
                                                   BaselineObservation, ImportanceComponents,
                                                   ImportanceScore, OrgBaseline,
                                                   compute_org_baseline, explain_importance,
                                                   score_importance)

__all__ = [
    "IMPORTANCE_VERSION",
    "IMPORTANCE_WEIGHTS_V1",
    "MAX_SIGNALS_PER_EVENT",
    "PRECEDENCE",
    "BaselineObservation",
    "DetectedSignal",
    "DetectionInput",
    "DetectionOutcome",
    "ImportanceComponents",
    "ImportanceScore",
    "OrgBaseline",
    "SignalClassification",
    "classify_signals",
    "compute_org_baseline",
    "detect_signals",
    "explain_importance",
    "precedence_rank",
    "score_importance",
]
