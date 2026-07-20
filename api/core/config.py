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
    LOCAL_BASE_URL: str = "http://ollama:11434/v1"
    LOCAL_MODEL: str = "phi3:mini"
    LOCAL_API_KEY: str = "dummy"

    # OpenRouter (remote)
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    OPENROUTER_API_KEY: str = ""

    # LangFuse
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    @property
    def active_llm_model(self) -> str:
        return (
            self.OPENROUTER_MODEL
            if self.LLM_BACKEND == "openrouter"
            else self.LOCAL_MODEL
        )

    @property
    def active_llm_api_key(self) -> str:
        return (
            self.OPENROUTER_API_KEY
            if self.LLM_BACKEND == "openrouter"
            else self.LOCAL_API_KEY
        )

    @property
    def active_llm_base_url(self) -> str:
        return (
            self.OPENROUTER_BASE_URL
            if self.LLM_BACKEND == "openrouter"
            else self.LOCAL_BASE_URL
        )


settings = Settings()  # type: ignore[call-arg]
