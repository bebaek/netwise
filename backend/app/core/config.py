from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Netwise"
    database_url: str = "sqlite:///./netwise.db"
    public_signup: bool = False
    single_household_mode: bool = True

    model_config = SettingsConfigDict(env_prefix="NETWISE_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
