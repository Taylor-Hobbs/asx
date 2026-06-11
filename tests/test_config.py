"""Tests for asx_engine.config.

These use pytest's monkeypatch fixture to control environment variables:
monkeypatch sets/deletes env vars for the duration of one test and restores
them automatically afterwards, so tests can't contaminate each other.
"""

import pytest
from pydantic import ValidationError

from asx_engine.config import Settings


@pytest.fixture
def required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASX_GCP_PROJECT", "test-project")
    monkeypatch.setenv("ASX_GCS_RAW_BUCKET", "test-bucket")


def test_settings_read_from_environment(required_env: None) -> None:
    settings = Settings()
    assert settings.gcp_project == "test-project"
    assert settings.gcs_raw_bucket == "test-bucket"


def test_defaults_are_polite(required_env: None) -> None:
    settings = Settings()
    assert settings.bq_dataset == "asx_engine"
    # Ingestion etiquette: ~1 request per few seconds, identifiable UA.
    assert settings.request_interval_seconds >= 3.0
    assert "github.com/Taylor-Hobbs/asx" in settings.user_agent


def test_missing_required_settings_fail_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASX_GCP_PROJECT", raising=False)
    monkeypatch.delenv("ASX_GCS_RAW_BUCKET", raising=False)
    # _env_file=None disables .env loading so this test can't accidentally
    # pass/fail based on a developer's local .env file.
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_env_overrides_default(required_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASX_BQ_DATASET", "asx_engine_dev")
    assert Settings().bq_dataset == "asx_engine_dev"
