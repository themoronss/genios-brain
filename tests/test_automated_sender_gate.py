"""Machine senders (noreply@/notify./mailer-daemon/role-inboxes) must NOT become person nodes —
they pollute the relationship graph (cloudflare/mongodb/algolia). Deterministic, recall-safe."""
from genios_engine.context.pipeline import _is_automated_sender


def test_machine_senders_detected():
    for e in ["noreply@notify.cloudflare.com", "no-reply@algolia.com", "donotreply@upwork.com",
              "cloud-manager-support@mongodb.com", "community@growthx.club", "naukrialerts@naukri.com",
              "jobalerts-noreply@linkedin.com", "newsletters@yourstory.com", "no-reply@ycombinator.com",
              "usr-3bk@user.luma-mail.com", "mailer-daemon@x.com", "notifications@github.com"]:
        assert _is_automated_sender(e), e


def test_real_people_not_flagged():
    for e in ["deebaj.mir@greychaindesign.com", "ray@inkbox.ai", "mrrohitswerashi@gmail.com",
              "kiran.adsule@acme.com", "divya.tarak@company.com", "john.support.smith@acme.com",
              "rohit@startup.io"]:
        assert not _is_automated_sender(e), e


def test_empty_is_not_automated():
    assert not _is_automated_sender("") and not _is_automated_sender(None)
