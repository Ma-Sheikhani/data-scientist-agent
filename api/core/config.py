from pydantic_settings import BaseSettings


class Settings(BaseSettings):
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

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
