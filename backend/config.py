from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    ANTHROPIC_API_KEY: str
    GMAIL_CREDENTIALS_PATH: str = "./credentials.json"
    DATABASE_URL: str = "sqlite+aiosqlite:///./mailbox.db"
    CLAUDE_MODEL: str = "claude-opus-4-5"

    # Stage 4 — AbstractAPI keys (matching .env variable names exactly)
    Calendar: str = ""   # AbstractAPI Holidays API key
    Scrape: str = ""     # AbstractAPI Web Scraping API key

    # Default country code for holiday checks (ISO 3166-1 alpha-2)
    DEFAULT_COUNTRY_CODE: str = "AU"


settings = Settings()
