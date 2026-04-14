from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TradePilot API"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/tradepilot"
    market_data_provider: str = "yahoo"
    market_data_base_url: str = "https://query1.finance.yahoo.com"
    market_data_timeout_seconds: float = 8.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
