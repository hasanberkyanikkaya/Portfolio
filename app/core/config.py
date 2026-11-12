from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Portfolio Analysis Platform"
    database_url: str = "postgresql+asyncpg://portfolio:portfolio@localhost:5434/portfolio"

    finnhub_api_key: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    scheduler_enabled: bool = True  # set False to run the API without the report scheduler

    # "anthropic" = direct Claude API (needs ANTHROPIC_API_KEY).
    # "bedrock"   = Claude on Amazon Bedrock (uses AWS credentials/credits; no Anthropic key).
    claude_provider: str = "anthropic"
    aws_region: str = "us-east-1"  # only used when claude_provider=bedrock


@lru_cache
def get_settings() -> Settings:
    return Settings()
