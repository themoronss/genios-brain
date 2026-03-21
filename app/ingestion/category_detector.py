"""
Category Detector — Entity type classification with confidence scoring.

PDF spec: "Domain match against a curated VC/investor domain list (~500 known firms).
           Every entity gets a category_confidence score."

Confidence tiers:
  0.95 — VC domain match (hardcoded list)
  0.80 — Email signature role match (CEO/Founder/Partner at known firm pattern)
  0.75 — LLM classified as investor
  0.65 — Thread keyword match (term sheet, cap table, due diligence, etc.)
  0.55 — LLM classified as non-investor category
  0.50 — Default (no signal)
"""

# ── VC / Investor Firm Domains ────────────────────────────────────────────────
# Curated list of known VC, PE, and angel investor firm domains
VC_DOMAINS = {
    # Tier 1 — Major US VC
    "sequoiacap.com", "a16z.com", "andreessenhorowitz.com", "accel.com",
    "kpcb.com", "kleinerperkins.com", "benchmark.com", "greylock.com",
    "lightspeedvp.com", "nea.com", "generalatlantic.com", "tpg.com",
    "kkr.com", "carlyle.com", "bain.com", "apollo.com",
    "firstround.com", "founderfund.com", "khoslaventures.com",
    "bvp.com", "bessemervp.com", "redpoint.com", "usv.com",
    "unionsquareventures.com", "spark.com", "sparkcapital.com",
    "matrix.com", "matrixpartners.com", "ivp.com", "ivpvc.com",
    "dragoneer.com", "coatue.com", "tiger.com", "tigerbrokers.com",
    "gv.com", "capitalg.com", "googleventures.com",
    "intelcapital.com", "salesforceventures.com",
    "microsoftventures.com", "nvventures.com",

    # Tier 2 — Growth & Multi-stage
    "softbank.com", "softbankvision.com", "svf.com",
    "insight.com", "insightpartners.com",
    "summit.com", "summitpartners.com",
    "warburg.com", "warburgpincus.com",
    "permira.com", "advent.com", "adventinternational.com",
    "francisco.com", "franciscopartners.com",
    "thoma.com", "thomabravo.com", "vistaequitypartners.com",
    "hggc.com", "silverlake.com", "silverlakegroup.com",

    # Tier 3 — Seed / Early stage
    "ycombinator.com", "yc.com", "combinator.com",
    "500.co", "500startups.com", "techstars.com",
    "angelpad.com", "seedcamp.com", "betaworks.com",
    "precursor.vc", "hustle.vc", "hustle.fund",
    "initialized.com", "initializedcapital.com",
    "floodgate.com", "floodgatevc.com",
    "dcvc.com", "deepcorevc.com",

    # Tier 4 — India / Asia-focused
    "accel.in", "sequoia.in", "nexusvp.com",
    "blume.vc", "blumekona.com", "blumekona.vc",
    "kalaari.com", "kalaari.vc", "stellarispvp.com",
    "elevationcapital.com", "saif.com", "saifpartners.com",
    "matrix.in", "matrixpartners.in",
    "lightboxvc.com", "lightboxvc.in",
    "chiratae.com", "chirataeventures.com",
    "india.sequoiacap.com",
    "softtbank.co.jp", "softbank.co.jp",
    "mirae.com", "miraeventures.com",
    "dst.com", "dstglobal.com",
    "Tiger21.com",

    # Tier 5 — European
    "indexventures.com", "atomico.com", "balderton.com",
    "creandum.com", "northzone.com", "earlybird.com",
    "hv.com", "hvventures.com", "lakestar.com",
    "speedinvest.com", "point9.vc", "point9capital.com",

    # Tier 6 — Corporate / CVC
    "indigoag.com", "boschventure.com",
    "qualcommventures.com", "comcastventures.com",
    "amdventures.com", "ciscoventures.com",
    "sapventures.com", "oracleventures.com",

    # Tier 7 — Family offices / Angels (common domains)
    "yieldstreet.com", "angellist.com", "syndicateroom.com",
    "republic.co", "wefunder.com", "seedinvest.com",
}

# ── Thread/Topic Keywords for Investor Classification ─────────────────────────
INVESTOR_KEYWORDS = {
    "term sheet", "valuation", "due diligence", "cap table", "round",
    "series a", "series b", "series c", "seed round", "pre-seed",
    "investment", "investor", "portfolio", "fund", "lp", "gp",
    "carried interest", "equity stake", "dilution", "convertible note",
    "safe note", "priced round", "lead investor", "co-investor",
    "pitch deck", "deck review", "post-money", "pre-money",
    "runway", "burn rate", "mrr", "arr", "unit economics",
    "board seat", "board observer", "pro-rata rights",
}

# ── Role Keywords for Investor Pattern ────────────────────────────────────────
INVESTOR_ROLES = {
    "partner", "general partner", "gp", "managing partner", "managing director",
    "principal", "associate", "analyst", "venture partner", "lp",
    "limited partner", "angel investor", "investor", "fund manager",
    "investment director", "investment manager", "portfolio manager",
    "vice president", "vp investments",
}

# ── Vendor Keywords ────────────────────────────────────────────────────────────
VENDOR_KEYWORDS = {
    "invoice", "payment", "contract", "proposal", "quote", "pricing",
    "service agreement", "sow", "statement of work", "vendor",
    "subscription", "renewal", "license", "procurement", "purchase order",
}

# ── Customer Keywords ──────────────────────────────────────────────────────────
CUSTOMER_KEYWORDS = {
    "onboarding", "support", "feature request", "bug report", "ticket",
    "trial", "demo", "signup", "account", "customer success",
    "implementation", "integration help", "user feedback",
}


def detect_entity_category(
    email: str,
    name: str = "",
    contact_role: str = None,
    thread_topics: list = None,
    email_body: str = "",
) -> tuple[str, float]:
    """
    Detect entity type and confidence score for a contact.

    Returns:
        (entity_type, confidence) tuple
        entity_type: 'investor' | 'vendor' | 'customer' | 'team' | 'other'
        confidence: 0.0 to 1.0
    """
    domain = email.split("@")[-1].lower() if "@" in email else ""
    body_lower = (email_body or "").lower()
    topics_lower = [t.lower() for t in (thread_topics or [])]
    role_lower = (contact_role or "").lower()

    # ── 1. VC Domain Match (highest confidence) ───────────────────────────────
    if domain in VC_DOMAINS:
        return ("investor", 0.95)

    # ── 2. LLM said investor ──────────────────────────────────────────────────
    if role_lower == "investor":
        return ("investor", 0.75)

    # ── 3. Role keyword match (signature parsing) ─────────────────────────────
    if any(inv_role in role_lower for inv_role in INVESTOR_ROLES):
        return ("investor", 0.80)

    # ── 4. Thread topic keyword match ─────────────────────────────────────────
    topic_text = " ".join(topics_lower) + " " + body_lower
    investor_hits = sum(1 for kw in INVESTOR_KEYWORDS if kw in topic_text)
    if investor_hits >= 2:
        return ("investor", 0.65)
    elif investor_hits == 1 and role_lower in ("advisor", "partner", "other"):
        return ("investor", 0.55)

    # ── 5. Vendor detection ───────────────────────────────────────────────────
    if role_lower == "vendor":
        return ("vendor", 0.75)
    vendor_hits = sum(1 for kw in VENDOR_KEYWORDS if kw in topic_text)
    if vendor_hits >= 2:
        return ("vendor", 0.65)

    # ── 6. Customer detection ─────────────────────────────────────────────────
    if role_lower == "customer":
        return ("customer", 0.75)
    customer_hits = sum(1 for kw in CUSTOMER_KEYWORDS if kw in topic_text)
    if customer_hits >= 2:
        return ("customer", 0.65)

    # ── 7. LLM-assigned non-investor roles ────────────────────────────────────
    role_map = {
        "partner": ("partner", 0.55),
        "advisor": ("advisor", 0.55),
        "candidate": ("candidate", 0.55),
        "team": ("team", 0.55),
        "media": ("media", 0.55),
        "lead": ("lead", 0.55),
    }
    if role_lower in role_map:
        return role_map[role_lower]

    # ── 8. Default ────────────────────────────────────────────────────────────
    return ("other", 0.50)


def is_vc_domain(email: str) -> bool:
    """Quick check if email domain is a known VC firm."""
    domain = email.split("@")[-1].lower() if "@" in email else ""
    return domain in VC_DOMAINS
