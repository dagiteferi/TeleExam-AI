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


settings = Settings()