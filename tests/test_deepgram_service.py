import httpx
import pytest

from app.config import Settings
from app.services.deepgram_service import DeepgramService, DeepgramServiceError


def make_response(status_code=200, json_data=None, text=None):
    request = httpx.Request("POST", "https://api.deepgram.com/v1/listen")
    if json_data is not None:
        return httpx.Response(status_code, json=json_data, request=request)
    return httpx.Response(status_code, text=text or "", request=request)


def deepgram_payload(transcript="Hello Rex", confidence=0.93):
    return {
        "metadata": {
            "request_id": "deepgram-request-1",
            "duration": 1.42,
        },
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {
                            "transcript": transcript,
                            "confidence": confidence,
                            "detected_language": "en",
                        }
                    ]
                }
            ]
        },
    }


@pytest.mark.asyncio
async def test_transcribe_audio_posts_audio_to_deepgram(monkeypatch):
    calls = []

    async def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        return make_response(json_data=deepgram_payload())

    monkeypatch.setattr("app.services.deepgram_service.request_with_retries", fake_request)
    service = DeepgramService(
        Settings(
            deepgram_api_key="test-key",
            deepgram_model="nova-3",
            deepgram_language="en-US",
        )
    )

    result = await service.transcribe_audio(
        b"audio-bytes",
        content_type="audio/mp4",
        filename="voice.m4a",
    )

    assert result["transcript"] == "Hello Rex"
    assert result["confidence"] == 0.93
    assert result["duration_seconds"] == 1.42
    assert result["metadata"]["request_id"] == "deepgram-request-1"
    assert result["metadata"]["filename"] == "voice.m4a"
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == "https://api.deepgram.com/v1/listen"
    assert calls[0]["headers"]["Authorization"] == "Token test-key"
    assert calls[0]["headers"]["Content-Type"] == "audio/mp4"
    assert calls[0]["params"]["model"] == "nova-3"
    assert calls[0]["params"]["language"] == "en-US"
    assert calls[0]["params"]["smart_format"] == "true"
    assert calls[0]["content"] == b"audio-bytes"


@pytest.mark.asyncio
async def test_transcribe_audio_requires_configuration():
    service = DeepgramService(Settings(deepgram_api_key=None))

    with pytest.raises(DeepgramServiceError) as exc_info:
        await service.transcribe_audio(b"audio", content_type="audio/mp4")

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Voice transcription is not configured."


@pytest.mark.asyncio
async def test_transcribe_audio_rejects_empty_audio():
    service = DeepgramService(Settings(deepgram_api_key="test-key"))

    with pytest.raises(DeepgramServiceError) as exc_info:
        await service.transcribe_audio(b"", content_type="audio/mp4")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "I did not catch any audio."


@pytest.mark.asyncio
async def test_transcribe_audio_rejects_empty_transcript(monkeypatch):
    async def fake_request(method, url, **kwargs):
        return make_response(json_data=deepgram_payload(transcript=""))

    monkeypatch.setattr("app.services.deepgram_service.request_with_retries", fake_request)
    service = DeepgramService(Settings(deepgram_api_key="test-key"))

    with pytest.raises(DeepgramServiceError) as exc_info:
        await service.transcribe_audio(b"audio", content_type="audio/mp4")

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "I did not catch any audio."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected_status", "expected_detail"),
    [
        (401, 503, "Invalid token"),
        (403, 503, "Invalid token"),
        (400, 400, "Bad audio"),
        (413, 413, "Voice recording is too long."),
        (429, 503, "Rate limited"),
        (500, 503, "Vendor down"),
    ],
)
async def test_transcribe_audio_maps_deepgram_errors(
    monkeypatch,
    status_code,
    expected_status,
    expected_detail,
):
    async def fake_request(method, url, **kwargs):
        return make_response(status_code, json_data={"err_msg": expected_detail})

    monkeypatch.setattr("app.services.deepgram_service.request_with_retries", fake_request)
    service = DeepgramService(Settings(deepgram_api_key="test-key"))

    with pytest.raises(DeepgramServiceError) as exc_info:
        await service.transcribe_audio(b"audio", content_type="audio/mp4")

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail == expected_detail


@pytest.mark.asyncio
async def test_transcribe_audio_maps_network_errors(monkeypatch):
    async def fake_request(method, url, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr("app.services.deepgram_service.request_with_retries", fake_request)
    service = DeepgramService(Settings(deepgram_api_key="test-key"))

    with pytest.raises(DeepgramServiceError) as exc_info:
        await service.transcribe_audio(b"audio", content_type="audio/mp4")

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Cannot reach Deepgram right now."
