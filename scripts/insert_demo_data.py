"""
Demo data insert — psycopg2 direct, no SQLAlchemy text() issues.
Run: cd genios-brain && source venv/bin/activate && python3 scripts/insert_demo_data.py
"""
import os, sys, json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()
ORG_ID = "0031178b-2f9d-4881-88d7-b39218292077"
DB_URL = os.getenv("DATABASE_URL")

def ago(days):
    return datetime.now(timezone.utc) - timedelta(days=days)

def sh(points):  # sentiment_history
    return json.dumps([{"timestamp": (datetime.now(timezone.utc) - timedelta(days=d)).isoformat(), "sentiment": s, "source": "email"} for d, s in points])

CONTACTS = [
    {
        "email": "arjun.kapoor@sequoiacap.com",
        "name": "Arjun Kapoor",
        "company": "Sequoia India",
        "entity_type": "investor",
        "classification": "investor",
        "classification_confidence": 0.97,
        "last_sentiment": 0.72,
        "last_interaction_at": ago(18),
        "interaction_count": 4,
        "sentiment_history": sh([(40,0.5),(30,0.6),(20,0.72),(18,0.72)]),
        "communication_style": json.dumps({"preferred_channel":"email","avg_response_hours":6,"prefers_short":False,"formality":"formal"}),
        "metadata": json.dumps({"ticket_size":"$500K","stage":"seed","deck_opens":6,"fund":"Sequoia Surge"}),
        "interactions": [
            ("outbound","GeniOS — Intro via Sandeep Agrawal","Sent intro email to Arjun via warm intro from Sandeep. Shared 2-line pitch.",0.5,ago(40),"email_one_way"),
            ("inbound","Re: GeniOS intro","Arjun replied positively. Asked for the deck and suggested a call next week.",0.75,ago(35),"email_reply"),
            ("outbound","GeniOS Pitch Deck + 3-min Demo","Sent 12-slide deck and Loom recording. Asked for Thursday 4PM slot.",0.7,ago(22),"email_one_way"),
            ("inbound","[No reply — deck opened 6x]","Arjun opened the deck 6 times over 4 days. Last open 3 days ago. No reply.",0.72,ago(18),"email_one_way"),
        ],
        "commitments": [
            ("Schedule follow-up call with Arjun — he said 'let's talk next week' on May 7","us",ago(11),"OVERDUE"),
            ("Send traction update: MoM growth numbers + enterprise pilot status","us",ago(5),"OVERDUE"),
        ],
    },
    {
        "email": "priya.nair@zomato.com",
        "name": "Priya Nair",
        "company": "Zomato",
        "entity_type": "lead",
        "classification": "customer",
        "classification_confidence": 0.89,
        "last_sentiment": 0.31,
        "last_interaction_at": ago(10),
        "interaction_count": 6,
        "sentiment_history": sh([(60,0.8),(45,0.75),(30,0.65),(15,0.45),(10,0.31)]),
        "communication_style": json.dumps({"preferred_channel":"whatsapp","avg_response_hours":2,"prefers_short":True,"formality":"casual"}),
        "metadata": json.dumps({"deal_size":"28L INR/yr","role":"Head of Engineering","internal_champion":True,"procurement_contact":"Ravi Mehta","whatsapp_reply_rate":"100%","email_reply_rate":"42%"}),
        "interactions": [
            ("inbound","Saw GeniOS at YC Demo Day!","Priya reached out after demo day. Said: 'this is exactly what we've been looking for for our brand partnerships team'.",0.85,ago(60),"email_reply"),
            ("outbound","GeniOS Full Demo — Zomato Eng Team","90-min Zoom demo with Priya + 3 team members. She said 'let's move forward'. Agreed to intro procurement.",0.8,ago(45),"meeting"),
            ("outbound","Intro to Ravi Mehta (Procurement)","Priya cc'd Ravi Mehta in procurement. Rohit sent proposal directly to Ravi.",0.7,ago(25),"email_one_way"),
            ("outbound","GeniOS Proposal — 50 seats, ₹28L/yr","Sent commercial proposal to procurement. No response in 3 weeks.",0.5,ago(21),"email_one_way"),
            ("outbound","Quick follow-up on proposal","Gentle nudge to Ravi. Still no reply.",0.4,ago(14),"email_one_way"),
            ("outbound","Hey Priya — any update from procurement?","Pinged Priya directly. No reply in 10 days. Last seen LinkedIn 3 days ago.",0.3,ago(10),"email_one_way"),
        ],
        "commitments": [
            ("Send competitive comparison vs Salesforce + HubSpot — Ravi's procurement asked for this","us",ago(7),"OVERDUE"),
            ("Follow up with Priya on WhatsApp — email not working, she replies on WhatsApp within 2 hours","us",ago(5),"OVERDUE"),
        ],
    },
    {
        "email": "rahul.mehta.ca@gmail.com",
        "name": "Rahul Mehta",
        "company": "Mehta & Associates (CA Firm)",
        "entity_type": "contact",
        "classification": "contact",
        "classification_confidence": 0.82,
        "last_sentiment": 0.65,
        "last_interaction_at": ago(92),
        "interaction_count": 9,
        "sentiment_history": sh([(180,0.7),(150,0.72),(92,0.65)]),
        "communication_style": json.dumps({"preferred_channel":"whatsapp","avg_response_hours":3,"prefers_short":True,"formality":"informal"}),
        "metadata": json.dumps({"referrals_sent":4,"referral_value_total_inr":4800000,"last_referral_company":"Suresh Industries","last_referral_deal_closed":True,"last_referral_value_inr":1200000,"relationship_type":"top_referral_source"}),
        "interactions": [
            ("inbound","Intro: Suresh Gupta — needs what you're building","Rahul introduced Rohit to Suresh Gupta of Suresh Industries. 'He needs exactly what you're building.'",0.75,ago(150),"email_reply"),
            ("outbound","Re: Intro — scheduling demo with Suresh","Followed up on intro. Demo scheduled.",0.7,ago(148),"email_reply"),
            ("outbound","Suresh Industries deal closed! ₹12L","Rohit sent a brief update to Rahul that Suresh signed. No specific thank-you or appreciation sent.",0.0,ago(92),"email_one_way"),
        ],
        "commitments": [
            ("Send personal thank-you to Rahul for Suresh referral — ₹12L deal closed because of him","us",ago(85),"OVERDUE"),
            ("Update Rahul on Suresh's success + ask if anyone else in his network could benefit","us",ago(30),"OPEN"),
        ],
    },
    {
        "email": "karan.shah@kalaari.com",
        "name": "Karan Shah",
        "company": "Kalaari Capital",
        "entity_type": "investor",
        "classification": "investor",
        "classification_confidence": 0.95,
        "last_sentiment": 0.55,
        "last_interaction_at": ago(45),
        "interaction_count": 5,
        "sentiment_history": sh([(90,0.6),(60,0.65),(45,0.55)]),
        "communication_style": json.dumps({"preferred_channel":"email","avg_response_hours":24,"prefers_short":False,"formality":"semi-formal"}),
        "metadata": json.dumps({"ticket_size":"50L INR","stage":"pre-seed","fund":"Kalaari Capital","specifically_asked_for":"Q1 numbers: ARR, MoM growth, enterprise pipeline"}),
        "interactions": [
            ("outbound","GeniOS — Intro from Ankit Sharma","Cold intro via common connection. Sent 1-pager.",0.5,ago(90),"email_one_way"),
            ("inbound","Re: GeniOS — interesting angle","Karan replied. Said the relationship intelligence angle is unique. Wants to see Q1 numbers before any decision.",0.7,ago(60),"email_reply"),
            ("outbound","[DRAFT NEVER SENT] GeniOS Q1 Numbers","Q1 ended April 30. 3x YoY growth, 12 paying customers, 2 enterprise pilots. Numbers never sent to Karan.",0.0,ago(45),"email_one_way"),
        ],
        "commitments": [
            ("Send Q1 numbers to Karan — he SPECIFICALLY asked: ARR, MoM growth, enterprise pipeline. Q1 done April 30, still not sent.","us",ago(25),"OVERDUE"),
        ],
    },
    {
        "email": "neha.agarwal.advisor@gmail.com",
        "name": "Neha Agarwal",
        "company": "Ex-Freshworks CPO (Advisor)",
        "entity_type": "advisor",
        "classification": "advisor",
        "classification_confidence": 0.93,
        "last_sentiment": 0.5,
        "last_interaction_at": ago(40),
        "interaction_count": 6,
        "sentiment_history": sh([(80,0.75),(60,0.7),(40,0.5)]),
        "communication_style": json.dumps({"preferred_channel":"linkedin","avg_response_hours":12,"prefers_short":True,"formality":"casual"}),
        "metadata": json.dumps({"equity_pct":0.25,"intros_promised":3,"intros_done":1,"intros_pending":["PhonePe CTO","Meesho Head of Growth"],"role":"Product Strategy Advisor"}),
        "interactions": [
            ("outbound","Advisory Agreement — GeniOS (0.25% for 3 intros)","Sent advisory agreement. 0.25% equity, 3 warm enterprise intros.",0.7,ago(80),"email_one_way"),
            ("inbound","Re: Advisory Agreement — signed + first intro coming","Neha signed. Will intro: Swiggy VP Product, PhonePe CTO, Meesho Growth Head.",0.8,ago(70),"email_reply"),
            ("inbound","Intro: Sanya Gupta (Swiggy Growth Head)","Neha made 1st intro to Sanya at Swiggy. 2 more still pending.",0.7,ago(55),"email_reply"),
            ("outbound","Thanks! + PhonePe/Meesho intros?","Thanked Neha for Swiggy intro. Asked about PhonePe and Meesho. No reply in 40 days.",0.5,ago(40),"email_one_way"),
        ],
        "commitments": [
            ("Follow up with Neha on 2 pending intros she promised: PhonePe CTO + Meesho Growth Head","us",ago(25),"OPEN"),
        ],
    },
    {
        "email": "deepak.joshi@hdfc.com",
        "name": "Deepak Joshi",
        "company": "HDFC Bank",
        "entity_type": "lead",
        "classification": "customer",
        "classification_confidence": 0.91,
        "last_sentiment": 0.42,
        "last_interaction_at": ago(14),
        "interaction_count": 5,
        "sentiment_history": sh([(35,0.7),(25,0.75),(14,0.42)]),
        "communication_style": json.dumps({"preferred_channel":"email","avg_response_hours":48,"prefers_short":False,"formality":"formal"}),
        "metadata": json.dumps({"deal_size":"85L INR/yr","role":"CTO","board_presentation_date":"2026-06-10","pilot_verbally_agreed":True,"days_to_board_presentation":16}),
        "interactions": [
            ("outbound","GeniOS Enterprise — HDFC Relationship Management","Personalized cold outreach to Deepak around HDFC's complex relationship-heavy business.",0.5,ago(50),"email_one_way"),
            ("inbound","Re: GeniOS — want to see a full demo","Deepak replied. Impressed by HDFC use case. Wants demo for full team.",0.7,ago(40),"email_reply"),
            ("outbound","GeniOS Demo — HDFC (90 min)","Full demo with Deepak + 4 team members. He said 'let's do a 30-day pilot, I'll present this to the board June 10'.",0.78,ago(25),"meeting"),
            ("outbound","GeniOS Pilot Proposal — HDFC Bank (₹85L/yr)","Sent detailed pilot proposal. 30 days, 10 users, success metrics tied to his board presentation.",0.6,ago(18),"email_one_way"),
            ("outbound","Following up on pilot proposal","No reply from Deepak in 14 days. Board presentation is June 10 — 16 days away.",0.4,ago(14),"email_one_way"),
        ],
        "commitments": [
            ("Get pilot agreement signed before Deepak's board presentation on June 10 — ₹85L deal at stake","us","2026-06-05 00:00:00+00","OPEN"),
        ],
    },
    {
        "email": "sanya.gupta@swiggy.in",
        "name": "Sanya Gupta",
        "company": "Swiggy",
        "entity_type": "lead",
        "classification": "customer",
        "classification_confidence": 0.78,
        "last_sentiment": 0.68,
        "last_interaction_at": ago(5),
        "interaction_count": 1,
        "sentiment_history": sh([(5,0.75)]),
        "communication_style": json.dumps({"preferred_channel":"linkedin","avg_response_hours":8,"prefers_short":True,"formality":"casual"}),
        "metadata": json.dumps({"source":"webinar","lead_message":"Very interested. We manage 200+ brand partnerships at Swiggy. This could be huge for us.","introduced_by_name":"Neha Agarwal","deal_size_est":"18L INR/yr","warm_lead":True}),
        "interactions": [
            ("inbound","GeniOS Webinar — Contact Form Submission","Sanya filled form after webinar. Said: 'Very interested. Manage 200+ brand partnerships at Swiggy. This could be huge for us.' Zero human outbound sent in 5 days.",0.75,ago(5),"email_one_way"),
        ],
        "commitments": [
            ("URGENT: Reach out to Sanya Gupta (Swiggy) NOW — she expressed strong buying intent 5 days ago, warm leads go cold in 48-72 hours","us",ago(3),"OVERDUE"),
        ],
    },
    {
        "email": "vikram.nair@yc.com",
        "name": "Vikram Nair",
        "company": "Y Combinator (W21 Alum)",
        "entity_type": "contact",
        "classification": "contact",
        "classification_confidence": 0.85,
        "last_sentiment": 0.6,
        "last_interaction_at": ago(30),
        "interaction_count": 4,
        "sentiment_history": sh([(60,0.8),(45,0.75),(30,0.6)]),
        "communication_style": json.dumps({"preferred_channel":"twitter","avg_response_hours":4,"prefers_short":True,"formality":"very_casual"}),
        "metadata": json.dumps({"yc_batch":"W21","location":"San Francisco","network_value":"500+ YC founders + investors","intros_made":2,"intros_followed_up_by_rohit":0,"potential_intros":"10+"}),
        "interactions": [
            ("outbound","Hey Vikram — building GeniOS, YC W26","Twitter DM to Vikram. Mutual YC connection.",0.6,ago(60),"other"),
            ("inbound","Re: GeniOS — sounds dope, I'll make some intros","Vikram replied. Very enthusiastic. Said he'd intro 2-3 founders in his network.",0.8,ago(55),"other"),
            ("inbound","Intro: Harsh Malhotra + Rohan Singh (both need this)","Vikram made 2 intros via email. Neither followed up by Rohit in 30 days.",0.7,ago(30),"email_one_way"),
        ],
        "commitments": [
            ("Follow up on both of Vikram's intros: Harsh Malhotra + Rohan Singh — 30 days overdue, Vikram will stop making intros if ignored","us",ago(20),"OVERDUE"),
            ("Update Vikram on intro outcomes — he needs to know they're working to make more intros","us",ago(10),"OPEN"),
        ],
    },
    {
        "email": "ashish.tiwari@zenith-tech.co",
        "name": "Ashish Tiwari",
        "company": "Zenith Tech Solutions",
        "entity_type": "customer",
        "classification": "customer",
        "classification_confidence": 0.98,
        "last_sentiment": 0.58,
        "last_interaction_at": ago(42),
        "interaction_count": 18,
        "sentiment_history": sh([(240,0.8),(180,0.82),(120,0.78),(60,0.72),(42,0.58)]),
        "communication_style": json.dumps({"preferred_channel":"email","avg_response_hours":12,"prefers_short":False,"formality":"semi-formal"}),
        "metadata": json.dumps({"plan":"startup","mrr_inr":41667,"annual_contract_inr":500000,"renewal_date":"2026-06-15","months_active":8,"nps_last":8,"last_nps_date":"2025-11-01","quote":"saves me 3 hours/week on follow-ups","churn_risk":"medium","days_to_renewal":21}),
        "interactions": [
            ("outbound","Welcome to GeniOS, Ashish!","Onboarding email. Ashish very enthusiastic from day 1.",0.8,ago(240),"email_one_way"),
            ("inbound","Re: Q3 check-in — loving it!","Ashish: 'NPS 8/10, saves me 3 hours/week on follow-ups. Great product.'",0.82,ago(120),"email_reply"),
            ("outbound","GeniOS Product Update — March 2026","Generic newsletter. No personal check-in in 42 days. Renewal in 21 days. No one has talked to Ashish.",0.6,ago(42),"email_one_way"),
        ],
        "commitments": [
            ("Personal check-in call with Ashish before June 15 renewal — ₹5L annual, no human contact in 42 days","us","2026-06-01 00:00:00+00","OPEN"),
            ("Send Ashish NPS survey + renewal proposal with upgraded plan options","us",ago(14),"OVERDUE"),
        ],
    },
    {
        "email": "meera.desai@yourstory.com",
        "name": "Meera Desai",
        "company": "YourStory Media",
        "entity_type": "contact",
        "classification": "contact",
        "classification_confidence": 0.80,
        "last_sentiment": 0.62,
        "last_interaction_at": ago(58),
        "interaction_count": 4,
        "sentiment_history": sh([(90,0.7),(65,0.72),(58,0.62)]),
        "communication_style": json.dumps({"preferred_channel":"linkedin","avg_response_hours":24,"prefers_short":False,"formality":"semi-formal"}),
        "metadata": json.dumps({"publication":"YourStory","article_views":12000,"article_published_date":"2026-03-27","upcoming_article":"Top 10 AI Tools for Founders 2026","coverage_potential":"high"}),
        "interactions": [
            ("inbound","YourStory Feature Request — GeniOS","Meera reached out for a feature on AI tools for founders.",0.7,ago(90),"email_one_way"),
            ("outbound","Re: Feature — happy to chat, here's my calendar","Agreed to interview. 45-min call done.",0.72,ago(85),"email_reply"),
            ("outbound","Thanks Meera — article looks great!","Article published March 27, 12K views. Rohit sent a generic thanks. No follow-up since to build the relationship.",0.62,ago(58),"email_one_way"),
        ],
        "commitments": [
            ("Build proper relationship with Meera — her next piece is 'Top 10 AI Tools 2026', GeniOS should be in it","us",ago(40),"OVERDUE"),
        ],
    },
]


def run():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    print(f"Inserting demo data for org: {ORG_ID}\n")

    for c in CONTACTS:
        interactions = c.pop("interactions")
        commitments = c.pop("commitments")

        # Upsert contact
        cur.execute("SELECT id FROM contacts WHERE org_id = %s AND email = %s", (ORG_ID, c["email"]))
        row = cur.fetchone()

        if row:
            contact_id = str(row[0])
            cur.execute("""
                UPDATE contacts SET name=%s, company=%s, entity_type=%s, classification=%s,
                    classification_confidence=%s, last_sentiment=%s, last_interaction_at=%s,
                    interaction_count=%s, sentiment_history=%s::jsonb,
                    communication_style=%s::jsonb, metadata=%s::jsonb
                WHERE id=%s
            """, (c["name"], c["company"], c["entity_type"], c["classification"],
                  c["classification_confidence"], c["last_sentiment"], c["last_interaction_at"],
                  c["interaction_count"], c["sentiment_history"],
                  c["communication_style"], c["metadata"], contact_id))
        else:
            cur.execute("""
                INSERT INTO contacts (org_id, email, name, company, entity_type, classification,
                    classification_confidence, last_sentiment, last_interaction_at,
                    interaction_count, sentiment_history, communication_style, metadata)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)
                RETURNING id
            """, (ORG_ID, c["email"], c["name"], c["company"], c["entity_type"], c["classification"],
                  c["classification_confidence"], c["last_sentiment"], c["last_interaction_at"],
                  c["interaction_count"], c["sentiment_history"],
                  c["communication_style"], c["metadata"]))
            contact_id = str(cur.fetchone()[0])

        print(f"  ✓ {c['name']} ({contact_id[:8]}...)")

        for direction, subject, summary, sentiment, interaction_at, itype in interactions:
            cur.execute("""
                INSERT INTO interactions (org_id, contact_id, direction, subject, summary, sentiment, interaction_at, interaction_type)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING
            """, (ORG_ID, contact_id, direction, subject, summary, sentiment, interaction_at, itype))
        print(f"    → {len(interactions)} interactions")

        for commit_text, owner, due_date, status in commitments:
            try:
                cur.execute("""
                    INSERT INTO commitments (org_id, contact_id, commit_text, owner, due_date, status)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (ORG_ID, contact_id, commit_text, owner, due_date, status))
            except Exception:
                conn.rollback()
                continue
        print(f"    → {len(commitments)} commitments\n")

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Done! Now run: curl -X POST https://squid-app-2zuqf.ondigitalocean.app/v1/scan ...")


if __name__ == "__main__":
    run()
