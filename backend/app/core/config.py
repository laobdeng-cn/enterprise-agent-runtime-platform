from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "enterprise-agent-runtime-platform"
    app_version: str = "0.2.0"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+psycopg://agent:agent@localhost:5432/agent_runtime"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = "development-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    bootstrap_admin_username: str = ""
    bootstrap_admin_password: str = ""
    bootstrap_admin_email: str = ""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
