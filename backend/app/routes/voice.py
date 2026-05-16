from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.dependencies import get_chat_service, get_deepgram_service, get_google_tts_service
from app.models.voice import (
    VoiceSynthesisRequest,
    VoiceSynthesisResponse,
    VoiceTranscriptionResponse,
    VoiceTurnResponse,
)
from app.services.ai_service import AIServiceError
from app.services.chat_service import ChatService, ConversationNotFoundError
from app.services.deepgram_service import DeepgramService, DeepgramServiceError
from app.services.google_tts_service import GoogleTTSService, GoogleTTSServiceError
from app.services.memory_service import MemoryServiceError


router = APIRouter(prefix="/voice", tags=["voice"])

MAX_AUDIO_UPLOAD_BYTES = 10 * 1024 * 1024
SUPPORTED_AUDIO_TYPES = {
    "audio/aac",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "application/octet-stream",
}


@router.post("/transcribe", response_model=VoiceTranscriptionResponse)
async def transcribe_voice(
    audio: UploadFile = File(...),
    input_mime_type: Optional[str] = Form(None),
    deepgram_service: DeepgramService = Depends(get_deepgram_service),
) -> VoiceTranscriptionResponse:
    audio_bytes, content_type = await _read_audio_upload(audio, input_mime_type)

    try:
        transcription = await deepgram_service.transcribe_audio(
            audio_bytes=audio_bytes,
            content_type=content_type,
            filename=audio.filename,
        )
    except DeepgramServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

    return VoiceTranscriptionResponse(**transcription)


@router.post("/turn", response_model=VoiceTurnResponse)
async def voice_turn(
    audio: UploadFile = File(...),
    conversation_id: Optional[str] = Form(None),
    input_mime_type: Optional[str] = Form(None),
    deepgram_service: DeepgramService = Depends(get_deepgram_service),
    chat_service: ChatService = Depends(get_chat_service),
    google_tts_service: GoogleTTSService = Depends(get_google_tts_service),
) -> VoiceTurnResponse:
    audio_bytes, content_type = await _read_audio_upload(audio, input_mime_type)

    try:
        transcription = await deepgram_service.transcribe_audio(
            audio_bytes=audio_bytes,
            content_type=content_type,
            filename=audio.filename,
        )
        chat_result = await chat_service.send_message(
            message=transcription["transcript"],
            conversation_id=conversation_id,
        )
        synthesis = await google_tts_service.synthesize_speech(chat_result["response"])
    except DeepgramServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    except ConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail="Conversation not found.") from error
    except AIServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    except MemoryServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    except GoogleTTSServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

    user_message = chat_result.get("user_message") or {}
    assistant_message = chat_result.get("assistant_message") or {}
    voice_metadata = {
        "stt": transcription.get("metadata") or {},
        "tts": synthesis.get("metadata") or {},
    }
    try:
        metadata_record = await chat_service.save_voice_turn_metadata(
            conversation_id=chat_result["conversation_id"],
            user_message_id=user_message.get("id"),
            assistant_message_id=assistant_message.get("id"),
            transcript_confidence=transcription.get("confidence"),
            audio_duration_seconds=transcription.get("duration_seconds"),
            input_mime_type=content_type,
            output_audio_encoding=synthesis.get("audio_encoding"),
            metadata={
                "stt": transcription.get("metadata") or {},
                "tts": synthesis.get("metadata") or {},
            },
        )
    except Exception:
        metadata_record = None

    if metadata_record is not None:
        voice_metadata["record"] = {
            key: value
            for key, value in metadata_record.items()
            if key != "metadata"
        }

    return VoiceTurnResponse(
        conversation_id=chat_result["conversation_id"],
        transcript=transcription["transcript"],
        transcript_confidence=transcription.get("confidence"),
        response_text=chat_result["response"],
        audio_content_type=synthesis["audio_content_type"],
        audio_base64=synthesis["audio_base64"],
        audio_encoding=synthesis["audio_encoding"],
        voice_name=synthesis["voice_name"],
        language_code=synthesis["language_code"],
        messages=chat_result.get("messages") or [],
        voice_metadata=voice_metadata,
    )


@router.post("/synthesize", response_model=VoiceSynthesisResponse)
async def synthesize_voice(
    request: VoiceSynthesisRequest,
    google_tts_service: GoogleTTSService = Depends(get_google_tts_service),
) -> VoiceSynthesisResponse:
    try:
        synthesis = await google_tts_service.synthesize_speech(request.text)
    except GoogleTTSServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

    return VoiceSynthesisResponse(**synthesis)


async def _read_audio_upload(
    audio: UploadFile,
    input_mime_type: Optional[str],
) -> tuple[bytes, str]:
    content_type = (input_mime_type or audio.content_type or "").strip().lower()
    if content_type not in SUPPORTED_AUDIO_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported audio type. Use m4a/aac, mp3, wav, or webm audio.",
        )

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="I did not catch any audio.")
    if len(audio_bytes) > MAX_AUDIO_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Voice recording is too long.")

    return audio_bytes, content_type
