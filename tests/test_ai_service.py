import pytest
import httpx

from app.config import Settings
from app.services.ai_service import AIService, AIServiceError


def test_ai_service_does_not_inject_personality_prompt():
    service = AIService(
        Settings(
            grok_api_key="test-key",
            grok_model="grok-test",
        )
    )
    messages = [
        {"role": "system", "content": "PromptService-owned system prompt"},
        {"role": "user", "content": "Hello Rex"},
    ]

    prompt_messages = service._validated_prompt_messages(messages)

    assert prompt_messages == messages


def test_ai_service_still_validates_required_grok_config():
    service = AIService(Settings(grok_api_key=None, grok_model="grok-test"))

    with pytest.raises(AIServiceError) as error:
        service._validated_prompt_messages([{"role": "user", "content": "Hello"}])

    assert error.value.detail == "Grok API key is not configured."


def test_ai_service_surfaces_grok_capacity_errors():
    service = AIService(Settings(grok_api_key="test-key", grok_model="grok-test"))
    response = httpx.Response(
        429,
        json={
            "code": "Some resource has been exhausted",
            "error": "The model is currently at capacity due to high demand.",
        },
    )

    error = service._http_status_error(response)

    assert error.status_code == 503
    assert error.detail == "The model is currently at capacity due to high demand."


def test_ai_service_surfaces_invalid_model_errors():
    service = AIService(Settings(grok_api_key="test-key", grok_model="grok-test"))
    response = httpx.Response(
        400,
        json={
            "code": "Client specified an invalid argument",
            "error": "Model not found: grok-test",
        },
    )

    error = service._http_status_error(response)

    assert error.status_code == 502
    assert error.detail == "Model not found: grok-test"
