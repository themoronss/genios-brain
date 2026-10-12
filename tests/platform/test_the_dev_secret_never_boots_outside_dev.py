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


def test_an_unset_environment_reads_dev_as_it_always_has():
    """The deploy precondition, pinned: the refusal only reaches an environment that names itself."""
    assert _settings().env == "dev"
    assert C.insecure_boot(_settings()) is None


def test_the_shipped_secret_is_named_once():
    assert _settings().jwt_secret == C.DEFAULT_JWT_SECRET
