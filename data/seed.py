from supabase import create_client
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from google import genai
from google.genai import types
import uuid, os
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
qdrant = QdrantClient(url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

ORG_ID = os.getenv("ORG_ID")


def store_context(context_type, content, entity_name=None):
    supabase.table("org_context").insert(
        {
            "org_id": ORG_ID,
            "context_type": context_type,
            "entity_name": entity_name,
            "content": content,
        }
    ).execute()

    # Generate embedding using Gemini
    result = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=content,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT", output_dimensionality=384
        ),
    )
    vector = result.embeddings[0].values

    qdrant.upsert(
        collection_name="genios_context",
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "org_id": ORG_ID,
                    "context_type": context_type,
                    "entity_name": entity_name,
                    "content": content,
                },
            )
        ],
    )


# ====== Add Real Context Below ======

# Organization Profile
store_context(
    "profile",
    """
GeniOS Brain is a decision and cognition layer for agentic AI systems.
We are pre-seed stage, building the governance and intelligence layer
that sits between AI orchestrators and agents. Current focus: prototype validation.
Stage: pre-seed, building prototype. Location: India.
""",
)

# Policies - Critical Rules
store_context(
    "policy", "Follow up with investors maximum once every 6 days unless they respond."
)
store_context(
    "policy", "Never share financial projections without founder approval first."
)
store_context(
    "policy",
    "Always personalize investor outreach based on their portfolio thesis before sending.",
)
store_context(
    "policy",
    "Escalate to founder when any investor responds positively or requests a meeting.",
)
store_context(
    "policy",
    "Do not follow up with investors who have explicitly said no in last 90 days.",
)
store_context(
    "policy", "All external communications must reference latest product update."
)

# Key Relationships - Investors
store_context(
    "relationship",
    """Investor Rahul at SeedFund. Focus areas: B2B SaaS, AI infrastructure, developer tools.
    Last contact: 10 days ago. Status: warm lead. Interested in governance layers for AI.
    Next action: Share product update about prototype progress.""",
    entity_name="Rahul",
)

store_context(
    "relationship",
    """Investor Priya at TechVentures. Focus: Early-stage AI/ML startups, enterprise software.
    Last contact: 3 days ago. Status: very warm, requested demo.
    Next action: Schedule demo call within 48 hours.""",
    entity_name="Priya",
)

store_context(
    "relationship",
    """Investor Amit at GrowthCapital. Focus: Series A+ B2B companies.
    Last contact: 45 days ago. Status: cold, said timing not right.
    Next action: Do not contact until Q3 2026.""",
    entity_name="Amit",
)

# Entity States - Current status
supabase.table("entity_state").insert(
    {
        "org_id": ORG_ID,
        "entity_type": "investor",
        "entity_name": "Rahul",
        "current_state": {
            "status": "warm",
            "last_contact_days_ago": 10,
            "follow_up_due": True,
            "next_action": "share product update",
            "meeting_scheduled": False,
        },
    }
).execute()

supabase.table("entity_state").insert(
    {
        "org_id": ORG_ID,
        "entity_type": "investor",
        "entity_name": "Priya",
        "current_state": {
            "status": "very_warm",
            "last_contact_days_ago": 3,
            "follow_up_due": True,
            "next_action": "schedule demo",
            "meeting_scheduled": False,
            "requested_demo": True,
        },
    }
).execute()

supabase.table("entity_state").insert(
    {
        "org_id": ORG_ID,
        "entity_type": "investor",
        "entity_name": "Amit",
        "current_state": {
            "status": "cold",
            "last_contact_days_ago": 45,
            "follow_up_due": False,
            "next_action": "wait until Q3 2026",
            "meeting_scheduled": False,
            "said_no": True,
        },
    }
).execute()

print("Seed data inserted: profile + 6 policies + 3 investors + 3 entity states")
