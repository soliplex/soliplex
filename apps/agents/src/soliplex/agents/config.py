import enum

from pydantic_settings import BaseSettings


class SCM(str, enum.Enum):
    GITHUB = "github"
    GITEA = "gitea"


class Settings(BaseSettings):
    gitea_url: str | None = None
    gitea_token: str | None = None
    gitea_owner: str | None = "admin"
    gh_token: str | None = None
    gh_owner: str | None = None
    extensions: list[str] = ["md", "pdf", "doc", "docx"]
    log_level: str = "INFO"
    endpoint_url: str = "http://localhost:8000/api/v1"


settings = Settings()
