import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_chat_service, get_deepgram_service, get_google_tts_service
from app.main import app
from app.services.ai_service import AIServiceError
from app.services.chat_service import ConversationNotFoundError
from app.services.deepgram_service import DeepgramServiceError
from app.services.google_tts_service import GoogleTTSServiceError
from app.services.memory_service import MemoryServiceError


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class FakeDeepgramService:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    async def transcribe_audio(self, audio_bytes, content_type, filename=None):
        self.calls.append(
            {
                "audio_bytes": audio_bytes,
                "content_type": content_type,
                "filename": filename,
            }
        )
        if self.error is not None:
            raise self.error

        return {
            "transcript": "Hey Rex",
            "confidence": 0.95,
            "duration_seconds": 1.2,
            "metadata": {
                "request_id": "request-1",
                "model": "nova-3",
                "language": "en-US",
            },
        }


class FakeGoogleTTSService:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    async def synthesize_speech(self, text):
        self.calls.append({"text": text})
        if self.error is not None:
            raise self.error

        return {
            "audio_content_type": "audio/mpeg",
            "audio_base64": "bXAzLWJ5dGVz",
            "audio_encoding": "MP3",
            "voice_name": "en-US-Neural2-J",
            "language_code": "en-US",
            "metadata": {
                "vendor": "google_tts",
                "text_character_count": len(text.strip()),
            },
        }


class FakeChatService:
    def __init__(self, error=None, metadata_error=None):
        self.error = error
        self.metadata_error = metadata_error
        self.calls = []
        self.voice_metadata_calls = []

    async def send_message(self, message, conversation_id=None, file=None):
        self.calls.append(
            {
                "message": message,
                "conversation_id": conversation_id,
                "file": file,
            }
        )
        if self.error is not None:
            raise self.error

        resolved_conversation_id = conversation_id or "conversation-voice"
        return {
            "conversation_id": resolved_conversation_id,
            "response": "Rex voice response",
            "user_message": {
                "id": "user-message-1",
                "conversation_id": resolved_conversation_id,
                "role": "user",
                "content": message,
                "timestamp": "2026-05-15T22:00:00Z",
            },
            "assistant_message": {
                "id": "assistant-message-1",
                "conversation_id": resolved_conversation_id,
                "role": "assistant",
                "content": "Rex voice response",
                "timestamp": "2026-05-15T22:00:01Z",
            },
            "messages": [
                {
                    "id": "user-message-1",
                    "conversation_id": resolved_conversation_id,
                    "role": "user",
                    "content": message,
                    "timestamp": "2026-05-15T22:00:00Z",
                },
                {
                    "id": "assistant-message-1",
                    "conversation_id": resolved_conversation_id,
                    "role": "assistant",
                    "content": "Rex voice response",
                    "timestamp": "2026-05-15T22:00:01Z",
                },
            ],
        }

    async def save_voice_turn_metadata(self, **kwargs):
        self.voice_metadata_calls.append(kwargs)
        if self.metadata_error is not None:
            raise self.metadata_error

        return {
            "id": "voice-turn-1",
            **kwargs,
            "created_at": "2026-05-15T22:00:02Z",
        }


def override_deepgram_service(fake_deepgram_service):
    app.dependency_overrides[get_deepgram_service] = lambda: fake_deepgram_service


def override_google_tts_service(fake_google_tts_service):
    app.dependency_overrides[get_google_tts_service] = lambda: fake_google_tts_service


def override_chat_service(fake_chat_service):
    app.dependency_overrides[get_chat_service] = lambda: fake_chat_service


def test_transcribe_voice_upload_success(client):
    fake_deepgram_service = FakeDeepgramService()
    override_deepgram_service(fake_deepgram_service)

    response = client.post(
        "/voice/transcribe",
        files={"audio": ("voice.m4a", b"audio-bytes", "audio/mp4")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["transcript"] == "Hey Rex"
    assert data["confidence"] == 0.95
    assert data["duration_seconds"] == 1.2
    assert data["metadata"]["request_id"] == "request-1"
    assert fake_deepgram_service.calls == [
        {
            "audio_bytes": b"audio-bytes",
            "content_type": "audio/mp4",
            "filename": "voice.m4a",
        }
    ]


def test_transcribe_voice_uses_explicit_mime_type(client):
    fake_deepgram_service = FakeDeepgramService()
    override_deepgram_service(fake_deepgram_service)

    response = client.post(
        "/voice/transcribe",
        data={"input_mime_type": "audio/aac"},
        files={"audio": ("voice.bin", b"audio-bytes", "application/octet-stream")},
    )

    assert response.status_code == 200
    assert fake_deepgram_service.calls[0]["content_type"] == "audio/aac"


def test_transcribe_voice_rejects_unsupported_audio_type(client):
    override_deepgram_service(FakeDeepgramService())

    response = client.post(
        "/voice/transcribe",
        files={"audio": ("voice.txt", b"not-audio", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["detail"] == (
        "Unsupported audio type. Use m4a/aac, mp3, wav, or webm audio."
    )


def test_transcribe_voice_rejects_empty_audio(client):
    override_deepgram_service(FakeDeepgramService())

    response = client.post(
        "/voice/transcribe",
        files={"audio": ("voice.m4a", b"", "audio/mp4")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "I did not catch any audio."


def test_transcribe_voice_rejects_large_audio(client):
    override_deepgram_service(FakeDeepgramService())

    response = client.post(
        "/voice/transcribe",
        files={"audio": ("voice.m4a", b"x" * (10 * 1024 * 1024 + 1), "audio/mp4")},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Voice recording is too long."


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            DeepgramServiceError("Voice transcription is not configured.", 503),
            503,
            "Voice transcription is not configured.",
        ),
        (
            DeepgramServiceError("I did not catch any audio.", 422),
            422,
            "I did not catch any audio.",
        ),
        (
            DeepgramServiceError("Deepgram is rate limiting transcription right now.", 503),
            503,
            "Deepgram is rate limiting transcription right now.",
        ),
    ],
)
def test_transcribe_voice_maps_service_errors(
    client,
    error,
    expected_status,
    expected_detail,
):
    override_deepgram_service(FakeDeepgramService(error=error))

    response = client.post(
        "/voice/transcribe",
        files={"audio": ("voice.m4a", b"audio-bytes", "audio/mp4")},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail


def test_synthesize_voice_success(client):
    fake_google_tts_service = FakeGoogleTTSService()
    override_google_tts_service(fake_google_tts_service)

    response = client.post(
        "/voice/synthesize",
        json={"text": "Hey Rex"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["audio_content_type"] == "audio/mpeg"
    assert data["audio_base64"] == "bXAzLWJ5dGVz"
    assert data["audio_encoding"] == "MP3"
    assert data["voice_name"] == "en-US-Neural2-J"
    assert data["language_code"] == "en-US"
    assert data["metadata"]["vendor"] == "google_tts"
    assert fake_google_tts_service.calls == [{"text": "Hey Rex"}]


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            GoogleTTSServiceError("Voice playback is not configured.", 503),
            503,
            "Voice playback is not configured.",
        ),
        (
            GoogleTTSServiceError("Text to speak cannot be empty.", 400),
            400,
            "Text to speak cannot be empty.",
        ),
        (
            GoogleTTSServiceError("Google Text-to-Speech is rate limiting voice playback.", 503),
            503,
            "Google Text-to-Speech is rate limiting voice playback.",
        ),
    ],
)
def test_synthesize_voice_maps_service_errors(
    client,
    error,
    expected_status,
    expected_detail,
):
    override_google_tts_service(FakeGoogleTTSService(error=error))

    response = client.post(
        "/voice/synthesize",
        json={"text": "Hey Rex"},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail


def test_voice_turn_completes_full_non_streaming_pipeline(client):
    fake_deepgram_service = FakeDeepgramService()
    fake_chat_service = FakeChatService()
    fake_google_tts_service = FakeGoogleTTSService()
    override_deepgram_service(fake_deepgram_service)
    override_chat_service(fake_chat_service)
    override_google_tts_service(fake_google_tts_service)

    response = client.post(
        "/voice/turn",
        data={"conversation_id": "conversation-existing"},
        files={"audio": ("voice.m4a", b"audio-bytes", "audio/mp4")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == "conversation-existing"
    assert data["transcript"] == "Hey Rex"
    assert data["transcript_confidence"] == 0.95
    assert data["response_text"] == "Rex voice response"
    assert data["audio_content_type"] == "audio/mpeg"
    assert data["audio_base64"] == "bXAzLWJ5dGVz"
    assert data["audio_encoding"] == "MP3"
    assert data["voice_name"] == "en-US-Neural2-J"
    assert data["language_code"] == "en-US"
    assert len(data["messages"]) == 2
    assert data["voice_metadata"]["record"]["id"] == "voice-turn-1"
    assert fake_deepgram_service.calls[0]["audio_bytes"] == b"audio-bytes"
    assert fake_chat_service.calls == [
        {
            "message": "Hey Rex",
            "conversation_id": "conversation-existing",
            "file": None,
        }
    ]
    assert fake_google_tts_service.calls == [{"text": "Rex voice response"}]
    assert fake_chat_service.voice_metadata_calls[0]["conversation_id"] == (
        "conversation-existing"
    )
    assert fake_chat_service.voice_metadata_calls[0]["user_message_id"] == (
        "user-message-1"
    )
    assert fake_chat_service.voice_metadata_calls[0]["assistant_message_id"] == (
        "assistant-message-1"
    )
    assert fake_chat_service.voice_metadata_calls[0]["input_mime_type"] == "audio/mp4"
    assert fake_chat_service.voice_metadata_calls[0]["output_audio_encoding"] == "MP3"


def test_voice_turn_creates_new_conversation_when_missing_id(client):
    fake_chat_service = FakeChatService()
    override_deepgram_service(FakeDeepgramService())
    override_chat_service(fake_chat_service)
    override_google_tts_service(FakeGoogleTTSService())

    response = client.post(
        "/voice/turn",
        files={"audio": ("voice.m4a", b"audio-bytes", "audio/mp4")},
    )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "conversation-voice"
    assert fake_chat_service.calls[0]["conversation_id"] is None


@pytest.mark.parametrize(
    ("dependency_error", "expected_status", "expected_detail"),
    [
        (
            DeepgramServiceError("Voice transcription is not configured.", 503),
            503,
            "Voice transcription is not configured.",
        ),
        (
            ConversationNotFoundError(),
            404,
            "Conversation not found.",
        ),
        (
            AIServiceError("Grok unavailable.", 503),
            503,
            "Grok unavailable.",
        ),
        (
            MemoryServiceError("Supabase unavailable.", 503),
            503,
            "Supabase unavailable.",
        ),
        (
            GoogleTTSServiceError("Voice playback is not configured.", 503),
            503,
            "Voice playback is not configured.",
        ),
    ],
)
def test_voice_turn_maps_pipeline_errors(
    client,
    dependency_error,
    expected_status,
    expected_detail,
):
    override_deepgram_service(FakeDeepgramService())
    override_chat_service(FakeChatService())
    override_google_tts_service(FakeGoogleTTSService())
    if isinstance(dependency_error, DeepgramServiceError):
        override_deepgram_service(FakeDeepgramService(error=dependency_error))
    elif isinstance(dependency_error, GoogleTTSServiceError):
        override_google_tts_service(FakeGoogleTTSService(error=dependency_error))
    else:
        override_chat_service(FakeChatService(error=dependency_error))

    response = client.post(
        "/voice/turn",
        files={"audio": ("voice.m4a", b"audio-bytes", "audio/mp4")},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail


def test_voice_turn_ignores_metadata_persistence_failures(client):
    fake_chat_service = FakeChatService(metadata_error=RuntimeError("metadata failed"))
    override_deepgram_service(FakeDeepgramService())
    override_chat_service(fake_chat_service)
    override_google_tts_service(FakeGoogleTTSService())

    response = client.post(
        "/voice/turn",
        files={"audio": ("voice.m4a", b"audio-bytes", "audio/mp4")},
    )

    assert response.status_code == 200
    assert "record" not in response.json()["voice_metadata"]
    assert len(fake_chat_service.voice_metadata_calls) == 1
