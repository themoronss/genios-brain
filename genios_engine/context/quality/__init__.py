"""L2.5 · Context Quality — the group whose law is that most damaging false positives originate
HERE, not at Layer 4. A card that is confidently wrong is almost always a quality failure wearing
a reasoning failure's clothes.

X6 lands two of the group's units and nothing else; the package is laid out so the rest arrive
beside them rather than through them.

    `epoch.py`      L-5 · the coverage epoch. The window over which `coverage_ready` was true for
                    a source, so a negative inference can be REVOKED when the sources move.
    `lens.py`       one org's tri-state coverage, read once and injected — the thing that makes
                    the classifier pure.
    `missing.py`    L2.5.5-U1 · BLG-15 · typed absence. The cascade that decides whether a gap is
                    a finding, a blind spot, a stale reading or nothing at all.
    `inference.py`  the licence as the layers ABOVE see it: the seam that makes `ContextAdapter`
                    ask before it says "there is no amendment".

`AbsenceType` and `MissingFact` are NOT here. They are boundary vocabulary and live in
`contracts/quality.py`, where `licenses_negative_inference` is computed and unsettable — this
package is what decides which member applies, and it deliberately cannot widen the rule.
"""

from genios_engine.context.quality.epoch import (CoverageEpoch, CoverageWindow, EpochChange,
                                                 advance_epochs, coverage_over, current_epochs,
                                                 epoch_at, epochs_over, stale_coverage)
from genios_engine.context.quality.inference import absence_metadata, may_infer_absent
from genios_engine.context.quality.lens import CoverageLens, read_coverage_lens
from genios_engine.context.quality.missing import (AbsenceSubject, Expectation, StoredAbsence,
                                                   absence_counts, absent_fields,
                                                   classify_absence, classify_all, detect_missing,
                                                   expectations_from_spec, findings, missing_fact,
                                                   read_absences, refresh_typed_absences,
                                                   unknowable_fields)

__all__ = ["AbsenceSubject", "CoverageEpoch", "CoverageLens", "CoverageWindow", "EpochChange",
           "Expectation", "StoredAbsence", "absence_counts", "absence_metadata", "absent_fields",
           "advance_epochs", "classify_absence", "classify_all", "coverage_over",
           "current_epochs", "detect_missing", "epoch_at", "epochs_over",
           "expectations_from_spec", "findings", "may_infer_absent", "missing_fact",
           "read_absences", "read_coverage_lens", "refresh_typed_absences", "stale_coverage",
           "unknowable_fields"]
