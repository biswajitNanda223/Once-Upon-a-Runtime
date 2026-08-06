from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    auth_mode: str = "databricks"
    database_url: str
    internal_identity_hmac_secret: str = Field(min_length=32)
    signature_max_age_seconds: int = Field(default=60, ge=10, le=300)

    def validate_runtime(self) -> None:
        if self.auth_mode not in {"databricks", "local"}:
            raise ValueError("AUTH_MODE must be databricks or local")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()  # type: ignore[call-arg]
    settings.validate_runtime()
    return settings
