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

    REDIS_HOST: str
    REDIS_PORT: int
    GROQ_API_KEY: str
    SLACK_BOT_TOKEN: str
    SLACK_SIGNING_SECRET: str

@lru_cache()
def get_settings():
    return Settings()