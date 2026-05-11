from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    grok_api_key: Optional[str] = None
    grok_base_url: str = "https://api.x.ai/v1"
    grok_model: Optional[str] = None
    grok_timeout_seconds: int = 120

    supabase_url: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    supabase_conversations_table: str = "conversations"
    supabase_messages_table: str = "messages"
    supabase_long_term_memory_table: str = "long_term_memory"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def grok_chat_url(self) -> str:
        return f"{self.grok_base_url.rstrip('/')}/chat/completions"

    @property
    def supabase_rest_url(self) -> Optional[str]:
        if not self.supabase_url:
            return None

        return f"{self.supabase_url.rstrip('/')}/rest/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
