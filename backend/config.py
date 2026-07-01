from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    ANTHROPIC_API_KEY: str
    GMAIL_CREDENTIALS_PATH: str = "./credentials.json"
    DATABASE_URL: str = "sqlite+aiosqlite:///./mailbox.db"
    CLAUDE_MODEL: str = "claude-opus-4-5"


settings = Settings()
