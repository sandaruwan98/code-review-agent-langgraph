from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # LLM
    anthropic_api_key: str = Field(..., env="ANTHROPIC_API_KEY")
    model_name: str = Field("claude-sonnet-4-6", env="MODEL_NAME")

    # GitHub
    github_token: str = Field(..., env="GITHUB_TOKEN")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
