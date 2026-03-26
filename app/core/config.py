from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str
    supabase_service_role_key: str
    telegram_webhook_secret: str
    groq_api_key: str
    environment: str = "development"
    sqlalchemy_database_url: str
    cors_allow_origins: list[str] = ["*"]

    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    # Session settings
    EXAM_GRACE_PERIOD_SECONDS: int = 600  # 10 minutes
    DEFAULT_EXAM_TTL_SECONDS: int = 7200  # 2 hours
    DEFAULT_PRACTICE_TTL_SECONDS: int = 86400  # 24 hours
    DEFAULT_QUIZ_TTL_SECONDS: int = 1800  # 30 minutes
    DEFAULT_QUIZ_QUESTION_COUNT: int = 5

    # Qtoken settings
    QTOKEN_TTL_SECONDS: int = 90 # 60-120 seconds recommended

settings = Settings()
