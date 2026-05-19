from collections.abc import AsyncIterator
import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.services.voice_stream_session as voice_stream_session_module
from app.dependencies import (
    get_chat_service,
    get_deepgram_streaming_service,
    get_google_tts_service,
)
from app.main import app
from app.services.deepgram_service import DeepgramServiceError
from app.services.google_tts_service import GoogleTTSServiceError
from app.services.voice_stream_session import VoiceStreamSession


@pytest.fixture
def client():
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class FakeDeepgramStreamingService:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    async def transcribe_audio_stream(
        self,
        audio_chunks: AsyncIterator[bytes],
        content_type: str,
        sample_rate: int = 16000,
        on_transcript=None,
    ):
        chunks = []
        async for chunk in audio_chunks:
            chunks.append(chunk)
        self.calls.append(
            {
                "audio_chunks": chunks,
                "content_type": content_type,
                "sample_rate": sample_rate,
            }
        )
        if self.error is not None:
            raise self.error
        if on_transcript is not None:
            await on_transcript(
                {
                    "event": "transcript.partial",
                    "transcript": "Hey",
                    "confidence": 0.7,
                    "metadata": {"vendor": "deepgram"},
                }
            )
        return {
            "transcript": "Hey Rex",
            "confidence": 0.96,
            "duration_seconds": 1.4,
            "metadata": {"request_id": "stream-request-1"},
        }


class SlowDeepgramStreamingService(FakeDeepgramStreamingService):
    async def transcribe_audio_stream(
        self,
        audio_chunks: AsyncIterator[bytes],
        content_type: str,
        sample_rate: int = 16000,
        on_transcript=None,
    ):
        async for _ in audio_chunks:
            pass
        await asyncio.sleep(30)
        return await super().transcribe_audio_stream(
            self._empty_chunks(),
            content_type=content_type,
            sample_rate=sample_rate,
            on_transcript=on_transcript,
        )

    async def _empty_chunks(self):
        if False:
            yield b""


class FakeChatService:
    def __init__(self):
        self.stream_calls = []
        self.metadata_calls = []

    async def stream_message(self, message, conversation_id=None, file=None):
        self.stream_calls.append(
            {
                "message": message,
                "conversation_id": conversation_id,
                "file": file,
            }
        )
        resolved_conversation_id = conversation_id or "conversation-stream"
        yield {"event": "conversation", "conversation_id": resolved_conversation_id}
        yield {"event": "token", "token": "Rex "}
        yield {"event": "token", "token": "streaming "}
        yield {"event": "token", "token": "response."}
        yield {
            "event": "done",
            "conversation_id": resolved_conversation_id,
            "response": "Rex streaming response.",
            "messages": [
                {
                    "id": "user-message-1",
                    "conversation_id": resolved_conversation_id,
                    "role": "user",
                    "content": message,
                    "timestamp": "2026-05-17T00:00:00Z",
                },
                {
                    "id": "assistant-message-1",
                    "conversation_id": resolved_conversation_id,
                    "role": "assistant",
                    "content": "Rex streaming response.",
                    "timestamp": "2026-05-17T00:00:01Z",
                },
            ],
        }

    async def save_voice_turn_metadata(self, **kwargs):
        self.metadata_calls.append(kwargs)
        return {"id": "voice-turn-stream", **kwargs}


class FakeGoogleTTSService:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    async def synthesize_speech(self, text):
        self.calls.append(text)
        if self.error is not None:
            raise self.error
        return {
            "audio_content_type": "audio/mpeg",
            "audio_base64": "bXAzLWJ5dGVz",
            "audio_encoding": "MP3",
            "voice_name": "en-US-Neural2-J",
            "language_code": "en-US",
            "metadata": {"vendor": "google_tts"},
        }


class FakeWebSocket:
    def __init__(self):
        self.events = []

    async def send_json(self, payload):
        self.events.append(payload)


class FakeLiveTranscription:
    def __init__(self):
        self.closed = False

    async def finish(self):
        return {
            "transcript": "Hey Rex",
            "confidence": 0.91,
            "duration_seconds": 1.2,
            "metadata": {"transport": "websocket-live"},
        }

    async def close(self):
        self.closed = True


class FakeLiveDeepgramStreamingService:
    settings = SimpleNamespace(deepgram_endpointing_ms=3000)


def override_services(
    deepgram_streaming_service=None,
    chat_service=None,
    google_tts_service=None,
):
    app.dependency_overrides[get_deepgram_streaming_service] = (
        lambda: deepgram_streaming_service or FakeDeepgramStreamingService()
    )
    app.dependency_overrides[get_chat_service] = (
        lambda: chat_service or FakeChatService()
    )
    app.dependency_overrides[get_google_tts_service] = (
        lambda: google_tts_service or FakeGoogleTTSService()
    )


def receive_until(websocket, event_name):
    while True:
        event = websocket.receive_json()
        if event["event"] == event_name:
            return event


def test_voice_stream_completes_streaming_turn(client):
    deepgram = FakeDeepgramStreamingService()
    chat = FakeChatService()
    tts = FakeGoogleTTSService()
    override_services(deepgram, chat, tts)

    with client.websocket_connect("/voice/stream") as websocket:
        websocket.send_json(
            {
                "event": "session.start",
                "conversation_id": "conversation-existing",
                "input_mime_type": "audio/linear16",
                "sample_rate": 16000,
            }
        )
        started = websocket.receive_json()
        assert started["event"] == "session.started"
        assert started["conversation_id"] == "conversation-existing"

        websocket.send_bytes(b"pcm-frame-1")
        received = websocket.receive_json()
        assert received["event"] == "audio.received"
        assert received["chunk_count"] == 1

        websocket.send_bytes(b"pcm-frame-2")
        websocket.receive_json()
        websocket.send_json({"event": "utterance.end"})

        partial = receive_until(websocket, "transcript.partial")
        assert partial["transcript"] == "Hey"

        final = receive_until(websocket, "transcript.final")
        assert final["transcript"] == "Hey Rex"
        assert final["confidence"] == 0.96

        token = receive_until(websocket, "assistant.token")
        assert token["token"] == "Rex "

        audio_chunk = receive_until(websocket, "assistant.audio_chunk")
        assert audio_chunk["text"] == "Rex streaming response."
        assert audio_chunk["audio_base64"] == "bXAzLWJ5dGVz"

        messages = receive_until(websocket, "messages.updated")
        assert messages["conversation_id"] == "conversation-existing"
        assert messages["voice_metadata"]["record"]["id"] == "voice-turn-stream"

        done = receive_until(websocket, "assistant.done")
        assert done["conversation_id"] == "conversation-existing"
        assert done["response_text"] == "Rex streaming response."
        assert "stt_ms" in done["timings"]
        assert "turn_ms" in done["timings"]

        websocket.send_json({"event": "session.end"})
        ended = websocket.receive_json()
        assert ended["event"] == "session.ended"

    assert deepgram.calls == [
        {
            "audio_chunks": [b"pcm-frame-1", b"pcm-frame-2"],
            "content_type": "audio/linear16",
            "sample_rate": 16000,
        }
    ]
    assert chat.stream_calls == [
        {
            "message": "Hey Rex",
            "conversation_id": "conversation-existing",
            "file": None,
        }
    ]
    assert tts.calls == ["Rex streaming response."]
    assert chat.metadata_calls[0]["conversation_id"] == "conversation-existing"
    assert chat.metadata_calls[0]["user_message_id"] == "user-message-1"
    assert chat.metadata_calls[0]["assistant_message_id"] == "assistant-message-1"


@pytest.mark.asyncio
async def test_voice_stream_live_transcript_idle_starts_turn(monkeypatch):
    async def instant_sleep(_delay):
        return None

    monkeypatch.setattr(voice_stream_session_module.asyncio, "sleep", instant_sleep)
    websocket = FakeWebSocket()
    chat = FakeChatService()
    session = VoiceStreamSession(
        websocket=websocket,
        deepgram_streaming_service=FakeLiveDeepgramStreamingService(),
        chat_service=chat,
        google_tts_service=FakeGoogleTTSService(),
    )
    session.conversation_id = "conversation-existing"
    session._live_transcription = FakeLiveTranscription()
    transcript_timestamp = 10.0
    session._last_live_transcript_at = transcript_timestamp

    await session._process_live_utterance_after_transcript_idle(
        transcript_timestamp,
    )
    assert session._active_turn_task is not None
    await session._active_turn_task

    assert chat.stream_calls[0]["message"] == "Hey Rex"
    assert any(event["event"] == "assistant.done" for event in websocket.events)


def test_voice_stream_creates_conversation_when_missing_id(client):
    chat = FakeChatService()
    override_services(chat_service=chat)

    with client.websocket_connect("/voice/stream") as websocket:
        websocket.send_json({"event": "session.start"})
        assert websocket.receive_json()["event"] == "session.started"
        websocket.send_bytes(b"pcm-frame")
        websocket.receive_json()
        websocket.send_json({"event": "utterance.end"})

        done = receive_until(websocket, "assistant.done")
        assert done["conversation_id"] == "conversation-stream"

    assert chat.stream_calls[0]["conversation_id"] is None


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_detail"),
    [
        (
            DeepgramServiceError("Voice transcription is not configured.", 503),
            503,
            "Voice transcription is not configured.",
        ),
        (
            GoogleTTSServiceError("Voice playback is not configured.", 503),
            503,
            "Voice playback is not configured.",
        ),
    ],
)
def test_voice_stream_sends_error_events(
    client,
    error,
    expected_status,
    expected_detail,
):
    deepgram = FakeDeepgramStreamingService()
    tts = FakeGoogleTTSService()
    if isinstance(error, DeepgramServiceError):
        deepgram = FakeDeepgramStreamingService(error=error)
    else:
        tts = FakeGoogleTTSService(error=error)
    override_services(deepgram_streaming_service=deepgram, google_tts_service=tts)

    with client.websocket_connect("/voice/stream") as websocket:
        websocket.send_json({"event": "session.start"})
        websocket.receive_json()
        websocket.send_bytes(b"pcm-frame")
        websocket.receive_json()
        websocket.send_json({"event": "utterance.end"})

        event = receive_until(websocket, "error")
        assert event["status_code"] == expected_status
        assert event["detail"] == expected_detail


def test_voice_stream_rejects_empty_utterance(client):
    override_services()

    with client.websocket_connect("/voice/stream") as websocket:
        websocket.send_json({"event": "session.start"})
        websocket.receive_json()
        websocket.send_json({"event": "utterance.end"})

        event = websocket.receive_json()
        assert event["event"] == "error"
        assert event["code"] == "empty_audio"
        assert event["detail"] == "I did not catch any audio."


def test_voice_stream_interrupts_active_turn(client):
    deepgram = SlowDeepgramStreamingService()
    chat = FakeChatService()
    override_services(deepgram_streaming_service=deepgram, chat_service=chat)

    with client.websocket_connect("/voice/stream") as websocket:
        websocket.send_json({"event": "session.start"})
        assert websocket.receive_json()["event"] == "session.started"
        websocket.send_bytes(b"pcm-frame")
        assert websocket.receive_json()["event"] == "audio.received"
        websocket.send_json({"event": "utterance.end"})
        websocket.send_json({"event": "user.interrupt"})

        interrupted = receive_until(websocket, "session.interrupted")
        assert interrupted["event"] == "session.interrupted"

    assert chat.stream_calls == []
