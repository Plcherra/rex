import pytest

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
