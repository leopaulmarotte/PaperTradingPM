"""
Application configuration loaded from environment variables.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""
    
    # MongoDB
    mongo_uri: str = "mongodb://mongodb:27017"
    
    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    
    # JWT Configuration
    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION_USE_STRONG_SECRET"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    
    # Rate Limiting (TODO: will be used with Redis)
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 60
    user_lockout_threshold: int = 10
    user_lockout_duration_minutes: int = 30
    global_rate_limit_per_minute: int = 100
    
    # Polymarket API
    gamma_url: str = "https://gamma-api.polymarket.com"
    clob_url: str = "https://clob.polymarket.com"
    data_url: str = "https://data-api.polymarket.com"
    polymarket_api_key: str | None = None
    
    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
