"""Application settings, loaded from the environment.

Uses pydantic-settings: a Settings class whose fields are populated from
environment variables (case-insensitive, prefixed with ASX_) and validated
exactly like any other Pydantic model. This gives one typed, testable source
of truth for configuration instead of scattered os.environ lookups.

Example:
    ASX_GCP_PROJECT=my-project ASX_GCS_BUCKET=my-bucket python -m ...

Secrets (e.g. ANTHROPIC_API_KEY) are read by their client libraries directly
and never stored in this object, so they can't leak via logging/repr.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASX_", env_file=".env", extra="ignore")

    # GCP resources. No defaults: a missing value should fail at startup,
    # loudly, rather than half-run against the wrong project.
    gcp_project: str
    gcs_raw_bucket: str
    bq_dataset: str = "asx_engine"

    # Ingestion etiquette (see CLAUDE.md "Data sources"). Defaults are the
    # polite values; they can be tightened via env but the floor is enforced
    # by the rate limiter itself, not just config.
    request_interval_seconds: float = 3.0
    user_agent: str = (
        "asx-announcement-research/0.1 (personal research project; github.com/Taylor-Hobbs/asx)"
    )


def load_settings() -> Settings:
    """Construct Settings from the environment.

    A factory function (rather than a module-level singleton) keeps imports
    side-effect free and lets tests build Settings with explicit values.
    """
    return Settings()  # type: ignore[call-arg]  # fields come from env at runtime
