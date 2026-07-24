from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    replica_id: str = "cas-replica-01"
    min_replicas: int = 3
    audit_timeout_seconds: float = 5.0
    redis_host: str = "localhost"
    redis_port: int = 6379
    calibration_threshold: int = 20
    default_phase: str = "CONTEXT_ESTABLISHMENT"


@lru_cache
def get_settings() -> Settings:
    return Settings()
