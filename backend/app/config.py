from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_environment: str = "development"
    app_timezone: str = "America/New_York"
    cors_allowed_origins: str = ""

    grok_api_key: Optional[str] = None
    grok_base_url: str = "https://api.x.ai/v1"
    grok_model: Optional[str] = None
    grok_timeout_seconds: int = 120

    supabase_url: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    supabase_conversations_table: str = "conversations"
    supabase_messages_table: str = "messages"
    supabase_long_term_memory_table: str = "long_term_memory"
    supabase_memory_corrections_table: str = "memory_corrections"
    supabase_memory_candidates_table: str = "memory_candidates"
    supabase_voice_turns_table: str = "voice_turns"

    deepgram_api_key: Optional[str] = None
    deepgram_model: str = "nova-3"
    deepgram_language: str = "en-US"
    deepgram_base_url: str = "https://api.deepgram.com/v1"
    deepgram_timeout_seconds: int = 60
    deepgram_endpointing_ms: int = 3000

    google_tts_project_id: Optional[str] = None
    google_tts_credentials_json: Optional[str] = None
    google_application_credentials: Optional[str] = None
    google_tts_base_url: str = "https://texttospeech.googleapis.com/v1"
    google_tts_voice_name: str = "en-US-Neural2-J"
    google_tts_language_code: str = "en-US"
    google_tts_audio_encoding: str = "MP3"
    google_tts_speaking_rate: float = 1.14
    google_tts_pitch: float = 0.0
    google_tts_timeout_seconds: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def grok_chat_url(self) -> str:
        return f"{self.grok_base_url.rstrip('/')}/chat/completions"

    @property
    def supabase_rest_url(self) -> Optional[str]:
        if not self.supabase_url:
            return None

        return f"{self.supabase_url.rstrip('/')}/rest/v1"

    @property
    def deepgram_transcription_url(self) -> str:
        return f"{self.deepgram_base_url.rstrip('/')}/listen"

    @property
    def google_tts_is_configured(self) -> bool:
        return bool(
            self.google_tts_project_id
            and (
                self.google_tts_credentials_json
                or self.google_application_credentials
            )
        )

    @property
    def google_tts_synthesize_url(self) -> str:
        return f"{self.google_tts_base_url.rstrip('/')}/text:synthesize"

    @property
    def cloud_voice_is_configured(self) -> bool:
        return bool(self.deepgram_api_key and self.google_tts_is_configured)

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
