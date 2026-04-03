"""
Insight detectors — each function takes (db, org_id) and returns List[Dict].
Grouped by category for maintainability.
"""

from app.graph.detectors.relationship import RELATIONSHIP_DETECTORS
from app.graph.detectors.commitment import COMMITMENT_DETECTORS
from app.graph.detectors.network import NETWORK_DETECTORS
from app.graph.detectors.data_quality import DATA_QUALITY_DETECTORS
from app.graph.detectors.disengagement import DISENGAGEMENT_DETECTORS
from app.graph.detectors.cross_tool import CROSS_TOOL_DETECTORS

ALL_DETECTORS = (
    RELATIONSHIP_DETECTORS
    + COMMITMENT_DETECTORS
    + NETWORK_DETECTORS
    + DATA_QUALITY_DETECTORS
    + DISENGAGEMENT_DETECTORS
    + CROSS_TOOL_DETECTORS
)
