from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:72b"
    ollama_timeout_seconds: int = 120

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def ollama_chat_url(self) -> str:
        return f"{self.ollama_base_url.rstrip('/')}/api/chat"


@lru_cache
def get_settings() -> Settings:
    return Settings()
