"""
J0.2 — Thresholds

Configurable thresholds and weights for judgement scoring.
These can vary by org_mode (fundraising vs hiring vs default).
"""

# --- Risk Thresholds ---
RISK_AUTO_EXECUTE_MAX = 0.4     # risk below this → can auto-execute
RISK_HIGH_THRESHOLD = 0.7       # risk above this → classified as 'high'
RISK_MEDIUM_THRESHOLD = 0.4     # risk above this → classified as 'medium'

# --- Priority Thresholds ---
PRIORITY_MIN_SCORE = 0.3        # below this → low priority / distraction

# --- Factor Weights by Org Mode ---
ORG_MODE_WEIGHTS = {
    "fundraising": {
        "vip_investor": 1.5,
        "revenue": 0.8,
        "hiring": 0.3,
        "internal": 0.4,
    },
    "hiring": {
        "vip_investor": 0.5,
        "revenue": 0.5,
        "hiring": 1.5,
        "internal": 0.8,
    },
    "default": {
        "vip_investor": 1.0,
        "revenue": 1.0,
        "hiring": 1.0,
        "internal": 1.0,
    },
}

# --- Risk Weights ---
RISK_WEIGHTS = {
    "vip_recipient": 0.3,
    "external_contact": 0.2,
    "irreversible_action": 0.25,
    "sensitive_topic": 0.15,
    "existing_thread": -0.1,   # lowers risk (known context)
}

# --- Approval Thresholds ---
APPROVAL_REQUIRED_RISK_THRESHOLD = 0.6  # risk above this → needs approval
