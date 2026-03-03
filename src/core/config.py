from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=True)

    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    DB_HOST: str
    DB_PORT: int

    REDIS_HOST: str
    REDIS_PORT: int
    CACHE_TTL: int = 7200

    GROQ_API_KEY: str
    MODEL_NAME: str = "llama-3.3-70b-versatile"
    SLACK_BOT_TOKEN: str
    SLACK_SIGNING_SECRET: str

@lru_cache()
def get_settings():
    return Settings()