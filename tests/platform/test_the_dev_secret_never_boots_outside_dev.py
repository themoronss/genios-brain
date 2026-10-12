"""STEP-18 B7 · the shipped JWT secret never signs a session outside dev.

    pytest tests/platform/test_the_dev_secret_never_boots_outside_dev.py -q

`yc2_w27_s18` M49.C3.L-contract.V0.U07 (`platform/config.insecure_boot`) and
M49.C3.L-integration.V1.U08 (`main.lifespan` asks it first).

⛔ WHAT WAS WRONG. `platform/config.Settings.jwt_secret` defaults to a string that is in the
repository (`genios-dev-secret-change-in-prod`), and nothing checked it: an image deployed without
`GENIOS_JWT_SECRET` signs and verifies every session with a key anyone can read, so anyone can sign
one. The rule: an environment named outside dev with the shipped (or an empty) secret may not serve.
An UNSET `GENIOS_ENV` reads `dev`, as it always has — so the deploy that turns this on is the one
that names its environment (STEP-18 §8.3 s18-F11, Harsh's precondition).

⛔ RE-PINNED by `06` D62 (Rohit, 12 Oct; `yc2_w27_s18` M49.C3.L-contract.V1.U10, crosscheck S18-X03):
the unset case let a production that never named its environment boot on the public secret, while
`platform/egress` already read an unset `GENIOS_ENV` as production. Now an UNSET `GENIOS_ENV` is not
dev — here as in egress, from one `DEV_ENVS` — and `change-me-in-prod`, the placeholder
`.env.example` hands every checkout, is refused like the default.
"""
from __future__ import annotations

import pytest

from genios_engine.platform import config as C


@pytest.fixture(autouse=True)
def _no_ambient_settings(monkeypatch):
    """What the shell exports must not decide these: each test names what it means."""
    for name in ("GENIOS_ENV", "GENIOS_JWT_SECRET"):
        monkeypatch.delenv(name, raising=False)


def _settings(**values) -> C.Settings:
    return C.Settings(_env_file=None, **values)


@pytest.mark.parametrize("env", ["production", "prod", "staging", "Production "])
def test_a_named_environment_with_the_shipped_secret_may_not_serve(env):
    reason = C.insecure_boot(_settings(env=env))
    assert reason and "GENIOS_JWT_SECRET" in reason and env.strip().lower() in reason


@pytest.mark.parametrize("env", ["production", "staging"])
def test_an_empty_secret_is_no_better(env):
    assert C.insecure_boot(_settings(env=env, jwt_secret="   "))


@pytest.mark.parametrize("env", ["dev", "development", "test", "local", "DEV"])
def test_dev_may_use_the_shipped_secret(env):
    assert C.insecure_boot(_settings(env=env)) is None


def test_a_secret_of_its_own_may_serve_anywhere():
    assert C.insecure_boot(_settings(env="production", jwt_secret="a-secret-of-our-own-9f2c")) is None


def test_an_unset_environment_is_not_dev():
    """`06` D62: `Settings.env` still defaults to "dev" for every other reader, and the boot does not
    trust that default — the field the environment never provided is not a development one."""
    unset = _settings()
    assert unset.env == "dev" and "env" not in unset.model_fields_set
    reason = C.insecure_boot(unset)
    assert reason and "unset" in reason and "GENIOS_JWT_SECRET" in reason, reason


def test_an_unset_environment_with_a_secret_of_its_own_boots():
    """The negative control: an unset environment is refused only for a public secret."""
    assert C.insecure_boot(_settings(jwt_secret="a-secret-of-our-own-9f2c")) is None


@pytest.mark.parametrize("value, refused", [("dev", False), ("local", False), ("", True),
                                             ("production", True)])
def test_the_environment_counts_as_set_from_the_process_env_too(monkeypatch, value, refused):
    """How a deployment sets it: `GENIOS_ENV` in the process environment, never a keyword."""
    monkeypatch.setenv("GENIOS_ENV", value)
    assert bool(C.insecure_boot(C.Settings(_env_file=None))) is refused, value


@pytest.mark.parametrize("secret", ["change-me-in-prod", " change-me-in-prod "])
def test_the_example_placeholder_is_refused_like_the_default(secret):
    """`.env.example`'s `GENIOS_JWT_SECRET=change-me-in-prod` is in the repository too."""
    reason = C.insecure_boot(_settings(env="production", jwt_secret=secret))
    assert reason and ".env.example" in reason, reason
    assert C.insecure_boot(_settings(env="dev", jwt_secret=secret)) is None


def test_the_example_files_placeholder_is_the_one_refused():
    """Read off `.env.example` itself, so a new placeholder there cannot slip past the list."""
    from pathlib import Path

    example = Path(__file__).resolve().parents[2] / ".env.example"
    values = [line.split("=", 1)[1].split("#", 1)[0].strip()
              for line in example.read_text(encoding="utf-8").splitlines()
              if line.startswith("GENIOS_JWT_SECRET=")]
    assert values and set(values) <= C.PUBLIC_JWT_SECRETS, values


def test_one_list_of_dev_environments_serves_the_boot_and_egress(monkeypatch):
    """`06` D62: egress and the boot read one `DEV_ENVS`, and both read an unset env as not dev."""
    from genios_engine.platform import egress

    assert egress.DEV_ENVS is C.DEV_ENVS
    for env in sorted(C.DEV_ENVS) + ["production", "staging", ""]:
        assert egress.is_dev(env) is (C.insecure_boot(_settings(env=env)) is None), env
    unset = _settings()
    monkeypatch.setattr(egress, "get_settings", lambda: unset)
    assert egress.is_dev() is False and C.insecure_boot(unset) is not None


def test_the_shipped_secret_is_named_once():
    assert _settings().jwt_secret == C.DEFAULT_JWT_SECRET


# ── the boot asks it first (M49.C3.L-integration.V1.U08) ──────────────────────────────────────

def _boot(monkeypatch, settings: C.Settings) -> None:
    """Run `main.lifespan` to its yield and back, with `settings` as the process's settings."""
    import asyncio

    from genios_engine import main

    monkeypatch.setattr(main, "get_settings", lambda: settings)

    async def _run():
        async with main.lifespan(main.app):
            pass

    asyncio.run(_run())


def test_a_production_boot_with_the_shipped_secret_refuses(monkeypatch):
    with pytest.raises(RuntimeError, match="refusing to boot.*GENIOS_JWT_SECRET"):
        _boot(monkeypatch, _settings(env="production", database_url=""))


def test_the_refusal_comes_before_anything_starts(monkeypatch):
    """Asked first: no migration, no scheduler, no worker is started by a refused boot."""
    from genios_engine.platform import migrate, scheduler, screen_promoter, sync_worker, warm_lane

    called = []
    monkeypatch.setattr(migrate, "apply_migrations", lambda *a, **k: called.append("migrate"))
    for module, name in ((scheduler, "start_scheduler"), (sync_worker, "start_sync_worker"),
                         (warm_lane, "start_warm_lane"),
                         (screen_promoter, "start_screen_promoter")):
        monkeypatch.setattr(module, name, lambda *a, _n=name, **k: called.append(_n))
    with pytest.raises(RuntimeError):
        _boot(monkeypatch, _settings(env="production", database_url="postgresql://nowhere/x"))
    assert called == []


def test_a_dev_boot_and_a_production_boot_with_its_own_secret_proceed(monkeypatch):
    # No database, so nothing is migrated or started: the boot runs to its yield and back.
    _boot(monkeypatch, _settings(env="dev", database_url=""))
    _boot(monkeypatch, _settings(env="production", jwt_secret="a-secret-of-our-own-9f2c",
                                 database_url=""))
