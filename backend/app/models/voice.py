from typing import Any, Optional

from pydantic import BaseModel, Field


class VoiceTranscriptionResponse(BaseModel):
    transcript: str
    confidence: Optional[float] = None
    duration_seconds: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VoiceSynthesisRequest(BaseModel):
    text: str


class VoiceSynthesisResponse(BaseModel):
    audio_content_type: str
    audio_base64: str
    audio_encoding: str
    voice_name: str
    language_code: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class VoiceTurnResponse(BaseModel):
    conversation_id: str
    transcript: str
    transcript_confidence: Optional[float] = None
    response_text: str
    audio_content_type: str
    audio_base64: str
    audio_encoding: str
    voice_name: str
    language_code: str
    messages: list[dict[str, Any]] = Field(default_factory=list)
    voice_metadata: dict[str, Any] = Field(default_factory=dict)
