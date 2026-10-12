from pydantic import field_validator, Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict, PydanticBaseSettingsSource
from typing import Type, Tuple


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        # OS env vars take priority (Docker/HuggingFace platform vars), then .env file as fallback
        return (init_settings, env_settings, dotenv_settings, file_secret_settings)

    supabase_url: str
    supabase_service_role_key: str
    telegram_webhook_secret: str = Field(
        ...,
        validation_alias=AliasChoices(
            "TELEGRAM_WEBHOOK_SECRET",
            "BACKEND_SECRET",
            "telegram_webhook_secret",
            "backend_secret",
        ),
    )
    groq_api_key: str
    groq_model: str
    environment: str = "development"
    sqlalchemy_database_url: str
    cors_allow_origins: list[str] = ["*"]

    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    EXAM_GRACE_PERIOD_SECONDS: int = 600
    DEFAULT_EXAM_TTL_SECONDS: int = 7200
    DEFAULT_PRACTICE_TTL_SECONDS: int = 86400
    DEFAULT_QUIZ_TTL_SECONDS: int = 1800
    DEFAULT_QUIZ_QUESTION_COUNT: int = 5
    DEFAULT_COMPLETED_SESSION_TTL_SECONDS: int = 3600

    QTOKEN_TTL_SECONDS: int = 300

    admin_jwt_secret: str
    admin_jwt_algorithm: str = "HS256"
    admin_jwt_ttl_minutes: int = 60

    
    superadmin_email: str
    superadmin_password: str

    telegram_bot_token: str | None = None  # Used for sending admin notifications to users

    @field_validator("telegram_webhook_secret", "admin_jwt_secret")
    @classmethod
    def _require_strong_secret(cls, v: str) -> str:
        if not v or len(v.strip()) < 16:
            raise ValueError('secret is too short (minimum 16 characters required)')
        return v

settings = Settings()