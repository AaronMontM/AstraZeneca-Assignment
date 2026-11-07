from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):

    APP_NAME: str = "Finance Spend Intelligence Assistant"

    # Ollama
    OLLAMA_HOST: str = "http://localhost:11434"
    #OLLAMA_MODEL: str = "qwen3.6:27b"
    OLLAMA_MODEL: str = "qwen3.5:9b"
    TEMPERATURE: float = 0.0

    # Data
    DATA_PATH: Path = PROJECT_ROOT / "data/processed/enriched_invoices_2025.csv"
    POLICY_PATH: Path = PROJECT_ROOT / "data/procurement_policy.md"

    # Database
    DATABASE_URL: str = (
        "postgresql://finance_user:finance_password@localhost:5432/finance_assistant"
    )

    # Conversation
    MAX_HISTORY_MESSAGES: int = 10

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("DATA_PATH", "POLICY_PATH", mode="before")
    @classmethod
    def resolve_project_paths(cls, value):
        path = Path(value)

        if not path.is_absolute():
            path = PROJECT_ROOT / path

        return path


settings = Settings()