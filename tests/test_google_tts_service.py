import base64

import httpx
import pytest

from app.config import Settings
from app.services.google_tts_service import GoogleTTSService, GoogleTTSServiceError


def make_response(status_code=200, json_data=None, text=None):
    request = httpx.Request("POST", "https://texttospeech.googleapis.com/v1/text:synthesize")
    if json_data is not None:
        return httpx.Response(status_code, json=json_data, request=request)
    return httpx.Response(status_code, text=text or "", request=request)


def configured_settings(**overrides):
    values = {
        "google_tts_project_id": "rex-voice",
        "google_tts_credentials_json": '{"type":"service_account"}',
        "google_application_credentials": None,
        "google_tts_voice_name": "en-US-Neural2-J",
        "google_tts_language_code": "en-US",
        "google_tts_audio_encoding": "MP3",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.asyncio
async def test_synthesize_speech_posts_to_google_tts(monkeypatch):
    calls = []
    audio_base64 = base64.b64encode(b"mp3-bytes").decode()

    async def fake_request(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        return make_response(json_data={"audioContent": audio_base64})

    monkeypatch.setattr(
        "app.services.google_tts_service.request_with_retries",
        fake_request,
    )
    service = GoogleTTSService(configured_settings())
    monkeypatch.setattr(service, "_access_token", lambda: async_token("access-token"))

    result = await service.synthesize_speech("Hey Rex")

    assert result["audio_content_type"] == "audio/mpeg"
    assert result["audio_base64"] == audio_base64
    assert result["audio_encoding"] == "MP3"
    assert result["voice_name"] == "en-US-Neural2-J"
    assert result["language_code"] == "en-US"
    assert result["metadata"]["vendor"] == "google_tts"
    assert result["metadata"]["text_character_count"] == 7
    assert calls[0]["method"] == "POST"
    assert calls[0]["url"] == "https://texttospeech.googleapis.com/v1/text:synthesize"
    assert calls[0]["headers"]["Authorization"] == "Bearer access-token"
    assert calls[0]["headers"]["x-goog-user-project"] == "rex-voice"
    assert calls[0]["json"]["input"]["text"] == "Hey Rex"
    assert calls[0]["json"]["voice"]["name"] == "en-US-Neural2-J"
    assert calls[0]["json"]["audioConfig"]["audioEncoding"] == "MP3"


async def async_token(token):
    return token


@pytest.mark.asyncio
async def test_synthesize_speech_requires_config():
    service = GoogleTTSService(Settings(_env_file=None))

    with pytest.raises(GoogleTTSServiceError) as exc_info:
        await service.synthesize_speech("Hey Rex")

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Voice playback is not configured."


@pytest.mark.asyncio
async def test_synthesize_speech_rejects_empty_text():
    service = GoogleTTSService(configured_settings())

    with pytest.raises(GoogleTTSServiceError) as exc_info:
        await service.synthesize_speech("   ")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Text to speak cannot be empty."


@pytest.mark.asyncio
async def test_synthesize_speech_rejects_long_text():
    service = GoogleTTSService(configured_settings())

    with pytest.raises(GoogleTTSServiceError) as exc_info:
        await service.synthesize_speech("x" * 5001)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Text is too long for voice playback."


@pytest.mark.asyncio
async def test_synthesize_speech_maps_invalid_credentials(monkeypatch):
    service = GoogleTTSService(configured_settings(google_tts_credentials_json="not-json"))

    with pytest.raises(GoogleTTSServiceError) as exc_info:
        await service.synthesize_speech("Hey Rex")

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Google Text-to-Speech credentials are invalid."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected_status", "expected_detail"),
    [
        (400, 400, "Invalid voice"),
        (401, 503, "Invalid credentials"),
        (403, 503, "Invalid credentials"),
        (429, 503, "Rate limited"),
        (500, 503, "Vendor down"),
    ],
)
async def test_synthesize_speech_maps_google_errors(
    monkeypatch,
    status_code,
    expected_status,
    expected_detail,
):
    async def fake_request(method, url, **kwargs):
        return make_response(
            status_code,
            json_data={"error": {"message": expected_detail}},
        )

    monkeypatch.setattr(
        "app.services.google_tts_service.request_with_retries",
        fake_request,
    )
    service = GoogleTTSService(configured_settings())
    monkeypatch.setattr(service, "_access_token", lambda: async_token("access-token"))

    with pytest.raises(GoogleTTSServiceError) as exc_info:
        await service.synthesize_speech("Hey Rex")

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail == expected_detail


@pytest.mark.asyncio
async def test_synthesize_speech_maps_network_errors(monkeypatch):
    async def fake_request(method, url, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(
        "app.services.google_tts_service.request_with_retries",
        fake_request,
    )
    service = GoogleTTSService(configured_settings())
    monkeypatch.setattr(service, "_access_token", lambda: async_token("access-token"))

    with pytest.raises(GoogleTTSServiceError) as exc_info:
        await service.synthesize_speech("Hey Rex")

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Cannot reach Google Text-to-Speech right now."


@pytest.mark.asyncio
async def test_synthesize_speech_rejects_missing_audio_content(monkeypatch):
    async def fake_request(method, url, **kwargs):
        return make_response(json_data={})

    monkeypatch.setattr(
        "app.services.google_tts_service.request_with_retries",
        fake_request,
    )
    service = GoogleTTSService(configured_settings())
    monkeypatch.setattr(service, "_access_token", lambda: async_token("access-token"))

    with pytest.raises(GoogleTTSServiceError) as exc_info:
        await service.synthesize_speech("Hey Rex")

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "Google Text-to-Speech returned no audio."
