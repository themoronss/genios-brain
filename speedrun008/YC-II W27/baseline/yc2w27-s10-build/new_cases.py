"""STEP-10 · C6.U01 — writes the three new founder cases (D40) into tests/replays/specs/founder/.

    cd <worktree> && python3 new_cases.py
"""
import json
from pathlib import Path

FOUNDER = {"name": "Arjun Rao", "email": "arjun@nimbuslabs.test", "company": "Nimbus Labs",
           "timezone": "Asia/Kolkata"}
ARJUN = "Arjun Rao <arjun@nimbuslabs.test>"
OUT = Path("tests/replays/specs/founder")


def intent(category, asks, tone="neutral"):
    return {"category": category, "tone": tone, "formality": "professional",
            "addressed_personally": True, "human_authored": True, "asks_for_reply": asks,
            "engagement": "high"}


# ---------------------------------------------------------------------------------------------
# F45 — your own reply time, at several speeds (n = 6)
# ---------------------------------------------------------------------------------------------
MEERA = "Meera Shah <meera@bluepeak.test>"
QUESTIONS = [  # (day, hour, gap_days, subject, question sentence, short question)
    ("2026-08-05", 9, 0.5, "Bluepeak x Nimbus - retention",
     "Could you share how the first three pilot teams retained over eight weeks?",
     "Share the eight-week retention of the first three pilot teams"),
    ("2026-08-12", 9, 1, "Bluepeak x Nimbus - pricing",
     "How do you plan to price the team tier once the pilots convert?",
     "Explain how the team tier will be priced after the pilots convert"),
    ("2026-08-19", 9, 1, "Bluepeak x Nimbus - hiring",
     "Who is the first engineer you plan to hire after the round?",
     "Say who the first engineering hire after the round will be"),
    ("2026-08-26", 9, 2, "Bluepeak x Nimbus - pipeline",
     "How many teams are in your pipeline for the next quarter?",
     "Give the number of teams in next quarter's pipeline"),
    ("2026-09-02", 9, 3, "Bluepeak x Nimbus - competition",
     "Which tool do your pilot teams use today instead of Nimbus Labs?",
     "Name the tool the pilot teams use today instead of Nimbus Labs"),
    ("2026-09-09", 9, 6, "Bluepeak x Nimbus - references",
     "Could two of your pilot customers take a short reference call with us?",
     "Arrange two pilot-customer reference calls"),
]
ANSWERS = [
    "Hi Meera,\n\nAll three pilot teams were still active at week eight; usage grew in two of them.\n\nArjun",
    "Hi Meera,\n\nThe team tier will be priced per seat, with a floor of five seats.\n\nArjun",
    "Hi Meera,\n\nA backend engineer who has built sync pipelines before.\n\nArjun",
    "Hi Meera,\n\nNine teams are in conversation for next quarter.\n\nArjun",
    "Hi Meera,\n\nMost of them use shared spreadsheets and a chat channel today.\n\nArjun",
    "Hi Meera,\n\nYes - two pilot leads have agreed; I will send their details separately.\n\nArjun",
]


def f45():
    from datetime import datetime, timedelta, timezone
    objects = []
    for i, ((day, hour, gap, subject, question, short), answer) in enumerate(zip(QUESTIONS, ANSWERS),
                                                                              start=1):
        asked = datetime.fromisoformat(day).replace(hour=hour, tzinfo=timezone.utc)
        answered = asked + timedelta(days=gap)
        sweep = 0 if answered < datetime(2026, 8, 31, 18, tzinfo=timezone.utc) else 1
        body = f"Hi Arjun,\n\n{question}\n\nMeera Shah\nBluepeak Ventures"
        objects.append({
            "id": f"q{i}", "source": "gmail", "sweep": 0 if asked < datetime(
                2026, 8, 31, 18, tzinfo=timezone.utc) else 1,
            "occurred_at": asked.isoformat().replace("+00:00", "Z"), "from": MEERA,
            "to": ["arjun@nimbuslabs.test"], "subject": subject, "body": body,
            "labels": ["INBOX"], "thread": f"t-bluepeak-{i}",
            "read": {"gate": "keep", "relevance": "business", "extraction": {
                "intent": "request", "stance": "positive", "topics": ["fundraising"],
                "entity_mentions": [
                    {"surface_form": "Meera Shah", "entity_type": "person", "quote": "Meera Shah"},
                    {"surface_form": "Bluepeak Ventures", "entity_type": "organization",
                     "quote": "Bluepeak Ventures"}],
                "questions": [{"text": short, "asked_by": "Meera Shah", "asked_of": "Arjun Rao",
                               "quote": question}],
                "exchange_intent": intent("working", True)}}})
        objects.append({
            "id": f"a{i}", "source": "gmail", "sweep": sweep,
            "occurred_at": answered.isoformat().replace("+00:00", "Z"), "from": ARJUN,
            "to": ["meera@bluepeak.test"], "subject": f"Re: {subject}", "body": answer,
            "labels": ["SENT"], "thread": f"t-bluepeak-{i}",
            "read": {"gate": "keep", "relevance": "business", "extraction": {
                "intent": "inform", "stance": "positive", "topics": ["fundraising"],
                "entity_mentions": [{"surface_form": "Meera", "entity_type": "person",
                                     "quote": "Meera"}],
                "exchange_intent": intent("working", False)}}})
    return {
        "case_id": "F45",
        "title": "The founder answers an investor's questions at several speeds - his own reply time, exact",
        "kind": "must_detect", "label_row": 45, "labelled_by": "claude", "replays": ["01"],
        "founder": FOUNDER, "sweeps": ["2026-08-31T18:00:00Z", "2026-09-30T12:00:00Z"],
        "objects": objects,
        "expected": {"cards": [{"about": ["Meera", "Bluepeak"], "min": 1, "max": 1}],
                     "brief": "how fast you answer Bluepeak: usually 1.5 days (n=6)"},
        "forbidden": {"names": [], "phrases": []},
        "witness": None,
        "not_expressible": {
            "cards": "brief only - how fast the founder answers is a line in the morning brief, "
                     "not a card (D12d)",
            "brief": "STEP-15 - there is no morning brief to appear in"},
        "model": {},
        "notes": "STEP-10 (06 D40): the golden set held one founder reply to an inbound mail (F14, "
                 "n = 1). Here Meera asks six questions, each in its own thread, and the founder "
                 "answers after 0.5, 1, 1, 2, 3 and 6 days: his reply time with her is their "
                 "median, 1.5 days, on 6 answers - a normal, at NORMAL_AT or more "
                 "(tests/replays/test_every_number_says_its_n.py).",
    }


# ---------------------------------------------------------------------------------------------
# F46 — two mailboxes: the answer arrives in the other one
# ---------------------------------------------------------------------------------------------
def f46():
    pitch = ("Hi Ravi,\n\nNimbus Labs is raising a seed round to bring calendar-aware planning to "
             "small teams. Could we find 20 minutes next week?\n\nArjun")
    reply = ("Hi Arjun,\n\nThanks for reaching out. Could you send the deck before we speak?\n\n"
             "Ravi Iyer\nSeedfund Partners")
    return {
        "case_id": "F46",
        "title": "An investor answers in the founder's other mailbox - both are read, and the file "
                 "says so",
        "kind": "must_detect", "label_row": 46, "labelled_by": "claude", "replays": ["01"],
        "founder": {**FOUNDER, "also": ["arjun.rao@gmail.test"]},
        "sweeps": ["2026-09-10T12:00:00Z"],
        "objects": [
            {"id": "pitch", "source": "gmail", "sweep": 0, "occurred_at": "2026-09-01T09:00:00Z",
             "from": "Arjun Rao <arjun.rao@gmail.test>", "to": ["ravi@seedfund.test"],
             "subject": "Nimbus Labs - raising our seed round", "body": pitch, "labels": ["SENT"],
             "thread": "t-seedfund-personal", "mailbox": "personal",
             "read": {"gate": "keep", "relevance": "business", "extraction": {
                 "intent": "request", "stance": "positive", "topics": ["fundraising"],
                 "entity_mentions": [{"surface_form": "Ravi", "entity_type": "person",
                                      "quote": "Ravi"}],
                 "exchange_intent": intent("working", True)}}},
            {"id": "reply", "source": "gmail", "sweep": 0, "occurred_at": "2026-09-03T09:00:00Z",
             "from": "Ravi Iyer <ravi@seedfund.test>", "to": ["arjun@nimbuslabs.test"],
             "subject": "Re: Nimbus Labs - raising our seed round", "body": reply,
             "labels": ["INBOX"], "thread": "t-seedfund-work",
             "read": {"gate": "keep", "relevance": "business", "extraction": {
                 "intent": "request", "stance": "positive", "topics": ["fundraising"],
                 "entity_mentions": [
                     {"surface_form": "Ravi Iyer", "entity_type": "person", "quote": "Ravi Iyer"},
                     {"surface_form": "Seedfund Partners", "entity_type": "organization",
                      "quote": "Seedfund Partners"}],
                 "questions": [{"text": "Send the deck before the call", "asked_by": "Ravi Iyer",
                                "asked_of": "Arjun Rao",
                                "quote": "Could you send the deck before we speak?"}],
                 "exchange_intent": intent("working", True)}}},
        ],
        "expected": {"gate": {"pitch": "emitted", "reply": "emitted"},
                     "memory": {"pitch": True, "reply": True},
                     "cards": [{"about": ["Ravi", "Seedfund"], "min": 1, "max": 1,
                                "mentions": ["deck"]}],
                     "workstream": "investor - asked for the deck; our move"},
        "forbidden": {"names": [], "phrases": ["no reply", "has not replied", "follow up with Ravi"]},
        "witness": None,
        "not_expressible": {
            "workstream": "STEP-11 - the file exists since STEP-09 (`GET /v1/workstreams`) and "
                          "names both mailboxes since STEP-10, but this line names its stage, and "
                          "no stage is derived to compare against"},
        "model": {},
        "notes": "STEP-10 (06 D40): the golden set had one mailbox. The founder pitched from his "
                 "personal Gmail; the investor answered his company address. Read from one "
                 "mailbox, the pitch is unanswered and 'no reply' would be said; read from both, "
                 "the answer is in the file and the move is ours. The file's receipt names both "
                 "connections (tests/replays/test_every_number_says_its_n.py). A reply that "
                 "arrives in another mailbox opens another conversation, so it is not paired with "
                 "the pitch as a reply time - declared, not hidden.",
    }


# ---------------------------------------------------------------------------------------------
# F47 — a bounce in the shape Gmail sends it
# ---------------------------------------------------------------------------------------------
def f47():
    pitch = ("Hi Ardent Ridge team,\n\nNimbus Labs is raising a seed round. Could we find 20 "
             "minutes?\n\nArjun")
    notice = ("Address not found\n\nYour message wasn't delivered to partners@ardentridge.test "
              "because the domain ardentridge.test couldn't be found. Check for typos or "
              "unnecessary spaces and try again.")
    return {
        "case_id": "F47",
        "title": "A pitch bounced, in the shape Gmail sends it - the report kept, the original not "
                 "a document",
        "kind": "must_detect", "label_row": 47, "labelled_by": "claude", "replays": ["01"],
        "founder": FOUNDER, "sweeps": ["2026-08-14T18:00:00Z"],
        "objects": [
            {"id": "sent", "source": "gmail", "sweep": 0, "occurred_at": "2026-08-14T06:00:00Z",
             "from": ARJUN, "to": ["partners@ardentridge.test"],
             "subject": "Nimbus Labs - raising our seed round", "body": pitch, "labels": ["SENT"],
             "thread": "t-ardent",
             "read": {"gate": "keep", "relevance": "business", "extraction": {
                 "intent": "request", "stance": "positive", "topics": ["fundraising"],
                 "entity_mentions": [{"surface_form": "Ardent Ridge", "entity_type": "organization",
                                      "quote": "Ardent Ridge"}],
                 "exchange_intent": intent("working", True)}}},
            {"id": "bounce", "source": "gmail", "sweep": 0, "occurred_at": "2026-08-14T06:00:20Z",
             "from": "Mail Delivery Subsystem <mailer-daemon@mailhost.test>",
             "to": ["arjun@nimbuslabs.test"],
             "subject": "Delivery Status Notification (Failure)", "body": notice,
             "labels": ["INBOX"], "thread": "t-ardent",
             "headers": {"Auto-Submitted": "auto-replied"},
             "attachments": [
                 {"filename": "", "mime": "message/delivery-status", "fetch": "ok",
                  "text": "Reporting-MTA: dns; mailhost.test\nFinal-Recipient: rfc822; "
                          "partners@ardentridge.test\nAction: failed\nStatus: 5.1.1"},
                 {"filename": "Nimbus Labs - raising our seed round.eml",
                  "mime": "message/rfc822", "fetch": "ok", "text": pitch}],
             "read": {"gate": "drop", "relevance": "business", "extraction": {
                 "intent": "inform", "stance": "negative", "topics": ["delivery failure"],
                 "exchange_intent": {"category": "automated", "tone": "neutral",
                                     "formality": "templated", "addressed_personally": False,
                                     "human_authored": False, "asks_for_reply": False,
                                     "engagement": "high"}}}},
        ],
        "expected": {"gate": {"bounce": "emitted"}, "memory": {"bounce": True},
                     "cards": [{"about": ["ardentridge.test", "Ardent Ridge"], "min": 1, "max": 1}],
                     "workstream": "your outbound - a fund never received your mail"},
        "forbidden": {"names": [], "phrases": []},
        "witness": None,
        "not_expressible": {
            "workstream": "STEP-11 - the file exists since STEP-09 (`GET /v1/workstreams`), and "
                          "carries the bounce since STEP-10, but this line names its state, and "
                          "no stage is derived to compare against"},
        "model": {},
        "notes": "STEP-10 (06 D38, D40): F16's bounce in production's shape - Gmail marks its "
                 "report Auto-Submitted: auto-replied and attaches the status and the original "
                 "pitch. Before STEP-10 N-01 archived it; then S2's junk filter did (production's "
                 "filter called all five real reports junk); and the attached original was a "
                 "document of its own. Now the report is kept and read, the bounce is on the "
                 "fund's file and ends its wait, and the original is not a document. No card yet "
                 "shows a bounce (STEP-14).",
    }


for case in (f45(), f46(), f47()):
    path = OUT / f"{case['case_id']}.json"
    path.write_text(json.dumps(case, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", path, len(case["objects"]), "objects")
