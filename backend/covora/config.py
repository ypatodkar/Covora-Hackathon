import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]

RoutingMode = Literal["fixed", "switchyard", "baseline_nano", "baseline_super"]


class ModelPriceConfig(BaseModel):
    input_per_m: float
    output_per_m: float


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://covora:covora@localhost:5434/covora"

    nvidia_api_key: SecretStr | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_structured_mode: Literal["guided_json", "response_format", "none"] = "response_format"
    nemotron_nano_model: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    nemotron_super_model: str = "nvidia/nemotron-3-super-120b-a12b"
    nemotron_embed_model: str = "nvidia/nemotron-3-embed-1b"
    nemotron_embed_dim: int = 2048

    routing_mode: RoutingMode = "fixed"
    nano_timeout_s: float = 60
    super_timeout_s: float = 180
    nano_concurrency: int = 8
    super_concurrency: int = 4
    retry_base_delay_s: float = 1.0
    # Tasks that run with model reasoning on (default: none; measured 4x slower with no quality gain).
    reasoning_tasks: list[str] = []
    model_prices: dict[str, ModelPriceConfig] = {}
    log_llm_payloads: bool = True

    ydc_api_key: SecretStr | None = None
    youcom_budget_usd: float = 80
    youcom_base_url: str = "https://ydc-index.io/v1"
    youcom_search_price_usd: float = 0.005
    youcom_contents_price_usd: float = 0.001
    youcom_cache_ttl_days: int = 14
    youcom_timeout_s: float = 30.0

    # Research: "youcom" for real web research, "mock" for the fixture web (development; labeled synthetic).
    research_provider: Literal["youcom", "mock"] = "youcom"
    mock_web_path: str | None = None
    research_blocklist_domains: list[str] = []
    min_fit_score: int = 60
    max_candidates_per_wave: int = 40
    max_waves: int = 15
    contact_yield_buffer: float = 1.25

    worker_poll_interval_s: float = 1.0
    job_stale_after_s: float = 300

    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None
    token_encryption_key: SecretStr | None = None

    cors_origin: str = "http://localhost:5180"

    def memory_enabled(self, agent: str) -> bool:
        """Memory ablation switch (spec §7.4): MEMORY_ENABLED_<AGENT>=false turns retrieval off."""
        value = os.environ.get(f"MEMORY_ENABLED_{agent.upper()}", "true")
        return value.strip().lower() not in {"false", "0"}

    def secret_values(self) -> list[str]:
        """Values of every secret field, for log redaction."""
        values = []
        for name in type(self).model_fields:
            field_value = getattr(self, name)
            if isinstance(field_value, SecretStr) and field_value.get_secret_value():
                values.append(field_value.get_secret_value())
        return values


@lru_cache
def get_settings() -> Settings:
    return Settings()
