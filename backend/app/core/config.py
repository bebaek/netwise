from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Netwise"
    database_url: str = "sqlite:///./netwise.db"
    public_signup: bool = False
    single_household_mode: bool = True
    enable_admin_tools: bool = False
    auth_cookie_name: str = "netwise_session"
    auth_cookie_secure: bool = False
    auth_session_days: int = Field(default=30, ge=1, le=365)

    model_config = SettingsConfigDict(env_prefix="NETWISE_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
