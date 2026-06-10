"""
Unit tests for the tunables module — no network needed.
Verifies that env-driven configuration works correctly.
"""
import os
import pytest


class TestBroadcastDetection:
    def test_default_patterns_loaded(self):
        from app.tunables import BROADCAST_LOCAL_PATTERNS
        assert len(BROADCAST_LOCAL_PATTERNS) > 10, "Should have 10+ default patterns"
        assert "noreply" in BROADCAST_LOCAL_PATTERNS

    def test_default_domains_loaded(self):
        from app.tunables import BROADCAST_DOMAINS
        assert len(BROADCAST_DOMAINS) > 5
        assert "sendgrid" in BROADCAST_DOMAINS

    def test_broadcast_regex_matches(self):
        from app.context.bundle_builder import _is_broadcast_address
        assert _is_broadcast_address("noreply@xyz.com") is True
        assert _is_broadcast_address("information@hdfcbank.net") is True
        assert _is_broadcast_address("alice@acme.com") is False
        assert _is_broadcast_address("tripathihk2014@gmail.com") is False

    def test_broadcast_regex_domains(self):
        from app.context.bundle_builder import _is_broadcast_address
        assert _is_broadcast_address("someone@naukri.com") is True
        assert _is_broadcast_address("events@calendar.luma-mail.com") is True
        assert _is_broadcast_address("ceo@real-company.com") is False

    def test_env_override_patterns(self, monkeypatch):
        monkeypatch.setenv("GENIOS_BROADCAST_LOCAL_PATTERNS", "custom1,custom2")
        # Need to reimport to pick up env change
        import importlib
        import app.tunables as tunables_mod
        importlib.reload(tunables_mod)
        assert tunables_mod.BROADCAST_LOCAL_PATTERNS == ["custom1", "custom2"]
        # Restore
        monkeypatch.delenv("GENIOS_BROADCAST_LOCAL_PATTERNS", raising=False)
        importlib.reload(tunables_mod)


class TestMeetingTopics:
    def test_default_topic_map_loaded(self):
        from app.tunables import MEETING_TITLE_TOPIC_MAP
        assert "interview" in MEETING_TITLE_TOPIC_MAP
        assert "standup" in MEETING_TITLE_TOPIC_MAP

    def test_title_extraction(self):
        from app.ingestion.calendar_bridge import _topics_from_title
        assert "interview" in _topics_from_title("Adobe Interview- Harsh Tripathi")
        assert "1:1" in _topics_from_title("Weekly 1:1 with Alice")
        assert "review" in _topics_from_title("Sprint review")

    def test_stopwords_filtered(self):
        from app.ingestion.calendar_bridge import _topics_from_title
        topics = _topics_from_title("Meeting call with team")
        assert "meeting" not in topics
        assert "call" not in topics
        assert "with" not in topics
