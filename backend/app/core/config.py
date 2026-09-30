from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "enterprise-agent-runtime-platform"
    app_version: str = "0.9.0"

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

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_timeout_seconds: float = 60.0

    workspace_root: str = "/data/workspaces"
    workspace_max_file_bytes: int = 5 * 1024 * 1024
    workspace_quota_bytes: int = 50 * 1024 * 1024

    docker_host: str = "tcp://docker:2375"
    docker_api_version: str = "1.45"
    sandbox_image: str = "enterprise-agent-runtime-sandbox:0.7.0"
    sandbox_build_context: str = "/sandbox-image"
    sandbox_cpu_limit: float = 1.0
    sandbox_memory_limit_mb: int = 512
    sandbox_timeout_seconds: float = 60.0
    sandbox_pids_limit: int = 64
    sandbox_tmpfs_mb: int = 64
    sandbox_max_output_bytes: int = 256 * 1024
    sandbox_max_artifacts: int = 20
    sandbox_max_code_bytes: int = 100 * 1024

    memory_context_limit: int = 8
    memory_search_candidate_limit: int = 200
    memory_search_min_score: float = 0.12
    memory_default_ttl_days: int = 0

    context_token_budget: int = 32768
    context_reserved_output_tokens: int = 4096
    context_runtime_reserve_tokens: int = 4096
    context_additional_tokens: int = 8192
    context_memory_tokens: int = 6144
    context_skill_tokens: int = 4096
    context_skill_limit: int = 8
    context_item_max_tokens: int = 2048
    context_fallback_skill_count: int = 3

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
