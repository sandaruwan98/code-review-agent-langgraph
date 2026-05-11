from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # LLM
    model_base_url: str = Field(..., env="MODEL_BASE_URL")
    anthropic_api_key: str = Field(..., env="ANTHROPIC_API_KEY")
    model_name: str = Field("claude-sonnet-4-6", env="MODEL_NAME")

    # GitHub
    github_token: str = Field(..., env="GITHUB_TOKEN")

    # Review behaviour
    min_severity: str = Field("minor", env="MIN_SEVERITY")  # critical | major | minor
    post_to_github: bool = Field(False, env="POST_TO_GITHUB")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
