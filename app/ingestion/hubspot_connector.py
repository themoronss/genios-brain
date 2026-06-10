"""
HubSpot connector — OAuth 2.0 (authorization code) + contacts/deals API.

Scopes used:
  crm.objects.contacts.read
  crm.objects.deals.read
  oauth

OAuth flow:
  1. GET /auth/hubspot/connect?org_id=... → redirect to HubSpot consent
  2. GET /auth/hubspot/callback?code=...&state=... → exchange code, store tokens
"""

import requests
from urllib.parse import urlencode

from app.config import HUBSPOT_CLIENT_ID, HUBSPOT_CLIENT_SECRET, HUBSPOT_REDIRECT_URI

HUBSPOT_AUTH_URL = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://api.hubapi.com/oauth/v1/token"
HUBSPOT_API_BASE = "https://api.hubapi.com"

HUBSPOT_SCOPES = [
    "crm.objects.contacts.read",
    "crm.objects.deals.read",
    "oauth",
]


def get_hubspot_authorize_url(state: str) -> str:
    """Build the HubSpot OAuth authorization URL."""
    params = {
        "client_id": HUBSPOT_CLIENT_ID,
        "redirect_uri": HUBSPOT_REDIRECT_URI,
        "scope": " ".join(HUBSPOT_SCOPES),
        "state": state,
    }
    return f"{HUBSPOT_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    """
    Exchange authorization code for access + refresh tokens.
    Returns dict with: access_token, refresh_token, expires_in, hub_id, hub_domain.
    """
    response = requests.post(
        HUBSPOT_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": HUBSPOT_CLIENT_ID,
            "client_secret": HUBSPOT_CLIENT_SECRET,
            "redirect_uri": HUBSPOT_REDIRECT_URI,
            "code": code,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    response.raise_for_status()
    data = response.json()
    if "access_token" not in data:
        raise ValueError(f"HubSpot token exchange failed: {data}")

    # Fetch portal info (hub_id, hub_domain)
    portal = _get_portal_info(data["access_token"])
    data["hub_id"] = portal.get("portalId")
    data["hub_domain"] = portal.get("uiDomain", "")
    return data


def refresh_access_token(refresh_token: str) -> dict:
    """Exchange refresh token for a new access token."""
    response = requests.post(
        HUBSPOT_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": HUBSPOT_CLIENT_ID,
            "client_secret": HUBSPOT_CLIENT_SECRET,
            "refresh_token": refresh_token,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    response.raise_for_status()
    return response.json()


def _get_portal_info(access_token: str) -> dict:
    """Fetch portal (hub) info — used for the account_email key prefix."""
    response = requests.get(
        f"{HUBSPOT_API_BASE}/integrations/v1/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if response.ok:
        return response.json()
    return {}


def fetch_contacts(access_token: str, after: str = None, limit: int = 100) -> dict:
    """
    Fetch HubSpot contacts (paginated).
    Returns: {results: [...], paging: {next: {after: ...}}}
    Properties returned: firstname, lastname, email, company, jobtitle,
                         phone, lifecyclestage, hs_lead_status, lastmodifieddate
    """
    params = {
        "limit": limit,
        "properties": ",".join([
            "firstname", "lastname", "email", "company", "jobtitle",
            "phone", "lifecyclestage", "hs_lead_status", "lastmodifieddate",
            "createdate",
        ]),
    }
    if after:
        params["after"] = after

    response = requests.get(
        f"{HUBSPOT_API_BASE}/crm/v3/objects/contacts",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
    )
    response.raise_for_status()
    return response.json()


def fetch_deals(access_token: str, after: str = None, limit: int = 100) -> dict:
    """
    Fetch HubSpot deals (paginated).
    Properties returned: dealname, dealstage, amount, closedate,
                         pipeline, hs_deal_stage_probability, associatedcompanyids
    """
    params = {
        "limit": limit,
        "properties": ",".join([
            "dealname", "dealstage", "amount", "closedate",
            "pipeline", "hs_deal_stage_probability", "createdate",
            "hubspot_owner_id",
        ]),
        "associations": "contacts",
    }
    if after:
        params["after"] = after

    response = requests.get(
        f"{HUBSPOT_API_BASE}/crm/v3/objects/deals",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
    )
    response.raise_for_status()
    return response.json()


def fetch_all_contacts(access_token: str) -> list:
    """Fetch all contacts across all pages."""
    contacts = []
    after = None
    while True:
        page = fetch_contacts(access_token, after=after)
        contacts.extend(page.get("results", []))
        paging = page.get("paging", {})
        after = paging.get("next", {}).get("after")
        if not after:
            break
    return contacts


def fetch_all_deals(access_token: str) -> list:
    """Fetch all deals across all pages."""
    deals = []
    after = None
    while True:
        page = fetch_deals(access_token, after=after)
        deals.extend(page.get("results", []))
        paging = page.get("paging", {})
        after = paging.get("next", {}).get("after")
        if not after:
            break
    return deals
