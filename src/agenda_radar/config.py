from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    data_dir: Path = Path("data")
    secrets_dir: Path = Path("secrets")
    app_timezone: str = "America/Argentina/Buenos_Aires"
    app_base_url: str = "http://127.0.0.1:8765"
    cookie_secure: bool = True
    session_hours: int = 12
    default_language: str = "en"
    collaboration_enabled: bool = False
    fetch_concurrency: int = 3
    openai_daily_budget_usd: float = 1
    openai_monthly_budget_usd: float = 20
    backup_dir: Path = Path("data/backups")

    demo_enabled: bool = False
    demo_showcase: bool = False
    demo_mode: bool = False
    demo_epoch: float | None = None
    demo_dir: Path = Path("data/demo")
    demo_max_sessions: int = 10
    demo_session_seconds: int = 7200
    demo_corpus_dir: Path = Path("demo-corpus")

    @property
    def database_path(self) -> Path:
        return self.data_dir / "agenda.db"
