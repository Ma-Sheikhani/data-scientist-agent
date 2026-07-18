"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",  # ignore unused env vars, optional but safe
    )

    PROJECT_NAME: str = "Data Scientist Agent"
    API_V1_PREFIX: str = "/v1"

    # Database
    DATABASE_URL: str

    # Redis / Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # Auth
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # LLM configuration
    LLM_BACKEND: str = "local"  # "local" or "openrouter"

    # Local Ollama
    LLM_BASE_URL_LOCAL: str = "http://ollama:11434/v1"
    LLM_MODEL_LOCAL: str = "phi3:mini"
    LLM_API_KEY_LOCAL: str = "dummy"

    # OpenRouter (remote)
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    OPENROUTER_API_KEY: str = ""


settings = Settings()  # type: ignore[call-arg]
